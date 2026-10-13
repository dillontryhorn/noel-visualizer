# Public software and protocol references

The implementation uses Three.js for the local browser scene, Python's standard
library for transport, and a source Unreal Engine project for a second renderer.
xLights can provide sequenced RGB values through its Ethernet output.

- [Three.js documentation](https://threejs.org/docs/) and
  [source](https://github.com/mrdoob/three.js).
- [Python HTTP server](https://docs.python.org/3/library/http.server.html) and
  [socket documentation](https://docs.python.org/3/library/socket.html).
- [xLights downloads](https://xlights.org/releases/) and
  [source repository](https://github.com/xLightsSequencer/xLights).
- [xLights controller setup](https://manual.xlights.org/xlights/chapters/chapter-two-quick-start-guide/network-definition)
  describes adding an Ethernet controller and mapping universes and channels.
- [xLights controller settings](https://manual.xlights.org/xlights/chapters/chapter-four-set-up/lighting-networks)
  lists DDP and E1.31 among supported Ethernet protocols.
- [xLights model import](https://manual.xlights.org/xlights/chapters/chapter-four-tabs/download-import-models)
  describes importing `.xmodel` files in the Layout tab.
- [xLights DDP output source](https://github.com/xLightsSequencer/xLights/blob/master/src-core/outputs/DDPOutput.cpp)
  is the compatibility reference for byte offsets, packet splitting and PUSH.
- [DDP specification by 3waylabs](https://www.3waylabs.com/ddp/) is the protocol
  author's original specification, linked by the xLights source. That site was
  unavailable during development; the public xLights source was used to verify
  the implemented packet subset.
- [xLights E1.31 output source](https://github.com/xLightsSequencer/xLights/blob/master/src-core/outputs/E131Output.cpp)
  is the compatibility reference for data packets, universe addressing and its
  default of 510 channels per universe.
- [xLights custom-model deserializer](https://github.com/xLightsSequencer/xLights/blob/master/src-core/XmlSerializer/XmlDeserializingModelFactory.cpp)
  and [custom-model parser](https://github.com/xLightsSequencer/xLights/blob/master/src-core/XmlSerializer/XmlSerializeFunctions.cpp)
  provide the XML field and numbered-node-grid references for the exporter.
- [Unreal Engine documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine)
  covers the separately installed engine and C++ toolchain.

These are references for interoperability. No xLights implementation source is
copied into this project.
