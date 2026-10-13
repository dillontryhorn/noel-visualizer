# Third-party software

The application code in this repository is MIT licensed; see [LICENSE](LICENSE).

The browser viewer uses **Three.js 0.180.0**, distributed under the MIT License.
Its vendored files and upstream license are in `web/vendor/three/`. See
[Three.js](https://threejs.org/) and the
[upstream license](https://github.com/mrdoob/three.js/blob/dev/LICENSE).
The pinned package version is recorded in `package.json` and `package-lock.json`.

The Python service uses the Python standard library. Python is installed
separately and is covered by the
[Python license](https://docs.python.org/3/license.html).

xLights is optional, separately installed software. This repository contains
generated model descriptions and an independent protocol implementation; it does
not bundle xLights source code or binaries. See
[xLights](https://xlights.org/) and its
[license](https://github.com/xLightsSequencer/xLights/blob/master/License.txt).

Unreal Engine is installed separately. The C++ project in `unreal/ChristmasLights`
uses Epic's public Unreal Engine APIs and built-in assets; the engine and those
assets remain covered by
[Epic's Unreal Engine license](https://www.unrealengine.com/en-US/eula/unreal).

MATLAB and a Java runtime are optional, separately installed dependencies for the
test scripts in `matlab/`. They are not bundled with this project. See
[MATLAB documentation](https://www.mathworks.com/help/matlab/) and
[MathWorks' supported Java runtimes](https://www.mathworks.com/support/requirements/openjdk.html).
