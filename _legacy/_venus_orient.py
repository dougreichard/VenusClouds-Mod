"""Orient a finished .glb to the Cosmos convention: +Z long, +Y up.

Do this LAST. Two traps make any earlier attempt unreliable:
  * Blender is Z-up and the glTF exporter converts to Y-up, so an in-Blender rotation does not
    land where you expect in the file.
  * Trellis2MeshTexturing re-orients the mesh, so anything done before texturing is undone.

Operating on the written file with trimesh avoids both: what we measure is what Cosmos reads.
Convention derived from the meshes themselves - longest extent is the hull's length, second
longest is the envelope-over-gondola vertical.

  python orient.py <in.glb> <out.glb>
"""
import sys
import numpy as np
import trimesh

src, dst = sys.argv[1], sys.argv[2]
scene = trimesh.load(src)

# Bake the scene graph down to real vertex data. Measuring scene.geometry[*].bounds reads the
# LOCAL frame and ignores node transforms, and a transform left on the graph does not survive
# export reliably - both of which silently make this a no-op.
mesh = scene.dump(concatenate=True) if hasattr(scene, "dump") else scene

size = mesh.bounds[1] - mesh.bounds[0]
order = np.argsort(size)                              # ascending: smallest, middle, longest
src_x, src_y, src_z = order[0], order[1], order[2]    # -> X, Y(up), Z(long)

P = np.zeros((4, 4)); P[3, 3] = 1.0
P[0, src_x] = 1.0
P[1, src_y] = 1.0
P[2, src_z] = 1.0
if np.linalg.det(P[:3, :3]) < 0:                      # keep it a rotation, never a mirror
    P[0, src_x] = -1.0

print("orient: extents %s -> mapping X<-%s Y<-%s Z<-%s" %
      (tuple(round(float(v), 3) for v in size), "XYZ"[src_x], "XYZ"[src_y], "XYZ"[src_z]))

mesh.apply_transform(P)
mesh.export(dst)

chk = trimesh.load(dst)
chk = chk.dump(concatenate=True) if hasattr(chk, "dump") else chk
e = chk.bounds[1] - chk.bounds[0]
t = getattr(chk.visual.material, "baseColorTexture", None)
print("RESULT extents X=%.3f Y=%.3f Z=%.3f -> long axis %s | faces=%d | baseColor %s" %
      (e[0], e[1], e[2], "XYZ"[int(np.argmax(e))], len(chk.faces), t.size if t else None))
