# xLights fixture exports

Import the `.xmodel` files into xLights' Layout tab and verify the start channels
in `channel-map.csv`. Follow [docs/xlights.md](../docs/xlights.md) to configure
the controller and output.

The exports preserve every fixture's RGB node numbering. Their geometry is an
approximate XY projection with nearby-cell displacement for overlapping nodes;
the full 3D coordinates remain in `../layouts/default.json` and `pixel-map.csv`.

Regenerate all exports and maps with:

```powershell
python tools\export_xlights.py
```

The default map uses universes starting at 1 and 510 slots per universe. Use
`--universe-size 512` or `--start-universe N` when your receiver configuration
differs. These options change CSV universe addresses, not fixture RGB channels.
