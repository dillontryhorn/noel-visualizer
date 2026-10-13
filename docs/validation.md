# Validation performed

The default display contains 1,425 RGB pixels, 4,275 channels, and ten fixtures.

- `python -m unittest discover -s tests -v`: **33 tests passed**. Coverage includes malformed and bounded DDP/sACN input, PUSH assembly, sequence handling, sACN source priority and expiration, 510/512 channel universes, layout validation, atomic controls, multiple SSE readers, actual UDP input → HTTP preview → Unreal relay byte equivalence, scene validation, layout persistence and backup, revision and external-file conflicts, stale browser saves after restart, and Unreal copy behavior.
- `node --test tests/scene_model.test.mjs`: **14 tests passed**, covering linked object transforms, independent fixture movement, rotation and resizing, undo snapshots, added and removed geometry, channel reservations, import validation, and frontend-to-Python persistence.
- Scene editor browser check: numeric house placement, linked sizing, Undo/Redo, and dragging a transform handle were exercised without console errors. A private test scene saved the moved house and a new 40-pixel arch: file and API readback confirmed 1,465 pixels / 4,395 channels, the correct linked roof coordinates, and an original-scene backup. Reloading the browser retained those edits. The unsaved-change dialog and discard flow were also checked. The shipped sample layout was not changed by those tests, and private QA files were removed.
- Browser inspection: Three.js scene and shaders rendered without console errors after corrections. Mobile and desktop layouts were inspected. Effect selection, pause, timeline seeking, brightness, fixture masks, bridge switching, camera selection, and setup guide were exercised.
- Browser → service check: pause and seek produced time 120 with a frozen frame; brightness zero produced all zero channels. Switching from a paused demo to Live resumed reception. A real DDP sender delivered 60 frames / 180 packets, and the browser output contained exactly 1,425 copies of the requested RGB color. Disabling the window fixture zeroed only its mapped channels.
- xLights export: each generated model contains its node numbers exactly once; exported CSV positions and RGB addresses match the shared JSON. The xLights desktop application's import/playback was not executed.
- MATLAB R2026b: serializer assertions passed. A real Java UDP loopback check received 21 datagrams representing six complete rainbow frames and one complete blackout frame, each spanning 4,275 channels.
- Unreal source project: project JSON, Python asset bootstrap syntax, and copied layout consistency checked. Legacy sample scenery clearance was analytically checked for all 1,425 bulb spheres, with at least 2 cm clearance from the house, roof, and ground. The C++ receiver includes Unreal automation tests.

Scene editor additions: the Unreal asset script still passes a Python syntax
check. The actual Euler XYZ expressions extracted from `SceneGeometry.cpp`
were compared with the installed Three.js renderer for 1,000 arbitrary rotations
and nonuniform scales; the maximum difference was `1.42e-14` meters. The supplied
`ChristmasLights.Scene.Transform` automation test checks units, axis mapping,
individual rotations and a known compound transform. These source checks do
not confirm Unreal compilation or rendering.

**Unreal Engine is not installed in this environment.** Engine compilation, execution of the asset bootstrap, shader compilation, Unreal automation tests, and rendered comparison must be performed with the build/test commands in `unreal/ChristmasLights/README.md`.

The browser automation's download event timed out while saving the preview. PNG download was therefore not confirmed in the in-app browser; the normal browser download implementation is included.
