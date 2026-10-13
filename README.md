# Christmas Lights Visualizer

A local 3D Christmas light show preview with a Python service, a Three.js browser
viewer, and an Unreal Engine 5.6 C++ test project. The sample display has 1,425 RGB
pixels across a house outline, windows, doorway, mega tree, topper, mini trees,
arches and walkway. Both renderers use the same fixture coordinates and channel
mapping.

The service generates an animated demo or receives live RGB output from publicly
available sequencers such as [xLights](https://xlights.org/). It relays the displayed
RGB frame to Unreal over local UDP. No physical lighting controller is required.

## Run the browser visualizer

Install **Python 3.10 or newer**, then run these commands in the repository:

```powershell
python server.py
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080) in a browser with WebGL enabled.
Keep the terminal open; stop the service with `Ctrl+C`. The browser dependencies
are included locally, so the viewer needs no npm install or CDN connection.

On Windows, the launcher also accepts the service's command-line arguments:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

The demo runs without xLights or Unreal. Select an effect, adjust brightness,
speed and BPM, pause or scrub the timeline, and enable individual fixture groups.
Use the camera controls to inspect the display from different angles. Switch to
**Live input** when sending packets from a sequencer.

## Connect xLights

Use one Ethernet controller addressed to `127.0.0.1`, outputting **4,275 RGB
channels starting at channel 1**. Select either:

| Protocol | Destination | Mapping |
| --- | --- | --- |
| DDP | UDP port 4048 | Byte offset 0 corresponds to channel 1; RGB order |
| E1.31 / sACN | UDP port 5568 | Universes 1–9, 510 channels per universe |

Import the supplied `xlights/*.xmodel` files and check each model's start channel
against [xlights/channel-map.csv](xlights/channel-map.csv). The custom models
preserve wire node numbers and use an approximate 2D projection; the browser and
Unreal retain the original 3D coordinates. Then enable **Output to Lights** in
xLights and choose **Live input** in the browser.

See [the full xLights setup and mapping guide](docs/xlights.md) for DDP options,
512-channel universes and input from another computer.

## Run the Unreal Engine test

The project is at
[unreal/ChristmasLights/ChristmasLights.uproject](unreal/ChristmasLights/ChristmasLights.uproject).
Install **Unreal Engine 5.6** and its Windows C++ build toolchain, build the editor
target, then run the supplied asset/setup script to create the playable test map.
The Python visualizer service sends the displayed RGB values to
`127.0.0.1:4049` by default, so the browser demo and live xLights output can both
drive the Unreal scene.

Follow [the Unreal project's build and test instructions](unreal/ChristmasLights/README.md).
Unreal Engine was not installed in the development environment; the delivered
source project must be built and visually checked on a machine with the engine.

An optional [MATLAB test sender](matlab/README.md) generates DDP frames from the
same layout. It can drive both renderers through the Python bridge or target
Unreal directly. It requires MATLAB with Java enabled and no additional MATLAB
toolboxes. The MATLAB packet serialization and actual loopback UDP transmission
were checked locally; Unreal rendering still requires the engine.

## Customize the display

Use **Edit scene** in the browser to change the display without editing JavaScript.
Select the house, a tree, an arch or a light fixture; move it using the handles or
enter its position, rotation and size. Add scenery, change colors and adjust the
environment. Linked lights move with their scenery, so resizing the house can
keep its roofline, windows and door lights aligned.

**Save changes** writes the active layout, keeps its previous contents in a
`.bak` file, and applies the result to the running preview. It also copies the
layout to the bundled Unreal project; restart Unreal **Play** to load it. Follow
[the scene editor guide](docs/scene-editor.md) for controls, linked lights,
import/export and recovery.

For another display file, run
`python server.py --layout path/to/layout.json`. Advanced users can also edit
[layouts/default.json](layouts/default.json) directly. A fixture defines a unique
`id`, label, type, one-based `startChannel` and ordered `pixels` array. Each pixel
is `[x, y, z]` in meters: X is horizontal, Y is up and positive Z points toward the
viewer. Each pixel occupies three consecutive channels in RGB order. Restart
the server after editing a file externally.

The service validates coordinates and rejects overlapping channel ranges.
After changing fixture geometry or channels, regenerate the matching xLights exports:

```powershell
python tools\export_xlights.py
```

For a custom layout:

```powershell
python tools\export_xlights.py --layout layouts\my-display.json --output xlights\my-display
```

Editor saves synchronize Unreal's `Content/Data/default.json`, including when the
service uses a custom layout file. For changes made externally, copy the desired
JSON there or set Unreal's `LayoutFile` to the active file before restarting Play.
Use `--no-unreal-sync` to disable editor saves to the bundled Unreal copy.

## Development and limits

```powershell
python server.py --help
python -m unittest discover -s tests -v
```

See [docs/protocols.md](docs/protocols.md) for packet subsets and API details,
[docs/sources.md](docs/sources.md) for primary references, and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for licenses. The application
source is [MIT licensed](LICENSE).

This is a visualizer and protocol bridge. Sequence files such as FSEQ are played
by an external sequencer; they are not directly imported by this application.
The demo BPM controls procedural effects and does not perform audio analysis.
