"""Build a Cosmos ship art set from PROCEDURAL geometry - no kitbash, no source packs.

    blender --background --python _venus_scratch_ship.py -- <out.obj> [texsize]

Everything here is authored in bmesh: a lofted boat hull, a lifting envelope, masts and
sails, tail fins. Nothing is imported. The point is to show the pipeline does not depend on
Synty parts - the ONE-TEXTURE-SET constraint is satisfied by unwrapping the finished mesh
and baking its flat material colours into a single atlas, exactly the way the kitbash bake
does it, so the output drops into media/ships next to the kitbashed hulls.

The subject is a KDM sky-skiff: a hull slung under a gasbag, with sails. That shape is what
the Venus setting asks for and is precisely what the kitbashed pirate hulls do not deliver -
they are scifi-pack fighters with capital-ship armour plating used as pontoons.

WHY THE NORMAL MAP IS FLAT. The kitbash bake gets a real normal map by baking a high-poly
reference onto the decimated mesh. Procedural geometry has no high-poly twin, so a flat
(128,128,255) normal is the honest answer rather than inventing surface detail. Specular IS
derived, from the baked diffuse's luminance, same reasoning as _venus_kit_bake.py.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
TEX = int(argv[1]) if len(argv) > 1 else 1024
# NOT 7,800. That figure is the STOCK art's range (1,790-7,784 across the 201 shipped .obj)
# and the kitbash bake's self-imposed cap - it is not an engine limit. Measured across the
# 46 meshes in Cosmos-TNG-Mod, which load in engine: max 145,856 tris (FED_Ambassador),
# median 14,092, several in the 34-61k band, and up to 31 separate objects in one model.
# So aim at the TNG median or above; the engine has an order of magnitude more headroom
# than the stock hulls suggest.
TARGET_TRIS = int(argv[2]) if len(argv) > 2 else 40000


def _log(msg):
    print("SCRATCH: %s" % msg)


# --------------------------------------------------------------------- setup ---
bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
scene = bpy.context.scene


def _mat(name, rgb, rough=0.85, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    return m


# Palette chosen to sit beside the existing fleet: weathered dark timber, bone canvas,
# and one saturated accent, rather than the scifi pack's oxblood-and-charcoal.
MATERIALS = [
    _mat("hull",     (0.115, 0.082, 0.062)),          # 0 tarred timber
    _mat("deck",     (0.330, 0.235, 0.140)),          # 1 planking
    _mat("envelope", (0.720, 0.690, 0.600)),          # 2 canvas gasbag
    _mat("sail",     (0.420, 0.105, 0.095)),          # 3 crimson canvas
    _mat("metal",    (0.240, 0.250, 0.265), 0.45, 0.9),  # 4 iron fittings
    _mat("trim",     (0.520, 0.400, 0.150), 0.55, 0.6),  # 5 brass trim
]
HULL, DECK, ENVELOPE, SAIL, METAL, TRIM = range(6)

bm = bmesh.new()


def _prim(op, mat_index, matrix=None, **kw):
    """Create a bmesh primitive, move it into place, and tag its faces' material.

    Take the new geometry from the OPERATOR'S RETURN VALUE, never from a positional slice
    like `list(bm.verts)[v0:]`. The sequence is not a stable append-only log once bmesh.ops
    has run a few times, so a slice silently grabs the wrong vertices and the matrix gets
    applied to unrelated geometry - which smeared two of the envelope hoops into 8-unit
    shells sprawled across the ship. The symptom was a tan wedge that looked like a texture
    bug from one camera; only a per-shell bounding-box audit named it.
    """
    res = op(bm, **kw)
    new_verts = list(res.get("verts", []))
    if matrix is not None and new_verts:
        bmesh.ops.transform(bm, matrix=matrix, verts=new_verts)
    vset = set(new_verts)
    new_faces = list(dict.fromkeys(
        f for v in new_verts for f in v.link_faces if vset.issuperset(f.verts)))
    for f in new_faces:
        f.material_index = mat_index
    # Recalculate per primitive, while this shell is still an isolated body. One blanket
    # recalc at the end works on a soup of closed shells and open ones (sails, bulwark
    # strips, uncapped hoops) and can flip whole bodies inside out.
    bmesh.ops.recalc_face_normals(bm, faces=new_faces)


def _box(mat_index, center, size, rot_y=0.0, rot_z=0.0):
    m = Matrix.Translation(Vector(center))
    if rot_z:
        m = m @ Matrix.Rotation(rot_z, 4, "Z")
    if rot_y:
        m = m @ Matrix.Rotation(rot_y, 4, "Y")
    m = m @ Matrix.Diagonal(Vector(size).to_4d())
    _prim(bmesh.ops.create_cube, mat_index, matrix=m, size=1.0)


def _tube(mat_index, center, radius, height, segments=8, rot_y=0.0):
    m = Matrix.Translation(Vector(center))
    if rot_y:
        m = m @ Matrix.Rotation(rot_y, 4, "Y")
    _prim(bmesh.ops.create_cone, mat_index, matrix=m,
          cap_ends=True, cap_tris=False, segments=segments,
          radius1=radius, radius2=radius, depth=height)


# ---------------------------------------------------------------------- hull ---
# Lofted from cross-sections. Each station is a half-width and a depth; the profile below
# runs from the starboard deck edge, around the keel, to the port deck edge, leaving the
# deck itself open so it can be floored and railed separately.
STATIONS = [
    (-6.30, 0.06, 0.28),
    (-5.20, 0.40, 0.60),
    (-3.60, 0.76, 0.92),
    (-1.60, 1.00, 1.10),
    (0.70, 1.08, 1.12),
    (2.70, 0.98, 1.00),
    (4.30, 0.80, 0.80),
    (5.45, 0.55, 0.52),
]
PROFILE = [
    (1.00, 0.00), (0.98, -0.30), (0.82, -0.62), (0.52, -0.88),
    (0.00, -1.00),
    (-0.52, -0.88), (-0.82, -0.62), (-0.98, -0.30), (-1.00, 0.00),
]

rings = []
for x, hw, depth in STATIONS:
    rings.append([bm.verts.new((x, yf * hw, zf * depth)) for yf, zf in PROFILE])
bm.verts.ensure_lookup_table()

hull_faces = []
for a, b in zip(rings, rings[1:]):
    for i in range(len(PROFILE) - 1):
        hull_faces.append(bm.faces.new((a[i], a[i + 1], b[i + 1], b[i])))
    # Deck line: close the open top between the two sheer edges.
    hull_faces.append(bm.faces.new((a[-1], a[0], b[0], b[-1])))
hull_faces.append(bm.faces.new(list(reversed(rings[0]))))   # bow cap
hull_faces.append(bm.faces.new(rings[-1]))                  # transom
for f in hull_faces:
    f.material_index = HULL
# Recalc NOW, while these faces still exist. The bevel later deletes and rebuilds them, so
# holding the references until finalize raises "BMFace has been removed".
bmesh.ops.recalc_face_normals(bm, faces=hull_faces)

# Deck floor, inset slightly so the bulwark reads as a wall standing on it.
deck_rings = []
for x, hw, _d in STATIONS[1:-1]:
    inner = hw * 0.88
    deck_rings.append((bm.verts.new((x, inner, -0.10)), bm.verts.new((x, -inner, -0.10))))
for (sa, pa), (sb, pb) in zip(deck_rings, deck_rings[1:]):
    f = bm.faces.new((sa, pa, pb, sb))
    f.material_index = DECK

# Bulwark: a low wall following the sheer on both sides.
for side in (1, -1):
    prev = None
    for x, hw, _d in STATIONS[1:-1]:
        lo = bm.verts.new((x, side * hw, 0.0))
        hi = bm.verts.new((x, side * hw * 0.97, 0.30))
        if prev is not None:
            f = bm.faces.new((prev[0], lo, hi, prev[1]) if side > 0
                             else (prev[1], hi, lo, prev[0]))
            f.material_index = HULL
        prev = (lo, hi)

_log("hull lofted from %d stations" % len(STATIONS))

# ------------------------------------------------------------------ envelope ---
# The gasbag. This is what makes it read as an AIRSHIP at silhouette distance, which is the
# single thing the kitbashed hulls are missing.
# These numbers are load-bearing and were got WRONG on the first pass: an envelope whose
# underside sat at z=1.85 swallowed masts that rose to 3.05, so the whole rig was buried
# inside the gasbag. It looked fine as arithmetic. Keep ENV_FLOOR above every mast top.
ENV_CENTER = Vector((-0.20, 0.0, 4.55))
ENV_R = Vector((4.70, 1.42, 1.32))
ENV_FLOOR = ENV_CENTER.z - ENV_R.z            # 3.23
ENV_STERN = ENV_CENTER.x + ENV_R.x            # 4.50
MAST_TOP_MAX = ENV_FLOOR - 0.35

_prim(bmesh.ops.create_uvsphere, ENVELOPE,
      matrix=Matrix.Translation(ENV_CENTER) @ Matrix.Diagonal(ENV_R.to_4d()),
      u_segments=64, v_segments=32, radius=1.0)

# Envelope ribbing - three hoops, so the canvas reads as panelled rather than as a balloon.
# Each hoop is scaled to the ellipsoid's cross-section at its own station, otherwise the
# ribs stand proud at the waist and sink into the skin toward the ends.
for x in (-2.90, -0.20, 2.50):
    t = (x - ENV_CENTER.x) / ENV_R.x
    shrink = math.sqrt(max(0.0, 1.0 - t * t)) * 1.05
    ry, rz = ENV_R.y * shrink, ENV_R.z * shrink
    # create_cone runs along local Z; rotating 90 deg about Y maps local Z to world X,
    # local Y to world Y and local X to world -Z - hence the (rz, ry, 1) scale order.
    _prim(bmesh.ops.create_cone, TRIM,
          matrix=Matrix.Translation(Vector((x, 0.0, ENV_CENTER.z)))
          @ Matrix.Rotation(math.radians(90), 4, "Y")
          @ Matrix.Diagonal(Vector((rz, ry, 1.0)).to_4d()),
          cap_ends=False, cap_tris=False, segments=36,
          radius1=1.0, radius2=1.0, depth=0.16)

# Tail fins, overlapping the envelope's stern so they read as attached rather than floating.
_box(SAIL, (ENV_STERN - 0.35, 0.0, ENV_CENTER.z + 1.25), (1.55, 0.10, 1.45))
_box(SAIL, (ENV_STERN - 0.35, 1.05, ENV_CENTER.z), (1.55, 1.55, 0.10))
_box(SAIL, (ENV_STERN - 0.35, -1.05, ENV_CENTER.z), (1.55, 1.55, 0.10))

# Struts slinging the hull under the envelope - they must SPAN deck to envelope floor.
_strut_h = ENV_FLOOR - 0.30
for sx in (-2.30, 2.10):
    for sy in (0.78, -0.78):
        _box(METAL, (sx, sy, 0.30 + _strut_h / 2.0), (0.14, 0.14, _strut_h))

_log("envelope, fins and struts placed")

# --------------------------------------------------------------- masts + sails ---
def _sail(x, half_w, bottom, top, belly):
    """A square sail bellied out to leeward, built as a bent grid."""
    cols, rows = 15, 10
    grid = []
    for c in range(cols):
        u = c / (cols - 1.0)
        column = []
        for r in range(rows):
            v = r / (rows - 1.0)
            # Belly peaks mid-sail and falls off toward the spars holding it.
            bulge = math.sin(u * math.pi) * math.sin(v * math.pi) * belly
            column.append(bm.verts.new((
                x + bulge,
                (u - 0.5) * 2.0 * half_w,
                bottom + v * (top - bottom),
            )))
        grid.append(column)
    for c in range(cols - 1):
        for r in range(rows - 1):
            f = bm.faces.new((grid[c][r], grid[c + 1][r],
                              grid[c + 1][r + 1], grid[c][r + 1]))
            f.material_index = SAIL


for mast_x, half_w, top in ((-2.60, 1.05, min(2.55, MAST_TOP_MAX)),
                            (1.70, 1.25, min(2.85, MAST_TOP_MAX))):
    _tube(METAL, (mast_x, 0.0, top / 2.0), 0.085, top, segments=14)
    _tube(TRIM, (mast_x, 0.0, top), 0.055, half_w * 2.15, segments=12,
          rot_y=math.radians(90))          # yard arm
    _sail(mast_x + 0.16, half_w, 0.55, top - 0.12, 0.42)

# Bowsprit and a stern lantern, for read at the extremities.
_tube(METAL, (-6.65, 0.0, -0.05), 0.07, 1.30, segments=10, rot_y=math.radians(90))
_box(TRIM, (5.30, 0.0, 0.45), (0.26, 0.26, 0.42))

_log("masts, sails and fittings placed")

# ------------------------------------------------------- high-poly detail pass ---
# Everything below exists to be BAKED, not shipped. The decimator throws most of this
# geometry away; the normal map keeps its shading. That is the trick behind the engine's
# stock hulls reading dense at 2-8k tris, and it is what the first version of this script
# was missing when it shipped a flat normal map.

# Deck cross-beams, each sized from the hull's own half-width at that station so they
# cannot poke through the sides.
for _i in range(1, len(STATIONS) - 1):
    _x, _hw, _dep = STATIONS[_i]
    _box(DECK, (_x, 0.0, -0.055), (0.20, _hw * 1.68, 0.07))

# Bulwark stanchions.
for _i in range(1, len(STATIONS) - 1):
    _x, _hw, _dep = STATIONS[_i]
    for _side in (1, -1):
        _box(HULL, (_x, _side * _hw * 0.985, 0.16), (0.10, 0.07, 0.32))

# Extra envelope seams between the structural hoops - panel lines for the normal map.
for _x in (-4.00, -1.55, 0.90, 3.40):
    _t = (_x - ENV_CENTER.x) / ENV_R.x
    if abs(_t) >= 0.985:
        continue
    _s = math.sqrt(max(0.0, 1.0 - _t * _t)) * 1.015
    _prim(bmesh.ops.create_cone, ENVELOPE,
          matrix=Matrix.Translation(Vector((_x, 0.0, ENV_CENTER.z)))
          @ Matrix.Rotation(math.radians(90), 4, "Y")
          @ Matrix.Diagonal(Vector((ENV_R.z * _s, ENV_R.y * _s, 1.0)).to_4d()),
          cap_ends=False, cap_tris=False, segments=44,
          radius1=1.0, radius2=1.0, depth=0.07)

_log("detail pass added, now %d faces" % len(bm.faces))

# Round every edge. Bevels are the single biggest contributor to a useful normal map -
# a perfectly sharp edge bakes to nothing, a rounded one bakes to a highlight.
# Bevel only HARD edges. Rounding every edge is fine when the decimator is about to delete
# most of them, but at 40k tris the creases survive and a smooth-shaded gasbag comes out
# looking quilted - every quad boundary of the sphere baked as a seam. Filtering by face
# angle keeps the corners and chines that want a highlight and leaves curvature alone.
_hard = [e for e in bm.edges
         if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(22)]
bmesh.ops.bevel(bm, geom=_hard, offset=0.011, segments=3, profile=0.62,
                affect="EDGES", clamp_overlap=True)
_log("bevelled %d hard edges -> %d faces" % (len(_hard), len(bm.faces)))

# ------------------------------------------------------------------ finalize ---
# NOTE: deliberately no recalc_face_normals here. Primitives recalc per shell in _prim(),
# the hull recalcs at build time, and a blanket pass over bm.faces would flip open shells
# (sails, bulwark strips, uncapped hoops) inside out anyway.
mesh = bpy.data.meshes.new("VEN_SkySkiff")
bm.to_mesh(mesh)
bm.free()

obj = bpy.data.objects.new("VEN_SkySkiff", mesh)
scene.collection.objects.link(obj)
for m in MATERIALS:
    obj.data.materials.append(m)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

# Shade flat: this is a faceted low-poly style, and flat shading is what bakes cleanly.
bpy.ops.object.shade_flat()
_log("mesh built: %d faces (pre-triangulation)" % len(mesh.polygons))

# ----------------------------------------------------------------- high-poly ---
# Snapshot BEFORE decimation. Taking it afterwards bakes the low-poly against itself and
# produces a flat, useless map - same reasoning as the kitbash bake.
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.duplicate()
high_obj = bpy.context.view_layer.objects.active     # duplicate() makes the COPY active
high_obj.name = "SCRATCH_HIGH"
# Subdivide the reference. With hard-edge bevels holding the corners, subdivision gives a
# genuinely smooth, dense high-poly to bake FROM. Without this the reference is the same
# mesh as the low-poly, the ratio comes out 1.000, and the normal bake writes the mesh
# against itself - a flat map, which is the failure this whole stage exists to avoid.
bpy.context.view_layer.objects.active = high_obj
_sub = high_obj.modifiers.new("subsurf", "SUBSURF")
_sub.levels = _sub.render_levels = 2
bpy.ops.object.modifier_apply(modifier=_sub.name)
_log("high-poly reference: %d faces (subdivided)" % len(high_obj.data.polygons))

# ----------------------------------------------------------------- decimate ----
# `obj` stays the low-poly that ships, so everything downstream is unchanged.
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
# Triangulate FIRST, so every count from here on is in the same unit the engine budgets in.
# Without this the ratio is computed against mixed quads and ngons while the exporter
# triangulates on the way out - which shipped a 12,958-tri hull against a 7,800 budget
# while the log cheerfully reported 7,427. Always measure in the unit you are bounded by.
_tri = obj.modifiers.new("triangulate", "TRIANGULATE")
bpy.ops.object.modifier_apply(modifier=_tri.name)
_before = len(obj.data.polygons)
if _before > TARGET_TRIS:
    _dec = obj.modifiers.new("decimate", "DECIMATE")
    _dec.ratio = float(TARGET_TRIS) / _before
    bpy.ops.object.modifier_apply(modifier=_dec.name)
    _log("decimated %d -> %d tris (ratio %.3f)"
         % (_before, len(obj.data.polygons), _dec.ratio))
else:
    # Under target already - decimating would only throw away detail we are allowed to keep.
    _log("kept %d tris (under the %d target, no decimation)" % (_before, TARGET_TRIS))

# ------------------------------------------------------------------- unwrap ----
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
# island_margin is 0.006 in the kitbash bake, which suits chunky imported parts. Authored
# geometry here includes long thin slivers - ribbing hoops, yard arms, struts - and
# smart_project packs those hard against the big envelope panels. At margin 8 the bake then
# dilates brass into the canvas, which showed up as a tan wedge across the envelope's stern.
# Give the islands room; at 672 faces there is plenty of atlas to spend.
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.022)
bpy.ops.object.mode_set(mode="OBJECT")
_log("unwrapped %d faces" % len(mesh.polygons))

# --------------------------------------------------------------------- bake ----
scene.render.engine = "CYCLES"
try:
    scene.cycles.device = "CPU"
    scene.cycles.samples = 4          # flat colour needs almost nothing
    scene.cycles.use_denoising = False
except Exception:                     # noqa: BLE001
    pass
scene.render.bake.use_selected_to_active = False
scene.render.bake.margin = 8


def _new_image(name, color, non_color=False):
    img = bpy.data.images.new(name, TEX, TEX, alpha=False)
    img.generated_color = color
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def _bake_to(img, bake_type, **kw):
    targets = []
    for slot in obj.material_slots:
        m = slot.material
        if not m or not m.use_nodes:
            continue
        node = m.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        m.node_tree.nodes.active = node
        node.select = True
        targets.append((m, node))
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.bake(type=bake_type, **kw)
    for m, node in targets:
        m.node_tree.nodes.remove(node)


root = os.path.splitext(OUT)[0]

diffuse_img = _new_image("scratch_diffuse", (0.5, 0.5, 0.5, 1.0))
_bake_to(diffuse_img, "DIFFUSE", pass_filter={"COLOR"})
diffuse_img.filepath_raw = root + "_diffuse.png"
diffuse_img.file_format = "PNG"
diffuse_img.save()
_log("baked diffuse")

emissive_img = _new_image("scratch_emissive", (0.0, 0.0, 0.0, 1.0))
_bake_to(emissive_img, "EMIT")
emissive_img.filepath_raw = root + "_emissive.png"
emissive_img.file_format = "PNG"
emissive_img.save()
_log("baked emissive")

# --- normal, baked from the HIGH-poly onto the decimated mesh ------------------
# This is the whole point of building high and shipping low: the bevels, beams, stanchions
# and panel seams the decimator deleted come back as shading.
normal_img = _new_image("scratch_normal", (0.5, 0.5, 1.0, 1.0), non_color=True)
try:
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.cage_extrusion = 0.35
    bpy.ops.object.select_all(action="DESELECT")
    high_obj.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for slot in obj.material_slots:
        m = slot.material
        node = m.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = normal_img
        m.node_tree.nodes.active = node
        node.select = True
    bpy.ops.object.bake(type="NORMAL")
    _log("baked normal from high-poly (%d -> %d tris)"
         % (len(high_obj.data.polygons), len(obj.data.polygons)))
except Exception as e:                            # noqa: BLE001
    _log("normal bake failed (%s) - shipping flat" % e)
finally:
    scene.render.bake.use_selected_to_active = False
normal_img.filepath_raw = root + "_normal.png"
normal_img.file_format = "PNG"
normal_img.save()

# The high-poly is scaffolding; only the baked low-poly ships.
bpy.data.objects.remove(high_obj, do_unlink=True)

# Specular derived from the baked diffuse's luminance, damped - painted metal trim reads
# brighter than canvas or timber, and it is at least DERIVED rather than guessed.
import numpy as np                                              # noqa: E402

px = np.empty(len(diffuse_img.pixels), dtype=np.float32)
diffuse_img.pixels.foreach_get(px)
rgba = px.reshape(-1, 4)
lum = rgba[:, :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
lum = np.clip((lum - 0.5) * 1.3 + 0.5, 0.0, 1.0) * 0.45
spec_img = _new_image("scratch_specular", (0.0, 0.0, 0.0, 1.0))
spec_img.pixels.foreach_set(
    np.stack([lum, lum, lum, np.ones_like(lum)], axis=1).ravel())
spec_img.filepath_raw = root + "_specular.png"
spec_img.file_format = "PNG"
spec_img.save()
_log("wrote maps at %dpx" % TEX)

# -------------------------------------------------------------------- export ---
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.wm.obj_export(filepath=OUT, export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, export_normals=True, export_uv=True)
_log("wrote %s" % OUT)
