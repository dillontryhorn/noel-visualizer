import dataclasses
import math
import random
import struct
import unittest

from lightshow.effects import EFFECTS, render
from lightshow.layout import pixel_mapping, validate_layout
from lightshow.protocols import (DDPAssembler, DDPPacket, PacketError, SACNMerger, ddp_packets,
                                 parse_ddp, parse_sacn, sacn_packets, sequence_is_new)


class DDPTests(unittest.TestCase):
    def test_chunked_roundtrip_push_and_sequences(self):
        rgb = bytes(i % 256 for i in range(4275))
        assembler = DDPAssembler(len(rgb))
        current = bytes(len(rgb))
        packets = list(ddp_packets(rgb, sequence=14))
        self.assertEqual([seq for _, seq in packets], [14, 15, 1])
        self.assertTrue(all(len(packet) <= 1450 for packet, _ in packets))
        for index, (wire, _) in enumerate(packets):
            packet = parse_ddp(wire, len(rgb))
            result = assembler.ingest(packet, ("sender", 1), current, now=1)
            if index < len(packets) - 1:
                self.assertIsNone(result)
            else:
                self.assertEqual(result, rgb)

    def test_partial_writes_persist_and_duplicate_push_is_ignored(self):
        assembler = DDPAssembler(6)
        packet = DDPPacket(1, 0, b"\x10\x20\x30", True)
        self.assertEqual(assembler.ingest(packet, "sender", bytes(6), 1), b"\x10\x20\x30\0\0\0")
        self.assertIsNone(assembler.ingest(packet, "sender", bytes(6), 1.1))
        second = DDPPacket(2, 3, b"\x40\x50\x60", True)
        self.assertEqual(assembler.ingest(second, "sender", bytes(6), 1.2), b"\x10\x20\x30\x40\x50\x60")

    def test_push_only_commits_staged_data(self):
        assembler = DDPAssembler(3)
        self.assertIsNone(assembler.ingest(DDPPacket(1, 0, b"abc", False), "a", bytes(3), 1))
        self.assertEqual(assembler.ingest(DDPPacket(2, 0, b"", True), "a", bytes(3), 1.1), b"abc")

    def test_timecode_header_and_legacy_rgb(self):
        wire = struct.pack("!BBBBIH", 0x51, 1, 1, 1, 0, 3) + b"\0\0\0\0abc"
        self.assertEqual(parse_ddp(wire, 3).data, b"abc")

    def test_malformed_and_unrelated_packets(self):
        valid = struct.pack("!BBBBIH", 0x41, 1, 0x0B, 1, 0, 3) + b"abc"
        for packet in (valid[:9], valid[:-1], valid + b"x",
                       bytes([0x81]) + valid[1:], valid[:1] + b"\x11" + valid[2:],
                       struct.pack("!BBBBIH", 0x41, 1, 0x0B, 1, 0xffffffff, 3) + b"abc"):
            with self.subTest(packet=packet), self.assertRaises(PacketError):
                parse_ddp(packet, 3)
        self.assertIsNone(parse_ddp(bytes([0x42]) + valid[1:], 3))
        self.assertIsNone(parse_ddp(valid[:2] + bytes([0x13]) + valid[3:], 3))
        self.assertIsNone(parse_ddp(valid[:3] + bytes([250]) + valid[4:], 3))

    def test_sources_bounded_and_expire(self):
        assembler = DDPAssembler(3, max_sources=2)
        for sender in (1, 2, 3):
            assembler.ingest(DDPPacket(1, 0, b"abc", True), sender, bytes(3), now=sender)
        self.assertEqual(len(assembler.sources), 2)
        assembler.ingest(DDPPacket(2, 0, b"", True), 4, b"xyz", now=10)
        self.assertEqual(len(assembler.sources), 1)
        self.assertEqual(bytes(assembler.sources[4]["rgb"]), b"xyz")


class SACNTests(unittest.TestCase):
    def packet(self, rgb=b"abc", sequence=1, cid=b"a" * 16, priority=100, universe=1):
        return parse_sacn(next(sacn_packets(rgb, sequence, 510, universe, cid, priority)))

    def test_wire_offsets_and_510_universe_mapping(self):
        rgb = bytes(i % 256 for i in range(1026))
        wires = list(sacn_packets(rgb, sequence=245, universe_size=510, start_universe=7, cid=b"a" * 16))
        self.assertEqual(len(wires), 3)
        parsed = [parse_sacn(wire) for wire in wires]
        self.assertEqual([packet.universe for packet in parsed], [7, 8, 9])
        self.assertEqual([len(packet.slots) for packet in parsed], [510, 510, 6])
        merger = SACNMerger(len(rgb), universe_size=510, start_universe=7)
        for packet in parsed:
            self.assertTrue(merger.ingest(packet, now=1))
        self.assertEqual(merger.merge(bytes(len(rgb)), now=1)[0], rgb)

    def test_512_universe_mapping(self):
        rgb = bytes(i % 256 for i in range(1026))
        merger = SACNMerger(len(rgb), universe_size=512)
        for wire in sacn_packets(rgb, universe_size=512, cid=b"a" * 16):
            merger.ingest(parse_sacn(wire), now=1)
        self.assertEqual(merger.merge(bytes(len(rgb)), now=1)[0], rgb)

    def test_priority_htp_termination_and_expiry(self):
        merger = SACNMerger(3)
        merger.ingest(self.packet(b"\xff\0\0", cid=b"a" * 16, priority=100), now=1)
        merger.ingest(self.packet(b"\0\x80\x10", cid=b"b" * 16, priority=110), now=1)
        self.assertEqual(merger.merge(bytes(3), now=1)[0], b"\0\x80\x10")
        merger.ingest(self.packet(b"\x20\x40\x70", cid=b"c" * 16, priority=110), now=1)
        self.assertEqual(merger.merge(bytes(3), now=1)[0], b"\x20\x80\x70")
        terminated = dataclasses.replace(self.packet(cid=b"b" * 16, sequence=2), options=0x40)
        merger.ingest(terminated, now=1.1)
        self.assertEqual(merger.merge(bytes(3), now=1.1)[0], b"\x20\x40\x70")
        self.assertEqual(merger.merge(b"xyz", now=4)[0], bytes(3))
        self.assertEqual(merger.merge(bytes(3), now=4)[1], 0)

    def test_sequences_duplicates_stale_wrap_and_reset(self):
        merger = SACNMerger(3)
        self.assertTrue(merger.ingest(self.packet(b"abc", 254), now=1))
        self.assertFalse(merger.ingest(self.packet(b"xyz", 254), now=1.01))
        self.assertFalse(merger.ingest(self.packet(b"xyz", 253), now=1.02))
        self.assertTrue(merger.ingest(self.packet(b"def", 0), now=1.03))
        self.assertFalse(merger.ingest(self.packet(b"xyz", 255), now=1.04))
        self.assertEqual(merger.merge(bytes(3), now=1.04)[0], b"def")
        self.assertTrue(sequence_is_new(10, 100))
        self.assertFalse(sequence_is_new(80, 99))
        self.assertTrue(merger.ingest(self.packet(b"new", 0), now=5))

    def test_alternate_startcode_sync_and_unmapped_universes_are_ignored(self):
        merger = SACNMerger(3)
        for packet in (dataclasses.replace(self.packet(), start_code=0xDD),
                       dataclasses.replace(self.packet(), sync_address=10),
                       dataclasses.replace(self.packet(), options=0x20), self.packet(universe=2)):
            self.assertFalse(merger.ingest(packet, now=1))
        self.assertEqual(merger.merge(bytes(3), now=1)[0], bytes(3))

    def test_source_capacity_prefers_higher_priority(self):
        merger = SACNMerger(3, max_sources=2)
        merger.ingest(self.packet(b"low", cid=b"a" * 16, priority=50), now=1)
        merger.ingest(self.packet(b"mid", cid=b"b" * 16, priority=100), now=1)
        merger.ingest(self.packet(b"top", cid=b"c" * 16, priority=200), now=1)
        self.assertEqual(len(merger.sources[1]), 2)
        self.assertEqual(merger.merge(bytes(3), now=1)[0], b"top")
        self.assertFalse(merger.ingest(self.packet(b"new", cid=b"d" * 16, priority=10), now=1))

    def test_malformed_wire_inputs(self):
        valid = next(sacn_packets(b"abc", cid=b"a" * 16))
        bad_packets = [valid[:125], valid[:-1], valid + b"x"]
        for offset, value in ((0, 1), (4, 0), (16, 0), (21, 3), (38, 0), (43, 1),
                              (108, 201), (112, 1), (113, 0), (114, 0), (115, 0),
                              (117, 3), (118, 0), (119, 1), (122, 2), (123, 255)):
            mutated = bytearray(valid)
            mutated[offset] = value
            # Universe zero takes both bytes, while offset113 is already0.
            if offset in (113, 114):
                mutated[113:115] = b"\0\0"
            bad_packets.append(bytes(mutated))
        for packet in bad_packets:
            with self.subTest(packet=packet), self.assertRaises(PacketError):
                parse_sacn(packet)

    def test_random_datagrams_never_escape_packet_error(self):
        generator = random.Random(4)
        for _ in range(300):
            data = generator.randbytes(generator.randrange(0, 700))
            for parser in (parse_sacn, lambda wire: parse_ddp(wire, 4275)):
                try:
                    parser(data)
                except PacketError:
                    pass


class LayoutEffectTests(unittest.TestCase):
    def layout(self):
        return {"name": "Test", "fixtures": [{"id": "one", "pixels": [[0, 1, 0], [1, 2, 0]], "startChannel": 4},
                                              {"id": "two", "pixels": [[2, 3, 0]], "startChannel": 10}]}

    def test_sparse_mapping_and_bounded_deterministic_effects(self):
        layout = validate_layout(self.layout())
        self.assertEqual(layout["channelCount"], 12)
        self.assertEqual(layout["pixelCount"], 3)
        mapping = list(pixel_mapping(layout))
        for effect in EFFECTS:
            first = render(effect, 12.5, mapping, 12, bpm=180)
            second = render(effect, 12.5, mapping, 12, bpm=180)
            self.assertEqual(first, second)
            self.assertEqual(len(first), 12)
            self.assertEqual(first[:3], bytes(3))
            self.assertTrue(all(0 <= value <= 255 for value in first))

    def test_invalid_layouts(self):
        for change in ("overlap", "nonfinite", "duplicate", "empty", "unbounded", "wrong_count"):
            data = self.layout()
            if change == "overlap":
                data["fixtures"][1]["startChannel"] = 6
            elif change == "nonfinite":
                data["fixtures"][0]["pixels"][0][1] = math.inf
            elif change == "duplicate":
                data["fixtures"][1]["id"] = "one"
            elif change == "empty":
                data["fixtures"][0]["pixels"] = []
            elif change == "unbounded":
                data["fixtures"][0]["startChannel"] = 100_000
            else:
                data["pixelCount"] = 4
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_layout(data)


if __name__ == "__main__":
    unittest.main()
