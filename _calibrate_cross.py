"""Measure the Cosmos skybox cross layout - which face goes in which cell, and at what
rotation - instead of guessing it.

THE TEST. Six of the twelve cells in the 4x3 cross hold faces (measured from `sky1.png`):

        .   TOP   .    .
       L   CENTER  R   FAR
        .   BOT   .    .

Every pair of cells that touch in the IMAGE is a pair of faces that share an edge on the
CUBE. So a correct cross is continuous across all five internal borders: the last pixel row
of TOP is the same view direction as the first pixel row of CENTER, give or take half a
pixel. Compare the border lines and the arrangement with the lowest mismatch is the right
one - orientation becomes a measurement rather than a cubemap tutorial's word.

Validated against skies known to work in Cosmos: `sky1.png` totals ~1, and rotating one of
its faces 90 degrees sends that join from 0.36 to 20. The signal is enormous.

WHAT IT SEARCHES. Two unknowns, not one:

  * WHICH face sits in which cell. The first version of the generator took A28's prose
    ("front on the top row, then left up right down across the middle, back on the bottom")
    literally and scored 317. Prose about somebody else's tool is not a measurement.
  * WHAT ORIENTATION each needs - one of eight dihedral transforms (four rotations, each
    optionally mirrored), because an unfolding can join edges that run opposite ways.

720 assignments x a greedy orientation solve each. The geometry makes the greedy part
exact: fix CENTER, match its four neighbors against it, then match FAR against R.
"""
import argparse
import itertools
import os

import numpy as np
from PIL import Image

import _gen_skybox as G

CELLS = {"TOP": (0, 1), "L": (1, 0), "CENTER": (1, 1), "R": (1, 2), "FAR": (1, 3),
         "BOT": (2, 1)}

# (cell A, edge of A, cell B, edge of B) - "t"/"b"/"l"/"r"
JOINS = [
    ("TOP", "b", "CENTER", "t"),
    ("L", "r", "CENTER", "l"),
    ("CENTER", "r", "R", "l"),
    ("R", "r", "FAR", "l"),
    ("CENTER", "b", "BOT", "t"),
]

FACES = ("front", "back", "left", "right", "up", "down")
OPS = [(k, m) for k in range(4) for m in (False, True)]


def apply_op(img, op):
    k, m = op
    out = np.rot90(img, k)
    return out[:, ::-1] if m else out


def edge(img, which):
    return {"t": img[0, :], "b": img[-1, :], "l": img[:, 0], "r": img[:, -1]}[which]


def mismatch(a, b):
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    return float(min(np.abs(a - b).mean(), np.abs(a - b[::-1]).mean()))


def score_cells(cell_img):
    detail = [(ca + "|" + cb, mismatch(edge(cell_img[ca], ea), edge(cell_img[cb], eb)))
              for ca, ea, cb, eb in JOINS]
    return sum(d[1] for d in detail), detail


def solve_ops(cell_img, center_op=(0, False)):
    """Orientation per cell that makes every join continuous, for a given CENTER rotation.

    CENTER'S ROTATION IS NOT FREE, which is the trap that cost a regeneration here. It is
    tempting to pin it at identity because a sky has no landmark - but rotating CENTER
    changes WHICH of its edges faces the TOP cell, and the cell assignment is fixed. So the
    caller sweeps all eight and keeps the best; only then is the answer real.
    """
    cell_img = dict(cell_img)
    cell_img["CENTER"] = apply_op(cell_img["CENTER"], center_op)
    ops = {"CENTER": center_op}
    for ca, ea, cb, eb in JOINS:
        if cb == "CENTER":
            other, e_other, e_center = ca, ea, eb
        elif ca == "CENTER":
            other, e_other, e_center = cb, eb, ea
        else:
            continue
        base = edge(cell_img["CENTER"], e_center)
        best = min(OPS, key=lambda o: mismatch(edge(apply_op(cell_img[other], o), e_other),
                                               base))
        ops[other] = best
    r = apply_op(cell_img["R"], ops["R"])
    ops["FAR"] = min(OPS, key=lambda o: mismatch(edge(r, "r"),
                                                 edge(apply_op(cell_img["FAR"], o), "l")))
    return ops


def check_geometry(n=64):
    """Assert the cube is a genuine unfolding: handedness, and ALL TWELVE edges.

    THIS IS THE CHECK THAT WAS MISSING. The border score below only looks at the five joins
    the cross image happens to expose; the other seven cube edges are cut by the unfolding
    and were never tested. A fitted set of per-face rotations scored 0.59 on the border test
    - better than sky1.png - and still seamed in game, because three of its faces were
    MIRRORED and the seven unexamined edges tore.

    Pure geometry, no pixels: two faces that share a cube edge must map their shared border
    to the SAME set of 3D directions. If they do for all twelve pairs, no sky built on these
    frames can seam, whatever the shading does.
    """
    import numpy as np

    frames = {f: tuple(np.array(x, np.float32) for x in fr)
              for f, fr in G.CELL_FRAMES.items()}

    print("HANDEDNESS - every face must satisfy cross(r, d) == -n, or it is mirrored:")
    ok = True
    for f, (nn, r, d) in frames.items():
        good = np.allclose(np.cross(r, d), -nn)
        ok &= bool(good)
        print("    %-6s %s" % (f, "ok" if good else "MIRRORED - this face will seam"))

    def border(f, which):
        nn, r, d = frames[f]
        t = np.linspace(-1, 1, n, dtype=np.float32)
        if which in ("t", "b"):
            v = -1.0 if which == "t" else 1.0
            vec = nn + t[:, None] * r + v * d
        else:
            u = -1.0 if which == "l" else 1.0
            vec = nn + u * r + t[:, None] * d
        return vec / np.linalg.norm(vec, axis=-1, keepdims=True)

    print()
    print("TWELVE CUBE EDGES - each adjacent pair must share a border exactly:")
    faces = list(frames)
    edges = 0
    for a, b in itertools.combinations(faces, 2):
        na, nb = frames[a][0], frames[b][0]
        if abs(float(np.dot(na, nb))) > 1e-6:      # opposite or same face: not adjacent
            continue
        edges += 1
        best = None
        for ea in "tblr":
            for eb in "tblr":
                pa, pb = border(a, ea), border(b, eb)
                m = min(float(np.abs(pa - pb).max()),
                        float(np.abs(pa - pb[::-1]).max()))
                if best is None or m < best[0]:
                    best = (m, ea, eb)
        good = best[0] < 1e-5
        ok &= good
        print("    %-6s %-6s  %s edge %s/%s  max dev %.2e" % (
            a, b, "ok  " if good else "TORN", best[1], best[2], best[0]))
    print()
    print("  %d edges checked - %s" % (edges, "ALL CONSISTENT" if ok else "FAILED"))
    return ok


def roundtrip(path, variant, width=512):
    """Sample the SHIPPED cross the way a renderer does, and compare to the sky it encodes.

    The end-to-end check. `--geometry` proves the frames are consistent and the border score
    proves five joins line up; this reads the actual PNG back through the inverse of the
    projection and compares every direction on the sphere against `shade()` directly. If the
    cross encodes the sky correctly, the two agree everywhere - including across the seven
    edges no other check here can see.
    """
    import numpy as np

    cells = split_cross(path)
    face_px = next(iter(cells.values())).shape[0]
    frames = {f: tuple(np.array(x, np.float32) for x in fr)
              for f, fr in G.CELL_FRAMES.items()}

    height = width // 2
    lon = (np.arange(width, dtype=np.float32) + 0.5) / width * 2 * np.pi - np.pi
    lat = np.pi / 2 - (np.arange(height, dtype=np.float32) + 0.5) / height * np.pi
    lo, la = np.meshgrid(lon, lat)
    d = np.stack([np.cos(la) * np.sin(lo), np.sin(la), np.cos(la) * np.cos(lo)], -1
                 ).astype(np.float32)

    got = np.zeros(d.shape, np.float32)
    cell_of = {"up": "CENTER", "front": "TOP", "left": "L", "right": "R",
               "down": "FAR", "back": "BOT"}
    for face, (n, r, dv) in frames.items():
        dot = d @ n
        u = (d @ r) / np.where(np.abs(dot) < 1e-9, 1e-9, dot)
        v = (d @ dv) / np.where(np.abs(dot) < 1e-9, 1e-9, dot)
        # This face owns the direction when it is the one being looked at, inside its square.
        own = (dot > 0) & (np.abs(u) <= 1.0000001) & (np.abs(v) <= 1.0000001)
        px = np.clip(((u + 1) / 2 * face_px).astype(int), 0, face_px - 1)
        py = np.clip(((v + 1) / 2 * face_px).astype(int), 0, face_px - 1)
        img = cells[cell_of[face]]
        got[own] = img[py[own], px[own]]

    want = G.shade(d, G.VARIANTS[variant][1]).astype(np.float32)
    diff = np.abs(got - want)
    print("  %-24s mean %6.3f  p99 %6.3f  max %6.1f"
          % (os.path.basename(path), diff.mean(), np.percentile(diff, 99), diff.max()))
    return float(diff.mean())


def split_cross(path):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    fw, fh = W // 4, H // 3
    a = np.asarray(im, np.float32)
    return {cell: a[r * fh:(r + 1) * fh, c * fw:(c + 1) * fw]
            for cell, (r, c) in CELLS.items()}


def report(name, cell_img):
    total, detail = score_cells(cell_img)
    print("  %-24s total %8.2f   %s" % (
        name, total, "  ".join("%s %6.2f" % (k, v) for k, v in detail)))
    return total


# MEASURED from a working Cosmos sky, by matching each cell of `a28_sb00.png` against the
# Artemis 2.8 source faces it was built from (E:/a/a28/art/sb00). Every cell identified with
# a score of 0.008-0.014 against a next-best of 0.5-0.86 - not a close call. This is the
# authority; the continuity search below only settles ROTATION.
AUTHORITATIVE = {"TOP": "front", "L": "left", "CENTER": "up",
                 "R": "right", "FAR": "down", "BOT": "back"}


def search(faces, assign=None):
    """Orientations for the known assignment, sweeping CENTER's own rotation.

    Pass assign=None to also search all 720 assignments - useful to confirm the
    authoritative one is at least competitive, but it cannot BEAT it: a sky that is nearly
    symmetric in longitude makes several assignments near-degenerate, which is exactly how
    the first attempt at this talked itself into the wrong one.
    """
    candidates = ([assign] if assign else
                  [dict(zip(("TOP", "L", "CENTER", "R", "FAR", "BOT"), p))
                   for p in itertools.permutations(FACES)])
    results = []
    for a in candidates:
        cell_img = {c: faces[a[c]] for c in CELLS}
        for center_op in OPS:
            ops = solve_ops(cell_img, center_op)
            fixed = {c: apply_op(cell_img[c], ops[c]) for c in CELLS}
            total, _ = score_cells(fixed)
            results.append((total, a, ops))
    results.sort(key=lambda r: r[0])
    return results


def main():
    ap = argparse.ArgumentParser(description="Measure the cross layout.")
    ap.add_argument("--ref", action="append", default=[])
    ap.add_argument("--face", type=int, default=192)
    ap.add_argument("--variant", default="venus_sky_midday")
    ap.add_argument("--roundtrip", default=None, metavar="PNG",
                    help="sample a shipped cross back through the inverse projection and "
                         "compare to the sky it encodes - the end-to-end check")
    ap.add_argument("--geometry", action="store_true",
                    help="assert handedness and all twelve cube edges - the check the "
                         "border score cannot make")
    ap.add_argument("--verify", action="append", default=[],
                    help="score a GENERATED cross png - the end-to-end check, since it "
                         "reads what actually ships rather than a model of it")
    a = ap.parse_args()

    if a.roundtrip:
        print("ROUND TRIP - shipped cross decoded and compared against shade():")
        m = roundtrip(a.roundtrip, a.variant)
        print()
        print("  mean under ~1.0 means the cross encodes the sky; a torn edge shows up as "
              "a large max")
        raise SystemExit(0 if m < 2.0 else 1)

    if a.geometry:
        raise SystemExit(0 if check_geometry() else 1)

    if a.verify:
        print("VERIFY - shipped crosses, scored the same way as the references:")
        worst = 0.0
        for p in a.verify:
            worst = max(worst, report(os.path.basename(p), split_cross(p)))
        print()
        print("  worst %.2f - compare with sky1.png at 1.01 and a scrambled face at 21"
              % worst)
        return

    if a.ref:
        print("REFERENCE SKIES - a working cross scores LOW on every join:")
        for p in a.ref:
            cells = split_cross(p)
            report(os.path.basename(p), cells)
            scrambled = dict(cells)
            scrambled["TOP"] = apply_op(cells["TOP"], (1, False))
            report("  ^ TOP rotated 90 (control)", scrambled)
        print()

    p = G.VARIANTS[a.variant][1]
    faces = {f: G.shade(G._face_dirs(f, a.face), p).astype(np.float32) for f in FACES}

    print("SOLVE - authoritative assignment, sweeping CENTER's rotation:")
    results = search(faces, AUTHORITATIVE)
    total, assign, ops = results[0]
    print("  total %8.2f  (runner-up %.2f)" % (total, results[1][0]))
    for cell in ("TOP", "L", "CENTER", "R", "FAR", "BOT"):
        k, m = ops[cell]
        print("      %-7s %-6s rot90=%d mirror=%s" % (cell, assign[cell], k, m))
    print()
    print("  paste into _gen_skybox.FACE_OPS:")
    print("    FACE_OPS = {" + ", ".join(
        '"%s": (%d, %s)' % (assign[c], ops[c][0], ops[c][1])
        for c in ("TOP", "L", "CENTER", "R", "FAR", "BOT")) + "}")


if __name__ == "__main__":
    main()
