# Transport, control API and supported packet subsets

The Python service owns the show clock and RGB output. At 30 frames per second
by default, it generates a demo or samples live input, applies master brightness
and fixture enable masks, publishes a browser frame and sends the same RGB bytes
to the Unreal relay. Reading a frame does not advance the clock.

## Addresses and mapping

| Purpose | Default address | Configuration |
| --- | --- | --- |
| Browser and control API | HTTP `127.0.0.1:8080` | `--host`, `--port` |
| DDP input | UDP `127.0.0.1:4048` | `--udp-host`, `--ddp-port` |
| E1.31 / sACN input | UDP `127.0.0.1:5568` | `--udp-host`, `--sacn-port` |
| Unreal output | UDP `127.0.0.1:4049` | `--relay-host`, `--relay-port`, `--no-relay` |

The default display spans channels 1–4275. Layout channels are one-based; DDP
byte offsets and internal RGB buffer indices are zero-based. Fixture node N uses
R/G/B channels `startChannel + 3 * (N - 1)` through two channels after that.
The shared coordinates are meters, X horizontal, Y up and positive Z toward the
viewer. Unreal converts to centimeters and its Z-up coordinate system.

sACN maps universe U to internal byte offset
`(U - startUniverse) * universeSize`. Defaults are start universe 1 and size 510.
The final universe may contain fewer data slots; missing slots are zero-filled.
The size can be changed to 512 when the sender uses that mapping.

## DDP input and output

The receiver supports version-1 display writes, destination 1 or 255, RGB8 type
`0x0B`, unspecified type `0`, and legacy type `1`. A 10-byte header carries flags,
sequence, data type, destination, big-endian byte offset and big-endian payload
length. Chunks stage
per sender and become a displayed frame on PUSH. Exact repeated sequenced chunks
are suppressed. A partial write retains the other channels from that sender's
staged frame. Each sender's staging state expires after 2.5 seconds.

The optional time field is parsed but its scheduled time is not honored; a PUSH
displays immediately. Query, reply, storage and non-RGB traffic are ignored.
Malformed packet lengths or writes beyond the layout's channel span are rejected
and counted. The preview does not provide DDP controller discovery or a full DDP
device configuration service.

The Unreal relay sends a complete output buffer each tick, split into payloads
of at most 1440 bytes, RGB8 type `0x0B`, display destination 1 and PUSH on the last
packet. The relay uses incrementing packet sequences 1–15. Input and relay ports
are separate so both applications can run on one computer.

DDP input holds its last displayed frame when the sender stops. Disable the
affected fixtures or return to Demo to change it. Unreal likewise holds its last
complete frame and marks the signal idle when relay traffic stops.

The compatibility reference is
[xLights' DDP sender](https://github.com/xLightsSequencer/xLights/blob/master/src-core/outputs/DDPOutput.cpp).
See [sources.md](sources.md) for the original specification link.

## E1.31 / sACN input

The supported subset is IPv4 unicast, with optional multicast membership for
the configured universe range. Data packets must use the standard ACN identifier,
root/framing/DMP data vectors, sequential slots and NULL DMX start code. The
receiver validates lengths, universe range and priority, and applies sequence
filtering, stream termination and 2.5-second source loss.

Within a universe, the highest-priority source wins. Equal-priority sources merge
by the maximum value of each channel (HTP). Sources are bounded to eight per
universe. When all sources for a tracked universe expire, that universe becomes
black. Universes update independently, so this is a practical preview rather
than an atomic multi-universe presentation.

Synchronization packets, nonzero synchronization addresses, force-sync sources
and per-address priority are not supported. Disable synchronization in the
sender. If DDP and sACN both send data, the most recently accepted protocol
controls the live buffer; use one protocol at a time for predictable preview.

The compatibility reference is
[xLights' E1.31 sender](https://github.com/xLightsSequencer/xLights/blob/master/src-core/outputs/E131Output.cpp).

## HTTP API

The browser uses server-sent events (SSE). Other local clients may poll JSON.
Requests must target the server's own origin. Controls require a JSON object and
`Content-Type: application/json`.

| Route | Result |
| --- | --- |
| `GET /api/layout` | Validated fixture geometry, scenery, counts, universe mapping and `revision` |
| `GET /api/status` | Current controls and receiver/relay status, without RGB data |
| `GET /api/frame` | Status plus `rgb`, a base64 encoding of the full channel buffer |
| `GET /api/events` | SSE stream; each data event contains the same shape as `/api/frame` |
| `POST /api/control` | Atomically validate and apply controls, then return a current snapshot |
| `POST /api/layout` | Validate, save and apply a complete layout using its expected revision |

Decode `rgb` to bytes. Its length is `channelCount`; each fixture samples from its
declared `startChannel - 1`. The `frame` field increments on the service clock.
`time` is the demo playhead, looping through a 120-second duration. Status includes
`activeProtocol`, `lastPacketAge`, receiver packet/error/ignored counts, and relay
destination/enabled/error/count fields. A successful UDP send is not an
acknowledgement that Unreal is receiving; its in-game HUD provides that check.
Status also includes `layoutRevision`; clients should refresh `/api/layout` when
this value changes.

### Scene and layout saves

`POST /api/layout` accepts `{"layout": <complete layout>, "revision": <integer>}`.
Use the revision returned by `GET /api/layout`. Success returns `layout` (including
the new revision), `status` and `unrealSync`. Revisions are positive JavaScript-safe
integer tokens, freshly seeded when the server starts and incremented on saves;
they are not stored in the layout file. An outdated revision returns
HTTP 409; obtain the latest layout before resubmitting. An active file changed
or deleted outside the server also returns 409 without replacing it; export
any browser draft and restart the server to load the external file. Reloading
the browser alone does not reread disk. Invalid geometry or scenery returns HTTP 400. Layout bodies are
limited to 8,000,000 bytes; control bodies remain limited to 16 KiB.

The service validates the complete replacement before writing, preserves the
previous active file as `<layout file>.bak`, replaces the file atomically and
applies the mapping to the running service. Receiver buffers are reset when
channel mapping changes; live senders should continue output after a save.
A successful save also copies the layout to the bundled Unreal
`Content/Data/default.json` when synchronization
is enabled. `unrealSync.saved` reports that copy, and `unrealSync.error` describes
a copy failure. A failed Unreal copy does not undo a successful primary save.
Unreal reads the new geometry when Play starts again.

The optional `scene` object has `version: 1`, `environment` and `objects`.
Environment fields are `skyColor`, `groundColor`, `snowfall`, `glow`,
`groundVisible` and `exposure` (0.1–3). A scenery object defines `id`, `name`,
`type`, `position`, `rotation`, `scale`, `color` and `fixtureIds`. Supported types
are `house`, `pine`, `box`, `cone`, `arch` and `arches`; there may be up to 100
objects. Transform vectors contain three finite numbers: positions are meters
within ±1000, rotations are Euler XYZ degrees within ±360, and scales are
positive factors from 0.001 to 1000. Each fixture may be linked to one scenery
object. The browser editor applies object transformations to linked fixture
pixels before saving; the server and Unreal use these saved world coordinates.
Older layouts without a scene receive editable sample scenery in the browser.

Supported control fields:

| Field | Accepted value |
| --- | --- |
| `mode` | `"demo"` or `"live"` |
| `effect` | `"aurora"`, `"candy"`, `"rainbow"`, `"sparkle"`, `"solid"`, `"blackout"` |
| `playing` | Boolean; pause freezes the sampled live frame or demo playhead |
| `brightness` | Number from 0 to 1; applies to demo, live and relay output |
| `speed` | Number from 0.25 to 3; multiplies the demo clock |
| `bpm` | Number from 40 to 240; procedural demo pulse rate |
| `time` | Number from 0 to 120; seek the demo playhead |
| `solidColor` | Six-digit hex color, such as `"#ffcc88"` |
| `fixtureEnabled` | Object mapping known fixture IDs to booleans; merges specified values |
| `relayEnabled` | Boolean |

Controls become visible in the RGB output on the next clock tick. Unknown fields,
invalid values, non-finite numbers and bodies over 16 KiB fail without partially
applying the request.

Example in PowerShell while the service is running:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8080/api/control -Method Post -ContentType application/json -Body '{"mode":"demo","effect":"candy","brightness":0.75,"playing":true}'
```

## Exercise the input without xLights

Keep `python server.py` running, then open a second terminal:

```powershell
python tools\send_test.py --protocol ddp --seconds 10
python tools\send_test.py --protocol sacn --universe-size 510 --start-universe 1 --seconds 10
```

The sender switches the preview to Live, starts playback and sets brightness to
1 through the local API. Its default effect is a rainbow. Use
`--effect chase --color '#ff0000'` for a chase or
`--effect solid --color '#00ff00'` for a solid green frame. `--no-auto-live`
leaves browser controls unchanged. `--api`, `--host`, `--port`, `--layout`,
`--fps` and the sACN mapping options allow testing other configurations.

The sender uses unicast. It can target Unreal directly with
`--protocol ddp --port 4049 --no-auto-live`, but disable the service relay first
so only one sender drives that receiver. For a full integration test, send to the
service's input port and inspect both browser output and the Unreal HUD.
