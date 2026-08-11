"""glb -> a complete Cosmos ship art set, scaled.

    python make_art.py <in.glb> <out_dir> <ArtName> <target_long_axis> [blender.exe]

Produces the five files the engine and the mock both expect:
    <Name>.obj  _diffuse.png  _specular.png  _emissive.png  _normal.png

Three things this exists to get right, each learned by getting it wrong:
  * the OBJ must carry UVs and normals - trimesh drops both, so the mesh goes through Blender;
  * Trellis2 normalises to a UNIT CUBE, so an unscaled hull is a sub-pixel speck;
  * emissive and normal are optional to loadShipMesh but the webgpu_field overlay asks for
    them, so ship all four maps.
"""
import os, subprocess, sys
import numpy as np
import trimesh
from PIL import Image

src, out_dir, name, target = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
blender = sys.argv[5] if len(sys.argv) > 5 else r"C:/b/stable/blender-5.2.0-lts.fbe6228777e7/blender.exe"
os.makedirs(out_dir, exist_ok=True)
obj = os.path.join(out_dir, name + ".obj")

here = os.path.dirname(os.path.abspath(__file__))
subprocess.run([blender, "-b", "-P", os.path.join(here, "glb2obj_blender.py"), "--", src, obj],
               check=True, capture_output=True)

scene = trimesh.load(src)
mesh = scene.to_geometry() if hasattr(scene, "to_geometry") else scene
mat = getattr(mesh.visual, "material", None)
size = (2048, 2048)

base = getattr(mat, "baseColorTexture", None)
if base is not None:
    base.convert("RGB").save(os.path.join(out_dir, name + "_diffuse.png"))
    size = base.size

mr = getattr(mat, "metallicRoughnessTexture", None)
if mr is not None:                      # glTF packs roughness in G; invert it for specular
    a = np.asarray(mr.convert("RGB")).astype(np.float32)
    Image.fromarray(np.clip(255.0 - a[:, :, 1], 0, 255).astype(np.uint8), "L") \
         .convert("RGB").save(os.path.join(out_dir, name + "_specular.png"))

Image.new("RGB", size, (0, 0, 0)).save(os.path.join(out_dir, name + "_emissive.png"))
Image.new("RGB", size, (128, 128, 255)).save(os.path.join(out_dir, name + "_normal.png"))

lines = open(obj, errors="ignore").read().splitlines()
lo = [1e18]*3; hi = [-1e18]*3
for ln in lines:
    if ln.startswith("v "):
        xyz = [float(v) for v in ln.split()[1:4]]
        for i, v in enumerate(xyz):
            lo[i] = min(lo[i], v); hi[i] = max(hi[i], v)
ext = [hi[i]-lo[i] for i in range(3)]
f = target / max(ext)
out = []
for ln in lines:
    if ln.startswith("v "):
        p = ln.split()
        out.append("v %.6f %.6f %.6f" % tuple(float(p[i+1])*f for i in range(3)))
    else:
        out.append(ln)
open(obj, "w", newline="\n").write("\n".join(out) + "\n")
print("%s: scaled x%.2f -> %s  long=%s" %
      (name, f, [round(e*f, 1) for e in ext], "XYZ"[max(range(3), key=lambda i: ext[i])]))
for fn in sorted(os.listdir(out_dir)):
    if fn.startswith(name):
        print("   ", fn)
