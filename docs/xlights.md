# Send a show from xLights

Install [xLights](https://xlights.org/releases/) separately. This guide follows its
[Ethernet controller setup](https://manual.xlights.org/xlights/chapters/chapter-two-quick-start-guide/network-definition)
and [model import](https://manual.xlights.org/xlights/chapters/chapter-four-tabs/download-import-models)
documentation. Exact labels may vary between xLights releases. Packet
compatibility and exported node mappings are tested separately; the xLights GUI
has not been run in the development environment.

## Use DDP on the same computer

1. Run `python server.py` and open `http://127.0.0.1:8080`.
2. In xLights' **Controllers** tab, add an Ethernet controller named `Visualizer`.
   Set its protocol to **DDP**, IP address to `127.0.0.1` and channel count to
   `4275`. Use RGB channel order. A separate show folder with this controller
   first, starting at global channel 1, makes the supplied mapping easiest to use.
3. Map the controller's first output byte to visualizer channel 1. When this is
   the first controller and its global start channel is 1, either DDP channel
   numbering setting yields offset 0. If xLights has earlier controllers, disable
   **Keep Channel Numbers** so this controller's output rebases to byte offset 0,
   and add `controllerGlobalStart - 1` to every model start in the table below.
   Avoid controller auto-layout settings that rewrite the fixture start channels.
4. Import each `xlights/*.xmodel` in the **Layout** tab. Check **Start Channel**
   against the table below (plus the offset described above if applicable); if
   xLights rewrites starts during import or controller assignment, set them
   explicitly. Keep each model's string type **RGB Nodes**.
5. Add effects to those models, enable **Output to Lights**, and play the sequence.
6. Select **Live input** in the browser. Packet counters and input age should update.

DDP uses UDP port `4048`. The receiver assembles chunks by their zero-based byte
offsets and displays the frame when the sender marks PUSH. Leave DDP broadcast
sync disabled for the simplest unicast setup. Query/configuration discovery is
not implemented; enter the IP address manually.

## Default fixture mapping

| Model file | Pixels | RGB channels |
| --- | ---: | ---: |
| `roofline.xmodel` | 242 | 1–726 |
| `windows.xmodel` | 128 | 727–1110 |
| `door.xmodel` | 73 | 1111–1329 |
| `megatree.xmodel` | 512 | 1330–2865 |
| `star.xmodel` | 50 | 2866–3015 |
| `mini-left.xmodel` | 72 | 3016–3231 |
| `mini-center.xmodel` | 72 | 3232–3447 |
| `mini-right.xmodel` | 72 | 3448–3663 |
| `arches.xmodel` | 120 | 3664–4023 |
| `path.xmodel` | 84 | 4024–4275 |

[channel-map.csv](../xlights/channel-map.csv) includes DDP offsets and sACN
universe/slot ranges. [pixel-map.csv](../xlights/pixel-map.csv) lists every node's
exact source coordinate and individual RGB channels.

`.xmodel` geometry is an XY projection quantized to 25 cells per meter. Nodes
that project to the same cell move to nearby vacant cells so all node numbers
remain present once. Imported models are positioned and sized in xLights' own
layout editor; these files do not reproduce the complete 3D scene. For each
fixture, node 1 starts at its declared channel; node N starts at
`startChannel + 3 * (N - 1)`.

## Use E1.31 / sACN

Configure the Ethernet controller as **E1.31**, destination `127.0.0.1`, start
universe `1`, universe count `9`, and **510 channels per universe**. The default
service maps consecutive universes with that same size. Only the first 195 slots
of universe 9 are needed. Turn off E1.31 synchronization for this preview.

To use 512 slots per universe instead, match both ends explicitly:

```powershell
python server.py --universe-size 512
python tools\export_xlights.py --universe-size 512
```

The second command updates CSV universe/slot mapping; it does not change RGB
fixture channels. With 512-slot universes an RGB pixel can straddle universes.
Keep the fixture start channels as shown above. The receiver handles this split.

Multicast reception is opt-in:

```powershell
python server.py --udp-host 0.0.0.0 --sacn-multicast
```

The service joins the multicast groups for its configured universe range. A
network interface or firewall can prevent multicast delivery; unicast is the
default and easiest way to test locally.

## Send from another computer

Start the service with a UDP bind address that accepts network traffic:

```powershell
python server.py --udp-host 0.0.0.0
```

Set the xLights controller IP to the visualizer computer's LAN IPv4 address.
If Windows asks about network access, permit Python on the network you intend to
use. HTTP remains on `127.0.0.1`, so open the viewer on the visualizer computer.
To view it from another computer as well, use `--host 0.0.0.0` and navigate to
`http://VISUALIZER-IP:8080`. This service has no login and is intended for a
trusted local machine or LAN.

## Troubleshooting

- **Packet count stays at zero:** Enable xLights output, select the correct
  controller protocol/IP, and check the UDP bind address and firewall. The
  browser must use Live input to display received data.
- **Fixtures use the wrong colors or order:** Use RGB Nodes, verify model start
  channels against the CSV, and rebase DDP offsets if other controllers precede
  the visualizer controller.
- **First universe looks correct, later fixtures shift:** Match 510 versus 512
  channels per universe on both ends and check the start universe.
- **Port already in use:** Stop the other program using that port or change
  the service port and corresponding sender. Only one preview service should
  listen on a given UDP port.
- **Unreal has no data:** Start Play in its test map and enable the browser's
  Unreal relay; its default receiver port is 4049, separate from input port 4048.
