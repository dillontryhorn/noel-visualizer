function send_light_show(durationSeconds, destinationPort, destinationHost)
%SEND_LIGHT_SHOW Drive the browser bridge or Unreal with a rainbow DDP test.
% send_light_show(10)          -> Python bridge 127.0.0.1:4048 -> UE :4049
% send_light_show(10, 4049)    -> UE directly (stop the Python relay first)
% Uses MATLAB's Java interface; no Unreal or Instrument Control toolbox.
arguments
    durationSeconds (1,1) double {mustBeFinite,mustBePositive} = 10
    destinationPort (1,1) double {mustBeInteger,mustBeInRange(destinationPort,1,65535)} = 4048
    destinationHost (1,1) string = "127.0.0.1"
end
if ~usejava('jvm')
    error('ChristmasLights:NoJVM', 'Configure a supported Java runtime or set MATLAB_JAVA before startup to send UDP. See matlab/README.md.');
end
projectRoot = fileparts(fileparts(mfilename('fullpath')));
layout = jsondecode(fileread(fullfile(projectRoot, 'layouts', 'default.json')));
fixtures = layout.fixtures;
channelCount = 0;
for fixtureIndex = 1:numel(fixtures)
    fixture = getFixture(fixtures, fixtureIndex);
    channelCount = max(channelCount, fixture.startChannel - 1 + size(fixture.pixels, 1) * 3);
end
if isfield(layout, 'channelCount')
    channelCount = max(channelCount, layout.channelCount);
end
socket = javaObject('java.net.DatagramSocket');
cleanup = onCleanup(@() socket.close()); %#ok<NASGU>
address = javaMethod('getByName', 'java.net.InetAddress', char(destinationHost));
sequence = 1;
frameCount = 0;
frameRate = 30;
timer = tic;
fprintf('Sending %d RGB channels to %s:%d for %.1f s.\n', channelCount, destinationHost, destinationPort, durationSeconds);
while toc(timer) < durationSeconds
    elapsed = toc(timer);
    channels = zeros(1, channelCount, 'uint8');
    for fixtureIndex = 1:numel(fixtures)
        fixture = getFixture(fixtures, fixtureIndex);
        pixelCount = size(fixture.pixels, 1);
        hue = mod((0:pixelCount-1).' / max(1, pixelCount) - elapsed * 0.2 + fixtureIndex * 0.04, 1);
        rgb = hsv2rgb([hue ones(pixelCount, 1) 0.85 * ones(pixelCount, 1)]);
        first = fixture.startChannel;
        channels(first:first + pixelCount * 3 - 1) = reshape(uint8(round(rgb.' * 255)), 1, []);
    end
    [packets, sequence] = ddp_packets(channels, sequence);
    sendPackets(socket, address, destinationPort, packets);
    frameCount = frameCount + 1;
    pause(max(0, frameCount / frameRate - toc(timer)));
end
% End with a complete black frame to leave both viewers in a known state.
packets = ddp_packets(zeros(1, channelCount, 'uint8'), sequence);
sendPackets(socket, address, destinationPort, packets);
fprintf('Sent %d rainbow frames and one blackout frame.\n', frameCount);
end

function fixture = getFixture(fixtures, index)
if iscell(fixtures)
    fixture = fixtures{index};
else
    fixture = fixtures(index);
end
end

function sendPackets(socket, address, port, packets)
for packetIndex = 1:numel(packets)
    bytes = typecast(packets{packetIndex}, 'int8');
    datagram = javaObject('java.net.DatagramPacket', bytes, int32(numel(bytes)), address, int32(port));
    socket.send(datagram);
end
end
