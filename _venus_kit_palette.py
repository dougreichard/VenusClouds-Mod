"""Score a recipe's palette against every candidate atlas, using ALL of its parts.

WHY THIS EXISTS. Picking an atlas by sampling ONE part's UVs has now produced two wrong
answers: the Kingdom envelope came out stone-grey because the choice was measured on the
hull, and the Armada came out purple-and-lime because the choice was measured on the body.
A ship samples the atlas through every part it is made of, so that is what has to be
measured - each part's UVs, weighted by how much of the ship it actually is.

    python _venus_kit_palette.py <recipe> [pack]
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import venus_kit_recipes as KIT     # noqa: E402


def _part_uv_and_weight(path):
    """UVs of a part, plus a weight = its triangle count (its share of the ship)."""
    uv, faces = [], 0
    for line in open(path, encoding="utf-8", errors="ignore"):
        if line.startswith("vt "):
            q = line.split()
            uv.append((float(q[1]), float(q[2])))
        elif line.startswith("f "):
            faces += 1
    return np.array(uv, np.float32) if uv else None, max(faces, 1)


def probe(recipe_name, pack_filter=None):
    r = KIT.RECIPES[recipe_name]
    samples = []          # (uv array, weight)
    for obj_name, _o, _rr, _s in r["parts"]:
        pack, part = KIT.kit_split_part(obj_name, r["pack"])
        if pack_filter and pack != pack_filter:
            continue
        path = KIT.kit_part_path(pack, part)
        if not path or not path.lower().endswith(".obj"):
            continue
        uv, w = _part_uv_and_weight(path)
        if uv is not None and len(uv):
            samples.append((uv, w))
    if not samples:
        print("no sampleable parts")
        return

    pack_key = pack_filter or r["pack"]
    texdir = KIT.PACKS[pack_key]["tex"]
    cands = []
    for root, _d, files in os.walk(texdir):
        for f in files:
            if f.lower().endswith(".png") and "emissive" not in f.lower() \
               and "mask" not in f.lower() and "texture" in f.lower():
                cands.append(os.path.join(root, f))

    print("%s - %d part(s) sampled, %d candidate atlases" % (recipe_name, len(samples), len(cands)))
    rows = []
    for p in sorted(cands):
        im = Image.open(p).convert("RGB")
        W, H = im.size
        a = np.asarray(im)
        acc, tot = np.zeros(3), 0
        for uv, w in samples:
            x = np.clip((uv[:, 0] * W).astype(int), 0, W - 1)
            y = np.clip(((1 - uv[:, 1]) * H).astype(int), 0, H - 1)
            acc += a[y, x].mean(axis=0) * w
            tot += w
        c = acc / tot
        lum = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
        sat = float(c.max() - c.min())
        rows.append((lum, sat, os.path.basename(p), c))
    for lum, sat, n, c in sorted(rows):
        print("  %-44s rgb(%3.0f,%3.0f,%3.0f)  lum %5.1f  sat %5.1f" % (n, *c, lum, sat))


if __name__ == "__main__":
    probe(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
