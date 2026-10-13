This Unreal Engine 5.6 C++ project receives the same RGB channel stream as the browser visualizer. The Python bridge relays DDP to `127.0.0.1:4049`; Unreal builds the shared fixture layout and displays each bulb as an emissive sphere. Saved browser scenes create the same house, pines, boxes, cones and arches with shared positions, rotation, sizes and colors. It is a visual test scene with simpler materials and geometry than the browser preview.

The repository contains source, configuration, and JSON layout data. Unreal generates its own material and map binary assets through the supplied Editor Python script. **Unreal Engine is unavailable on the implementation machine, so this project's engine compilation, generated shaders, and rendering have not been executed.**

## Build and create assets

Install Unreal Engine 5.6 through Epic's launcher, Visual Studio 2022 with **Game development with C++**, the MSVC v143 toolchain, and a supported Windows SDK. Unreal Engine is publicly available under Epic's license; see [Epic's UE5.6 toolchain guidance](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine?application_version=5.6).

From the repository root in PowerShell, adapt the engine path to the installation:

```powershell
$ue = 'C:\Program Files\Epic Games\UE_5.6'
$project = Join-Path (Get-Location) 'unreal\ChristmasLights\ChristmasLights.uproject'
$setup = Join-Path (Get-Location) 'unreal\ChristmasLights\Scripts\setup_assets.py'
& "$ue\Engine\Build\BatchFiles\Build.bat" ChristmasLightsEditor Win64 Development "-Project=$project" -WaitMutex
& "$ue\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" $project -run=pythonscript "-script=$setup" -unattended -nosplash
& "$ue\Engine\Binaries\Win64\UnrealEditor.exe" $project /Game/Maps/LightShow
```

The build must succeed before running the asset script. The project enables PythonScriptPlugin and EditorScriptingUtilities for setup, and the built-in ProceduralMeshComponent plugin for saved scenery. The script copies `layouts/default.json` into `Content/Data/default.json`, creates `/Game/Materials/M_Pixel` and `/Game/Materials/M_Scenery`, and saves `/Game/Maps/LightShow`. The map contains a Light Show DDP Receiver actor whose Details panel exposes port, bind address, layout path, bulb radius, packet bound, and timeouts. The scene and pixels appear when **Play** starts; the Editor viewport before Play is empty. Initial defaults use the built-in Entry map so the source project can open before generated assets exist. Setup switches startup defaults to the generated map.

To run setup interactively, open **Tools > Execute Python Script** and select `Scripts/setup_assets.py`. Save other open work first: setup loads its generated map. Rerunning setup refreshes the copied layout and rebuilds these two generated materials; preserve any manual material customizations separately.

## Test the shared stream

Start the Python server using the main repository instructions, open its browser visualizer, and press **Play** in Unreal. Choose a browser demo pattern or **Live input** for external DDP. Unreal's HUD should show **LIVE**, a growing frame count, and 1,425 pixels / 4,275 channels for the default layout.

Controls: **W/A/S/D** fly, **mouse** look, **Q/E** descend/ascend, **Home** reset the overview. In Play In Editor, **Shift+F1** releases the mouse. Run a single Play window: a second local receiver cannot bind the same UDP port.

A game window can also be launched after asset setup:

```powershell
& "$ue\Engine\Binaries\Win64\UnrealEditor.exe" $project /Game/Maps/LightShow -game -DdpBind=127.0.0.1 -DdpPort=4049
```

The optional [MATLAB sender](../../matlab/README.md) exercises the same bridge and Unreal stream without additional MATLAB toolboxes. A direct external sender can target Unreal's UDP 4049 while the Python relay is stopped. The Python bridge is the recommended path for xLights: configure its DDP output for UDP 4048 and select **Live input** in the browser.

Use **Edit scene** in the browser and **Save changes** to synchronize the bundled
`Content/Data/default.json`. Stop Unreal Play, then press **Play** again to read
the saved geometry. RGB frames keep streaming while Play runs, but changes to
the layout file are loaded only at the next Play start. The server also copies
editor saves when `--layout` points at a custom file. `--no-unreal-sync` disables
that copy. A copy failure is reported by the browser; the primary layout is still
saved and can be copied manually.

After upgrading an existing project to the scene editor, **rebuild the Editor
target and rerun `Scripts/setup_assets.py` once** to create the vertex-color
scenery material. If using a custom layout, save it through the browser again
after setup because setup copies the repository's default file.

For a file edited outside the browser, rerun setup or copy it explicitly before restarting Play:

```powershell
Copy-Item -LiteralPath 'layouts\default.json' -Destination 'unreal\ChristmasLights\Content\Data\default.json'
```

Runtime settings may also be specified in `Config/DefaultGame.ini` under `[ChristmasLights]`: `BindAddress`, `ListenPort`, and `LayoutFile`. Values changed from the actor's class defaults in the map take priority over these INI defaults. A relative layout path resolves under project `Content`; an absolute path is supported for local testing. Command-line `-DdpBind`, `-DdpPort`, and `-LightLayout` override both. Disable **Build Scenery** when placing scenery manually in Unreal; pixels continue to use the shared layout.

The optional `scene` field contains version 1, environment settings and up to
100 scenery objects. Each object has an ID, type, position, rotation, positive
scale and `#RRGGBB` color. The receiver rejects invalid transforms and types.
Object transforms use the same Euler XYZ rotation order as Three.js and are
applied in scale, rotation, translation order before converting meters to
Unreal centimeters. Ground color and visibility are shared. Snowfall, browser
sky color, browser exposure and browser glow are currently browser settings;
Unreal uses its own exposure and bloom. Arch supports use rectangular segments,
cones use opaque surfaces and house details are simplified. Layouts without a
`scene` field retain the original sample house, ground and mega-tree post.

## Receiver behavior and checks

DDP v1 has a ten-byte header, byte offsets, big-endian offset/length fields, display destination 1, and RGB24 data type `0x0B` (legacy RGB `0x01` also accepted). Non-PUSH chunks accumulate in a pending buffer. PUSH commits the transaction, including partial updates, while untouched channels retain their previous values. Sequence values 0..15 are accepted, with no assumption that chunks share a sequence. Timestamp, query/reply, storage, RGBW, non-RGB formats, and other destinations are rejected. The Python relay emits the supported RGB24 form; [WLED's protocol definitions](https://github.com/wled/WLED/blob/main/wled00/src/dependencies/e131/ESPAsyncE131.h) document these data types.

The receiver validates exact datagram length and bounds offsets against the layout's channel span. Layout loading rejects overlapping channel ranges, duplicate IDs, invalid coordinates, and channel spans above one million; declared `channelCount` may include padding. Browser coordinates `[x,y,z]` in meters become Unreal `[z*100,x*100,y*100]` in centimeters.

The socket is nonblocking and polled on the game thread with a default bound of 256 packets per tick. Materials and components are changed on that same thread; the newest committed frame is applied once per tick. Incomplete transactions are discarded after one second, malformed chunks discard pending data, and the last complete frame is held when input stops. HUD signal state turns idle after two seconds. DDP provides no retransmission; packet loss or multiple interleaved sources can produce partial displays. This test is intended for one sender, normally over loopback.

`M_Pixel` combines three per-instance color floats, passes them through a VertexInterpolator, multiplies by a Glow parameter, and connects the result to emissive output. Bulbs are instances of one mesh rather than thousands of separate dynamic materials. Rendering uses fixed exposure and bloom; authored scenery uses a two-sided unlit material with vertex colors and a Color parameter. [Epic's material editing API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MaterialEditingLibrary?application_version=5.6) generates the assets; [ProceduralMeshComponent](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/ProceduralMeshComponent/UProceduralMeshComponent?application_version=5.6) builds scenery at runtime.

Run the included Unreal automation checks after building the Editor target:

```powershell
& "$ue\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" $project -unattended -nop4 -NullRHI '-ExecCmds=Automation RunTests ChristmasLights' '-TestExit=Automation Test Queue Empty' -log
```

`ChristmasLights.DDP.ChunkAssembly`, `.Validation`, and `.DiscardPending` cover atomic PUSH updates, partial persistence, overflow, malformed headers, unsupported variants, legacy RGB, and transaction discard. `ChristmasLights.Scene.Transform` checks axes, units, rotation order and nonuniform scale against known coordinates. Inspect `Saved/Logs` for automation results. The Python asset script passed a local syntax check; Unreal tests are supplied for execution on an installed engine and are not reported as having passed here.

Packaging must follow asset setup. Material content is configured for cooking and `Content/Data` is staged as UFS so `FFileHelper` can read the layout in a packaged build. Include `/Game/Maps/LightShow` in the maps to package if using a custom packaging profile.
