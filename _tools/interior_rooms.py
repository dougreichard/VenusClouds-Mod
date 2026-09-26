"""Lay out a Venus hull's Engineering floor plan on the ENGINE's own hull map.

Damcon teams walk only the cells the engine reports open (is_grid_point_open),
four-connected. v0.2.0 derived the floor from the top-down sprite instead; the engine's map
is narrower and shifted (the same 0.79 disagreement sbs_utils/GRID_REFERENCE.md s2
records for stock hulls), so 53 of 54 plans put a system where no damcon could reach it -
typically the engines, at the stern. So the floor here is the engine's map, captured in
engine_hull_maps.json, and only its largest connected region: a room anywhere else is
unrepairable by construction.

Systems get several nodes each, scaled by hull size - a single-cell engine room was one
damage hit from dead and gave the damcons nothing to work through.
"""
from check_interiors import components, open_cells, check_plan

LEGEND = {"E": "sensors", "d": "fwd-shield", "a": "aft-shield", "T": "torp-tube", "C": "computer",
          "u": "crew-quarters", "s": "crew-mess", "k": "sick-bay", "g": "cargo", "K": "workshop",
          "i": "impulse", "M": "maneuver", "W": "warp", "L": "lift-ring", "h": "shuttle-bay"}


def _clamp(v, lo, hi):
    return max(lo, min(hi, int(round(v))))


def plan_rooms(key, design, cfg, hull_map, ring_cells):
    """The .grid text for one hull.

    hull_map   - the captured engine entry ({"w", "h", "open": [...]}).
    ring_cells - (row, col) near each lift ring; snapped to the nearest reachable cell.
    """
    w, h = hull_map["w"], hull_map["h"]
    comps = components(open_cells(hull_map))
    if not comps:
        raise SystemExit(f"{key}: the engine reports no open interior cells")
    hull = sorted(comps[0])
    rows = [r for r, _ in hull]
    top, bot = min(rows), max(rows)
    grid = [[" "] * w for _ in range(h)]
    for r, c in hull:
        grid[r][c] = "."
    free = set(hull)
    area = len(hull)
    small = area <= 24
    s = area / 150.0          # ~1.0 for a cruiser

    def t(r):
        return (r - top) / max(1, bot - top)

    def take(cands, ch, n):
        got = 0
        for rc in cands:
            if got >= n:
                break
            if rc in free:
                grid[rc[0]][rc[1]] = ch
                free.discard(rc)
                got += 1
        return got

    cx = (w - 1) / 2
    by_center = sorted(hull, key=lambda rc: (abs(rc[1] - cx), rc[0]))
    fwd = sorted(hull, key=lambda rc: (rc[0], abs(rc[1] - cx)))
    aft = sorted(hull, key=lambda rc: (-rc[0], abs(rc[1] - cx)))
    mid = sorted(hull, key=lambda rc: (abs(t(rc[0]) - 0.5), abs(rc[1] - cx)))

    def near(anchor):
        return sorted(hull, key=lambda rc: ((rc[0] - anchor[0]) ** 2 + (rc[1] - anchor[1]) ** 2, rc))

    # Lift rings first: they are where they are, and they are the mod's core system.
    for anchor in ring_cells:
        take(near(anchor), "L", 1 if small else 2)
    if small:
        counts = dict(T=1 if cfg["tubes"] else 0, E=1, d=1, a=1, i=2 if area >= 10 else 1, W=1, M=1)
    else:
        counts = dict(T=_clamp(4 * s, 2, 6) if cfg["tubes"] else 0, E=_clamp(3 * s, 2, 5),
                      d=_clamp(4 * s, 2, 6), a=_clamp(4 * s, 2, 6), i=_clamp(5 * s, 3, 8),
                      W=_clamp(3 * s, 2, 5), M=_clamp(3 * s, 2, 5))
    where = {"T": fwd, "E": fwd, "d": fwd, "a": aft, "i": aft,
             "W": [rc for rc in aft if t(rc[0]) > 0.5] or aft,
             "M": [rc for rc in aft if t(rc[0]) > 0.4] or aft}
    # A small hull runs out of cells: what it cannot fly without goes first.
    order = "iEWMdaT" if small else "TEdaiWM"
    for ch in order:
        take(where[ch], ch, counts[ch])
    if not small:
        take(by_center, "C", _clamp(2 * s, 1, 3))
        take(mid, "k", 1)
        take(mid, "s", max(1, area // 60))
        take(mid, "u", max(2, area // 25))
        take(mid, "K", max(1, area // 50))
        if "cargo" in cfg["roles"] or "tanker" in cfg["roles"]:
            take(mid, "g", 6)
        if design == "carrier":
            take(mid, "h", 4)
    used = sorted({ch for row in grid for ch in row if ch not in " ."})
    for need in (("L", "i") if small else ("L", "E", "i", "W")):
        if need not in used:
            raise SystemExit(f"{key}: the engine's interior ({area} open cells) has no room for {LEGEND[need]}")
    damcons = 1 if small else (3 if area > 120 else 2)
    lines = [f"ship: {key}", "layout: default", f"size: {w}x{h}", f"damcons: {damcons}", "legend:"]
    lines += [f"  {ch}: {LEGEND[ch]}" for ch in used]
    lines.append("---")
    lines += ["".join(row) for row in grid]
    text = "\n".join(lines) + "\n"
    _key, problems = check_plan(text, {key: hull_map})
    if problems:
        raise SystemExit(f"{key}: generated plan fails the reachability check: {problems}")
    return text
