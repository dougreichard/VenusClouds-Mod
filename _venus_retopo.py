"""Voxel-remesh then decimate, to reach a real poly budget.

Collapse decimation stalls on these ships because the rigging and struts are open surfaces:
their boundary edges cannot be collapsed across, so the mesh floors out around 85k. A voxel
remesh rebuilds the whole thing as ONE closed manifold shell, after which decimation runs
freely to target.

  blender -b -P retopo.py -- <in.glb> <voxel_size> <target_faces> <out.glb>

voxel_size is in model units; the ships are normalized to ~1.0 long, so 0.004 keeps fairly
fine detail and 0.010 is chunky.
"""
# NOTE: orientation is NOT done here. Blender is Z-up and the glTF exporter converts to
# Y-up, so an in-Blender rotation does not land where you expect in the written file; and
# Trellis2MeshTexturing re-orients afterwards anyway. Run _venus_orient.py on the FINISHED
# textured .glb instead - it works in glTF space, where what you measure is what Cosmos reads.

import bpy, sys
from mathutils import Vector

src, voxel, target, out = sys.argv[-4], float(sys.argv[-3]), int(sys.argv[-2]), sys.argv[-1]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
print("BEFORE faces", sum(len(o.data.polygons) for o in meshes), "objects", len(meshes))

# join everything first - a voxel remesh of separate objects would produce separate shells
bpy.ops.object.select_all(action='DESELECT')
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
obj = bpy.context.view_layer.objects.active

m = obj.modifiers.new("remesh", 'REMESH')
m.mode = 'VOXEL'
m.voxel_size = voxel
m.use_smooth_shade = True
bpy.ops.object.modifier_apply(modifier=m.name)
print("REMESHED faces", len(obj.data.polygons))

n = len(obj.data.polygons)
if n > target:
    d = obj.modifiers.new("dec", 'DECIMATE')
    d.decimate_type = 'COLLAPSE'
    d.ratio = target / n
    d.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=d.name)

# weld: glTF export splits a vertex per face otherwise, giving a triangle soup with no adjacency
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=1e-5)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')

print("AFTER faces", len(obj.data.polygons), "verts", len(obj.data.vertices))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True)
print("SAVED", out)
