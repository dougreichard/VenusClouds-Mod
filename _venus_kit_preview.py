"""Render a kitbashed .obj to a PNG, with its atlas applied, so the assembly can be judged.

    blender --background --python _venus_kit_preview.py -- <mesh.obj> <diffuse.png> <out.png>

Three-quarter view, because that is the angle that shows both the length of a hull and the
envelope sitting above it. Textured rather than grey: half the point of the single-atlas
trick is whether the UVs land somewhere sensible, and grey clay cannot show that.
"""
import os
import sys
import math

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
MESH, DIFFUSE, OUT = argv[0], argv[1], argv[2]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=MESH)

objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]

mat = bpy.data.materials.new("atlas")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = bpy.data.images.load(DIFFUSE)
tex.interpolation = "Closest"          # Synty atlases are flat colour blocks; no blur
mat.node_tree.links.new(bsdf.inputs["Base Color"], tex.outputs["Color"])
bsdf.inputs["Roughness"].default_value = 0.85
for o in objs:
    o.data.materials.clear()
    o.data.materials.append(mat)

mins = Vector((1e9,) * 3)
maxs = Vector((-1e9,) * 3)
for o in objs:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            mins[i] = min(mins[i], w[i])
            maxs[i] = max(maxs[i], w[i])
center = (mins + maxs) / 2.0
radius = max((maxs - mins).length / 2.0, 0.001)

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
d = radius * 2.9
cam.location = center + Vector((d * 0.72, -d * 0.80, d * 0.42))
direction = center - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

key = bpy.data.objects.new("key", bpy.data.lights.new("key", type="SUN"))
key.data.energy = 4.0
key.rotation_euler = (math.radians(52), 0, math.radians(35))
bpy.context.scene.collection.objects.link(key)

w = bpy.data.worlds.new("w")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.30, 0.28, 0.26, 1)
bpy.context.scene.world = w

s = bpy.context.scene
s.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in \
    [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] \
    else "BLENDER_WORKBENCH"
s.render.resolution_x, s.render.resolution_y = 1000, 700
s.render.film_transparent = False
s.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("KIT: preview -> %s" % OUT)
