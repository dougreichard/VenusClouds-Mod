# Venus Clouds

A sky-kingdom setting for Artemis Cosmos: dirigibles, sky cities and pirates in the cloud
deck of Venus. Nineteen hulls across three factions, six skies, and two fleet ladders,
**declared** as an add-on rather than unzipped over the game folder.

Nothing in the game install is touched, and nothing is written into a mission folder.

## The setting

Two fleets with mirrored ladders, from the concept art in `E:\a\venus_clouds`:

| | Kingdom | Armada |
|---|---|---|
| looks like | brass, gold domes, paddle-wheels | salvage plating, red plasma, spikes |
| fights by | armor and weight of shell | speed, numbers, boarding and ramming |
| capital | Imperial Bulwark | Black-Tide |
| heavy | Golden Vanguard | Blood Hawk |
| escort | Valiant | Black Sails |
| special | Thunderbolt (rail-cannon gunboat) | Nighthawk (stealth) |
| logistics | Mender, Gold-Harvest | Scrap King, Scavenger |
| platforms | Skyward Citadel, Observatory Sky-Dome, Harvester's Reach, Mender's Berth | Armada Hub |

Plus the **Guild** - the free cities, hostile to nobody, which is the point: they sell
lifting gas to whoever moors, and the drama is what the two fleets are willing to do about
that. A mission that wants the Guild to pick a side should flip it at runtime with
`side_set_relations`, so the choice belongs to the mission and not to this mastlib.

The stats express that asymmetry rather than sitting at stock values: Kingdom hulls run
`speed_coeff` 0.40-0.70 with turn rates as low as 0.24, Armada hulls 1.15-1.35 and far less
hull. An Imperial Bulwark does not maneuver; it arrives.

### Altitude is the axis space does not have

The one thing this setting has that a starfield does not is a **floor and a ceiling**. Down
is pressure and heat; up is air too thin to hold lift. That is not decoration - it is the
tactical dial the whole setting turns on, and it is why the skies below are not
interchangeable and why the platforms matter (they are the only places you can stop).

Not implemented yet. It wants a lethal-proximity ticker on `y`, the same shape as the
black-hole gravity fix, and it belongs in the MISSION rather than in this mod.

## Layout: who reads it decides where it lives

The useful split is not "art vs code". It is **what the ENGINE opens** (needs a real file on
a real disk) versus **what MAST reads** (perfectly happy inside a zip).

```
VenusClouds-Mod/
  __lib__.json          {"version":"v0.1.0","mastlib":["venus_races"],"zip":["media"]}
  media/                -> <owner>.VenusClouds-Mod.media.v0.1.0.zip
    venus_ships.yaml       19 hulls: the ENGINE opens this one itself
    skybox/                venus_sky_*.png  x6, 4096x3072, 13 MB total
    ships/                 (empty until mod-carried art works - see below)
  venus_races/          -> <owner>.VenusClouds-Mod.venus_races.v0.1.0.mastlib  (FLAT)
    __init__.mast          load order, gates, the create_sides route
    venus_setup.py         race registration, ship declaration, manifest gates
    venus_sides.amd        three factions + diplomacy
    venus_skies.mast       the six @media/skybox labels
    venus_skies.py         did the art arrive?
    venus_manifest.json    which interiors and ladders belong to which faction
    venus_*_fleets.yaml    x2, eleven difficulty tiers each
    venus_*.grid           x8, one floor plan per flyable hull
  _build_ships.py       regenerates venus_ships.yaml from stock + deltas
  _gen_skybox.py        regenerates the six skies
  _calibrate_cross.py   MEASURES the cross layout the skies have to match
```

A mission takes the mod with two lines in `story.json`:

```json
"mastlib":      [ "<owner>.VenusClouds-Mod.venus_races.v0.1.0.mastlib" ],
"shared_media": [ "<owner>.VenusClouds-Mod.media.v0.1.0.zip" ]
```

**Forgetting the second line is silent.** A `@media/skybox` label whose PNG is missing tests
False, drops out of the random pick, and says nothing; the hulls lose their ship data the
same quiet way. `__init__.mast` therefore counts both at load, logs them, and publishes
`VENUS_SKYBOX_COUNT` and `VENUS_MOD_VERSION` as shared variables for a test range to assert.

## The hulls wear borrowed art, and that is deliberate

`artfileroot` on every entry points at a **stock** mesh that already exists in
`data/graphics/ships`, not at this mod's own `VEN_*` art.

That is a safety requirement, not laziness. **An unresolvable `artfileroot` segfaults the
engine at render** (reproduced 4/4), so a mod that declares hulls pointing at art the engine
cannot reach crashes any mission that spawns one. `_build_ships.py` checks every borrowed
root against the `.paxmesh` files actually present and refuses to write a list that would
crash.

**Mod-carried art does not work on the current build at all.** Re-measured on the 2026-08-05
dev engine (write-up appended to `VisualTestRange/ENGINE_BUG_derived_art_generation.md`):

| case | result |
|---|---|
| stock-art map, no mod art | runs clean |
| complete art set in a mod folder via `artfilepath` | **segfault, 2/2** - a regression |
| source-only art in a mod folder | segfault, writes `<root>1024.png` first |
| source art staged in `data/graphics/ships` | **works** - generates `.paxmesh`, `.pointcube` |

So the only route that renders custom hulls today is installing the art into the game, which
is exactly what an add-on is supposed to avoid. The mod is built to be ready rather than to
pretend: each entry records the art it wants as `venus_art` (a field the engine ignores),
and `_build_ships.py --venus-art` swaps every root over in one rebuild.

Generating the meshes is not the blocker. The prop farm on the 3090 box does
ref -> shape -> paint -> finalize with a PBR track and a REST API, and already has a
`to_fbx` converter to model a `to_cosmos` one on (OBJ + the four maps). It is worth pointing
at the schematic sheets as IPAdapter style refs so twenty hulls read as one fleet. What is
missing is an engine that will load the result.

## The skies

Six of them, and they are **not interchangeable** - the altitude gradient is the most
important thing this art says, because it tells the player which way is down.

| label | when to use it |
|---|---|
| `venus_sky_high_haze` | the thin bright air at the top of the world |
| `venus_sky_midday` | the working altitude - the trade lanes |
| `venus_sky_dusk` | the terminator; the classic Kingdom postcard |
| `venus_sky_stormwall` | a convective wall; something has gone wrong |
| `venus_sky_deep` | below the lanes, where salvage and pirates live |
| `venus_sky_nightside` | no sun at all, only the glow of the deck |

They are **procedural, not generated**. A skybox has to be seamless across twelve cube edges
and both poles, and six independently diffused faces are not - the join is the one defect
you cannot unsee once the ship turns. Here every pixel is a pure function of its 3D
direction, so continuity is structural. Six full-resolution 4096x3072 skies come to 13 MB,
because smooth gradients deflate well; the whole set is smaller than two stock skies.

### The cross layout was measured twice, because the first answer was wrong

Cosmos wants one image: a 4x3 cross. Which of the twelve cells hold faces is easy to measure
(`sky1.png` and the A28 pack agree exactly). **Which face goes in which cell, at what
rotation, is not**, and taking it from prose produced six skies rotated 90 degrees.

**The border score is necessary but NOT sufficient, and that cost a third regeneration.**
The cross image exposes only **five of the cube's twelve edges** - the other seven are cut
by the unfolding. A version that fitted a rotation-and-mirror per face scored 0.59 there,
better than `sky1.png`, and still seamed visibly in game, because three of its faces were
**mirrored**: a mirror flips that face's handedness, so the five joins the metric could see
lined up while the seven it could not see tore.

The fix was to stop fitting and start deriving. `CELL_FRAMES` in `_gen_skybox.py` writes the
unfolding down directly - each cell gets a face normal plus the world directions that
image-right and image-down point along - so all twelve edges agree by construction. The
invariant that guarantees it is handedness, `cross(r, d) == -n` on every face, and
`--geometry` asserts that plus all twelve edges at exactly zero deviation:

```
python _calibrate_cross.py --geometry
```

Run that one, not just the border score. The lesson worth keeping: **a metric that only sees
part of the object will happily report success on a broken one.** The border score was not
wrong, it was partial.

With that settled, three independent lines of evidence fix the cell assignment, and they are
worth keeping separate because the third alone gave the wrong answer:

0. **boxey's source** (`github.com/dougreichard/boxey`, `src/main.cpp`) - the tool that
   built the reference sky. It draws `front` at column 1 row 0, `left up right down` across
   row 1, `back` at column 1 row 2. Note its Blender preset `-t 0` calls
   `make_blender(no_rotate=true)`: it is pure PLACEMENT and applies no rotations, so
   routing faces through it does not solve orientation - that still has to be right going
   in. `_gen_skybox.py --faces DIR` emits boxey-compatible numbered faces anyway, so the
   sky can be assembled by boxey or opened in any other cubemap tool; a byte-for-byte check
   confirms that reassembly equals what we ship.

1. **Identity, from a working sky.** `a28_sb00.png` was built by `boxey` from the Artemis
   2.8 source faces, which are still on disk, so each cell was matched against them *by
   name*: every cell identified at 0.008-0.014 against a next-best of 0.5-0.86. That gives
   `front` on top, `up` in the center, `down` at the far right - and it settles up/down,
   since `skybox_UP` lands in the cell the `+Y` face goes in.
2. **Rotation, from continuity.** Every pair of cells that touch in the image is a pair of
   faces sharing a cube edge, so a correct cross is continuous across all five internal
   borders. `sky1.png` scores 1.01 on that metric and rotating one of its faces sends that
   join from 0.36 to 20.

**The trap:** it is tempting to pin the center face at identity, since a sky has no landmark
and its rotation looks free. It is not - rotating the center changes which of its edges
faces the cell above it, and the assignment is fixed. Pinning it made a pure-continuity
search prefer a *different, wrong* cell assignment that scored well because a
longitudinally-symmetric sky makes several arrangements near-degenerate. Sweeping the
center's own rotation takes the real assignment from 25 to 3.14, against a runner-up of
12.71.

```
python _calibrate_cross.py --ref E:/a/Cosmos-dev/data/graphics/sky1.png
python _calibrate_cross.py --verify media/skybox/venus_sky_midday.png
```

There are three checks, in increasing order of how much they actually prove, and the shipped
set passes all of them:

| check | what it proves | result |
|---|---|---|
| `--geometry` | handedness + all 12 cube edges, from the frames alone | 12/12 at **0.00e+00** deviation |
| `--roundtrip` | the shipped PNG decoded over the whole sphere equals the sky it encodes | mean **0.07-0.12** of 255, max 4 |
| `--verify` | the 5 borders the cross image exposes | **0.43-0.78** total (`sky1.png` is 1.01) |

`--roundtrip` is the one that matters, because it is the only one that sees all twelve
edges through real pixels. Its control: mirror one face of a shipped cross - the exact
defect the fitted version had - and it goes from mean 0.089 to **8.93**, max 2 to **162**.

Re-run all three whenever `CELL_FRAMES` or the face directions change.

## Building it

```
python sbs.pyz lib VenusClouds-Mod
```

Regenerating the inputs (needs numpy + Pillow; the `comfyui` conda env on the 3090 box has
both, the game's embedded Python does not):

```
python _build_ships.py                 # media/venus_ships.yaml from stock + deltas
python _gen_skybox.py --face 1024      # the six skies + equirect previews
```

`_build_ships.py` derives each entry from the **current** stock entry rather than freezing a
copy, so the mod stays current with the game instead of quietly reverting fields it never
meant to touch - a mistake the TNG pack had to be rebuilt to undo.

## Still to do

- **A mission.** The mod is content; the story is not written yet. Characters, the Guild
  city the crew works out of, and what the Kingdom is actually doing in the deep deck.
- **The altitude band**, as described above - the floor and ceiling that make this Venus
  rather than space with orange fog.
- **A test range.** A separate top-level mission, so the compiler cannot substitute the
  source and it loads the BUILT mastlib - and asserting that the art ARRIVED, because both
  ways this fails report `PASS`.
- **Interiors are borrowed too.** The eight `.grid` plans are LM's plans for each hull's
  base, re-keyed. They are correct floor plans; they are not airship floor plans.
