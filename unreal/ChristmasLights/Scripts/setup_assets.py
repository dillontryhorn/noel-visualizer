"""Run with Unreal Editor's Python plugin after building ChristmasLightsEditor.

Creates real .uasset/.umap files through Unreal APIs. Rebuilds this project's two
generated materials and refreshes Content/Data/default.json from the shared layout.
"""
from pathlib import Path
import json
import shutil

import unreal


def connect(source, target, input_name=""):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(source, "", target, input_name):
        raise RuntimeError(f"Cannot connect material node to {input_name or 'first input'}")


def output(source, material_property):
    if not unreal.MaterialEditingLibrary.connect_material_property(source, "", material_property):
        raise RuntimeError(f"Cannot connect material output {material_property}")


def make_material(name):
    path = f"/Game/Materials/{name}"
    assets = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    material = assets.load_asset(path)
    if material is None:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, "/Game/Materials", unreal.Material, unreal.MaterialFactoryNew()
        )
    if not isinstance(material, unreal.Material):
        raise RuntimeError(f"{path} must be a Material")
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    return material


def create_pixel_material():
    material = make_material("M_Pixel")
    material.set_editor_property("used_with_instanced_static_meshes", True)
    nodes = []
    for index in range(3):
        node = unreal.MaterialEditingLibrary.create_material_expression(
            material, unreal.MaterialExpressionPerInstanceCustomData, -900, index * 160
        )
        node.set_editor_property("data_index", index)
        node.set_editor_property("const_default_value", 0.0)
        nodes.append(node)
    rg = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionAppendVector, -650, 0)
    rgb = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionAppendVector, -450, 0)
    interpolate = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionVertexInterpolator, -250, 0)
    glow = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -250, 240)
    glow.set_editor_property("parameter_name", "Glow")
    glow.set_editor_property("default_value", 6.0)
    multiply = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionMultiply, -50, 0)
    connect(nodes[0], rg, "A")
    connect(nodes[1], rg, "B")
    connect(rg, rgb, "A")
    connect(nodes[2], rgb, "B")
    connect(rgb, interpolate)
    connect(interpolate, multiply, "A")
    connect(glow, multiply, "B")
    output(multiply, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    unreal.MaterialEditingLibrary.recompile_material(material)
    if not unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).save_loaded_asset(material, False):
        raise RuntimeError("Failed to save M_Pixel")


def create_scenery_material():
    material = make_material("M_Scenery")
    material.set_editor_property("two_sided", True)
    color = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -450, 0)
    color.set_editor_property("parameter_name", "Color")
    color.set_editor_property("default_value", unreal.LinearColor(0.012, 0.020, 0.032, 1.0))
    vertex = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionVertexColor, -450, 180)
    multiply = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionMultiply, -200, 0)
    connect(color, multiply, "A")
    if not unreal.MaterialEditingLibrary.connect_material_expressions(vertex, "RGB", multiply, "B"):
        raise RuntimeError("Cannot connect scenery vertex colors")
    output(multiply, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    unreal.MaterialEditingLibrary.recompile_material(material)
    if not unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).save_loaded_asset(material, False):
        raise RuntimeError("Failed to save M_Scenery")


def main():
    project = Path(unreal.Paths.project_dir()).resolve()
    source = project.parents[1] / "layouts" / "default.json"
    if not source.is_file():
        raise RuntimeError(f"Shared layout missing: {source}")
    layout = json.loads(source.read_text(encoding="utf-8"))
    pixel_count = sum(len(fixture["pixels"]) for fixture in layout["fixtures"])
    destination = project / "Content" / "Data" / "default.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    create_pixel_material()
    create_scenery_material()

    assets = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    map_path = "/Game/Maps/LightShow"
    if assets.does_asset_exist(map_path):
        if not levels.load_level(map_path):
            raise RuntimeError("Cannot load LightShow map")
    elif not levels.new_level(map_path):
        raise RuntimeError("Cannot create LightShow map")
    show_class = unreal.load_class(None, "/Script/ChristmasLights.LightShowActor")
    if show_class is None:
        raise RuntimeError("ChristmasLights C++ module is not loaded; build the Editor target first")
    if not any(actor.get_class() == show_class for actor in actors.get_all_level_actors()):
        show = actors.spawn_actor_from_class(show_class, unreal.Vector(0.0, 0.0, 0.0))
        if show is None:
            raise RuntimeError("Cannot create LightShowActor")
        show.set_actor_label("Light Show DDP Receiver")
    if not levels.save_current_level():
        raise RuntimeError("Cannot save LightShow map")

    # The initial repository project uses Engine/Maps/Entry until the real map exists.
    config = project / "Config" / "DefaultEngine.ini"
    contents = config.read_text(encoding="utf-8")
    contents = contents.replace("EditorStartupMap=/Engine/Maps/Entry", f"EditorStartupMap={map_path}")
    contents = contents.replace("GameDefaultMap=/Engine/Maps/Entry", f"GameDefaultMap={map_path}")
    config.write_text(contents, encoding="utf-8")
    unreal.log(f"ChristmasLights setup complete: {pixel_count} pixels, map {map_path}, layout {destination}")


if __name__ == "__main__":
    main()
