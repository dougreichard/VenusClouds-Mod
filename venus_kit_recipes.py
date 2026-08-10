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
# Packs are read from a LOCAL kit folder, never from OneDrive or the N: share.
#
# The canonical archive is `N:\data_backup\purchased-backupsD-assets\synty` (59 source
# packs), but it is an SMB mount: building off it is slow and depends on the network being
# up. `E:/ai/kits/` holds an extracted copy of just the packs this mod uses, pulled from
# that archive - so provenance is the archive, and the build only ever touches local disk.
#
# A OneDrive path was used first and is deliberately NOT here: sync state is not a build
# dependency anyone wants, and files can be cloud-only placeholders that stall a read.
KIT_ROOT = r"E:/ai/kits"

# PACKS ARE NOT IN THE SAME UNITS, and mixing them without normalising is how a turret
# arrives the size of the ship. Measured: the Pirates medium hull is 14.3 long, while the
# Sci-Fi `SM_Veh_Part_Body_03` is 724 and `SM_Ship_Fighter_Heavy_02` is 1,664 - roughly a
# 30-50x difference. Pirates is the reference (1.0) because the fleet's proportions were
# established there; every other pack declares what to multiply by so a recipe can be
# written in one consistent scale.

PACKS = {
    "pirates": {
        "unit_scale": 1.0,          # the reference scale for the whole fleet
        "obj": KIT_ROOT + "/POLYGON_Pirates_Pack_Source_Files/SourceFiles/OBJ",
        "tex": KIT_ROOT + "/POLYGON_Pirates_Pack_Source_Files/SourceFiles/Textures",
        "emissive": "Texture_Emmisive.png",   # the pack's own spelling
    },
    # Cranes, girders, pipes, tanks - the Mender's workshop gear and the refinery modules
    # on Harvester's Reach. 576 parts.
    "construction": {
        "unit_scale": 0.02,
        "obj": KIT_ROOT + "/POLYGON_Construction_SourceFiles_v3/SourceFiles/OBJ",
        "tex": KIT_ROOT + "/POLYGON_Construction_SourceFiles_v3/SourceFiles/Textures",
        "atlas": "PolygonConstruction_Texture_01_A.png",
        "emissive": None,          # this pack ships no emissive map
    },
    # NOT yet copied into the kit folder - still sitting in E:/tmp, which is a temp
    # directory and can be cleaned out from under us. Pull it from the N: archive
    # (POLYGON_ScifiSpace_SourceFiles.zip) before any Armada recipe depends on it.
    "scifi": {
        "unit_scale": 0.02,
        "obj": KIT_ROOT + "/POLYGON_ScifiSpace_SourceFiles/OBJ",
        "tex": KIT_ROOT + "/POLYGON_ScifiSpace_SourceFiles/Textures",
        "atlas": "PolygonSciFiSpace_Texture_01_A.png",
        "emissive": "PolygonSciFiSpace_Emissive_01.png",
    },
}

# Faction palette = which colour variant of the shared layout to ship as the diffuse.
#
# CHOOSE IT ON THE ENVELOPE, NOT THE HULL. The variants recolour atlas REGIONS
# independently, so a variant picked for its hull colour says nothing about the rest of the
# ship. 02_B was chosen because it is the darkest at the hull's UVs (54,48,36) - and the
# Armada came out with BRIGHT BLUE gasbags, because the barrel's UVs land on a region that
# variant paints blue (66,81,95). The envelope is the biggest single surface on any of
# these ships, so it is what the palette has to be judged on.
#
# Measured at Barrel_03's own UVs:
#   01_C  (133, 97, 89)  warm terracotta   -> Kingdom
#   03_B  ( 90, 76, 72)  dark, desaturated -> Armada: grimier, same hue family, which is
#                                             the fiction - they fly stolen Kingdom hulls
#   04_C  (126,131, 88)  olive/brass       -> Guild
FACTION_ATLAS = {
    "kingdom": ("pirates", "Texture_01_C.png"),
    "armada":  ("pirates", "Texture_03_B.png"),
    "guild":   ("pirates", "Texture_04_C.png"),
}


# ------------------------------------------------------------ envelope ----
# The gas envelope is a stretched barrel. `SM_Prop_Barrel_03` rather than `_01` because the
# two are the same 0.86 x 1.07 x 0.88 shape but land on different atlas regions - measured
# through the Kingdom atlas, _01 is grey (117,114,112) and _03 is warm (133,97,89). The
# first Valiant looked like it had a stone envelope for exactly that reason.
ENVELOPE_PART = "SM_Prop_Barrel_03"
_BARREL = (0.86, 1.07, 0.88)


def env(length, diameter):
    """Barrel scale factors for an envelope of a given length and diameter.

    Written in the units the schematics think in - "a 20-unit envelope 4.5 across" - rather
    than as raw multipliers nobody can picture. Proportion that reads as an airship:
    envelope roughly 1.4x the hull length, and about a third as thick as it is long.
    """
    return (diameter / _BARREL[0], diameter / _BARREL[1], length / _BARREL[2])


def env_height(hull_height, diameter, gap=2.0):
    """How far above the origin the envelope centre sits: clear of the hull, plus a gap."""
    return hull_height * 0.5 + diameter * 0.5 + gap

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
            (ENVELOPE_PART, (0, 9.2, 0), (0, 0, 0), env(20.2, 4.4)),
        ],
    },

    # ---- the rest of the Kingdom -------------------------------------------
    #
    # Same kit, bigger hull, more masts. Envelope length is ~1.4x the hull. Hull lengths
    # are measured, not guessed: rowing 5.4, small 8.5, medium 14.3, large 33.0.

    "venus_kdm_skiff": {
        "faction": "kingdom", "pack": "pirates", "art": "VEN_ScoutSkiff",
        "desc": "Scout skiff - a rowing hull under a small envelope",
        "parts": [
            ("SM_Veh_Boat_Rowing_01_Hull_Pirate", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            # A shrunken medium mast, so there is something the envelope hangs FROM.
            ("SM_Veh_Boat_Medium_01_Mast", (0, -0.2, 0), (0, 0, 0), (0.32, 0.20, 0.34)),
            (ENVELOPE_PART, (0, 2.3, 0), (0, 0, 0), env(7.6, 2.0)),
        ],
    },

    "venus_kdm_thunderbolt": {
        "faction": "kingdom", "pack": "pirates", "art": "VEN_Thunderbolt",
        "desc": "Thunderbolt gunboat - one enormous mortar on the smallest hull that carries it",
        "parts": [
            ("SM_Veh_Boat_Small_01_Hull_Pirate", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            # The mortar, forward and raised - the whole identity of the class.
            ("SM_Prop_Cannon_01", (0, 1.0, 2.2), (0, 0, 0), (1.4, 1.4, 1.4)),
            ("SM_Veh_Boat_Medium_01_Mast", (0, -0.3, 0), (0, 0, 0), (0.45, 0.26, 0.50)),
            ("SM_Veh_Boat_Medium_01_Rigging", (0, -0.3, 0), (0, 0, 0), (0.45, 0.30, 0.50)),
            (ENVELOPE_PART, (0, 3.1, 0), (0, 0, 0), env(11.9, 2.8)),
        ],
    },

    "venus_kdm_vanguard": {
        "faction": "kingdom", "pack": "pirates", "art": "VEN_GoldenVanguard",
        "desc": "Golden Vanguard heavy cruiser - twin envelopes over a large hull",
        "parts": [
            ("SM_Veh_Veh_Boat_Large_01_Hull_Pirate", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            ("SM_Veh_Boat_Large_Mast_01", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            ("SM_Veh_Veh_Boat_Large_01_Rigging", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            # TWIN envelopes, which is what the schematic gives this class and what reads
            # as "heavy cruiser" at a glance rather than "bigger escort".
            (ENVELOPE_PART, (-4.2, 16.0, 0), (0, 0, 0), env(40.0, 7.0)),
            (ENVELOPE_PART, (4.2, 16.0, 0), (0, 0, 0), env(40.0, 7.0)),
        ],
    },

    "venus_kdm_bulwark": {
        "faction": "kingdom", "pack": "pirates", "art": "VEN_ImperialBulwark",
        "desc": "Imperial Bulwark ironclad - it does not maneuver, it arrives",
        "parts": [
            # The BARE warship hull: the dressed one is 14,693 verts alone, which would
            # spend the whole ship's budget before an envelope is added.
            ("SM_Veh_Boat_Warship_01_Hull_Bare", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            ("SM_Veh_Boat_Warship_01_Mast_01", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            ("SM_Veh_Boat_Warship_01_Mast_02", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            ("SM_Veh_Boat_Warship_01_Rigging", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            # 6.5:1 rather than the ~4.6:1 the smaller hulls use. At the same ratio the
            # envelope read as STUBBY here, because it is being judged against a 39.7-long
            # hull instead of a 14-long one - a capital ship needs a longer, leaner gasbag
            # to look like it could lift that much.
            (ENVELOPE_PART, (0, 22.5, 0), (0, 0, 0), env(62.0, 9.5)),
        ],
    },

    # ---- the Armada --------------------------------------------------------
    #
    # SAME PACK, DARK ATLAS. An Armada hull cannot mix in Sci-Fi parts: two packs means two
    # atlases means two texture sets, and Cosmos allows one. It does not need to - the
    # Pirates pack ships `_Pirate` variants of every mast and sail plus three shipwrecks,
    # and the faction reads from the 02_B atlas (54,48,36 against the Kingdom's 96,70,57).
    #
    # That is also honest to the fiction: the Armada flies stolen and salvaged Kingdom
    # hulls, so it SHOULD be the same boats in worse condition.

    "venus_pir_scavenger": {
        "faction": "armada", "pack": "pirates", "art": "VEN_Scavenger",
        "desc": "Scavenger trolley raider - an engine, a claw, and someone willing to fly it",
        "parts": [
            ("SM_Veh_Boat_Rowing_01_Hull_Pirate", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            ("SM_Prop_Cannon_01", (0, 0.7, 1.4), (0, 0, 0), (0.9, 0.9, 0.9)),
            ("SM_Veh_Boat_Medium_01_Mast_Pirate", (0, -0.2, 0), (0, 0, 0), (0.30, 0.18, 0.32)),
            (ENVELOPE_PART, (0, 2.2, 0), (0, 0, 0), env(7.0, 1.8)),
        ],
    },

    "venus_pir_blacksails": {
        "faction": "armada", "pack": "pirates", "art": "VEN_BlackSails",
        "desc": "Black Sails raider escort - patched envelope, grappling gear where armor should be",
        "parts": [
            ("SM_Veh_Boat_Medium_01_Hull_Pirate", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            ("SM_Veh_Boat_Medium_01_Mast_Pirate", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            ("SM_Veh_Boat_Medium_01_Rigging", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            # A narrower envelope than the Kingdom escort of the same hull - the Armada
            # runs its gasbags lean and fast, and it is the silhouette difference a player
            # reads at distance before any colour.
            (ENVELOPE_PART, (0, 8.6, 0), (0, 0, 0), env(21.0, 3.6)),
        ],
    },

    "venus_pir_bloodhawk": {
        "faction": "armada", "pack": "scifi", "art": "VEN_BloodHawk",
        "desc": "Blood Hawk heavy raider - engines and a ram, not a gasbag with guns",
        # THE ARMADA IS NOT A DARKER KINGDOM. An earlier pass built these from the same boat
        # hulls on a dimmer atlas, reasoning that pirates fly stolen ships. That is good
        # fiction and bad silhouette: at any distance the two fleets read as one. The
        # concept art disagrees with the fiction here - its raiders are angular, engine-
        # heavy and spiked, nothing like a boat - and the art wins, because a player has to
        # tell friend from foe in a second.
        #
        # Mixing packs is only possible because the art is BAKED to one texture set now.
        "parts": [
            ("SM_Veh_Part_Body_03", (0, 0, 0), (0, 0, 0), (1.3, 1.3, 1.3)),
            ("SM_Veh_Part_Cockpit_02", (0, 1.2, 3.0), (0, 0, 0), (0.7, 0.7, 0.7)),
            # Oversized engines, mounted low and wide - "high-output plasma engines" is the
            # phrase on the schematic and the thing that should read first.
            ("SM_Veh_Part_Engine_03", (-3.2, -0.6, -6.5), (0, 0, 0), (1.1, 1.1, 1.1)),
            ("SM_Veh_Part_Engine_03", (3.2, -0.6, -6.5), (0, 0, 0), (1.1, 1.1, 1.1)),
            # Wings as swept spikes rather than lift surfaces.
            ("SM_Veh_Part_Wing_04", (-4.0, 0.2, -1.0), (0, 0, -18), (1.2, 1.2, 1.2)),
            ("SM_Veh_Part_Wing_04", (4.0, 0.2, -1.0), (0, 0, 18), (-1.2, 1.2, 1.2)),
            ("SM_Prop_Turret_Base_Double_03", (0, 1.9, -1.5), (0, 0, 0), (0.8, 0.8, 0.8)),
            # A SMALL patched envelope, not a Kingdom gasbag. It still has to fly in an
            # atmosphere, but the Armada makes lift the junior partner to thrust.
            ("pirates:" + ENVELOPE_PART, (0, 4.6, -1.0), (0, 0, 0), env(16.0, 3.0)),
        ],
    },

    "venus_pir_scrapking": {
        "faction": "armada", "pack": "pirates", "art": "VEN_ScrapKing",
        "desc": "Scrap King armored logistics - what it kills, it eats",
        "parts": [
            ("SM_Veh_Veh_Boat_Large_01_Hull_Pirate", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            ("SM_Veh_Boat_Large_Mast_01_Pirate", (0, 0, 0), (0, 0, 0), (1, 1, 1)),
            # Salvage lashed to the deck - the class identity, and the reason to use the
            # wreck props the pack already ships.
            ("SM_Prop_Shipwreck_03", (0, 3.4, -6.0), (0, 14, 0), (0.55, 0.55, 0.55)),
            ("SM_Prop_Crate_01", (2.1, 3.6, 5.0), (0, 20, 0), (1.6, 1.6, 1.6)),
            ("SM_Prop_Barrel_05", (-2.2, 3.6, 7.5), (0, 0, 0), (1.5, 1.5, 1.5)),
            (ENVELOPE_PART, (0, 15.0, 0), (0, 0, 0), env(42.0, 8.5)),
        ],
    },
}


def kit_split_part(name, default_pack):
    """`"scifi:SM_Prop_Turret_01"` -> ("scifi", "SM_Prop_Turret_01").

    A bare name uses the recipe's own pack. Mixing packs in one hull is only possible
    because the art is BAKED to a single texture set - before that, every part had to index
    the same atlas and a hull was locked to one pack.
    """
    if ":" in name:
        pack, obj_name = name.split(":", 1)
        return pack.strip(), obj_name.strip()
    return default_pack, name


def kit_part_path(pack, obj_name):
    """Absolute path to a part, or None if the pack or part is missing.

    Tries .obj then .fbx: the older packs ship both, the newer ones (Kaiju, Mech) ship FBX
    only - and those are the packs with the organic parts this setting still needs.
    """
    p = PACKS.get(pack)
    if not p:
        return None
    for root_dir, ext in ((p.get("obj"), ".obj"), (p.get("fbx") or p.get("obj"), ".fbx")):
        if not root_dir:
            continue
        path = os.path.join(root_dir, obj_name + ext)
        if os.path.exists(path):
            return path
    return None


def kit_unit_scale(pack):
    """Multiplier that brings a pack's units into the fleet's reference scale."""
    return float((PACKS.get(pack) or {}).get("unit_scale", 1.0))


def kit_part_textures(pack, faction):
    """(diffuse, emissive) for a part from `pack`, seen by a ship of `faction`.

    The Pirates pack has faction colour variants; the others have one atlas each, so a
    Construction crane looks the same on a Kingdom tender and an Armada scrapper. That is
    correct - it is the same crane.
    """
    p = PACKS.get(pack)
    if not p:
        return None, None
    if pack == "pirates":
        return kit_atlas_path(faction)
    diffuse = os.path.join(p["tex"], p["atlas"]) if p.get("atlas") else None
    emissive = os.path.join(p["tex"], p["emissive"]) if p.get("emissive") else None
    return (diffuse if diffuse and os.path.exists(diffuse) else None,
            emissive if emissive and os.path.exists(emissive) else None)


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
        pack, name = kit_split_part(obj_name, r["pack"])
        if pack not in PACKS:
            problems.append("unknown pack: " + pack)
        elif kit_part_path(pack, name) is None:
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