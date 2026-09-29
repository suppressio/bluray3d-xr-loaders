"""
loader_retrowave.py — the loading animation shown after a jump (--loader), built
from scratch in Blender, retrowave style: a neon grid floor running towards the
viewer, a holographic disc rising on the horizon like the sun and spinning, a
loading bar made of equalizer bars jumping as if to music, "LOADING".
Everything is procedural (no images, no external fonts): free of anyone else's
rights.

4 s at 24 fps, 1920x1080, a seamless loop: every motion is a whole number of
turns / cycles / grid cells per loop. Animation uses drivers on the frame
number, not keyframes (stable across Blender versions).

Preview in Blender: Scripting tab -> Open this file -> Run Script, then look
through the camera (Numpad 0) and play (Space).
Render the video (2D), or the side-by-side 3D version (3840x1080, full SBS,
for 3D movies: the grid and the disc go into the distance, the bar floats in front):
    blender -b -P loader_retrowave.py -- retrowave.mp4 --sbs      # the one shipped
    blender -b -P loader_retrowave.py -- retrowave-2d.mp4
"""
import contextlib
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy
import mathutils

FPS = 24
FRAMES = 96                       # 4 s loop
WIDTH, HEIGHT = 1920, 1080

SKY = (0.018, 0.004, 0.045)       # deep purple
GRID = (0.75, 0.18, 1.0)          # neon violet
CYAN = (0.1, 0.85, 1.0)
MAGENTA = (1.0, 0.15, 0.7)
TEXT = (0.95, 0.9, 1.0)

CELL = 1.0                        # grid cell size (m)
LOOP_CELLS = 4                    # the grid runs this many cells per loop

T = f"((frame - 1) / {FRAMES})"   # 0..1 over the loop, in driver expressions


def clear_scene() -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras,
                 bpy.data.lights):
        for block in list(coll):
            coll.remove(block)


def drive(obj: bpy.types.Object, path: str, index: int, expression: str) -> None:
    fcurve = obj.driver_add(path, index) if index >= 0 else obj.driver_add(path)
    fcurve.driver.type = "SCRIPTED"
    fcurve.driver.expression = expression


def emission(name: str, color: tuple[float, float, float],
             strength: float = 1.0) -> bpy.types.Material:
    """A flat glowing colour: the scene has no lights, everything glows by itself."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1.0)
    em.inputs["Strength"].default_value = strength
    links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def ramp_material(name: str, stops: list[tuple[float, tuple[float, float, float]]],
                  source: str, strength: float = 1.0, gradient: str = "LINEAR",
                  axis: str = "X") -> tuple[bpy.types.Material, bpy.types.Nodes,
                                          bpy.types.NodeLinks, bpy.types.Node]:
    """Emission coloured by a gradient over the object's coordinates."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    coords = nodes.new("ShaderNodeTexCoord")
    vector = coords.outputs[source]
    if gradient == "LINEAR":                       # 0..1 along one axis
        sep = nodes.new("ShaderNodeSeparateXYZ")
        links.new(vector, sep.inputs["Vector"])
        fac = sep.outputs[axis]
    else:
        grad = nodes.new("ShaderNodeTexGradient")
        grad.gradient_type = gradient
        links.new(vector, grad.inputs["Vector"])
        fac = grad.outputs["Fac"]
    ramp = nodes.new("ShaderNodeValToRGB")
    elements = ramp.color_ramp.elements
    while len(elements) < len(stops):
        elements.new(0.5)
    for element, (pos, rgb) in zip(elements, stops, strict=True):
        element.position = pos
        element.color = (*rgb, 1.0)
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    links.new(fac, ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], em.inputs["Color"])
    links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat, nodes, links, em


# --- the world ---------------------------------------------------------------

def world(scene: bpy.types.Scene) -> None:
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    bg = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (*SKY, 1.0)


def grid() -> None:
    """Neon lines on the floor, running towards the camera: LOOP_CELLS cells per
    loop, so the last frame joins the first. The lines fade with the distance
    from the camera (world position, so the fade does not move with the grid).
    A dark floor under it hides what is below the horizon."""
    size_x, size_y = 60, 80
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=int(size_x / CELL),
                                    y_subdivisions=int(size_y / CELL),
                                    size=1, location=(0, size_y / 2 - 12, 0))
    g = bpy.context.object
    g.name = "Grid"
    # the size goes into the mesh: an object scale would also scale the lines' width
    g.data.transform(mathutils.Matrix.Diagonal((size_x, size_y, 1, 1)))
    wire = g.modifiers.new("Wire", "WIREFRAME")
    wire.thickness = 0.03
    wire.use_replace = True
    mat = bpy.data.materials.new("Grid")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    geo = nodes.new("ShaderNodeNewGeometry")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geo.outputs["Position"], sep.inputs["Vector"])
    fade = nodes.new("ShaderNodeMapRange")          # near: 0, horizon: 1
    fade.inputs["From Min"].default_value = -6.0
    fade.inputs["From Max"].default_value = 60.0
    links.new(sep.outputs["Y"], fade.inputs["Value"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*GRID, 1.0)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (*SKY, 1.0)
    mid = ramp.color_ramp.elements.new(0.45)
    mid.color = (0.5, 0.1, 0.75, 1.0)
    links.new(fade.outputs["Result"], ramp.inputs["Fac"])
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.6
    links.new(ramp.outputs["Color"], em.inputs["Color"])
    links.new(em.outputs["Emission"], out.inputs["Surface"])
    g.data.materials.append(mat)
    drive(g, "location", 1, f"{size_y / 2 - 12} - {T} * {LOOP_CELLS * CELL}")

    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 30, -0.02))
    floor = bpy.context.object
    floor.name = "Floor"
    floor.data.transform(mathutils.Matrix.Diagonal((200, 200, 1, 1)))
    floor.data.materials.append(emission("Floor", (0.008, 0.002, 0.02)))


# --- the disc ----------------------------------------------------------------

def disc(location: tuple[float, float, float], radius: float, tilt: float = 90.0,
         bob: float = 0.0) -> None:
    """A holographic disc facing the camera (tilted back by 90 - `tilt` degrees),
    spinning (1 turn per loop) and floating up and down by `bob` (1 cycle per loop)."""
    pastel = [(0.0, (0.55, 0.95, 0.95)), (0.17, (0.95, 0.6, 0.9)), (0.33, (0.6, 0.7, 1.0)),
              (0.5, (0.6, 1.0, 0.8)), (0.67, (0.95, 0.65, 0.9)), (0.83, (0.55, 0.85, 1.0)),
              (1.0, (0.55, 0.95, 0.95))]
    # layers a little apart towards the viewer, in proportion to the size
    parts = [("Disc", radius, None, 0.0),
             ("Hub", radius * 0.34, (0.55, 0.55, 0.7), radius * 0.004),
             ("HubRing", radius * 0.25, (0.25, 0.22, 0.4), radius * 0.006),
             ("Hole", radius * 0.13, SKY, radius * 0.008)]
    bpy.ops.object.empty_add(location=location)
    holder = bpy.context.object
    holder.name = "DiscHolder"
    holder.rotation_mode = "ZYX"            # local spin first, then the tilt
    holder.rotation_euler = (math.radians(tilt), 0, 0)
    drive(holder, "rotation_euler", 2, f"{T} * 2 * pi")
    if bob:
        drive(holder, "location", 2, f"{location[2]} + {bob} * sin({T} * 2 * pi)")
    for name, r, color, z in parts:
        bpy.ops.mesh.primitive_circle_add(vertices=192, radius=r, fill_type="NGON",
                                          location=(0, 0, z))
        obj = bpy.context.object
        obj.name = name
        if color is None:
            mat, *_ = ramp_material("Disc", pastel, "Object", 0.8, gradient="RADIAL")
        else:
            mat = emission(name, color)
        obj.data.materials.append(mat)
        obj.parent = holder
    bpy.ops.curve.primitive_bezier_circle_add(radius=radius, location=(0, 0, radius * 0.01))
    rim = bpy.context.object
    rim.name = "Rim"
    rim.data.bevel_depth = radius * 0.012
    rim.data.materials.append(emission("Rim", (0.8, 0.85, 1.0), 1.0))
    rim.parent = holder


# --- the loading bar -----------------------------------------------------------

def equalizer(center: tuple[float, float, float], bars: int, width: float) -> None:
    """Bars jumping as if to music: each height is a mix of two waves with a
    whole number of cycles per loop, so the loop has no seam."""
    gap = width / bars
    bar_w = gap * 0.62
    for i in range(bars):
        x = center[0] - width / 2 + gap * (i + 0.5)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, center[1], center[2]))
        bar = bpy.context.object
        bar.name = f"Bar{i:02d}"
        # origin at the bottom, so the bar grows upwards
        bar.data.transform(mathutils.Matrix.Translation((0, 0, 0.5)))
        bar.scale = (bar_w, 0.06, 0.1)
        f1, f2 = 4 + (i * 7) % 5, 6 + (i * 5) % 7            # cycles per loop
        p1, p2 = i * 1.3, i * 2.1
        drive(bar, "scale", 2,
              f"0.06 + 0.5 * (0.5 + 0.5 * sin({T} * 2 * pi * {f1} + {p1}))"
              f" * (0.55 + 0.45 * sin({T} * 2 * pi * {f2} + {p2}))")
        t = i / (bars - 1)
        color = tuple(c * (1 - t) + m * t for c, m in zip(CYAN, MAGENTA, strict=True))
        bar.data.materials.append(emission(f"Bar{i:02d}", color, 1.0))

    # the frame of the loading bar
    bpy.ops.mesh.primitive_plane_add(size=1, location=(center[0], center[1] + 0.02,
                                                      center[2] + 0.3))
    frame = bpy.context.object
    frame.name = "BarFrame"
    frame.rotation_euler = (math.pi / 2, 0, 0)
    frame.scale = (width + 0.25, 0.75, 1)
    wire = frame.modifiers.new("Wire", "WIREFRAME")
    wire.thickness = 0.025
    wire.use_replace = True
    frame.data.materials.append(emission("BarFrame", (0.8, 0.7, 1.0), 1.5))


def label(text: str, location: tuple[float, float, float], size: float) -> None:
    bpy.ops.object.text_add(location=location, rotation=(math.pi / 2, 0, 0))
    obj = bpy.context.object
    obj.name = "Loading"
    obj.data.body = text
    obj.data.size = size
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.space_character = 1.4
    obj.data.materials.append(emission("Text", TEXT, 1.5))


def build() -> None:
    clear_scene()
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, FRAMES
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    with contextlib.suppress(TypeError):
        scene.view_settings.view_transform = "Standard"     # colours as written
    world(scene)

    bpy.ops.object.camera_add(location=(0, -9.5, 2.3),
                              rotation=(math.radians(84), 0, 0))
    cam = bpy.context.object
    cam.data.lens = 32
    scene.camera = cam

    grid()
    # the disc is the sun of the scene: big, far away, cut by the horizon
    disc((0, 70, 4.5), 12.0)
    equalizer((0, -0.6, 0.72), 18, 2.6)
    label("LOADING", (0, -0.6, 0.35), 0.26)
    scene.frame_set(1)


def stereo(scene: bpy.types.Scene) -> None:
    """Two cameras a little apart, rendered side by side at full width. The
    screen plane (convergence) is just behind the loading bar: the bar floats in
    front of the screen, grid and disc go into the distance."""
    scene.render.use_multiview = True
    scene.render.views_format = "STEREO_3D"
    cam = scene.camera.data
    cam.stereo.convergence_mode = "OFFAXIS"
    cam.stereo.interocular_distance = 0.12      # a wide base: the scene is small
    cam.stereo.convergence_distance = 11.0      # the bar is 9 m from the camera
    settings = scene.render.image_settings
    settings.views_format = "STEREO_3D"
    settings.stereo_3d_format.display_mode = "SIDEBYSIDE"
    settings.stereo_3d_format.use_sidebyside_crosseyed = False
    settings.stereo_3d_format.use_squeezed_frame = False   # full SBS: 3840x1080


def render(output: Path, sbs: bool = False) -> None:
    scene = bpy.context.scene
    frames = Path(tempfile.mkdtemp(prefix="loader-"))
    scene.render.image_settings.file_format = "PNG"
    if sbs:
        stereo(scene)
    scene.render.filepath = str(frames / "f_####")
    bpy.ops.render.render(animation=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS),
                    "-i", str(frames / "f_%04d.png"), "-c:v", "libx264", "-preset", "veryslow",
                    # flat colours compress well: ~1 MB (the program re-encodes it anyway)
                    "-crf", "26", "-pix_fmt", "yuv420p", str(output)], check=True)
    shutil.rmtree(frames)
    sys.stdout.write(f"loader written: {output}\n")


build()
if bpy.app.background:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    paths = [a for a in args if not a.startswith("--")]
    render(Path(paths[0] if paths else "loader-retrowave.mp4").resolve(), sbs="--sbs" in args)
