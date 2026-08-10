"""Kitbash recipes: each Venus hull as a list of parts from a Synty pack.

WHY RECIPES AND NOT MODELS. Nineteen hulls over one shared kit means the marginal cost of
hull twenty is a recipe, not a generation run - and changing the envelope part once updates
every Kingdom ship. A recipe is also SOURCE-INDEPENDENT: swapping a Synty part for a
generated one later is a one-line change per slot, not a re-layout.

MEASURED FACTS THIS FILE IS BUILT ON (see the mod README for the full survey):

* The Synty boat parts are already **+Z long, +Y up** - exactly Cosmos's convention, so no
  axis correction is needed. (`SM_Veh_Boat_Medium_01_Hull_Pirate` is 5.07 x 4.67 x 14.29.)
* Parts of one boat are **co-registered**: hull, mast, rigging and sails share an origin
  frame and assemble at IDENTITY. Only added parts need an offset.
* The pack's atlases `Texture_01..04` x `_A/_B/_C` are **colour variants of ONE shared UV
  layout** - measured by sampling the hull's own UVs through each and getting plausible
  hull browns from all twelve. So a faction palette is a free choice of atlas variant:
  same meshes, different look, no extra work.
* Cosmos needs **one texture set per ship**, not one object. A hull built from ONE pack
  already satisfies that, because every part indexes the same atlas - no bake, no re-unwrap,
  no join. Multi-object OBJ is fine (`God_Phoenix` ships 16 submeshes; stock `monster2` is
  itself a two-part kitbash).

A part entry is ``(obj_name, (dx, dy, dz), (rx, ry, rz) degrees, (sx, sy, sz))``. Offsets
and scales are in the pack's own units; the hull above is ~14 long, which is the yardstick.
"""

import os

# ---------------------------------------------------------------- packs ----
PACKS = {
    "pirates": {
        "obj": r"E:/o/OneDrive/b/poly-pirate-test/POLYGON_Pirates_Pack_Source_Files/SourceFiles/OBJ",
        "tex": r"E:/o/OneDrive/b/poly-pirate-test/POLYGON_Pirates_Pack_Source_Files/SourceFiles/Textures",
        "emissive": "Texture_Emmisive.png",   # the pack's own spelling
    },
    "scifi": {
        "obj": r"E:/tmp/POLYGON_ScifiSpace_SourceFiles/OBJ",
        "tex": r"E:/tmp/POLYGON_ScifiSpace_SourceFiles/Textures",
        "emissive": "PolygonSciFiSpace_Emissive_01.png",
    },
}

# Faction palette = which colour variant of the shared layout to ship as the diffuse.
# Measured mean hull colour through each: 01_C is the warmest (96,70,57), 02_B the darkest
# (54,48,36). That is the entire difference between a Kingdom brass hull and an Armada one.
FACTION_ATLAS = {
    "kingdom": ("pirates", "Texture_01_C.png"),
    "armada":  ("pirates", "Texture_02_B.png"),
    "guild":   ("pirates", "Texture_03_C.png"),
}

# ------------------------------------------------------------- recipes ----
#
# PHASE 1 SCOPE: one hull, to prove the pipeline end to end in the mock.
#
# The envelope is a PLACEHOLDER and deliberately a pack part rather than a Blender
# primitive: a generated cylinder would carry no atlas UVs and would break the
# one-texture-set rule on its first frame. A barrel stretched along Z reads as a ribbed gas
# envelope surprisingly well, and its wood-slat banding is close to the canvas-over-frame
# look in the concept art. It gets replaced by a generated envelope in Phase 3.

RECIPES = {
    "venus_kdm_valiant": {
        "faction": "kingdom",
        "pack": "pirates",
        # The artfileroot to write. Matches the `venus_art` value _build_ships.py already
        # records for this hull, so `_build_ships.py --venus-art` points the ship data at
        # this kit output with no second naming scheme to keep in sync.
        "art": "VEN_Valiant",
        "desc": "Valiant-class escort airship - gondola, mast and rigging under an envelope",
        "parts": [
            # The boat, at identity - these three are co-registered by the pack.
            ("SM_Veh_Boat_Medium_01_Hull_Pirate", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            ("SM_Veh_Boat_Medium_01_Mast",        (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            ("SM_Veh_Boat_Medium_01_Rigging",     (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            # The envelope, riding above the hull. Barrel is 0.86 x 1.07 x 0.88, so this
            # scales it to roughly 4.1 x 4.7 x 20 - HALF AGAIN the 14.3 hull and slimmer
            # than it is tall, which is the long-cigar proportion the schematics show. The
            # first pass at 5.5/5.0/18 came out as a fat ovoid.
            #
            # The happy accident worth preserving: the boat's own rigging lines run from
            # the hull up to roughly this height, so they read as the envelope's
            # suspension cables. Move the envelope far and that stops working.
            ("SM_Prop_Barrel_01", (0, 9.2, 0), (0, 0, 0), (4.8, 4.4, 23.0)),
        ],
    },
}


def kit_part_path(pack, obj_name):
    """Absolute path to a part's .obj, or None if the pack or part is missing."""
    p = PACKS.get(pack)
    if not p:
        return None
    path = os.path.join(p["obj"], obj_name + ".obj")
    return path if os.path.exists(path) else None


def kit_atlas_path(faction):
    """(diffuse_png, emissive_png) for a faction, or (None, None)."""
    pack_key, tex = FACTION_ATLAS.get(faction, (None, None))
    if pack_key is None:
        return None, None
    pack = PACKS[pack_key]
    diffuse = os.path.join(pack["tex"], tex)
    emissive = os.path.join(pack["tex"], pack["emissive"])
    return (diffuse if os.path.exists(diffuse) else None,
            emissive if os.path.exists(emissive) else None)


def kit_check(name):
    """Every problem with one recipe, as a list of strings. Empty means it will build.

    Checked up front because a missing part is a silent hole in the middle of a ship, and
    an unresolvable art root segfaults the engine - both are much cheaper to catch here.
    """
    r = RECIPES.get(name)
    if r is None:
        return ["no such recipe: " + str(name)]
    problems = []
    for obj_name, _o, _r, _s in r["parts"]:
        if kit_part_path(r["pack"], obj_name) is None:
            problems.append("missing part: " + obj_name)
    diffuse, emissive = kit_atlas_path(r["faction"])
    if diffuse is None:
        problems.append("missing diffuse atlas for faction " + r["faction"])
    if emissive is None:
        problems.append("missing emissive atlas for faction " + r["faction"])
    return problems


if __name__ == "__main__":
    for name in RECIPES:
        problems = kit_check(name)
        print("%-24s %s" % (name, "OK" if not problems else "; ".join(problems)))
        r = RECIPES[name]
        for obj_name, off, rot, scl in r["parts"]:
            print("    %-38s off=%-16s scale=%s" % (obj_name, off, scl))
