"""
loader_simple.py — the loading animation shown after a jump (--loader), built
from scratch in Blender: a disc seen from above spinning slowly, a loading arc
spinning around it, "LOADING" with dots appearing one by one. Everything is
procedural (no images, no external fonts): free of anyone else's rights.

2 s at 24 fps, 1920x1080, a seamless loop: frame 49 would be frame 1 again.
Animation uses drivers on the frame number, not keyframes (stable across
Blender versions).

Preview in Blender: Scripting tab -> Open this file -> Run Script, then look
through the camera (Numpad 0) and play (Space).
Render the video:
    blender -b -P loader_simple.py -- simple.mp4
"""
import contextlib
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy

FPS = 24
FRAMES = 48                       # 2 s loop
WIDTH, HEIGHT = 1920, 1080

BACKGROUND = (0.004, 0.006, 0.012)
ACCENT = (0.12, 0.72, 1.0)        # cyan of the arc and the rim
TEXT = (0.85, 0.9, 1.0)


def clear_scene() -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras):
        for block in list(coll):
            coll.remove(block)


def emission(name: str, color: tuple[float, float, float],
             strength: float = 1.0) -> bpy.types.Material:
    """A flat, unlit colour: the scene has no lights, everything glows by itself."""
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


def disc_material() -> bpy.types.Material:
    """Dark disc with a faint rainbow that follows the angle: turning with the
    disc, it shows the spin (like light on a real disc)."""
    mat = bpy.data.materials.new("Disc")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    coords = nodes.new("ShaderNodeTexCoord")
    grad = nodes.new("ShaderNodeTexGradient")
    grad.gradient_type = "RADIAL"
    ramp = nodes.new("ShaderNodeValToRGB")
    stops = [(0.0, (0.05, 0.07, 0.12)), (0.12, (0.35, 0.15, 0.6)), (0.22, (0.1, 0.5, 0.9)),
             (0.32, (0.1, 0.8, 0.6)), (0.42, (0.05, 0.07, 0.12)), (0.62, (0.05, 0.07, 0.12)),
             (0.72, (0.8, 0.5, 0.2)), (0.82, (0.6, 0.2, 0.7)), (0.92, (0.05, 0.07, 0.12)),
             (1.0, (0.05, 0.07, 0.12))]
    elements = ramp.color_ramp.elements
    while len(elements) < len(stops):
        elements.new(0.5)
    for element, (pos, rgb) in zip(elements, stops, strict=True):
        element.position = pos
        element.color = (*rgb, 1.0)
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 0.55
    links.new(coords.outputs["Object"], grad.inputs["Vector"])
    links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], em.inputs["Color"])
    links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def spin(obj: bpy.types.Object, turns: int) -> None:
    """Rotation about Z driven by the frame: `turns` full turns every FRAMES
    frames (negative: clockwise), so the loop has no seam."""
    fcurve = obj.driver_add("rotation_euler", 2)
    fcurve.driver.type = "SCRIPTED"
    fcurve.driver.expression = f"(frame - 1) / {FRAMES} * {turns} * 2 * pi"


def ring(y: float, radius: float, thickness: float, color: tuple[float, float, float],
         strength: float, name: str, z: float) -> bpy.types.Object:
    """A circle drawn as a tube."""
    bpy.ops.curve.primitive_bezier_circle_add(radius=radius, location=(0, y, z))
    obj = bpy.context.object
    obj.name = name
    obj.data.bevel_depth = thickness
    obj.data.bevel_resolution = 4
    obj.data.resolution_u = 64
    obj.data.materials.append(emission(name, color, strength))
    return obj


def arc(y: float, radius: float, thickness: float, portion: float,
        z: float) -> bpy.types.Object:
    """`portion` of a circle as a tube with round ends, from 12 o'clock clockwise.
    An open curve: trimming a closed circle (bevel factor) has no effect in Blender 5."""
    curve = bpy.data.curves.new("Arc", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = thickness
    curve.bevel_resolution = 4
    curve.use_fill_caps = True
    spline = curve.splines.new("POLY")
    n = 64
    spline.points.add(n - 1)
    for i, p in enumerate(spline.points):
        a = math.pi / 2 - i / (n - 1) * portion * 2 * math.pi
        p.co = (radius * math.cos(a), radius * math.sin(a), 0, 1)
    curve.materials.append(emission("Arc", ACCENT, 1.4))
    obj = bpy.data.objects.new("Arc", curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = (0, y, z)
    return obj


def disc(y: float, radius: float) -> None:
    bpy.ops.mesh.primitive_circle_add(vertices=256, radius=radius, fill_type="NGON",
                                      location=(0, y, 0))
    body = bpy.context.object
    body.name = "Disc"
    body.data.materials.append(disc_material())
    spin(body, 1)
    # the clamping area and the hole in the middle, which do not show the spin
    for name, r, color, z in (("Hub", radius * 0.32, (0.09, 0.11, 0.16), 0.01),
                              ("Hole", radius * 0.11, BACKGROUND, 0.02)):
        bpy.ops.mesh.primitive_circle_add(vertices=128, radius=r, fill_type="NGON",
                                          location=(0, y, z))
        part = bpy.context.object
        part.name = name
        part.data.materials.append(emission(name, color))
    ring(y, radius, 0.012, ACCENT, 0.9, "Rim", 0.03)


def label(text: str, x: float, y: float, size: float,
          align: str = "CENTER") -> bpy.types.Object:
    bpy.ops.object.text_add(location=(x, y, 0))
    obj = bpy.context.object
    obj.data.body = text
    obj.data.size = size
    obj.data.align_x = align
    obj.data.align_y = "CENTER"
    obj.data.space_character = 1.25
    obj.data.materials.append(emission("Text", TEXT))
    return obj


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
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.color = BACKGROUND
    scene.world.use_nodes = True
    bg = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (*BACKGROUND, 1.0)

    bpy.ops.object.camera_add(location=(0, 0, 10), rotation=(0, 0, 0))
    cam = bpy.context.object
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 9.0
    scene.camera = cam

    disc_y, radius = 0.35, 1.45
    disc(disc_y, radius)
    spinner = arc(disc_y, radius + 0.28, 0.035, 0.28, 0.04)
    spin(spinner, -2)
    # a fainter track under the arc
    ring(disc_y, radius + 0.28, 0.012, (0.08, 0.16, 0.24), 1.0, "Track", 0.035)

    word = label("LOADING", 0, -1.85, 0.42)
    bpy.context.view_layer.update()
    x = word.dimensions.x / 2 + 0.08
    for k in (1, 2, 3):                       # one more dot every 16 frames
        dot = label(".", x + (k - 1) * 0.17, -1.85, 0.42, align="LEFT")
        dot.name = f"Dot{k}"
        for prop in ("hide_render", "hide_viewport"):
            fcurve = dot.driver_add(prop)
            fcurve.driver.type = "SCRIPTED"
            fcurve.driver.expression = f"floor((frame - 1) / 16) + 1 < {k}"
    scene.frame_set(1)


def render(output: Path) -> None:
    scene = bpy.context.scene
    frames = Path(tempfile.mkdtemp(prefix="loader-"))
    scene.render.image_settings.file_format = "PNG"
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
    render(Path(args[0] if args else "loader-simple.mp4").resolve())
