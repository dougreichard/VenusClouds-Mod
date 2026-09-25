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
import contextlib
import functools
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


def _mat(name, rgb, rough=0.85, metallic=0.0, emit=None, strength=1.0):
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


def _join_detail(high, b, scene):
    """Join the greeble layer into the high-poly. It never touches the low-poly."""
    if not b.bm_detail.faces:
        b.bm_detail.free()
        return 0
    dmesh = bpy.data.meshes.new(b.name + "_detail")
    b.bm_detail.to_mesh(dmesh)
    b.bm_detail.free()
    dobj = bpy.data.objects.new(b.name + "_detail", dmesh)
    # Same material list in the same order, so joining preserves material_index.
    for m in b.materials:
        dobj.data.materials.append(m)
    scene.collection.objects.link(dobj)
    n = len(dmesh.polygons)
    # One level of subsurf so rivet heads and pipe runs bake ROUND. They used to ride the
    # hull's own subsurf-2; joining after it would otherwise leave them visibly faceted in
    # the normal map, which is the one place this detail now exists.
    bpy.ops.object.select_all(action="DESELECT")
    dobj.select_set(True)
    bpy.context.view_layer.objects.active = dobj
    dsub = dobj.modifiers.new("dsubsurf", "SUBSURF")
    dsub.levels = dsub.render_levels = 1
    bpy.ops.object.modifier_apply(modifier=dsub.name)
    bpy.ops.object.select_all(action="DESELECT")
    dobj.select_set(True)
    high.select_set(True)
    bpy.context.view_layer.objects.active = high
    bpy.ops.object.join()
    _log("%-26s %6d greeble faces (high-poly only)" % (b.name, n))
    return n


def _window_mask(nt, plans):
    """Build a 0/1 mask node for every window plan, OR-ed together."""
    def _sock(v):
        """A NODE yields its first output; a SOCKET is already one; a number is neither."""
        if hasattr(v, "outputs"):
            return v.outputs[0]
        if hasattr(v, "is_linked"):
            return v
        return None

    def m(op, a, b=None, c=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for idx, val in ((0, a), (1, b), (2, c)):
            if val is None:
                continue
            sk = _sock(val)
            if sk is not None:
                nt.links.new(n.inputs[idx], sk)
            else:
                n.inputs[idx].default_value = val
        return n

    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(sep.inputs[0], coord.outputs["Object"])
    x, y, z = sep.outputs[0], sep.outputs[1], sep.outputs[2]

    def band(val, center, half):
        return m("LESS_THAN", m("ABSOLUTE", m("SUBTRACT", val, center)), half)

    total = None
    for p in plans:
        if p["kind"] == "row":
            # A pulse train along x, inside a height band, on the flanks only.
            phase = m("FRACT", m("DIVIDE", m("SUBTRACT", x, p["x0"]), p["pitch"]))
            mask = m("MULTIPLY", m("LESS_THAN", phase, p["duty"]),
                     band(z, p["z"], p["zh"]))
            mask = m("MULTIPLY", mask, m("GREATER_THAN", x, p["x0"]))
            mask = m("MULTIPLY", mask, m("LESS_THAN", x, p["x1"]))
            mask = m("MULTIPLY", mask,
                     m("GREATER_THAN", m("ABSOLUTE", y), p["ymin"]))
        else:
            # Angular pulse train round a drum, in a height band at a given radius.
            xe = m("DIVIDE", x, max(1e-6, p["ex"]))
            ang = nt.nodes.new("ShaderNodeMath")
            ang.operation = "ARCTAN2"
            nt.links.new(ang.inputs[0], y)
            nt.links.new(ang.inputs[1], xe.outputs[0])
            phase = m("FRACT", m("DIVIDE", ang, TAU / p["count"]))
            rad = m("SQRT", m("ADD", m("MULTIPLY", xe, xe), m("MULTIPLY", y, y)))
            mask = m("MULTIPLY", m("LESS_THAN", phase, p["duty"]),
                     band(z, p["z"], p["zh"]))
            mask = m("MULTIPLY", mask, band(rad, p["r"], p["r"] * 0.06))
        total = mask if total is None else m("MAXIMUM", total, mask)
    return total


def _shade_windows(materials, plans, emit, strength=1.0):
    """Mix lit windows into every material as an emission mask.

    Applied to all slots because a window band crosses hull, deck and trim; the mask
    itself decides where it lands, so this cannot smear onto the wrong surface.
    """
    if not plans:
        return
    for mat in materials:
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        if bsdf is None:
            continue
        mask = _window_mask(nt, plans)
        prev = bsdf.inputs["Emission Color"].default_value[:3]
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        nt.links.new(mix.inputs["Factor"], mask.outputs[0])
        mix.inputs[6].default_value = (prev[0], prev[1], prev[2], 1.0)
        mix.inputs[7].default_value = (emit[0], emit[1], emit[2], 1.0)
        nt.links.new(bsdf.inputs["Emission Color"], mix.outputs[2])
        # Strength must also be masked, or the whole hull glows at window brightness.
        est = nt.nodes.new("ShaderNodeMath")
        est.operation = "MAXIMUM"
        est.inputs[0].default_value = bsdf.inputs["Emission Strength"].default_value
        nt.links.new(est.inputs[1], mask.outputs[0])
        nt.links.new(bsdf.inputs["Emission Strength"], est.outputs[0])


def kdm_palette():
    # Brass reads as brass only if the BASE COLOUR is warm and light - the bake keeps
    # colour and discards metalness, so a dark metallic swatch comes out grey.
    return [_mat("timber", (0.100, 0.070, 0.048)),
            _mat("deck",   (0.292, 0.206, 0.122)),
            _mat("canvas", (0.660, 0.600, 0.462)),
            _mat("brass",  (0.740, 0.540, 0.180), 0.32, 0.90),
            _mat("iron",   (0.150, 0.148, 0.156), 0.55, 0.80),
            _mat("lamp",   (1.000, 0.760, 0.420), 0.30, 0.0,
                 (1.00, 0.72, 0.34), 1.0)]


def pir_palette():
    return [_mat("gunmetal", (0.070, 0.072, 0.080), 0.50, 0.85),
            _mat("armor",    (0.130, 0.128, 0.132), 0.62, 0.60),
            _mat("canvasp",  (0.088, 0.086, 0.092), 0.45, 0.70),
            _mat("brasspir", (0.430, 0.300, 0.110), 0.42, 0.85),
            _mat("blood",    (0.300, 0.045, 0.040), 0.60, 0.20),
            _mat("plasma",   (0.900, 0.180, 0.090), 0.30, 0.0, (1.00, 0.22, 0.08))]


# Slot names are shared between palettes so the archetypes can index them by meaning.
HULL, DECK, SKIN, TRIM, MECH, GLOW = range(6)

# How far lit texels are pulled toward white. 0 = the authored hue at full chroma,
# 1 = pure white.
#
# Held at 0. The engine's emissive intensity is clamped 0-1.0, so it can only ATTENUATE -
# there is no headroom above 1.0 to clip toward white, and no way to recover a hue that
# was baked out. The map therefore has to carry the final look. A ladder at 0/0.15/0.30/
# 0.50 confirmed it by eye: the pirate glow is firebox, draught slots and plasma, and
# fire that is not orange stops reading as fire.
EMISSIVE_DESAT = 0.0

PROFILE = [
    (1.00, 0.00), (0.99, -0.28), (0.86, -0.60), (0.56, -0.87),
    (0.00, -1.00),
    (-0.56, -0.87), (-0.86, -0.60), (-0.99, -0.28), (-1.00, 0.00),
]


def _greeble(fn):
    """Mark a helper as surface detail: its geometry goes to the high-poly layer only."""
    @functools.wraps(fn)
    def wrapper(self, *a, **kw):
        with self.detail():
            return fn(self, *a, **kw)
    return wrapper


class Build:
    def __init__(self, name, materials):
        self.name = name
        self.materials = materials
        self.bm = bmesh.new()
        # Windows are FLAT features - a lit rectangle on the hull, not a box standing off
        # it. As geometry they spend low-poly triangles AND can only ever be as accurate
        # as a guess at where the surface is, which is why they floated. Instead we record
        # a PLAN here and paint it onto the high-poly's own faces before the bake, so the
        # lights land exactly on the skin and cost the shipped mesh nothing at all.
        self.window_plans = []
        # GREEBLE LAYER. Rivets, pipes, gauges and cogs are surface detail, and the entire
        # point of a high-to-low bake is that such detail lives in the NORMAL MAP rather
        # than in shipped triangles. Kept in the single bmesh they were doing both: eating
        # the 14k budget that should be paying for silhouette, then getting decimated into
        # specks. This layer is joined into the high-poly only, so it bakes and costs the
        # shipped mesh nothing.
        self.bm_detail = bmesh.new()

    @contextlib.contextmanager
    def detail(self):
        """Route geometry built inside this block to the high-poly-only layer."""
        main = self.bm
        self.bm = self.bm_detail
        try:
            yield
        finally:
            self.bm = main

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
        # Ribs follow the skin exactly and live in the bake only - no cylinder to cut
        # in, and no triangles spent on a detail the normal map carries.
        for i in range(ribs):
            t = -0.66 + i * (1.32 / max(1, ribs - 1))
            self.env_rib(mi_rib, c, r, t)
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

    def whale(self, mi_skin, mi_plate, c, r, seg=13, mi_glow=None):
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
        # Widest-section sizing again: bands take the larger of their own station and the
        # neighbour toward the chest, so the band sits proud rather than sinking in.
        with self.detail():
            for i, (t, ws, hs, _dz) in enumerate(prof[2:7], start=2):
                wn = max(ws, prof[i - 1][1] if t > 0 else prof[i + 1][1])
                hn = max(hs, prof[i - 1][2] if t > 0 else prof[i + 1][2])
                self.ring(mi_plate, (c.x + t * r.x, c.y, c.z), r.y * wn * 1.045,
                          r.z * hn * 1.045, 0.12, seg=seg * 2, axis="X")
        for k in range(5):
            t = -0.55 + k * 0.26
            h = r.z * (0.30 - abs(t) * 0.12)
            self.box(mi_plate, (c.x + t * r.x, c.y, c.z + r.z * 0.92 + h * 0.4),
                     (r.x * 0.10, 0.10, h), ry=math.radians(-22))
        # Running lights down the ridge and along the flanks - a predator with its
        # lamps lit, which is more intimidating than a dark shape.
        if mi_glow is not None:
            for k in range(5):
                t = -0.55 + k * 0.26
                h = r.z * (0.30 - abs(t) * 0.12)
                self.sphere(mi_glow, (c.x + t * r.x, c.y, c.z + r.z * 0.92 + h * 0.95),
                            (0.070, 0.070, 0.070), u=8, v=5)
            for sgn in (1, -1):
                for t in (-0.30, 0.10, 0.46):
                    self.sphere(mi_glow, (c.x + t * r.x, c.y + sgn * r.y * 0.84,
                                          c.z - r.z * 0.18),
                                (0.060, 0.060, 0.060), u=8, v=5)
        # Rivets along the body's own profile, so they lie on the plating.
        with self.detail():
            for sgn in (1, -1):
                for t, ws, hs, dz in prof[1:8]:
                    for k in (-0.35, 0.0, 0.35):
                        self.sphere(mi_plate,
                                    (c.x + (t + k * 0.06) * r.x,
                                     c.y + sgn * r.y * ws * 1.005,
                                     c.z + dz * r.z), (0.05, 0.05, 0.05), u=6, v=4)
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
        # Firebox glare under the cab and glowing draught slots along the boiler - the
        # engine should look like it is being WORKED, not merely parked.
        self.box(mi_glow, (c.x + length * 0.30, c.y, c.z - radius * 0.62),
                 (length * 0.14, radius * 1.16, radius * 0.20))
        for k in (-0.30, -0.06, 0.18):
            for side in (1, -1):
                self.box(mi_glow, (c.x + k * length, c.y + side * radius * 1.01,
                                   c.z - radius * 0.30),
                         (length * 0.05, 0.04, radius * 0.28))
        # External plumbing, gauges and a safety valve - the boiler is machinery.
        for side in (1, -1):
            self.pipe(mi_brass, [(c.x - length * 0.46, c.y + side * radius * 1.02, c.z),
                                 (c.x - length * 0.10, c.y + side * radius * 1.16,
                                  c.z + radius * 0.55),
                                 (c.x + length * 0.30, c.y + side * radius * 1.05,
                                  c.z + radius * 0.20)], r=0.055)
            self.gauge(mi_brass, mi_glow, (c.x - length * 0.24,
                                           c.y + side * radius * 1.10, c.z + radius * 0.7),
                       r=0.13)
            self.cog(mi_brass, (c.x + length * 0.20, c.y + side * radius * 1.10,
                                c.z - radius * 0.40), r=radius * 0.34, teeth=10,
                     thick=0.10, axis="Y")
        self.valve(mi_brass, (c.x + length * 0.06, c.y, c.z + radius * 1.18), r=0.20)
        self.tube(mi_brass, (c.x + length * 0.20, c.y, c.z + radius * 1.32),
                  radius * 0.11, radius * 0.50, seg=8)
        for side in (1, -1):
            ex = c.x + length * 0.60
            self.tube(mi_iron, (ex, c.y + side * radius * 0.60, c.z), radius * 0.40,
                      length * 0.26, seg=14, ry=math.radians(90))
            self.ring(mi_brass, (ex + length * 0.12, c.y + side * radius * 0.60, c.z),
                      radius * 0.43, radius * 0.43, 0.14, seg=16, axis="X")
            self.tube(mi_glow, (ex + length * 0.17, c.y + side * radius * 0.60, c.z),
                      radius * 0.30, 0.26, seg=14, ry=math.radians(90))

    # ------------------------------------------------------- steampunk greeble --
    @_greeble
    def rivets(self, mi, a, b_, r=0.045, n=14):
        """A riveted seam from a to b. The single most legible steampunk cue: it says
        "plate and hammer" at any distance, and it costs nothing but high-poly."""
        a, b_ = Vector(a), Vector(b_)
        for i in range(n):
            t = (i + 0.5) / n
            self.sphere(mi, a.lerp(b_, t), (r, r, r), u=6, v=4)

    @_greeble
    def env_rib(self, mi, c, r, t, hw=0.030, lift=1.018, seg=32):
        """A rib that HUGS the envelope, because it is made OF the envelope.

        A cylinder can only ever approximate a curving body - size it to its centre and
        the edges cut in, size it to its widest span and it stands off. Instead sample the
        ellipsoid at three stations and push the middle one out: the rib now follows the
        curvature exactly, at any station, on any proportion of bag. Being baked-only it
        can hug this tightly without worrying about surviving decimation.
        """
        rings = []
        for tt, lf in ((t - hw, 1.004), (t, lift), (t + hw, 1.004)):
            sc = math.sqrt(max(0.0, 1.0 - min(1.0, tt * tt)))
            rings.append([self.bm.verts.new(
                (c.x + tt * r.x,
                 c.y + math.cos(a * TAU / seg) * r.y * sc * lf,
                 c.z + math.sin(a * TAU / seg) * r.z * sc * lf)) for a in range(seg)])
        faces = []
        for a_, b_ in zip(rings, rings[1:]):
            for i in range(seg):
                j = (i + 1) % seg
                faces.append(self.bm.faces.new((a_[i], a_[j], b_[j], b_[i])))
        for f in faces:
            f.material_index = mi
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)

    @_greeble
    def hull_seam(self, mi, stations, prof_index, side=1, r=0.042, step=1,
                  lift=1.005):
        """Rivets along one profile line of a lofted hull.

        `prof_index` picks a line of PROFILE (0 = sheer, 4 = keel), so every rivet sits on
        a point the hull surface actually passes through. `lift` nudges them a hair proud
        of the skin - enough to read as a raised head, far inside the bake cage.
        """
        yf, zf = PROFILE[prof_index]
        pts = []
        for x, hw, dp in stations:
            pts.append((x, side * yf * hw * lift, zf * dp * lift))
        # Subdivide between stations so the spacing is even along a curving sheer.
        for a, b_ in zip(pts, pts[1:]):
            for i in range(step * 3):
                t = (i + 0.5) / (step * 3)
                self.sphere(mi, (a[0] + (b_[0] - a[0]) * t,
                                 a[1] + (b_[1] - a[1]) * t,
                                 a[2] + (b_[2] - a[2]) * t), (r, r, r), u=6, v=4)

    def ports(self, mi, x0, x1, y, z, n=8, r=0.05):
        """A row of lit portholes along a hull side."""
        for i in range(n):
            t = (i + 0.5) / n
            self.tube(mi, (x0 + (x1 - x0) * t, y, z), r, 0.06, seg=10,
                      rx=math.radians(90))

    def lantern(self, mi_case, mi_lamp, c, r=0.13, mount_z=None):
        """A lantern: bracket, lit core, cap. The stern light every gondola has.

        `mount_z` is the surface it is bolted to - the post runs the whole way down to it
        and gets a foot, so the lamp reads as ATTACHED rather than hovering nearby.
        """
        top = c[2] - r * 0.9
        bot = top - r * 1.1 if mount_z is None else mount_z
        h = max(0.05, top - bot)
        self.tube(mi_case, (c[0], c[1], bot + h * 0.5), r * 0.20, h, seg=8)
        self.box(mi_case, (c[0], c[1], bot + 0.03), (r * 0.55, r * 0.55, 0.035))
        self.sphere(mi_lamp, c, (r * 0.72, r * 0.72, r * 0.82), u=10, v=6)
        self.ring(mi_case, c, r * 1.10, r * 1.10, 0.05, seg=10, axis="Z")
        self.sphere(mi_case, (c[0], c[1], c[2] + r * 1.15), (r * 0.5,) * 3, u=8, v=5)

    def window_band(self, mi, c, half, h, n=6, rz=0.0):
        """A run of lit windows across a deckhouse wall."""
        for i in range(n):
            t = ((i + 0.5) / n - 0.5) * 2.0
            self.box(mi, (c[0] + t * half * math.cos(rz),
                          c[1] + t * half * math.sin(rz), c[2]),
                     (half * 0.34 / n, 0.04, h), rz=rz)

    def window_row(self, x0, x1, z, zh=0.10, pitch=0.42, duty=0.42, ymin=0.0):
        """A row of lit ports along both flanks. No geometry - painted at bake time."""
        self.window_plans.append(
            {"kind": "row", "x0": x0, "x1": x1, "z": z, "zh": zh,
             "pitch": pitch, "duty": duty, "ymin": ymin})

    def window_ring(self, r, z, zh=0.12, count=26, duty=0.40, ex=1.0):
        """A ring of lit gallery windows round a drum. No geometry."""
        self.window_plans.append(
            {"kind": "ring", "r": r, "z": z, "zh": zh, "count": count,
             "duty": duty, "ex": ex})

    @_greeble
    def pipe(self, mi, pts, r=0.06, seg=8):
        """An external pipe run with elbows - machinery worn on the outside."""
        pts = [Vector(p) for p in pts]
        for p, q in zip(pts, pts[1:]):
            d = q - p
            L = d.length
            if L < 1e-5:
                continue
            m = (Matrix.Translation(p.lerp(q, 0.5))
                 @ d.to_track_quat("Z", "Y").to_matrix().to_4x4())
            self.prim(bmesh.ops.create_cone, mi, matrix=m, cap_ends=True,
                      cap_tris=False, segments=seg, radius1=r, radius2=r, depth=L)
            self.sphere(mi, q, (r * 1.05,) * 3, u=8, v=5)   # elbow, not a ball

    @_greeble
    def gauge(self, mi_case, mi_face, c, r=0.11, rx=0.0, ry=0.0):
        """A pressure gauge: brass case, pale dial. Reads as instrumentation."""
        self.tube(mi_case, c, r, 0.10, seg=12, rx=rx, ry=ry)
        self.tube(mi_face, (c[0], c[1], c[2] + 0.055), r * 0.78, 0.03, seg=12,
                  rx=rx, ry=ry)

    @_greeble
    def valve(self, mi, c, r=0.14, spokes=5, rx=0.0):
        """A spoked valve handwheel."""
        self.ring(mi, c, r, r, 0.06, seg=14, axis="Z" if not rx else "Y")
        for i in range(spokes):
            a = i / float(spokes) * TAU
            self.box(mi, (c[0] + math.cos(a) * r * 0.5, c[1] + math.sin(a) * r * 0.5,
                          c[2]), (r * 0.9, 0.045, 0.045), rz=a)

    @_greeble
    def cog(self, mi, c, r=0.22, teeth=10, thick=0.08, axis="Y"):
        """An exposed gear. Gear trains are the whole visual thesis of the setting."""
        self.ring(mi, c, r * 0.82, r * 0.82, thick, seg=16, axis=axis)
        for i in range(teeth):
            a = i / float(teeth) * TAU
            if axis == "Y":
                self.box(mi, (c[0] + math.cos(a) * r, c[1], c[2] + math.sin(a) * r),
                         (r * 0.30, thick, r * 0.22), ry=-a)
            else:
                self.box(mi, (c[0] + math.cos(a) * r, c[1] + math.sin(a) * r, c[2]),
                         (r * 0.30, r * 0.22, thick), rz=a)

    def boiler_dress(self, mi_brass, mi_iron, mi_face, c, length, radius):
        """Gauges, valves, a safety stack and a pipe run over a boiler or hull side."""
        c = Vector(c)
        self.gauge(mi_brass, mi_face, (c.x - length * 0.18, c.y, c.z + radius * 1.02))
        self.gauge(mi_brass, mi_face, (c.x + length * 0.02, c.y, c.z + radius * 1.02),
                   r=0.12)
        self.valve(mi_brass, (c.x + length * 0.22, c.y, c.z + radius * 1.05), r=0.18)
        self.tube(mi_brass, (c.x + length * 0.34, c.y, c.z + radius * 1.20),
                  radius * 0.10, radius * 0.55, seg=8)
        self.pipe(mi_brass, [(c.x - length * 0.34, c.y + radius * 0.85, c.z),
                             (c.x - length * 0.02, c.y + radius * 1.02, c.z + radius * 0.5),
                             (c.x + length * 0.30, c.y + radius * 0.95, c.z)], r=0.055)

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
        # Exposed gear train driving the wheel - cogs, not a hidden disc.
        self.cog(mi_brass, (x - r * 0.86, y * 0.84, 0.10), r=r * 0.34, teeth=11,
                 thick=0.12, axis="Y")
        self.cog(mi_iron, (x - r * 1.24, y * 0.84, -r * 0.22), r=r * 0.20, teeth=8,
                 thick=0.10, axis="Y")
        self.valve(mi_brass, (x - r * 0.60, y * 0.70, r * 0.55), r=r * 0.20)

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
    # PADDLE WHEELS ARE NOT UNIVERSAL. The art gives them to the steamers; dinghies and
    # launches have none, and some hulls drive on a stern screw instead. Making them a
    # fixture is what made eight Kingdom hulls read as one ship at different scales.
    if s.get("paddle", True):
        for side in (1, -1):
            px = s["len"] * s.get("paddle_x", 0.22)
            b.box(HULL, (px, side * s["beam"] * 0.95, -0.18),
                  (s["len"] * 0.26, s["beam"] * 0.70, 0.42))
            b.paddle(HULL, TRIM, MECH, px, side * s["beam"] * 1.32, s["beam"] * 0.95,
                     boards=s.get("boards", 8))
    if s.get("screw"):
        # Stern screw: a hub and blades under the counter, plus its shaft housing.
        sx = s["len"] * 0.95
        b.tube(MECH, (sx - s["len"] * 0.10, 0.0, -s["depth"] * 0.55), s["beam"] * 0.16,
               s["len"] * 0.22, seg=12, ry=math.radians(90))
        b.tube(TRIM, (sx, 0.0, -s["depth"] * 0.55), s["beam"] * 0.18, 0.16, seg=12,
               ry=math.radians(90))
        for k in range(4):
            a = k / 4.0 * TAU
            b.box(TRIM, (sx + 0.05, math.cos(a) * s["beam"] * 0.42,
                         -s["depth"] * 0.55 + math.sin(a) * s["beam"] * 0.42),
                  (0.07, s["beam"] * 0.60, 0.16), ry=math.radians(24), rx=-a)
    # GUN DECKS - what makes a man-o-war read as a man-o-war rather than a big launch.
    for d in range(s.get("decks", 0)):
        dz = 0.42 + d * 0.52
        b.box(HULL, (0.0, 0.0, dz + 0.26),
              (s["len"] * 1.62, s["beam"] * (1.86 - d * 0.16), 0.50))
        b.box(TRIM, (0.0, 0.0, dz + 0.52),
              (s["len"] * 1.64, s["beam"] * (1.88 - d * 0.16), 0.07))
        for side in (1, -1):
            for i in range(7):
                gx = (i - 3) * s["len"] * 0.22
                b.box(MECH, (gx, side * s["beam"] * (0.93 - d * 0.08), dz + 0.26),
                      (s["len"] * 0.08, 0.10, 0.20))
    for i, sx in enumerate(s.get("stacks", [-0.06])):
        b.stack(MECH, TRIM, s["len"] * sx, 0.0, s["depth"] * 1.10, 0.30, 2.20)
    # Riveted plate seams that FOLLOW the lofted skin - sheer line and a lower strake.
    for side in (1, -1):
        b.hull_seam(TRIM, st, 0, side=side, r=0.042)     # sheer
        b.hull_seam(TRIM, st, 2, side=side, r=0.038)     # turn of the bilge
    b.boiler_dress(TRIM, MECH, SKIN, (s["len"] * 0.10, 0.0, s["depth"] * 0.30),
                   s["len"] * 0.70, s["beam"] * 0.55)

    # Lit portholes down both flanks, painted onto the skin at bake time.
    b.window_row(-s["len"] * 0.60, s["len"] * 0.62, -s["depth"] * 0.28,
                 zh=s["depth"] * 0.085, pitch=s["len"] * 0.115,
                 duty=0.40, ymin=s["beam"] * 0.45)
    # Lanterns: bow, stern and quarters. The stern light reads at any distance.
    b.lantern(TRIM, GLOW, (s["len"] * 0.88, 0.0, 0.62), mount_z=0.14)
    b.lantern(TRIM, GLOW, (-s["len"] * 0.84, 0.0, 0.50), r=0.11, mount_z=0.14)
    for side in (1, -1):
        b.lantern(TRIM, GLOW, (s["len"] * 0.08, side * s["beam"] * 0.94, 0.58),
                  r=0.10, mount_z=0.14)

    # Superstructure: a deckhouse and, on the bigger classes, brass domes.
    b.box(HULL, (-s["len"] * 0.42, 0.0, 0.52), (s["len"] * 0.22, s["beam"] * 1.05, 1.00))
    b.box(TRIM, (-s["len"] * 0.42, 0.0, 0.88), (s["len"] * 0.23, s["beam"] * 1.10, 0.10))
    # The deckhouse windows are lit - that is where the crew is.
    b.window_row(-s["len"] * 0.60, -s["len"] * 0.24, 0.60, zh=0.16,
                 pitch=s["len"] * 0.075, duty=0.44, ymin=s["beam"] * 0.55)
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
    # Rivet band on the deck drum. The drum is tube(R*0.64) tapering to 0.92, so the
    # wall at this height sits at about R*0.62 - place them there, not on a guess.
    with b.detail():
        for i in range(46):
            a = i * (TAU / 46.0)
            b.sphere(TRIM, (math.cos(a) * R * 0.622 * E, math.sin(a) * R * 0.622, 0.72),
                     (0.05, 0.05, 0.05), u=6, v=4)
    # Lit gallery windows round the deck drum, painted onto the drum wall itself.
    b.window_ring(R * 0.626, 0.64, zh=0.13, count=28, duty=0.20, ex=E)
    for i in range(6):
        a = i * (TAU / 6.0) + 0.4
        b.lantern(TRIM, GLOW, (math.cos(a) * R * 0.58 * E, math.sin(a) * R * 0.58, 1.56),
                  r=0.14, mount_z=0.86)
    b.gauge(TRIM, GLOW, (R * 0.40 * E, R * 0.30, 1.16))
    b.valve(TRIM, (R * 0.30 * E, -R * 0.34, 1.16), r=0.24)
    b.cog(TRIM, (-R * 0.44 * E, R * 0.26, 1.20), r=0.34, teeth=12, thick=0.10,
          axis="Z")
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
    floor = b.whale(SKIN, DECK, (0.0, 0.0, D * 2.3), (L, B * 1.5, D * 1.35),
                    mi_glow=GLOW)

    if s.get("ram", True):
        b.tube(DECK, (-L * 1.22, 0.0, D * 2.3), B * 0.30, L * 0.34, seg=12,
               ry=math.radians(90), taper=0.05)
        b.ring(TRIM, (-L * 1.05, 0.0, D * 2.3), B * 0.34, B * 0.34, 0.16, seg=16, axis="X")

    loco_z = floor - D * 0.95
    drive = s.get("drive", "loco")
    if drive == "turbine":
        # Turbine drive: a bare armoured spine with ducted fans, no boiler or wheels.
        b.tube(HULL, (L * 0.05, 0.0, loco_z), B * 0.52, L * 1.60, seg=16,
               ry=math.radians(90))
        for k in (-0.28, 0.06, 0.40):
            b.ring(TRIM, (L * (0.05 + k), 0.0, loco_z), B * 0.56, B * 0.56, 0.12,
                   seg=18, axis="X")
        for side in (1, -1):
            b.tube(DECK, (L * 0.30, side * B * 0.95, loco_z), B * 0.40, L * 0.55,
                   seg=14, ry=math.radians(90))
            b.tube(GLOW, (L * 0.60, side * B * 0.95, loco_z), B * 0.30, 0.26, seg=14,
                   ry=math.radians(90))
    else:
        b.locomotive(HULL, DECK, TRIM, GLOW, (L * 0.05, 0.0, loco_z), L * 1.05, B * 0.62)
    # TRAIN CARS trailing the engine - hoppers, flatbeds and tankers. This is the other
    # half of the locomotive read, and what separates a salvager from a raider.
    for i in range(s.get("cars", 0)):
        cx = L * (0.95 + i * 0.62)
        kind = (s.get("car_kinds") or ["hopper", "flat", "tank"])[i % 3]
        b.box(DECK, (cx, 0.0, loco_z - B * 0.72), (L * 0.26, B * 1.30, B * 0.18))
        if kind == "hopper":
            b.box(HULL, (cx, 0.0, loco_z - B * 0.10), (L * 0.24, B * 1.10, B * 1.00))
            b.box(TRIM, (cx, 0.0, loco_z + B * 0.42), (L * 0.26, B * 1.16, 0.09))
        elif kind == "tank":
            b.tube(HULL, (cx, 0.0, loco_z - B * 0.05), B * 0.60, L * 0.46, seg=16,
                   ry=math.radians(90))
            b.ring(TRIM, (cx, 0.0, loco_z - B * 0.05), B * 0.63, B * 0.63, 0.10,
                   seg=16, axis="X")
        else:                                    # flatbed with lashed salvage
            b.box(SKIN, (cx, 0.0, loco_z - B * 0.30), (L * 0.24, B * 1.14, B * 0.30))
            b.box(HULL, (cx, B * 0.30, loco_z + B * 0.10), (L * 0.15, B * 0.45, B * 0.55))
        for side in (1, -1):
            for wx in (-L * 0.13, L * 0.13):
                b.ring(TRIM, (cx + wx, side * B * 0.78, loco_z - B * 1.00),
                       B * 0.26, B * 0.26, 0.10, seg=12, axis="Y")
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
    # An open launch: no gas bag at all, screw-driven. The smallest thing that flies.
    "VEN_KdmDinghy":       ("kdm_ship", dict(len=2.6, beam=0.70, depth=0.60,
                                             paddle=False, screw=True, stacks=[0.10])),
    "VEN_KdmLaunch":       ("kdm_ship", dict(len=3.8, beam=0.92, depth=0.80,
                                             paddle=False, screw=True,
                                             bag=(2.4, 0.94, 0.86, 3.15), ribs=3)),
    "VEN_KdmThunderbolt":  ("kdm_ship", dict(len=6.2, beam=1.30, depth=1.10, railgun=True,
                                             bag=(3.6, 1.36, 1.24, 4.35), ribs=4)),
    "VEN_KdmValiant":      ("kdm_ship", dict(len=6.6, beam=1.34, depth=1.18,
                                             bag=(4.6, 1.50, 1.40, 4.60), ribs=5,
                                             domes=[-0.42])),
    "VEN_KdmSentinel":     ("kdm_ship", dict(len=7.4, beam=1.52, depth=1.24,
                                             paddle=False, screw=True,
                                             turrets=[-0.18, 0.30],
                                             bag=(5.1, 1.62, 1.50, 4.95), ribs=5)),
    "VEN_KdmMender":       ("kdm_ship", dict(len=6.8, beam=1.60, depth=1.20, crane=True,
                                             blunt=True, stacks=[-0.10, 0.16],
                                             bag=(4.7, 1.60, 1.48, 4.80), ribs=4)),
    "VEN_KdmGoldenVanguard": ("kdm_ship", dict(len=9.2, beam=1.90, depth=1.40, decks=2,
                                               domes=[-0.40, -0.10, 0.20],
                                               turrets=[0.44], stacks=[-0.02, 0.22],
                                               boards=10,
                                               bag=(7.0, 2.05, 1.90, 6.10), ribs=6)),
    "VEN_KdmImperialBulwark": ("kdm_ship", dict(len=10.6, beam=2.30, depth=1.55, decks=3,
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
                                             cars=2, car_kinds=["flat", "tank"],
                                             cargo=True,
                                             bag=(3.7, 1.08, 0.95, 3.65), ribs=4)),
    "VEN_PirNighthawk":    ("pir_ship", dict(len=7.0, beam=1.10, depth=1.05, drive="turbine",
                                             turrets=[0.10],
                                             bag=(4.6, 1.15, 1.00, 4.05), ribs=5)),
    "VEN_PirBloodHawk":    ("pir_ship", dict(len=7.6, beam=1.18, depth=1.14, claws=True,
                                             turrets=[-0.10],
                                             bag=(4.9, 1.24, 1.08, 4.20), ribs=5)),
    "VEN_PirScrapKing":    ("pir_ship", dict(len=9.0, beam=1.60, depth=1.20, blunt=True,
                                             cars=3, car_kinds=["hopper", "flat", "hopper"],
                                             crane=True, cargo=True, claws=True,
                                             bag=(5.6, 1.55, 1.30, 4.70), ribs=5)),
    "VEN_PirBlackTide":    ("pir_ship", dict(len=11.0, beam=1.95, depth=1.45, blunt=True,
                                             cars=2, car_kinds=["tank", "hopper"],
                                             turrets=[-0.30, 0.04, 0.34],
                                             bag=(7.4, 1.95, 1.65, 5.80), ribs=6)),
    "VEN_PirGossamerGhost": ("pir_ship", dict(len=6.4, beam=1.02, depth=0.98, drive="turbine",
                                              ram=False, turrets=[0.16])),
    "VEN_PirMaelstrom":    ("pir_ship", dict(len=9.8, beam=1.75, depth=1.34, blunt=True,
                                             cars=1, car_kinds=["tank"],
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
    _join_detail(high, b, scene)
    _glow = b.materials[GLOW].node_tree.nodes["Principled BSDF"]
    _shade_windows(b.materials, b.window_plans,
                   _glow.inputs["Emission Color"].default_value[:3])

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
    import numpy as np                            # noqa: E402

    # Flat base colour is why these read as cardboard. Bake AMBIENT OCCLUSION as well and
    # multiply it in: contact shadows in every rivet seam, pipe run and plate gap are what
    # make a baked surface read as geometry rather than paint.
    d = img(b.name + "_d", (0.5, 0.5, 0.5, 1.0))
    bake(d, "DIFFUSE", pass_filter={"COLOR"})
    ao = img(b.name + "_ao", (1.0, 1.0, 1.0, 1.0))
    try:
        scene.cycles.samples = 24                 # AO is noisy at the flat-colour setting
        bake(ao, "AO")
    except Exception as ex:                       # noqa: BLE001
        _log("%s: AO bake failed (%s)" % (b.name, ex))
    finally:
        scene.cycles.samples = 4

    dpx = np.empty(len(d.pixels), dtype=np.float32)
    d.pixels.foreach_get(dpx)
    apx = np.empty(len(ao.pixels), dtype=np.float32)
    ao.pixels.foreach_get(apx)
    dr = dpx.reshape(-1, 4)
    ar = apx.reshape(-1, 4)[:, 0]
    # Keep some ambient - fully multiplying AO crushes cavities to black.
    shade = (0.42 + 0.58 * np.clip(ar, 0.0, 1.0))[:, None]
    dr[:, :3] = np.clip(dr[:, :3] * shade, 0.0, 1.0)
    d.pixels.foreach_set(dr.ravel())
    d.filepath_raw = root + "_diffuse.png"
    d.file_format = "PNG"
    d.save()

    e = img(b.name + "_e", (0.0, 0.0, 0.0, 1.0))
    bake(e, "EMIT")
    # DESATURATE toward white. A real emitter is overdriven at its core and reads nearly
    # white, with the hue carried by the spill - lamps authored at full chroma look like
    # colored plastic instead of light, and the engine's own intensity multiplier only
    # pushes them further. Pulling each channel toward the BRIGHTEST channel whitens the
    # lit texels while leaving black at black, so the map does not grey out.
    epx = np.empty(len(e.pixels), dtype=np.float32)
    e.pixels.foreach_get(epx)
    er = epx.reshape(-1, 4)
    peak = er[:, :3].max(axis=1)[:, None]
    er[:, :3] += (peak - er[:, :3]) * EMISSIVE_DESAT
    e.pixels.foreach_set(er.ravel())
    e.filepath_raw = root + "_emissive.png"
    e.file_format = "PNG"
    e.save()

    n_img = img(b.name + "_n", (0.5, 0.5, 1.0, 1.0), non_color=True)
    try:
        scene.render.bake.use_selected_to_active = True
        # Enough cage to cover rivet heads and pipe runs standing proud of the skin.
        scene.render.bake.cage_extrusion = 0.55
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

    # Specular from the material's ACTUAL roughness rather than guessed from diffuse
    # luminance: brass and iron come out bright and tight, canvas and timber matte, which
    # is the whole point of authoring metallic/roughness in the first place.
    rough = img(b.name + "_r", (0.5, 0.5, 0.5, 1.0), non_color=True)
    try:
        bake(rough, "ROUGHNESS")
        rpx = np.empty(len(rough.pixels), dtype=np.float32)
        rough.pixels.foreach_get(rpx)
        gloss = 1.0 - np.clip(rpx.reshape(-1, 4)[:, 0], 0.0, 1.0)
    except Exception as ex:                       # noqa: BLE001
        _log("%s: roughness bake failed (%s)" % (b.name, ex))
        gloss = np.full(len(d.pixels) // 4, 0.35, dtype=np.float32)
    spec = np.clip(gloss ** 1.4, 0.0, 1.0) * 0.85
    sp = img(b.name + "_s", (0.0, 0.0, 0.0, 1.0))
    sp.pixels.foreach_set(np.stack([spec, spec, spec, np.ones_like(spec)], axis=1).ravel())
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
