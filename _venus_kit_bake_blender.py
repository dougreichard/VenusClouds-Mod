"""Headless Blender: assemble kitbash parts and BAKE one Cosmos texture set.

    blender --background --python _venus_kit_bake_blender.py -- <job.json> <out.obj> <budget> <texsize>

WHY BAKE AT ALL. Cosmos allows exactly ONE texture set per ship. While every part came from
a single Synty pack that was free - all parts already index the same atlas - but it also
locked each hull to one pack, which is a heavy price to pay in silhouette for a saving in
pipeline. Baking removes the constraint: parts can come from anywhere, and the ship still
ships four maps named `<root>_{diffuse,emissive,specular,normal}.png`.

WHAT IS HONESTLY BAKED, because the packs do not ship four maps each:

    diffuse   REAL. Baked from each part's own colour atlas through Cycles.
    emissive  REAL where the pack has one (Pirates and Sci-Fi do, Construction does not).
    normal    REAL, and the reason this is worth doing: baked from the PRE-DECIMATION
              assembly onto the decimated mesh, so the detail the budget throws away comes
              back as surface normal. Not invented - measured off the high-poly.
    specular  DERIVED from the baked diffuse. No pack ships a specular map, so there is no
              authored source to bake; this is an honest approximation, not real data.

ORDER MATTERS. The high-poly copy is taken BEFORE decimation - that is the whole point -
and the UV atlas is made AFTER the join, because a bake target needs one UV layout.
"""
import json
import math
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
JOB, OUT = argv[0], argv[1]
BUDGET = int(argv[2]) if len(argv) > 2 else 0
TEX = int(argv[3]) if len(argv) > 3 else 1024

with open(JOB, encoding="utf-8") as f:
    job = json.load(f)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# The UV layer the SOURCE atlases are addressed through, and the separate one the
# bake writes into. Two layers, never one.
SRC_UV = "UVMap"
BAKE_UV = "kit_bake"


def _log(msg):
    print("KIT: " + msg)


# ---------------------------------------------------------------- import ----
_materials = {}


def _material_for(diffuse, emissive):
    """One material per (diffuse, emissive) pair, so parts from a pack share a material."""
    key = (diffuse or "", emissive or "")
    if key in _materials:
        return _materials[key]
    mat = bpy.data.materials.new("kit_%d" % len(_materials))
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]

    # BIND THE SOURCE TEXTURES TO THE ORIGINAL UV LAYER, EXPLICITLY.
    #
    # An unbound image node samples through whatever UV layer is ACTIVE. The bake needs a
    # fresh unwrap, and `smart_project` writes into the active layer - so without this node
    # the source atlas gets sampled with the BAKE layout and the ship comes out a patchwork
    # of unrelated colours. That is exactly what happened on the first attempt.
    uvnode = nt.nodes.new("ShaderNodeUVMap")
    uvnode.uv_map = SRC_UV

    if diffuse and os.path.exists(diffuse):
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(diffuse)
        tex.interpolation = "Closest"      # Synty atlases are flat blocks; no blur
        nt.links.new(tex.inputs["Vector"], uvnode.outputs["UV"])
        nt.links.new(bsdf.inputs["Base Color"], tex.outputs["Color"])
    if emissive and os.path.exists(emissive):
        et = nt.nodes.new("ShaderNodeTexImage")
        et.image = bpy.data.images.load(emissive)
        et.interpolation = "Closest"
        et.image.colorspace_settings.name = "sRGB"
        nt.links.new(et.inputs["Vector"], uvnode.outputs["UV"])
        nt.links.new(bsdf.inputs["Emission Color"], et.outputs["Color"])
        bsdf.inputs["Emission Strength"].default_value = 1.0
    else:
        bsdf.inputs["Emission Strength"].default_value = 0.0
    _materials[key] = mat
    return mat


placed = 0
for part in job["parts"]:
    path = part["path"]
    before = set(scene.objects)
    try:
        # Newer Synty packs ship FBX with no OBJ folder at all (Kaiju is 93 fbx / 0 obj),
        # and those are the packs with the organic, spined parts the Brood needs.
        if path.lower().endswith(".fbx"):
            bpy.ops.import_scene.fbx(filepath=path)
        else:
            bpy.ops.wm.obj_import(filepath=path)
    except Exception as e:                       # noqa: BLE001
        _log("FAILED to import %s: %s" % (path, e))
        continue
    new = [o for o in scene.objects if o not in before]
    if not new:
        _log("imported nothing from %s" % path)
        continue

    off = part.get("offset", [0, 0, 0])
    rot = part.get("rot", [0, 0, 0])
    scl = part.get("scale", [1, 1, 1])
    mat = _material_for(part.get("diffuse"), part.get("emissive"))
    for o in new:
        o.scale = tuple(o.scale[i] * scl[i] for i in range(3))
        o.rotation_euler = tuple(o.rotation_euler[i] + math.radians(rot[i]) for i in range(3))
        # The importer maps the file's Y-up into Blender's Z-up, so a recipe offset written
        # in COSMOS axes (x, y=up, z=long) is mapped the same way.
        o.location = (o.location[0] + off[0], o.location[1] + off[2], o.location[2] + off[1])
        o.data.materials.clear()
        o.data.materials.append(mat)
        o.name = os.path.splitext(os.path.basename(path))[0]
    placed += 1

meshes = [o for o in scene.objects if o.type == "MESH"]
if not meshes:
    _log("nothing to build")
    sys.exit(1)
_log("placed %d/%d parts" % (placed, len(job["parts"])))


def _faces():
    return sum(len(o.data.polygons) for o in scene.objects if o.type == "MESH")


# ------------------------------------------------------------ high-poly ----
# Snapshot BEFORE decimation - this is what the normal map is baked from, and taking it
# afterwards would bake the low-poly against itself and produce a flat, useless map.
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.duplicate()
high = [o for o in bpy.context.selected_objects]
for o in high:
    o.name = "HIGH_" + o.name
bpy.ops.object.select_all(action="DESELECT")
for o in high:
    o.select_set(True)
bpy.context.view_layer.objects.active = high[0]
bpy.ops.object.join()
high_obj = bpy.context.view_layer.objects.active
high_obj.name = "KIT_HIGH"
if high_obj.data.uv_layers:
    high_obj.data.uv_layers[0].name = SRC_UV
high_obj.hide_render = False
_log("high-poly reference: %d tris" % len(high_obj.data.polygons))

work = [o for o in scene.objects if o.type == "MESH" and o is not high_obj]

# ----------------------------------------------------- triangulate/budget ----
for o in work:
    bpy.context.view_layer.objects.active = o
    m = o.modifiers.new("kit_tri", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=m.name)

before = sum(len(o.data.polygons) for o in work)
if BUDGET and before > BUDGET:
    # Spend the cut where the triangles are: anything already cheap keeps full resolution,
    # because the cheap parts usually carry the read (the envelope's rib bands are 1,046
    # tris and a uniform ratio flattened them while the hull had detail to spare).
    PROTECT = 1200
    small = [o for o in work if len(o.data.polygons) <= PROTECT]
    big = [o for o in work if len(o.data.polygons) > PROTECT]
    kept = sum(len(o.data.polygons) for o in small)
    big_tris = sum(len(o.data.polygons) for o in big)
    if big and big_tris and (BUDGET - kept) > 0:
        ratio = max(0.05, float(BUDGET - kept) / float(big_tris))
        targets = big
    else:
        ratio = max(0.05, float(BUDGET) / float(before))
        targets = work
    for o in targets:
        bpy.context.view_layer.objects.active = o
        m = o.modifiers.new("kit_dec", "DECIMATE")
        m.ratio = ratio
        bpy.ops.object.modifier_apply(modifier=m.name)
    _log("decimated %d -> %d tris (ratio %.3f)"
         % (before, sum(len(o.data.polygons) for o in work), ratio))

# ------------------------------------------------------------- join + UV ----
# A bake target needs ONE UV layout, so the working copy becomes one object here. The
# recipe stays the source of truth for what the ship is made of.
bpy.ops.object.select_all(action="DESELECT")
for o in work:
    o.select_set(True)
bpy.context.view_layer.objects.active = work[0]
if len(work) > 1:
    bpy.ops.object.join()
low = bpy.context.view_layer.objects.active
low.name = "KIT_LOW"

bpy.ops.object.select_all(action="DESELECT")
low.select_set(True)
bpy.context.view_layer.objects.active = low
# Rename whatever the importer produced to the expected source name, then ADD the bake
# layer beside it and make that active. smart_project only touches the active layer.
if low.data.uv_layers:
    low.data.uv_layers[0].name = SRC_UV
bake_uv = low.data.uv_layers.get(BAKE_UV) or low.data.uv_layers.new(name=BAKE_UV)
low.data.uv_layers.active = bake_uv

bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.006)
bpy.ops.object.mode_set(mode="OBJECT")
_log("unwrapped %d tris into '%s' (source '%s' preserved)"
     % (len(low.data.polygons), BAKE_UV, SRC_UV))

# ---------------------------------------------------------------- bake ------
scene.render.engine = "CYCLES"
try:
    scene.cycles.device = "CPU"
    scene.cycles.samples = 4          # flat colour needs almost nothing
    scene.cycles.use_denoising = False
except Exception:                     # noqa: BLE001
    pass
scene.render.bake.use_selected_to_active = False
scene.render.bake.margin = 8

bake_mat = bpy.data.materials.new("kit_baked")
bake_mat.use_nodes = True
bake_nt = bake_mat.node_tree
bake_bsdf = bake_nt.nodes["Principled BSDF"]

images = {}


def _new_image(name, color, non_color=False):
    img = bpy.data.images.new(name, TEX, TEX, alpha=False)
    img.generated_color = color
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    images[name] = img
    return img


def _bake_to(img, bake_type, source_objs=None, **kw):
    """Point every material at `img` as the active bake target, then bake."""
    targets = []
    for o in (source_objs or [low]):
        for slot in o.material_slots:
            m = slot.material
            if not m or not m.use_nodes:
                continue
            node = m.node_tree.nodes.new("ShaderNodeTexImage")
            node.image = img
            m.node_tree.nodes.active = node
            node.select = True
            targets.append((m, node))
    bpy.ops.object.select_all(action="DESELECT")
    for o in (source_objs or [low]):
        o.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.bake(type=bake_type, **kw)
    for m, node in targets:
        m.node_tree.nodes.remove(node)


# --- diffuse: colour only, no lighting ---------------------------------------
diffuse_img = _new_image("kit_diffuse", (0.5, 0.5, 0.5, 1.0))
_bake_to(diffuse_img, "DIFFUSE", pass_filter={"COLOR"})
_log("baked diffuse")

# --- emissive ----------------------------------------------------------------
emissive_img = _new_image("kit_emissive", (0.0, 0.0, 0.0, 1.0))
_bake_to(emissive_img, "EMIT")
_log("baked emissive")

# --- normal, from the HIGH-poly onto the decimated mesh ----------------------
normal_img = _new_image("kit_normal", (0.5, 0.5, 1.0, 1.0), non_color=True)
try:
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.cage_extrusion = 0.35
    bpy.ops.object.select_all(action="DESELECT")
    high_obj.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    node = None
    for slot in low.material_slots:
        m = slot.material
        node = m.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = normal_img
        m.node_tree.nodes.active = node
        node.select = True
    bpy.ops.object.bake(type="NORMAL")
    _log("baked normal from high-poly (%d -> %d tris)"
         % (len(high_obj.data.polygons), len(low.data.polygons)))
except Exception as e:                            # noqa: BLE001
    _log("normal bake failed (%s) - shipping flat" % e)
finally:
    scene.render.bake.use_selected_to_active = False

# ------------------------------------------------------------------ save ----
out_dir = os.path.dirname(OUT) or "."
os.makedirs(out_dir, exist_ok=True)
root = os.path.splitext(os.path.basename(OUT))[0]
for name, suffix in (("kit_diffuse", "_diffuse"), ("kit_emissive", "_emissive"),
                     ("kit_normal", "_normal")):
    img = images[name]
    img.filepath_raw = os.path.join(out_dir, root + suffix + ".png")
    img.file_format = "PNG"
    img.save()
_log("wrote maps at %dpx" % TEX)

# The baked mesh is what ships; the high-poly is scaffolding.
bpy.data.objects.remove(high_obj, do_unlink=True)
bpy.ops.object.select_all(action="DESELECT")
low.select_set(True)
# Ship the BAKE layout - it is what the baked maps are addressed in. Removing the source
# layer guarantees the exporter cannot pick the wrong one.
if low.data.uv_layers.get(SRC_UV) and len(low.data.uv_layers) > 1:
    low.data.uv_layers.remove(low.data.uv_layers[SRC_UV])
bpy.ops.wm.obj_export(filepath=OUT, export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, export_normals=True, export_uv=True)
_log("wrote %s (%d tris)" % (OUT, len(low.data.polygons)))
