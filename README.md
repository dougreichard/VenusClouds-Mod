# Above the Venusian Clouds

A Cosmos mod: six salvage-airship navies and the cloud sea they fly over. Every ship was
built on Venus from the wrecks of the starships that brought its people there, so each
fleet is a different species' spacecraft remade into something that floats.

It adds content without touching the game install. The hulls are **declared** through
`ship_data_add_extra`, and nothing is written into the game folder or a mission folder.

| | |
|---|---|
| Hulls | 84: six fleets x (13 roles + a turret) |
| Clouds | 11 cloud types, plain, storm and resource, as passive terrain |
| Interiors | 54 (9 flyable roles x 6 fleets), with lift-ring rooms where the rings are |
| Fleet ladders | 6, JSON |
| Skies | 6 amber skyboxes by altitude band |

## The six fleets

| Fleet | Race | Built from | Look | Smoke |
|---|---|---|---|---|
| Salvage Flotilla | Flotilla | wrecked starship hulls | riverboat decks, paddlewheels, stacks | white steam |
| Aurelian Concord | Concord | chrome ocean-liner starships | deco zeppelins, gold trim | white steam |
| Atomic Directorate | Directorate | finned rocket ships | reactor-lit lift rings, ray guns | green motes |
| Iron Syndicate | Syndicate | armored warships | rivets, propellers, twin turrets | black exhaust |
| Sunward Commons | Commons | light eco-starships | solar-sail wings, gardens | pollen |
| Verdant Brood | Brood | living insectoid bio-starships | regrown creatures, spines | spores |

Every fleet has the same roles, so they fight the same game: carrier, cruiser, destroyer,
frigate, cargo barge, steam tender, fighter, launch, tug, and four stations (command,
industrial, civil, science). Keys are `venus_<tag>_<role>`, with the tags `steam`, `deco`,
`atom`, `diesel`, `solar` and `bio` (for example `venus_diesel_cruiser`). Clouds are
`venus_cloud_<name>`.

## What it adds to play

- **Lift.** Every hull flies on grav-lift rings, and the rings are rooms in its interior.
  Damage to them bleeds lift, and a ship that cannot hold its altitude **sinks** toward the
  crushing deck. Damage control on the ring rooms restores lift, and so does a refit at a
  market station.
- **Cloud cover.** Each cloud carries an engine nebula. A ship inside one
  (`inside_nebula_count`) is tagged `venus_in_cloud`, and turrets and missile volleys will
  not shoot at it.
- **Storms.** Storm cells strike ships inside them every few seconds, draining lift and
  hull. Their lightning flickers (`blink_state`).
- **Harvest and salvage.** A ship sitting in a resource cloud fills its hold: ice gives
  coolant, sulfur fuel, ore materials, spores medicine and aether aether. The cloud shrinks
  and finally disperses. Wrecks give salvage plus a replacement ring. Missions decide what
  the cargo is worth; `venus_cargo(ship)` reads a hold.
- **Turrets.** Carriers, cruisers and stations carry separate, destructible turret objects
  welded at the mount points the art recorded.
- **Missiles only.** Ships carry no beams. NPC hulls fire missile volleys, and carriers and
  stations also launch drones.
- **Smoke and shimmer.** Stacks trail their faction's smoke, each lift ring glows beneath
  the hull, and a ship below half lift smolders.

## Using it in a mission

Pin both halves in the mission's `story.json`:

```json
"mastlib":      ["artemis-sbs.VenusClouds-Mod.venus_fleets.v0.2.0.mastlib"],
"shared_media": ["artemis-sbs.VenusClouds-Mod.media.v0.2.0.zip"]
```

Turn on declared ship data in the mission's `settings.yaml`. Without it the hulls are
simply absent:

```yaml
EXTRA_SHIP_DATA: true
```

Then spawn hulls by key, dress a map, and let the mod's ticker run:

```
venus_world_spawn(0, 0, 32000, lanes=20, resources=16, storms=3, wrecks=5)
prefab_spawn("prefab_fleet_raider", {"race": "Syndicate", "fleet_difficulty": 4, "faction_side": True})
```

The mod's ticker starts on the `game_started` signal. It works best alongside
LegendaryMissions (fleets, prefabs, docking), but it does not require it.

Two missions already use the mod:

- **Venus_TestRange** checks it in the engine.
- **VenusSalvage** is a playable salvage-and-survival mission built on it.

## Viewer and prebake

The repo root is also a mission: a hull browser, plus the **prebake**. The engine bakes each
hull's `.paxmesh` and radar sprite the first time it draws the hull, and mesh load is where
it is fragile. So bake before a session, on the machine that will run it:

```
Artemis3-x64-release.exe autostartserver defaultmission=VenusClouds-Mod map=venus_ships bake=venus
```

The bake walks every hull through the browser's 3D widget. It also re-hulls a server-side
player ship through each key, so the server loads each hull as ship art, not just as a
picture.

**Re-run the bake after every `sbs lib VenusClouds-Mod`.** Unpacking the pack removes the
baked files.

## Layout

The MAST side (a flat mastlib) and the engine side (a media pack) are split by who opens
the file:

```
VenusClouds-Mod/
  __lib__.json         {"version":"v0.2.0","mastlib":["venus_fleets"],"zip":["media"]}
  story.mast, maps/    the viewer and prebake (a mission, not shipped)
  media/               -> artemis-sbs.VenusClouds-Mod.media.<tag>.zip
    venus_ships.json      all 95 entries; HJSON-valid JSON, one file, generated
    ships/<fleet>/        OBJ + _diffuse/_emissive/_specular/_normal per hull
    ships/clouds/         the 11 clouds
    skybox/               six amber skies
  venus_fleets/        -> artemis-sbs.VenusClouds-Mod.venus_fleets.<tag>.mastlib (FLAT)
    __init__.mast         declares ships, registers races and rooms, loads interiors and ladders, routes
    venus_setup.py        manifest, races, ship declaration, ladders
    venus_world.py        clouds, cover, storms, harvest, lift
    venus_turrets.py      turret welding and targeting
    venus_missiles.py     NPC missile volleys
    venus_particles.py    smoke, ring shimmer, smolder
    venus_altitude.py     altitude bands, sinking, deck hazard
    venus_*.grid          54 interiors
    venus_<tag>_fleets.json   fleet ladders
    venus_manifest.json   per hull: rings, emitters, turret mounts, stern (engine space)
    venus_sides.amd       six factions + diplomacy
  _tools/              build_mod.py, balance_targets.json (not shipped)
  _legacy/             the v0.1 hulls, kit, YAML and docs (not shipped)
```

## Rebuilding

The art is procedural Blender source in the `VenusClouds-Art` repo (`E:\ai\art`). See
`ART_DIRECTION.md` for what the art must stay true to.

```
SKY_MOD=1 NORENDER=1 ./sky_core/run.sh /e/ai/art/<fleet>    # each fleet; guns become mount points
NORENDER=1 ./sky_core/run.sh /e/ai/art/terrain              # the clouds
python _tools/build_mod.py                                  # art -> media, ship data, grids, manifest, ladders
python sbs.pyz lib VenusClouds-Mod                          # from data/missions
```

`build_mod.py` is repeatable: two runs give identical md5s. Stats come from
`_tools/balance_targets.json` (per-role targets times per-fleet multipliers), so tune
there, never in `venus_ships.json`.

## Rules this mod follows

- The ship file is HJSON-valid JSON: every key quoted, LF line endings, a final newline,
  one file per stem, and each entry built from a whole stock template (zero-beam
  `hull_port_sets` kept).
- `artfileroot` carries the full pack path, including the version. Bump `__lib__.json` and
  regenerate together.
- Derived art (`.paxmesh`, `.pointcube`, `.rawbitmap`, `*1024.png`, `*256.png`) is never
  committed or packaged.
- Every public function is prefixed `venus_`.
