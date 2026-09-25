# Above the Venusian Clouds - faction doctrines and wind lanes.
#
# Each faction has ONE ability, used from the Airship ePADD app (venus_console.mast) or by
# script (venus_ability_use). Wind lanes are fast lanes through the cloud sea: a ship
# flying WITH the wind goes faster.
#
# Both change speed, so both go through one multiplier: base x ability x wind, recomputed
# on the mod's ticker. A player's speed is impulse_upgrade_coeff, an NPC's speed_coeff.
# The base is captured the first time a boost touches a ship, so a mission or upgrade
# that set it first is respected rather than overwritten.
#
# State lives on the ship's inventory (and the lanes on SHARED's), never in a module
# container - a module container outlives a mission in the reused dev interpreter.

import math

# faction -> (name, cooldown s, duration s, one-line description)
VENUS_ABILITIES = {
    "Flotilla":    ("Boiler Vent", 75.0, 12.0, "Vent the boilers: a steam screen hides the ship as a cloud does."),
    "Concord":     ("Gas Trim", 90.0, 0.0, "Trim the envelope: restore a third of the ship's lift."),
    "Directorate": ("Reactor Overcharge", 90.0, 12.0, "Shields to full and half again the speed."),
    "Syndicate":   ("Flak Curtain", 60.0, 0.0, "Shoot down every missile within 1500."),
    "Commons":     ("Sail Sprint", 60.0, 10.0, "Unfurl the sails: double speed."),
    "Brood":       ("Regrowth", 120.0, 20.0, "Regrow: lift and shields recover over 20 seconds."),
}
VENUS_ABILITY_SPEED = {"Directorate": 1.5, "Commons": 2.0}
VENUS_FLAK_RANGE = 1500.0
VENUS_WIND_SPEED = 1.6          # speed multiplier flying with a wind lane
VENUS_WIND_ALIGN = 0.5          # cos of the widest angle to the wind that still counts


def _venus_now():
    from sbs_utils.helpers import FrameContext
    return FrameContext.sim_seconds or 0.0


def _venus_inv(obj, key, default=None):
    from sbs_utils.procedural.inventory import get_inventory_value
    return get_inventory_value(obj.id, key, default)


def _venus_set(obj, key, value):
    from sbs_utils.procedural.inventory import set_inventory_value
    set_inventory_value(obj.id, key, value)


def venus_ability_info(ship):
    """(name, description, seconds until ready, seconds still active) for a Venus hull,
    or None for a hull with no faction."""
    from sbs_utils.procedural.query import to_object
    ship = to_object(ship)
    info = venus_hull_info(ship) if ship is not None else None
    if info is None or info["faction"] not in VENUS_ABILITIES:
        return None
    name, cd, dur, desc = VENUS_ABILITIES[info["faction"]]
    now = _venus_now()
    ready = max(0.0, (_venus_inv(ship, "venus_ability_ready", 0.0) or 0.0) - now)
    active = max(0.0, (_venus_inv(ship, "venus_ability_until", 0.0) or 0.0) - now)
    return name, desc, ready, active


def venus_ability_use(ship):
    """Fire this hull's faction ability. Returns a short result line (engine-safe ASCII)."""
    from sbs_utils.procedural.query import to_object
    ship = to_object(ship)
    info = venus_hull_info(ship) if ship is not None else None
    if info is None or info["faction"] not in VENUS_ABILITIES:
        return "No doctrine for this hull."
    fac = info["faction"]
    name, cd, dur, desc = VENUS_ABILITIES[fac]
    now = _venus_now()
    if (_venus_inv(ship, "venus_ability_ready", 0.0) or 0.0) > now:
        return name + " is not ready."
    _venus_set(ship, "venus_ability_ready", now + cd)
    _venus_set(ship, "venus_ability_until", now + dur)
    _venus_set(ship, "venus_ability_kind", fac)
    if fac == "Flotilla":
        from sbs_utils.procedural.roles import add_role
        add_role(ship.id, VENUS_IN_CLOUD)
        _venus_burst(ship, "#eee,#bbb", True)
    elif fac == "Concord":
        venus_lift_restore(ship, 0.34)
    elif fac == "Directorate":
        _venus_shields_full(ship)
        _venus_burst(ship, "#6f8,#1c9", False)
    elif fac == "Syndicate":
        n = _venus_flak(ship)
        return name + ": " + str(n) + " missiles down."
    elif fac == "Brood":
        _venus_burst(ship, "#3fc,#1a8", False)
    venus_speed_refresh(ship)
    return name + "!"


def venus_ability_hides(ship):
    """True while a Flotilla steam screen is up - the world tick counts it as cloud cover."""
    return (_venus_inv(ship, "venus_ability_kind", None) == "Flotilla"
            and (_venus_inv(ship, "venus_ability_until", 0.0) or 0.0) > _venus_now())


def _venus_burst(ship, color, smoke):
    # image_cell is REQUIRED in practice: a burst without one crashed the CLIENT in
    # Render3DObject::EmitAt (null deref, engine-measured 2026-09-25, Boiler Vent). Every
    # library preset carries one; this burst did not.
    try:
        from sbs_utils.procedural.particles import particle_burst
        particle_burst(ship.id, shape="hull", align=True, color=color, lifespan=40,
                       image_cell=(4 if smoke else (0, 3)), size=4.0, speed=0.6, count=40,
                       smoke=smoke)
    except Exception:
        pass


def _venus_shields_full(ship, fraction=1.0):
    ds = ship.data_set
    try:
        n = int(ds.get("shield_count", 0) or 0)
    except Exception:
        n = 0
    for i in range(max(n, 2)):
        try:
            top = ds.get("shield_max_val", i)
            cur = ds.get("shield_val", i)
            if top is None or cur is None:
                continue
            ds.set("shield_val", min(top, cur + top * fraction), i)
        except Exception:
            pass


def _venus_flak(ship):
    """Destroy every torpedo/missile within range of the ship. Returns how many."""
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.query import to_object_list
    from sbs_utils.procedural.space_objects import delete_object
    n = 0
    for t in to_object_list(role("torpedo")):
        if t is None:
            continue
        d = math.sqrt((t.pos.x - ship.pos.x) ** 2 + (t.pos.y - ship.pos.y) ** 2 + (t.pos.z - ship.pos.z) ** 2)
        if d <= VENUS_FLAK_RANGE:
            try:
                delete_object(t.id)
                n += 1
            except Exception:
                pass
    return n


def venus_abilities_tick(dt=2.0):
    """Run lasting effects and expire them; refresh every boosted ship's speed."""
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.query import to_object_list
    now = _venus_now()
    for s in to_object_list(role("venus_hull") - role(VENUS_TURRET_ROLE)):
        if s is None:
            continue
        until = _venus_inv(s, "venus_ability_until", 0.0) or 0.0
        kind = _venus_inv(s, "venus_ability_kind", None)
        if kind and until > now:
            if kind == "Brood":
                venus_lift_restore(s, 0.02 * dt)
                _venus_shields_full(s, 0.03 * dt)
        elif kind:
            # expired; venus_world_tick drops a finished steam screen's cover on its own
            _venus_set(s, "venus_ability_kind", None)
        if kind or _venus_inv(s, "venus_speed_base", None) is not None:
            venus_speed_refresh(s)


# --------------------------------------------------------------------------- speed
def _venus_speed_key(ship):
    from sbs_utils.procedural.roles import has_role
    return "impulse_upgrade_coeff" if has_role(ship.id, "__player__") else "speed_coeff"


def venus_speed_refresh(ship):
    """Speed = base x ability x wind. Idempotent; call whenever a boost may have changed."""
    key = _venus_speed_key(ship)
    base = _venus_inv(ship, "venus_speed_base", None)
    if base is None:
        try:
            base = ship.data_set.get(key, 0)
        except Exception:
            base = None
        base = 1.0 if base in (None, 0) else float(base)
        _venus_set(ship, "venus_speed_base", base)
    mult = 1.0
    kind = _venus_inv(ship, "venus_ability_kind", None)
    if kind and (_venus_inv(ship, "venus_ability_until", 0.0) or 0.0) > _venus_now():
        mult *= VENUS_ABILITY_SPEED.get(kind, 1.0)
    mult *= _venus_inv(ship, "venus_wind_mult", 1.0) or 1.0
    try:
        ship.data_set.set(key, base * mult, 0)
    except Exception:
        pass
    return base * mult


# --------------------------------------------------------------------------- wind lanes
def venus_wind_lane(x0, z0, x1, z1, y=0.0, width=1500.0, wisps=True):
    """A fast lane from (x0, z0) to (x1, z1) at altitude y. Ships flying with it (within
    60 degrees of its direction, inside `width`) go VENUS_WIND_SPEED times faster.
    wisps=True strings small clouds along it trailing streaks, so the lane can be seen.
    Returns the lane count."""
    from sbs_utils.agent import Agent
    lanes = list(Agent.SHARED.get_inventory_value("venus_wind_lanes", []) or [])
    lanes.append((float(x0), float(z0), float(x1), float(z1), float(y), float(width)))
    Agent.SHARED.set_inventory_value("venus_wind_lanes", lanes)
    if wisps:
        _venus_wind_wisps(x0, z0, x1, z1, y)
    return len(lanes)


def _venus_wind_wisps(x0, z0, x1, z1, y):
    from sbs_utils.procedural.particles import particle_effect, particle_preset_get, particle_preset_define
    if particle_preset_get("venus_wind") is None:
        particle_preset_define("venus_wind", align=True, smoke=True, shape="line_z", color="#fff,#dde",
                               lifespan=60, image_cell=4, size=2.0, speed=1.5, count=1)
    length = math.hypot(x1 - x0, z1 - z0)
    steps = max(2, int(length / 3000.0))
    yaw = math.atan2(x1 - x0, z1 - z0)
    for i in range(steps + 1):
        t = i / steps
        cid = venus_cloud_spawn("venus_cloud_cumulus_small", x0 + (x1 - x0) * t, y, z0 + (z1 - z0) * t, cover=False)
        if cid is None:
            continue
        try:
            from sbs_utils.procedural.query import to_object
            o = to_object(cid)
            o.engine_object.steer_yaw = 0
            venus_cloud_scale(o, (0.45, 0.35, 0.8))           # a thin streak along the wind
        except Exception:
            pass
        try:
            particle_effect(cid, "venus_wind", slot="venus_wind", priority=0)
        except Exception:
            pass
    return steps + 1


def venus_wind_tick(dt=2.0):
    """Mark every Venus hull flying with a lane; refresh its speed when that changes."""
    from sbs_utils.agent import Agent
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.query import to_object_list
    lanes = Agent.SHARED.get_inventory_value("venus_wind_lanes", []) or []
    if not lanes:
        return 0
    n = 0
    for s in to_object_list(role("venus_hull") - role(VENUS_TURRET_ROLE)):
        if s is None:
            continue
        mult = 1.0
        head = _venus_heading(s)
        for (x0, z0, x1, z1, y, width) in lanes:
            dx, dz = x1 - x0, z1 - z0
            L = math.hypot(dx, dz) or 1.0
            ux, uz = dx / L, dz / L
            t = ((s.pos.x - x0) * ux + (s.pos.z - z0) * uz)
            if t < 0 or t > L:
                continue
            off = abs((s.pos.x - x0) * uz - (s.pos.z - z0) * ux)
            if off > width or abs(s.pos.y - y) > width:
                continue
            if head is not None and head[0] * ux + head[1] * uz >= VENUS_WIND_ALIGN:
                mult = VENUS_WIND_SPEED
                break
        if (_venus_inv(s, "venus_wind_mult", 1.0) or 1.0) != mult:
            _venus_set(s, "venus_wind_mult", mult)
            venus_speed_refresh(s)
            n += 1
    return n


def _venus_heading(ship):
    """Unit (x, z) heading from the engine's forward vector, or None."""
    try:
        eo = ship.engine_object
        fx, fz = eo.forward_vector().x, eo.forward_vector().z
    except Exception:
        try:
            yaw = ship.engine_object.yaw
            fx, fz = math.sin(yaw), math.cos(yaw)
        except Exception:
            return None
    L = math.hypot(fx, fz)
    return (fx / L, fz / L) if L > 1e-6 else None


# --------------------------------------------------------------------------- console text
def venus_console_clean(text):
    """Safe inside a style string and an f-string assign: no : ; { } [ ]."""
    out = str(text)
    for a, b in ((":", " -"), (";", ","), ("{", ""), ("}", ""), ("[", ""), ("]", "")):
        out = out.replace(a, b)
    return out


def venus_console_revision(ship):
    """Changes whenever anything the VENUS tab shows would change."""
    from sbs_utils.procedural.query import to_object
    s = to_object(ship)
    if s is None:
        return None
    info = venus_ability_info(s)
    ready = int(info[2]) if info else 0
    active = int(info[3]) if info else 0
    return (int(venus_lift_get(s) * 100), sum(venus_cargo(s).values()), ready, active)


def venus_console_style(ship, part):
    """The full style string for one line of the VENUS tab (Text.update replaces the WHOLE
    style, so color and font travel with every update)."""
    from sbs_utils.procedural.query import to_object
    s = to_object(ship)
    if s is None:
        return "$text:No ship;color:#888;"
    hull = venus_hull_info(s) or {}
    fac = venus_faction_info(hull.get("faction", "")) or {}
    if part == "head":
        t, c, f = (fac.get("name") or "Venus") + " - " + str(hull.get("design", "")).replace("_", " "), "#fc8", "gui-4"
    elif part == "lift":
        lift = venus_lift_get(s)
        t = "Lift " + str(int(lift * 100)) + " percent" + (" - SINKING" if venus_is_sinking(s, s.pos.y) else "")
        c, f = ("#8f8" if lift > 0.6 else "#fd6" if lift > 0.35 else "#f66"), "gui-3"
    elif part == "hold":
        cargo = venus_cargo(s)
        held = sum(cargo.values())
        t = "Hold " + str(held) + " of " + str(venus_hold_capacity(s))
        if cargo:
            t += " - " + ", ".join(str(v) + " " + k for k, v in sorted(cargo.items()))
        c, f = "#cde", "gui-2"
    elif part == "ability":
        info = venus_ability_info(s)
        if info is None:
            t, c = "No doctrine", "#888"
        elif info[3] > 0:
            t, c = info[0] + " - ACTIVE " + str(int(info[3])) + "s", "#8f8"
        elif info[2] > 0:
            t, c = info[0] + " - ready in " + str(int(info[2])) + "s", "#fd6"
        else:
            t, c = info[0] + " - READY", "#8cf"
        f = "gui-3"
    else:
        info = venus_ability_info(s)
        t, c, f = (info[1] if info else ""), "#aaa", "gui-2"
    return "$text:" + venus_console_clean(t) + ";color:" + c + ";font:" + f + ";"


def venus_console_title(ship):
    """'<Fleet> <design>' for the Airship app's title bar."""
    from sbs_utils.procedural.query import to_object
    s = to_object(ship)
    hull = venus_hull_info(s) if s is not None else None
    if hull is None:
        return ""
    fac = venus_faction_info(hull.get("faction", "")) or {}
    return (fac.get("name") or "Venus") + " " + str(hull.get("design", "")).replace("_", " ")


def venus_epadd_badge():
    """The Airship tile's badge: lift, and the doctrine when it is ready or running. Empty
    on a hull that is not Venus (the route hides that tile anyway)."""
    from sbs_utils.helpers import FrameContext
    try:
        import sbs
        ship = sbs.get_ship_of_client(FrameContext.client_id)
    except Exception:
        return ""
    from sbs_utils.procedural.query import to_object
    s = to_object(ship)
    if s is None or venus_hull_info(s) is None:
        return ""
    out = "lift " + str(int(venus_lift_get(s) * 100)) + "%"
    info = venus_ability_info(s)
    if info is not None:
        if info[3] > 0:
            out += " - active"
        elif info[2] <= 0:
            out += " - ready"
    return out
