import base64
import http.client
import json
from pathlib import Path
import socket
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from lightshow.app import Config, LightShowApplication
from lightshow.protocols import DDPAssembler, ddp_packets, parse_ddp, sacn_packets


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.web = Path(self.temporary.name) / "web"
        self.web.mkdir()
        (self.web / "index.html").write_text("<!doctype html><title>Fixture</title>", encoding="utf-8")
        self.relay = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.relay.bind(("127.0.0.1", 0))
        self.relay.settimeout(.25)
        self.app = LightShowApplication(Config(port=0, ddp_port=0, sacn_port=0,
                                               relay_port=self.relay.getsockname()[1], web_dir=self.web)).start()
        self.base = f"http://127.0.0.1:{self.app.config.port}"

    def tearDown(self):
        self.app.stop()
        self.relay.close()
        self.temporary.cleanup()

    def get(self, path):
        with urlopen(self.base + path, timeout=3) as response:
            return json.loads(response.read())

    def post(self, values, headers=None):
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})
        request = Request(self.base + "/api/control", data=json.dumps(values).encode(),
                          headers=request_headers, method="POST")
        with urlopen(request, timeout=3) as response:
            return json.loads(response.read())

    def wait_frame(self, predicate, timeout=2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            frame = self.get("/api/frame")
            if predicate(frame):
                return frame
            time.sleep(.015)
        self.fail("Expected output frame did not arrive")

    def test_layout_status_static_and_atomic_controls(self):
        layout, status = self.get("/api/layout"), self.get("/api/status")
        self.assertEqual(layout["channelCount"], 4275)
        self.assertEqual(layout["pixelCount"], 1425)
        self.assertEqual(layout["universeSize"], 510)
        self.assertNotIn("rgb", status)
        self.assertIsNone(status["receivers"]["ddp"]["error"])
        with urlopen(self.base + "/", timeout=3) as response:
            self.assertIn(b"Fixture", response.read())
        before = self.get("/api/status")["brightness"]
        with self.assertRaises(HTTPError) as error:
            self.post({"brightness": .2, "speed": 100})
        self.assertEqual(error.exception.code, 400)
        error.exception.close()
        self.assertEqual(self.get("/api/status")["brightness"], before)
        with self.assertRaises(HTTPError) as error:
            self.post({"mode": "live"}, {"Origin": "https://example.com"})
        self.assertEqual(error.exception.code, 403)
        error.exception.close()
        self.assertEqual(self.get("/api/status")["mode"], "demo")
        connection = http.client.HTTPConnection("127.0.0.1", self.app.config.port, timeout=3)
        connection.request("GET", "/api/status", headers={"Host": "attacker.invalid"})
        response = connection.getresponse()
        self.assertEqual(response.status, 403)
        response.read()
        connection.close()

    def test_solid_pause_scrub_brightness_fixture_mask(self):
        self.post({"playing": False, "time": 42, "effect": "solid", "solidColor": "#804020", "brightness": .5})
        frame = self.wait_frame(lambda value: base64.b64decode(value["rgb"])[:3] == b"\x40\x20\x10")
        self.assertEqual(frame["time"], 42)
        self.post({"fixtureEnabled": {"roofline": False}, "relayEnabled": False})
        fixture = self.app.layout["fixtures"][0]
        span = fixture["pixelCount"] * 3
        frame = self.wait_frame(lambda value: base64.b64decode(value["rgb"])[:span] == bytes(span))
        self.assertFalse(frame["fixtureEnabled"]["roofline"])
        self.assertFalse(frame["relay"]["enabled"])
        self.assertEqual(base64.b64decode(frame["rgb"])[span:span + 3], b"\x40\x20\x10")
        time.sleep(.08)
        self.assertEqual(self.get("/api/frame")["time"], 42)

    def test_ddp_live_and_unreal_relay_are_byte_equivalent(self):
        self.post({"mode": "live", "playing": True, "brightness": 1})
        expected = bytes((index * 13 + 19) % 256 for index in range(self.app.channel_count))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            for packet, _ in ddp_packets(expected, 1):
                sender.sendto(packet, ("127.0.0.1", self.app.config.ddp_port))
        frame = self.wait_frame(lambda value: base64.b64decode(value["rgb"]) == expected)
        self.assertEqual(frame["receivers"]["ddp"]["packets"], 3)
        self.assertEqual(frame["activeProtocol"], "ddp")
        self.assertIsNotNone(frame["lastPacketAge"])
        assembler = DDPAssembler(len(expected))
        relayed = bytes(len(expected))
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            packet, _ = self.relay.recvfrom(2048)
            published = assembler.ingest(parse_ddp(packet, len(expected)), "relay", relayed)
            if published is not None:
                relayed = published
                if published == expected:
                    break
        self.assertEqual(relayed, expected)

    def test_sacn_live_and_malformed_packet_recovery(self):
        self.post({"mode": "live", "brightness": 1})
        expected = bytes((index * 7 + 31) % 256 for index in range(self.app.channel_count))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.sendto(b"invalid", ("127.0.0.1", self.app.config.sacn_port))
            for packet in sacn_packets(expected, sequence=1, cid=b"t" * 16):
                sender.sendto(packet, ("127.0.0.1", self.app.config.sacn_port))
        frame = self.wait_frame(lambda value: base64.b64decode(value["rgb"]) == expected)
        self.assertEqual(frame["receivers"]["sacn"]["packets"], 9)
        self.assertEqual(frame["receivers"]["sacn"]["errors"], 1)
        self.assertIsNone(frame["receivers"]["sacn"]["error"])
        self.assertEqual(frame["activeProtocol"], "sacn")

    def test_multiple_event_readers_do_not_advance_paused_time(self):
        self.post({"playing": False, "time": 30})
        first = http.client.HTTPConnection("127.0.0.1", self.app.config.port, timeout=3)
        second = http.client.HTTPConnection("127.0.0.1", self.app.config.port, timeout=3)
        initial = self.get("/api/status")["frame"]
        try:
            first.request("GET", "/api/events")
            second.request("GET", "/api/events")
            for response in (first.getresponse(), second.getresponse()):
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Content-Type"), "text/event-stream")
                line = response.fp.readline()
                self.assertTrue(line.startswith(b"id: "))
                data_line = response.fp.readline()
                payload = json.loads(data_line[6:])
                self.assertEqual(payload["time"], 30)
                self.assertEqual(len(base64.b64decode(payload["rgb"])), self.app.channel_count)
            for _ in range(20):
                self.get("/api/status")
            final = self.get("/api/status")
            self.assertEqual(final["time"], 30)
            self.assertLess(final["frame"] - initial, 60)
        finally:
            first.close()
            second.close()

    def test_live_pause_keeps_receiving_but_freezes_display(self):
        self.post({"mode": "live", "brightness": 1})
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            rgb = b"\xff\0\0" * self.app.layout["pixelCount"]
            for packet, _ in ddp_packets(rgb):
                sender.sendto(packet, ("127.0.0.1", self.app.config.ddp_port))
            self.wait_frame(lambda value: base64.b64decode(value["rgb"]) == rgb)
            self.post({"playing": False})
            second = b"\0\xff\0" * self.app.layout["pixelCount"]
            for packet, _ in ddp_packets(second):
                sender.sendto(packet, ("127.0.0.1", self.app.config.ddp_port))
            self.wait_frame(lambda value: value["receivers"]["ddp"]["packets"] == 6)
            self.assertEqual(base64.b64decode(self.get("/api/frame")["rgb"]), rgb)
            self.post({"playing": True})
            self.wait_frame(lambda value: base64.b64decode(value["rgb"]) == second)


if __name__ == "__main__":
    unittest.main()
