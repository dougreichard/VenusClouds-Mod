"""Build `media/venus_ships.yaml` - the Kingdom and Armada hulls.

WHY A BUILD SCRIPT AND NOT A HAND-WRITTEN YAML. Each entry is a CURRENT stock entry with
only this mod's own deltas applied on top. Hand-copying a shipData entry freezes every
field the mod never meant to touch at whatever value it had the day it was copied - the TNG
mod hit exactly that and had to be rebuilt to fix it. Deriving keeps us current with the
game for free, and it makes the deltas below the honest, readable statement of what this
mod actually changes.

UNIQUE KEYS. Nothing here collides with `data/shipData.yaml`: `venus_kdm_*` / `venus_pir_*`
ADD hulls rather than replacing them, so a mission can field a Golden Vanguard and a TSN
cruiser in the same map and a second mod can be installed alongside this one.

ART IS BORROWED ON PURPOSE, AND THIS IS THE LOAD-BEARING DECISION HERE.
`artfileroot` points at a STOCK mesh that already exists in `data/graphics/ships`, not at
this mod's own `VEN_*` art. That is not laziness, it is a safety requirement: an
unresolvable `artfileroot` SEGFAULTS the engine at render (reproduced 4/4, see
`VisualTestRange/ENGINE_BUG_derived_art_generation.md`), so declaring hulls that point at
art the engine cannot reach would make this mod crash any mission that spawns one. Every
root below was checked against the `.paxmesh` files actually present.

The Venus art root each hull WANTS is recorded as `venus_art` and is not read by the
engine. When mod-carried art works, `--venus-art` swaps them in with one flag and one
rebuild. Until then the silhouettes are chosen to be the closest stock stand-in - a
`cylinder` reads as an envelope far better than a starship does.

STATS EXPRESS THE FICTION. Airships are not starships: the Kingdom flies slow, heavily
built dirigibles with big guns and poor turn rates, and the Armada flies light, fast,
fragile hulls that live by boarding and ramming. That asymmetry is the whole tactical
identity of the setting, so it is declared here rather than left at stock values.
"""
import argparse
import copy
import os

import json
import yaml

STOCK = r"E:/a/Cosmos-dev/data/shipData.yaml"
GFX = r"E:/a/Cosmos-dev/data/graphics/ships"
KIT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media", "ships")

KINGDOM = "Kingdom"
ARMADA = "Armada"
GUILD = "Guild"
BROOD = "Brood"



# The Brood's weapons, because the stock biomech hulls it derives from ship NO
# `hull_port_sets` at all - a swarm that cannot hurt anything, discovered only by reading
# "npc(armed) w/beams 0/2" out of a headless run. The mission's climax was two harmless
# creatures drifting at the players.
#
# SHORT RANGE AND FAST, deliberately. A Kingdom beam reaches 1,680 and an Armada raider
# further; the Brood reaches 900, so it has to close, and closing is the only tactic it
# has. Wide arc because it does not aim - it arrives. No torpedoes: nothing aboard it is
# machinery.
BROOD_PORTS = {
    "beam Primary Beams": [
        {"position": [0.0, 0.0, 120.0], "color": "#7c3",
         "arccolor": "#250", "cycle_time": 12, "damage_coeff": 1.6,
         "range": 900, "arcwidth": 90, "barrel_angle": 0},
        {"position": [-30.0, 0.0, 80.0], "color": "#7c3",
         "arccolor": "#250", "cycle_time": 16, "damage_coeff": 1.2,
         "range": 800, "arcwidth": 80, "barrel_angle": 0},
        {"position": [30.0, 0.0, 80.0], "color": "#7c3",
         "arccolor": "#250", "cycle_time": 16, "damage_coeff": 1.2,
         "range": 800, "arcwidth": 80, "barrel_angle": 0},
    ]
}

# key, base stock key, borrowed art root, the VEN_ root it wants, side, deltas
HULLS = [
    # ---- Kingdom: slow, armored, ceremonial brass ------------------------
    ("venus_kdm_valiant", "tsn_escort", "TSN_Escort", "VEN_Valiant", KINGDOM, dict(
        name="Valiant", roles="ship,warship,patrol,light,defender,airship",
        speed_coeff=0.62, turn_rate=0.75, hullpoints=8,
        long_desc="Valiant-class escort airship. The Kingdom's workhorse: a single "
                  "gas envelope over an armored gondola, slow but nearly unsinkable.")),
    ("venus_kdm_vanguard", "tsn_heavy_cruiser", "TSN_Heavy_Cruiser", "VEN_GoldenVanguard",
     KINGDOM, dict(
        name="Golden Vanguard", roles="ship,warship,patrol,heavy,leader,airship",
        speed_coeff=0.55, turn_rate=0.42, hullpoints=14,
        long_desc="Golden Vanguard-class heavy cruiser. Twin envelopes, paddle-wheel "
                  "drives and a ceremonial deck the Kingdom will not give up.")),
    ("venus_kdm_bulwark", "tsn_battleship", "TSNBattleship", "VEN_ImperialBulwark",
     KINGDOM, dict(
        name="Imperial Bulwark", roles="ship,warship,heavy,leader,airship",
        speed_coeff=0.40, turn_rate=0.24, hullpoints=22,
        long_desc="Imperial Bulwark-class ironclad. A flying fortress of brasswork and "
                  "gear drives. It does not maneuver; it arrives.")),
    ("venus_kdm_thunderbolt", "tsn_destroyer", "TSN_Destroyer", "VEN_Thunderbolt",
     KINGDOM, dict(
        name="Thunderbolt", roles="ship,warship,support,patrol,light,airship",
        speed_coeff=0.70, turn_rate=0.80, hullpoints=7,
        long_desc="Thunderbolt-class rail-cannon gunboat. One enormous mortar bolted to "
                  "the smallest hull that can carry it.")),
    ("venus_kdm_mender", "transport_ship", "transport", "VEN_Mender", KINGDOM, dict(
        name="Mender", roles="ship,civilian,support,transport,airship",
        speed_coeff=0.50, turn_rate=0.55, hullpoints=9,
        long_desc="Mender-class repair tender. Articulated cranes and a workshop deck; "
                  "the reason Kingdom hulls come home at all.")),
    ("venus_kdm_goldharvest", "cargo_ship", "cargo", "VEN_GoldHarvest", KINGDOM, dict(
        name="Gold-Harvest", roles="ship,civilian,cargo,transport,airship",
        speed_coeff=0.45, turn_rate=0.40, hullpoints=10,
        long_desc="Gold-Harvest-class logistics vessel. Bulk lift for the sky cities: "
                  "sulfur, water ice and refined lifting gas.")),
    ("venus_kdm_skiff", "tsn_scout", "TSN_Scout", "VEN_ScoutSkiff", KINGDOM, dict(
        name="Scout Skiff", roles="ship,scout,patrol,support,light,airship",
        speed_coeff=0.95, turn_rate=1.30, hullpoints=4,
        long_desc="Single-rotor scout skiff. Fast, unarmored, and the only thing in the "
                  "Kingdom fleet that can climb out of a storm cell.")),

    # ---- Kingdom platforms ----------------------------------------------
    ("venus_kdm_citadel", "starbase_command", "tsn-big-base", "VEN_SkywardCitadel",
     KINGDOM, dict(
        name="Skyward Citadel", roles="station,fortress,airship",
        long_desc="Skyward Citadel. An aerial fortress on high-altitude buoyancy engines: "
                  "garrisons, cannon emplacements and a repair bay under the deck.")),
    ("venus_kdm_skydome", "starbase_science", "science_station", "VEN_SkyDome", KINGDOM, dict(
        name="Observatory Sky-Dome", roles="station,science,airship",
        long_desc="Observatory Sky-Dome. Celestial and atmospheric sensors above the "
                  "murk - the Kingdom's eyes, and its listening post.")),
    ("venus_kdm_harvester", "starbase_industry", "industry_station", "VEN_HarvestersReach",
     KINGDOM, dict(
        name="Harvester's Reach", roles="station,industry,airship",
        long_desc="Harvester's Reach. Refinery modules and harvesting arms that strip "
                  "lifting gas straight out of the deck.")),
    ("venus_kdm_berth", "starbase_civil", "civil_station", "VEN_MendersBerth", KINGDOM, dict(
        name="Mender's Berth", roles="station,civilian,airship",
        long_desc="Mender's Berth. A fleet logistics platform: dry-dock cradles, "
                  "workshops, and the only hot meal for four hundred miles.")),

    # ---- Armada: fast, fragile, plasma and salvage -----------------------
    ("venus_pir_blacksails", "kralien_cruiser", "kralien_cruiser", "VEN_BlackSails",
     ARMADA, dict(
        name="Black Sails", roles="ship,warship,light,patrol,pirate,airship",
        speed_coeff=1.15, turn_rate=1.25, hullpoints=5,
        long_desc="Black Sails-class raider escort. Patched envelope, oversized plasma "
                  "engines, and grappling gear where the armor should be.")),
    ("venus_pir_bloodhawk", "skaraan_enforcer", "skaraan_enforcer", "VEN_BloodHawk",
     ARMADA, dict(
        name="Blood Hawk", roles="ship,warship,heavy,leader,pirate,airship",
        speed_coeff=1.30, turn_rate=0.95, hullpoints=11,
        long_desc="Blood Hawk-class heavy raider. High-output plasma engines and a "
                  "dreadnought ram - it closes fast and it does not turn away.")),
    ("venus_pir_nighthawk", "skaraan_defiler", "skaraan_defiler", "VEN_Nighthawk",
     ARMADA, dict(
        name="Nighthawk", roles="ship,warship,medium,loner,pirate,airship",
        speed_coeff=1.20, turn_rate=1.05, hullpoints=7,
        long_desc="Nighthawk-class stealth raider. Camouflage panels and a quiet drive; "
                  "in this murk you hear it before the scope finds it.")),
    ("venus_pir_blacktide", "torgoth_behemoth", "Torgoth_Behemoth", "VEN_BlackTide",
     ARMADA, dict(
        name="Black-Tide", roles="ship,warship,heavy,leader,carrier,pirate,airship",
        speed_coeff=0.85, turn_rate=0.35, hullpoints=20,
        long_desc="Black-Tide-class dreadnought. A stolen Kingdom keel grown over with "
                  "salvage plating, a ramming prow, and a hangar full of skiffs.")),
    ("venus_pir_scrapking", "pirate_brigantine", "Brigantine", "VEN_ScrapKing", ARMADA, dict(
        name="Scrap King", roles="ship,pirate,carrier,cargo,airship",
        speed_coeff=0.75, turn_rate=0.50, hullpoints=13,
        long_desc="Scrap King-class armored logistics hull. Recovery cranes and an "
                  "internal smelter: what it kills, it eats.")),
    ("venus_pir_scavenger", "pirate_longbow", "longbow", "VEN_Scavenger", ARMADA, dict(
        name="Scavenger", roles="ship,scout,pirate,light,airship",
        speed_coeff=1.35, turn_rate=1.40, hullpoints=4,
        long_desc="Scavenger-class trolley raider. Barely a hull - an engine, a claw, "
                  "and someone willing to fly it.")),
    ("venus_pir_hub", "starbase_skaraan", "skaraan_station", "VEN_ArmadaHub", ARMADA, dict(
        name="Armada Hub", roles="station,fortress,pirate,airship",
        long_desc="An Armada hub. Plasma turrets on a captured platform, and a market "
                  "below decks that will buy anything with the numbers filed off.")),

    # ---- The Brood: grown, not built -------------------------------------
    #
    # Borrows `biomech` art until its own is in place, because that is the only stock
    # family that is not a ship - and an unresolvable artfileroot segfaults the engine, so
    # the fallback has to be something real.
    ("venus_brd_swarmer", "biomech_a", "Drone1", "VEN_BroodSwarmer", BROOD, dict(
        name="Swarmer", roles="ship,brood,light,airship",
        speed_coeff=1.05, turn_rate=1.45, hullpoints=4,
        hull_port_sets=BROOD_PORTS,
        long_desc="It does not hail, it does not surrender, and nothing aboard it is "
                  "machinery. It comes up when the deck is disturbed.")),
    ("venus_brd_render", "biomech_c", "Drone3", "VEN_BroodRender", BROOD, dict(
        name="Render", roles="ship,brood,medium,leader,airship",
        speed_coeff=0.95, turn_rate=1.10, hullpoints=9,
        hull_port_sets=BROOD_PORTS,
        long_desc="Larger, older, and slower to break off. The Armada has a word for "
                  "these and it is not a word for an animal.")),

    # ---- Neutral: the sky cities everyone needs and nobody owns ----------
    ("venus_civ_skycity", "starbase_civil", "civil_station", "VEN_SkyCity", GUILD, dict(
        name="Free City", roles="station,civilian,neutral,airship",
        long_desc="A free-floating sky city. Neutral by treaty and by necessity: it sells "
                  "lifting gas to whoever lands, and it has outlived three kingdoms.")),
]


def _index(stock):
    out = {}
    for e in stock["#ship-list"]:
        # Keep the FIRST occurrence: get_ship_index keeps the last, which is a known
        # library defect, but the stock file has no duplicates so either is fine here.
        out.setdefault(e.get("key"), e)
    return out


def _have_art():
    return {f[:-8] for f in os.listdir(GFX) if f.endswith(".paxmesh")}


def build(use_venus_art=False):
    stock = yaml.safe_load(open(STOCK, encoding="utf-8"))
    by_key = _index(stock)
    have = _have_art()

    entries, problems = [], []
    for key, base_key, art, venus_art, side, deltas in HULLS:
        base = by_key.get(base_key)
        if base is None:
            problems.append("%s: base key %s not in shipData" % (key, base_key))
            continue
        e = copy.deepcopy(base)
        e["key"] = key
        e["side"] = side
        e["origin"] = side
        # --venus-art is INCREMENTAL and per-hull, not a global switch. A hull only moves
        # to its VEN_* root once that art actually exists in media/ships; the rest keep the
        # stock silhouette. Without this, turning the flag on with a half-built kit points
        # 18 hulls at art that is not there - and an unresolvable artfileroot SEGFAULTS the
        # engine at render (reproduced 4/4). Half a fleet in Venus art is fine; half a
        # fleet crashing is not.
        have_kit = os.path.exists(os.path.join(KIT_DIR, venus_art + ".obj"))
        e["artfileroot"] = venus_art if (use_venus_art and have_kit) else art
        e["venus_art"] = venus_art          # not read by the engine; the swap target
        e.update(deltas)

        if not use_venus_art and art not in have:
            # Fatal if shipped: an unresolvable artfileroot segfaults the engine at render.
            problems.append("%s: borrowed art %r has no .paxmesh - would CRASH" % (key, art))
        entries.append(e)

    return entries, problems


def main():
    ap = argparse.ArgumentParser(description="Build the Venus hull list.")
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--out", default=os.path.join(here, "media", "venus_ships.yaml"))
    ap.add_argument("--venus-art", action="store_true",
                    help="point artfileroot at this mod's own VEN_* art. Only safe once "
                         "mod-carried art works in the engine, or the art is installed "
                         "into data/graphics/ships - otherwise every spawn segfaults.")
    a = ap.parse_args()

    entries, problems = build(a.venus_art)
    for p in problems:
        print("  PROBLEM  " + p)
    if problems and not a.venus_art:
        raise SystemExit("refusing to write a ship list that would crash the engine")

    header = (
        "# GENERATED by _build_ships.py - do not edit by hand.\n"
        "#\n"
        "# Each entry is the CURRENT stock entry for its base hull with only this mod's\n"
        "# deltas applied, so the mod stays current with the game instead of freezing a\n"
        "# year-old copy of every field it never meant to touch.\n"
        "#\n"
        "# UNIQUE KEYS: nothing here collides with data/shipData.yaml.\n"
        "#\n"
        "# artfileroot is a STOCK mesh on purpose. An unresolvable artfileroot segfaults\n"
        "# the engine at render, so until mod-carried art works these hulls borrow a\n"
        "# silhouette. `venus_art` records the art each one wants; the engine ignores it.\n"
        "# Rebuild with --venus-art to swap them over.\n"
    )
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(header)
        # HJSON, NOT BLOCK YAML. The engine parses extra ship data as HJSON
        # (data/shipData.yaml says so in its own header): no block sequences, no
        # whitespace in a key. safe_dump writes exactly those, so the file was
        # REJECTED WHOLE by the engine - `RuntimeError: Found whitespace in your key
        # name ... >>> - 2000` - and not one hull in it ever existed there. Nothing
        # reported it, because the add-on merges library-side too, so the test range,
        # every headless run and every name lookup passed regardless. Measured on
        # engine 1.3.6, 2026-08-15.
        #
        # The .yaml EXTENSION stays: that is the engine's own convention
        # (data/shipData.yaml is HJSON). It is the CONTENT that has to be brace-style.
        # JSON is a subset of HJSON, and `#` header comments above are valid HJSON.
        f.write(json.dumps({"#ship-list": entries}, indent=2,
                           ensure_ascii=True) + chr(10))

    on_kit = sum(1 for e in entries if not str(e["artfileroot"]).startswith(("TSN", "tsn", "skaraan", "kralien", "Torgoth", "Brigantine", "longbow", "transport", "cargo", "civil", "science", "industry", "arvonian")))
    print("  %d hull(s) on kitbashed Venus art; the rest on stock silhouettes" % on_kit)
    kdm = sum(1 for e in entries if e["side"] == KINGDOM)
    arm = sum(1 for e in entries if e["side"] == ARMADA)
    brd = sum(1 for e in entries if e["side"] == BROOD)
    civ = len(entries) - kdm - arm - brd
    print("  wrote %s" % a.out)
    print("  %d hulls: %d Kingdom, %d Armada, %d Brood, %d neutral%s"
          % (len(entries), kdm, arm, brd, civ, "  (VENUS ART)" if a.venus_art else ""))


if __name__ == "__main__":
    main()
