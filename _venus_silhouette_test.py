"""Render a glb as a TRUE silhouette: transparent film, orthographic side profile.
Usage: blender -b -P silhouette.py -- <glb> <out.png>
The alpha channel is the silhouette; a PIL pass converts it to black-on-white."""
import bpy, sys, math
from mathutils import Vector

glb = sys.argv[-2]
out = sys.argv[-1]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)

objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
mins = Vector((1e9,)*3); maxs = Vector((-1e9,)*3)
for o in objs:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            mins[i] = min(mins[i], w[i]); maxs[i] = max(maxs[i], w[i])
center = (mins + maxs) / 2.0
size = maxs - mins

# Pure SIDE profile. The camera must look PERPENDICULAR to the long axis, otherwise the
# render is an end-on view and every ship looks like a disc. Pick the view direction as the
# SHORTEST extent, so the two longest axes both lie in frame.
cam_data = bpy.data.cameras.new("Cam")
cam_data.type = 'ORTHO'
axes = [(size.x, 0), (size.y, 1), (size.z, 2)]
view_axis = min(axes)[1]                     # look along the thinnest direction
in_frame = [size[i] for i in range(3) if i != view_axis]
cam_data.ortho_scale = max(in_frame) * 1.35
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
dist = max(size) * 3.0
if view_axis == 0:      # look along -X
    cam.location = center + Vector((dist, 0, 0))
    cam.rotation_euler = (math.radians(90), 0, math.radians(90))
elif view_axis == 1:    # look along -Y
    cam.location = center + Vector((0, -dist, 0))
    cam.rotation_euler = (math.radians(90), 0, 0)
else:                   # look along -Z
    cam.location = center + Vector((0, 0, dist))
    cam.rotation_euler = (0, 0, 0)
print("VIEW AXIS", view_axis, "extents", tuple(round(v, 3) for v in size))

scn = bpy.context.scene
scn.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [
    e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items
] else 'BLENDER_EEVEE'
scn.render.film_transparent = True          # alpha IS the silhouette
scn.render.resolution_x = 900
scn.render.resolution_y = 900
scn.render.image_settings.file_format = 'PNG'
scn.render.image_settings.color_mode = 'RGBA'
scn.render.filepath = out
bpy.ops.render.render(write_still=True)
print("SILHOUETTE SAVED", out)
