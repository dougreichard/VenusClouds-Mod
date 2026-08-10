"""Headless Blender half of the kitbash assembler: place parts, export one OBJ.

Geometry ONLY. Textures are the driver's job (`_venus_kit_bake.py`), because Blender's
bundled Python has no PIL and the texture step is a file copy plus two solid-colour images.

    blender --background --python _venus_kit_blender.py -- <job.json> <out.obj>

The job JSON is ``{"parts": [{"path":..., "offset":[x,y,z], "rot":[x,y,z], "scale":[x,y,z]}]}``.

AXES. The Synty boat parts are already +Z long / +Y up, which is Cosmos's own convention,
so nothing needs rotating. Blender's OBJ importer and exporter both default to
forward=-Z, up=Y, so a round trip through here is axis-neutral - the defaults are LEFT
ALONE deliberately, and changing one without the other silently rolls every ship 90 degrees.

NO JOIN. Multi-object OBJ is legal (`God_Phoenix` ships 16 submeshes and loads; stock
`monster2` is itself a two-part kitbash), and keeping parts separate leaves them
individually editable. What Cosmos actually requires is one TEXTURE SET, which a
single-atlas pack satisfies for free.

NO normalize_prop. That script hardcodes `location.z -= mn[2]` (base-at-floor - the plinths
under the first generated hulls) AND rescales every mesh to 1.0m, which would destroy the
relative scale of parts that are meant to fit together.
"""
import json
import math
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
JOB, OUT = argv[0], argv[1]
BUDGET = int(argv[2]) if len(argv) > 2 else 0

with open(JOB, encoding="utf-8") as f:
    job = json.load(f)

bpy.ops.wm.read_factory_settings(use_empty=True)

placed = 0
for part in job["parts"]:
    path = part["path"]
    before = set(bpy.context.scene.objects)
    try:
        bpy.ops.wm.obj_import(filepath=path)
    except Exception as e:                      # noqa: BLE001 - report and keep going
        print("KIT: FAILED to import %s: %s" % (path, e))
        continue
    new = [o for o in bpy.context.scene.objects if o not in before]
    if not new:
        print("KIT: imported nothing from %s" % path)
        continue

    off = part.get("offset", [0, 0, 0])
    rot = part.get("rot", [0, 0, 0])
    scl = part.get("scale", [1, 1, 1])
    for o in new:
        # Scale and rotate about the part's own origin, then offset - which is what a
        # recipe author means by "put this there at this size".
        o.scale = (o.scale[0] * scl[0], o.scale[1] * scl[1], o.scale[2] * scl[2])
        o.rotation_euler = (o.rotation_euler[0] + math.radians(rot[0]),
                            o.rotation_euler[1] + math.radians(rot[1]),
                            o.rotation_euler[2] + math.radians(rot[2]))
        # The importer already mapped the file's Y-up into Blender's Z-up, so a recipe
        # offset written in COSMOS axes (x, y=up, z=long) has to be mapped the same way.
        o.location = (o.location[0] + off[0],
                      o.location[1] + off[2],
                      o.location[2] + off[1])
        o.name = os.path.splitext(os.path.basename(path))[0]
    placed += 1

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]


def _faces():
    return sum(len(o.data.polygons)
               for o in bpy.context.scene.objects if o.type == "MESH")


# DECIMATE AFTER ASSEMBLY, never per part. Reducing a part in isolation cannot know which
# of its faces end up buried inside a neighbour, so the same triangle budget buys a lot
# more silhouette when it is spent across the finished ship.
#
# Collapse ratio is applied uniformly rather than per-object: weighting it by object would
# quietly erase the small parts (the rigging is only 1584 faces and is most of what reads
# as an airship) to protect the hull.
if BUDGET and meshes:
    # TRIANGULATE FIRST, then budget. The exporter triangulates anyway, so decimating a
    # quad count is budgeting a number that never ships - the first attempt reduced 6669
    # "faces" by 6% and still exported 8653 triangles. Counting triangles up front makes
    # the budget mean what it says.
    for o in meshes:
        bpy.context.view_layer.objects.active = o
        mod = o.modifiers.new("kit_tri", "TRIANGULATE")
        bpy.ops.object.modifier_apply(modifier=mod.name)

    before = _faces()
    if before > BUDGET:
        ratio = max(0.05, float(BUDGET) / float(before))
        for o in meshes:
            bpy.context.view_layer.objects.active = o
            mod = o.modifiers.new("kit_decimate", "DECIMATE")
            mod.ratio = ratio
            bpy.ops.object.modifier_apply(modifier=mod.name)
        print("KIT: decimated %d -> %d tris (ratio %.3f, budget %d)"
              % (before, _faces(), ratio, BUDGET))
    else:
        print("KIT: %d tris, within budget %d - no decimation" % (before, BUDGET))

verts = sum(len(o.data.vertices) for o in meshes)
tris = sum(len(o.data.loop_triangles) if o.data.loop_triangles else len(o.data.polygons)
           for o in meshes)
print("KIT: placed %d/%d parts, %d objects, %d verts, ~%d faces"
      % (placed, len(job["parts"]), len(meshes), verts, tris))

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.wm.obj_export(filepath=OUT,
                      export_selected_objects=True,
                      export_materials=False,   # the engine names textures from artfileroot;
                                                # 63 stock OBJs point at a missing .mtl and
                                                # render fine, so a material is dead weight
                      export_triangulated_mesh=True,
                      export_normals=True,
                      export_uv=True)
print("KIT: wrote %s" % OUT)
