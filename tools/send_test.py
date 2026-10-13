#!/usr/bin/env python3
"""Stream RGB test frames into the preview using public DDP or sACN protocols."""

import argparse
import colorsys
import json
import math
from pathlib import Path
import re
import socket
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lightshow.layout import load_layout
from lightshow.protocols import ddp_packets, sacn_packets


def test_frame(layout, elapsed, effect, color):
    rgb = bytearray(layout["channelCount"])
    for fixture_index, fixture in enumerate(layout["fixtures"]):
        start = fixture["startChannel"] - 1
        for pixel in range(len(fixture["pixels"])):
            if effect == "solid":
                values = color
            elif effect == "chase":
                head = (elapsed * 32) % len(fixture["pixels"])
                distance = (pixel - head) % len(fixture["pixels"])
                scale = max(.015, 1 - distance / 10) if distance < 10 else .015
                values = tuple(round(component * scale) for component in color)
            else:
                hue = (pixel / max(1, len(fixture["pixels"])) + elapsed * .16 + fixture_index * .075) % 1
                values = tuple(round(component * 255) for component in colorsys.hsv_to_rgb(hue, .9, 1))
            offset = start + pixel * 3
            rgb[offset:offset + 3] = bytes(values)
    return bytes(rgb)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", choices=("ddp", "sacn"), default="ddp")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, help="UDP target port (4048 for DDP, 5568 for sACN)")
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--fps", type=float, default=30)
    parser.add_argument("--effect", choices=("rainbow", "chase", "solid"), default="rainbow")
    parser.add_argument("--color", default="#ffcc88")
    parser.add_argument("--layout", type=Path, default=ROOT / "layouts" / "default.json")
    parser.add_argument("--universe-size", type=int, choices=(510, 512), default=510)
    parser.add_argument("--start-universe", type=int, default=1)
    parser.add_argument("--api", default="http://127.0.0.1:8080", help="Preview URL used to enter Live mode")
    parser.add_argument("--no-auto-live", action="store_true", help="Leave preview controls unchanged")
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 86400:
        parser.error("--seconds must be from 0 (exclusive) to 86400")
    if not math.isfinite(args.fps) or not 1 <= args.fps <= 60:
        parser.error("--fps must be from 1 to 60")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", args.color):
        parser.error("--color must be a six-digit color such as #ffcc88")
    port = args.port if args.port is not None else (4048 if args.protocol == "ddp" else 5568)
    if not 1 <= port <= 65535:
        parser.error("--port must be from 1 to 65535")
    try:
        layout = load_layout(args.layout)
        if args.protocol == "sacn":
            # Validate the complete range before starting any network action.
            list(sacn_packets(bytes(layout["channelCount"]), universe_size=args.universe_size,
                              start_universe=args.start_universe))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if not args.no_auto_live:
        try:
            request = Request(args.api.rstrip("/") + "/api/control",
                              data=json.dumps({"mode": "live", "playing": True, "brightness": 1}).encode(),
                              headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=3) as response:
                response.read()
        except (OSError, URLError) as error:
            print(f"Cannot switch preview to Live mode: {error}. Choose Live manually.", file=sys.stderr)
    cid, sequence, frames, packets = uuid.uuid4().bytes, 1, 0, 0
    color = tuple(int(args.color[index:index + 2], 16) for index in (1, 3, 5))
    start, deadline = time.monotonic(), time.monotonic()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        try:
            while time.monotonic() - start < args.seconds:
                rgb = test_frame(layout, time.monotonic() - start, args.effect, color)
                if args.protocol == "ddp":
                    for packet, emitted_sequence in ddp_packets(rgb, sequence):
                        udp.sendto(packet, (args.host, port))
                        sequence = emitted_sequence % 15 + 1
                        packets += 1
                else:
                    for packet in sacn_packets(rgb, sequence, args.universe_size, args.start_universe, cid):
                        udp.sendto(packet, (args.host, port))
                        packets += 1
                    sequence = (sequence + 1) % 256
                frames += 1
                deadline += 1 / args.fps
                delay = deadline - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
        except KeyboardInterrupt:
            pass
    print(f"Sent {frames} frames / {packets} {args.protocol.upper()} packets to {args.host}:{port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
