"""Assemble an airship from generated PARTS, the way venus_kit_recipes.py composes a hull.

  blender -b -P assemble.py -- <envelope.glb> <gondola.glb> <out.glb>

Parts arrive at arbitrary scale, so the gondola is normalized against the envelope's length
rather than trusting either file's units - the same problem the kit solves with per-pack
scale factors. Gap is expressed as a fraction of envelope height so it survives a re-generate.
"""
import bpy, sys
from mathutils import Vector

env_path, gon_path, out_path = sys.argv[-3], sys.argv[-2], sys.argv[-1]

GONDOLA_LEN_FRAC = 0.52   # gondola length as a fraction of envelope length
GAP_FRAC         = 0.08   # open air between them, as a fraction of envelope height

bpy.ops.wm.read_factory_settings(use_empty=True)

def load(path, tag):
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.context.scene.objects if o not in before and o.type == 'MESH']
    for o in new:
        o.name = f"{tag}_{o.name}"
    return new

def bounds(objs):
    mins = Vector((1e9,)*3); maxs = Vector((-1e9,)*3)
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                mins[i] = min(mins[i], w[i]); maxs[i] = max(maxs[i], w[i])
    return mins, maxs

def long_axis(size):
    return max(range(3), key=lambda i: size[i])

env = load(env_path, "ENV")
emin, emax = bounds(env)
esize = emax - emin
ecen = (emin + emax) / 2
ea = long_axis(esize)
# "up" is the axis that is neither the long axis nor the thinnest
order = sorted(range(3), key=lambda i: esize[i])
up = order[1]

gon = load(gon_path, "GON")
gmin, gmax = bounds(gon)
gsize = gmax - gmin
ga = long_axis(gsize)

# ALIGN: the parts are generated independently, so the gondola's long axis is whatever
# Trellis2 happened to produce. Without this the car hangs crosswise under the envelope
# and reads as a detached blob.
if ga != ea:
    import mathutils
    k = [i for i in range(3) if i not in (ga, ea)][0]
    axis = [(1, 0, 0), (0, 1, 0), (0, 0, 1)][k]
    gcen0 = (gmin + gmax) / 2
    R = mathutils.Matrix.Rotation(1.5707963267948966, 4, axis)
    T1 = mathutils.Matrix.Translation(-gcen0)
    T2 = mathutils.Matrix.Translation(gcen0)
    for o in gon:
        o.matrix_world = T2 @ R @ T1 @ o.matrix_world
    bpy.context.view_layer.update()
    gmin, gmax = bounds(gon)
    gsize = gmax - gmin
    ga = long_axis(gsize)
    print("ALIGNED gondola: rotated about axis", k, "-> long axis now", ga)

# normalize the gondola against the envelope's length
target_len = esize[ea] * GONDOLA_LEN_FRAC
scale = target_len / gsize[ga] if gsize[ga] > 0 else 1.0
for o in gon:
    o.scale = (scale, scale, scale)
bpy.context.view_layer.update()

gmin, gmax = bounds(gon)
gcen = (gmin + gmax) / 2
gsize = gmax - gmin

# hang it below the envelope with a real gap
delta = Vector((0, 0, 0))
for i in range(3):
    delta[i] = ecen[i] - gcen[i]
gap = esize[up] * GAP_FRAC
delta[up] = (emin[up] - gap - gmax[up])
for o in gon:
    o.location = o.location + delta
bpy.context.view_layer.update()

# STRUTS. Without them the two parts read as two objects floating near each other rather
# than one ship. A kit recipe would fill this slot with a part; procedural pylons are cheaper
# and always fit, because they are measured from the actual gap after placement.
gmin, gmax = bounds(gon)
strut_r = esize[ea] * 0.013
top = emin[up] + esize[up] * 0.02      # bite slightly into the envelope
bot = gmax[up] - esize[up] * 0.02      # and into the gondola roof
mid = (top + bot) / 2.0
height = abs(top - bot)
gcen2 = (gmin + gmax) / 2
along = [-0.30, 0.30]                  # fore and aft, as a fraction of GONDOLA length
across = [-0.18, 0.18]                 # modest splay, kept inside the gondola roof
third = [i for i in range(3) if i not in (ea, up)][0]
struts = []
for da in along:
    for dc in across:
        loc = [0.0, 0.0, 0.0]
        loc[ea] = gcen2[ea] + gsize[ea] * da     # measure from the GONDOLA, not the envelope
        loc[third] = gcen2[third] + gsize[third] * dc
        loc[up] = mid
        bpy.ops.mesh.primitive_cylinder_add(radius=strut_r, depth=height, location=loc)
        o = bpy.context.active_object
        if up == 0:
            o.rotation_euler = (0, 1.5707963267948966, 0)
        elif up == 1:
            o.rotation_euler = (1.5707963267948966, 0, 0)
        struts.append(o)
print("STRUTS", len(struts), "height=%.4f radius=%.4f" % (height, strut_r))

fmin, fmax = bounds(env + gon)
print("ASSEMBLED long_axis=%d up=%d envelope=%s gondola_scale=%.4f total=%s" % (
    ea, up, tuple(round(v, 3) for v in esize), scale, tuple(round(v, 3) for v in (fmax - fmin))))

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=out_path, export_format='GLB', use_selection=True)
print("SAVED", out_path)
