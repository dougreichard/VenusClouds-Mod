"""glb -> .obj in the same shape the existing VEN_* ships have.

trimesh's OBJ export drops UVs and normals unless textures are included, giving
position-only faces (`f 11 13 6`). The mock's _parseOBJ and the engine both want
`f v/vt/vn` - without UVs the diffuse map has nothing to map onto and the ship
renders as an untextured placeholder. The shipped VEN_*.obj were written by Blender,
so use Blender.

  blender -b -P glb2obj_blender.py -- <in.glb> <out.obj>
"""
import bpy, sys

src, dst = sys.argv[-2], sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
print("imported", len(meshes), "mesh objects, faces",
      sum(len(o.data.polygons) for o in meshes))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.wm.obj_export(filepath=dst,
                      export_selected_objects=True,
                      export_uv=True,
                      export_normals=True,
                      export_materials=False,
                      export_triangulated_mesh=True)
print("SAVED", dst)
