function test_ddp_packets()
%TEST_DDP_PACKETS Local serialization assertions; no UDP/Unreal required.
channels = uint8(mod(0:4274, 256));
[packets, nextSequence] = ddp_packets(channels, 14);
assert(numel(packets) == 3);
assert(nextSequence == 2);
assert(isequal(cellfun(@(packet) double(packet(2)), packets), [14 15 1]));
assert(all(cellfun(@(packet) packet(3) == 11 && packet(4) == 1, packets)));
assert(isequal(cellfun(@(packet) double(packet(1)), packets), [64 64 65]));
assembled = zeros(1, numel(channels), 'uint8');
for index = 1:numel(packets)
    packet = packets{index};
    offset = double(packet(5:8)) * [2^24; 2^16; 2^8; 1];
    count = double(packet(9:10)) * [2^8; 1];
    assert(numel(packet) == count + 10);
    assert(count <= 1440);
    assembled(offset + 1:offset + count) = packet(11:end);
end
assert(isequal(assembled, channels));
single = ddp_packets(uint8([255 0 0]), 1);
assert(isequal(single{1}, uint8([65 1 11 1 0 0 0 0 0 3 255 0 0])));
didThrow = false;
try
    ddp_packets(uint8([]), 1);
catch exception
    didThrow = strcmp(exception.identifier, 'ChristmasLights:EmptyFrame');
end
assert(didThrow, 'Empty frames must be rejected.');
fprintf('MATLAB DDP packet tests passed (3 chunks, sequence wrap, PUSH, offsets, RGB, empty rejection).\n');
end
