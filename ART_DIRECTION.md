# Above the Venusian Clouds - art direction

The v0.1 direction (two AI-generated factions, kitbashed) is archived at
`_legacy/ART_DIRECTION_v0.1.md`. This document covers the six procedural fleets. The build
rules every fleet follows are in `E:\ai\art\sky_core\FLEET_BRIEF.md`; this is the look.

## The premise, in one line

**Starships that became airships.** Every hull is a wreck from space, rebuilt by a people
who can never leave the clouds. You should be able to see both halves: the starship it was
(plating with panel seams, a canopy, dead thrusters, nacelles) and the airship it is now
(decks, lift, smoke, a flag).

## What makes all six fleets one game

- **The lift ring.** Every hull and every station floats on at least one visible grav-lift
  ring, with a glowing core and the fleet's `LIFT_COLOR` underneath. A fleet may restyle
  the ring's housing, but never the ring's shape. The rings are also gameplay: they are
  rooms in the interior, and losing them sinks the ship.
- **A fleet color band** on every hull.
- **The same 13 roles at the same sizes**, so a lineup of any two fleets compares
  role-for-role. Carrier 1100, cruiser 800, destroyer 550, frigate 380, cargo barge 600,
  tender 500, fighter 45, launch 90, tug 80. The stations run from 1000 to 1500.
- **Human scale.** One Blender unit is about 2.5 m. Railings stand 0.7 high and a window is
  about 0.7 x 1.0, so crews read at the same size in every fleet.

## What makes each fleet itself

| Fleet | Species' ships | Shape language | Palette | Signature parts | Guns |
|---|---|---|---|---|---|
| Salvage Flotilla (steam) | wrecked starship hulls | a riverboat on a hull: tiered cabins, stacks | grey plating, red trim, brass, wood decks | paddlewheels, stern wheels, smokestacks | none on the hull (turret mounts) |
| Aurelian Concord (deco) | chrome ocean-liner starships | rigid airship envelopes over polished liner hulls | ivory fabric, chrome, pewter, black lacquer, gold chevrons, teal-and-gold speed lines | envelopes, cruciform lacquer fins | blisters |
| Atomic Directorate (atom) | finned rocket ships | Googie: boomerangs, swept fins, bubble canopies | gloss white, candy-apple red, turquoise, chrome | the atom lift: reactor sphere inside the ring, crossed orbits | ray guns |
| Iron Syndicate (diesel) | armored warships | slab-sided faceted armor | olive drab, gunmetal, rust, hazard stripes, blood-red band | multi-blade propellers, riveted ring collars glowing amber | twin turrets, flak |
| Sunward Commons (solar) | light eco-starships | soft arches, greenhouses, open decks | white ceramic, pale birch, leaf green, sunflower yellow | solar-sail wings, gardens and trees, wooden ring cradles | light lances |
| Verdant Brood (bio) | living insectoid bio-starships | creatures: overlapping plates, ribs, horns | bone, chitin brown, violet and maroon flesh, teal glow spots | gas bladders, rings grown into the flesh | spine turrets |

A small render must say both the **role** and the **fleet**. Two designs in one fleet must
never read as the same ship.

## Textures

Every material gets a 256 px cell of a palette sheet. The cell holds a procedural pattern
(`sky_core/texgen.py`), written into all four maps, and every face is box-projected into
its material's cell:

| Kind | Materials | Normal | Specular | Diffuse |
|---|---|---|---|---|
| panel | hull plating, nacelles, steel, brass | plate seams and rivets | worn metal, dark seams | tone per plate, grime |
| siding | cabins | board edges | | |
| plank | decks, crates | board gaps, grain | grain | board tone |
| fabric | canvas, envelopes, membranes | weave, seam rows | low | weave |
| block | brick, concrete, slate | mortar | | |
| organic | flesh, chitin, bone, leaf | ridged cells | wet ridges | |
| glass | canopies, windows | frame bars | high | |
| glow | lamps, reactors, lift glow | flat | | emissive kept |
| cloud | clouds | soft noise | low | self-lit (`game_glow`) |

Base colors are brightened 15% (`texgen.BRIGHTEN`). The engine has no subsurface
scattering and no global illumination, and the Venus sun is dim, so the flat palette read
dark and grey.

Clouds carry their own light in the emissive map (`game_glow`, 60% of the diffuse, 35% for
storm cells). Without it a white cloud renders flat grey in the engine.

**Judge textures the way the engine sees them**, not from the Cycles gallery renders:

```
blender --background --factory-startup --python sky_core/texpreview.py -- <cosmos_dir> <root> <out.png>
```

That renders the exported OBJ with its four maps under one sun and a dim ambient.

## Smoke and light

- **Smoke:** white steam for the Flotilla and the Concord, black exhaust for the
  Syndicate, green motes for the Directorate, pollen for the Commons and spores for the
  Brood. Each plume comes from the stack tops the art recorded, or from the stern on
  fleets without stacks.
- **Lift shimmer:** one glow point under each ring, in the fleet's lift color.
- **Blink:** storm-cell lightning blinks; aether and spore clouds pulse slowly
  (`blink_state`).
