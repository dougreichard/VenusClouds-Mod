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
    # GENERATED parts - prop-farm output, which brings its OWN baked texture rather than
    # indexing a shared atlas. That is fine now the pipeline bakes: a part with no pack
    # atlas keeps the material it arrived with, and the bake resolves everything into one
    # texture set regardless of where each part's colour came from.
    #
    # This is what Phase 3 was for. The Kaiju pack turned out to be two whole-creature FBXs
    # rather than a parts kit, so the Brood cannot be kitbashed from it - but the prop farm
    # already produced exactly the right thing.
    "generated": {
        "unit_scale": 1.0,
        "obj": os.path.join(os.path.dirname(os.path.abspath(__file__)), "_propfarm"),
        "atlas": None,          # brings its own material
        "emissive": None,
    },

    # NOT yet copied into the kit folder - still sitting in E:/tmp, which is a temp
    # directory and can be cleaned out from under us. Pull it from the N: archive
    # (POLYGON_ScifiSpace_SourceFiles.zip) before any Armada recipe depends on it.
    "scifi": {
        "unit_scale": 0.02,
        # CHOSEN BY LOOKING AT THE SWATCHES, not by a mean. Two prior attempts picked an
        # atlas by averaging one part's UVs and both were wrong - the mean hides a
        # high-variance palette, so 04_A scored "dark neutral" (69,67,62) and rendered
        # purple-and-lime, because bright purple and lime average to grey.
        #
        # `_venus_kit_palette.py` now renders the DOMINANT colours a whole recipe actually
        # samples, per candidate. Across those, 02_A is the only variant that is mostly
        # grey, dark maroon, rust and olive with a single cyan accent instead of several.
        # That is a raider; the rest are showroom liveries.
        "faction_atlas": {"armada": "Alts/PolygonSciFiSpace_Texture_02_A.png"},
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
# ARMADA uses 02_B for its Pirates-pack parts specifically because that variant paints the
# BARREL blue-grey (66,81,95) - which read as "wrong" when the whole ship was a boat, but
# reads as painted steel on a raider whose only Pirates part is its envelope. Same
# measurement that once looked like a mistake, now the right answer for a different ship.
FACTION_ATLAS = {
    "kingdom": ("pirates", "Texture_01_C.png"),
    "armada":  ("pirates", "Texture_02_B.png"),
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


# The ARMADA's envelope is a different object entirely: an industrial cylinder, not a
# ship's barrel. A wooden gasbag over a steel warship was the last thing making the Blood
# Hawk read as two unrelated models bolted together - the silhouette was right and the
# MATERIAL was wrong. `SM_Prop_Pipe_Concrete_Huge_01` is a clean 90-face cylinder already
# long on Z, so it costs almost nothing and reads as an armoured gas cell.
ARMADA_ENVELOPE = "construction:SM_Prop_Pipe_Concrete_Huge_01"
_PIPE = (227.0 * 0.02, 227.0 * 0.02, 513.4 * 0.02)     # after the pack's unit_scale


def env_pipe(length, diameter):
    """Scale factors for the Armada's cylindrical envelope, in fleet units."""
    return (diameter / _PIPE[0], diameter / _PIPE[1], length / _PIPE[2])


# THE ARMADA'S LIFT BODY is the pack's long armoured capital hull, not a ship's barrel.
# `SM_Ship_Galactic_Carrier_Armor_01` is 5.3:1 and armour-plated at only 1,996 faces, so it
# reads as an armoured gas cell rather than a wooden cask - the material clash that made
# every earlier Blood Hawk look like two models bolted together.
ARMADA_FLOAT = "SM_Ship_Galactic_Carrier_Armor_01"
_FLOAT_LEN = 16913.0 * 0.02        # after the pack's unit_scale


def armada_floats(length, x, y, z=-0.5):
    """Paired armoured lift bodies, sized by LENGTH (they keep their own proportions)."""
    k = length / _FLOAT_LEN
    return [(ARMADA_FLOAT, (-x, y, z), (0, 0, 0), (k, k, k)),
            (ARMADA_FLOAT, (x, y, z), (0, 0, 0), (k, k, k))]


def pontoons(length, diameter, x, y, z=-0.5):
    """The Armada's paired lift floats, as two part entries.

    Placement is the settled one: LOW and slightly proud of the beam. Fully outboard at
    deck height they compete with the hull for the silhouette; fully tucked underneath they
    disappear. A helper because every raider needs the same relationship and eyeballing it
    per hull is how a fleet stops looking like a fleet.
    """
    return [("pirates:" + ENVELOPE_PART, (-x, y, z), (0, 0, 0), env(length, diameter)),
            ("pirates:" + ENVELOPE_PART, (x, y, z), (0, 0, 0), env(length, diameter))]


def struts(x, y, z=-1.0, scale=0.45):
    """Stubby struts where each float meets the keel."""
    return [("SM_Veh_Part_Wing_011", (-x, y, z), (0, 0, 80), (scale, scale, scale)),
            ("SM_Veh_Part_Wing_011", (x, y, z), (0, 0, 100), (scale, scale, scale))]


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

    # ---- the Armada ---------------------------------------------------------
    #
    # ONE HERO HULL PER CLASS, not one body rescaled four times. The first pass built every
    # raider from SM_Veh_Part_Body_03 at different sizes and the four ships were
    # indistinguishable at a glance - which matters more in play than telling Kingdom from
    # Armada, since the HUD already colours sides. The pack ships 32 finished hulls with
    # genuinely different silhouettes; using them is both better looking and less work.

    "venus_pir_scavenger": {
        "faction": "armada", "pack": "scifi", "art": "VEN_Scavenger",
        "desc": "Scavenger - flat, cheap and fast; an engine with a claw on it",
        "parts": [
            # Stealth_01 is the flattest hull in the pack (1854 x 219 x 1969) and the
            # cheapest at 1,038 faces - a scout should read as a blade, not a brick.
            ("SM_Ship_Stealth_01", (0, 0, 0), (0, 0, 0), (0.30, 0.30, 0.30)),
        ] + armada_floats(13.0, x=3.6, y=-1.6),
    },

    "venus_pir_blacksails": {
        "faction": "armada", "pack": "scifi", "art": "VEN_BlackSails",
        "desc": "Black Sails raider escort - a bomber airframe with grapples",
        "parts": [
            # Bomber_01 is broad and short (3009 x 532 x 2191) - a wide, mean planform
            # that cannot be confused with the scout's blade or the cruiser's spine.
            ("SM_Ship_Bomber_01", (0, 0, 0), (0, 0, 0), (0.32, 0.32, 0.32)),
            ("SM_Prop_Turret_Base_Double_03", (0, 1.0, -1.0), (0, 0, 0), (0.5, 0.5, 0.5)),
        ] + armada_floats(17.0, x=5.4, y=-2.0),
    },

    "venus_pir_bloodhawk": {
        "faction": "armada", "pack": "scifi", "art": "VEN_BloodHawk",
        "desc": "Blood Hawk heavy raider - it closes fast and it does not turn away",
        "parts": [
            # Cruiser_02: a long spined capital hull, 2.2:1, the only Armada ship with a
            # real keel line.
            ("SM_Ship_Cruiser_02", (0, 0, 0), (0, 0, 0), (0.22, 0.22, 0.22)),
            ("SM_Prop_Turret_Base_Double_03", (0, 2.2, 2.0), (0, 0, 0), (0.6, 0.6, 0.6)),
            ("SM_Prop_Turret_Base_Double_03", (0, 2.2, -4.0), (0, 0, 0), (0.6, 0.6, 0.6)),
        ] + armada_floats(24.0, x=6.2, y=-3.0),
    },

    "venus_pir_scrapking": {
        "faction": "armada", "pack": "scifi", "art": "VEN_ScrapKing",
        "desc": "Scrap King armored logistics - what it kills, it eats",
        "parts": [
            # Transport_01: slab-sided and 2.8:1, obviously a hauler rather than a warship.
            ("SM_Ship_Transport_01", (0, 0, 0), (0, 0, 0), (0.085, 0.085, 0.085)),
            # Salvage lashed to the deck. The one place a Pirates part still belongs on an
            # Armada hull - it is LOOT, so it SHOULD look like it came off somebody else.
            ("pirates:SM_Prop_Shipwreck_03", (0, 3.2, -2.0), (0, 16, 0), (0.42, 0.42, 0.42)),
            ("pirates:SM_Prop_Crate_01", (2.2, 3.0, 4.0), (0, 22, 0), (1.5, 1.5, 1.5)),
        ] + armada_floats(26.0, x=7.0, y=-3.6),
    },

    # ---- the Brood ----------------------------------------------------------
    #
    # Neither boats nor spacecraft, which is the whole point - the Brood is the faction a
    # kit cannot build. The Kaiju pack ships two whole creatures rather than parts, so this
    # uses the prop-farm mesh generated earlier: a chitinous carapace with spines and red
    # markings, which is the battle-scene concept art almost exactly.
    #
    # It arrives with its own baked texture instead of a pack atlas, and the bake folds it
    # into one Cosmos texture set like anything else.

    "venus_brd_swarmer": {
        "faction": "brood", "pack": "generated", "art": "VEN_BroodSwarmer",
        "desc": "Brood swarmer - grown, not built; it comes up when the deck is disturbed",
        "parts": [
            ("venus_brood_raider_painted", (0, 0, 0), (0, 0, 0), (9.0, 9.0, 9.0)),
        ],
    },

    # ---- Platforms ----------------------------------------------------------
    #
    # A Venus platform is a DECK ON BUOYANCY HULLS, which is what the schematics draw and
    # what separates a station from a ship here: ships have one envelope and go somewhere,
    # platforms have several and stay. Twin envelopes below, working gear above.
    #
    # Budget discipline matters more here than on ships: SM_Bld_Crane_01 is 8,862 faces on
    # its own - more than a whole station - so the cheap Construction parts do the work
    # (water tower 734, tank 407, fuel tank 567, pipe 90, crane section 150).

    "venus_kdm_harvester": {
        "faction": "kingdom", "pack": "construction", "art": "VEN_HarvestersReach",
        "desc": "Harvester's Reach - refinery modules and arms that strip lifting gas from the deck",
        "parts": [
            # A CATAMARAN, not a raft. The first pass hid the buoyancy hulls under a small
            # deck and the platform read as a water tower on a pallet - the envelopes are
            # the reason it is in the sky and they have to be the biggest thing in the
            # silhouette. Deck spans BETWEEN them at their tops; gear sits on the deck.
            # 6.1 x 6.3 x 2.5 after unit_scale, so these factors give ~20 x 22 and a 1-thick
            # slab. The previous 11x read as an aircraft carrier deck with a toy on it.
            ("SM_Bld_ConcreteFrame_Wall_01", (0, 1.4, 0), (90, 0, 0), (3.3, 3.5, 0.4)),
            # Refinery gear, asymmetric on purpose - a working platform is not a parade,
            # and scaled DOWN so the deck still reads as a deck rather than a plinth.
            ("SM_Bld_WaterTank_01", (-5.0, 3.4, -3.0), (0, 0, 0), (0.7, 0.7, 0.7)),
            ("SM_Prop_Fuel_Tank_01", (4.5, 2.8, 2.0), (0, 0, 0), (1.6, 1.6, 1.6)),
            ("SM_Prop_Fuel_Tank_01", (7.0, 2.8, -1.0), (0, 0, 0), (1.6, 1.6, 1.6)),
            ("SM_Bld_WaterTower_01", (0.5, 3.4, 6.0), (0, 0, 0), (0.8, 0.8, 0.8)),
            ("SM_Prop_Pipe_Concrete_Huge_01", (-1.5, 2.6, 2.0), (0, 20, 0), (0.7, 0.7, 1.6)),
            ("SM_Prop_Crane_Section_01", (-8.0, 3.0, 5.0), (0, 0, 35), (1.0, 1.0, 3.2)),
            # Buoyancy hulls: outboard, large, and with their tops at deck level so they
            # are the first thing read.
            ("pirates:" + ENVELOPE_PART, (-11.0, -0.6, 0), (0, 0, 0), env(34.0, 8.5)),
            ("pirates:" + ENVELOPE_PART, (11.0, -0.6, 0), (0, 0, 0), env(34.0, 8.5)),
        ],
    },

    "venus_civ_skycity": {
        "faction": "guild", "pack": "construction", "art": "VEN_SkyCity",
        "desc": "A free city - neutral by treaty and by necessity; it sells gas to whoever moors",
        "parts": [
            ("SM_Bld_ConcreteFrame_Wall_01", (0, 1.6, 0), (90, 0, 0), (4.4, 4.6, 0.4)),
            # A skyline rather than a refinery: towers and tanks at several heights, so it
            # reads as somewhere people LIVE instead of somewhere gas is cracked.
            ("SM_Bld_WaterTower_01", (-6.0, 4.2, -4.0), (0, 0, 0), (1.1, 1.1, 1.1)),
            ("SM_Bld_WaterTower_01", (5.0, 3.6, 5.0), (0, 0, 0), (0.9, 0.9, 0.9)),
            ("SM_Bld_WaterTank_02", (0, 3.8, 0), (0, 0, 0), (0.8, 0.8, 0.8)),
            ("SM_Bld_WaterTank_01", (8.0, 3.0, -6.0), (0, 0, 0), (0.8, 0.8, 0.8)),
            ("SM_Prop_Elevator_Frame_01", (-3.0, 3.2, 7.5), (0, 0, 0), (1.6, 2.2, 1.6)),
            # FOUR hulls, because a city is heavier than a refinery and the second pair
            # reads as permanence - this thing is not going anywhere.
            ("pirates:" + ENVELOPE_PART, (-11.5, -1.0, -6.0), (0, 0, 0), env(26.0, 7.0)),
            ("pirates:" + ENVELOPE_PART, (11.5, -1.0, -6.0), (0, 0, 0), env(26.0, 7.0)),
            ("pirates:" + ENVELOPE_PART, (-11.5, -1.0, 6.0), (0, 0, 0), env(26.0, 7.0)),
            ("pirates:" + ENVELOPE_PART, (11.5, -1.0, 6.0), (0, 0, 0), env(26.0, 7.0)),
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
    for root_dir, ext in ((p.get("obj"), ".obj"), (p.get("obj"), ".glb"),
                          (p.get("fbx") or p.get("obj"), ".fbx")):
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
    # A pack may declare its own per-faction variants; otherwise its single atlas is used.
    variant = (p.get("faction_atlas") or {}).get(faction) or p.get("atlas")
    diffuse = os.path.join(p["tex"], variant) if variant else None
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
    # Textures are checked PER PART, not per faction. A generated part carries its own
    # baked material and needs no atlas at all - demanding a faction atlas for the whole
    # recipe would reject a perfectly valid Brood hull that has no Synty parts in it.
    for obj_name, _o, _r, _s in r["parts"]:
        pack, name = kit_split_part(obj_name, r["pack"])
        if pack not in PACKS:
            continue
        needs_atlas = bool((PACKS[pack].get("atlas") is not None) or pack == "pirates")
        if not needs_atlas:
            continue
        diffuse, _e = kit_part_textures(pack, r["faction"])
        if diffuse is None:
            problems.append("no diffuse atlas for %s part %s (faction %s)"
                            % (pack, name, r["faction"]))
    return problems


if __name__ == "__main__":
    for name in RECIPES:
        problems = kit_check(name)
        print("%-24s %s" % (name, "OK" if not problems else "; ".join(problems)))
        r = RECIPES[name]
        for obj_name, off, rot, scl in r["parts"]:
            print("    %-38s off=%-16s scale=%s" % (obj_name, off, scl))