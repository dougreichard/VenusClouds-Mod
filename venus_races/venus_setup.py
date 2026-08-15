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


def venus_declare_ships(ships_file):
    """Give the hulls to the ENGINE and to the library, without writing a file.

    TWO CONSUMERS, and they are not the same thing:

      * the ENGINE needs them to build hulls, and learns them from a real file on disk.
        `sbs.add_extra_ship_data(name, path)` points it straight at the mod's own copy -
        no extension on the name, the engine tries .yaml then .json itself.
      * the LIBRARY needs them for its own queries: `filter_ship_data_by_side` is how a
        prefab finds "an Armada raider" and `get_ship_name` is what a console displays.
        The engine call does not populate that, so it is merged here too.

    NOT `ship_data_merge_mod`: it is the BROKEN route, not the alternative one. It gets
    ships to the engine by GENERATING `extraShipData.json` in the mission folder during
    sim_create(). That file stays on disk, and on the next run `get_ship_data()` prepends it
    whole - `#mod` entries and all - while the add-on declares the same entries again. The
    TNG pack measured 51 hulls becoming 102 from run 2 onward. The file the feature
    generates is the input that breaks it.

    NO `artfilepath` IS SET, deliberately. These hulls borrow STOCK art roots, which the
    engine already resolves out of `data/graphics/ships`. Pointing them at this pack's own
    art would currently segfault the engine at render - see the mod README.

    Returns a short STATUS STRING rather than a dict: MAST re-runs an assigned string
    through f-string formatting, so a dict's braces reaching `log(f"...{result}")` die.
    """
    import os
    import re
    from sbs_utils.helpers import FrameContext
    from sbs_utils.fs import get_mission_dir
    from sbs_utils.procedural.ship_data import get_ship_data_for, merge_mod_ship_yaml

    if not ships_file:
        return "NOT DECLARED - the media pack was not found"

    # media_shared answers RELATIVE TO THE MISSION. Neither open() nor the engine is
    # standing in the mission folder, so resolve it before using it either way.
    if not os.path.isabs(ships_file):
        ships_file = os.path.abspath(os.path.join(get_mission_dir(), ships_file))
    pack_dir = os.path.dirname(ships_file)

    told_engine = None
    try:
        sbs = FrameContext.context.sbs
        # ONE argument, the whole file. The 2026-08-15 engine takes
        # `add_extra_ship_data(fully_pathed_file)`; the old `(name, folder)` form is a
        # TypeError, caught below as "failed:" and otherwise silent - the library merge
        # still runs, so the hulls have every stat and simply do not exist in the engine.
        sbs.add_extra_ship_data(ships_file)
        told_engine = True
    except AttributeError:
        # An older engine or sbslib without the call. Not fatal: the library merge below
        # still gives the mission its ships, they just have no engine-side hull.
        told_engine = False
    except Exception as e:
        told_engine = "failed: " + str(e)

    # The presence guard is what makes this safe to call twice: the MOCK's
    # add_extra_ship_data already merges library-side, the real engine does not, and one
    # guard covers both without either knowing about the other.
    merged = 0
    if get_ship_data_for(VENUS_PROBE_KEY) is None:
        try:
            with open(ships_file, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            return venus_safe_status("engine=" + str(told_engine)
                                     + " library=unreadable " + str(e))
        merge_mod_ship_yaml(re.sub(r"^[ \t]*//.*$", "", text, flags=re.M), "venus_races")
        merged = 1
    return "engine=" + str(told_engine) + " library=" + ("merged" if merged else "already present")


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
