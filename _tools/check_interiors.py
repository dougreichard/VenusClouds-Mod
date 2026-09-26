"""Check every venus_ floor plan against the ENGINE's hull map.

Damcon teams walk only cells the engine reports open (is_grid_point_open), four-connected.
A plan cell on a closed cell does not exist for them, and a system room outside the ship's
main open region can never be repaired. The engine's map is captured, not derived (see
engine_hull_maps.json and Venus_TestRange/venus_hullmap.py).

    python _tools/check_interiors.py            # report
    python _tools/check_interiors.py --strict   # exit 1 on any unreachable system

Also imported by build_mod.py, which refuses to write a plan that fails.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)
MAPS = os.path.join(HERE, "engine_hull_maps.json")


def load_maps(path=MAPS):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if isinstance(v, dict) and "open" in v}


def open_cells(entry):
    return {(r, c) for r, row in enumerate(entry["open"]) for c, ch in enumerate(row) if ch == "#"}


def components(cells):
    """Four-connected components of a set of (row, col), largest first."""
    left, out = set(cells), []
    while left:
        start = left.pop()
        comp, stack = {start}, [start]
        while stack:
            r, c = stack.pop()
            for n in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if n in left:
                    left.discard(n)
                    comp.add(n)
                    stack.append(n)
        out.append(comp)
    return sorted(out, key=len, reverse=True)


def parse_plan(text):
    key = re.search(r"^ship:\s*(\S+)", text, re.M).group(1)
    body = text.split("\n---\n", 1)[1].rstrip("\n").split("\n")
    rooms = {}
    for r, row in enumerate(body):
        for c, ch in enumerate(row):
            if ch not in " .":
                rooms.setdefault(ch, []).append((r, c))
    return key, rooms


def check_plan(text, maps):
    """Returns (key, problems) - problems is a list of strings, empty when the plan is sound."""
    key, rooms = parse_plan(text)
    entry = maps.get(key)
    if entry is None:
        return key, ["no engine hull map captured"]
    opened = open_cells(entry)
    comps = components(opened)
    main = comps[0] if comps else set()
    problems = []
    for ch, cells in sorted(rooms.items()):
        on_closed = [rc for rc in cells if rc not in opened]
        stranded = [rc for rc in cells if rc in opened and rc not in main]
        reachable = [rc for rc in cells if rc in main]
        if not reachable:
            problems.append(f"{ch}: no reachable cell ({len(on_closed)} on closed cells, {len(stranded)} stranded)")
        elif on_closed or stranded:
            problems.append(f"{ch}: {len(on_closed)} cell(s) on closed cells, {len(stranded)} stranded "
                            f"({len(reachable)} ok)")
    return key, problems


def main():
    maps = load_maps()
    bad = 0
    for path in sorted(glob.glob(os.path.join(MOD, "venus_fleets", "*.grid"))):
        with open(path, encoding="utf-8") as f:
            key, problems = check_plan(f.read(), maps)
        if problems:
            bad += any("no reachable" in p for p in problems)
            print(f"{key}:")
            for p in problems:
                print(f"    {p}")
    print(f"{bad} plan(s) with a system nobody can reach")
    return 1 if bad and "--strict" in sys.argv else 0


if __name__ == "__main__":
    sys.exit(main())
