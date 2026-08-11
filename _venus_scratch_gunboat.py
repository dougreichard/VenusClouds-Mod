"""Build a Kingdom steam gunboat from PROCEDURAL geometry, against the concept art.

    blender --background --python _venus_scratch_gunboat.py -- <out.obj> [texsize] [tris]

Designed from `_refs/_grid_fleet_component.png` (KINGDOM FLEET COMPONENT SCHEMATICS, the
"CLASSIC GUNBOAT" in the SCOUT SKIFF & GUNBOAT row) and the sepia fleet concept in
`E:/a/venus_clouds/venus_clouds.png`, where the same little steam launches recur under the
big dirigibles. Five things the concept has that the kitbashed fleet does not:

  * PADDLE WHEELS with gear drives - the Kingdom's signature, called out by name on the
    schematic for the outpost, the Golden Vanguard and here;
  * a SMOKESTACK trailing smoke, with a steam dome ahead of it;
  * BRASS everywhere - banding, rails, fittings - over dark tarred timber;
  * a SHORT, FAT lift bag, not the long cigar the cruisers carry;
  * a sepia/amber palette. The kitbash hulls are orange-red; the art is brass and tan.

Pipeline is the same as _venus_scratch_ship.py and the kitbash bake: author a detailed
mesh, subdivide a copy as the high-poly reference, decimate to target, and bake diffuse,
emissive and a real high-to-low normal into ONE atlas.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
TEX = int(argv[1]) if len(argv) > 1 else 2048
# The TNG mod's 46 in-engine meshes run to 145,856 tris (median 14,092), so the stock
# hulls' 1,790-7,784 is a description of the base art, not a ceiling. Sit near that median.
TARGET_TRIS = int(argv[2]) if len(argv) > 2 else 14000


def _log(msg):
    print("GUNBOAT: %s" % msg)


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


# Sampled off the concept art, not invented: tarred timber, sun-bleached canvas, and a lot
# of brass. Deliberately warmer and far less saturated than the kitbash fleet's orange-red.
MATERIALS = [
    _mat("timber",  (0.098, 0.068, 0.046)),              # 0 tarred hull planking
    _mat("deck",    (0.285, 0.200, 0.118)),              # 1 holystoned deck
    _mat("canvas",  (0.640, 0.580, 0.442)),              # 2 lift bag
    _mat("brass",   (0.520, 0.372, 0.128), 0.38, 0.85),  # 3 banding, rails, fittings
    _mat("iron",    (0.150, 0.148, 0.156), 0.55, 0.80),  # 4 stack, machinery
    _mat("verdig",  (0.180, 0.330, 0.286), 0.60, 0.30),  # 5 weathered copper accent
]
TIMBER, DECK, CANVAS, BRASS, IRON, VERDIG = range(6)

bm = bmesh.new()


def _prim(op, mat_index, matrix=None, **kw):
    """Create a primitive, place it, tag its material, fix its normals.

    New geometry comes from the OPERATOR'S RETURN VALUE. A positional slice like
    `list(bm.verts)[v0:]` is not reliable once bmesh.ops has run a few times - it grabs the
    wrong verts and the matrix lands on unrelated geometry.
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
    bmesh.ops.recalc_face_normals(bm, faces=new_faces)


def _box(mat_index, center, size, rot_x=0.0, rot_y=0.0, rot_z=0.0):
    m = Matrix.Translation(Vector(center))
    if rot_z:
        m = m @ Matrix.Rotation(rot_z, 4, "Z")
    if rot_y:
        m = m @ Matrix.Rotation(rot_y, 4, "Y")
    if rot_x:
        m = m @ Matrix.Rotation(rot_x, 4, "X")
    _prim(bmesh.ops.create_cube, mat_index, matrix=m @ Matrix.Diagonal(Vector(size).to_4d()),
          size=1.0)


def _tube(mat_index, center, radius, height, segments=16, rot_x=0.0, rot_y=0.0, taper=1.0):
    m = Matrix.Translation(Vector(center))
    if rot_y:
        m = m @ Matrix.Rotation(rot_y, 4, "Y")
    if rot_x:
        m = m @ Matrix.Rotation(rot_x, 4, "X")
    _prim(bmesh.ops.create_cone, mat_index, matrix=m,
          cap_ends=True, cap_tris=False, segments=segments,
          radius1=radius, radius2=radius * taper, depth=height)


# ----------------------------------------------------------------------- hull ---
# Beamier and blunter than the scout skiff - this is a gunboat, and the schematic's
# silhouette is a working boat, not a yacht.
STATIONS = [
    (-5.60, 0.08, 0.30),
    (-4.60, 0.52, 0.66),
    (-3.10, 0.92, 0.98),
    (-1.20, 1.20, 1.14),
    (0.90, 1.26, 1.16),
    (2.80, 1.18, 1.06),
    (4.20, 1.00, 0.88),
    (5.10, 0.86, 0.74),      # near-square transom, like the schematic's stern
]
PROFILE = [
    (1.00, 0.00), (0.99, -0.28), (0.86, -0.60), (0.56, -0.87),
    (0.00, -1.00),
    (-0.56, -0.87), (-0.86, -0.60), (-0.99, -0.28), (-1.00, 0.00),
]

rings = []
for x, hw, depth in STATIONS:
    rings.append([bm.verts.new((x, yf * hw, zf * depth)) for yf, zf in PROFILE])
bm.verts.ensure_lookup_table()

hull_faces = []
for a, b in zip(rings, rings[1:]):
    for i in range(len(PROFILE) - 1):
        hull_faces.append(bm.faces.new((a[i], a[i + 1], b[i + 1], b[i])))
    hull_faces.append(bm.faces.new((a[-1], a[0], b[0], b[-1])))     # sheer line
hull_faces.append(bm.faces.new(list(reversed(rings[0]))))           # stem
hull_faces.append(bm.faces.new(rings[-1]))                          # transom
for f in hull_faces:
    f.material_index = TIMBER
# Recalc while these faces still exist - the bevel later deletes and rebuilds them.
bmesh.ops.recalc_face_normals(bm, faces=hull_faces)

# Deck, bulwark, and a brass capping rail along the sheer.
deck_rings = []
for x, hw, _d in STATIONS[1:-1]:
    inner = hw * 0.88
    deck_rings.append((bm.verts.new((x, inner, -0.09)), bm.verts.new((x, -inner, -0.09))))
for (sa, pa), (sb, pb) in zip(deck_rings, deck_rings[1:]):
    f = bm.faces.new((sa, pa, pb, sb))
    f.material_index = DECK

for side in (1, -1):
    prev = None
    for x, hw, _d in STATIONS[1:-1]:
        lo = bm.verts.new((x, side * hw, 0.0))
        hi = bm.verts.new((x, side * hw * 0.97, 0.34))
        if prev is not None:
            f = bm.faces.new((prev[0], lo, hi, prev[1]) if side > 0
                             else (prev[1], hi, lo, prev[0]))
            f.material_index = TIMBER
        prev = (lo, hi)
    for x, hw, _d in STATIONS[1:-1]:
        _box(BRASS, (x, side * hw * 0.97, 0.37), (0.30, 0.10, 0.07))   # capping rail

_log("hull lofted from %d stations" % len(STATIONS))

# --------------------------------------------------------------- paddle wheels ---
# THE Kingdom signature. The schematic labels "PROPULSION PADDLE WHEELS" and "PADDLE WHEELS
# & GEAR DRIVES" on three separate classes, and the concept art's launches all carry them.
PADDLE_X = 1.35
WHEEL_R = 1.16
for side in (1, -1):
    y = side * 1.62
    # Sponson carrying the wheel outboard of the hull.
    _box(TIMBER, (PADDLE_X, side * 1.18, -0.18), (1.55, 0.85, 0.42))
    # Hub and axle.
    _tube(IRON, (PADDLE_X, y, 0.0), 0.20, 0.46, segments=14, rot_x=math.radians(90))
    _tube(BRASS, (PADDLE_X, side * 1.05, 0.0), 0.085, 1.30, segments=10,
          rot_x=math.radians(90))
    # Paddle boards on radial arms - eight, as drawn.
    for i in range(8):
        a = i / 8.0 * math.tau
        cy, cz = math.cos(a), math.sin(a)
        # radial arm
        _box(BRASS, (PADDLE_X + cy * WHEEL_R * 0.55, y, cz * WHEEL_R * 0.55),
             (WHEEL_R * 0.92, 0.07, 0.07), rot_y=-a)
        # the board itself, tangential at the rim
        _box(TIMBER, (PADDLE_X + cy * WHEEL_R, y, cz * WHEEL_R),
             (0.30, 0.62, 0.09), rot_y=-a)
    # Outer rim ring.
    _prim(bmesh.ops.create_cone, BRASS,
          matrix=Matrix.Translation(Vector((PADDLE_X, y, 0.0)))
          @ Matrix.Rotation(math.radians(90), 4, "X")
          @ Matrix.Diagonal(Vector((WHEEL_R, WHEEL_R, 1.0)).to_4d()),
          cap_ends=False, cap_tris=False, segments=32,
          radius1=1.0, radius2=1.0, depth=0.52)
    # Paddle box: the housing hooding the top of the wheel.
    _box(TIMBER, (PADDLE_X, y, WHEEL_R * 0.86), (1.70, 0.66, 0.34))
    _box(BRASS, (PADDLE_X, y, WHEEL_R * 1.06), (1.76, 0.70, 0.08))
    # Gear drive on the inboard face.
    _tube(BRASS, (PADDLE_X - 0.95, side * 1.20, 0.10), 0.34, 0.14, segments=18,
          rot_x=math.radians(90))
    _tube(IRON, (PADDLE_X - 0.95, side * 1.20, 0.10), 0.13, 0.20, segments=10,
          rot_x=math.radians(90))

_log("paddle wheels, boxes and gear drives placed")

# ------------------------------------------------------- stack, dome, machinery ---
# Funnel amidships with brass banding, and the steam dome ahead of it.
_tube(IRON, (-0.30, 0.0, 1.35), 0.30, 2.30, segments=18, taper=0.88)
for zz in (0.55, 1.35, 2.15):
    _tube(BRASS, (-0.30, 0.0, zz), 0.335, 0.13, segments=18)
_tube(BRASS, (-0.30, 0.0, 2.52), 0.335, 0.16, segments=18)          # crown
_tube(BRASS, (-1.45, 0.0, 0.34), 0.42, 0.62, segments=18)           # steam dome
_prim(bmesh.ops.create_uvsphere, BRASS,
      matrix=Matrix.Translation(Vector((-1.45, 0.0, 0.64)))
      @ Matrix.Diagonal(Vector((0.42, 0.42, 0.26)).to_4d()),
      u_segments=18, v_segments=9, radius=1.0)
# Engine housing between the wheels, and a verdigris condenser.
_box(TIMBER, (0.95, 0.0, 0.28), (2.30, 1.55, 0.72))
_box(BRASS, (0.95, 0.0, 0.66), (2.36, 1.60, 0.09))
_tube(VERDIG, (2.55, 0.0, 0.36), 0.30, 1.05, segments=14, rot_y=math.radians(90))

# Wheelhouse forward, with a brass-framed window band.
_box(TIMBER, (-2.60, 0.0, 0.52), (1.30, 1.30, 1.00))
_box(BRASS, (-2.60, 0.0, 0.86), (1.36, 1.36, 0.10))
_box(VERDIG, (-2.60, 0.0, 1.06), (1.10, 1.10, 0.30))                # roof

# Bow gun on a pivot - "CLASSIC GUNBOAT".
_tube(IRON, (-4.05, 0.0, 0.30), 0.26, 0.34, segments=14)
_tube(IRON, (-4.55, 0.0, 0.46), 0.105, 1.30, segments=12, rot_y=math.radians(90))
_tube(BRASS, (-4.10, 0.0, 0.46), 0.135, 0.22, segments=12, rot_y=math.radians(90))

_log("stack, dome, wheelhouse and bow gun placed")

# -------------------------------------------------------------------- lift bag ---
# Short and fat, per the schematic's gunboat - the long cigar belongs to the cruisers.
ENV_C = Vector((0.10, 0.0, 4.15))
ENV_R = Vector((3.30, 1.34, 1.24))
_prim(bmesh.ops.create_uvsphere, CANVAS,
      matrix=Matrix.Translation(ENV_C) @ Matrix.Diagonal(ENV_R.to_4d()),
      u_segments=56, v_segments=28, radius=1.0)
# Longitudinal ribbing: the concept bags are visibly framed, not smooth balloons.
for x in (-2.10, -0.75, 0.60, 1.95):
    t = (x - ENV_C.x) / ENV_R.x
    if abs(t) >= 0.985:
        continue
    s = math.sqrt(max(0.0, 1.0 - t * t)) * 1.02
    _prim(bmesh.ops.create_cone, BRASS,
          matrix=Matrix.Translation(Vector((x, 0.0, ENV_C.z)))
          @ Matrix.Rotation(math.radians(90), 4, "Y")
          @ Matrix.Diagonal(Vector((ENV_R.z * s, ENV_R.y * s, 1.0)).to_4d()),
          cap_ends=False, cap_tris=False, segments=30,
          radius1=1.0, radius2=1.0, depth=0.10)
# Stern fins.
_box(CANVAS, (ENV_C.x + ENV_R.x - 0.30, 0.0, ENV_C.z + 1.05), (1.15, 0.09, 1.05))
_box(CANVAS, (ENV_C.x + ENV_R.x - 0.30, 0.92, ENV_C.z), (1.15, 1.25, 0.09))
_box(CANVAS, (ENV_C.x + ENV_R.x - 0.30, -0.92, ENV_C.z), (1.15, 1.25, 0.09))
# Suspension: struts plus rigging lines down to the sheer.
ENV_FLOOR = ENV_C.z - ENV_R.z
for sx in (-1.55, 1.70):
    for sy in (0.72, -0.72):
        h = ENV_FLOOR - 0.34
        _box(IRON, (sx, sy, 0.34 + h / 2.0), (0.11, 0.11, h))
for sx in (-2.70, 2.85):
    for sy in (0.95, -0.95):
        _tube(BRASS, (sx, sy, (ENV_FLOOR + 0.30) / 2.0 + 0.15), 0.035,
              ENV_FLOOR - 0.30, segments=6)

_log("lift bag, ribbing, fins and rigging placed")

# ------------------------------------------------------------- high-poly detail ---
for i in range(1, len(STATIONS) - 1):
    x, hw, _d = STATIONS[i]
    _box(DECK, (x, 0.0, -0.048), (0.20, hw * 1.66, 0.07))            # deck beams
    for side in (1, -1):
        _box(TIMBER, (x, side * hw * 0.985, 0.17), (0.10, 0.07, 0.34))   # stanchions
_log("detail pass added, now %d faces" % len(bm.faces))

# Bevel HARD edges only. Rounding every edge quilts a smooth-shaded gas bag once the mesh
# is dense enough that the decimator no longer erases the creases.
_hard = [e for e in bm.edges
         if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(22)]
bmesh.ops.bevel(bm, geom=_hard, offset=0.010, segments=3, profile=0.62,
                affect="EDGES", clamp_overlap=True)
_log("bevelled %d hard edges -> %d faces" % (len(_hard), len(bm.faces)))

mesh = bpy.data.meshes.new("VEN_Gunboat")
bm.to_mesh(mesh)
bm.free()

obj = bpy.data.objects.new("VEN_Gunboat", mesh)
scene.collection.objects.link(obj)
for m in MATERIALS:
    obj.data.materials.append(m)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.shade_flat()
_log("mesh built: %d faces" % len(mesh.polygons))

# ------------------------------------------------------------------ high-poly ---
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.duplicate()
high_obj = bpy.context.view_layer.objects.active
high_obj.name = "GUNBOAT_HIGH"
bpy.context.view_layer.objects.active = high_obj
_sub = high_obj.modifiers.new("subsurf", "SUBSURF")
_sub.levels = _sub.render_levels = 2
bpy.ops.object.modifier_apply(modifier=_sub.name)
_log("high-poly reference: %d faces (subdivided)" % len(high_obj.data.polygons))

# ------------------------------------------------------------------- decimate ---
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
# Triangulate FIRST so every count is in the unit the budget is written in - the exporter
# triangulates on the way out, so a ratio taken against quads ships far more than intended.
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
    _log("kept %d tris (under the %d target)" % (_before, TARGET_TRIS))

# --------------------------------------------------------------------- unwrap ---
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.022)
bpy.ops.object.mode_set(mode="OBJECT")
_log("unwrapped %d faces" % len(obj.data.polygons))

# ----------------------------------------------------------------------- bake ---
scene.render.engine = "CYCLES"
try:
    scene.cycles.device = "CPU"
    scene.cycles.samples = 4
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

diffuse_img = _new_image("gb_diffuse", (0.5, 0.5, 0.5, 1.0))
_bake_to(diffuse_img, "DIFFUSE", pass_filter={"COLOR"})
diffuse_img.filepath_raw = root + "_diffuse.png"
diffuse_img.file_format = "PNG"
diffuse_img.save()
_log("baked diffuse")

emissive_img = _new_image("gb_emissive", (0.0, 0.0, 0.0, 1.0))
_bake_to(emissive_img, "EMIT")
emissive_img.filepath_raw = root + "_emissive.png"
emissive_img.file_format = "PNG"
emissive_img.save()

normal_img = _new_image("gb_normal", (0.5, 0.5, 1.0, 1.0), non_color=True)
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

bpy.data.objects.remove(high_obj, do_unlink=True)

import numpy as np                                              # noqa: E402

px = np.empty(len(diffuse_img.pixels), dtype=np.float32)
diffuse_img.pixels.foreach_get(px)
rgba = px.reshape(-1, 4)
lum = rgba[:, :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
lum = np.clip((lum - 0.5) * 1.3 + 0.5, 0.0, 1.0) * 0.45
spec_img = _new_image("gb_specular", (0.0, 0.0, 0.0, 1.0))
spec_img.pixels.foreach_set(
    np.stack([lum, lum, lum, np.ones_like(lum)], axis=1).ravel())
spec_img.filepath_raw = root + "_specular.png"
spec_img.file_format = "PNG"
spec_img.save()
_log("wrote maps at %dpx" % TEX)

bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.wm.obj_export(filepath=OUT, export_selected_objects=True, export_materials=False,
                      export_triangulated_mesh=True, export_normals=True, export_uv=True)
_log("wrote %s" % OUT)
