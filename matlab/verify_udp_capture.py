"""Listen for a MATLAB smoke test; run before send_light_show(0.2, 4059).

Uses the shared layout and asserts a complete final blackout frame. This is a
local integration check of MATLAB's Java UDP call and DDP serialization.
"""
import json
from pathlib import Path
import socket
import struct
import time


def main():
    root = Path(__file__).resolve().parents[1]
    layout = json.loads((root / "layouts" / "default.json").read_text(encoding="utf-8"))
    channels = layout["channelCount"]
    frame = bytearray(channels)
    seen = bytearray(channels)
    committed = 0
    received = 0
    saw_color = False
    previous_sequence = None
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 4059))
        receiver.settimeout(1)
        print("READY: listening on 127.0.0.1:4059", flush=True)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                packet, _ = receiver.recvfrom(65535)
            except socket.timeout:
                continue
            flags, sequence, data_type, destination, offset, length = struct.unpack("!BBBBIH", packet[:10])
            assert flags in (0x40, 0x41)
            assert data_type == 0x0B and destination == 1
            assert 1 <= sequence <= 15
            if previous_sequence is not None:
                assert sequence == previous_sequence % 15 + 1
            previous_sequence = sequence
            assert len(packet) == length + 10 and 0 < length <= 1440
            assert offset + length <= channels
            frame[offset:offset + length] = packet[10:]
            seen[offset:offset + length] = b"\x01" * length
            received += 1
            if flags & 1:
                assert all(seen), "Every test frame must cover the shared layout"
                committed += 1
                saw_color |= any(frame)
                if saw_color and not any(frame):
                    print(f"PASS: MATLAB UDP captured {received} datagrams / {committed} complete frames; final blackout; {channels} channels", flush=True)
                    return
                seen[:] = b"\x00" * channels
    raise AssertionError("Timed out waiting for rainbow and complete final blackout")


if __name__ == "__main__":
    main()
