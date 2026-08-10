"""Build Cosmos ship art from kitbash recipes.

    python _venus_kit_bake.py [name ...] [--out DIR]

For each recipe: validate it, drive headless Blender to place and export the mesh, then lay
down the four maps the engine expects. Output is a complete art set in `media/ships/`:

    <root>.obj  <root>_diffuse.png  <root>_normal.png  <root>_specular.png  <root>_emissive.png

WHY THE TEXTURES ARE A COPY AND NOT A BAKE. Cosmos requires ONE texture set per ship, and a
single-atlas Synty pack already gives every part UVs into the same atlas - so the atlas IS
the diffuse map. No UV re-unwrap, no atlas packing, no bake. This is the step the first
draft of the plan expected to be hardest, and the pack structure removes it.

`_normal` and `_specular` are SYNTHESIZED flat because the pack ships neither. A flat normal
(128,128,255) is "no perturbation" and a mid-grey specular is a uniform, mild highlight -
both are honest neutral defaults rather than invented detail. The engine wants the files to
exist; it does not want us to make up surface detail the artist never authored.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import venus_kit_recipes as KIT     # noqa: E402

BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
BLENDER_SCRIPT = os.path.join(HERE, "_venus_kit_blender.py")

# Stock Cosmos hulls measured across all 201 .obj: 1,790-7,784 faces. Over this and the
# hull is heavier than anything the game ships, which is the point at which to decimate.
FACE_BUDGET = 7800


def _flat_png(path, rgb, size=512):
    from PIL import Image
    Image.new("RGB", (size, size), rgb).save(path)


def bake(name, out_dir):
    problems = KIT.kit_check(name)
    if problems:
        print("  %-24s REFUSING: %s" % (name, "; ".join(problems)))
        return False

    recipe = KIT.RECIPES[name]
    parts = []
    for obj_name, off, rot, scl in recipe["parts"]:
        parts.append({"path": KIT.kit_part_path(recipe["pack"], obj_name).replace("\\", "/"),
                      "offset": list(off), "rot": list(rot), "scale": list(scl)})

    os.makedirs(out_dir, exist_ok=True)
    job = os.path.join(out_dir, "_" + name + "_job.json")
    with open(job, "w", encoding="utf-8") as f:
        json.dump({"parts": parts}, f, indent=2)

    art = recipe.get("art", name)
    out_obj = os.path.join(out_dir, art + ".obj")
    proc = subprocess.run([BLENDER, "--background", "--python", BLENDER_SCRIPT,
                           "--", job, out_obj, str(FACE_BUDGET)],
                          capture_output=True, text=True)
    for line in (proc.stdout or "").splitlines():
        if line.startswith("KIT:"):
            print("    " + line)
    if not os.path.exists(out_obj):
        print("  %-24s FAILED - no mesh written" % name)
        print((proc.stdout or "")[-800:])
        print((proc.stderr or "")[-800:])
        return False
    os.remove(job)

    # --- the four maps -----------------------------------------------------
    diffuse, emissive = KIT.kit_atlas_path(recipe["faction"])
    shutil.copyfile(diffuse, os.path.join(out_dir, art + "_diffuse.png"))
    shutil.copyfile(emissive, os.path.join(out_dir, art + "_emissive.png"))
    _flat_png(os.path.join(out_dir, art + "_normal.png"), (128, 128, 255))
    _flat_png(os.path.join(out_dir, art + "_specular.png"), (60, 60, 60))

    # --- report against the stock budget -----------------------------------
    faces = sum(1 for line in open(out_obj, encoding="utf-8", errors="ignore")
                if line.startswith("f "))
    objs = sum(1 for line in open(out_obj, encoding="utf-8", errors="ignore")
               if line.startswith("o "))
    flag = "" if faces <= FACE_BUDGET else "  OVER BUDGET - needs decimation"
    print("  %-24s %d objects, %d faces (stock 1790-7784)%s" % (name, objs, faces, flag))
    return True


def main():
    ap = argparse.ArgumentParser(description="Build ship art from kitbash recipes.")
    ap.add_argument("names", nargs="*", help="recipe names (default: all)")
    ap.add_argument("--out", default=os.path.join(HERE, "media", "ships"))
    # The MOCK serves art from the mission folder and the missions root only
    # (mission_runner passes static_roots=[mission_folder, missions_root]), so it cannot
    # reach into the unpacked media pack. Mirroring into <mission>/ships is what puts a
    # freshly built hull in front of the browser without a rebuild-and-repack cycle.
    ap.add_argument("--mirror", default=None, metavar="MISSION_DIR",
                    help="also copy the art into MISSION_DIR/ships so the mock can serve it")
    a = ap.parse_args()

    names = a.names or list(KIT.RECIPES)
    ok = 0
    for n in names:
        if bake(n, a.out):
            ok += 1
            if a.mirror:
                dst = os.path.join(a.mirror, "ships")
                os.makedirs(dst, exist_ok=True)
                art = KIT.RECIPES[n].get("art", n)
                for suffix in (".obj", "_diffuse.png", "_normal.png",
                               "_specular.png", "_emissive.png"):
                    src = os.path.join(a.out, art + suffix)
                    if os.path.exists(src):
                        shutil.copyfile(src, os.path.join(dst, art + suffix))
                print("    mirrored %s -> %s" % (art, dst))
    print("built %d/%d into %s" % (ok, len(names), a.out))
    return 0 if ok == len(names) else 1


if __name__ == "__main__":
    raise SystemExit(main())
