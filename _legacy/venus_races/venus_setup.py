# Helpers for the Venus Clouds add-on.
#
# Everything is `venus_`-prefixed on purpose: a .mastlib's .py files are exec'd into one
# shared namespace and every function in them becomes a MAST GLOBAL, so an unprefixed name
# collides with any .mast variable of the same name anywhere in the story. A helper called
# `_ship` in the TNG pack took down a whole run against LM's standard_consoles.mast, which
# assigns to `_ship`.

VENUS_FACTIONS = ("Kingdom", "Armada", "Guild")   # playable; Brood is NPC-only

# The one hull the library is asked about to decide whether the merge already happened.
VENUS_PROBE_KEY = "venus_kdm_valiant"


def venus_register_races():
    """Add the Venus factions to PLAYABLE_RACES / NPC_RACES, keeping what is already there.

    ADD rather than replace, so this mod can sit beside LM's own races and a mission can
    still field a TSN cruiser. A pure Venus game is then a mission SETTING - name only these
    factions - rather than something installing a mastlib does to you.

    `settings_add_defaults` cannot do this: it only fills MISSING keys, and both of these
    always have a value. `settings_get_defaults()` returns the live cached dict, so this
    edits it in place. Must run before anything reads those settings.
    """
    from sbs_utils.procedural.settings import settings_get_defaults
    settings = settings_get_defaults()
    added = []
    # The Guild is a station-only faction - neutral sky cities - so it is playable (someone
    # will want a free-trader campaign) but never an NPC fleet ladder.
    #
    # The Brood is the mirror image: an NPC race and NOT playable. It has no consoles, no
    # doctrine and nothing to talk to. Leaving it out of NPC_RACES silently drops its fleet
    # ladder at load - the swarm still spawns, but as whatever stock race the caller named,
    # which is exactly the bug this gate is meant to prevent.
    for key, wanted in (("PLAYABLE_RACES", VENUS_FACTIONS),
                        ("NPC_RACES", ("Kingdom", "Armada", "Brood"))):
        raw = settings.get(key) or ""
        if not isinstance(raw, str):
            raw = ",".join(str(x) for x in raw)
        have = {r.strip().lower() for r in raw.split(",") if r.strip()}
        new = [f for f in wanted if f.lower() not in have]
        if new:
            settings[key] = (raw + ", " if raw.strip() else "") + ", ".join(new)
            added += new
    return added


def venus_safe_status(text):
    """Make a status string safe to hand back to MAST.

    MAST re-runs every assigned string through f-string formatting, so a `{` anywhere in it
    is compiled as an expression - and an exception message quoting YAML syntax is exactly
    the shape that blows up, reported against the CALLER's line rather than here.
    """
    text = str(text).replace("{", "(").replace("}", ")")
    return text if len(text) <= 300 else text[:297] + "..."


def venus_declare_ships(ships_file=None):
    """Give the hulls to the ENGINE and to the library, without writing a file.

    THROUGH `ship_data.add_extra`, NEVER `sbs.add_extra_ship_data` DIRECTLY.

    `create_new_sim()` REBUILDS the engine's ship table and drops everything registered
    before it. `sim_create()` compensates by replaying afterwards - but `extra_replay()`
    can only replay files it has a RECORD of, and the only thing that records one is
    `add_extra`. This add-on declares at story load, always before the first map calls
    `sim_create()`, so calling the engine raw meant the hulls were registered and then
    thrown away with nothing reporting it: the LIBRARY kept every stat, so headless runs,
    name lookups, pickers and lint all said the hulls were there while the engine had none
    of them. It surfaced as a spawn dying inside the engine with `bad allocation`, minutes
    later, against a line that never mentions ship data. Measured on engine 1.3.6-A,
    2026-08-21, on the sibling TNG mod; this one had the identical defect.

    `add_extra` also finds the file (this mission, then each pinned pack, PREFERRING the
    unpacked `__lib__/media` copy - the only one the engine can open), decides the
    extension by which file actually opens, merges library-side so
    `filter_ship_data_by_side` and `get_ship_name` work, and writes one line to
    `debug.log` saying whether the engine took it.

    NOT `ship_data_merge_mod`: it is the BROKEN route, not the alternative one. It gets
    ships to the engine by GENERATING `extraShipData.json` during sim_create(); that file
    stays on disk and is read back next run while the add-on declares the same entries
    again - the TNG pack measured 51 hulls becoming 102 from run 2 onward. On engine 1.3.6
    the route is dead outright: the binary no longer contains the string `extraShipData`.

    NO `artfilepath` IS SET, deliberately - and as of engine v1.3.6 the field is obsolete
    anyway. These hulls borrow STOCK art roots, which the engine already resolves out of
    `data/graphics/ships`. Pointing them at this pack's own art would currently segfault
    the engine at render - see the mod README.

    `ships_file` is accepted and ignored, so an older call site still works.

    Returns a short STATUS STRING rather than a dict: MAST re-runs an assigned string
    through f-string formatting, so a dict's braces reaching `log(f"...{result}")` die.
    """
    from sbs_utils.procedural.ship_data import add_extra, get_ship_data_for

    # No extension: add_extra decides the format by which file opens, and hands the engine
    # the exact file it read.
    reached = add_extra("venus_ships", mod="venus_races")

    # A verification, NOT a merge gate - add_extra has already merged library-side.
    have = get_ship_data_for(VENUS_PROBE_KEY) is not None
    return venus_safe_status("engine=" + str(reached)
                             + " library=" + ("ok" if have else "MISSING - file not found"))
def venus_hull_count():
    """How many Venus hulls the LIBRARY can see. The test range asserts this, because a
    mastlib that fails to load still reports PASS."""
    from sbs_utils.procedural.ship_data import get_ship_data
    data = get_ship_data() or []
    return sum(1 for e in data if str(getattr(e, "key", None) or
                                      (e.get("key") if hasattr(e, "get") else "")
                                      or "").startswith("venus_"))


def _venus_enabled(manifest, kind):
    """The manifest sections whose faction the mission has actually switched on.

    Driven from the manifest rather than literal calls in __init__.mast, so a renamed file
    fails loudly at load instead of drifting silently.
    """
    from sbs_utils.procedural.settings import (settings_race_is_playable,
                                               settings_race_is_npc)
    check = settings_race_is_playable if kind == "interiors" else settings_race_is_npc
    section = (manifest or {}).get(kind) or {}
    return [faction for faction in sorted(section) if check(faction)]


def venus_interiors_enabled(manifest):
    """Every .grid file for a PLAYABLE faction. Interiors are about flying a hull, so the
    gate is playability - an NPC never opens an Engineering console."""
    out = []
    for faction in _venus_enabled(manifest, "interiors"):
        out.extend((manifest or {}).get("interiors", {}).get(faction) or [])
    return out


def venus_fleets_enabled(manifest):
    """Every fleet ladder for a faction in NPC_RACES. Ladders are about being spawned AT
    the players, so the gate is the NPC list."""
    return [(manifest or {}).get("fleets", {}).get(f)
            for f in _venus_enabled(manifest, "fleets")]
