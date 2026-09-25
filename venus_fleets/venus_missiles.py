# Above the Venusian Clouds - NPC missile volleys. Missiles only: Venus warships carry no
# working beams, so an NPC warship fights by launching real torpedoes at whatever its AI
# is targeting.
#
# ENGINE-VERIFIED (Venus_TestRange venus_probe, 2026-09-24): a registered torpedo type,
# `torpedoLaunchType` on the blob, then `sim.launch_torpedo(engine_object, 0, 0)` on an NPC
# puts a real torpedo in the world - three calls, three new engine objects. The recipe is
# the engine team's own (BeamArcTest) and event_probe's.
#
# Driven by the shared server ticker (__init__.mast), not a brain per ship. The cooldown
# lives in each ship's inventory, so it dies with the ship.

VENUS_MISSILE_TYPE = "VenusMissile"
VENUS_MISSILE_DESC = ("gui_text:Missile; speed:9; lifetime:25; flare_color:#fc8; trail_color:#ddd; "
                      "warhead:standard; damage:30; explosion_size:10; explosion_color:fire; "
                      "behavior:homing; energy_conversion_value:100; desc:`Venus salvage missile`")
VENUS_VOLLEY_RANGE = 5000.0
# seconds between launches, per role (stations defend their own airspace)
VENUS_VOLLEY_EVERY = {"frigate": 9.0, "destroyer": 5.0, "cruiser": 6.0, "carrier": 10.0,
                      "station_command": 4.0, "station_industrial": 8.0, "station_science": 8.0}


def venus_missile_register():
    """Register the missile type with the engine. Safe to repeat."""
    from sbs_utils.helpers import FrameContext
    try:
        FrameContext.context.sbs.set_shared_string(VENUS_MISSILE_TYPE, VENUS_MISSILE_DESC)
        return True
    except Exception:
        return False


def venus_missiles_tick(dt=2.0):
    """Every NPC Venus warship with a live target in range launches on its cooldown."""
    from sbs_utils.helpers import FrameContext
    from sbs_utils.procedural.roles import role, has_role
    from sbs_utils.procedural.query import to_object_list, object_exists, get_data_set_value
    from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
    ctx = FrameContext.context
    if ctx is None:
        return 0
    fired = 0
    for s in to_object_list(role("venus_hull") - role("__player__") - role("venus_turret")):
        if s is None:
            continue
        info = venus_hull_info(s)
        every = VENUS_VOLLEY_EVERY.get(info["design"]) if info else None
        if not every:
            continue
        cd = (get_inventory_value(s.id, "venus_volley_cd", 0.0) or 0.0) - dt
        if cd > 0:
            set_inventory_value(s.id, "venus_volley_cd", cd)
            continue
        target = get_data_set_value(s.id, "target_id", default=0) or 0
        if not target or not object_exists(target) or has_role(target, "venus_in_cloud"):
            continue
        try:
            if ctx.sbs.distance_id(s.id, target) > VENUS_VOLLEY_RANGE:
                continue
            s.data_set.set("torpedoLaunchType", VENUS_MISSILE_TYPE, 0)
            ctx.sim.launch_torpedo(s.engine_object, 0, 0)
            fired += 1
        except Exception:
            continue
        set_inventory_value(s.id, "venus_volley_cd", every)
    if fired:
        from sbs_utils.procedural.execution import get_shared_variable, set_shared_variable
        set_shared_variable("VENUS_MISSILES_FIRED", (get_shared_variable("VENUS_MISSILES_FIRED") or 0) + fired)
    return fired
