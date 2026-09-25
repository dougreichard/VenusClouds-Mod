# Above the Venusian Clouds - the world: the cloud sea, cover, storms, harvest, salvage,
# and lift that bleeds away until a ship sinks.
#
# State lives on the OBJECTS (roles and inventory), never in module-level containers: a
# module container outlives a mission in the reused dev interpreter and has to be declared
# to the reset ledger, while an object's inventory dies with the object.
#
# One server ticker (__init__.mast) calls venus_world_tick(dt) every couple of seconds -
# proximity over a few dozen clouds and ships, not a per-tick scan.

import math
import random

VENUS_CLOUD_ROLE = "venus_cloud"
VENUS_IN_CLOUD = "venus_in_cloud"
VENUS_HARVEST_RATE = 2.0          # units per second inside a resource cloud
VENUS_CLOUD_STOCK = (150, 400)    # units a resource cloud starts with
VENUS_SINK_RATE = 60.0            # world units per second while above the ceiling lift allows
VENUS_STORM_EVERY = 6.0           # seconds between storm strikes on a ship inside a cell
VENUS_STORM_BLINK = -3           # blink_state for storm cells: lightning flicker
VENUS_PULSE = 6                  # blink_state pulse for aether and spore clouds
VENUS_PULSE_RESOURCES = ("aether", "medicine")
VENUS_NPC_LIFT_PER_HULL = 0.12
# Units a hold carries, by role. Without a cap a crew parked in one cloud until it was gone
# (a balance session hauled 200 a trip only because the autopilot chose to turn back).
# The cap is what makes the logistics hulls worth flying and the trip home the game.
VENUS_HOLD = {"cargo_barge": 800, "steam_tender": 500, "carrier": 400, "cruiser": 250,
              "destroyer": 150, "frigate": 120, "tug": 100, "launch": 60, "fighter": 20}
VENUS_HOLD_DEFAULT = 150    # lift an NPC loses per hull point of damage


# --------------------------------------------------------------------------- per hull
VENUS_TURRET_HOSTS = ("carrier", "cruiser", "station_command", "station_industrial", "station_civil",
                      "station_science")


def venus_on_spawn(obj_id):
    """A Venus hull just spawned: tag it, fill its lift, light its smoke and (carriers,
    cruisers, stations) weld its turrets on. Turrets themselves only get the tag."""
    from sbs_utils.procedural.query import to_object
    from sbs_utils.procedural.roles import add_role, has_role
    obj = to_object(obj_id)
    info = venus_hull_info(obj)
    if obj is None or info is None or has_role(obj.id, "venus_hull"):
        return 0
    add_role(obj.id, "venus_hull")
    add_role(obj.id, "venus_" + info["faction"].lower())
    if info["design"] == "turret":
        return 0
    venus_lift_set(obj, 1.0)
    try:
        venus_particles_attach(obj)
    except Exception:
        pass
    venus_hangar_stock(obj, info)
    if info["design"] in VENUS_TURRET_HOSTS:
        return len(venus_turrets_attach(obj))
    return 0


# Craft a Venus hull carries for LM's hangar console: (role in this fleet, hangar type, count).
VENUS_HANGAR = {
    "carrier": (("fighter", "fighter", 4), ("launch", "shuttle", 1)),
    "station_command": (("fighter", "fighter", 2), ("launch", "shuttle", 1)),
    "station_civil": (("launch", "shuttle", 1),),
}


def venus_hangar_stock(obj, info=None):
    """Stock a carrier or station's hangar with its OWN fleet's fighters and launches.
    Only when LegendaryMissions' hangar is loaded (looked up at call time, so the mod
    works without it). Returns the number of craft spawned."""
    from sbs_utils.mast.mast_globals import MastGlobals
    spawn = MastGlobals.globals.get("hangar_craft_spawn")
    info = info or venus_hull_info(obj)
    if spawn is None or info is None or info["design"] not in VENUS_HANGAR:
        return 0
    tag = (venus_faction_info(info["faction"]) or {}).get("tag", "steam")
    n = 0
    for design, kind, count in VENUS_HANGAR[info["design"]]:
        for i in range(count):
            try:
                if spawn(obj.id, {"key": "venus_" + tag + "_" + design, "type": kind}) is not None:
                    n += 1
            except Exception:
                pass
    return n


# --------------------------------------------------------------------------- spawning
def venus_cloud_spawn(key, x, y, z, cover=True):
    """Place one cloud (a venus_cloud_* hull) as passive terrain. Resource clouds get a
    stock to harvest. cover=True puts an engine nebula inside it - the engine's own
    sensor cover, which is what makes hiding in a cloud real."""
    from sbs_utils.procedural.spawn import terrain_spawn
    from sbs_utils.procedural.roles import add_role
    from sbs_utils.procedural.inventory import set_inventory_value
    from sbs_utils.procedural.query import to_id
    info = (venus_manifest().get("clouds") or {}).get(key)
    if info is None:
        return None
    obj = terrain_spawn(x, y, z, "", "#,venus_cloud", key, "behav_asteroid")
    cid = to_id(obj)
    if cid is None:
        return None
    add_role(cid, VENUS_CLOUD_ROLE)
    set_inventory_value(cid, "venus_radius", info["radius"])
    if info.get("resource"):
        add_role(cid, "venus_resource")
        set_inventory_value(cid, "venus_resource", info["resource"])
        stock = random.uniform(*VENUS_CLOUD_STOCK)
        set_inventory_value(cid, "venus_stock", stock)
        set_inventory_value(cid, "venus_stock_full", stock)
    if info.get("storm"):
        add_role(cid, "venus_storm")
    # The glow is the emissive map; blink_state animates it (positive = pulse delay,
    # negative = blink delay). A storm cell's lightning flickers; the living and the
    # exotic resource clouds breathe.
    try:
        if info.get("storm"):
            obj.engine_object.blink_state = VENUS_STORM_BLINK
        elif info.get("resource") in VENUS_PULSE_RESOURCES:
            obj.engine_object.blink_state = VENUS_PULSE
    except Exception:
        pass
    if cover:
        # ONE engine nebula, cloud-sized, at the cloud's own position. Engine-measured: the
        # sphere-cluster helper spawned none inside a 600-unit cloud (inside_nebula_count
        # stayed 0), and terrain_nebula_spawn forces y onto the 0 plane.
        try:
            from sbs_utils.procedural.terrain import terrain_setup_nebula
            neb = terrain_spawn(x, y, z, None, "#, nebula", "nebula", "behav_nebula")
            neb.blob.set("unselectable", 1)
            terrain_setup_nebula(neb, min(1500.0, info["radius"] * 2.0), 0.6, "yellow")
            set_inventory_value(cid, "venus_nebulae", [to_id(neb)])
        except Exception:
            pass
    return cid


def venus_world_spawn(cx=0.0, cz=0.0, radius=40000.0, lanes=24, resources=10, storms=2, wrecks=3,
                      floor=36, seed=None):
    """Dress a map: a cloud-sea floor at the deck band, scattered lane clouds, resource
    clouds, storm cells and wrecks. Returns a short status string."""
    rng = random.Random(seed)
    clouds = list((venus_manifest().get("clouds") or {}).keys())
    plain = [k for k in clouds if not (venus_manifest()["clouds"][k].get("resource")
                                       or venus_manifest()["clouds"][k].get("storm"))]
    res = [k for k in clouds if venus_manifest()["clouds"][k].get("resource") and "wreck" not in k]
    storm = [k for k in clouds if venus_manifest()["clouds"][k].get("storm")]
    wreck = [k for k in clouds if "wreck" in k]
    floor_y = venus_floor_y()      # venus_altitude.py

    def at(r_min, r_max):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(r_min, r_max)
        return cx + math.cos(a) * d, cz + math.sin(a) * d

    n = 0
    for i in range(floor):                         # the sea you can see down there
        x, z = at(0, radius * 1.2)
        n += venus_cloud_spawn("venus_cloud_stratus_bank", x, floor_y + rng.uniform(-400, 400), z, cover=False) is not None
    for i in range(lanes):
        x, z = at(radius * 0.1, radius)
        n += venus_cloud_spawn(rng.choice(plain), x, rng.uniform(-2500, 2500), z) is not None
    for i in range(resources):
        x, z = at(radius * 0.2, radius)
        n += venus_cloud_spawn(rng.choice(res), x, rng.uniform(-3500, 2000), z) is not None
    for i in range(storms):
        x, z = at(radius * 0.3, radius)
        n += venus_cloud_spawn(rng.choice(storm), x, rng.uniform(-1500, 1500), z) is not None
    for i in range(wrecks):
        x, z = at(radius * 0.3, radius)
        n += venus_cloud_spawn(rng.choice(wreck), x, rng.uniform(-5000, -2000), z) is not None
    return "venus world: " + str(n) + " clouds"


# --------------------------------------------------------------------------- the tick
def _venus_dist(a, b):
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def venus_world_tick(dt=2.0):
    """Cover, storms, harvest and salvage for every ship near every cloud."""
    from sbs_utils.procedural.roles import role, add_role, remove_role, has_role
    from sbs_utils.procedural.query import to_object_list, to_object
    from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
    clouds = [c for c in to_object_list(role(VENUS_CLOUD_ROLE)) if c is not None]
    ships = [s for s in to_object_list(role("ship") | role("__player__")) if s is not None]
    for s in ships:
        inside = False
        spos = s.pos
        for c in clouds:
            r = get_inventory_value(c.id, "venus_radius", 0) or 0
            if r <= 0 or _venus_dist(spos, c.pos) > r:
                continue
            inside = True
            if has_role(c.id, "venus_storm"):
                _venus_storm(s, dt)
            if has_role(c.id, "venus_resource") and has_role(s.id, "__player__"):
                _venus_harvest(s, c, dt)
        # The engine's own answer too: every cloud carries nebulae, and the blob counts the
        # nebulae a ship is inside (object_data_documentation.txt: inside_nebula_count).
        if not inside:
            try:
                from sbs_utils.procedural.query import get_data_set_value
                inside = (get_data_set_value(s.id, "inside_nebula_count", default=0) or 0) > 0
            except Exception:
                pass
        if not inside:
            inside = venus_ability_hides(s)          # the Flotilla's steam screen
        if inside and not has_role(s.id, VENUS_IN_CLOUD):
            add_role(s.id, VENUS_IN_CLOUD)
        elif not inside and has_role(s.id, VENUS_IN_CLOUD):
            remove_role(s.id, VENUS_IN_CLOUD)


def _venus_storm(ship, dt):
    from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
    from sbs_utils.procedural.roles import has_role
    t = (get_inventory_value(ship.id, "venus_storm_t", 0.0) or 0.0) + dt
    if t < VENUS_STORM_EVERY:
        set_inventory_value(ship.id, "venus_storm_t", t)
        return
    set_inventory_value(ship.id, "venus_storm_t", 0.0)
    try:
        from sbs_utils.procedural.particles import particle_burst
        particle_burst(ship, None, align=True, shape="hull", color="#bdf,white", lifespan=6,
                       image_cell=(0, 3), size=3, speed=6, count=30)
    except Exception:
        pass
    if has_role(ship.id, "__player__"):
        try:
            from sbs_utils.procedural.internal_damage import grid_damage_system
            grid_damage_system(ship.id, None)
        except Exception:
            pass
    else:
        venus_lift_bleed(ship, 0.05)


def _venus_harvest(ship, cloud, dt):
    """Fill the ship's hold from a resource cloud; the cloud shrinks and finally goes.
    The wreck gives salvage and restores the ship's lift - a replacement ring."""
    from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
    from sbs_utils.procedural.space_objects import delete_object
    res = get_inventory_value(cloud.id, "venus_resource", None)
    stock = get_inventory_value(cloud.id, "venus_stock", 0.0) or 0.0
    if not res or stock <= 0:
        return
    room = venus_hold_capacity(ship) - sum(venus_cargo(ship).values())
    take = min(stock, VENUS_HARVEST_RATE * dt, max(0.0, room))
    if take <= 0:
        return
    stock -= take
    set_inventory_value(cloud.id, "venus_stock", stock)
    key = "venus_cargo_" + res
    set_inventory_value(ship.id, key, (get_inventory_value(ship.id, key, 0.0) or 0.0) + take)
    if res == "salvage" and venus_lift_get(ship) < 1.0:
        venus_lift_restore(ship, take / 60.0)
    full = get_inventory_value(cloud.id, "venus_stock_full", stock) or 1.0
    try:
        cloud.data_set.set("local_scale_coeff", max(0.35, stock / full), 0)
    except Exception:
        pass
    if stock <= 0:
        for nid in get_inventory_value(cloud.id, "venus_nebulae", []) or []:
            try:
                delete_object(nid)
            except Exception:
                pass
        delete_object(cloud.id)


def venus_hold_capacity(ship):
    """How many units this hull's hold carries (VENUS_HOLD by role)."""
    info = venus_hull_info(ship)
    from sbs_utils.procedural.inventory import get_inventory_value
    from sbs_utils.procedural.query import to_id
    bonus = get_inventory_value(to_id(ship), "venus_hold_bonus", 0) or 0
    if info is None:
        return VENUS_HOLD_DEFAULT + bonus
    return VENUS_HOLD.get(info.get("design"), VENUS_HOLD_DEFAULT) + bonus


def venus_cargo(ship):
    """A ship's harvested resources, as a dict (for a console or a trade screen)."""
    from sbs_utils.procedural.inventory import get_inventory_value
    out = {}
    for res in ("coolant", "fuel", "aether", "medicine", "materials", "salvage"):
        v = get_inventory_value(ship if isinstance(ship, int) else ship.id, "venus_cargo_" + res, 0.0) or 0.0
        if v:
            out[res] = int(v)
    return out


# --------------------------------------------------------------------------- lift
def venus_lift_from_grid(ship_id):
    """A player ship's lift: the share of its lift-ring rooms that are not damaged.
    None when the ship has no lift rooms (no interior loaded)."""
    from sbs_utils.procedural.grid import grid_objects
    from sbs_utils.procedural.roles import role
    rooms = grid_objects(ship_id) & role("lift")
    if not rooms:
        return None
    broken = rooms & role("__damaged__")
    return 1.0 - len(broken) / float(len(rooms))


def venus_lift_refit(ship):
    """A full refit: every lift-ring room repaired, lift back to full. What a yard, a wreck's
    salvage or a trade gives. Setting lift alone is NOT a refit on a player - venus_lift_tick
    re-reads lift from the damaged ring rooms every tick, so it would fall straight back."""
    from sbs_utils.procedural.query import to_object
    from sbs_utils.procedural.roles import has_role, role
    ship = to_object(ship)
    if ship is None:
        return 0
    n = 0
    if has_role(ship.id, "__player__"):
        try:
            from sbs_utils.procedural.grid import grid_objects
            from sbs_utils.procedural.internal_damage import grid_repair_grid_objects
            broken = grid_objects(ship.id) & role("lift") & role("__damaged__")
            n = len(broken)
            if broken:
                grid_repair_grid_objects(ship.id, broken)
        except Exception:
            pass
    venus_lift_set(ship, 1.0)
    return n


def venus_lift_restore(ship, amount):
    """Give back `amount` (0..1) of lift. An NPC's lift is a number; a player's is its ring
    ROOMS, so the fraction accumulates and whole rooms are repaired as it adds up."""
    from sbs_utils.procedural.query import to_object
    from sbs_utils.procedural.roles import has_role, role
    from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
    ship = to_object(ship)
    if ship is None or amount <= 0:
        return 0
    if not has_role(ship.id, "__player__"):
        venus_lift_set(ship, min(1.0, venus_lift_get(ship) + amount))
        return 0
    try:
        from sbs_utils.procedural.grid import grid_objects
        from sbs_utils.procedural.internal_damage import grid_repair_grid_objects
        rooms = grid_objects(ship.id) & role("lift")
        broken = sorted(rooms & role("__damaged__"))
    except Exception:
        return 0
    if not rooms or not broken:
        set_inventory_value(ship.id, "venus_lift_owed", 0.0)
        return 0
    owed = (get_inventory_value(ship.id, "venus_lift_owed", 0.0) or 0.0) + amount * len(rooms)
    fix = min(len(broken), int(owed))
    if fix:
        grid_repair_grid_objects(ship.id, set(broken[:fix]))
    set_inventory_value(ship.id, "venus_lift_owed", owed - fix)
    return fix


def venus_lift_on_damage(ship, hull_lost):
    """Hull damage costs lift. Players: a hit may land in a lift room (the grid decides);
    this adds a chance to hit one outright. NPCs have no interior: lift bleeds directly."""
    from sbs_utils.procedural.roles import has_role
    if ship is None or hull_lost <= 0:
        return
    if has_role(ship.id, "__player__"):
        if random.random() < min(0.6, 0.25 * hull_lost):
            try:
                from sbs_utils.procedural.internal_damage import grid_damage_system
                grid_damage_system(ship.id, "lift")
            except Exception:
                pass
    else:
        venus_lift_bleed(ship, VENUS_NPC_LIFT_PER_HULL * hull_lost)


def venus_lift_tick(dt=2.0):
    """Every Venus hull: update lift, squeeze it down to the altitude its lift can hold,
    apply deck pressure, smolder when crippled, and dress each crew's sky for its band."""
    from sbs_utils.procedural.roles import role, has_role
    from sbs_utils.procedural.query import to_object_list
    from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
    from sbs_utils.procedural.space_objects import set_pos
    # A crew seated by a map's Crew: block is RE-HULLED after it spawns, so the //spawn
    # route saw the stock hull (engine-measured: a Flotilla cruiser with no turrets, no
    # smoke and untracked lift). Adopt any player now flying a Venus hull.
    for p in to_object_list(role("__player__") - role("venus_hull")):
        if p is not None and venus_hull_info(p) is not None:
            venus_on_spawn(p.id)
    from sbs_utils.procedural.query import object_exists
    # turrets are venus_hull too, but have no lift - and a re-weld below deletes them
    # mid-pass, so every hull is re-checked before it is read
    for s in to_object_list(role("venus_hull") - role(VENUS_TURRET_ROLE)):
        if s is None or not object_exists(s.id):
            continue
        # a re-hulled / re-sided crew: turrets follow the ship, smoke follows the new art
        if venus_turrets_sync(s) and has_role(s.id, "__player__"):
            try:
                venus_particles_attach(s)
            except Exception:
                pass
        if has_role(s.id, "__player__"):
            g = venus_lift_from_grid(s.id)
            if g is not None:
                venus_lift_set(s, g)
        lift = venus_lift_get(s)
        p = s.pos
        if p is None:
            continue
        ceiling = venus_ceiling_for_lift(lift)
        if p.y > ceiling:
            set_pos(s, p.x, max(ceiling, p.y - VENUS_SINK_RATE * dt), p.z)
        hazard = venus_hazard(p.y)
        if hazard > 0.4:
            venus_lift_on_damage(s, hazard * dt * 0.5)
        if abs(get_inventory_value(s.id, "venus_lift_shown", 1.0) - lift) > 0.2:
            set_inventory_value(s.id, "venus_lift_shown", lift)
            try:
                venus_particles_damaged(s, lift)
            except Exception:
                pass
        if has_role(s.id, "__player__"):
            band = venus_band(p.y)
            if get_inventory_value(s.id, "venus_band", None) != band:
                set_inventory_value(s.id, "venus_band", band)
                try:
                    from sbs_utils.procedural.media import skybox_schedule
                    skybox_schedule(venus_band_sky(band), s.id)
                except Exception:
                    pass
