# Change the display in the browser

Start `python server.py`, open [the preview](http://127.0.0.1:8080) and choose
**Edit scene**. Changes appear in the 3D preview while you work. Saving writes
the active layout; JavaScript changes are no longer needed for scene placement.

## Place and resize scenery

Choose a scenery object in the editor or select it in the preview. Use the
position, rotation and size controls to move or reshape it, and the name and
color controls to identify and style it. Drag the transform handles in the
preview for direct placement. Orbit and camera presets help check depth and
alignment. **Frame selection** (or **F** while outside a text field) centers the
camera on the selected object.

Position uses meters: **X** moves left/right, **Y** changes height, and **Z**
moves toward/away from the front of the display. Rotation uses degrees. **Size**
uses meters for width, height and depth; for example, set the house width to
10 to make it 10 m wide. The layout stores these dimensions as scale factors
relative to each object's native size. Objects are placed from their base
center, except the house, whose origin is at the center of its
front wall at ground level.

| Scenery | Native size before scaling |
| --- | --- |
| House | 8 m wide, 4 m deep; walls 3.5 m high, roof peak 5.8 m |
| Pine tree | 1 m wide and 1 m high |
| Cone / mega-tree body | 1 m diameter and 1 m high |
| Box | 1 m wide, high and deep |
| Arch | 1 m wide and 1 m high |
| Three arches | Three 2 m wide, 1.2 m high arches with centers 2.3 m apart |

Choose an item in the menu and press **+ Add** to create scenery. Removing
scenery removes its geometry; its light fixtures remain in the display.
**Undo**, **Redo** and **Reset draft** help compare changes before saving.

## Keep lights aligned

The sample house is linked to its roofline, window and door fixtures. Its
mega tree is linked to the tree strands and star; mini trees, arches and the
walkway have their corresponding light groups. Linked fixtures follow the
object's position, rotation and scale when the editor moves it. Uncheck
**Move attached lights** to change the scenery while leaving its lights in place.

Select a light fixture to move or resize its pixels directly. The light group's
wire order and start channel remain the mapping used for incoming RGB data.
Moving a fixture changes its coordinates, not its channel count. The **+ Add**
menu also creates a 64-pixel light string, a 192-pixel tree or a 40-pixel light
arch. New fixtures use unused channels after the current display's span.
Removing a fixture keeps other fixtures' channel addresses unchanged; at least
one fixture must remain. Re-export xLights models after changing fixture
geometry or adding/removing lights:

```powershell
python tools\export_xlights.py
```

For a custom active file, add `--layout layouts/my-display.json`. Update the
xLights controller's channel count and model patch to include any new fixtures.

Scene settings also control the sky and ground colors, snowfall, glow, ground
visibility and exposure. These appearance changes do not change channel data.

## Save, transfer and recover a scene

**Save changes** validates and writes the active layout, then updates the running
preview. The previous file is kept beside it with `.bak` appended, for example
`layouts/default.json.bak`. Editor changes remain a draft until saved.
**Done editing** offers **Keep editing**, **Discard changes** and **Save and
close** when the draft has unsaved changes.

**Export scene** keeps a portable JSON copy. **Import scene** loads a compatible
layout JSON to preview it before saving. Use another file as the active display with
`python server.py --layout layouts/my-display.json`; saves update that file.

If another browser saves first, the editor reports a save conflict. Export your
draft, then leave the editor and enter it again to load the newer layout. The
server does not overwrite a newer revision with an older browser's draft.
Changes made directly to the active file also block an editor save. Export any
browser draft and restart the server before editing again; refreshing the
browser alone does not read external file changes.

To restore the last file backup, stop the server, then run:

```powershell
Copy-Item -LiteralPath 'layouts\default.json.bak' -Destination 'layouts\default.json'
python server.py
```

For a custom active file, use its backup and restart with the same `--layout`
argument. The backup is the previous save, so export separate copies for
longer-term versions.

## Preview the same edits in Unreal

Successful editor saves also copy the active layout to
`unreal/ChristmasLights/Content/Data/default.json`. This includes saves made with
`--layout` pointing to a custom file. Stop Unreal Play and start it again to
load the updated scene. If the browser reports an Unreal copy failure, the
primary layout is still saved; copy it to Unreal manually or fix the destination
and save again. `--no-unreal-sync` disables this copy.

After updating an existing Unreal project, rebuild it and rerun
`Scripts/setup_assets.py` once for the new scenery material. The test project
supports the same object transforms and fixture coordinates, with simpler
house details, opaque cone surfaces and segmented arch supports. Ground color
and visibility are shared; browser sky, snowfall, glow and exposure use the
browser renderer's settings. See [the Unreal instructions](../unreal/ChristmasLights/README.md)
for setup. Unreal compilation and rendering require an installed engine and
have not been verified in this workspace.
