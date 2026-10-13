"""Bounded RGB DDP and E1.31 data packet support.

DDP follows the xLights wire implementation and the open 3waylabs protocol.
E1.31 follows ANSI E1.31-2018 data framing. This preview supports unicast and
optional IPv4 multicast, NULL-start-code slots, source priority, HTP for equal
priority sources, sequence filtering, stream termination and 2.5s source loss.
Synchronization packets and per-address priorities are intentionally outside
this preview's scope. Optional DDP timecode headers are parsed, then displayed
immediately. DMX transit, storage, query and reply packets are not RGB data.
"""

from dataclasses import dataclass
import math
import struct
import time
import uuid

DDP_PORT = 4048
SACN_PORT = 5568
DDP_MAX_DATA = 1440
SOURCE_TIMEOUT = 2.5


class PacketError(ValueError):
    """Malformed or out-of-range wire input (safe to report and continue)."""


@dataclass(frozen=True)
class DDPPacket:
    sequence: int
    offset: int
    data: bytes
    push: bool


def parse_ddp(data, channel_count):
    if len(data) < 10:
        raise PacketError("DDP header is shorter than 10 bytes")
    flags, sequence, kind, destination, offset, length = struct.unpack("!BBBBIH", data[:10])
    if flags & 0xC0 != 0x40 or flags & 0x20:
        raise PacketError("unsupported DDP version or reserved flag")
    if sequence & 0xF0:
        raise PacketError("DDP sequence uses reserved high bits")
    if flags & 0x0E:  # Query, reply or storage; none carries ordinary RGB writes.
        return None
    if destination not in (1, 255) or kind not in (0, 1, 0x0B):
        return None
    header_length = 14 if flags & 0x10 else 10
    if len(data) != header_length + length:
        raise PacketError("DDP payload does not match declared length")
    if offset > channel_count or length > channel_count - offset:
        raise PacketError("DDP write is outside the layout's channel span")
    return DDPPacket(sequence, offset, bytes(data[header_length:]), bool(flags & 1))


def ddp_packets(rgb, sequence=0, chunk_size=DDP_MAX_DATA):
    """Yield (packet, sequence) pairs; sequence increments for every packet.

    A zero sequence disables sequence numbering. Offset and size refer to
    bytes, allowing fixture channel spans to contain deliberate gaps.
    """
    if not 1 <= chunk_size <= DDP_MAX_DATA:
        raise ValueError("DDP chunk size must be from 1 to 1440 bytes")
    if not 0 <= sequence <= 15:
        raise ValueError("DDP sequence must be from 0 to 15")
    for offset in range(0, max(1, len(rgb)), chunk_size):
        chunk = rgb[offset:offset + chunk_size]
        final = offset + len(chunk) >= len(rgb)
        yield struct.pack("!BBBBIH", 0x40 | int(final), sequence, 0x0B, 1,
                          offset, len(chunk)) + bytes(chunk), sequence
        if sequence:
            sequence = sequence % 15 + 1


class DDPAssembler:
    """Stage per-sender partial writes; publish only when a PUSH arrives."""

    def __init__(self, channel_count, max_sources=8):
        self.channel_count = channel_count
        self.max_sources = max_sources
        self.sources = {}

    def ingest(self, packet, sender, current, now=None):
        now = time.monotonic() if now is None else now
        expired = [key for key, value in self.sources.items() if now - value["last"] > SOURCE_TIMEOUT]
        for key in expired:
            del self.sources[key]
        source = self.sources.get(sender)
        if source is None:
            if len(self.sources) >= self.max_sources:
                del self.sources[min(self.sources, key=lambda key: self.sources[key]["last"])]
            source = {"rgb": bytearray(current), "last": now, "packet": None}
            self.sources[sender] = source
        signature = (packet.sequence, packet.offset, packet.push, packet.data)
        source["last"] = now
        if packet.sequence and source["packet"] == signature:
            return None
        source["packet"] = signature
        source["rgb"][packet.offset:packet.offset + len(packet.data)] = packet.data
        return bytes(source["rgb"]) if packet.push else None


@dataclass(frozen=True)
class SACNPacket:
    cid: bytes
    source_name: str
    universe: int
    priority: int
    sequence: int
    options: int
    sync_address: int
    start_code: int
    slots: bytes

    @property
    def terminated(self):
        return bool(self.options & 0x40)


def _pdu_length(data, offset):
    value = struct.unpack_from("!H", data, offset)[0]
    if value & 0xF000 != 0x7000 or value & 0x0FFF != len(data) - offset:
        raise PacketError("E1.31 layer flags or length are invalid")


def parse_sacn(data):
    if not 126 <= len(data) <= 638:
        raise PacketError("E1.31 data packet must contain 126 to 638 bytes")
    if data[:4] != b"\x00\x10\x00\x00" or data[4:16] != b"ASC-E1.17\x00\x00\x00":
        raise PacketError("invalid E1.31 preamble or ACN identifier")
    _pdu_length(data, 16)
    _pdu_length(data, 38)
    _pdu_length(data, 115)
    if data[18:22] != b"\x00\x00\x00\x04" or data[40:44] != b"\x00\x00\x00\x02":
        raise PacketError("unsupported E1.31 root/framing vector")
    if data[117:119] != b"\x02\xa1" or data[119:123] != b"\x00\x00\x00\x01":
        raise PacketError("invalid E1.31 DMP vector or addressing")
    count = struct.unpack_from("!H", data, 123)[0]
    if not 1 <= count <= 513 or count != len(data) - 125:
        raise PacketError("invalid E1.31 property count")
    universe = struct.unpack_from("!H", data, 113)[0]
    if not 1 <= universe <= 63999 or data[108] > 200 or data[112] & 0x1F:
        raise PacketError("invalid E1.31 universe, priority or reserved options")
    if b"\x00" not in data[44:108]:
        raise PacketError("E1.31 source name must be null-terminated")
    return SACNPacket(bytes(data[22:38]), data[44:108].split(b"\0", 1)[0].decode("utf-8", "replace"),
                      universe, data[108], data[111], data[112],
                      struct.unpack_from("!H", data, 109)[0], data[125], bytes(data[126:]))


def sacn_packets(rgb, sequence=0, universe_size=510, start_universe=1, cid=None,
                 priority=100, source_name="Christmas Lights test"):
    """Build E1.31 NULL-start-code packets for tests and software senders."""
    if universe_size not in (510, 512) or not 0 <= priority <= 200:
        raise ValueError("invalid E1.31 universe size or priority")
    universe_count = math.ceil(len(rgb) / universe_size)
    if not 1 <= start_universe <= 63999 or start_universe + universe_count - 1 > 63999:
        raise ValueError("E1.31 universe range is outside 1 to 63999")
    cid = uuid.uuid4().bytes if cid is None else bytes(cid)
    if len(cid) != 16:
        raise ValueError("E1.31 CID must be 16 bytes")
    name = source_name.encode("utf-8")[:63].ljust(64, b"\0")
    for index in range(universe_count):
        slots = bytes(rgb[index * universe_size:(index + 1) * universe_size])
        packet = bytearray(126 + len(slots))
        packet[:16] = b"\x00\x10\x00\x00ASC-E1.17\x00\x00\x00"
        for offset in (16, 38, 115):
            struct.pack_into("!H", packet, offset, 0x7000 | (len(packet) - offset))
        packet[18:22], packet[22:38] = b"\x00\x00\x00\x04", cid
        packet[40:44], packet[44:108] = b"\x00\x00\x00\x02", name
        packet[108], packet[111] = priority, sequence & 255
        struct.pack_into("!H", packet, 113, start_universe + index)
        packet[117:123] = b"\x02\xa1\x00\x00\x00\x01"
        struct.pack_into("!H", packet, 123, 1 + len(slots))
        packet[126:] = slots
        yield bytes(packet)


def sequence_is_new(new, old):
    # E1.31 section 6.7.2: suppress duplicates and the previous 19 sequences;
    # permit large jumps so a resetting source can recover without a long wait.
    delta = (new - old + 128) % 256 - 128
    return not (-20 < delta <= 0)


class SACNMerger:
    """Keep bounded sources per universe, merging only the highest priority."""

    def __init__(self, channel_count, universe_size=510, start_universe=1, max_sources=8):
        if universe_size not in (510, 512):
            raise ValueError("universe_size must be 510 or 512")
        self.channel_count, self.universe_size = channel_count, universe_size
        self.start_universe, self.max_sources = start_universe, max_sources
        self.universe_count = math.ceil(channel_count / universe_size)
        if start_universe < 1 or start_universe + self.universe_count - 1 > 63999:
            raise ValueError("E1.31 universe range is outside 1 to 63999")
        self.sources = {}

    def ingest(self, packet, now=None):
        now = time.monotonic() if now is None else now
        index = packet.universe - self.start_universe
        if not 0 <= index < self.universe_count or packet.start_code != 0:
            return False
        if packet.sync_address or packet.options & 0x20:
            return False  # Synchronized sources require the optional sync receiver.
        sources = self.sources.setdefault(packet.universe, {})
        existing = sources.get(packet.cid)
        if existing and now - existing["last"] <= SOURCE_TIMEOUT:
            if not sequence_is_new(packet.sequence, existing["sequence"]):
                return False
        if packet.terminated:
            sources.pop(packet.cid, None)
            return True
        if packet.cid not in sources and len(sources) >= self.max_sources:
            # Evict expired/lowest-priority sources rather than allocating endlessly.
            weakest = min(sources, key=lambda key: (sources[key]["last"] > now - SOURCE_TIMEOUT,
                                                   sources[key]["priority"], sources[key]["last"]))
            if sources[weakest]["last"] > now - SOURCE_TIMEOUT and sources[weakest]["priority"] > packet.priority:
                return False
            del sources[weakest]
        slots = packet.slots[:self.universe_size].ljust(self.universe_size, b"\0")
        sources[packet.cid] = {"last": now, "sequence": packet.sequence,
                               "priority": packet.priority, "slots": slots}
        return True

    def merge(self, current, now=None):
        """Write tracked universes into current; return frame and active-source count."""
        now = time.monotonic() if now is None else now
        result = bytearray(current)
        active_sources = 0
        for universe, sources in self.sources.items():
            for cid in [key for key, item in sources.items() if now - item["last"] > SOURCE_TIMEOUT]:
                del sources[cid]
            offset = (universe - self.start_universe) * self.universe_size
            length = min(self.universe_size, self.channel_count - offset)
            if not sources:
                result[offset:offset + length] = bytes(length)
                continue
            priority = max(item["priority"] for item in sources.values())
            winners = [item["slots"] for item in sources.values() if item["priority"] == priority]
            active_sources += len(sources)
            merged = winners[0] if len(winners) == 1 else bytes(max(values) for values in zip(*winners))
            result[offset:offset + length] = merged[:length]
        return bytes(result), active_sources

