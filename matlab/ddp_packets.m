function [packets, nextSequence] = ddp_packets(channels, sequence)
%DDP_PACKETS Encode a full RGB channel frame into DDP v1 UDP packets.
% Each packet has at most 1440 bytes of data. PUSH is set on the final packet.
% Sequence numbers advance per packet through 1..15 (not per frame).
arguments
    channels (1,:) uint8
    sequence (1,1) double {mustBeInteger,mustBeInRange(sequence,1,15)} = 1
end
if isempty(channels)
    error('ChristmasLights:EmptyFrame', 'A DDP frame must contain channel data.');
end
packetCount = ceil(numel(channels) / 1440);
packets = cell(1, packetCount);
for packetIndex = 1:packetCount
    offset = (packetIndex - 1) * 1440;
    payload = channels(offset + 1:min(offset + 1440, numel(channels)));
    flags = uint8(64 + (packetIndex == packetCount));
    packetOffset = uint32(offset);
    packetLength = uint16(numel(payload));
    header = [flags uint8(sequence) uint8(11) uint8(1) ...
        uint8(bitand(bitshift(packetOffset,-24),255)) ...
        uint8(bitand(bitshift(packetOffset,-16),255)) ...
        uint8(bitand(bitshift(packetOffset,-8),255)) uint8(bitand(packetOffset,255)) ...
        uint8(bitshift(packetLength,-8)) uint8(bitand(packetLength,255))];
    packets{packetIndex} = [header payload];
    sequence = mod(sequence, 15) + 1;
end
nextSequence = sequence;
end
