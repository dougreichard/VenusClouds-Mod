"""Three-quarter render that finds the ship's own axes first.

prop_farm/render_glb.py places the camera at a FIXED world offset, which is fine for a compact
prop but looks straight down the nose of a long hull whose orientation changed - and Trellis2's
texturing stage re-orients meshes, so the orientation is not predictable. This computes the
camera from the mesh's own longest / vertical axes instead.

  blender -b -P render3q.py -- <in.glb> <out.png>
"""
import bpy, sys, math
from mathutils import Vector

src, out = sys.argv[-2], sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)

objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
mn = Vector((1e9,)*3); mx = Vector((-1e9,)*3)
for o in objs:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
center = (mn + mx) / 2.0
size = mx - mn
order = sorted(range(3), key=lambda i: size[i])   # ascending
depth_i, up_i, long_i = order[0], order[1], order[2]
radius = max(size)

# stand off along the SHORT axis, slide down the long axis, and lift along the vertical
off = Vector((0, 0, 0))
off[depth_i] = radius * 2.60
off[long_i]  = -radius * 0.55
off[up_i]    = radius * 1.10

cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
cam.location = center + off
d = center - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cam_data.lens = 50

world = bpy.data.worlds.new("W"); bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.55, 0.57, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sun_d = bpy.data.lights.new("Sun", 'SUN'); sun_d.energy = 4.0
sun = bpy.data.objects.new("Sun", sun_d); bpy.context.scene.collection.objects.link(sun)
sun.rotation_euler = (math.radians(55), math.radians(15), math.radians(35))

scn = bpy.context.scene
scn.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [
    e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items
] else 'BLENDER_EEVEE'
scn.render.resolution_x = 900
scn.render.resolution_y = 620
scn.render.filepath = out
print("axes: long=%s up=%s depth=%s  extents=%s" %
      ("XYZ"[long_i], "XYZ"[up_i], "XYZ"[depth_i], tuple(round(v,3) for v in size)))
bpy.ops.render.render(write_still=True)
print("SAVED", out)
