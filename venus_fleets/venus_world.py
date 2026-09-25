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
# blink_state: positive = pulse delay, negative = blink delay; bigger is SLOWER. The unit
# is undocumented - -3 / 6 read far too fast in the engine (user, 2026-09-25). Each cloud
# picks from a range so a sky full of them does not flash in step.
VENUS_PULSE = (40, 70)           # aether and spore clouds: slow pulse delay range
VENUS_PULSE_RESOURCES = ("aether", "medicine")
VENUS_NPC_LIFT_PER_HULL = 0.12
# Clouds are scaled per instance, the way LM scales asteroids: a size, stretched a little
# per axis, and a slow drift in yaw - so no two read as the same mesh.
VENUS_CLOUD_SIZE = (0.7, 2.4)     # plain clouds
VENUS_RESOURCE_SIZE = (0.8, 1.5)  # resource clouds (their stock does not scale with them)
VENUS_CLOUD_DRIFT = (0.00003, 0.00025)
# The engine nebula inside a cloud (its sensor cover). The library caps a nebula at 1500
# across (terrain.NEB_MAX_SIZE); a cloud's own nebula is written past that cap.
VENUS_NEBULA_MAX = 10000.0
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
def venus_cloud_spawn(key, x, y, z, cover=True, scale=None):
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
    if scale is None:
        scale = random.uniform(*(VENUS_RESOURCE_SIZE if info.get("resource") else VENUS_CLOUD_SIZE))
    sx = scale * random.uniform(0.9, 1.3)
    sy = scale * random.uniform(0.6, 1.0)
    sz = scale * random.uniform(0.9, 1.3)
    venus_cloud_scale(obj, (sx, sy, sz))
    try:
        obj.engine_object.steer_yaw = random.uniform(*VENUS_CLOUD_DRIFT) * random.choice((-1, 1))
    except Exception:
        pass
    radius = info["radius"] * max(sx, sz)
    set_inventory_value(cid, "venus_radius", radius)
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
        # (a storm cell no longer blinks: its lightning is Typhon beam fire now)
        if info.get("resource") in VENUS_PULSE_RESOURCES:
            obj.engine_object.blink_state = random.randint(*VENUS_PULSE)
    except Exception:
        pass
    # The cloud BODY is an engine nebula now; the mesh keeps only what is inside it
    # (crystals, veins, spores, ore, debris, lightning). Sized like the puff it replaced,
    # tinted to the cloud, and COVER - hiding in a cloud means hiding in this. Placed here
    # directly: terrain_nebula_spawn forces y onto the 0 plane.
    kind = "storm" if info.get("storm") else info.get("resource")
    if kind == "storm":
        venus_storm_bolts(cid, x, y, z, radius)
    nid = venus_nebula(x, y, z, min(VENUS_NEBULA_MAX, radius * VENUS_BODY_SPAN),
                       VENUS_STORM_DENSITY if kind == "storm" else VENUS_BODY_DENSITY,
                       venus_cloud_color(kind), cover=cover)
    if nid is not None:
        set_inventory_value(cid, "venus_nebulae", [nid])
    return cid


def venus_in_cover_nebula(ship):
    """True when the engine says this ship is inside a nebula tagged venus_cover."""
    from sbs_utils.procedural.roles import has_role
    try:
        ds = ship.data_set
        n = int(ds.get("inside_nebula_count", 0) or 0)
        for i in range(n):
            nid = ds.get("inside_nebula_id", i)
            if nid and has_role(nid, VENUS_COVER_ROLE):
                return True
    except Exception:
        pass
    return False


# ---- storm lightning ---------------------------------------------------------------
# A storm's lightning is BEAM FIRE: pairs of tiny Typhon monsters hidden in the cell shoot
# each other, and a Typhon beam reads as lightning (user's idea, 2026-09-25). They are
# shrunk to nothing, unselectable, re-healed every tick and never move.
VENUS_BOLT_ROLE = "venus_bolt"
VENUS_BOLT_ANCHOR_ROLE = "venus_bolt_anchor"
VENUS_BOLT_PAIRS = 3
VENUS_BOLT_SCALE = 0.05            # the anchor's size (a Typhon ignores it)
VENUS_BOLT_BODY = "#4a4c58"        # storm grey
VENUS_BOLT_CYCLE = (1.5, 4.0)       # seconds between one Typhon's beam shots
VENUS_BOLT_RANGE = 4000.0
VENUS_BOLT_LENGTH = (1500.0, 3000.0)
VENUS_BOLT_COLOR = "#dde8ff"
VENUS_BOLT_HEALTH = 1.0e9


def venus_storm_bolts(storm_id, x, y, z, radius):
    """VENUS_BOLT_PAIRS lightning bolts in a storm cell: a tiny Typhon high in the cell
    firing down at a tiny NPC anchor below it, which moves around (venus_bolts_tick).

    Engine-measured 2026-09-25, each rule the reason for a line below:
      * a Typhon will not fire at another Typhon - the anchor is an ordinary NPC;
      * nor at a cloaked one - the anchor's art is a real hull, not "invisible";
      * nor at its own side - the Typhon is `monster`, the anchor `venus`;
      * held still it fires only inside beam range - 600 fired, 2000 never did;
      * steering at its own position is a NaN assert - it aims at the anchor, and is held
        by a zero monster_speed. Returns the ids."""
    from sbs_utils.procedural.spawn import npc_spawn
    from sbs_utils.procedural.query import to_id, to_object
    from sbs_utils.procedural.inventory import set_inventory_value
    from sbs_utils.procedural.space_objects import target
    ids = []
    for k in range(VENUS_BOLT_PAIRS):
        tx = x + random.uniform(-0.5, 0.5) * radius
        ty = y + random.uniform(0.6, 1.0) * radius
        tz = z + random.uniform(-0.5, 0.5) * radius
        # Both shrunk to nothing: an engine run with full-size and tiny pairs side by side
        # fired all of them, so scale does not matter. The anchor is a VISIBLE hull:
        # "invisible" is the cloak, and a Typhon does not fire at a cloaked target.
        bolt = to_id(npc_spawn(tx, ty, tz, "", "monster," + VENUS_BOLT_ROLE, "-", "behav_typhon"))
        ax, ay, az = _venus_bolt_ground(tx, ty, tz)
        # The anchor is an ordinary NPC ship, shrunk. Every alternative drew the 3D bolt to
        # the ORIGIN (engine, 2026-09-25): the "invisible" art is a cloak (no fire at all),
        # and a behav_selection marker or a made-up behavior is not in the 3D view, so the
        # beam has no endpoint there - the 2D view still drew it to the right place.
        anchor = to_id(npc_spawn(ax, ay, az, "", "venus," + VENUS_BOLT_ANCHOR_ROLE,
                                 "tsn_light_cruiser", "behav_npcship"))
        if anchor is None or bolt is None:
            continue
        for oid in (anchor, bolt):
            o = to_object(oid)
            try:
                # A near-zero radar icon hides it on the 2D views. NOT elite_low_vis, and
                # NOT elite_main_scn_invis on the anchor: a target missing from the 3D view
                # has its bolt drawn to the origin (engine, 2026-09-25).
                o.data_set.set("icon_scale", 0.01, 0)
                if oid == bolt:
                    o.data_set.set("elite_main_scn_invis", 1, 0)
                # hiding on the 2D view: elite_low_vis and icon_scale do nothing for a
                # monster (engine); a transparent radar color is the next try
                o.data_set.set("radar_color_override", "#00000000", 0)
                o.data_set.set("local_scale_coeff", VENUS_BOLT_SCALE, 0)
                if oid == bolt:
                    # Scale does nothing to a Typhon (local_scale_coeff and the body size
                    # coeffs both tried, engine), and any body it wears hides the bolt it
                    # fires. So both bodies are a near-zero mesh the mod ships (bolt_mote).
                    # Bodies resolve from data/graphics (stock "typhon-balls" is
                    # graphics/typhon-balls), so the pack is reached relative to that.
                    ds = o.data_set
                    for i in ("1", "2"):
                        ds.set("body_" + i + "_geom_filename", venus_bolt_mote_path(), 0)
                        ds.set("body_" + i + "_color", VENUS_BOLT_BODY, 0)
                    for i in ("1", "2", "3"):
                        ds.set("particle_color_" + i, VENUS_BOLT_BODY, 0)
                    ds.set("unselectable", 1, 0)   # the TARGET stays selectable
                o.engine_object.exclusion_radius = 1      # never 0: a divide waiting
            except Exception:
                pass
            set_inventory_value(oid, "venus_bolt_storm", storm_id)
        try:
            ad = to_object(anchor).data_set
            ad.set("throttle", 0.0, 0)
            # no shields, so no shield ring on the 2D view; at 0.01 damage a shot the
            # hull outlasts any game
            for i in range(2):
                ad.set("shield_max_val", 0.0, i)
                ad.set("shield_val", 0.0, i)
            bd = to_object(bolt).data_set
            bd.set("monster_health_max", VENUS_BOLT_HEALTH, 0)
            bd.set("monster_health", VENUS_BOLT_HEALTH, 0)
            bd.set("beamColor", VENUS_BOLT_COLOR, 0)
            target(bolt, anchor, True, 1.0)              # as LM's Typhon brain does
            bd.set("monster_speed", 0.0, 0)              # ...then held still
            n = int(bd.get("beamCount", 0) or 0)
            for i in range(max(n, 1)):
                bd.set("beamCycleTime", random.uniform(*VENUS_BOLT_CYCLE), i)
                bd.set("beamRange", VENUS_BOLT_RANGE, i)
                # near-harmless, never 0: LM's Bulwark sets 0 and "never attacks". The
                # anchor's shields are refilled too - unrefilled test targets were killed.
                bd.set("beamDamage", 0.01, i)
        except Exception:
            pass
        set_inventory_value(bolt, "venus_bolt_mate", anchor)
        set_inventory_value(anchor, "venus_bolt_home", (tx, ty, tz))
        ids += [bolt, anchor]
    return ids


def _venus_bolt_ground(tx, ty, tz):
    """A point well BELOW a bolt-thrower for its anchor: a held-still Typhon with beamRange
    4000 fired at 1200, 2000 and 3000 (engine, 2026-09-25), so the bolt is long."""
    d = random.uniform(*VENUS_BOLT_LENGTH)
    j = d * 0.25
    return tx + random.uniform(-j, j), ty - d, tz + random.uniform(-j, j)


def venus_bolt_mote_path():
    """The bolt_mote body mesh, as a Typhon body filename: relative to data/graphics,
    into this mod's unpacked media pack, no extension."""
    ver = venus_manifest().get("version") or "v0.2.0"
    return "../missions/__lib__/media/artemis-sbs.VenusClouds-Mod.media." + ver + "/ships/clouds/bolt_mote"


def venus_bolts_tick():
    """Keep every bolt firing: its anchor moves to a new spot below it (so the bolt
    wanders), its target is re-set to the anchor, and the anchor's shields are refilled."""
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.query import to_object_list, to_object, object_exists
    from sbs_utils.procedural.inventory import get_inventory_value
    from sbs_utils.procedural.space_objects import set_pos
    n = 0
    for a in to_object_list(role(VENUS_BOLT_ANCHOR_ROLE)):
        if a is None:
            continue
        try:
            home = get_inventory_value(a.id, "venus_bolt_home", None)
            if home is not None:
                set_pos(a, *_venus_bolt_ground(*home))
        except Exception:
            pass
    for b in to_object_list(role(VENUS_BOLT_ROLE)):
        if b is None:
            continue
        try:
            bd = b.data_set
            bd.set("monster_health", VENUS_BOLT_HEALTH, 0)
            mate = get_inventory_value(b.id, "venus_bolt_mate", None)
            mo = to_object(mate) if mate and object_exists(mate) else None
            if mo is not None:
                bd.set("target_id", mate, 0)
                bd.set("target_pos_x", mo.pos.x, 0)
                bd.set("target_pos_y", mo.pos.y, 0)
                bd.set("target_pos_z", mo.pos.z, 0)
                n += 1
        except Exception:
            pass
    return n


def venus_cloud_puff(x, y, z, diameter, cover=True):
    """A plain cloud: an engine nebula alone - no mesh (a mesh puff reads as a hard slab,
    and the engine ignores mesh alpha). Cover like any cloud. Returns its id."""
    return venus_nebula(x, y, z, diameter, VENUS_BODY_DENSITY, venus_cloud_color(None), cover=cover)


def venus_cloud_scale(obj, scale):
    """Set a cloud's per-axis scale and remember it (depletion shrinks FROM it)."""
    from sbs_utils.procedural.inventory import set_inventory_value
    sx, sy, sz = scale
    try:
        ds = obj.data_set
        ds.set("local_scale_x_coeff", sx, 0)
        ds.set("local_scale_y_coeff", sy, 0)
        ds.set("local_scale_z_coeff", sz, 0)
        set_inventory_value(obj.id, "venus_scale", (sx, sy, sz))
    except Exception:
        pass


# The haze inside each mesh cloud, tinted by what the cloud IS, as emission (r, g, b) and
# an absorption scale. The engine ignores a mesh's diffuse ALPHA (measured 2026-09-25:
# noise alpha on the cloud textures changed nothing), so a soft edge has to come from a
# nebula around the mesh instead.
VENUS_CLOUD_TINTS = {
    # kind: (emission rgb, absorption scale, scattering scale). The nebula IS the cloud body
    # now (the meshes keep only what is inside). Resource clouds glow more than plain cloud
    # (user: "the resource ones can be more emissive"); a storm is dark but scatters hard,
    # so its lightning lights it up from inside.
    None:        ((0.95, 0.86, 0.62), 1.2, 1.0),   # plain cloud: warm, NOT white - nebulae ADD
    "coolant":   ((1.4, 1.8, 2.3), 1.0, 1.0),      # ice
    "fuel":      ((2.3, 2.0, 0.6), 1.0, 1.0),      # sulfur
    "materials": ((1.6, 1.15, 0.75), 1.3, 1.0),    # ore dust
    "medicine":  ((1.1, 2.1, 1.0), 1.0, 1.0),      # spores
    "aether":    ((1.8, 1.1, 2.4), 1.0, 1.0),      # aether
    "salvage":   ((1.3, 1.25, 1.2), 1.2, 1.0),     # wreck haze
    "storm":     ((0.22, 0.22, 0.3), 2.6, 1.6),    # storm cell: dark, thick, scattering
}
VENUS_COVER_ROLE = "venus_cover"  # nebulae that hide a ship (the cloud base); halos do not
VENUS_MURK_TOP = -600.0            # the top of the cloud base: ships ride just above it
VENUS_BODY_SPAN = 2.8              # a cloud's nebula body, as a multiple of its radius
VENUS_BODY_DENSITY = 0.8
VENUS_HALO_SPAN = 5.0              # halo diameter as a multiple of the cloud's radius
VENUS_HALO_DENSITY = 0.55          # 0.35 did not show at all, 0.7 was a wall at 4x (user, 2026-09-25)
VENUS_STORM_DENSITY = 1.4


def venus_cloud_color(kind=None):
    """A Venus cloud as an engine nebula color: the library's white, warmed and made to
    scatter more, tinted for `kind` (a resource, "storm", or None for plain cloud). A fresh
    dict per call: swirl, warp and anisotropy are drawn per nebula so no two bank alike."""
    (er, eg, eb), absorb, scat = VENUS_CLOUD_TINTS.get(kind, VENUS_CLOUD_TINTS[None])
    return {
        "display_text": "cloud" if kind is None else str(kind),
        "absorption_red": 0.22 * absorb, "absorption_green": 0.26 * absorb, "absorption_blue": 0.36 * absorb,
        "emission_red": er, "emission_green": eg, "emission_blue": eb,
        "scattering_red": 0.8 * scat, "scattering_green": 0.76 * scat, "scattering_blue": 0.68 * scat,
        "anisotropy": random.uniform(-0.2, 0.1),
        "base_frequency": 1.8, "base_amplitude": 1.1,
        "detail_frequency": 1.3055, "detail_amplitude": 1.1, "detail_lacunarity": 2.43,
        "domain_warp": random.random(), "swirl": random.random() * 10,
    }


def venus_murk_color(depth=0.0):
    """The cloud BASE: Venus's sulfuric murk, not Earth's white cloud. Nebulae are
    ADDITIVE, so dozens of bright ones stacked into pure white; this is dim olive-ochre
    that absorbs blue (sulfur haze) and darkens with `depth` (0 top .. 1 bottom), so the
    deck reads as heavy and dark (user reference, 2026-09-25)."""
    t = max(0.0, min(1.0, float(depth)))
    glow = 1.0 - 0.6 * t
    return {
        "display_text": "murk",
        # olive, not gold: red ~ green, blue about half, and DIM - the first cut (0.62/0.56/
        # 0.24, blue absorbed hard) stacked into saturated gold
        "absorption_red": 0.5 * (1 + t), "absorption_green": 0.5 * (1 + t), "absorption_blue": 0.7 * (1 + t),
        "emission_red": 0.34 * glow, "emission_green": 0.33 * glow, "emission_blue": 0.17 * glow,
        "scattering_red": 0.32, "scattering_green": 0.31, "scattering_blue": 0.2,
        "anisotropy": random.uniform(-0.1, 0.25),
        "base_frequency": 1.2, "base_amplitude": 1.3,
        "detail_frequency": 1.3055, "detail_amplitude": 1.4, "detail_lacunarity": 2.43,
        "domain_warp": random.random(), "swirl": random.random() * 10,
    }


def venus_nebula(x, y, z, diameter, density=0.6, color="yellow", cover=False):
    """An engine nebula of any size (the library setup caps it at 1500). cover=True tags it
    venus_cover, so a ship inside it counts as hidden. Returns its id."""
    from sbs_utils.procedural.spawn import terrain_spawn
    from sbs_utils.procedural.query import to_id
    try:
        from sbs_utils.procedural.terrain import terrain_setup_nebula
        neb = terrain_spawn(x, y, z, None, "#, nebula", "nebula", "behav_nebula")
        neb.blob.set("unselectable", 1)
        terrain_setup_nebula(neb, diameter, density, color)
        for k in ("size", "display_size", "effect_size"):
            neb.blob.set(k, float(diameter))
        if cover:
            from sbs_utils.procedural.roles import add_role
            add_role(to_id(neb), VENUS_COVER_ROLE)
        return to_id(neb)
    except Exception:
        return None


def venus_world_spawn(cx=0.0, cz=0.0, radius=40000.0, lanes=24, resources=10, storms=2, wrecks=3,
                      floor=0, under=0, base=110, mid=40, seed=None):
    """Dress a map. The cloud BASE is nebulae - a soft volume you fly into, and the
    engine's own cover - in two tiers: the cloud sea at the deck (`base`) and a patchier
    layer between the lanes and the floor (`mid`). A few big stratus banks (`floor`) stay
    as landmarks, since haze alone does not show where the floor is from above; `under`
    mesh clouds are off by default (they read as hard slabs). Then lane clouds, resource
    clouds, storm cells and wrecks, which are meshes because they are things you fly TO.
    Returns a short status string."""
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
    # THE MURK: the cloud base is a sea of dim olive nebulae whose TOP sits just under the
    # lanes, so ships ride on it (user, 2026-09-25: "I'd like the ships to be riding on top
    # of that"). Density and darkness grade with depth down past the deck (the library maps
    # a coefficient to shader density as 7.24x, clamped 1.95..20 - ~2.8 is opaque). Each
    # nebula is capped so its top never rises above VENUS_MURK_TOP: the lanes stay clear,
    # and a crew is not "in cover" until it dips into the murk.
    top_y, deep_y = VENUS_MURK_TOP, floor_y - 2500.0
    nebs = 0

    def depth(y):
        return max(0.0, min(1.0, (top_y - y) / (top_y - deep_y)))

    def dens(y):
        return 0.35 + 2.45 * depth(y) ** 1.3

    def murk(y, d):
        d = min(d, 2.0 * (top_y - y))                 # keep its top at or below the surface
        if d < 1200:
            return 0
        return venus_nebula(x, y, z, d, dens(y), venus_murk_color(depth(y)), cover=True) is not None

    for i in range(base):                          # the surface you ride on
        x, z = at(0, radius * 1.15)
        nebs += murk(top_y - rng.uniform(1600, 2600), rng.uniform(3600, 5000))
    for i in range(mid):                           # the body of the murk
        x, z = at(0, radius * 1.15)
        nebs += murk(rng.uniform(floor_y, top_y - 2600), 5000.0)
    for i in range(base // 3):                     # solid below the deck
        x, z = at(0, radius * 1.15)
        nebs += murk(floor_y - rng.uniform(800, 2500), 5000.0)
    for i in range(floor):                         # landmark banks breaking the surface
        x, z = at(0, radius * 1.2)
        n += venus_cloud_spawn("venus_cloud_stratus_bank", x, top_y - rng.uniform(0, 350), z, cover=False,
                               scale=rng.uniform(1.6, 3.6)) is not None
    below = [k for k in plain if "stratus" in k or "cumulus" in k] or plain
    for i in range(under):                         # optional mesh cloud down in the murk
        x, z = at(0, radius * 1.1)
        n += venus_cloud_spawn(rng.choice(below), x, rng.uniform(floor_y + 800, top_y - 800), z, cover=False,
                               scale=rng.uniform(1.2, 3.0)) is not None
    for i in range(lanes):                         # plain cloud: a nebula and nothing else
        x, z = at(radius * 0.1, radius)
        n += venus_cloud_puff(x, rng.uniform(VENUS_MURK_TOP + 900, 3000), z,
                              rng.uniform(1500, 4500)) is not None
    for i in range(resources):
        x, z = at(radius * 0.2, radius)
        n += venus_cloud_spawn(rng.choice(res), x, rng.uniform(VENUS_MURK_TOP + 500, 2500), z) is not None
    for i in range(storms):
        x, z = at(radius * 0.3, radius)
        n += venus_cloud_spawn(rng.choice(storm), x, rng.uniform(VENUS_MURK_TOP + 800, 2000), z) is not None
    for i in range(wrecks):
        x, z = at(radius * 0.3, radius)
        n += venus_cloud_spawn(rng.choice(wreck), x, rng.uniform(-5000, -2000), z) is not None
    return "venus world: " + str(n) + " clouds, " + str(nebs) + " base nebulae"


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
        # The engine's own answer too: the blob lists the nebulae a ship is inside
        # (inside_nebula_count / inside_nebula_id). Only COVER nebulae count - the cloud
        # base. A cloud's halo is scenery: halos are several times the cloud's size, and
        # counting them hid a crew parked at its own Haven inside 5 of them (measured).
        if not inside:
            inside = venus_in_cover_nebula(s)
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
    base = get_inventory_value(cloud.id, "venus_scale", None) or (1.0, 1.0, 1.0)
    f = max(0.35, stock / full)
    venus_cloud_scale(cloud, tuple(b * f for b in base))
    set_inventory_value(cloud.id, "venus_scale", base)      # keep the FULL size as the base
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
