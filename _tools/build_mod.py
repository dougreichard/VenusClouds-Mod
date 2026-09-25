"""Build the mod's data from the art pipeline. Run from anywhere with the dev Python:

    python _tools/build_mod.py [--art E:/ai/art] [--no-copy]

Everything it writes is GENERATED - edit balance_targets.json or the art, never the output:

    media/ships/<fleet>/<design>.obj + textures       copied from <art>/<fleet>/mod/<design>/cosmos
    media/ships/clouds/<cloud>.obj + textures          copied from <art>/terrain/out/<cloud>/cosmos
    media/venus_ships.json                             every hull, HJSON-valid JSON
    venus_fleets/venus_<tag>_<design>.grid             interiors of the flyable hulls
    venus_fleets/venus_<tag>_fleets.json               fleet ladders
    venus_fleets/venus_manifest.json                   what the runtime needs to know per key

Rules this obeys (see the making-a-mod skill): quoted keys, LF endings and a final newline;
ONE ship file (no .yaml beside the .json); every entry keeps hull_port_sets and
torpedostart; artfileroot is the full pack path, which carries the version, so bumping
__lib__.json means rebuilding; derived art (paxmesh, 1024/256 sprites) is never copied.
Running it twice must produce identical bytes - main() checks that with an md5.
"""
import argparse, hashlib, json, math, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)
OWNER = "artemis-sbs"
REPO = "VenusClouds-Mod"
ADDON = "venus_fleets"

DESIGNS = ["carrier", "cruiser", "destroyer", "frigate", "cargo_barge", "steam_tender", "fighter", "launch", "tug",
           "station_command", "station_industrial", "station_civil", "station_science", "turret"]
DERIVED = (".paxmesh", ".pointcube", ".rawbitmap")
PRETTY = {"cargo_barge": "Cargo Barge", "steam_tender": "Tender", "station_command": "Command Station",
          "station_industrial": "Industrial Station", "station_civil": "Civil Station",
          "station_science": "Science Station"}


def dump(path, obj):
    """JSON the engine's HJSON reader accepts: quoted keys, LF, final newline."""
    text = json.dumps(obj, indent=2, ensure_ascii=True) + "\n"
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write(text)
    return text


def obj_extent(path):
    lo = [1e9] * 3
    hi = [-1e9] * 3
    with open(path) as fh:
        for line in fh:
            if line.startswith("v "):
                v = [float(c) for c in line.split()[1:4]]
                lo = [min(a, b) for a, b in zip(lo, v)]
                hi = [max(a, b) for a, b in zip(hi, v)]
    return lo, hi


def design_target_len(art, cloud):
    """TARGET_LEN from a terrain recipe (E:/ai/art/terrain/designs/<cloud>.py), or None."""
    import re
    path = os.path.join(art, "terrain", "designs", cloud + ".py")
    try:
        m = re.search(r"^TARGET_LEN\s*=\s*([0-9.]+)", open(path, encoding="utf-8").read(), re.M)
    except OSError:
        return None
    return float(m.group(1)) if m else None


def copy_art(src_dir, dst_dir, root):
    """The engine-read files of one art set. Radar sprites are derived art: the engine
    bakes them from the .obj on first draw, so shipping ours would only go stale."""
    os.makedirs(dst_dir, exist_ok=True)
    for f in sorted(os.listdir(src_dir)):
        if f.endswith(DERIVED) or f in (f"{root}1024.png", f"{root}256.png") or ".blend" in f \
                or f.startswith("verify_") or f.endswith("_points.json"):
            continue
        shutil.copyfile(os.path.join(src_dir, f), os.path.join(dst_dir, f))


# --------------------------------------------------------------------------- grids
def silhouette(sprite, span, w, h):
    """The hull outline as a w x h grid, from the top-down sprite the art pipeline renders
    (the same alpha shape the engine cuts its Engineering hull map from). Top row = bow.
    Returns (cells, to_cell) where to_cell maps an engine-space (x, z) to a (col, row)."""
    from PIL import Image
    im = Image.open(sprite).convert("RGBA")
    a = im.getchannel("A")
    box = a.getbbox()
    S = im.width
    crop = a.crop(box).resize((w, h), Image.BOX)
    px = crop.load()
    cells = [[px[c, r] > 70 for c in range(w)] for r in range(h)]
    ortho = span * 1.1

    def to_cell(x, z):
        u = S / 2 + (-x) / ortho * S          # the sprite camera looks down with engine -X to the right
        v = S / 2 - z / ortho * S              # and +Z (the bow) up
        col = int((u - box[0]) / (box[2] - box[0]) * w)
        row = int((v - box[1]) / (box[3] - box[1]) * h)
        return max(0, min(w - 1, col)), max(0, min(h - 1, row))
    return cells, to_cell


def close_gaps(cells, gap=2):
    """Bridge short runs of off-hull cells between hull cells, row and column - thin pylons
    render as gaps at grid resolution and would cut a nacelle off from the hull."""
    h, w = len(cells), len(cells[0])
    out = [row[:] for row in cells]
    for r in range(h):
        on = [c for c in range(w) if cells[r][c]]
        for a, b in zip(on, on[1:]):
            if 1 < b - a <= gap + 1:
                for c in range(a + 1, b):
                    out[r][c] = True
    for c in range(w):
        on = [r for r in range(h) if cells[r][c]]
        for a, b in zip(on, on[1:]):
            if 1 < b - a <= gap + 1:
                for r in range(a + 1, b):
                    out[r][c] = True
    return out


def keep_largest(cells):
    h, w = len(cells), len(cells[0])
    seen = set()
    best = []
    for r in range(h):
        for c in range(w):
            if cells[r][c] and (r, c) not in seen:
                comp, stack = [], [(r, c)]
                seen.add((r, c))
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and cells[ny][nx] and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                if len(comp) > len(best):
                    best = comp
    keep = set(best)
    return [[(r, c) in keep for c in range(w)] for r in range(h)]


LEGEND = {"E": "sensors", "d": "fwd-shield", "a": "aft-shield", "T": "torp-tube", "C": "computer",
          "u": "crew-quarters", "s": "crew-mess", "k": "sick-bay", "g": "cargo", "K": "workshop",
          "i": "impulse", "M": "maneuver", "W": "warp", "L": "lift-ring", "h": "shuttle-bay"}


def make_grid(key, role, cfg, sprite, span, rings):
    w, h = cfg["grid"]
    cells, to_cell = silhouette(sprite, span, w, h)
    cells = keep_largest(close_gaps(cells))
    hull = [(r, c) for r in range(h) for c in range(w) if cells[r][c]]
    rows = [r for r, _ in hull]
    top, bot = min(rows), max(rows)
    grid = [[" " if not cells[r][c] else "." for c in range(w)] for r in range(h)]
    free = set(hull)

    def t(r):
        return (r - top) / max(1, bot - top)

    def take(cands, ch, n):
        """Paint the first n free cells of cands (in order)."""
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
    small = w * h <= 60

    # lift rings first: they are where they are, and they are the mod's core system
    for x, y, z, R in rings:
        c, r = to_cell(x, z)
        near = sorted(hull, key=lambda rc: (rc[0] - r) ** 2 + (rc[1] - c) ** 2)
        take(near, "L", 1 if small else 2)
    tubes = cfg["tubes"]
    if tubes:
        take(fwd, "T", max(1, min(tubes, 4)))
    take(fwd, "E", 1 if small else 2)
    take(fwd, "d", 1 if small else 2)
    take(aft, "a", 1 if small else 2)
    take(aft, "i", 1 if small else 2)
    take([rc for rc in aft if t(rc[0]) > 0.5], "W", 1)
    take([rc for rc in aft if t(rc[0]) > 0.4], "M", 1 if small else 2)
    if not small:
        take(by_center, "C", 1)
        take(mid, "k", 1)
        area = len(hull)
        take(mid, "s", max(1, area // 60))
        take(mid, "u", max(2, area // 25))
        take(mid, "K", max(1, area // 50))
        if "cargo" in cfg["roles"] or "tanker" in cfg["roles"]:
            take(mid, "g", 6)
        if role == "carrier":
            take(mid, "h", 4)
    used = sorted({ch for row in grid for ch in row if ch not in " ."})
    for need in (("L", "i") if small else ("L", "E", "i", "W")):
        if need not in used:
            raise SystemExit(f"{key}: grid has no room for {LEGEND[need]} ({w}x{h} too small)")
    damcons = 1 if small else (3 if w * h > 250 else 2)
    lines = [f"ship: {key}", "layout: default", f"size: {w}x{h}", f"damcons: {damcons}", "legend:"]
    lines += [f"  {ch}: {LEGEND[ch]}" for ch in used]
    lines.append("---")
    lines += ["".join(row) for row in grid]
    return "\n".join(lines) + "\n", (w, h)


# --------------------------------------------------------------------------- ship entries
def zero_beam():
    """Missiles only - but a hull without hull_port_sets has crashed the engine at load,
    so the beam set stays, zeroed, as LM's lm_turret_crate does it."""
    return {"beam Primary Beams": [{"position": [0, 0, 0], "color": "white", "arccolor": "#090", "cycle_time": 60,
                                    "damage_coeff": 0, "range": 0, "arcwidth": 360, "barrel_angle": 0}]}


def flak_beam(color):
    return {"beam Primary Beams": [{"position": [0, 0.5, 0], "color": color, "arccolor": "#090", "cycle_time": 3,
                                    "damage_coeff": 0.4, "range": 1200, "arcwidth": 360, "barrel_angle": 0}]}


def hexcolor(rgb):
    return "#" + "".join(f"{max(0, min(15, round(c * 15))):x}" for c in rgb)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--art", default="E:/ai/art")
    ap.add_argument("--no-copy", action="store_true")
    args = ap.parse_args()

    lib = json.load(open(os.path.join(MOD, "__lib__.json")))
    version = lib["version"]
    pack = f"data/missions/__lib__/media/{OWNER}.{REPO}.media.{version}"
    bal = json.load(open(os.path.join(HERE, "balance_targets.json")))
    media = os.path.join(MOD, "media")
    addon = os.path.join(MOD, ADDON)
    os.makedirs(os.path.join(media, "ships"), exist_ok=True)
    os.makedirs(addon, exist_ok=True)

    ships = []
    manifest = {"mod": "Above the Venusian Clouds", "version": version, "addon": ADDON,
                "factions": {}, "hulls": {}, "clouds": {}, "interiors": {}, "fleets": {}}
    for fleet, fc in bal["fleets"].items():
        tag, race = fc["tag"], fc["race"]
        manifest["factions"][race] = {"fleet": fleet, "tag": tag, "name": fc["faction"], "lore": fc["lore"],
                                      "emitter": fc["emitter"], "lift_color": fc["lift_color"],
                                      "turret": f"venus_{tag}_turret"}
        interiors = []
        for design in DESIGNS:
            rc = bal["roles"][design]
            src = os.path.join(args.art, fleet, "mod", design, "cosmos")
            obj = os.path.join(src, f"{design}.obj")
            if not os.path.exists(obj):
                raise SystemExit(f"missing art: {obj} (run SKY_MOD=1 run.sh for {fleet})")
            key = f"venus_{tag}_{design}"
            if not args.no_copy:
                copy_art(src, os.path.join(media, "ships", fleet), design)
            lo, hi = obj_extent(obj)
            span_xz = max(hi[0] - lo[0], hi[2] - lo[2])
            meshscale = rc["world_len"] / span_xz
            station = design.startswith("station")
            excl = 0.0 if design == "turret" else max(25.0, (0.4 if station else 0.52) * rc["world_len"])
            pts = json.load(open(os.path.join(src, f"{design}_points.json")))
            if design == "turret":
                # how big a welded turret must be scaled to match the gun it replaces:
                # coeff = mount size (world) * this. The turret design builds its gun at
                # size 1.4 (diesel 1.2) - see <art>/<fleet>/designs/turret.py.
                gun_param = 1.2 if fleet == "dieselpunk" else 1.4
                blender_extent = span_xz / pts["scale"]
                manifest["factions"][race]["turret_ref"] = round(blender_extent / (gun_param * rc["world_len"]), 4)
            entry = {
                "key": key, "name": f"{fc['faction']} {PRETTY.get(design, design.title())}",
                "origin": race, "side": race,
                "artfileroot": f"{pack}/ships/{fleet}/{design}",
                "meshscale": round(meshscale, 6), "radarscale": 1.0 if not design == "fighter" else 0.4,
                "exclusionradius": round(excl, 2), "meshrotate": 0,
                "long_desc": f"{fc['faction']} {PRETTY.get(design, design.title())}^{rc['long']}^{fc['lore']}",
                "tubecount": rc["tubes"],
                "torpedostart": [{k: v} for k, v in rc["torps"].items()],
                "internalmapscale": 1.0, "internalmapw": 4, "internalmaph": 4, "internalsymmetry": 1,
                "turn_rate": round(rc["turn"] * fc["turn"], 3), "speed_coeff": round(rc["speed"] * fc["speed"], 3),
                "scan_strength_coeff": 1, "ship_energy_cost": 1, "warp_energy_cost": 1, "jump_energy_cost": 2,
                "roles": rc["roles"],
                "shields": [round(s * fc["shield"]) for s in rc["shields"]],
                "hullpoints": max(1, round(rc["hull"] * fc["hull"])),
                "hull_port_sets": flak_beam(hexcolor(fc["lift_color"])) if design == "turret" else zero_beam(),
            }
            if rc["drone_timer"]:
                entry["drone_launch_timer"] = rc["drone_timer"]
            if design == "carrier":
                entry["baycount"] = 4
            grid_file = None
            if rc["flyable"]:
                sprite = os.path.join(src, f"{design}1024.png")
                text, (gw, gh) = make_grid(key, design, rc, sprite, span_xz, [
                    (r["pos"][0], r["pos"][1], r["pos"][2], r["radius"]) for r in pts["rings"]])
                grid_file = f"{key}.grid"
                with open(os.path.join(addon, grid_file), "w", newline="\n") as fh:
                    fh.write(text)
                entry["internalmapw"], entry["internalmaph"] = gw, gh
                interiors.append(grid_file)
            ships.append(entry)
            # points in WORLD units in the hull's own frame (+Z bow, +Y up)
            s = meshscale

            def w(p):
                return [round(c * s, 2) for c in p]
            manifest["hulls"][key] = {
                "faction": race, "fleet": fleet, "design": design, "world_len": rc["world_len"],
                "grid": grid_file, "station": station,
                "rings": [{"pos": w(r["pos"]), "radius": round(r["radius"] * s, 2)} for r in pts["rings"]],
                "emitters": [{"pos": w(e["pos"]), "size": round(e["size"] * s, 2)} for e in pts["emitters"]],
                "mounts": [{"pos": w(m["pos"]), "size": round(m["size"] * s, 2), "facing": m["facing"]}
                           for m in pts["mounts"]],
                "stern": w([0, 0, lo[2]]),
            }
        manifest["interiors"][race] = interiors
        # ladders: weight climbs with difficulty; civilians never appear in a war ladder
        f, d, c, cv = (f"venus_{tag}_{x}" for x in ("frigate", "destroyer", "cruiser", "carrier"))
        tiers = [[[f]], [[f, f]], [[d]], [[d, f]], [[d, d]], [[c]], [[c, f]], [[c, d]], [[c, d, f]],
                 [[cv, d]], [[cv, c, d]]]
        ladder = {"race": race, "fleets": tiers}
        dump(os.path.join(addon, f"venus_{tag}_fleets.json"), ladder)
        manifest["fleets"][race] = f"venus_{tag}_fleets.json"

    # clouds: passive terrain the ships fly through (exclusionradius 0)
    for cloud, cc in bal["clouds"].items():
        src = os.path.join(args.art, "terrain", "out", cloud, "cosmos")
        obj = os.path.join(src, f"{cloud}.obj")
        if not args.no_copy:
            copy_art(src, os.path.join(media, "ships", "clouds"), cloud)
        # The OBJ is exported at its recipe's TARGET_LEN, so that - not the measured extent -
        # is its span. A cloud exported without its body (SKY_NO_BODY: the puff is a nebula in
        # game) measures only its crystals or bolts, and would be blown up to fill the whole
        # cloud's world_len.
        span_xz = design_target_len(args.art, cloud)
        if span_xz is None:
            lo, hi = obj_extent(obj)
            span_xz = max(hi[0] - lo[0], hi[2] - lo[2])
        key = f"venus_cloud_{cloud}"
        roles = "terrain,cloud" + (",resource," + cc["resource"] if cc["resource"] else "") + \
            (",storm" if cc["storm"] else "")
        ships.append({
            "key": key, "name": cloud.replace("_", " ").title(), "origin": "Venus", "side": "Venus",
            "artfileroot": f"{pack}/ships/clouds/{cloud}", "meshscale": round(cc["world_len"] / span_xz, 6),
            "radarscale": 1.0, "exclusionradius": 0.0, "meshrotate": 0,
            "long_desc": cloud.replace("_", " ").title(), "tubecount": 0, "torpedostart": [],
            "internalmapscale": 1.0, "internalmapw": 4, "internalmaph": 4, "internalsymmetry": 1,
            "roles": roles, "shields": [0], "hullpoints": 9999, "hull_port_sets": zero_beam(),
        })
        manifest["clouds"][key] = {"world_len": cc["world_len"], "resource": cc["resource"],
                                   "storm": cc["storm"],
                                   "radius": round(cc["world_len"] / 2 * 0.8, 1)}

    text = dump(os.path.join(media, "venus_ships.json"), {"#ship-list": ships})
    for stale in ("venus_ships.yaml", "venus_ships.hjson"):
        if os.path.exists(os.path.join(media, stale)):
            raise SystemExit(f"media/{stale} beside venus_ships.json - the engine would read it first")
    manifest["hull_count"] = len(ships)
    mtext = dump(os.path.join(addon, "venus_manifest.json"), manifest)
    print(f"{len(ships)} hulls  ships md5 {hashlib.md5(text.encode()).hexdigest()[:10]}  "
          f"manifest md5 {hashlib.md5(mtext.encode()).hexdigest()[:10]}  "
          f"interiors {sum(len(v) for v in manifest['interiors'].values())}")


if __name__ == "__main__":
    main()
