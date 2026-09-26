"""Rewrite every venus_ floor plan on the engine's captured hull map, and nothing else.

build_mod.py regenerates the whole mod from the art pipeline; this touches only the .grid
files, so the interiors can be repaired without the art on hand. Lift-ring positions are
taken from each existing plan's `L` cells (one ring per connected group).

    python _tools/regrid.py [--dry-run]
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_interiors import components, load_maps, parse_plan  # noqa: E402
from interior_rooms import plan_rooms  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)


def design_of(key, roles):
    rest = key[len("venus_"):].split("_", 1)[1]
    if rest not in roles:
        raise SystemExit(f"{key}: no balance entry for design {rest!r}")
    return rest


def ring_anchors(rooms):
    anchors = []
    for comp in components(set(rooms.get("L", []))):
        rs = [r for r, _ in comp]
        cs = [c for _, c in comp]
        anchors.append((sum(rs) / len(rs), sum(cs) / len(cs)))
    return anchors


def summary(rooms):
    return " ".join(f"{ch}{len(v)}" for ch, v in sorted(rooms.items()) if ch in "TEdaiWML")


def main():
    dry = "--dry-run" in sys.argv
    maps = load_maps()
    roles = json.load(open(os.path.join(HERE, "balance_targets.json")))["roles"]
    for path in sorted(glob.glob(os.path.join(MOD, "venus_fleets", "*.grid"))):
        with open(path, encoding="utf-8") as f:
            old = f.read()
        key, rooms = parse_plan(old)
        design = design_of(key, roles)
        text = plan_rooms(key, design, roles[design], maps[key], ring_anchors(rooms))
        _k, new_rooms = parse_plan(text)
        print(f"{key:32s} {summary(rooms):28s} -> {summary(new_rooms)}")
        if not dry:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)


if __name__ == "__main__":
    main()
