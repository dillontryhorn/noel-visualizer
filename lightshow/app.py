"""Local HTTP preview, frame clock, UDP receivers and Unreal DDP relay."""

import base64
from collections import deque
import copy
import hashlib
from dataclasses import dataclass
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import secrets
import socket
import struct
import threading
import tempfile
import time
from urllib.parse import urlsplit

from .effects import EFFECTS, render
from .layout import load_layout_snapshot, pixel_mapping, validate_layout
from .protocols import DDPAssembler, PacketError, SACNMerger, ddp_packets, parse_ddp, parse_sacn

ROOT = Path(__file__).resolve().parents[1]
MAX_LAYOUT_REVISION = 2**53 - 1


class LayoutConflict(ValueError):
    """The editor is saving a layout superseded by another browser."""


def _atomic_write(path, encoded, backup=False):
    """Replace a complete file; a failed write never leaves a truncated layout."""
    path = Path(path)
    staged = []

    def stage(contents):
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as temporary:
            staged.append(Path(temporary.name))
            temporary.write(contents)
            temporary.flush()
            os.fsync(temporary.fileno())
        return staged[-1]

    try:
        pending = stage(encoded)
        if backup and path.exists():
            previous = stage(path.read_bytes())
            os.replace(previous, path.with_suffix(path.suffix + ".bak"))
        os.replace(pending, path)
    finally:
        for temporary in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                # Cleanup cannot turn an already committed replacement into a failure.
                pass


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8080
    udp_host: str = "127.0.0.1"
    ddp_port: int = 4048
    sacn_port: int = 5568
    sacn_multicast: bool = False
    multicast_interface: str = "0.0.0.0"
    universe_size: int | None = None
    start_universe: int | None = None
    relay_host: str = "127.0.0.1"
    relay_port: int = 4049
    relay_enabled: bool = True
    fps: float = 30
    layout: Path = ROOT / "layouts" / "default.json"
    web_dir: Path = ROOT / "web"
    unreal_layout: Path | None = ROOT / "unreal" / "ChristmasLights" / "Content" / "Data" / "default.json"


class LightShowApplication:
    """One frame producer; readers only observe immutable frame snapshots."""

    duration = 120.0

    def __init__(self, config=None):
        self.config = config or Config()
        if not math.isfinite(self.config.fps) or not 1 <= self.config.fps <= 60:
            raise ValueError("FPS must be from 1 to 60")
        for name in ("port", "ddp_port", "sacn_port", "relay_port"):
            value = getattr(self.config, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 65535:
                raise ValueError(f"{name} must be from 0 to 65535")
        self.layout, self._layout_fingerprint = load_layout_snapshot(self.config.layout)
        # Revision tokens are runtime-only. A fresh startup seed prevents an old
        # browser draft from matching a newly loaded layout after a restart.
        self.layout_revision = secrets.randbelow(2**52 - 1) + 1
        if self.config.universe_size is None:
            self.config.universe_size = self.layout["universeSize"]
        if self.config.start_universe is None:
            self.config.start_universe = self.layout["startUniverse"]
        self.mapping = list(pixel_mapping(self.layout))
        self.channel_count = self.layout["channelCount"]
        self.ddp = DDPAssembler(self.channel_count)
        self.sacn = SACNMerger(self.channel_count, self.config.universe_size, self.config.start_universe)
        self.layout.update(universeSize=self.config.universe_size, startUniverse=self.config.start_universe,
                           universeCount=self.sacn.universe_count)
        self.condition = threading.Condition(threading.RLock())
        self.stop_event = threading.Event()
        self.threads, self.udp_sockets = [], {}
        self.http_server = self.relay_socket = None
        self.started = False
        self.mode, self.effect, self.playing = "demo", "aurora", True
        self.brightness, self.speed, self.bpm, self.show_time = .85, 1., 120., 0.
        self.solid_color = "#ffcc88"
        self.fixture_enabled = {fixture["id"]: True for fixture in self.layout["fixtures"]}
        self.live_rgb = bytes(self.channel_count)
        self.frozen_live = self.live_rgb
        self.output_rgb = bytes(self.channel_count)
        self.output_base64 = base64.b64encode(self.output_rgb).decode("ascii")
        self.active_protocol, self.last_packet = None, None
        self.frame, self.measured_fps, self.sacn_sources = 0, 0., 0
        self.frame_times = deque(maxlen=61)
        self.receivers = {"ddp": {"port": self.config.ddp_port, "packets": 0, "errors": 0,
                                  "ignored": 0, "error": None},
                          "sacn": {"port": self.config.sacn_port, "packets": 0, "errors": 0,
                                   "ignored": 0, "error": None}}
        self.relay = {"host": self.config.relay_host, "port": self.config.relay_port,
                      "enabled": self.config.relay_enabled, "error": None, "packets": 0}
        self.relay_sequence = 1
        self._last_tick = None

    def snapshot(self, include_rgb=True):
        with self.condition:
            result = {"mode": self.mode, "effect": self.effect, "playing": self.playing,
                      "brightness": self.brightness, "speed": self.speed, "bpm": self.bpm,
                      "solidColor": self.solid_color, "fps": round(self.measured_fps, 1),
                      "targetFps": self.config.fps, "frame": self.frame, "time": round(self.show_time, 3),
                      "duration": self.duration, "pixelCount": self.layout["pixelCount"],
                      "layoutRevision": self.layout_revision,
                      "channelCount": self.channel_count, "universeSize": self.config.universe_size,
                      "startUniverse": self.config.start_universe, "universeCount": self.sacn.universe_count,
                      "fixtureEnabled": dict(self.fixture_enabled),
                      "receivers": {key: dict(value) for key, value in self.receivers.items()},
                      "relay": dict(self.relay), "lastPacketAge": None if self.last_packet is None
                      else round(max(0., time.monotonic() - self.last_packet), 3),
                      "activeProtocol": self.active_protocol, "sacnSources": self.sacn_sources}
            if include_rgb:
                result["rgb"] = self.output_base64
            return result

    def layout_snapshot(self):
        with self.condition:
            result = copy.deepcopy(self.layout)
            result["revision"] = self.layout_revision
            return result

    def _multicast_membership(self, universe, join=True):
        udp = self.udp_sockets.get("sacn")
        if not self.config.sacn_multicast or udp is None:
            return
        group = socket.inet_aton(f"239.255.{universe >> 8}.{universe & 255}")
        interface = socket.inet_aton(self.config.multicast_interface)
        udp.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP if join else socket.IP_DROP_MEMBERSHIP,
                       group + interface)

    def save_layout(self, data):
        """Validate, persist, then publish the new mapping as one locked change."""
        if not isinstance(data, dict) or set(data) != {"layout", "revision"}:
            raise ValueError("layout save must contain layout and revision")
        revision = data["revision"]
        if isinstance(revision, bool) or not isinstance(revision, int) or not 1 <= revision <= MAX_LAYOUT_REVISION:
            raise ValueError("revision must be a positive JavaScript-safe integer")
        layout = validate_layout(data["layout"])
        encoded = (json.dumps(layout, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if len(encoded) > 8_000_000:
            raise ValueError("saved layout JSON exceeds 8 MB")
        mapping = list(pixel_mapping(layout))
        ddp = DDPAssembler(layout["channelCount"])
        sacn = SACNMerger(layout["channelCount"], layout["universeSize"], layout["startUniverse"])
        with self.condition:
            if revision != self.layout_revision:
                raise LayoutConflict("The saved scene changed or the server restarted. Reload it before saving again.")
            if self.layout_revision == MAX_LAYOUT_REVISION:
                raise ValueError("Restart the server before saving more changes; the revision limit was reached.")
            try:
                disk_fingerprint = hashlib.sha256(Path(self.config.layout).read_bytes()).digest()
            except FileNotFoundError:
                disk_fingerprint = None
            if disk_fingerprint != self._layout_fingerprint:
                raise LayoutConflict("The layout file changed outside the visualizer. Export your draft, then restart the server to load that file before saving again.")
            old_groups = set(range(self.config.start_universe,
                                   self.config.start_universe + self.sacn.universe_count))
            new_groups = set(range(layout["startUniverse"], layout["startUniverse"] + sacn.universe_count))
            joined = []
            try:
                for universe in sorted(new_groups - old_groups):
                    self._multicast_membership(universe)
                    joined.append(universe)
                _atomic_write(self.config.layout, encoded, backup=True)
            except OSError:
                for universe in joined:
                    try:
                        self._multicast_membership(universe, False)
                    except OSError:
                        pass
                raise
            # The primary file is committed. No fallible work precedes publishing it.
            signature = lambda value: [(fixture["id"], fixture["startChannel"], fixture["pixelCount"])
                                       for fixture in value["fixtures"]]
            remapped = self.channel_count != layout["channelCount"] or signature(self.layout) != signature(layout)
            sacn_changed = remapped or self.config.universe_size != layout["universeSize"] or self.config.start_universe != layout["startUniverse"]
            self.fixture_enabled = {fixture["id"]: self.fixture_enabled.get(fixture["id"], True)
                                    for fixture in layout["fixtures"]}
            self.layout, self.mapping, self.channel_count = layout, mapping, layout["channelCount"]
            self.config.universe_size, self.config.start_universe = layout["universeSize"], layout["startUniverse"]
            if remapped:
                self.ddp = ddp
                self.live_rgb = self.frozen_live = self.output_rgb = bytes(self.channel_count)
                self.output_base64 = base64.b64encode(self.output_rgb).decode("ascii")
                self.active_protocol, self.last_packet = None, None
            if sacn_changed:
                self.sacn, self.sacn_sources = sacn, 0
                if self.active_protocol == "sacn":
                    self.live_rgb = self.frozen_live = bytes(self.channel_count)
                    self.active_protocol, self.last_packet = None, None
            self.layout_revision += 1
            self._layout_fingerprint = hashlib.sha256(encoded).digest()
            self.condition.notify_all()
            for universe in sorted(old_groups - new_groups):
                try:
                    self._multicast_membership(universe, False)
                except OSError as error:
                    self.receivers["sacn"]["error"] = f"Could not leave unused multicast group: {error}"
            unreal_sync = {"saved": False}
            unreal_path = self.config.unreal_layout
            if unreal_path is not None and Path(unreal_path).is_file():
                try:
                    if Path(unreal_path).resolve() != Path(self.config.layout).resolve():
                        _atomic_write(unreal_path, encoded)
                    unreal_sync["saved"] = True
                except OSError as error:
                    unreal_sync["error"] = str(error)
            return {"layout": self.layout_snapshot(), "status": self.snapshot(False), "unrealSync": unreal_sync}

    def control(self, data):
        """Validate all requested fields before applying the control atomically."""
        if not isinstance(data, dict):
            raise ValueError("control must be a JSON object")
        if any(not isinstance(key, str) for key in data):
            raise ValueError("control field names must be strings")
        allowed = {"mode", "effect", "playing", "brightness", "speed", "time", "bpm",
                   "fixtureEnabled", "relayEnabled", "solidColor"}
        if set(data) - allowed:
            raise ValueError("unknown control field: " + sorted(set(data) - allowed)[0])
        for name, options in (("mode", ("demo", "live")), ("effect", EFFECTS)):
            if name in data and data[name] not in options:
                raise ValueError(f"invalid {name}")
        for name in ("playing", "relayEnabled"):
            if name in data and not isinstance(data[name], bool):
                raise ValueError(f"{name} must be a boolean")
        for name, minimum, maximum in (("brightness", 0., 1.), ("speed", .25, 3.),
                                        ("time", 0., self.duration), ("bpm", 40., 240.)):
            if name in data:
                value = data[name]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f"{name} must be a finite number")
                if not minimum <= value <= maximum:
                    raise ValueError(f"{name} must be between {minimum} and {maximum}")
        if "solidColor" in data:
            if not isinstance(data["solidColor"], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", data["solidColor"]):
                raise ValueError("solidColor must be a six-digit hex color such as #ffcc88")
        if "fixtureEnabled" in data:
            values = data["fixtureEnabled"]
            if not isinstance(values, dict) or any(key not in self.fixture_enabled or not isinstance(value, bool)
                                                   for key, value in values.items()):
                raise ValueError("fixtureEnabled must map known fixture IDs to booleans")
        with self.condition:
            if data.get("playing") is False and self.playing or data.get("mode") == "live" and self.mode != "live":
                self.frozen_live = self.live_rgb
            for field, attr in (("mode", "mode"), ("effect", "effect"), ("playing", "playing"),
                                ("brightness", "brightness"), ("speed", "speed"), ("time", "show_time"),
                                ("bpm", "bpm"), ("solidColor", "solid_color")):
                if field in data:
                    setattr(self, attr, data[field])
            if "fixtureEnabled" in data:
                self.fixture_enabled.update(data["fixtureEnabled"])
            if "relayEnabled" in data:
                self.relay["enabled"] = data["relayEnabled"]
            # Render changes on the next clock tick; reading or controlling never advances time.
            self.condition.notify_all()
            return self.snapshot()

    def receive(self, protocol, data, sender=("127.0.0.1", 0), now=None):
        """Decode input without letting a bad datagram kill the receiver thread."""
        now = time.monotonic() if now is None else now
        try:
            with self.condition:
                # Parsing and ingestion must use the same channel span during editor saves.
                packet = parse_ddp(data, self.channel_count) if protocol == "ddp" else parse_sacn(data)
                receiver = self.receivers[protocol]
                if packet is None:
                    receiver["ignored"] += 1
                    return False
                if protocol == "ddp":
                    rgb = self.ddp.ingest(packet, sender, self.live_rgb, now)
                    if rgb is not None:
                        self.live_rgb = rgb
                        self.active_protocol = "ddp"
                else:
                    if not self.sacn.ingest(packet, now):
                        receiver["ignored"] += 1
                        return False
                    self.live_rgb, self.sacn_sources = self.sacn.merge(self.live_rgb, now)
                    self.active_protocol = "sacn"
                receiver["packets"] += 1
                receiver["error"] = None
                self.last_packet = now
                return True
        except (PacketError, ValueError, struct.error) as error:
            with self.condition:
                self.receivers[protocol]["errors"] += 1
                self.receivers[protocol]["error"] = str(error)
            return False

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        with self.condition:
            elapsed = 0. if self._last_tick is None else max(0., min(1., now - self._last_tick))
            self._last_tick = now
            if self.playing:
                self.show_time = (self.show_time + elapsed * self.speed) % self.duration
            if self.active_protocol == "sacn":
                self.live_rgb, self.sacn_sources = self.sacn.merge(self.live_rgb, now)
            if self.mode == "demo":
                output = render(self.effect, self.show_time, self.mapping, self.channel_count,
                                self.bpm, self.solid_color)
            else:
                if self.playing:
                    self.frozen_live = self.live_rgb
                output = bytearray(self.frozen_live)
            if self.brightness < 1:
                output = bytearray(round(value * self.brightness) for value in output)
            for fixture in self.layout["fixtures"]:
                if not self.fixture_enabled[fixture["id"]]:
                    start = fixture["startChannel"] - 1
                    output[start:start + fixture["pixelCount"] * 3] = bytes(fixture["pixelCount"] * 3)
            self.output_rgb = bytes(output)
            self.output_base64 = base64.b64encode(output).decode("ascii")
            self.frame += 1
            self.frame_times.append(now)
            if len(self.frame_times) > 1 and self.frame_times[-1] > self.frame_times[0]:
                self.measured_fps = (len(self.frame_times) - 1) / (self.frame_times[-1] - self.frame_times[0])
            self.condition.notify_all()
            relay_enabled, relay_frame = self.relay["enabled"], self.output_rgb
        if relay_enabled and self.relay_socket:
            self._send_relay(relay_frame)

    def _send_relay(self, rgb):
        try:
            for packet, sequence in ddp_packets(rgb, self.relay_sequence):
                self.relay_socket.sendto(packet, (self.config.relay_host, self.config.relay_port))
                self.relay_sequence = sequence % 15 + 1
                with self.condition:
                    self.relay["packets"] += 1
            with self.condition:
                self.relay["error"] = None
        except OSError as error:
            with self.condition:
                self.relay["error"] = str(error)

    def _frame_loop(self):
        interval = 1 / self.config.fps
        deadline = time.monotonic()
        while not self.stop_event.is_set():
            self.tick()
            deadline += interval
            current = time.monotonic()
            if deadline < current - interval:
                deadline = current
            self.stop_event.wait(max(0., deadline - current))

    def _udp_loop(self, protocol):
        udp = self.udp_sockets[protocol]
        while not self.stop_event.is_set():
            try:
                data, sender = udp.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError as error:
                if not self.stop_event.is_set():
                    with self.condition:
                        self.receivers[protocol]["error"] = str(error)
                break
            self.receive(protocol, data, sender)

    def _make_thread(self, target, name, *args):
        thread = threading.Thread(target=target, args=args, name=name, daemon=True)
        self.threads.append(thread)
        thread.start()

    def start(self):
        if self.started:
            return self
        self.stop_event.clear()
        application = self

        class Handler(PreviewHandler):
            app = application

        self.http_server = ThreadingHTTPServer((self.config.host, self.config.port),
                                               partial(Handler, directory=str(self.config.web_dir)))
        self.http_server.daemon_threads = True
        self.config.port = self.http_server.server_address[1]
        for protocol in ("ddp", "sacn"):
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.settimeout(.2)
            try:
                host = "0.0.0.0" if protocol == "sacn" and self.config.sacn_multicast else self.config.udp_host
                udp.bind((host, getattr(self.config, f"{protocol}_port")))
                if protocol == "sacn" and self.config.sacn_multicast:
                    interface = socket.inet_aton(self.config.multicast_interface)
                    for universe in range(self.config.start_universe,
                                          self.config.start_universe + self.sacn.universe_count):
                        group = socket.inet_aton(f"239.255.{universe >> 8}.{universe & 255}")
                        udp.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, group + interface)
                self.udp_sockets[protocol] = udp
                actual_port = udp.getsockname()[1]
                self.receivers[protocol]["port"] = actual_port
                setattr(self.config, f"{protocol}_port", actual_port)
                self._make_thread(self._udp_loop, f"{protocol}-receiver", protocol)
            except OSError as error:
                udp.close()
                self.receivers[protocol]["error"] = f"Cannot bind receiver: {error}"
        self.relay_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.started = True
        self._make_thread(self._frame_loop, "frame-clock")
        self._make_thread(self.http_server.serve_forever, "http-server")
        return self

    def stop(self):
        self.stop_event.set()
        with self.condition:
            self.condition.notify_all()
        if self.http_server:
            self.http_server.shutdown()
            self.http_server.server_close()
        for udp in self.udp_sockets.values():
            udp.close()
        if self.relay_socket:
            self.relay_socket.close()
        for thread in self.threads:
            if thread is not threading.current_thread():
                thread.join(timeout=1)
        self.started = False


class PreviewHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    app = None

    def log_message(self, format_string, *args):
        if len(args) >= 2 and str(args[1]) == "200":
            return
        super().log_message(format_string, *args)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        super().end_headers()

    def _json(self, data, status=200):
        encoded = json.dumps(data, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(encoded)

    def _trusted_request(self):
        # Prevent cross-origin writes and DNS-rebinding through arbitrary Host.
        # Loopback control remains useful even if UDP listens on a LAN interface.
        try:
            host = urlsplit("http://" + self.headers.get("Host", "")).hostname
            local_address = self.connection.getsockname()[0]
            if host not in {"localhost", "127.0.0.1", "::1", self.app.config.host, local_address}:
                return False
            origin = self.headers.get("Origin")
            if origin is not None:
                parsed = urlsplit(origin)
                if parsed.scheme != "http" or parsed.hostname != host or (parsed.port or 80) != self.app.config.port:
                    return False
            if self.headers.get("Sec-Fetch-Site") in ("cross-site", "none") and origin:
                return False
            return True
        except ValueError:
            return False

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/") and not self._trusted_request():
            self._json({"error": "API requests require this server's local origin"}, 403)
        elif path == "/api/layout":
            self._json(self.app.layout_snapshot())
        elif path == "/api/status":
            self._json(self.app.snapshot(False))
        elif path == "/api/frame":
            self._json(self.app.snapshot())
        elif path == "/api/events":
            self._events()
        elif path.startswith("/api/"):
            self._json({"error": "API route not found"}, 404)
        else:
            # A traversal may be normalized by SimpleHTTPRequestHandler, while a
            # symlink may leave web/. Resolve and constrain both before serving.
            requested = Path(self.translate_path(path)).resolve()
            if not requested.is_relative_to(Path(self.directory).resolve()):
                self.send_error(403, "Path leaves web directory")
                return
            super().do_GET()

    def do_HEAD(self):
        if urlsplit(self.path).path.startswith("/api/"):
            if not self._trusted_request():
                self._json({"error": "untrusted origin"}, 403)
            else:
                self._json(self.app.snapshot(False))
        else:
            requested = Path(self.translate_path(urlsplit(self.path).path)).resolve()
            if not requested.is_relative_to(Path(self.directory).resolve()):
                self.send_error(403, "Path leaves web directory")
            else:
                super().do_HEAD()

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in ("/api/control", "/api/layout"):
            self._json({"error": "API route not found"}, 404)
            return
        if not self._trusted_request():
            self._json({"error": "Writes require this server's local origin"}, 403)
            self.close_connection = True
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self._json({"error": "Content-Type must be application/json"}, 415)
            self.close_connection = True
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            maximum = 8_000_000 if path == "/api/layout" else 16384
            if not 1 <= length <= maximum:
                raise ValueError(f"Request body must contain 1 to {maximum} bytes")
            self.connection.settimeout(5)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("incomplete request body")
            data = json.loads(raw.decode("utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError("non-finite JSON value")))
            self._json(self.app.save_layout(data) if path == "/api/layout" else self.app.control(data))
        except LayoutConflict as error:
            self._json({"error": str(error), "layoutRevision": self.app.layout_revision}, 409)
        except (ValueError, UnicodeError) as error:
            self._json({"error": str(error)}, 400)
            self.close_connection = True
        except OSError as error:
            self._json({"error": f"Could not save layout: {error}" if path == "/api/layout" else str(error)}, 500)
            self.close_connection = True

    def _events(self):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True
        self.connection.settimeout(5)
        previous = -1
        previous_revision = -1
        try:
            while not self.app.stop_event.is_set():
                with self.app.condition:
                    self.app.condition.wait_for(lambda: self.app.frame != previous or self.app.layout_revision != previous_revision
                                                or self.app.stop_event.is_set(), timeout=10)
                    if self.app.stop_event.is_set():
                        break
                    state = self.app.snapshot()
                if state["frame"] == previous and state["layoutRevision"] == previous_revision:
                    self.wfile.write(b": heartbeat\n\n")
                else:
                    previous = state["frame"]
                    previous_revision = state["layoutRevision"]
                    message = json.dumps(state, separators=(",", ":"), allow_nan=False)
                    self.wfile.write(f"id: {previous}\ndata: {message}\n\n".encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            pass
