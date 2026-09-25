# Above the Venusian Clouds - smoke, exhaust and lift shimmer, as engine particle emitters.
#
# Where they go comes from the art: the manifest records every stack top (emitters) and
# every lift ring, in the hull's own frame and world units. Fleets that built no stacks
# (deco, atom, solar, bio) vent from the stern instead.
#
# APPEARANCE IS ENGINE-ONLY: the cosmos_dev mock tracks emitter handles but draws nothing,
# so judge these in the engine (VisualTestRange's visual_particles map), never the browser.

# One look per faction ("emitter" in the manifest) plus the ring shimmer, as descriptor
# kwargs for sbs_utils particle_preset_define. Counts are small: every hull carries these.
# ENGINE-JUDGED (Venus_TestRange): an emitter fires EVERY FRAME, so count is per frame and
# anything above 1 floods the view; with no shape the engine spreads particles over the
# whole hull. So: one particle, a cone_y plume. First cut (size ~1.6, lifespan ~45) was
# judged from the HELM view, which sits right on the stacks; from outside the ship it read
# as far too little smoke, so sizes and lifespans are roughly doubled - a trail, not a puff.
VENUS_EMITTER_LOOKS = {
    "steam":   dict(smoke=True, shape="cone_y", color="#eee,#bbb", lifespan=90, image_cell=4, size=3.2, speed=0.5, count=1),
    "exhaust": dict(smoke=True, shape="cone_y", color="#222,#000", lifespan=100, image_cell=4, size=3.6, speed=0.5, count=1),
    "atomic":  dict(smoke=False, shape="cone_y", color="#6f8,#1c9", lifespan=35, image_cell=(0, 3), size=1.2, speed=0.7, count=1),
    "pollen":  dict(smoke=False, shape="cone_y", color="#fe8,#fc4", lifespan=60, image_cell=9, size=0.9, speed=0.35, count=1),
    "spores":  dict(smoke=False, shape="cone_y", color="#3fc,#1a8", lifespan=70, image_cell=9, size=1.0, speed=0.35, count=1),
}
VENUS_MAX_EMITTERS = 4     # smoke/exhaust points per hull
VENUS_MAX_RINGS = 3        # ring shimmers per hull


def _venus_hex(rgb):
    return "#" + "".join("%x" % max(0, min(15, int(round(c * 15)))) for c in rgb)


def _venus_ensure_preset(name, **look):
    from sbs_utils.procedural.particles import particle_preset_get, particle_preset_define
    if particle_preset_get(name) is None:
        particle_preset_define(name, **look)
    return name


def venus_particles_attach(obj):
    """Give a Venus hull its smoke and ring shimmer. Returns the number of emitters set."""
    from sbs_utils.procedural.particles import particle_effect
    info = venus_hull_info(obj)
    if info is None:
        return 0
    fac = venus_faction_info(info["faction"]) or {}
    kind = fac.get("emitter", "steam")
    preset = _venus_ensure_preset("venus_" + kind, align=True, **VENUS_EMITTER_LOOKS.get(kind, VENUS_EMITTER_LOOKS["steam"]))
    ring = _venus_ensure_preset("venus_ring_" + info["faction"].lower(), align=True, smoke=False,
                                color=_venus_hex(fac.get("lift_color", (0.3, 0.85, 1.0))) + ",white",
                                lifespan=14, image_cell=(0, 3), size=0.8, speed=0.15, count=1, shape="cone_y")
    n = 0
    points = [e["pos"] for e in (info.get("emitters") or [])][:VENUS_MAX_EMITTERS]
    if not points and not info.get("station") and info["design"] != "turret":
        points = [info.get("stern") or [0, 0, -info["world_len"] / 2]]
    for i, p in enumerate(points):
        if particle_effect(obj, preset, slot="venus_smoke_" + str(i), priority=1, offset=tuple(p)):
            n += 1
    # A POINT glow just under each ring, not shape ring_y: a ring shape is sized by the
    # HULL (like shape hull), so it drew a hull-wide circle that read as the deck edge.
    for i, r in enumerate((info.get("rings") or [])[:VENUS_MAX_RINGS]):
        p = r["pos"]
        if particle_effect(obj, ring, slot="venus_ring_" + str(i), priority=0,
                           offset=(p[0], p[1] - r["radius"] * 0.6, p[2])):
            n += 1
    return n


def venus_particles_damaged(obj, lift):
    """Smolder once lift is below half; clear it when repaired."""
    from sbs_utils.procedural.particles import particle_effect, particle_effect_clear
    if lift < 0.5:
        particle_effect(obj, "smolder", slot="venus_damage", priority=2)
    else:
        particle_effect_clear(obj, slot="venus_damage")
