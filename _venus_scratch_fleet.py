"""Build Venus fleet art from PROCEDURAL geometry, designed against the concept art.

    blender --background --python _venus_scratch_fleet.py -- <outdir> <which> [tex] [tris]

    which: kdm_ship | kdm_outpost | pir_ship | pir_hub | all

Everything is authored in bmesh - no kitbash, no packs, no prop farm. Sources are
`_refs/_grid_fleet_component.png` (the KINGDOM / PIRATE FLEET COMPONENT SCHEMATICS) and
`E:/a/venus_clouds/venus_clouds.png` (the sepia fleet painting).

The two factions are drawn as opposites and the geometry follows that:

  KINGDOM - brass over tarred timber, sepia and amber. PADDLE WHEELS with gear drives
  (the schematic labels them on three separate classes), smokestacks, steam domes, ribbed
  canvas gas bags, balustraded decks, brass domes. Nothing glows.

  PIRATE - gunmetal and blood red, angular armour instead of planking. A DREADNOUGHT RAM,
  GRAPPLING MECHANISMS and HIGH-OUTPUT PLASMA ENGINES, which are the only light sources in
  the fleet, so they are authored as EMISSIVE and land in the emissive map rather than the
  diffuse.

Pipeline per model: author detail -> bevel hard edges only -> subdivide a copy as the
high-poly reference -> triangulate -> decimate to target -> unwrap -> bake diffuse,
emissive and a real high-to-low normal into ONE atlas. Same contract as the kitbash bake,
so the output drops into media/ships beside it.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUTDIR = argv[0]
WHICH = argv[1] if len(argv) > 1 else "all"
TEX = int(argv[2]) if len(argv) > 2 else 2048
# TNG's 46 in-engine meshes run to 145,856 tris, median 14,092. The stock hulls'
# 1,790-7,784 describes the base art, not a limit. Sit near the median.
TARGET = int(argv[3]) if len(argv) > 3 else 14000

TAU = math.pi * 2.0


def _log(msg):
    print("FLEET: %s" % msg)


# ============================================================== shared helpers ===
def new_scene():
    bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
    return bpy.context.scene


def mat(name, rgb, rough=0.85, metallic=0.0, emit=None, emit_strength=3.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    if emit is not None:
        # Authored emission is what makes the EMIT bake non-black. The plasma engines and
        # turret cores are the fleet's only light sources; everything else stays unlit.
        b.inputs["Emission Color"].default_value = (emit[0], emit[1], emit[2], 1.0)
        b.inputs["Emission Strength"].default_value = emit_strength
    return m


class Build:
    """One mesh under construction: a bmesh plus the material slots it indexes into."""

    def __init__(self, name, materials):
        self.name = name
        self.materials = materials
        self.bm = bmesh.new()

    # --- primitives -------------------------------------------------------------
    def prim(self, op, mi, matrix=None, **kw):
        """New geometry comes from the OPERATOR'S RETURN VALUE.

        A positional slice (`list(bm.verts)[v0:]`) is not reliable once bmesh.ops has run
        repeatedly - it grabs the wrong verts and the matrix lands on unrelated geometry.
        """
        res = op(self.bm, **kw)
        verts = list(res.get("verts", []))
        if matrix is not None and verts:
            bmesh.ops.transform(self.bm, matrix=matrix, verts=verts)
        vset = set(verts)
        faces = list(dict.fromkeys(
            f for v in verts for f in v.link_faces if vset.issuperset(f.verts)))
        for f in faces:
            f.material_index = mi
        # Per shell, while it is still an isolated body. A blanket recalc at the end works
        # on a soup of closed and open shells and flips whole bodies inside out.
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)
        return faces

    def box(self, mi, center, size, rx=0.0, ry=0.0, rz=0.0):
        m = Matrix.Translation(Vector(center))
        if rz:
            m = m @ Matrix.Rotation(rz, 4, "Z")
        if ry:
            m = m @ Matrix.Rotation(ry, 4, "Y")
        if rx:
            m = m @ Matrix.Rotation(rx, 4, "X")
        self.prim(bmesh.ops.create_cube, mi,
                  matrix=m @ Matrix.Diagonal(Vector(size).to_4d()), size=1.0)

    def tube(self, mi, center, radius, height, seg=16, rx=0.0, ry=0.0, taper=1.0):
        m = Matrix.Translation(Vector(center))
        if ry:
            m = m @ Matrix.Rotation(ry, 4, "Y")
        if rx:
            m = m @ Matrix.Rotation(rx, 4, "X")
        self.prim(bmesh.ops.create_cone, mi, matrix=m, cap_ends=True, cap_tris=False,
                  segments=seg, radius1=radius, radius2=radius * taper, depth=height)

    def ring(self, mi, center, ry_, rz_, thick, seg=30):
        """A hoop around the X axis - envelope ribbing, wheel rims, turret collars."""
        self.prim(bmesh.ops.create_cone, mi,
                  matrix=Matrix.Translation(Vector(center))
                  @ Matrix.Rotation(math.radians(90), 4, "Y")
                  @ Matrix.Diagonal(Vector((rz_, ry_, 1.0)).to_4d()),
                  cap_ends=False, cap_tris=False, segments=seg,
                  radius1=1.0, radius2=1.0, depth=thick)

    def sphere(self, mi, center, radii, u=32, v=16):
        self.prim(bmesh.ops.create_uvsphere, mi,
                  matrix=Matrix.Translation(Vector(center))
                  @ Matrix.Diagonal(Vector(radii).to_4d()),
                  u_segments=u, v_segments=v, radius=1.0)

    # --- composite pieces used by more than one model ---------------------------
    def hull(self, mi_hull, mi_deck, stations, profile, deck_z=-0.09, bulwark=0.34,
             mi_rail=None):
        """Loft a boat hull from cross-sections, then floor and rail it."""
        rings = []
        for x, hw, depth in stations:
            rings.append([self.bm.verts.new((x, yf * hw, zf * depth)) for yf, zf in profile])
        self.bm.verts.ensure_lookup_table()
        faces = []
        for a, b in zip(rings, rings[1:]):
            for i in range(len(profile) - 1):
                faces.append(self.bm.faces.new((a[i], a[i + 1], b[i + 1], b[i])))
            faces.append(self.bm.faces.new((a[-1], a[0], b[0], b[-1])))
        faces.append(self.bm.faces.new(list(reversed(rings[0]))))
        faces.append(self.bm.faces.new(rings[-1]))
        for f in faces:
            f.material_index = mi_hull
        # Recalc NOW: the bevel later deletes and rebuilds these faces, and holding the
        # references until the end raises "BMFace has been removed".
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)

        deck = []
        for x, hw, _d in stations[1:-1]:
            inner = hw * 0.88
            deck.append((self.bm.verts.new((x, inner, deck_z)),
                         self.bm.verts.new((x, -inner, deck_z))))
        for (sa, pa), (sb, pb) in zip(deck, deck[1:]):
            f = self.bm.faces.new((sa, pa, pb, sb))
            f.material_index = mi_deck

        for side in (1, -1):
            prev = None
            for x, hw, _d in stations[1:-1]:
                lo = self.bm.verts.new((x, side * hw, 0.0))
                hi = self.bm.verts.new((x, side * hw * 0.97, bulwark))
                if prev is not None:
                    f = self.bm.faces.new((prev[0], lo, hi, prev[1]) if side > 0
                                          else (prev[1], hi, lo, prev[0]))
                    f.material_index = mi_hull
                prev = (lo, hi)
            if mi_rail is not None:
                for x, hw, _d in stations[1:-1]:
                    self.box(mi_rail, (x, side * hw * 0.97, bulwark + 0.03),
                             (0.30, 0.10, 0.07))

    def paddle_wheel(self, mi_wood, mi_brass, mi_iron, x, y, r, boards=8):
        """The Kingdom signature: wheel, boards, rim, paddle box and gear drive."""
        self.tube(mi_iron, (x, y, 0.0), 0.20, 0.46, seg=14, rx=math.radians(90))
        for i in range(boards):
            a = i / float(boards) * TAU
            cy, cz = math.cos(a), math.sin(a)
            self.box(mi_brass, (x + cy * r * 0.55, y, cz * r * 0.55),
                     (r * 0.92, 0.07, 0.07), ry=-a)
            self.box(mi_wood, (x + cy * r, y, cz * r), (0.30, 0.62, 0.09), ry=-a)
        self.ring(mi_brass, (x, y, 0.0), r, r, 0.52, seg=32)
        # Paddle box, hooding the top of the wheel as the schematic draws it.
        self.box(mi_wood, (x, y, r * 0.92), (r * 1.55, 0.74, 0.40))
        self.box(mi_brass, (x, y, r * 1.14), (r * 1.60, 0.78, 0.09))
        self.tube(mi_brass, (x - r * 0.86, y * 0.80, 0.10), 0.34, 0.14, seg=18,
                  rx=math.radians(90))

    def envelope(self, mi_canvas, mi_rib, center, radii, ribs=(-0.55, 0.0, 0.55),
                 u=56, v=28, fins=None, mi_fin=None):
        """A ribbed gas bag. Ribs are scaled to the ellipsoid's own cross-section."""
        c, r = Vector(center), Vector(radii)
        self.sphere(mi_canvas, c, r, u=u, v=v)
        for frac in ribs:
            x = c.x + frac * r.x
            t = frac
            if abs(t) >= 0.985:
                continue
            s = math.sqrt(max(0.0, 1.0 - t * t)) * 1.02
            self.ring(mi_rib, (x, c.y, c.z), r.y * s, r.z * s, 0.10, seg=30)
        if fins:
            fm = mi_fin if mi_fin is not None else mi_canvas
            fx = c.x + r.x - 0.30
            self.box(fm, (fx, 0.0, c.z + r.z * 0.80), (fins[0], 0.09, fins[1]))
            for sgn in (1, -1):
                self.box(fm, (fx, sgn * r.y * 0.72, c.z), (fins[0], fins[1] * 1.05, 0.09))
        return c.z - r.z


PROFILE = [
    (1.00, 0.00), (0.99, -0.28), (0.86, -0.60), (0.56, -0.87),
    (0.00, -1.00),
    (-0.56, -0.87), (-0.86, -0.60), (-0.99, -0.28), (-1.00, 0.00),
]

# ================================================================ the four models ==
def build_kdm_ship():
    """Kingdom steam gunboat - 'CLASSIC GUNBOAT' from the multi-class row."""
    M = [
        mat("timber", (0.098, 0.068, 0.046)),
        mat("deck",   (0.285, 0.200, 0.118)),
        mat("canvas", (0.660, 0.600, 0.462)),
        # Brass reads as brass only if the BASE COLOUR is warm and light - the bake keeps
        # colour, not metalness, so a dark metallic swatch comes out grey.
        mat("brass",  (0.720, 0.520, 0.170), 0.34, 0.90),
        mat("iron",   (0.150, 0.148, 0.156), 0.55, 0.80),
        mat("verdig", (0.180, 0.330, 0.286), 0.60, 0.30),
    ]
    W, D, C, B, I, V = range(6)
    b = Build("VEN_KdmGunboat", M)
    stations = [(-5.60, 0.08, 0.30), (-4.60, 0.52, 0.66), (-3.10, 0.92, 0.98),
                (-1.20, 1.20, 1.14), (0.90, 1.26, 1.16), (2.80, 1.18, 1.06),
                (4.20, 1.00, 0.88), (5.10, 0.86, 0.74)]
    b.hull(W, D, stations, PROFILE, mi_rail=B)
    for side in (1, -1):
        b.box(W, (1.35, side * 1.18, -0.18), (1.55, 0.85, 0.42))
        b.paddle_wheel(W, B, I, 1.35, side * 1.62, 1.16)
    b.tube(I, (-0.30, 0.0, 1.35), 0.30, 2.30, seg=18, taper=0.88)
    for zz in (0.55, 1.35, 2.15, 2.52):
        b.tube(B, (-0.30, 0.0, zz), 0.335, 0.13, seg=18)
    b.tube(B, (-1.45, 0.0, 0.34), 0.42, 0.62, seg=18)
    b.sphere(B, (-1.45, 0.0, 0.64), (0.42, 0.42, 0.26), u=18, v=9)
    b.box(W, (0.95, 0.0, 0.28), (2.30, 1.55, 0.72))
    b.box(B, (0.95, 0.0, 0.66), (2.36, 1.60, 0.09))
    b.tube(V, (2.55, 0.0, 0.36), 0.30, 1.05, seg=14, ry=math.radians(90))
    b.box(W, (-2.60, 0.0, 0.52), (1.30, 1.30, 1.00))
    b.box(B, (-2.60, 0.0, 0.86), (1.36, 1.36, 0.10))
    b.box(V, (-2.60, 0.0, 1.06), (1.10, 1.10, 0.30))
    b.tube(I, (-4.05, 0.0, 0.30), 0.26, 0.34, seg=14)
    b.tube(I, (-4.55, 0.0, 0.46), 0.105, 1.30, seg=12, ry=math.radians(90))
    # Smaller, canvas-coloured fins: the first pass had pale slabs that read as shelves.
    floor = b.envelope(C, B, (0.10, 0.0, 4.15), (3.30, 1.34, 1.24),
                       ribs=(-0.62, -0.21, 0.20, 0.60), fins=(0.85, 0.72), mi_fin=C)
    for sx in (-1.55, 1.70):
        for sy in (0.72, -0.72):
            h = floor - 0.34
            b.box(I, (sx, sy, 0.34 + h / 2.0), (0.11, 0.11, h))
    for i in range(1, len(stations) - 1):
        x, hw, _d = stations[i]
        b.box(D, (x, 0.0, -0.048), (0.20, hw * 1.66, 0.07))
        for side in (1, -1):
            b.box(W, (x, side * hw * 0.985, 0.17), (0.10, 0.07, 0.34))
    return b


def build_kdm_outpost():
    """KINGDOM PLATFORM, 'Observatory Sky-Dome' family - from the KINGDOM FLOATING
    PLATFORM COMPONENT SCHEMATICS sheet, not the fleet sheet.

    The distinction is the whole design and I got it wrong on the first pass. SHIPS carry
    ribbed gas bags; PLATFORMS do not - the sheet labels "HIGH-ALTITUDE BUOYANCY ENGINES"
    as an internal system, so a platform is a tiered armoured hull that simply hangs there.
    A first version built as a barge with two gas bags was reading as a fat airship.

    Everything here is a callout off that sheet or the sky-city in the painting: a stepped
    fortress hull, the brass observatory DOME with its lantern, celestial and planar sensor
    arrays, GEAR DRIVES (PADDLE SYSTEM), cargo docking arms, and an articulated heavy
    crane (KINGDOM STANDARD).
    """
    M = [
        mat("timber", (0.105, 0.074, 0.050)),
        mat("deck",   (0.300, 0.212, 0.126)),
        mat("stone",  (0.360, 0.330, 0.280)),          # armoured plating, pale ashlar
        mat("brass",  (0.740, 0.540, 0.180), 0.32, 0.90),
        mat("iron",   (0.150, 0.148, 0.156), 0.55, 0.80),
        mat("glass",  (0.230, 0.400, 0.400), 0.25, 0.10),
    ]
    W, D, S, B, I, G = range(6)
    b = Build("VEN_KdmOutpost", M)

    # --- tiered hull: a lozenge saucer stepping up to the observatory -----------
    b.sphere(S, (0.0, 0.0, -0.30), (7.20, 4.40, 1.15), u=44, v=22)
    b.ring(B, (0.0, 0.0, -0.30), 4.46, 1.20, 0.30, seg=40)          # rubbing strake
    b.tube(W, (0.0, 0.0, 0.62), 4.60, 0.90, seg=30, taper=0.92)     # main deck drum
    b.ring(B, (0.0, 0.0, 1.02), 4.30, 4.30, 0.14, seg=36)
    b.tube(S, (0.0, 0.0, 1.55), 3.30, 1.00, seg=26, taper=0.90)     # gallery tier
    b.ring(B, (0.0, 0.0, 2.00), 3.05, 3.05, 0.12, seg=32)
    b.tube(W, (0.0, 0.0, 2.35), 2.20, 0.70, seg=22, taper=0.92)     # drum under dome

    # Balustrade around the main deck, as drawn on the sky-city.
    for i in range(24):
        a = i * (TAU / 24.0)
        b.box(B, (math.cos(a) * 4.35, math.sin(a) * 4.35, 1.32), (0.13, 0.13, 0.46), rz=a)

    # --- the observatory dome, the sheet's signature ---------------------------
    b.sphere(B, (0.0, 0.0, 2.70), (2.05, 2.05, 1.70), u=34, v=17)
    b.ring(B, (0.0, 0.0, 2.72), 2.10, 2.10, 0.16, seg=32)
    b.sphere(G, (0.0, 0.0, 3.05), (1.55, 1.55, 1.30), u=26, v=13)   # glazing inside
    b.tube(B, (0.0, 0.0, 4.55), 0.42, 0.70, seg=14, taper=0.75)     # lantern
    b.sphere(B, (0.0, 0.0, 5.02), (0.34, 0.34, 0.30), u=14, v=7)

    # Corner cupolas on the gallery tier.
    for i in range(4):
        a = i * (TAU / 4.0) + math.radians(45)
        cx, cy = math.cos(a) * 2.55, math.sin(a) * 1.95
        b.sphere(B, (cx, cy, 2.28), (0.72, 0.72, 0.60), u=20, v=10)
        b.tube(B, (cx, cy, 2.86), 0.09, 0.42, seg=8)

    # --- CELESTIAL & PLANAR ARRAYS ---------------------------------------------
    for sgn in (1, -1):
        mx = sgn * 3.05
        b.tube(I, (mx, 0.0, 3.15), 0.11, 2.30, seg=10)
        for zz, half in ((3.95, 1.05), (4.35, 0.78)):
            b.box(I, (mx, 0.0, zz), (0.09, half * 2, 0.07))
        b.sphere(B, (mx, 0.0, 4.60), (0.30, 0.30, 0.26), u=14, v=7)   # sensor bulb
    # A dish for the atmospheric sensors.
    b.tube(B, (-1.9, 2.6, 2.30), 0.90, 0.22, seg=20, rx=math.radians(58), taper=0.35)

    # --- GEAR DRIVES (PADDLE SYSTEM) -------------------------------------------
    for side in (1, -1):
        b.box(W, (0.0, side * 3.55, -0.05), (3.00, 1.20, 0.60))
        b.paddle_wheel(W, B, I, 0.0, side * 4.45, 1.80, boards=10)

    # --- CARGO DOCKING ARMS ----------------------------------------------------
    for sx in (-6.5, 6.5):
        b.box(I, (sx, 0.0, 0.15), (1.60, 0.55, 0.28))
        for side in (1, -1):
            b.box(B, (sx * 1.18, side * 1.05, 0.15), (0.90, 0.36, 0.42))
            b.tube(B, (sx * 1.05, side * 1.05, 0.55), 0.07, 0.80, seg=6)

    # --- ARTICULATED HEAVY CRANE (KINGDOM STANDARD) ----------------------------
    b.tube(I, (3.4, -1.9, 1.70), 0.26, 1.60, seg=12)
    b.box(I, (4.5, -1.9, 3.05), (3.00, 0.24, 0.24), ry=math.radians(-26))
    b.box(I, (6.2, -1.9, 3.55), (1.90, 0.20, 0.20), ry=math.radians(14))
    b.tube(B, (7.0, -1.9, 2.70), 0.05, 1.60, seg=6)                  # fall
    b.box(B, (7.0, -1.9, 1.80), (0.40, 0.34, 0.30))                  # hook block

    # --- stacks, trailing the smoke the painting always shows ------------------
    for sx in (-2.5, -3.6):
        b.tube(I, (sx, 1.5, 2.30), 0.30, 2.20, seg=18, taper=0.88)
        for zz in (1.45, 2.30, 3.15):
            b.tube(B, (sx, 1.5, zz), 0.335, 0.13, seg=18)
    return b


def build_pir_ship():
    """HEAVY RAIDER 'BLOOD HAWK' family - angular armour, dreadnought ram, grappling
    arms, and HIGH-OUTPUT PLASMA ENGINES that are the only lit thing in the fleet."""
    M = [
        mat("gunmetal", (0.070, 0.072, 0.080), 0.50, 0.85),
        mat("armor",    (0.130, 0.128, 0.132), 0.62, 0.60),
        mat("blood",    (0.300, 0.045, 0.040), 0.60, 0.20),
        mat("brasspir", (0.430, 0.300, 0.110), 0.42, 0.85),
        mat("canvasp",  (0.180, 0.165, 0.155)),
        mat("plasma",   (0.900, 0.180, 0.090), 0.30, 0.0,
            emit=(1.00, 0.22, 0.08), emit_strength=6.0),
    ]
    G, A, R, B, C, P = range(6)
    b = Build("VEN_PirRaider", M)

    # Angular armoured hull - a wedge, not a boat. Narrow, deep and mean.
    stations = [(-6.60, 0.06, 0.55), (-5.20, 0.46, 0.86), (-3.40, 0.86, 1.06),
                (-1.20, 1.06, 1.14), (1.00, 1.02, 1.10), (3.00, 0.86, 0.96),
                (4.60, 0.62, 0.76), (5.60, 0.40, 0.58)]
    b.hull(G, A, stations, PROFILE, bulwark=0.30)

    # DREADNOUGHT RAM - the schematic's callout, a spike off the bow.
    b.tube(A, (-7.55, 0.0, -0.18), 0.42, 2.10, seg=12, ry=math.radians(90), taper=0.06)
    b.box(R, (-6.30, 0.0, -0.18), (0.70, 0.86, 0.50))

    # Armour plating along the flanks, canted like the drawing.
    for side in (1, -1):
        for sx, sl in ((-3.6, 2.0), (-1.2, 2.2), (1.2, 2.0), (3.2, 1.5)):
            b.box(A, (sx, side * 1.02, -0.12), (sl, 0.20, 0.78), rx=side * math.radians(12))
        b.box(R, (0.0, side * 1.05, 0.30), (5.6, 0.10, 0.16))

    # GRAPPLING MECHANISMS - arms with claws, port and starboard.
    for side in (1, -1):
        b.box(B, (-2.2, side * 1.35, 0.10), (0.30, 0.90, 0.22))
        b.box(A, (-2.2, side * 1.95, 0.10), (0.24, 0.55, 0.50))
        for cz in (0.30, -0.30):
            b.box(B, (-2.55, side * 2.20, 0.10 + cz), (0.60, 0.16, 0.16),
                  rx=side * math.radians(28))

    # HIGH-OUTPUT PLASMA ENGINES: housings with glowing cores at the stern.
    for side in (1, -1):
        b.tube(G, (4.10, side * 0.72, 0.05), 0.42, 2.20, seg=16, ry=math.radians(90))
        b.ring(B, (4.95, side * 0.72, 0.05), 0.46, 0.46, 0.16, seg=18)
        b.tube(P, (5.35, side * 0.72, 0.05), 0.34, 0.30, seg=16, ry=math.radians(90))
    b.tube(P, (5.30, 0.0, 0.55), 0.20, 0.24, seg=14, ry=math.radians(90))

    # Turret and a raked mast with a pirate vane.
    b.tube(A, (-0.6, 0.0, 0.52), 0.52, 0.42, seg=14)
    b.tube(G, (-1.5, 0.0, 0.68), 0.11, 1.60, seg=10, ry=math.radians(90))
    b.tube(A, (1.4, 0.0, 1.30), 0.09, 2.10, seg=8, ry=math.radians(18))
    b.box(R, (2.05, 0.0, 2.35), (0.90, 0.05, 0.46))

    # Dark armoured gas bag - pirates fly the same principle, uglier.
    floor = b.envelope(C, A, (-0.30, 0.0, 3.95), (4.30, 1.20, 1.05),
                       ribs=(-0.60, -0.20, 0.20, 0.60), fins=(1.00, 0.85), mi_fin=R)
    for sx in (-2.4, 0.4, 2.6):
        for sy in (0.62, -0.62):
            h = floor - 0.30
            b.box(G, (sx, sy, 0.30 + h / 2.0), (0.13, 0.13, h))
    return b


def build_pir_hub():
    """PIRATE ARMADA HUB (CLASS 1) - the schematic's top view is a cross: a central mass
    with four arms, plasma turrets on the ends, and a sensor array on a mast."""
    M = [
        mat("gunmetal", (0.070, 0.072, 0.080), 0.50, 0.85),
        mat("armor",    (0.130, 0.128, 0.132), 0.62, 0.60),
        mat("blood",    (0.300, 0.045, 0.040), 0.60, 0.20),
        mat("brasspir", (0.430, 0.300, 0.110), 0.42, 0.85),
        mat("scrap",    (0.190, 0.170, 0.140)),
        mat("plasma",   (0.900, 0.180, 0.090), 0.30, 0.0,
            emit=(1.00, 0.22, 0.08), emit_strength=6.0),
    ]
    G, A, R, B, S, P = range(6)
    b = Build("VEN_PirHub", M)

    # Central mass: a stack of canted armoured drums.
    b.tube(A, (0.0, 0.0, 0.0), 3.10, 1.70, seg=16)
    b.ring(B, (0.0, 0.0, 0.0), 3.16, 3.16, 0.22, seg=20)
    b.tube(G, (0.0, 0.0, 1.15), 2.35, 1.10, seg=14)
    b.tube(A, (0.0, 0.0, 2.05), 1.55, 0.90, seg=12)
    b.tube(S, (0.0, 0.0, -1.05), 2.10, 1.00, seg=14, taper=0.55)

    # Four arms in a cross, each ending in a plasma turret - the top view's shape.
    for i in range(4):
        a = i * (TAU / 4.0)
        cx, cy = math.cos(a), math.sin(a)
        for t in (3.6, 5.0):
            b.box(G, (cx * t, cy * t, 0.10), (2.00, 0.90, 0.62), rz=a)
        b.box(A, (cx * 6.1, cy * 6.1, 0.10), (1.10, 1.30, 1.00), rz=a)
        # Turret: collar, barrels, and a glowing core.
        b.tube(A, (cx * 6.6, cy * 6.6, 0.55), 0.62, 0.50, seg=14)
        b.ring(B, (cx * 6.6, cy * 6.6, 0.55), 0.66, 0.66, 0.14, seg=16)
        for off in (-0.22, 0.22):
            b.tube(G, (cx * 7.5 - cy * off, cy * 7.5 + cx * off, 0.55), 0.11, 1.60,
                   seg=8, ry=math.radians(90), rx=a)
        b.tube(P, (cx * 6.6, cy * 6.6, 0.92), 0.30, 0.22, seg=14)
        # Scrap plating hung off the arms - a hub built from wreckage.
        for sgn in (1, -1):
            b.box(S, (cx * 4.3 - cy * sgn * 1.05, cy * 4.3 + cx * sgn * 1.05, -0.20),
                  (1.40, 0.16, 0.90), rz=a)

    # Sensor array on a mast, with a blood-red vane.
    b.tube(G, (0.0, 0.0, 3.40), 0.16, 2.00, seg=10)
    b.box(A, (0.0, 0.0, 4.45), (1.90, 0.14, 0.10))
    b.box(A, (0.0, 0.0, 4.75), (1.30, 0.14, 0.10))
    b.box(R, (0.70, 0.0, 5.15), (1.30, 0.05, 0.55))
    b.tube(P, (0.0, 0.0, 2.60), 0.26, 0.20, seg=14)

    # Mooring spars for raiders to tie up to, and a ring of hanging chains.
    for i in range(8):
        a = i * (TAU / 8.0) + (TAU / 16.0)
        cx, cy = math.cos(a), math.sin(a)
        b.box(B, (cx * 3.5, cy * 3.5, -0.75), (1.20, 0.14, 0.14), rz=a)
        b.tube(S, (cx * 4.0, cy * 4.0, -1.35), 0.06, 1.20, seg=6)
    return b


BUILDERS = {
    "kdm_ship": build_kdm_ship,
    "kdm_outpost": build_kdm_outpost,
    "pir_ship": build_pir_ship,
    "pir_hub": build_pir_hub,
}


# ================================================================ bake and export ==
def finish(b, out_path, target):
    scene = bpy.context.scene
    bm = b.bm

    # Bevel HARD edges only: rounding every edge quilts a smooth-shaded gas bag once the
    # mesh is dense enough that the decimator no longer erases the creases.
    hard = [e for e in bm.edges
            if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(22)]
    bmesh.ops.bevel(bm, geom=hard, offset=0.010, segments=3, profile=0.62,
                    affect="EDGES", clamp_overlap=True)
    _log("%s: bevelled %d hard edges -> %d faces" % (b.name, len(hard), len(bm.faces)))

    mesh = bpy.data.meshes.new(b.name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(b.name, mesh)
    scene.collection.objects.link(obj)
    for m in b.materials:
        obj.data.materials.append(m)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_flat()

    # High-poly reference: subdivide a COPY. Without this the reference is the same mesh
    # as the low-poly, the ratio comes out 1.000, and the normal bake writes the mesh
    # against itself - a flat map, which is the failure this stage exists to avoid.
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.duplicate()
    high = bpy.context.view_layer.objects.active
    high.name = b.name + "_HIGH"
    bpy.context.view_layer.objects.active = high
    sub = high.modifiers.new("subsurf", "SUBSURF")
    sub.levels = sub.render_levels = 2
    bpy.ops.object.modifier_apply(modifier=sub.name)

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    # Triangulate FIRST so counts are in the unit the budget is written in - the exporter
    # triangulates on the way out, so a ratio taken against quads ships far more.
    tri = obj.modifiers.new("triangulate", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=tri.name)
    before = len(obj.data.polygons)
    if before > target:
        dec = obj.modifiers.new("decimate", "DECIMATE")
        dec.ratio = float(target) / before
        bpy.ops.object.modifier_apply(modifier=dec.name)
    _log("%s: high %d tris -> low %d tris" % (b.name, len(high.data.polygons),
                                              len(obj.data.polygons)))

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.022)
    bpy.ops.object.mode_set(mode="OBJECT")

    scene.render.engine = "CYCLES"
    try:
        scene.cycles.device = "CPU"
        scene.cycles.samples = 4
        scene.cycles.use_denoising = False
    except Exception:                     # noqa: BLE001
        pass
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.margin = 8

    def new_image(name, color, non_color=False):
        img = bpy.data.images.new(name, TEX, TEX, alpha=False)
        img.generated_color = color
        if non_color:
            img.colorspace_settings.name = "Non-Color"
        return img

    def bake_to(img, bake_type, **kw):
        targets = []
        for slot in obj.material_slots:
            m = slot.material
            node = m.node_tree.nodes.new("ShaderNodeTexImage")
            node.image = img
            m.node_tree.nodes.active = node
            node.select = True
            targets.append((m, node))
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.bake(type=bake_type, **kw)
        for m, node in targets:
            m.node_tree.nodes.remove(node)

    root = os.path.splitext(out_path)[0]
    diffuse = new_image(b.name + "_d", (0.5, 0.5, 0.5, 1.0))
    bake_to(diffuse, "DIFFUSE", pass_filter={"COLOR"})
    diffuse.filepath_raw = root + "_diffuse.png"
    diffuse.file_format = "PNG"
    diffuse.save()

    emissive = new_image(b.name + "_e", (0.0, 0.0, 0.0, 1.0))
    bake_to(emissive, "EMIT")
    emissive.filepath_raw = root + "_emissive.png"
    emissive.file_format = "PNG"
    emissive.save()

    normal = new_image(b.name + "_n", (0.5, 0.5, 1.0, 1.0), non_color=True)
    try:
        scene.render.bake.use_selected_to_active = True
        scene.render.bake.cage_extrusion = 0.35
        bpy.ops.object.select_all(action="DESELECT")
        high.select_set(True)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        for slot in obj.material_slots:
            m = slot.material
            node = m.node_tree.nodes.new("ShaderNodeTexImage")
            node.image = normal
            m.node_tree.nodes.active = node
            node.select = True
        bpy.ops.object.bake(type="NORMAL")
    except Exception as e:                            # noqa: BLE001
        _log("%s: normal bake failed (%s) - shipping flat" % (b.name, e))
    finally:
        scene.render.bake.use_selected_to_active = False
    normal.filepath_raw = root + "_normal.png"
    normal.file_format = "PNG"
    normal.save()

    bpy.data.objects.remove(high, do_unlink=True)

    import numpy as np                                          # noqa: E402
    px = np.empty(len(diffuse.pixels), dtype=np.float32)
    diffuse.pixels.foreach_get(px)
    rgba = px.reshape(-1, 4)
    lum = rgba[:, :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    lum = np.clip((lum - 0.5) * 1.3 + 0.5, 0.0, 1.0) * 0.45
    spec = new_image(b.name + "_s", (0.0, 0.0, 0.0, 1.0))
    spec.pixels.foreach_set(np.stack([lum, lum, lum, np.ones_like(lum)], axis=1).ravel())
    spec.filepath_raw = root + "_specular.png"
    spec.file_format = "PNG"
    spec.save()

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.obj_export(filepath=out_path, export_selected_objects=True,
                          export_materials=False, export_triangulated_mesh=True,
                          export_normals=True, export_uv=True)
    _log("%s: wrote %s" % (b.name, out_path))


os.makedirs(OUTDIR, exist_ok=True)
names = list(BUILDERS) if WHICH == "all" else [WHICH]
for key in names:
    new_scene()
    builder = BUILDERS[key]()
    finish(builder, os.path.join(OUTDIR, builder.name + ".obj"), TARGET)
