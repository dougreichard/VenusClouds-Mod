"""Generate the whole Venus roster from PROCEDURAL geometry, against the concept art.

    blender --background --python _venus_scratch_roster.py -- <outdir> [which] [tex] [tris]

    which: a class key, a faction prefix (kdm/pir), or "all" (default)

No kitbash, no packs, no prop farm - every vertex is authored here. The roster and the
detailing come from the five schematic sheets in `E:/a/venus_clouds` plus the two fleet
paintings:

    Gemini ...mxs9xz  KINGDOM / PIRATE FLEET COMPONENT       (also _refs/_grid_fleet_component)
    Gemini ...n6hrtu  KINGDOM / PIRATE FLEET COMPONENT (II)   Bulwark, Sentinel, Thunderbolt,
                                                              Maelstrom, Nighthawk, Scavenger
    Gemini ...5adcyc  KINGDOM FLEET NAVAL COMPONENT           Valor-Wing, Shadow-Sentinel,
                                                              Gold-Harvest, Roy-Sky-Dome
    Gemini ...gd1l7f  KINGDOM FLOATING PLATFORM               Skyward Citadel, Harvester's
                                                              Reach, Mender's Berth, Sky-Dome
    Gemini ...ogu7jo  PIRATE FLOATING PLATFORM                Dreadnought Raider, Repair Rig
    Gemini ...t81ul2  PIRATE FLEET CAPITAL SHIPS              Black-Tide, Scrap King, Ghost

FOUR ARCHETYPES, because that is how the sheets are organised, and a per-class table of
parameters. The single most important distinction, and the one that was got wrong first
time: SHIPS carry ribbed gas bags; PLATFORMS do not. The platform sheets label
"HIGH-ALTITUDE BUOYANCY ENGINES" as an internal system, so a platform is a tiered armoured
hull that simply hangs there.

Kingdom reads brass-over-timber and nothing glows. Pirate reads gunmetal and blood red with
HIGH-OUTPUT PLASMA ENGINES, authored as real emission so they land in the emissive map.
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
TARGET = int(argv[3]) if len(argv) > 3 else 14000

TAU = math.pi * 2.0


def _log(msg):
    print("ROSTER: %s" % msg)


def _mat(name, rgb, rough=0.85, metallic=0.0, emit=None, strength=6.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    if emit is not None:
        b.inputs["Emission Color"].default_value = (emit[0], emit[1], emit[2], 1.0)
        b.inputs["Emission Strength"].default_value = strength
    return m


def kdm_palette():
    # Brass reads as brass only if the BASE COLOUR is warm and light - the bake keeps
    # colour and discards metalness, so a dark metallic swatch comes out grey.
    return [_mat("timber", (0.100, 0.070, 0.048)),
            _mat("deck",   (0.292, 0.206, 0.122)),
            _mat("canvas", (0.660, 0.600, 0.462)),
            _mat("brass",  (0.740, 0.540, 0.180), 0.32, 0.90),
            _mat("iron",   (0.150, 0.148, 0.156), 0.55, 0.80),
            _mat("glass",  (0.230, 0.400, 0.400), 0.25, 0.10)]


def pir_palette():
    return [_mat("gunmetal", (0.070, 0.072, 0.080), 0.50, 0.85),
            _mat("armor",    (0.130, 0.128, 0.132), 0.62, 0.60),
            _mat("canvasp",  (0.088, 0.086, 0.092), 0.45, 0.70),
            _mat("brasspir", (0.430, 0.300, 0.110), 0.42, 0.85),
            _mat("blood",    (0.300, 0.045, 0.040), 0.60, 0.20),
            _mat("plasma",   (0.900, 0.180, 0.090), 0.30, 0.0, (1.00, 0.22, 0.08))]


# Slot names are shared between palettes so the archetypes can index them by meaning.
HULL, DECK, SKIN, TRIM, MECH, GLOW = range(6)

PROFILE = [
    (1.00, 0.00), (0.99, -0.28), (0.86, -0.60), (0.56, -0.87),
    (0.00, -1.00),
    (-0.56, -0.87), (-0.86, -0.60), (-0.99, -0.28), (-1.00, 0.00),
]


class Build:
    def __init__(self, name, materials):
        self.name = name
        self.materials = materials
        self.bm = bmesh.new()

    def prim(self, op, mi, matrix=None, **kw):
        """New geometry comes from the OPERATOR'S RETURN VALUE - a positional slice of
        bm.verts is not reliable once bmesh.ops has run repeatedly."""
        res = op(self.bm, **kw)
        verts = list(res.get("verts", []))
        if matrix is not None and verts:
            bmesh.ops.transform(self.bm, matrix=matrix, verts=verts)
        vs = set(verts)
        faces = list(dict.fromkeys(
            f for v in verts for f in v.link_faces if vs.issuperset(f.verts)))
        for f in faces:
            f.material_index = mi
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)

    def box(self, mi, c, s, rx=0.0, ry=0.0, rz=0.0):
        m = Matrix.Translation(Vector(c))
        if rz:
            m = m @ Matrix.Rotation(rz, 4, "Z")
        if ry:
            m = m @ Matrix.Rotation(ry, 4, "Y")
        if rx:
            m = m @ Matrix.Rotation(rx, 4, "X")
        self.prim(bmesh.ops.create_cube, mi,
                  matrix=m @ Matrix.Diagonal(Vector(s).to_4d()), size=1.0)

    def tube(self, mi, c, r, h, seg=16, rx=0.0, ry=0.0, taper=1.0):
        m = Matrix.Translation(Vector(c))
        if ry:
            m = m @ Matrix.Rotation(ry, 4, "Y")
        if rx:
            m = m @ Matrix.Rotation(rx, 4, "X")
        self.prim(bmesh.ops.create_cone, mi, matrix=m, cap_ends=True, cap_tris=False,
                  segments=seg, radius1=r, radius2=r * taper, depth=h)

    def ring(self, mi, c, r1, r2, thick, seg=30, axis="X"):
        """A hoop whose AXLE runs along `axis`.

        The axis is not decoration - a paddle wheel's axle is athwartships ("Y") while an
        envelope's ribs run fore-and-aft ("X"), and a strake around a drum is horizontal
        ("Z"). Hard-coding one rotation put every paddle rim 90 degrees out, so the wheels
        read as hoops lying the wrong way while their boards sat correctly.
        """
        rot = {"X": Matrix.Rotation(math.radians(90), 4, "Y"),
               "Y": Matrix.Rotation(math.radians(90), 4, "X"),
               "Z": Matrix.Identity(4)}[axis]
        self.prim(bmesh.ops.create_cone, mi,
                  matrix=Matrix.Translation(Vector(c)) @ rot
                  @ Matrix.Diagonal(Vector((r1, r2, 1.0)).to_4d()),
                  cap_ends=False, cap_tris=False, segments=seg,
                  radius1=1.0, radius2=1.0, depth=thick)

    def sphere(self, mi, c, r, u=32, v=16):
        self.prim(bmesh.ops.create_uvsphere, mi,
                  matrix=Matrix.Translation(Vector(c)) @ Matrix.Diagonal(Vector(r).to_4d()),
                  u_segments=u, v_segments=v, radius=1.0)

    # ---------------------------------------------------------------- big pieces --
    def hull(self, mi_hull, mi_deck, length, beam, depth, bulwark=0.34, mi_rail=None,
             blunt=False):
        """A lofted hull, scaled from a normalised set of stations."""
        base = [(-1.00, 0.05, 0.28), (-0.82, 0.42, 0.60), (-0.55, 0.76, 0.88),
                (-0.21, 0.98, 1.00), (0.16, 1.00, 1.00), (0.50, 0.92, 0.92),
                (0.75, 0.78, 0.76), (0.91, 0.62, 0.62)]
        if blunt:                       # ironclads and logistics hulls are slab-sided
            base = [(x, min(1.0, hw * 1.18), d) for x, hw, d in base]
        stations = [(x * length, hw * beam, d * depth) for x, hw, d in base]
        rings = []
        for x, hw, dp in stations:
            rings.append([self.bm.verts.new((x, yf * hw, zf * dp)) for yf, zf in PROFILE])
        self.bm.verts.ensure_lookup_table()
        faces = []
        for a, b in zip(rings, rings[1:]):
            for i in range(len(PROFILE) - 1):
                faces.append(self.bm.faces.new((a[i], a[i + 1], b[i + 1], b[i])))
            faces.append(self.bm.faces.new((a[-1], a[0], b[0], b[-1])))
        faces.append(self.bm.faces.new(list(reversed(rings[0]))))
        faces.append(self.bm.faces.new(rings[-1]))
        for f in faces:
            f.material_index = mi_hull
        # Recalc now - the bevel later deletes and rebuilds these faces.
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)
        prev = None
        for x, hw, _d in stations[1:-1]:
            cur = (self.bm.verts.new((x, hw * 0.88, -0.09)),
                   self.bm.verts.new((x, -hw * 0.88, -0.09)))
            if prev:
                f = self.bm.faces.new((prev[0], prev[1], cur[1], cur[0]))
                f.material_index = mi_deck
            prev = cur
        for side in (1, -1):
            pv = None
            for x, hw, _d in stations[1:-1]:
                lo = self.bm.verts.new((x, side * hw, 0.0))
                hi = self.bm.verts.new((x, side * hw * 0.97, bulwark))
                if pv is not None:
                    f = self.bm.faces.new((pv[0], lo, hi, pv[1]) if side > 0
                                          else (pv[1], hi, lo, pv[0]))
                    f.material_index = mi_hull
                pv = (lo, hi)
                if mi_rail is not None:
                    self.box(mi_rail, (x, side * hw * 0.97, bulwark + 0.03),
                             (length * 0.06, 0.10, 0.07))
        return stations

    def envelope(self, mi_skin, mi_rib, c, r, ribs=4, fins=True, mi_fin=None):
        c, r = Vector(c), Vector(r)
        self.sphere(mi_skin, c, r, u=52, v=26)
        for i in range(ribs):
            t = -0.66 + i * (1.32 / max(1, ribs - 1))
            s = math.sqrt(max(0.0, 1.0 - t * t)) * 1.02
            self.ring(mi_rib, (c.x + t * r.x, c.y, c.z), r.y * s, r.z * s, 0.10, seg=28)
        if fins:
            fm = mi_fin if mi_fin is not None else mi_skin
            fx = c.x + r.x - 0.30
            # Tapered wedge fins, not slabs: flat plates read as shelves stuck on the bag.
            self.box(fm, (fx, 0.0, c.z + r.z * 0.86), (r.x * 0.26, 0.09, r.z * 0.72),
                     ry=math.radians(16))
            for sgn in (1, -1):
                self.box(fm, (fx, sgn * r.y * 0.74, c.z),
                         (r.x * 0.26, r.y * 0.80, 0.09), rx=sgn * math.radians(12))
        return c.z - r.z

    def whale(self, mi_skin, mi_plate, c, r, seg=13):
        """A METALLIC, WHALE-LIKE envelope - the pirate bag, per the art direction.

        Not an ellipsoid. Lofted from a profile with a blunt snout, the mass carried
        forward, and a long tapering tail with flukes: it reads as a hunting animal
        rather than a balloon, and the plating rings make it metal rather than canvas.
        """
        c, r = Vector(c), Vector(r)
        prof = [(-1.00, 0.10, 0.12, 0.02), (-0.92, 0.52, 0.55, 0.04),
                (-0.74, 0.86, 0.92, 0.03), (-0.50, 1.00, 1.00, 0.00),
                (-0.20, 0.97, 0.95, -0.02), (0.12, 0.84, 0.80, -0.04),
                (0.44, 0.62, 0.56, -0.05), (0.70, 0.40, 0.34, -0.04),
                (0.88, 0.22, 0.18, -0.02), (1.00, 0.08, 0.07, 0.00)]
        rings = []
        for t, ws, hs, dz in prof:
            ring = []
            for i in range(seg):
                a = i / float(seg) * TAU
                ring.append(self.bm.verts.new((
                    c.x + t * r.x,
                    c.y + math.cos(a) * r.y * ws,
                    c.z + math.sin(a) * r.z * hs + dz * r.z)))
            rings.append(ring)
        self.bm.verts.ensure_lookup_table()
        faces = []
        for a_, b_ in zip(rings, rings[1:]):
            for i in range(seg):
                j = (i + 1) % seg
                faces.append(self.bm.faces.new((a_[i], a_[j], b_[j], b_[i])))
        faces.append(self.bm.faces.new(list(reversed(rings[0]))))
        faces.append(self.bm.faces.new(rings[-1]))
        for f in faces:
            f.material_index = mi_skin
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)
        for t, ws, hs, _dz in prof[2:7]:
            self.ring(mi_plate, (c.x + t * r.x, c.y, c.z), r.y * ws * 1.03,
                      r.z * hs * 1.03, 0.12, seg=seg * 2, axis="X")
        for k in range(5):
            t = -0.55 + k * 0.26
            h = r.z * (0.30 - abs(t) * 0.12)
            self.box(mi_plate, (c.x + t * r.x, c.y, c.z + r.z * 0.92 + h * 0.4),
                     (r.x * 0.10, 0.10, h), ry=math.radians(-22))
        for sgn in (1, -1):
            self.box(mi_plate, (c.x + r.x * 0.92, sgn * r.y * 0.38, c.z),
                     (r.x * 0.22, r.y * 0.60, 0.10), rx=sgn * math.radians(24))
        self.box(mi_plate, (c.x + r.x * 0.90, 0.0, c.z + r.z * 0.42),
                 (r.x * 0.20, 0.09, r.z * 0.55), ry=math.radians(20))
        return c.z - r.z

    def locomotive(self, mi_iron, mi_plate, mi_brass, mi_glow, c, length, radius):
        """A STEAM LOCOMOTIVE slung under the whale, with jet exhaust out the back.

        Boiler, banded barrel, chimney and steam dome up front, driving wheels with a
        coupling rod along the flank, cab at the rear, and plasma nozzles firing aft.
        This is why the pirates read as machinery where the Kingdom reads as seamanship.
        """
        c = Vector(c)
        self.tube(mi_iron, (c.x, c.y, c.z), radius, length, seg=20, ry=math.radians(90))
        for k in (-0.34, -0.10, 0.16, 0.40):
            self.tube(mi_brass, (c.x + k * length, c.y, c.z), radius * 1.07, 0.12,
                      seg=20, ry=math.radians(90))
        self.tube(mi_plate, (c.x - length * 0.52, c.y, c.z), radius * 1.10, 0.30,
                  seg=20, ry=math.radians(90))
        self.tube(mi_iron, (c.x - length * 0.40, c.y, c.z + radius * 1.25),
                  radius * 0.30, radius * 1.10, seg=14, taper=1.25)
        self.sphere(mi_brass, (c.x - length * 0.12, c.y, c.z + radius * 1.05),
                    (radius * 0.34, radius * 0.34, radius * 0.30), u=16, v=8)
        # COW CATCHER (the pilot) - the raked, slatted wedge off the nose. A locomotive
        # without one reads as a boiler on wheels; it is the single silhouette cue that
        # says "engine", and on a raider it doubles as the thing it boards you with.
        nose = c.x - length * 0.62
        for i in range(9):
            t = (i - 4) / 4.0                       # -1..1 across the beam
            span = 1.0 - abs(t) * 0.62              # the wedge narrows toward the rails
            self.box(mi_plate,
                     (nose - radius * 0.62 * span, c.y + t * radius * 1.45,
                      c.z - radius * 0.70 - radius * 0.34 * (1.0 - span)),
                     (radius * 1.55 * span, 0.09, 0.11), ry=math.radians(34))
        # Frame: a top rail across the smokebox and a bottom rail at the point.
        self.box(mi_iron, (nose - radius * 0.10, c.y, c.z - radius * 0.34),
                 (radius * 0.42, radius * 2.90, 0.14))
        self.box(mi_iron, (nose - radius * 1.02, c.y, c.z - radius * 1.16),
                 (radius * 0.34, radius * 1.10, 0.14))
        for sgn in (1, -1):
            self.box(mi_iron, (nose - radius * 0.56, c.y + sgn * radius * 1.42,
                               c.z - radius * 0.76),
                     (radius * 1.45, 0.11, 0.13), ry=math.radians(34))
        # Buffer beam and a lamp above it, so the nose has mass.
        self.box(mi_plate, (nose + radius * 0.18, c.y, c.z - radius * 0.10),
                 (radius * 0.22, radius * 2.30, radius * 0.55))
        self.tube(mi_brass, (nose + radius * 0.05, c.y, c.z + radius * 0.55),
                  radius * 0.22, radius * 0.34, seg=12, ry=math.radians(90))

        self.box(mi_plate, (c.x + length * 0.40, c.y, c.z + radius * 0.85),
                 (length * 0.22, radius * 1.70, radius * 1.30))
        self.box(mi_brass, (c.x + length * 0.40, c.y, c.z + radius * 1.52),
                 (length * 0.24, radius * 1.78, 0.10))
        for side in (1, -1):
            for i in range(3):
                wx = c.x + (i - 1) * length * 0.24
                self.ring(mi_brass, (wx, c.y + side * radius * 1.05, c.z - radius * 0.85),
                          radius * 0.52, radius * 0.52, 0.14, seg=16, axis="Y")
                for k in range(6):
                    a = k / 6.0 * TAU
                    self.box(mi_iron, (wx + math.cos(a) * radius * 0.26,
                                       c.y + side * radius * 1.05,
                                       c.z - radius * 0.85 + math.sin(a) * radius * 0.26),
                             (radius * 0.50, 0.06, 0.06), ry=-a)
            self.box(mi_iron, (c.x, c.y + side * radius * 1.22, c.z - radius * 1.15),
                     (length * 0.62, 0.07, 0.12))
        for side in (1, -1):
            ex = c.x + length * 0.60
            self.tube(mi_iron, (ex, c.y + side * radius * 0.60, c.z), radius * 0.40,
                      length * 0.26, seg=14, ry=math.radians(90))
            self.ring(mi_brass, (ex + length * 0.12, c.y + side * radius * 0.60, c.z),
                      radius * 0.43, radius * 0.43, 0.14, seg=16, axis="X")
            self.tube(mi_glow, (ex + length * 0.17, c.y + side * radius * 0.60, c.z),
                      radius * 0.30, 0.26, seg=14, ry=math.radians(90))

    def paddle(self, mi_wood, mi_brass, mi_iron, x, y, r, boards=8):
        self.tube(mi_iron, (x, y, 0.0), r * 0.17, 0.46, seg=14, rx=math.radians(90))
        for i in range(boards):
            a = i / float(boards) * TAU
            cy, cz = math.cos(a), math.sin(a)
            self.box(mi_brass, (x + cy * r * 0.55, y, cz * r * 0.55),
                     (r * 0.92, 0.07, 0.07), ry=-a)
            self.box(mi_wood, (x + cy * r, y, cz * r), (r * 0.26, r * 0.54, 0.09), ry=-a)
        self.ring(mi_brass, (x, y, 0.0), r, r, 0.52, seg=30, axis="Y")
        self.box(mi_wood, (x, y, r * 0.92), (r * 1.55, 0.74, 0.40))
        self.box(mi_brass, (x, y, r * 1.14), (r * 1.60, 0.78, 0.09))
        self.tube(mi_brass, (x - r * 0.86, y * 0.82, 0.10), r * 0.29, 0.14, seg=16,
                  rx=math.radians(90))

    def stack(self, mi_iron, mi_brass, x, y, z, r, h):
        self.tube(mi_iron, (x, y, z), r, h, seg=18, taper=0.88)
        for k in (-0.38, 0.0, 0.38):
            self.tube(mi_brass, (x, y, z + k * h), r * 1.12, 0.13, seg=18)

    def crane(self, mi_iron, mi_brass, x, y, z, reach):
        """ARTICULATED HEAVY CRANE (KINGDOM STANDARD) / recovery crane."""
        self.tube(mi_iron, (x, y, z), 0.26, 1.60, seg=12)
        self.box(mi_iron, (x + reach * 0.34, y, z + 1.30), (reach * 0.80, 0.26, 0.26),
                 ry=math.radians(-26))
        self.box(mi_iron, (x + reach * 0.80, y, z + 1.75), (reach * 0.52, 0.22, 0.22),
                 ry=math.radians(14))
        self.tube(mi_brass, (x + reach, y, z + 0.90), 0.05, 1.70, seg=6)
        self.box(mi_brass, (x + reach, y, z + 0.05), (0.42, 0.36, 0.32))

    def turret(self, mi_armor, mi_brass, mi_barrel, x, y, z, r, barrels=2, length=1.6,
               mi_core=None):
        self.tube(mi_armor, (x, y, z), r, r * 0.85, seg=14)
        self.ring(mi_brass, (x, y, z), r * 1.06, r * 1.06, 0.14, seg=16,
                  axis="Z")
        for i in range(barrels):
            off = (i - (barrels - 1) / 2.0) * r * 0.55
            self.tube(mi_barrel, (x - length * 0.55, y + off, z + r * 0.20), r * 0.18,
                      length, seg=8, ry=math.radians(90))
        if mi_core is not None:
            self.tube(mi_core, (x, y, z + r * 0.62), r * 0.48, r * 0.30, seg=14)

    def rotor(self, mi_iron, mi_brass, x, y, z, r, blades=4):
        """SINGLE MAIN ROTOR - the scout skiff and the heli-craft tenders."""
        self.tube(mi_iron, (x, y, z - 0.55), 0.10, 1.10, seg=10)
        self.tube(mi_brass, (x, y, z), 0.20, 0.20, seg=12)
        for i in range(blades):
            a = i / float(blades) * TAU
            self.box(mi_iron, (x + math.cos(a) * r * 0.5, y + math.sin(a) * r * 0.5, z),
                     (r, 0.22, 0.05), rz=a)

    def claws(self, mi_arm, mi_grip, x, y, z, reach):
        """EXTERNAL SALVAGE & HARVESTING CLAWS / grappling mechanisms."""
        for side in (1, -1):
            self.box(mi_arm, (x, side * (y + reach * 0.35), z), (0.30, reach * 0.80, 0.24))
            self.box(mi_arm, (x, side * (y + reach * 0.85), z), (0.26, reach * 0.40, 0.44))
            for cz in (0.34, -0.34):
                self.box(mi_grip, (x - 0.30, side * (y + reach * 1.05), z + cz),
                         (0.66, 0.16, 0.16), rx=side * math.radians(28))

    def cargo(self, mi_a, mi_b, x, y, z, n, size):
        """CARGO MODULES (BULK SALVAGE) slung in racks."""
        for i in range(n):
            sx = x + (i - (n - 1) / 2.0) * size[0] * 1.25
            for side in (1, -1):
                self.box(mi_a if (i % 2 == 0) else mi_b, (sx, side * y, z), size)


# ================================================================== archetypes ====
def kdm_ship(b, s):
    """Kingdom airship: timber hull, ribbed bag, paddle wheels, stack, brass."""
    st = b.hull(HULL, DECK, s["len"], s["beam"], s["depth"], mi_rail=TRIM,
                blunt=s.get("blunt", False))
    for side in (1, -1):
        px = s["len"] * s.get("paddle_x", 0.22)
        b.box(HULL, (px, side * s["beam"] * 0.95, -0.18),
              (s["len"] * 0.26, s["beam"] * 0.70, 0.42))
        b.paddle(HULL, TRIM, MECH, px, side * s["beam"] * 1.32, s["beam"] * 0.95,
                 boards=s.get("boards", 8))
    for i, sx in enumerate(s.get("stacks", [-0.06])):
        b.stack(MECH, TRIM, s["len"] * sx, 0.0, s["depth"] * 1.10, 0.30, 2.20)
    # Superstructure: a deckhouse and, on the bigger classes, brass domes.
    b.box(HULL, (-s["len"] * 0.42, 0.0, 0.52), (s["len"] * 0.22, s["beam"] * 1.05, 1.00))
    b.box(TRIM, (-s["len"] * 0.42, 0.0, 0.88), (s["len"] * 0.23, s["beam"] * 1.10, 0.10))
    for dx in s.get("domes", []):
        b.sphere(TRIM, (s["len"] * dx, 0.0, 0.95), (s["beam"] * 0.55,) * 2 +
                 (s["beam"] * 0.45,), u=22, v=11)
    for tx in s.get("turrets", []):
        b.turret(HULL, TRIM, MECH, s["len"] * tx, 0.0, 0.62, s["beam"] * 0.34)
    if s.get("railgun"):
        b.tube(MECH, (-s["len"] * 0.30, 0.0, 0.95), 0.30, 0.40, seg=14)
        b.tube(MECH, (-s["len"] * 0.68, 0.0, 1.05), 0.20, s["len"] * 0.80, seg=12,
               ry=math.radians(90))
        b.ring(TRIM, (-s["len"] * 0.52, 0.0, 1.05), 0.27, 0.27, 0.16, seg=14)
    if s.get("crane"):
        b.crane(MECH, TRIM, s["len"] * 0.28, -s["beam"] * 0.60, 0.55, s["len"] * 0.42)
    if s.get("rotor"):
        b.rotor(MECH, TRIM, 0.0, 0.0, s["depth"] * 2.4, s["len"] * 0.72)
    if s.get("bag"):
        floor = b.envelope(SKIN, TRIM, (s["len"] * 0.02, 0.0, s["bag"][3]),
                           s["bag"][:3], ribs=s.get("ribs", 4), mi_fin=SKIN)
        for sx in (-0.30, 0.32):
            for sy in (0.55, -0.55):
                h = floor - 0.34
                b.box(MECH, (s["len"] * sx, s["beam"] * sy, 0.34 + h / 2.0),
                      (0.12, 0.12, h))
    return b


def kdm_platform(b, s):
    """Kingdom platform: tiered armoured hull, NO gas bag - buoyancy engines are internal.

    `stretch` matters: only the Observatory Sky-Dome is actually a disc. The strategic
    platforms, Skyward Citadel and Harvester's Reach are drawn as ELONGATED hulls in top
    view, so a circular saucer is the wrong read for them.
    """
    R = s["rad"]
    E = s.get("stretch", 1.0)
    b.sphere(DECK, (0.0, 0.0, -0.30), (R * E, R * 0.62, R * 0.16), u=42, v=21)
    b.ring(TRIM, (0.0, 0.0, -0.30), R * E, R * 0.62, 0.30, seg=38, axis="Z")
    b.tube(HULL, (0.0, 0.0, 0.62), R * 0.64, 0.90, seg=28, taper=0.92)
    b.ring(TRIM, (0.0, 0.0, 1.02), R * 0.60, R * 0.60, 0.14, seg=34, axis="Z")
    b.tube(DECK, (0.0, 0.0, 1.55), R * 0.46, 1.00, seg=24, taper=0.90)
    for i in range(20):
        a = i * (TAU / 20.0)
        b.box(TRIM, (math.cos(a) * R * 0.60, math.sin(a) * R * 0.60, 1.32),
              (0.13, 0.13, 0.46), rz=a)
    if s.get("dome"):
        b.tube(HULL, (0.0, 0.0, 2.35), R * 0.31, 0.70, seg=20, taper=0.92)
        b.sphere(TRIM, (0.0, 0.0, 2.70), (R * 0.285,) * 2 + (R * 0.236,), u=32, v=16)
        b.sphere(GLOW, (0.0, 0.0, 3.05), (R * 0.215,) * 2 + (R * 0.18,), u=24, v=12)
        b.tube(TRIM, (0.0, 0.0, 4.55), 0.42, 0.70, seg=14, taper=0.75)
    if s.get("fortress"):
        # FORTRESS WALLS & GARRISONS, MULTI-LEVEL WEAPON EMPLACEMENTS.
        for i in range(6):
            a = i * (TAU / 6.0)
            cx, cy = math.cos(a) * R * 0.52, math.sin(a) * R * 0.52
            b.box(HULL, (cx, cy, 1.95), (R * 0.22, R * 0.16, 0.90), rz=a)
            b.turret(HULL, TRIM, MECH, cx, cy, 2.55, R * 0.10,
                     mi_core=GLOW if s.get("plasma") else None)
    for i in range(s.get("sensors", 0)):
        mx = (i - (s["sensors"] - 1) / 2.0) * R * 0.44
        b.tube(MECH, (mx, 0.0, 3.15), 0.11, 2.30, seg=10)
        for zz, half in ((3.95, R * 0.15), (4.35, R * 0.11)):
            b.box(MECH, (mx, 0.0, zz), (0.09, half * 2, 0.07))
        b.sphere(TRIM, (mx, 0.0, 4.60), (0.30, 0.30, 0.26), u=14, v=7)
    for side in (1, -1):
        b.box(HULL, (0.0, side * R * 0.50, -0.05), (R * 0.42, R * 0.17, 0.60))
        b.paddle(HULL, TRIM, MECH, 0.0, side * R * 0.63, R * 0.25, boards=10)
    for sx in (-R * 0.92, R * 0.92):
        b.box(MECH, (sx, 0.0, 0.15), (R * 0.22, 0.55, 0.28))
        for side in (1, -1):
            b.box(TRIM, (sx * 1.16, side * 1.05, 0.15), (0.90, 0.36, 0.42))
    for i in range(s.get("cranes", 0)):
        ang = math.radians(38 + i * 104)
        b.crane(MECH, TRIM, math.cos(ang) * R * 0.48, math.sin(ang) * R * 0.34, 1.70,
                R * 0.52)
    for sx in s.get("stacks", []):
        b.stack(MECH, TRIM, sx * R, R * 0.20, 2.30, 0.30, 2.20)
    if s.get("cargo"):
        b.cargo(HULL, DECK, 0.0, R * 0.40, 0.30, 4, (R * 0.13, R * 0.10, 0.55))
    return b


def pir_ship(b, s):
    """Pirate raider: a metallic WHALE-LIKE envelope over a STEAM-LOCOMOTIVE gondola,
    with jet exhaust out the back of the train.

    The first pass gave the pirates a grey cigar over a plain boat hull, which read as a
    scruffier Kingdom ship rather than as a threat. The direction is specific: the bag is
    armoured and animal-shaped, what hangs beneath is machinery, and the thrust comes out
    the back of it. The menace is in the ram, the dorsal ridge, the claws and the glow -
    not in simply being dark.
    """
    L, B, D = s["len"], s["beam"], s["depth"]
    floor = b.whale(SKIN, DECK, (0.0, 0.0, D * 2.3), (L, B * 1.5, D * 1.35))

    if s.get("ram", True):
        b.tube(DECK, (-L * 1.22, 0.0, D * 2.3), B * 0.30, L * 0.34, seg=12,
               ry=math.radians(90), taper=0.05)
        b.ring(TRIM, (-L * 1.05, 0.0, D * 2.3), B * 0.34, B * 0.34, 0.16, seg=16, axis="X")

    loco_z = floor - D * 0.95
    b.locomotive(HULL, DECK, TRIM, GLOW, (L * 0.05, 0.0, loco_z), L * 1.05, B * 0.62)
    for sx in (-0.52, -0.10, 0.34):
        for sy in (0.55, -0.55):
            h = (floor - loco_z) - B * 0.55
            b.box(HULL, (L * sx, B * sy, loco_z + B * 0.62 + h / 2.0), (0.13, 0.13, h))

    for tx in s.get("turrets", []):
        b.turret(DECK, TRIM, HULL, L * tx, 0.0, loco_z + B * 0.95, B * 0.36, mi_core=GLOW)
    if s.get("claws"):
        b.claws(DECK, TRIM, -L * 0.30, B * 0.95, loco_z, B * 0.85)
    if s.get("crane"):
        b.crane(HULL, TRIM, L * 0.10, -B * 0.80, loco_z + B * 0.60, L * 0.45)
    if s.get("cargo"):
        b.cargo(DECK, SKIN, L * 0.10, B * 0.95, loco_z - B * 0.10, 3,
                (L * 0.10, B * 0.22, 0.55))

    b.tube(DECK, (L * 0.30, 0.0, D * 3.6), 0.09, L * 0.36, seg=8, ry=math.radians(18))
    b.box(SKIN, (L * 0.42, 0.0, D * 4.5), (L * 0.14, 0.05, 0.46))
    return b


def pir_platform(b, s):
    """Pirate hub: armoured drum, arms in a cross, plasma turrets, scrap plating."""
    R = s["rad"]
    b.tube(DECK, (0.0, 0.0, 0.0), R * 0.44, 1.70, seg=16)
    b.ring(TRIM, (0.0, 0.0, 0.0), R * 0.45, R * 0.45, 0.22, seg=20, axis="Z")
    b.tube(HULL, (0.0, 0.0, 1.15), R * 0.33, 1.10, seg=14)
    b.tube(DECK, (0.0, 0.0, 2.05), R * 0.22, 0.90, seg=12)
    b.tube(SKIN, (0.0, 0.0, -1.05), R * 0.30, 1.00, seg=14, taper=0.55)
    arms = s.get("arms", 4)
    for i in range(arms):
        a = i * (TAU / arms)
        cx, cy = math.cos(a), math.sin(a)
        for t in (0.51, 0.71):
            b.box(HULL, (cx * R * t, cy * R * t, 0.10), (R * 0.28, R * 0.13, 0.62), rz=a)
        b.box(DECK, (cx * R * 0.87, cy * R * 0.87, 0.10),
              (R * 0.16, R * 0.19, 1.00), rz=a)
        b.turret(DECK, TRIM, HULL, cx * R * 0.94, cy * R * 0.94, 0.55, R * 0.09,
                 mi_core=GLOW)
        for sgn in (1, -1):
            b.box(SKIN, (cx * R * 0.61 - cy * sgn * R * 0.15,
                         cy * R * 0.61 + cx * sgn * R * 0.15, -0.20),
                  (R * 0.20, 0.16, 0.90), rz=a)
    if s.get("claws"):
        b.claws(DECK, TRIM, 0.0, R * 0.50, -0.40, R * 0.30)
    for i in range(s.get("cranes", 0)):
        ang = math.radians(45 + i * 90)
        b.crane(HULL, TRIM, math.cos(ang) * R * 0.40, math.sin(ang) * R * 0.40, 1.60,
                R * 0.45)
    b.tube(HULL, (0.0, 0.0, 3.40), 0.16, 2.00, seg=10)
    b.box(DECK, (0.0, 0.0, 4.45), (R * 0.27, 0.14, 0.10))
    b.box(DECK, (0.0, 0.0, 4.75), (R * 0.19, 0.14, 0.10))
    b.box(SKIN, (R * 0.10, 0.0, 5.15), (R * 0.19, 0.05, 0.55))
    b.tube(GLOW, (0.0, 0.0, 2.60), R * 0.04, 0.20, seg=14)
    for i in range(8):
        a = i * (TAU / 8.0) + (TAU / 16.0)
        b.box(TRIM, (math.cos(a) * R * 0.50, math.sin(a) * R * 0.50, -0.75),
              (R * 0.17, 0.14, 0.14), rz=a)
    return b


def fighter(b, s):
    """Rotor-lifted FIGHTER - the "little copters" on both sheets.

    Kingdom draws a SCOUT SKIFF and a SKINK HELI-CRAFT with a "single wide rotor"; the
    pirates draw a SCOUT ORNITHOPTER and an ASSAULT SKIFF, "agile". They are the only
    craft in the setting with no lift envelope at all - the rotor IS the lift, which is
    why giving the scout skiff a gas bag was contradictory.

    Small, so it stays legible at fighter scale: a pod, a canopy, a tail boom, skids,
    forward guns, and the rotor. The faction difference is in the wings and the glow.
    """
    L, B, D = s["len"], s["beam"], s["depth"]
    pir = s.get("pirate", False)

    # Fuselage pod, tapering aft.
    b.tube(HULL, (0.0, 0.0, 0.0), B, L * 1.30, seg=16, ry=math.radians(90), taper=0.42)
    b.tube(DECK, (-L * 0.52, 0.0, 0.0), B * 1.06, L * 0.26, seg=16, ry=math.radians(90))
    # Canopy.
    b.sphere(GLOW if pir else TRIM, (-L * 0.44, 0.0, B * 0.42),
             (B * 0.62, B * 0.58, B * 0.48), u=18, v=9)
    # Tail boom and fin.
    b.tube(DECK, (L * 0.92, 0.0, B * 0.10), B * 0.20, L * 0.80, seg=10,
           ry=math.radians(90), taper=0.7)
    b.box(SKIN, (L * 1.26, 0.0, B * 0.72), (L * 0.20, 0.07, B * 0.95),
          ry=math.radians(pir and -22 or 12))
    for sgn in (1, -1):
        b.box(SKIN, (L * 1.20, sgn * B * 0.40, B * 0.16), (L * 0.16, B * 0.55, 0.07))
    # Skids.
    for sgn in (1, -1):
        b.box(MECH, (0.0, sgn * B * 0.80, -B * 1.05), (L * 0.95, 0.09, 0.09))
        for sx in (-0.45, 0.35):
            b.box(MECH, (L * sx, sgn * B * 0.80, -B * 0.55), (0.09, 0.09, B * 0.95))
    # Forward guns.
    for sgn in (1, -1):
        b.tube(MECH, (-L * 0.78, sgn * B * 0.52, -B * 0.20), B * 0.13, L * 0.60,
               seg=8, ry=math.radians(90))
    # Wings: stubby brass outriggers for the Kingdom, jagged blades for the pirates.
    for sgn in (1, -1):
        if pir:
            b.box(DECK, (L * 0.10, sgn * B * 1.35, -B * 0.10),
                  (L * 0.42, B * 1.00, 0.10), rx=sgn * math.radians(18))
            b.box(SKIN, (L * 0.34, sgn * B * 1.95, B * 0.10),
                  (L * 0.26, B * 0.55, 0.09), rx=sgn * math.radians(34))
        else:
            b.box(TRIM, (L * 0.05, sgn * B * 1.20, -B * 0.05),
                  (L * 0.34, B * 0.80, 0.10))
    # Exhaust: a plasma nozzle for pirates, a little banded stack for the Kingdom.
    if pir:
        b.tube(HULL, (L * 0.62, 0.0, 0.0), B * 0.34, L * 0.30, seg=12,
               ry=math.radians(90))
        b.tube(GLOW, (L * 0.80, 0.0, 0.0), B * 0.26, 0.22, seg=12, ry=math.radians(90))
    else:
        b.tube(MECH, (L * 0.18, 0.0, B * 0.95), B * 0.20, B * 0.90, seg=12, taper=1.2)
        b.tube(TRIM, (L * 0.18, 0.0, B * 1.30), B * 0.23, 0.10, seg=12)
    # THE ROTOR - the whole point of the class.
    b.rotor(MECH, TRIM, 0.0, 0.0, B * 1.85, L * 1.15, blades=s.get("blades", 4))
    return b


ARCH = {"kdm_ship": (kdm_ship, kdm_palette), "kdm_platform": (kdm_platform, kdm_palette),
        "pir_ship": (pir_ship, pir_palette), "pir_platform": (pir_platform, pir_palette),
        "kdm_fighter": (fighter, kdm_palette), "pir_fighter": (fighter, pir_palette)}

# =================================================================== the roster ===
# One row per class named on the sheets. Everything here is a parameter, not code.
SPECS = {
    # --- Kingdom ships ------------------------------------------------------------

    "VEN_KdmGunboat":      ("kdm_ship", dict(len=5.6, beam=1.26, depth=1.16,
                                             bag=(3.3, 1.34, 1.24, 4.15), ribs=4)),
    "VEN_KdmThunderbolt":  ("kdm_ship", dict(len=6.2, beam=1.30, depth=1.10, railgun=True,
                                             bag=(3.6, 1.36, 1.24, 4.35), ribs=4)),
    "VEN_KdmValiant":      ("kdm_ship", dict(len=6.6, beam=1.34, depth=1.18,
                                             bag=(4.6, 1.50, 1.40, 4.60), ribs=5,
                                             domes=[-0.42])),
    "VEN_KdmSentinel":     ("kdm_ship", dict(len=7.4, beam=1.52, depth=1.24,
                                             turrets=[-0.18, 0.30],
                                             bag=(5.1, 1.62, 1.50, 4.95), ribs=5)),
    "VEN_KdmMender":       ("kdm_ship", dict(len=6.8, beam=1.60, depth=1.20, crane=True,
                                             blunt=True, stacks=[-0.10, 0.16],
                                             bag=(4.7, 1.60, 1.48, 4.80), ribs=4)),
    "VEN_KdmGoldenVanguard": ("kdm_ship", dict(len=9.2, beam=1.90, depth=1.40,
                                               domes=[-0.40, -0.10, 0.20],
                                               turrets=[0.44], stacks=[-0.02, 0.22],
                                               boards=10,
                                               bag=(7.0, 2.05, 1.90, 6.10), ribs=6)),
    "VEN_KdmImperialBulwark": ("kdm_ship", dict(len=10.6, beam=2.30, depth=1.55,
                                                blunt=True, turrets=[-0.30, 0.06, 0.38],
                                                domes=[-0.52], stacks=[0.10, 0.30],
                                                boards=12,
                                                bag=(8.0, 2.35, 2.15, 6.90), ribs=6)),
    # --- Kingdom fighters (rotor-lifted, NO envelope) -----------------------------
    "VEN_KdmScoutSkiff":   ("kdm_fighter", dict(len=1.30, beam=0.42, depth=0.40)),
    "VEN_KdmSkinkHeli":    ("kdm_fighter", dict(len=1.55, beam=0.50, depth=0.46,
                                                blades=5)),
    # --- Kingdom platforms --------------------------------------------------------
    "VEN_KdmObservatory":  ("kdm_platform", dict(rad=7.2, dome=True, sensors=2)),
    "VEN_KdmMendersBerth": ("kdm_ship", dict(len=6.4, beam=1.55, depth=1.15, crane=True,
                                             blunt=True, stacks=[-0.08],
                                             bag=(4.4, 1.50, 1.38, 4.55), ribs=4)),

    "VEN_KdmHarvestersReach": ("kdm_platform", dict(rad=8.0, stretch=1.55, cranes=2, cargo=True,
                                                    stacks=[-0.40, -0.22], sensors=1)),
    "VEN_KdmSkywardCitadel": ("kdm_platform", dict(rad=9.0, stretch=1.35, fortress=True, dome=True,
                                                   sensors=2, stacks=[0.34])),
    "VEN_KdmSentinelPlatform": ("kdm_platform", dict(rad=6.8, stretch=1.25, sensors=1,
                                                     fortress=True)),
    # --- Pirate fighters ----------------------------------------------------------
    "VEN_PirOrnithopter":  ("pir_fighter", dict(len=1.35, beam=0.44, depth=0.40,
                                                pirate=True, blades=6)),
    "VEN_PirAssaultSkiff": ("pir_fighter", dict(len=1.20, beam=0.38, depth=0.36,
                                                pirate=True, blades=4)),
    # --- Pirate ships -------------------------------------------------------------
    "VEN_PirBlackSails":   ("pir_ship", dict(len=5.4, beam=1.00, depth=1.05,
                                             bag=(3.5, 1.05, 0.92, 3.55), ribs=4)),
    "VEN_PirScavenger":    ("pir_ship", dict(len=5.8, beam=1.05, depth=1.00, claws=True,
                                             cargo=True,
                                             bag=(3.7, 1.08, 0.95, 3.65), ribs=4)),
    "VEN_PirNighthawk":    ("pir_ship", dict(len=7.0, beam=1.10, depth=1.05,
                                             turrets=[0.10],
                                             bag=(4.6, 1.15, 1.00, 4.05), ribs=5)),
    "VEN_PirBloodHawk":    ("pir_ship", dict(len=7.6, beam=1.18, depth=1.14, claws=True,
                                             turrets=[-0.10],
                                             bag=(4.9, 1.24, 1.08, 4.20), ribs=5)),
    "VEN_PirScrapKing":    ("pir_ship", dict(len=9.0, beam=1.60, depth=1.20, blunt=True,
                                             crane=True, cargo=True, claws=True,
                                             bag=(5.6, 1.55, 1.30, 4.70), ribs=5)),
    "VEN_PirBlackTide":    ("pir_ship", dict(len=11.0, beam=1.95, depth=1.45, blunt=True,
                                             turrets=[-0.30, 0.04, 0.34],
                                             bag=(7.4, 1.95, 1.65, 5.80), ribs=6)),
    "VEN_PirGossamerGhost": ("pir_ship", dict(len=6.4, beam=1.02, depth=0.98,
                                              ram=False, turrets=[0.16])),
    "VEN_PirMaelstrom":    ("pir_ship", dict(len=9.8, beam=1.75, depth=1.34, blunt=True,
                                             claws=True, turrets=[-0.24, 0.10, 0.40])),
    # --- Pirate platforms ---------------------------------------------------------
    "VEN_PirArmadaHub":    ("pir_platform", dict(rad=7.4, arms=4)),
    "VEN_PirRepairRig":    ("pir_platform", dict(rad=6.6, arms=3, cranes=2)),
    "VEN_PirDreadRaider":  ("pir_platform", dict(rad=8.6, arms=6, claws=True, cranes=1)),
    "VEN_PirCitadel":      ("pir_platform", dict(rad=9.4, arms=5, cranes=1)),
}


# ============================================================== bake and export ===
def finish(b, out_path, target):
    scene = bpy.context.scene
    bm = b.bm
    # Bevel HARD edges only - rounding every edge quilts a smooth-shaded bag once the mesh
    # is dense enough that the decimator no longer erases the creases.
    hard = [e for e in bm.edges
            if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(22)]
    bmesh.ops.bevel(bm, geom=hard, offset=0.010, segments=3, profile=0.62,
                    affect="EDGES", clamp_overlap=True)
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

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.duplicate()
    high = bpy.context.view_layer.objects.active
    bpy.context.view_layer.objects.active = high
    sub = high.modifiers.new("subsurf", "SUBSURF")
    sub.levels = sub.render_levels = 2
    bpy.ops.object.modifier_apply(modifier=sub.name)

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    # Triangulate FIRST so counts are in the unit the budget is written in.
    tri = obj.modifiers.new("triangulate", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=tri.name)
    before = len(obj.data.polygons)
    if before > target:
        dec = obj.modifiers.new("decimate", "DECIMATE")
        dec.ratio = float(target) / before
        bpy.ops.object.modifier_apply(modifier=dec.name)

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
    scene.render.bake.margin = 8
    scene.render.bake.use_selected_to_active = False

    def img(name, color, non_color=False):
        i = bpy.data.images.new(name, TEX, TEX, alpha=False)
        i.generated_color = color
        if non_color:
            i.colorspace_settings.name = "Non-Color"
        return i

    def bake(image, kind, **kw):
        nodes = []
        for slot in obj.material_slots:
            m = slot.material
            n = m.node_tree.nodes.new("ShaderNodeTexImage")
            n.image = image
            m.node_tree.nodes.active = n
            n.select = True
            nodes.append((m, n))
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.bake(type=kind, **kw)
        for m, n in nodes:
            m.node_tree.nodes.remove(n)

    root = os.path.splitext(out_path)[0]
    d = img(b.name + "_d", (0.5, 0.5, 0.5, 1.0))
    bake(d, "DIFFUSE", pass_filter={"COLOR"})
    d.filepath_raw = root + "_diffuse.png"
    d.file_format = "PNG"
    d.save()

    e = img(b.name + "_e", (0.0, 0.0, 0.0, 1.0))
    bake(e, "EMIT")
    e.filepath_raw = root + "_emissive.png"
    e.file_format = "PNG"
    e.save()

    n_img = img(b.name + "_n", (0.5, 0.5, 1.0, 1.0), non_color=True)
    try:
        scene.render.bake.use_selected_to_active = True
        scene.render.bake.cage_extrusion = 0.35
        bpy.ops.object.select_all(action="DESELECT")
        high.select_set(True)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        for slot in obj.material_slots:
            m = slot.material
            nn = m.node_tree.nodes.new("ShaderNodeTexImage")
            nn.image = n_img
            m.node_tree.nodes.active = nn
            nn.select = True
        bpy.ops.object.bake(type="NORMAL")
    except Exception as ex:                           # noqa: BLE001
        _log("%s: normal bake failed (%s)" % (b.name, ex))
    finally:
        scene.render.bake.use_selected_to_active = False
    n_img.filepath_raw = root + "_normal.png"
    n_img.file_format = "PNG"
    n_img.save()
    # Read the count BEFORE the delete - touching high.data afterwards raises
    # "ReferenceError: StructRNA of type Object has been removed".
    high_tris = len(high.data.polygons)
    bpy.data.objects.remove(high, do_unlink=True)

    import numpy as np                                # noqa: E402
    px = np.empty(len(d.pixels), dtype=np.float32)
    d.pixels.foreach_get(px)
    lum = px.reshape(-1, 4)[:, :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    lum = np.clip((lum - 0.5) * 1.3 + 0.5, 0.0, 1.0) * 0.45
    sp = img(b.name + "_s", (0.0, 0.0, 0.0, 1.0))
    sp.pixels.foreach_set(np.stack([lum, lum, lum, np.ones_like(lum)], axis=1).ravel())
    sp.filepath_raw = root + "_specular.png"
    sp.file_format = "PNG"
    sp.save()

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.obj_export(filepath=out_path, export_selected_objects=True,
                          export_materials=False, export_triangulated_mesh=True,
                          export_normals=True, export_uv=True)
    _log("%-26s %6d tris  (high %d)" % (b.name, len(obj.data.polygons), high_tris))


os.makedirs(OUTDIR, exist_ok=True)
keys = [k for k in SPECS
        if WHICH == "all" or k == WHICH
        or (WHICH in ("kdm", "pir") and k.startswith("VEN_" + WHICH.capitalize()))]
for key in keys:
    arch_name, spec = SPECS[key]
    fn, palette = ARCH[arch_name]
    bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
    b = Build(key, palette())
    fn(b, spec)
    finish(b, os.path.join(OUTDIR, key + ".obj"), TARGET)
_log("built %d/%d" % (len(keys), len(SPECS)))
