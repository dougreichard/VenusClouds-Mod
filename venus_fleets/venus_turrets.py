# Above the Venusian Clouds - separate, destructible point-defense turrets.
#
# Carriers, cruisers and stations are exported WITHOUT their guns; the art pipeline records
# where each gun stood (manifest "mounts", in the hull's own frame, world units). On spawn
# the host gets its fleet's turret hull welded at each mount with the engine's tractor weld
# (sbs_utils mount.py) - no per-tick placement - and armed with sbs_utils turret.py.
#
# COST: every turret is another NPC. So the count per host is capped, and ONE server ticker
# (venus_turrets_tick, from __init__.mast) drives every Venus turret instead of a brain per
# turret - brains tick far slower in the engine than documented.

VENUS_TURRET_ROLE = "venus_turret"
VENUS_TURRET_MAX = 6                  # per host
VENUS_TURRET_RANGE = 1400.0
# What point defense shoots: ships and their missiles, never what is hidden in cloud.
VENUS_TURRET_TARGETS = "(__player__ | ship | shuttle | fighter | cockpit | drone | torpedo) - venus_in_cloud"
VENUS_TURRET_SCALE = True             # size each turret to the gun it replaces (local_scale_coeff)


def _venus_pick(mounts, n):
    """n mounts spread evenly through the list (the art records them bow to stern)."""
    if len(mounts) <= n:
        return list(mounts)
    step = len(mounts) / float(n)
    return [mounts[int(i * step)] for i in range(n)]


def venus_turrets_attach(host):
    """Weld the host's turrets on. Returns the ids created (possibly empty).

    A station whose art recorded no guns still gets a ring of four, so every station can
    defend itself; a ship with no mounts gets none.
    """
    from sbs_utils.procedural.query import to_object, to_id
    from sbs_utils.procedural.mount import mount_spawn, mount_ring
    from sbs_utils.procedural.turret import turret_make
    from sbs_utils.procedural.roles import add_role
    obj = to_object(host)
    info = venus_hull_info(obj)
    if obj is None or info is None:
        return []
    fac = venus_faction_info(info["faction"]) or {}
    key = fac.get("turret")
    if not key:
        return []
    side = obj.side
    ids = []
    mounts = _venus_pick(info.get("mounts") or [], VENUS_TURRET_MAX)
    if mounts:
        for m in mounts:
            mid = mount_spawn(obj, key, offset=tuple(m["pos"]), side=side)
            if mid is not None:
                ids.append(mid)
                if VENUS_TURRET_SCALE and fac.get("turret_ref"):
                    _venus_scale(mid, m["size"] * fac["turret_ref"])
    elif info.get("station"):
        ids = mount_ring(obj, key, 4, radius=info["world_len"] * 0.42, side=side) or []
    for mid in ids:
        turret_make(mid, range=VENUS_TURRET_RANGE, targets=VENUS_TURRET_TARGETS)
        add_role(mid, VENUS_TURRET_ROLE)
    obj.set_inventory_value("venus_turret_art", obj.art_id)
    return ids


def venus_turrets_sync(host):
    """Keep a host's turrets matching the host. Returns the number of turrets changed.

    A crew is RE-HULLED and RE-SIDED after its turrets are welded: a map's Crew: block seats
    one hull, then the mission seats the faction's cruiser and sets its side. The turrets
    kept the first side - hostile to their own ship, so they shot it (user report, Brood) -
    and the first hull's mount points. So: a new hull re-welds from scratch; a new side
    re-sides every turret.
    """
    from sbs_utils.procedural.query import to_object
    from sbs_utils.procedural.mount import mount_list, mount_detach_all
    obj = to_object(host)
    if obj is None:
        return 0
    welded_for = obj.get_inventory_value("venus_turret_art", None)
    if welded_for is None:
        return 0
    if welded_for != obj.art_id:
        mount_detach_all(obj, delete=True)
        obj.set_inventory_value("venus_turret_art", None)
        info = venus_hull_info(obj)
        if info is not None and info["design"] in VENUS_TURRET_HOSTS:
            return len(venus_turrets_attach(obj))
        return 0
    n = 0
    side = obj.side
    for mid in mount_list(obj) or []:
        t = to_object(mid)
        if t is not None and t.side != side:
            t.side = side
            n += 1
    return n


def _venus_scale(obj_id, coeff):
    """Size a welded turret to the gun it replaces. Clamped: an odd mount must not produce
    a turret larger than a frigate. local_scale_coeff is how LM monsters are sized."""
    from sbs_utils.procedural.query import to_object
    coeff = max(0.4, min(3.0, float(coeff)))
    try:
        to_object(obj_id).data_set.set("local_scale_coeff", coeff, 0)
    except Exception:
        pass


def venus_turrets_tick():
    """Acquire and engage for every Venus turret. Called on a timer by the server ticker."""
    from sbs_utils.procedural.turret import turret_tick
    from sbs_utils.procedural.roles import role
    n = 0
    for tid in role(VENUS_TURRET_ROLE):
        try:
            turret_tick(tid)
            n += 1
        except Exception:
            pass
    return n
