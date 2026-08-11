# Venus Clouds - art direction

The rule that decides what a Venus ship looks like. It exists because the look kept drifting:
the fleet is currently kitbashed from four unrelated Synty packs (Kingdom from `pirates`, Armada
from `scifi`, platforms from `construction`, Brood `generated`), and the shipped Blood Hawk is a
sci-fi cruiser hull with turrets where the art calls for an armored dirigible.

That drift has a single cause. The setting began with one prompt:

> *"Can you imagine an image of what it is like in the clouds of the planet Venus with floating
> steampunk platform zeppelins and small boat like craft that would be used in this. You depict
> two warring factions in this style and in the concept of in the Venus clouds"*

It asked for two warring factions but never said **how they differ**. The generator improvised a
contrast, and improvised it only inside that one painting (`E:/a/venus_clouds/venus_clouds.png`,
the `battle` sheet). Every later step re-improvised it from nothing. This file is the fix: the
rule now lives outside the pixels.

---

## The premise

Colonists came to Venus by ship. They live in the cloud deck now, and **everything they fly is
built from the remnants of the vessels and cargo that carried them there.** There is no foundry
on the ground and no ground worth standing on. Every hull is somebody's former spacecraft.

The two factions are not two art styles. They are **two engineering answers to the same
problem**, and the visual difference falls out of the answer.

| | **Kingdom** | **Armada** |
|---|---|---|
| **The answer** | *Refine and rebuild.* Smelt the wreck down and cast something new from it. | *Cut and bolt.* Keep the wreck as wreck; add to it what you take. |
| **What that says** | permanence, craft, the pretense of a civilization | survival that never ended, speed, appetite |
| **Register** | Victorian brass - a foundry culture | dieselpunk salvage - a scrapyard culture |

Everything below is downstream of that table. When a new hull is designed and the rule is
ambiguous, ask which answer the ship embodies, not which picture it resembles.

---

## The shared genus (both factions, non-negotiable)

A rigid **gas envelope riding above a gondola or superstructure**, trailing a smokestack plume,
carrying banners, in a golden-amber cloud deck. Anything without the envelope-over-gondola stack
is not a Venus ship. Both factions obey it, because both are solving lift in the same atmosphere.

Two words from the original prompt are load-bearing and must survive:

- **"platform zeppelins"** - the capital ships are *places you moor at*, not ships with ornament
  on them. This is the same fact the README states from the gameplay side: platforms are the only
  places you can stop.
- **"small boat like craft"** - the tenders are boats. Not shuttles, not fighters. Hull, deck,
  rails, a stack.

---

## The discriminator

> **Kingdom's envelope is bare fabric and the ornament is the building beneath it.**
> **Armada's envelope is itself armor and the ornament is spikes and salvaged drive gear.**

| | **Kingdom** | **Armada** |
|---|---|---|
| **Envelope** | pale cream-tan woven fabric - cargo canvas and parachute cloth - taut over visible longitudinal ribs, clean and repaired; capitals carry twin envelopes side by side | dark segmented hull plate cut from the colony ship and lapped over the gasbag, ribbed and scalloped like a carapace, riveted, weathered, still bearing fragments of the original markings |
| **Body** | an ornate *building*: cast gold onion domes with cupolas and finials, arched windows, balustraded promenade decks, tiered like a palace | a raked hull: spiked ram prow leading, jagged swept fin-blades, torn membrane fins, exposed conduit and pipework |
| **Motive power** | great spoked paddle-wheels on the flanks, driven by boilers | clustered salvaged drive pods, rear and flanks, glowing with underglow |
| **Palette** | warm - brass, gold, honey-brown, cream canvas | gunmetal, charcoal, rust-brown, with saturated magenta-crimson accents |
| **Wreck origin** | **invisible** - melted down and recast; smooth cast brass, nothing on the hull is nameable as a donor part | **recognizable** - engine bells, cargo containers, a hull section with its registry markings still faded on it, bolted where it landed |
| **Silhouette** | horizontal, symmetrical, stately | forward-raked, asymmetric, predatory |
| **Small craft** | wooden-decked steam launches - boat hull, tall stack, paddle-wheel, rails | rotor ornithopters - multi-blade rotors, small angular fuselage |
| **Reads as** | a cathedral that floats | a beetle or a wasp |

**The magenta is not fantasy.** It is repurposed drive and reactor hardware off the colony
fleet, which is why only the Armada has it: the Kingdom melted theirs down.

**Salvage visibility is the refine-vs-bolt answer made visible**, which is why it is a rule and
not a detail. You should be able to point at a spacecraft part on an Armada hull and name it. You
should not be able to find one on a Kingdom hull, because there are none left to find - that is
what a foundry does. When in doubt on a new design, this axis decides faster than palette does.

This matches the stats already in the mod - Kingdom `speed_coeff` 0.40-0.70 with turn rates as
low as 0.24 against Armada 1.15-1.35 and far less hull, and *"an Imperial Bulwark does not
maneuver; it arrives"* - and it matches the Armada parts atlas on disk (dark plating, orange-red
and brass accents).

---

## Writing prompts from this

The prompt that produced the good painting was short, concrete and **functional**. It named what
a thing IS and what it is FOR, and let the model supply coherence. A material checklist produces
a pile of materials.

- Keep the subject to roughly one sentence.
- Lead with the **type** ("a floating steampunk platform zeppelin"), not with adjectives.
- Carry the rule through two or three concrete **nouns** - domes, paddle-wheels, carapace, ram
  prow - rather than a dozen adjectives.
- **"in the clouds of Venus" is for CONCEPT ART only.** It buys the whole setting in five words
  and it is why the original painting works - but in an asset prompt it overrides the studio
  backdrop, tints everything, and shrinks the subject. Drop it when generating a model reference.
- The per-hull `desc` strings in `venus_kit_recipes.py` are the character notes. Write from
  them; do not re-invent ship personalities.

Technical framing language (single centered object, three-quarter view, studio lighting, grey
background) belongs in a fixed block appended to every subject, never mixed into the description
of the ship itself.

Worked examples - these are the **asset** prompts that actually produced airships (round 3),
not the concept-art phrasing:

- *Golden Vanguard*, Kingdom heavy, "twin envelopes over a large hull":
  > a steampunk airship with two clearly separate parts: above, a huge elongated cigar-shaped gas
  > balloon of pale cream fabric stretched over a rib frame; hanging well below it on tall visible
  > metal struts with open air between them, a separate ornate brass boat-hull gondola carrying
  > gold onion domes, railed promenade decks and a large spoked paddle-wheel on its side

- *Blood Hawk*, Armada heavy, "it closes fast and it does not turn away":
  > a steampunk raider airship with two clearly separate parts: above, a huge elongated gas
  > balloon sheathed in dark riveted scavenged metal hull plate with faded painted registry
  > markings; hanging well below it on visible struts with open air between them, a separate
  > armored gondola hull with a spiked ram at the nose and a cluster of engine bells at the tail

Note the Armada example still under-delivers on rake and asymmetry - see the findings below.

---

## The test

Render two ships, one per faction, in flat grey with color removed. **If you cannot tell them
apart by silhouette alone, the rule is not doing its job** and the wording needs sharpening
before a fleet gets built on it. Palette is the last line of defense, not the first.

---

## What generating these actually taught (measured, 2026-08-11)

Three rounds of six seeds per faction through SDXL, then Trellis2 for the shape. Each round
costs about 90 seconds, so iterate on the cheap stage and never spend 3D time on an unscreened
reference.

**Aspect ratio decides the silhouette.** A portrait frame (832x1216, inherited from the prop
pipeline where it exists to stop compact props tiling into grids) forces a vertical composition,
and SDXL answers with spherical hot-air balloons. Landscape 1216x832 is what produces a long
rigid airship. This one change did more than any wording.

**Name the gap or you get a submarine.** "Zeppelin", "airship" and "dirigible" all merge the
envelope and the hull into a single torpedo body. What works is describing **two clearly separate
parts with open air between them** - the envelope above, the gondola slung below on visible
struts. The gap IS the genus; state it explicitly every time.

**Colour is noise in a shape prompt, and it escapes.** "Magenta glow" became the ambient light of
the whole scene in one round, then the paint colour of the envelope in the next. It never once
stayed on the engines. Shape references should describe **form only** - the glow belongs in the
emissive map (`media/ships/VEN_*_emissive.png` already exists for this). The same applies to
"cream canvas" versus "cast brass": ask for the shapes, texture them later.

**Setting flavour fights the studio backdrop.** "in the clouds of Venus" is excellent prompt
writing for a scene and actively harmful for an asset - every image came back with a sky, which
drags in haze, tints everything, and drops the subject to 20-25% of frame. Drop it for asset
generation. Keep it for concept art.

**The prop pipeline's tiling filter rejects correct airships.** `_ref_score` in
`E:/ai/prop_farm/pipeline.py` hard-drops any image with two or more large foreground masses,
because for a compact prop that means a tiled grid. An airship is legitimately two masses. It
dropped one of the best Kingdom candidates. Do not reuse that filter for this fleet.

**Result.** Both pilots cleared the objective flatness gate with room to spare - Kingdom 0.590,
Armada 0.709, against a 0.35 threshold and a 0.47 benchmark from a known-good prop. The 3D path
works on Venus subjects.

**But the silhouette test did not pass cleanly.** Stripped of colour, the two pilots read as
similar fat envelopes over gondolas. The Armada lost its ram prow, forward rake and jagged fins
because the prompt leaned on palette words to carry the faction. That is the whole lesson in one
sentence: **if a faction's identity is not in the FORM words, it does not survive to the mesh.**
Next round's Armada prompt must spend its budget on rake, ram and asymmetry, not on rust and
magenta.

### The Armada problem (four rounds, unsolved by prompting alone)

The Kingdom solved in one round and holds. The Armada would not, and the way it failed is
informative. Each round bought one property and sold the other:

| round | prompt move | genus (envelope + gap + gondola) | faction form (ram, rake, fins) |
|---|---|---|---|
| 3 | "two clearly separate parts, open air between" | **yes** | no - reads as a Kingdom ship |
| 4 | + nose-down, spear ram, jagged fins, "clamped tight" | **no** - merged into one body, several became fish | yes |
| 5 | separate-parts clause + predatory form together | no - still merged | partly |
| 6 | gondola = "salvaged fuselage of a crashed spacecraft" | no | reads as an actual WRECK, derelict and torn open |

**Why the Kingdom holds and the Armada does not.** Kingdom's gondola is *a brass palace with
domes and promenade decks* - a strong, distinct object concept that cannot dissolve into a
balloon. The Armada's gondola kept being described as "an armored gondola hull", which is just
MORE HULL, so the model absorbs it into the envelope. Composition survives when each part is a
different KIND of thing, not when it is the same kind at a different size.

**And the salvage premise is dangerous in a prompt.** "Built from wreckage" / "crashed
spacecraft" makes the model render the wreck rather than the rebuild. The premise belongs in
this document, guiding which nouns get chosen; it should not be stated to the generator.

Practical conclusion: a one-shot text prompt reliably produces the Kingdom silhouette and does
not reliably produce the Armada one. The Armada probably wants its envelope and its gondola
generated as SEPARATE objects and assembled - which is what `venus_kit_recipes.py` already does,
and it already supports `"pack": "generated"` per slot.

### What worked: generate PARTS, assemble in a recipe

Whole-ship prompting solved the Kingdom and never solved the Armada. Generating the two parts
SEPARATELY solved it immediately, and it is the same shape as what `venus_kit_recipes.py`
already does.

Each part is a compact single object, which is the case the mesher handles best - the same
reason a guitar amp reconstructs perfectly and a whole airship does not. Both parts came out
clean on the first attempt, with no round-by-round trading:

- **envelope**: *"a huge armored airship gas balloon on its own, an elongated hull of riveted
  overlapping metal plates tapering to a sharp point at the front, a long spear-like ram spike
  projecting forward from the nose, jagged angular fin-blades jutting from the tail, nothing
  hanging underneath it, the bare balloon alone"*
- **gondola**: *"an armored airship crew gondola on its own, a long narrow riveted metal car
  with a row of small square windows down its side, a cluster of wide funnel-shaped engine
  bells at its stern, heavy suspension lugs along its roof, the car alone with nothing above
  it"*

"on its own" / "the bare balloon alone" / "nothing hanging underneath" are load-bearing - they
stop the model helpfully adding the other half.

`_venus_assemble_generated.py` does the composition:

    blender -b -P _venus_assemble_generated.py -- <envelope.glb> <gondola.glb> <out.glb>

Three things it has to do, each learned by getting it wrong first:

1. **Align the long axes.** Parts are generated independently, so the gondola's long axis is
   whatever the mesher happened to produce. Un-rotated, the car hangs crosswise and reads as a
   detached blob.
2. **Normalize scale against the envelope**, not against either file's units - the same problem
   the kit solves with per-pack scale factors.
3. **Add struts.** Without them the parts read as two objects floating near each other. Measure
   their placement from the GONDOLA's footprint; using the envelope's put them outside its ends.

`_venus_silhouette_test.py` renders the rule test - transparent film, orthographic, camera
perpendicular to the long axis (point it down the long axis and every ship looks like a disc).

**Result: the silhouette test passes.** Kingdom reads as a wide flat envelope over a long low
boat hull on many thin struts. Armada reads as a tapered finned envelope over a compact crew
car on four pylons. Different at a glance, with colour removed.

---

## Finishing a generated ship: density and textures

Raw output is 4-7M faces and untextured. Getting to a usable asset took three wrong turns, so
the order below is not negotiable.

**Texturing: use the MINIMAL chain.** `example_workflows/MeshWithTexturing.json` routes the mesh
through `FillHolesWithCuMesh` -> `SimplifyMesh` -> `FillHolesNicelyWithMeshlib` before texturing.
On these ships that shreds the thin struts and rigging into loose slivers - the mesh arrives at
the texturing stage already destroyed. `_venus_gen_textured.py` omits all three: it is exactly
the shape chain that works, plus `Trellis2MeshTexturing`. Output is a 2048x2048 baseColor and a
2048x2048 metallicRoughness with proper UVs, matching `media/ships/VEN_*_diffuse.png`.

**Decimation: Blender, on the BARE geometry, before texturing.** Three orders were measured:

| order | result |
|---|---|
| `Trellis2SimplifyMesh` in-chain, then texture | destroyed - struts collapse to slivers |
| texture dense, then decimate in Blender | torn - collapse cannot merge across UV seams; usable at ~90k, shredded at 14k |
| decimate bare geometry, weld, then texture | **works** |

`_venus_decimate.py` does the decimation; `_venus_texture_existing.py` textures an already
decimated `.glb` via `Trellis2LoadMesh`.

**The weld is essential.** glTF export splits a vertex per face, so a naive decimate produces a
TRIANGLE SOUP - 3x vertices, one body per face, no adjacency at all. It renders fine, which is
why this is easy to miss; it only shows up as a CuMesh `get_manifold_face_adjacency` failure at
texturing time. `_venus_decimate.py` merges by distance and makes normals consistent afterwards.

**Do not trust the flatness gate here.** A ship reduced to a starburst of needles still reports
`thin/long` 0.55 and still "passes", because the surviving needles preserve the bounding box.
Always render.

### Reaching the 14k budget: voxel remesh first

Collapse decimation stalls around 85k because the rigging and struts are OPEN surfaces - their
boundary edges cannot be collapsed across. A **voxel remesh rebuilds the ship as one closed
manifold shell**, and decimation then runs freely to any target.

    blender -b -P _venus_retopo.py -- <in.glb> <voxel_size> <target_faces> <out.glb>
    blender -b -P _venus_retopo.py -- ship.glb 0.004 7000 ship_14k.glb

Measured on the Kingdom Vanguard: 4,332,332 -> remesh 519,042 -> **13,890 faces**, textured
2048x2048 baseColor + metallicRoughness, `thin/long` 0.589. Envelope ribbing, gold rigging
bands, wooden gondola and prow all survive.

Two things to know:

- **Target HALF your triangle budget.** The remesh produces quads and `use_collapse_triangulate`
  doubles them, so `7000` yields ~14,000 triangles.
- `voxel_size` is in model units and the ships normalize to ~1.0 long. 0.004 keeps fine detail;
  0.010 is chunky. Anything coarser than a strut's thickness eats the strut.

**It also solves multi-part ships.** The Armada is assembled from six objects (envelope, gondola,
four struts); the remesh joins them into ONE mesh with one UV set, so the ship gets a single
texture set - which is what Cosmos wants and what two separately-generated parts would otherwise
violate. 8,095,220 faces across 6 objects -> 13,962 faces in 1 submesh.

### The full pipeline

    1. sweep      SDXL reference candidates          (cheap, screen by eye)
    2. shape      Trellis2 chain -> dense .glb        _venus_gen_textured.py (minus texturing)
    3. assemble   multi-part ships only               _venus_assemble_generated.py
    4. retopo     voxel remesh + decimate + weld      _venus_retopo.py
    5. texture    Trellis2LoadMesh -> MeshTexturing   _venus_texture_existing.py
    6. verify     silhouette + a RENDER, always       _venus_silhouette_test.py

---

## Corrections, measured (supersedes guesses above)

Three things in the sections above were reasoned rather than measured. All three were wrong.

**1. Rope is NOT why decimation stalls.** Adding rope/cable/rigging negatives to the prompt does
give visibly cleaner reference images and slightly cleaner ships - keep them - but it does not
help decimation at all. Plain collapse on a rope-free ship still stalled at 71,516 -> 70,637
against a 14,000 target.

**2. There are no open boundary edges.** Measured on both a rope-heavy and a rope-free mesh:
**zero** edges used by only one face. The "open surfaces block collapse" explanation was fiction.

**The real cause: 7,684 edges shared by FOUR faces** - non-manifold pinch points where the
isosurface self-touches. Blender's collapse decimation will not collapse a non-manifold edge, and
those constraints scattered through the mesh halt reduction around 70-85k.

Welding before decimating dissolves some of them but cannot close the gap:

| weld threshold | faces after weld | best decimate reached |
|---|---|---|
| 0.0001 | 3,411,658 | 70,942 |
| 0.001 | 2,602,212 | 60,078 |
| 0.003 | 397,348 | 31,624 |

The last already destroys detail and still misses 14,000 by 2x.

**So the voxel remesh is REQUIRED, not a fallback.** It is the only thing that reaches budget,
because it rebuilds the ship as one clean manifold shell rather than trying to repair a
non-manifold one.

**3. Orientation must be done LAST, on the written file.** Two traps make anything earlier
unreliable:

- **Blender is Z-up, glTF is Y-up.** An in-Blender rotation does not land where you expect in
  the exported file - the retopo script reported "rotated long axis X -> +Z" and still wrote an
  X-long file.
- **`Trellis2MeshTexturing` re-orients the mesh.** Anything done before texturing is undone.

`_venus_orient.py` does it on the finished `.glb` with trimesh, where what is measured is what
Cosmos reads. It maps longest extent -> +Z, second longest -> +Y (the envelope-over-gondola
vertical), and refuses to mirror. Verified: `X=0.546 Y=0.601 Z=1.000`, textures intact.

**A measurement trap worth remembering:** `scene.geometry[*].bounds` reads each mesh's LOCAL
frame and ignores node transforms, so a scene-graph rotation looks like a no-op and does not
survive export. Bake to real vertex data (`Scene.to_geometry()`) before measuring or exporting.

### Corrected pipeline order

    1. sweep      SDXL references, WITH rope negatives     _venus_gen_ref.py
    2. shape      Trellis2 chain -> dense .glb
    3. assemble   multi-part ships only                    _venus_assemble_generated.py
    4. retopo     voxel remesh + decimate + weld           _venus_retopo.py
    5. texture    Trellis2LoadMesh -> MeshTexturing        _venus_texture_existing.py
    6. orient     +Z long, +Y up - LAST, after texturing   _venus_orient.py
    7. verify     silhouette + a RENDER, always            _venus_silhouette_test.py

### Correcting the correction: KEEP the rope in the prompt

The rope negatives proposed above were tested and **reverted**. Measured A/B on the same seed:

| prompt | result |
|---|---|
| with rope words | ribbed envelope ABOVE, open gap, separate wooden boat gondola BELOW - a proper airship |
| with rope NEGATIVES | a fat barrel; envelope and gondola FUSED into one body |

Two ships in a row came out fused. **The visible rigging lines are what tell the shape model
there are two separate bodies.** Struts alone did not carry it.

So the rope is **scaffolding for the GENERATOR, not geometry for the game**. It is sub-voxel and
disappears in the voxel remesh regardless, so it costs nothing in the finished asset - and asking
for it costs nothing either, because it was never the reason decimation stalled. Keep it in the
prompt. `_venus_gen_ref.py` carries a guard comment saying so.

This is the second time a plausible story about the rope turned out to be wrong. The lesson is
narrower than "rope is bad": **rope is a generation cue with no downstream cost.**

### Rendering: prop_farm's render_glb.py is orientation-naive

`render_glb.py` puts the camera at a FIXED world offset, which looks straight down the nose of a
long hull once orientation changes - and `Trellis2MeshTexturing` re-orients meshes, so the
orientation is not predictable. `_venus_render3q.py` computes the camera from the mesh's own
longest / vertical / depth axes instead. Use it for every visual check, or you will "verify" a
ship you cannot actually see.

### Engine-ready output

    VEN_KdmGoldenVanguard_gen.glb   13,890 faces  2048^2  X=0.589 Y=0.701 Z=1.000
    VEN_ArmBloodHawk_gen.glb        13,962 faces  2048^2  X=0.576 Y=0.991 Z=1.000

Both +Z long, +Y up, one texture set each.

---

## Getting a generated ship on screen (mock) - and the two traps

Confirmed working: the generated Kingdom Vanguard renders in the mock's 3D view.

**1. SCALE. Trellis2 normalises every mesh to a UNIT CUBE.** Nothing downstream rescales it,
so an unscaled ship is ~580x smaller than a stock hull and draws as a sub-pixel speck. Every
diagnostic passes while this is wrong - HTTP 200 on all art, spawn breadcrumb present, no
`art load failed` in the console - because nothing IS failing. Measure extents against a
working hull before believing a "loads fine" report:

| mesh | extents |
|---|---|
| `tsn_light_cruiser.obj` (stock) | 291 x 118 x 583 |
| `VEN_GoldenVanguard.obj` (this kit) | 17.6 x 10.6 x 6.0 |
| raw Trellis2 output | 0.59 x 0.70 x 1.0 |

`_venus_scale_obj.py <obj> <target_long_axis>` rescales in place (uniform scale touches only
`v` lines; `vt` are unitless and `vn` unchanged). NOTE the two conventions differ ~33x - the
stock cruiser is 583 units at `meshscale 0.2`, this kit's ships are ~17.6 at `meshscale 0.18`.
A ship going into the FLEET should match the kit convention and take its `meshscale` from the
same formula `_build_ships.py` uses for the other 19 hulls.

**2. The .obj must carry UVs and normals.** trimesh's exporter drops both unless textures are
included, writing position-only faces (`f 11 13 6`). The mock's `_parseOBJ` and the engine both
want `f v/vt/vn`, and with no UVs the diffuse map has nothing to map onto. Export through
Blender (`_venus_glb2obj.py`), which is how the shipped `VEN_*.obj` were made.

**The art file set** is five files, matching the existing ships:
`<Name>.obj`, `_diffuse.png`, `_specular.png`, `_emissive.png`, `_normal.png`.
`loadShipMesh` only requires the `.obj` and treats the maps as optional, but the
`webgpu_field` overlay requests normal too. Specular is derived by inverting glTF's roughness
channel; emissive is black until a ship needs a glow - **which is where the Armada's magenta
belongs**, as a texture and not as geometry or a prompt word.

**Viewing recipe:**

    py -3 -m cosmos_dev.mission_runner VisualTestRange --gui --map visual_mod_art
    http://localhost:8765/server        (hard refresh - the mesh cache is per page load)

Add the ship as a variant in `MOD_ART_VARIANTS` in `VisualTestRange/maps/visual_harness.py`
and put the path in the **artfileroot** slot: the mock renders from `artfileroot` only and
ignores `art_file_path`. Relative spelling that works:
`../../missions/VenusClouds-Mod/media/ships/<Name>`.

Do NOT edit `maps/mod_art_ships.json` expecting a ship to appear - it feeds something else,
and the spawned list is generated from `MOD_ART_VARIANTS` into `mod_art_variants.json`.

**Expected frame on a machine without the anime mod:** every `God_Phoenix` variant 404s, so
three green spheres are CORRECT. Everything with `art_file_path` falls back to
`artfileroot: tsn_light_cruiser`. Judge by name tag; the frame is mirrored in world X.

**This proves the MOCK path only.** The mock reads `artfileroot` out of sbs_utils' merged ship
list, so it never needs the engine. `ship_data.py` is explicit that in the real engine
"stats travel through the library, artfileroot does not" - which is the open question
`visual_mod_art` exists to settle.

---

## BUG: the built kit ships are X-long; the engine expects Z-long

Found while checking which orientation a GENERATED ship should use. Measured, not inferred.

**The engine's convention is +Z long.** Of the stock hulls that are clearly elongated
(long axis at least 1.15x the next), **8 of 8 are Z-long and none is X- or Y-long**:

    tsn_light_cruiser   291.9 x 118.7 x 583.3   Z   2.00
    tsn_scout           216.1 x 121.8 x 550.4   Z   2.55
    skaraan_defiler     311.2 x 147.3 x 583.7   Z   1.88
    kralien_dreadnought 298.2 x  77.2 x 430.5   Z   1.44
    torgoth_behemoth      9.6 x   4.7 x  30.7   Z   3.21
    Brigantine          822.4 x 244.2 x 1027.5  Z   1.25
    ArvoCarrier1         13.2 x   3.5 x  19.9   Z   1.50
    monster2              4.2 x   4.0 x  13.9   Z   3.34

**Every built Venus hull is X-long**, and `meshrotate` is 0 on all 15 ship-data entries, so
nothing compensates:

    VEN_GoldenVanguard  17.6 x 10.6 x 6.0   X
    VEN_Valiant         12.6 x  7.9 x 4.3   X
    VEN_ImperialBulwark 20.2 x 12.2 x 7.3   X
    VEN_BloodHawk       18.4 x  6.4 x 4.6   X

They should therefore render broadside to their direction of travel.

**What is NOT the cause** (each ruled out by measurement):

* not the source art - `SM_Veh_Boat_Medium_01_Hull_Pirate.obj` measures 5.07 x 4.67 x 14.29,
  Z-long, exactly as this file's header states;
* not the Blender OBJ round trip - importing that part and re-exporting it with the kit's own
  default flags gives back 5.07 x 4.67 x 14.29, Z-long. (In-Blender it sits Y-long, which is
  just Blender being Z-up; the exporter converts it back.)
* not `env()` - it returns `(d/_BARREL[0], d/_BARREL[1], length/_BARREL[2])`, i.e. it puts
  LENGTH on Z, which is the right intent.

So the rotation enters during kit assembly, and the output also does not match the recipes'
own stated intent - the Valiant comment predicts "roughly 4.1 x 4.7 x 20" and the built ship
is 12.6 x 7.9 x 4.3. Finding the exact line needs stepping through `_venus_kit_blender.py`
with a single-part recipe; that is not done here.

**Consequence for generated ships:** `_venus_orient.py` targets +Z long, which matches the
ENGINE and therefore does NOT match the current kit output. Do not "fix" a generated ship to
agree with the kit hulls - the kit hulls are the ones that are wrong.
