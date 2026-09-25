"""Generate the Venus cloud-sea skyboxes as Cosmos 4x3 cross PNGs.

WHY PROCEDURAL AND NOT GENERATIVE. A skybox has to be seamless across all twelve cube
edges and at both poles. A diffusion model does not know that, and stitching six
independently generated faces leaves a visible join on every edge - which is the one defect
you cannot unsee once the ship turns. Here every pixel's color is a pure function of its
3D direction, so continuity is not something to fix afterwards: two faces that share an
edge sample the same directions and therefore produce the same pixels, by construction.
The poles come out right for the same reason.

It also buys control the prompt route does not have. Venus is banded - fast zonal winds
smear the deck into horizontal strata - and the altitude gradient (pale thin haze above,
deep umber deck below) is the single most important thing this art has to say, because it
tells the player which way is DOWN in a world where down kills you.

THE CROSS LAYOUT WAS MEASURED; THE ORIENTATIONS ARE DERIVED. Those are different jobs and
conflating them cost two regenerations.

WHICH face sits in WHICH cell was settled by identifying the cells of a sky KNOWN to work in
Cosmos. `a28_sb00.png` was built by `boxey` from the Artemis 2.8 source faces, which are
still on disk, so each cell was matched against them by name: every one came back at
0.008-0.014 against a next-best of 0.5-0.86. Not a close call:

        .   front  .    .
      left   up   right down
        .   back   .    .

CONFIRMED AGAINST BOXEY'S SOURCE (github.com/dougreichard/boxey, `src/main.cpp`), the tool
that produced that sky: it draws `front` at column 1 row 0, `left up right down` across row
1, `back` at column 1 row 2. Its `-t 1` preset also rotates front 180, left CW, right CCW,
down 180 - and the face-matching above recovered exactly that, including the opposite senses
for left and right, which is a good sign the measurement was sound rather than lucky.

HOW each face is oriented is NOT a measurement, and trying to make it one is the trap. The
second version fitted a rot90/mirror per face by minimizing mismatch across the cross's
internal borders. It scored 0.59 - better than sky1.png - AND STILL SEAMED IN GAME, because
the cross exposes only FIVE of the cube's TWELVE edges. The other seven are cut by the
unfolding, so nothing was checking them, and the fitted answer needed MIRRORS on three
faces. A mirror flips that face's handedness: the five visible joins lined up while the
seven invisible ones tore.

So the orientations are now derived from the unfolding itself - see CELL_FRAMES - which
makes all twelve edges consistent by construction rather than by search. The invariant is
handedness, `cross(r, d) == -n` on every face, and `_calibrate_cross.py --geometry` asserts
it along with all twelve edges. Run that, not just the border score:

    python _calibrate_cross.py --geometry
    python _calibrate_cross.py --verify media/skybox/venus_sky_midday.png

The lesson worth keeping: a metric that only sees part of the object will happily report
success on a broken one. The border score was not wrong, it was partial.

UP/DOWN IS SETTLED, not assumed: the 2.8 match puts `skybox_UP` in the CENTER cell, which is
where the `+Y` face goes. FLIP_VERTICAL_AXIS remains only as a one-line escape if a render
ever says otherwise.
"""
import argparse
import math
import os

import numpy as np
from PIL import Image

FLIP_VERTICAL_AXIS = False       # see module docstring

# The six cells the engine reads, as (row, col) in the 4x3 cross. Measured from sky1.png,
# and each cell IDENTIFIED by matching a working sky against the 2.8 faces it was built
# from - see the module docstring.
CROSS_CELLS = {
    "front": (0, 1),
    "left":  (1, 0),
    "up":    (1, 1),
    "right": (1, 2),
    "down":  (1, 3),
    "back":  (2, 1),
}

# PER-CELL FRAMES - the cross unfolding, written down directly.
#
# Each cell gets an orthonormal frame: `n` is the face normal, `r` is the direction that
# image-RIGHT points, `d` is the direction image-DOWN points. A pixel at (u, v), both in
# -1..1 with u rightward and v downward, looks along normalize(n + u*r + v*d).
#
# WHY THIS REPLACED A SET OF FITTED ROTATIONS. The first version generated faces in a
# generic cubemap convention and then searched for a rot90/mirror per face that made the
# cross continuous. It scored well and still showed seams in game, because the cross only
# exposes FIVE of the cube's TWELVE edges - the other seven are cut by the unfolding, and
# nothing was checking them. The fitted answer needed MIRRORS on three faces, and a mirror
# flips that face's handedness: the five visible joins lined up while the seven invisible
# ones did not.
#
# Derived instead of fitted, the frames below are a genuine unfolding, so all twelve edges
# are consistent by construction. The invariant that says so is HANDEDNESS: every frame
# here satisfies `cross(r, d) == -n`. If a future edit breaks that for one face, that face
# is mirrored and the sky will seam. `_calibrate_cross.py --geometry` asserts both the
# handedness and all twelve edges.
#
# Note `front` is -Z and `back` is +Z here. That is just what the slot names mean in the
# unfolding boxey writes; a sky has no canonical forward, so the naming carries no weight.
CELL_FRAMES = {
    "up":    ((0, 1, 0), (1, 0, 0), (0, 0, 1)),
    "front": ((0, 0, -1), (1, 0, 0), (0, 1, 0)),
    "left":  ((-1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "right": ((1, 0, 0), (0, -1, 0), (0, 0, 1)),
    "back":  ((0, 0, 1), (1, 0, 0), (0, -1, 0)),
    "down":  ((0, -1, 0), (-1, 0, 0), (0, 0, 1)),
}


# ---------------------------------------------------------------- noise ----
def _hash3(ix, iy, iz, seed):
    """Integer hash -> [0,1). Cheap, vectorized, and stable across runs, which matters:
    a sky that changes when it is rebuilt cannot be compared against its own screenshot."""
    n = (ix * 374761393 + iy * 668265263 + iz * 2147483647 + seed * 971) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    n = n ^ (n >> 16)
    return (n & 0xFFFFFF).astype(np.float32) / float(0xFFFFFF)


def _value_noise(p, seed):
    """Trilinear value noise with a smoothstep fade - the classic, and smooth enough that
    a cloud deck built from it has no lattice showing."""
    i = np.floor(p).astype(np.int64)
    f = p - i
    f = f * f * (3.0 - 2.0 * f)
    ix, iy, iz = i[..., 0], i[..., 1], i[..., 2]
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    c = {}
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                c[(dx, dy, dz)] = _hash3(ix + dx, iy + dy, iz + dz, seed)
    x00 = c[(0, 0, 0)] + (c[(1, 0, 0)] - c[(0, 0, 0)]) * fx
    x10 = c[(0, 1, 0)] + (c[(1, 1, 0)] - c[(0, 1, 0)]) * fx
    x01 = c[(0, 0, 1)] + (c[(1, 0, 1)] - c[(0, 0, 1)]) * fx
    x11 = c[(0, 1, 1)] + (c[(1, 1, 1)] - c[(0, 1, 1)]) * fx
    y0 = x00 + (x10 - x00) * fy
    y1 = x01 + (x11 - x01) * fy
    return y0 + (y1 - y0) * fz


def _fbm(p, seed, octaves=6, lacunarity=2.0, gain=0.5):
    total = np.zeros(p.shape[:-1], dtype=np.float32)
    amp, freq, norm = 1.0, 1.0, 0.0
    for o in range(octaves):
        total += amp * _value_noise(p * freq, seed + o * 101)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm


def _ridged(p, seed, octaves=5):
    """Ridged fBm - the sharp-edged, curdled look of a convective cloud top, as opposed to
    the woolly look plain fBm gives."""
    total = np.zeros(p.shape[:-1], dtype=np.float32)
    amp, freq, norm = 1.0, 1.0, 0.0
    for o in range(octaves):
        n = _value_noise(p * freq, seed + o * 313)
        n = 1.0 - np.abs(n * 2.0 - 1.0)
        total += amp * n * n
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return total / norm


# ---------------------------------------------------------------- faces ----
def _face_dirs(face, size):
    """Unit direction per pixel for one cross cell, from its CELL_FRAMES frame.

    u runs -1..1 left to right, v runs -1..1 top to bottom, matching image order - so the
    array this returns is already in the orientation its cell needs. No post-hoc rotation.
    """
    n, r, d = (np.array(x, np.float32) for x in CELL_FRAMES[face])
    t = (np.arange(size, dtype=np.float32) + 0.5) / size * 2.0 - 1.0
    u, v = np.meshgrid(t, t)                      # u varies along columns, v along rows
    vec = n + u[..., None] * r + v[..., None] * d
    return vec / np.linalg.norm(vec, axis=-1, keepdims=True)


def _ramp(alt, stops):
    """Piecewise-linear color ramp over altitude (-1 down .. +1 up). `stops` is a list of
    (altitude, (r,g,b)) in 0..255, low to high."""
    out = np.zeros(alt.shape + (3,), dtype=np.float32)
    for i in range(len(stops) - 1):
        a0, c0 = stops[i]
        a1, c1 = stops[i + 1]
        m = (alt >= a0) & (alt <= a1)
        if not m.any():
            continue
        w = ((alt[m] - a0) / max(a1 - a0, 1e-6))[..., None]
        out[m] = np.array(c0, np.float32) * (1 - w) + np.array(c1, np.float32) * w
    out[alt < stops[0][0]] = np.array(stops[0][1], np.float32)
    out[alt > stops[-1][0]] = np.array(stops[-1][1], np.float32)
    return out


def _billow(q, seed, octaves=5):
    """Puffy cumulus heights: |noise| folded UP (the inverse of ridged), so the tops are
    round and the gaps between them are the sharp creases."""
    total = np.zeros(q.shape[:-1], dtype=np.float32)
    amp, freq, norm = 1.0, 1.0, 0.0
    for o in range(octaves):
        n = _value_noise(q * freq, seed + o * 577)
        total += amp * np.abs(n * 2.0 - 1.0)
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return 1.0 - total / norm


def _puffs(u, v, seed, jitter=0.9):
    """Cellular cumulus as a SOFT field: every cell's puff is a smooth kernel (1-d^2)^2 and
    the kernels are SUMMED over the 3x3 neighborhood, so neighboring lobes merge the way
    cloud does. (Taking the max instead left hard creases - a cracked tile floor.)"""
    iu = np.floor(u).astype(np.int64)
    iv = np.floor(v).astype(np.int64)
    total = np.zeros(u.shape, np.float32)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cu, cv = iu + ox, iv + oy
            zero = np.zeros_like(cu)
            pu = cu + 0.5 + (_hash3(cu, cv, zero, seed) - 0.5) * jitter
            pv = cv + 0.5 + (_hash3(cu, cv, zero, seed + 17) - 0.5) * jitter
            r = 0.75 + 0.55 * _hash3(cu, cv, zero, seed + 29)
            d2 = ((u - pu) ** 2 + (v - pv) ** 2) / (r * r)
            k = np.clip(1.0 - d2, 0.0, 1.0)
            total += k * k * r
    return total


def _domes(az, alt, seed, count, height, width):
    """Cumulus towers on the horizon as a SOFT field in (azimuth, altitude): each tower is a
    column of lobes shrinking as it rises, every lobe a smooth kernel, all SUMMED so the
    lobes merge. Threshold it for the silhouette; its slope is the lighting."""
    rng = np.random.default_rng(seed)
    field = np.zeros(az.shape, np.float32)
    for i in range(count):
        a0 = rng.uniform(-math.pi, math.pi)
        tall = height * rng.uniform(0.3, 1.0) ** 1.5
        w0 = width * rng.uniform(0.6, 1.4)
        lobes = 4 + int(tall / height * 8)
        for k in range(lobes):
            f = rng.uniform(0.0, 1.0) ** 0.8
            cx = a0 + rng.normal(0.0, 0.45) * w0 * (1.0 - 0.6 * f)
            cy = tall * f * 0.9
            rw = w0 * (0.55 + 0.5 * rng.uniform()) * (1.0 - 0.5 * f)
            rh = rw * 0.85
            da = np.angle(np.exp(1j * (az - cx))) / rw
            dl = (alt - cy) / rh
            kk = np.clip(1.0 - (da * da + dl * dl), 0.0, 1.0)
            field += kk * kk
    return field


def _plane(d, y_sign, height, scale):
    """Where each direction meets a horizontal cloud plane `height` above (+1) or below (-1)
    the viewer, as 3D noise coordinates; plus the distance to it (for the haze fade)."""
    dy = np.maximum(d[..., 1] * y_sign, 1e-3)
    t = height / dy
    q = np.stack([d[..., 0] * t * scale, np.full(dy.shape, 0.37, np.float32),
                  d[..., 2] * t * scale], -1)
    return q, t


def _cloud_forms(d, alt, base, p):
    sea_amp = p.get("sea_amp", 0.0)
    bank_amp = p.get("bank_amp", 0.0)
    ceil_amp = p.get("ceil_amp", 0.0)
    fog = p.get("fog", 0.0)
    sd = np.array(p["sun_dir"], np.float32)
    sd = sd / np.linalg.norm(sd)
    lit_c = np.array(p.get("sea_lit", (250, 232, 196)), np.float32)
    shade_c = np.array(p.get("sea_shadow", (150, 110, 70)), np.float32)

    if sea_amp > 0:
        # The sea below. A fractal DENSITY on a plane under the viewer (billowed, so it
        # clumps into lobes), cut to a silhouette, and SELF-SHADOWED: a few samples stepped
        # toward the sun - thick cloud between a point and the sun darkens it, which is
        # what gives cumulus its volume. The horizon haze eats it with distance.
        q, t = _plane(d, -1.0, p.get("sea_depth", 1.0), p.get("sea_scale", 0.5))
        u, v = q[..., 0] * 0.8, q[..., 2] * 0.8
        near = np.exp(-t * 0.35)

        def dens(uu, vv):
            pp = np.stack([uu, np.full(uu.shape, 0.5, np.float32), vv], -1)
            big = _billow(pp, p["seed"] + 1201, octaves=4)
            fine = _billow(pp * 5.0, p["seed"] + 1211, octaves=3)
            return big * 0.9 + (fine - 0.5) * 0.35 * (0.3 + 0.7 * near)

        dd = dens(u, v)
        su, sv = sd[0], sd[2]
        sl = math.hypot(su, sv) or 1.0
        occl = np.zeros(u.shape, np.float32)
        for k in range(1, 5):
            st = 0.06 * k
            occl += np.clip(dens(u + su / sl * st, v + sv / sl * st) - dd * 0.9, 0.0, None)
        light = np.exp(-occl * 5.0) * (0.45 + 0.55 * np.clip((dd - 0.5) * 3.0, 0.0, 1.0))
        light = np.clip(light, 0.0, 1.0)[..., None]
        cover = np.clip((dd - p.get("sea_gap", 0.5)) / 0.08, 0.0, 1.0)
        color = shade_c * (1 - light) + lit_c * light
        below = np.clip((-alt - 0.015) / 0.06, 0.0, 1.0)
        far = np.exp(-t * p.get("sea_haze", 0.12))
        w = (cover * below * far * sea_amp)[..., None]
        base = base * (1 - w) + color * w

    if bank_amp > 0:
        # Towers on the horizon, the same way in (azimuth, altitude): a billowed density
        # under a ragged height envelope that varies around the ring, self-shadowed by
        # stepping toward the sun (sideways by azimuth, upward by altitude).
        az = np.arctan2(d[..., 0], d[..., 2])
        height = p.get("bank_height", 0.22)
        ring = np.stack([np.cos(az) * 2.2, np.sin(az) * 2.2, np.full(az.shape, 0.3, np.float32)], -1)
        top = height * (0.25 + 1.1 * np.power(np.clip(_fbm(ring, p["seed"] + 1301, 4) * 1.6 - 0.3, 0.0, 1.0), 2.0))

        def dens(a_, l_):
            pp = np.stack([np.cos(a_) * 16.0, l_ * 16.0, np.sin(a_) * 16.0], -1)
            b_ = _billow(pp, p["seed"] + 1307, octaves=4)
            env = 1.0 - np.clip((l_ + 0.02) / np.maximum(top, 1e-3), 0.0, 1.2)
            return b_ * 0.6 + env * 0.75 - 0.15

        dd = dens(az, alt)
        saz = math.atan2(sd[0], sd[2])
        rel = np.sign(np.sin(np.angle(np.exp(1j * (saz - az)))))
        occl = np.zeros(az.shape, np.float32)
        for k in range(1, 5):
            st = 0.006 * k
            occl += np.clip(dens(az + rel * st, alt + st * 0.8) - 0.45, 0.0, None)
        feet = np.clip((alt + 0.02) / max(height, 1e-3), 0.0, 1.0)
        light = np.clip(np.exp(-occl * 0.8) * (0.45 + 0.55 * feet) + 0.1, 0.0, 1.0)[..., None]
        inside = np.clip((dd - 0.45) / 0.1, 0.0, 1.0) * np.clip((alt + 0.06) / 0.05, 0.0, 1.0)
        color = shade_c * (1 - light) + lit_c * light
        w = (inside * bank_amp)[..., None]
        base = base * (1 - w) + color * w

    if ceil_amp > 0:
        # An overcast overhead - the layer above you - streaked along the zonal wind.
        q, t = _plane(d, 1.0, p.get("ceil_height", 1.0), p.get("ceil_scale", 1.2))
        q = q * np.array([0.7, 1.0, 1.0], np.float32)        # a little stretched: wind
        n = _fbm(q, p["seed"] + 1401, 5)
        cover = np.clip((n - p.get("ceil_gap", 0.42)) / 0.2, 0.0, 1.0)
        # faded out well above the horizon: the plane's grazing rows stretch into arcs
        above = np.clip((alt - 0.12) / 0.3, 0.0, 1.0)
        far = np.exp(-t * 0.3)
        under = np.array(p.get("ceil_color", (190, 150, 104)), np.float32)
        w = (cover * above * (0.35 + 0.65 * far) * ceil_amp)[..., None]
        base = base * (1 - w) + under * w

    if fog > 0:
        # Inside the layer: everything milky toward the horizon, where the most air is.
        mist = np.array(p.get("fog_color", (214, 186, 146)), np.float32)
        w = (fog * (1.0 - np.abs(alt)) ** 3)[..., None]
        base = base * (1 - w) + mist * w
    return base


def shade(d, p):
    """Color a set of directions. `p` is the variant's parameter dict."""
    alt = d[..., 1].copy()
    if FLIP_VERTICAL_AXIS:
        alt = -alt

    # Domain warp first: straight fBm reads as noise, warped fBm reads as weather.
    w = _fbm(d * p["warp_freq"], p["seed"] + 7, octaves=4)[..., None]
    dw = d + (w - 0.5) * p["warp"]

    base = _ramp(alt, p["stops"])

    # Zonal banding. Venus's super-rotation smears the deck into latitude stripes, and the
    # bands are what make an altitude readable at a glance rather than a smooth gradient.
    band = np.sin(alt * math.pi * p["bands"] + _fbm(dw * 1.7, p["seed"] + 31, 3) * p["band_wobble"])
    base += band[..., None] * np.array(p["band_tint"], np.float32) * p["band_amp"]

    # Cloud tops: ridged where the deck is thick, softer up high where the haze thins out.
    thick = np.clip((0.35 - alt) / 1.2, 0.0, 1.0)
    clouds = _ridged(dw * p["cloud_freq"], p["seed"] + 53) * thick
    base += clouds[..., None] * np.array(p["cloud_tint"], np.float32) * p["cloud_amp"]

    # Fine curdle, everywhere, so smooth areas are not plastic.
    base += (_fbm(dw * p["detail_freq"], p["seed"] + 77, 5)[..., None] - 0.5) * p["detail_amp"]

    # The sun, seen THROUGH the haze - a broad bloom, never a disc. On Venus the sun is a
    # bright smear; a hard disc would read as a different planet.
    sd = np.array(p["sun_dir"], np.float32)
    sd = sd / np.linalg.norm(sd)
    cosang = np.clip((d * sd).sum(-1), -1.0, 1.0)
    glow = np.power(np.clip(cosang, 0.0, 1.0), p["sun_tight"])
    base += glow[..., None] * np.array(p["sun_tint"], np.float32) * p["sun_amp"]

    # ---- Cloud FORMS (2026-09-25). Everything above is gradients and bands; nothing in it
    # reads as a CLOUD, so the sky said "haze" and never "you are flying in the clouds".
    base = _cloud_forms(d, alt, base, p)

    # Lightning: sparse, only down in the deck, where the concept art puts it.
    if p.get("lightning_amp", 0) > 0:
        lf = _fbm(dw * p["lightning_freq"], p["seed"] + 991, 3)
        strike = np.clip((lf - p["lightning_thresh"]) / (1.0 - p["lightning_thresh"]), 0, 1)
        strike = np.power(strike, 3.0) * np.clip((-alt - 0.05) * 2.2, 0, 1)
        base += strike[..., None] * np.array(p["lightning_tint"], np.float32) * p["lightning_amp"]

    return np.clip(base, 0, 255).astype(np.uint8)


# boxey's Blender preset (`-t 0`) names the six faces by number. Emitting them lets the
# sky be assembled by boxey, or opened in any other cubemap tool, instead of only by
# build_cross below.
#
# Note that `-t 0` assembles with NO rotation - it calls make_blender(no_rotate=true) and
# only places the images - which is exactly right, because CELL_FRAMES already produces each
# face in the orientation its cell needs. (boxey takes six FACES, not an equirectangular
# panorama - all three of its presets are six-file inputs.) boxey is not
# a way to avoid getting the orientation right; it is a way to hand the faces to something
# else once they are.
BOXEY_BLENDER_NAMES = {"left": "0001", "up": "0002", "right": "0003",
                       "down": "0004", "front": "0005", "back": "0006"}


def build_faces(p, face_size):
    """The six faces as separate images, oriented for the cross."""
    return {face: Image.fromarray(shade(_face_dirs(face, face_size), p), "RGB")
            for face in CROSS_CELLS}


def build_cross(p, face_size):
    img = np.zeros((face_size * 3, face_size * 4, 3), dtype=np.uint8)
    for face, (r, c) in CROSS_CELLS.items():
        px = shade(_face_dirs(face, face_size), p)
        img[r * face_size:(r + 1) * face_size, c * face_size:(c + 1) * face_size] = px
    return Image.fromarray(img, "RGB")


def build_equirect(p, width=1024):
    """A flat panorama of the same sky - not shipped, just the fastest way to judge a
    variant without opening the game."""
    height = width // 2
    lon = (np.arange(width, dtype=np.float32) + 0.5) / width * 2 * math.pi - math.pi
    lat = math.pi / 2 - (np.arange(height, dtype=np.float32) + 0.5) / height * math.pi
    lo, la = np.meshgrid(lon, lat)
    d = np.stack([np.cos(la) * np.sin(lo), np.sin(la), np.cos(la) * np.cos(lo)], -1)
    return Image.fromarray(shade(d.astype(np.float32), p), "RGB")


# ------------------------------------------------------------- variants ----
# Palettes are read off the concept art: sulfur ochre through amber to a deep umber deck.
_DAY = [(-1.0, (46, 30, 18)), (-0.55, (96, 62, 30)), (-0.15, (168, 120, 58)),
        (0.15, (214, 172, 104)), (0.55, (232, 200, 150)), (1.0, (240, 220, 182))]
_DUSK = [(-1.0, (30, 17, 12)), (-0.55, (86, 40, 22)), (-0.15, (166, 84, 40)),
         (0.15, (208, 130, 68)), (0.55, (222, 168, 116)), (1.0, (226, 190, 152))]
_STORM = [(-1.0, (18, 13, 11)), (-0.55, (48, 34, 24)), (-0.15, (96, 68, 42)),
          (0.15, (150, 112, 70)), (0.55, (186, 152, 106)), (1.0, (204, 176, 138))]
_DEEP = [(-1.0, (14, 9, 6)), (-0.55, (40, 25, 14)), (-0.15, (84, 54, 26)),
         (0.15, (124, 86, 44)), (0.55, (156, 116, 68)), (1.0, (172, 136, 90))]
_NIGHT = [(-1.0, (20, 12, 8)), (-0.55, (36, 22, 14)), (-0.15, (58, 38, 24)),
          (0.15, (74, 54, 40)), (0.55, (86, 70, 60)), (1.0, (92, 80, 74))]
_HIGH = [(-1.0, (78, 54, 30)), (-0.55, (142, 104, 54)), (-0.15, (200, 158, 92)),
         (0.15, (228, 196, 140)), (0.55, (240, 218, 176)), (1.0, (246, 232, 202))]

_BASE = dict(
    warp=0.55, warp_freq=1.6, bands=7.0, band_wobble=2.2, band_amp=16.0,
    band_tint=(1.0, 0.82, 0.55), cloud_freq=4.5, cloud_amp=52.0,
    cloud_tint=(1.0, 0.88, 0.68), detail_freq=13.0, detail_amp=14.0,
    sun_dir=(0.55, 0.30, 0.78), sun_tight=7.0, sun_amp=70.0,
    sun_tint=(1.0, 0.90, 0.70), lightning_amp=0.0,
    lightning_freq=9.0, lightning_thresh=0.80, lightning_tint=(0.72, 0.68, 1.0),
)


def _v(**kw):
    p = dict(_BASE)
    p.update(kw)
    return p


VARIANTS = {
    # Cloud forms by band (2026-09-25): high = the sea far below; lanes = the sea below and
    # towers on the horizon; storm/deep = INSIDE the layer, cloud overhead as well as below.
    "venus_sky_high_haze": ("Venus - High Haze (pale gold)", _v(
        seed=1101, stops=_HIGH, bands=6.0, cloud_amp=40.0, sun_amp=86.0, sun_tight=5.5,
        sea_amp=1.0, sea_depth=2.2, sea_scale=0.35, bank_amp=0.8, bank_height=0.1,
        fog=0.1, sea_lit=(255, 244, 218), sea_shadow=(176, 140, 96))),
    "venus_sky_midday": ("Venus - Midday Deck (amber)", _v(
        seed=2202, stops=_DAY, sea_amp=1.0, bank_amp=0.9, ceil_amp=0.35, fog=0.18,
        sea_shadow=(132, 92, 54))),
    "venus_sky_dusk": ("Venus - Terminator Dusk (orange)", _v(
        seed=3303, stops=_DUSK, sun_dir=(0.95, -0.05, 0.30), sun_tight=4.0, sun_amp=96.0,
        bands=8.0, sea_amp=1.0, bank_amp=0.95, bank_height=0.26, ceil_amp=0.3, fog=0.16,
        sea_lit=(250, 190, 130), sea_shadow=(110, 56, 32))),
    "venus_sky_stormwall": ("Venus - Storm Wall (dark umber)", _v(
        seed=4404, stops=_STORM, warp=0.85, cloud_freq=5.5, cloud_amp=64.0,
        sun_amp=34.0, lightning_amp=150.0, sea_amp=0.95, sea_depth=0.7, bank_amp=1.0,
        bank_height=0.38, ceil_amp=0.5, ceil_height=0.6, ceil_gap=0.45, fog=0.3,
        sea_lit=(196, 164, 124), sea_shadow=(58, 40, 28), ceil_color=(96, 72, 50),
        fog_color=(120, 94, 66))),
    "venus_sky_deep": ("Venus - Deep Deck (oppressive)", _v(
        seed=5505, stops=_DEEP, bands=9.0, cloud_amp=58.0, sun_amp=22.0, sun_tight=10.0,
        lightning_amp=110.0, lightning_thresh=0.84, sea_amp=0.9, sea_depth=0.45,
        bank_amp=0.9, bank_height=0.3, ceil_amp=0.9, ceil_height=0.5, ceil_gap=0.25,
        fog=0.38, sea_lit=(150, 112, 70), sea_shadow=(40, 26, 16), ceil_color=(84, 60, 38),
        fog_color=(96, 70, 44))),
    "venus_sky_nightside": ("Venus - Nightside (dim sulfur)", _v(
        seed=6606, stops=_NIGHT, sun_amp=8.0, cloud_amp=34.0, detail_amp=9.0,
        lightning_amp=190.0, lightning_thresh=0.86, sea_amp=0.9, bank_amp=0.8,
        ceil_amp=0.4, fog=0.2, sea_lit=(120, 102, 86), sea_shadow=(34, 24, 18),
        ceil_color=(60, 50, 44), fog_color=(70, 58, 50))),
}


def probe_cross(path):
    """Re-measure which cells a reference sky fills, so CROSS_CELLS stays a measurement."""
    im = Image.open(path).convert("RGB").resize((4 * 64, 3 * 64), Image.BILINEAR)
    a = np.asarray(im, np.float32)
    print(os.path.basename(path) + ":")
    for r in range(3):
        print("   ", "  ".join("%7.2f" % a[r * 64:(r + 1) * 64, c * 64:(c + 1) * 64].mean()
                               for c in range(4)))


def main():
    ap = argparse.ArgumentParser(description="Generate the Venus skybox set.")
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--out", default=os.path.join(here, "media", "skybox"))
    ap.add_argument("--preview", default=os.path.join(here, "_preview"))
    ap.add_argument("--face", type=int, default=1024, help="face size in px")
    ap.add_argument("--only", default=None, help="one variant key")
    ap.add_argument("--probe", default=None, help="measure a reference sky's cross instead")
    ap.add_argument("--faces", default=None, metavar="DIR",
                    help="also write the six faces separately, in boxey's Blender naming "
                         "(0001..0006), so the sky can be assembled by boxey -t 0 or "
                         "opened in another cubemap tool")
    a = ap.parse_args()

    if a.probe:
        probe_cross(a.probe)
        return

    os.makedirs(a.out, exist_ok=True)
    os.makedirs(a.preview, exist_ok=True)
    total = 0.0
    for key, (title, p) in VARIANTS.items():
        if a.only and key != a.only:
            continue
        cross = build_cross(p, a.face)
        dst = os.path.join(a.out, key + ".png")
        # Level 9: A28 measured the stock skies shipping at Blender's default level 1 and
        # recompressing them lossless for a third off. No reason to repeat that mistake.
        cross.save(dst, "PNG", optimize=True, compress_level=9)
        build_equirect(p).save(os.path.join(a.preview, key + "_equirect.png"))
        if a.faces:
            fdir = os.path.join(a.faces, key)
            os.makedirs(fdir, exist_ok=True)
            for face, img in build_faces(p, a.face).items():
                img.save(os.path.join(fdir, BOXEY_BLENDER_NAMES[face] + ".png"))
        mb = os.path.getsize(dst) / 1024.0 / 1024.0
        total += mb
        print("  %-24s %dx%d  %6.2f MB   %s" % (key, cross.size[0], cross.size[1], mb, title))
    print("  %-24s %6.2f MB" % ("TOTAL", total))


if __name__ == "__main__":
    main()
