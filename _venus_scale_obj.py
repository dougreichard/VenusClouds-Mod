"""Scale an .obj in place. Trellis2 normalises meshes to a UNIT CUBE, which is ~580x
smaller than a stock engine hull and ~18x smaller than this mod's own kit ships - so an
unscaled generated ship renders as an invisible speck whatever meshscale says.

Uniform scale touches only `v` lines: `vt` are unitless and `vn` are unchanged by it.

  python scale_obj.py <obj> <target_long_axis>
"""
import sys, shutil

p, target = sys.argv[1], float(sys.argv[2])
lines = open(p, "r", errors="ignore").read().splitlines()

lo = [1e18]*3; hi = [-1e18]*3
for ln in lines:
    if ln.startswith("v "):
        xyz = [float(v) for v in ln.split()[1:4]]
        for i, v in enumerate(xyz):
            lo[i] = min(lo[i], v); hi[i] = max(hi[i], v)
ext = [hi[i]-lo[i] for i in range(3)]
f = target / max(ext)
print("before %s  -> factor %.4f" % ([round(e,3) for e in ext], f))

shutil.copyfile(p, p + ".bak")
out = []
for ln in lines:
    if ln.startswith("v "):
        parts = ln.split()
        out.append("v %.6f %.6f %.6f" % tuple(float(parts[i+1])*f for i in range(3)))
    else:
        out.append(ln)
open(p, "w", newline="\n").write("\n".join(out) + "\n")

lo = [1e18]*3; hi = [-1e18]*3
for ln in out:
    if ln.startswith("v "):
        xyz = [float(v) for v in ln.split()[1:4]]
        for i, v in enumerate(xyz):
            lo[i] = min(lo[i], v); hi[i] = max(hi[i], v)
print("after  %s" % [round(hi[i]-lo[i], 2) for i in range(3)])
