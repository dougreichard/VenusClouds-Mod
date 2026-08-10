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
BAKE_SCRIPT = os.path.join(HERE, "_venus_kit_bake_blender.py")

# Stock Cosmos hulls measured across all 201 .obj: 1,790-7,784 faces. Over this and the
# hull is heavier than anything the game ships, which is the point at which to decimate.
FACE_BUDGET = 7800


def _flat_png(path, rgb, size=512):
    from PIL import Image
    Image.new("RGB", (size, size), rgb).save(path)


def _specular_from_diffuse(diffuse_path, out_path, gain=0.45):
    """A specular map derived from the baked diffuse.

    No Synty pack ships a specular map, so there is nothing authored to bake. Luminance is
    a reasonable stand-in - painted metal trim reads brighter than canvas or wood, and it
    is at least DERIVED from the ship rather than a flat grey guess. Damped, because a
    straight luminance copy makes everything shiny.
    """
    from PIL import Image, ImageEnhance
    if not os.path.exists(diffuse_path):
        return _flat_png(out_path, (60, 60, 60))
    im = Image.open(diffuse_path).convert("L")
    im = ImageEnhance.Contrast(im).enhance(1.3).point(lambda v: int(v * gain))
    im.convert("RGB").save(out_path)


def bake(name, out_dir, bake_textures=True, tex_size=1024):
    problems = KIT.kit_check(name)
    if problems:
        print("  %-24s REFUSING: %s" % (name, "; ".join(problems)))
        return False

    recipe = KIT.RECIPES[name]
    faction = recipe["faction"]
    parts = []
    for obj_name, off, rot, scl in recipe["parts"]:
        pack, part_name = KIT.kit_split_part(obj_name, recipe["pack"])
        diffuse, emissive = KIT.kit_part_textures(pack, faction)
        u = KIT.kit_unit_scale(pack)
        scl = tuple(v * u for v in scl)
        parts.append({"path": KIT.kit_part_path(pack, part_name).replace("\\", "/"),
                      "diffuse": (diffuse or "").replace("\\", "/"),
                      "emissive": (emissive or "").replace("\\", "/"),
                      "offset": list(off), "rot": list(rot), "scale": list(scl)})

    os.makedirs(out_dir, exist_ok=True)
    job = os.path.join(out_dir, "_" + name + "_job.json")
    with open(job, "w", encoding="utf-8") as f:
        json.dump({"parts": parts}, f, indent=2)

    art = recipe.get("art", name)
    out_obj = os.path.join(out_dir, art + ".obj")
    script = BAKE_SCRIPT if bake_textures else BLENDER_SCRIPT
    cmd = [BLENDER, "--background", "--python", script, "--", job, out_obj, str(FACE_BUDGET)]
    if bake_textures:
        cmd.append(str(tex_size))
    proc = subprocess.run(cmd, capture_output=True, text=True)
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
    if bake_textures:
        # diffuse / emissive / normal came out of the bake. Only specular is left, and no
        # pack ships one - so it is DERIVED from the baked diffuse (luminance, damped)
        # rather than invented as a flat grey. Honest approximation, labelled as such.
        _specular_from_diffuse(os.path.join(out_dir, art + "_diffuse.png"),
                               os.path.join(out_dir, art + "_specular.png"))
    else:
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
    ap.add_argument("--no-bake", action="store_true",
                    help="skip the texture bake and copy the pack atlas instead. Only valid "
                         "when every part of a hull comes from ONE pack.")
    ap.add_argument("--tex", type=int, default=1024, help="baked map size (default 1024)")
    ap.add_argument("--mirror", default=None, metavar="MISSION_DIR",
                    help="also copy the art into MISSION_DIR/ships so the mock can serve it")
    a = ap.parse_args()

    names = a.names or list(KIT.RECIPES)
    ok = 0
    for n in names:
        if bake(n, a.out, bake_textures=not a.no_bake, tex_size=a.tex):
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
