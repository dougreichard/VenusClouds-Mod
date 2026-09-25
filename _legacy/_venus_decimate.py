"""Blender decimate as a control against Trellis2SimplifyMesh.
  blender -b -P decimate.py -- <in.glb> <target_faces> <out.glb>"""
# NOTE: orientation is NOT done here. Blender is Z-up and the glTF exporter converts to
# Y-up, so an in-Blender rotation does not land where you expect in the written file; and
# Trellis2MeshTexturing re-orients afterwards anyway. Run _venus_orient.py on the FINISHED
# textured .glb instead - it works in glTF space, where what you measure is what Cosmos reads.

import bpy, sys

src, target, out = sys.argv[-3], int(sys.argv[-2]), sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)

meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
total = sum(len(o.data.polygons) for o in meshes)
print("BEFORE faces", total, "objects", len(meshes))

ratio = min(1.0, target / total) if total else 1.0
for o in meshes:
    bpy.context.view_layer.objects.active = o
    m = o.modifiers.new("dec", 'DECIMATE')
    m.decimate_type = 'COLLAPSE'
    m.ratio = ratio
    m.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=m.name)

# WELD. glTF export splits a vertex per face when normals/UVs are not shared, which turns the
# result into a triangle soup: 3x verts, one body per face, and NO face adjacency - which makes
# the mesh untexturable (CuMesh get_manifold_face_adjacency fails on it). Merge by distance and
# share normals so the mesh stays connected.
for o in meshes:
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=1e-5)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.shade_smooth()

after = sum(len(o.data.polygons) for o in bpy.context.scene.objects if o.type == 'MESH')
averts = sum(len(o.data.vertices) for o in bpy.context.scene.objects if o.type == 'MESH')
print("AFTER faces", after, "verts", averts, "ratio", round(ratio, 5))

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True)
print("SAVED", out)
