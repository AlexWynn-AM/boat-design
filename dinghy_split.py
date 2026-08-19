#!/usr/bin/env python3
"""
dinghy_split.py - Rev-3 transportable split of the Rev-2 dinghy hull.

Splits the 9ft hull into 4 independently watertight, car-transportable pieces,
reusing the parametric hull lines from dinghy_hull-2.py:

  * CENTER  - constant-width (42") open-top tub, x=0..BOW_SPLIT. The cargo/people
              barge. Vertical mating walls at y = +/-YC wherever the hull is wider
              than 42"; follows the hull lines forward of that. A complete boat by
              itself.
  * WEDGES  - port & starboard solid buoyancy pods outboard of y = +/-YC. Carry the
              original outer skin (bottom panel + spray-railed topside + gunwale).
              Triangular in plan (~13" at the transom -> 0" where the hull narrows
              to 42"). Each ~1 ft wide -> trivially transportable. Stern width can
              be grown just by enlarging the wedges, independent of transport.
  * BOW     - sealed nose pod, x=BOW_SPLIT..stem (simplified solid + flat deck).

Each piece is built as its own clean closed manifold (the Rev-2 monolith is NOT
watertight, so we construct rather than boolean-cut).

Phase 1: clean split + per-piece watertight check + exploded/assembled previews.
Phase 2 (later): vertical slide-down dovetail + above-waterline bolt bosses.

Usage:
    python dinghy_split.py                 # STLs + previews
    python dinghy_split.py --no-preview
    python dinghy_split.py --scale 10      # 1:10 mm models
"""

import argparse
import importlib.util
from pathlib import Path

import numpy as np

# ------------------------------------------------------------------
# Load the Rev-2 hull engine (file name has a hyphen -> import by path)
# ------------------------------------------------------------------
_spec = importlib.util.spec_from_file_location(
    "dinghy_hull2", str(Path(__file__).with_name("dinghy_hull-2.py"))
)
h2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h2)

DinghyHull = h2.DinghyHull
ear_clip = h2.ear_clip

# ------------------------------------------------------------------
# REV-3 HULL LINES (non-destructive override of dinghy-hull-2.py)
# ------------------------------------------------------------------
# "A little more triangular": same full 68" transom and the same deadrise/flare
# character, but the plan taper is pulled forward so the hull narrows to the 42"
# center width (sheer half-width = YC = 21") at x=60" instead of x=72". That makes
# the center a TRUE constant-width rectangle from the transom to the bow split, and
# lets the split land at x=60. Base file dinghy-hull-2.py is left untouched; we just
# swap the module's STATIONS before constructing the hull.
# Tuple format: (x_from_transom, bottom_half_beam, chine_z, sheer_half_beam, sheer_z, deadrise_deg)
REV3_STATIONS = [
    (0,    30.0,  2.6, 34.0, 22.0,  5),   # transom: full 68" beam
    (12,   29.0,  2.6, 33.0, 22.0,  6),
    (24,   27.5,  2.8, 31.0, 22.0,  8),
    (36,   24.5,  3.0, 28.0, 22.3, 10),
    (48,   20.5,  3.4, 24.5, 22.5, 12),
    (60,   16.0,  4.0, 21.0, 23.0, 14),   # <- narrows to 42" here (was x=72): split
    (72,   11.0,  6.0, 16.0, 23.5, 17),
    (84,    7.0,  8.5, 11.0, 24.0, 20),
    (96,    3.0, 11.0,  6.0, 24.8, 25),
    (108,   0.5, 14.0,  1.5, 25.5, 30),   # stem
]
h2.STATIONS = REV3_STATIONS   # DinghyHull() reads this at construction
h2.N_BOTTOM = 30   # source hull cross-section density (was 12) -> smoother sections
h2.N_SIDE = 37     # source topside/spray-rail curve density (was 10)

# ------------------------------------------------------------------
# SPLIT PARAMETERS
# ------------------------------------------------------------------
YC = 21.0                 # center half-width (42" full beam) -> car-fit constraint
WALL = h2.WALL_THICKNESS  # 0.75"
BOW_SPLIT = 60.0          # split where the hull narrows to 42" -> true-rectangle center
LOA = h2.LOA              # 108" (design length, before DESIGN_SCALE)

# Uniform downscale of the whole boat applied at STL export and in the fit summary.
# 0.90 -> 8.1 ft LOA, ~54" center -> comfortable GLC fit + nesting margin.
# NOTE: volume/displacement scales as DESIGN_SCALE**3 (0.9 -> ~27% less capacity).
DESIGN_SCALE = 0.90

# ------------------------------------------------------------------
# PRINT-AND-GLASS WALL THICKNESSES (full-size boat is ASA-printed then fiberglassed,
# so the print is a light core/substrate and the glass is the structure). Thin walls
# to save ASA; keep the sole thicker for stiffness; the transom stays solid.
# Values are REAL targets -> /DESIGN_SCALE gives the design-unit thickness.
SKIN = (7.0 / 25.4) / DESIGN_SCALE     # ~7 mm real: sides/topsides/deck/shells
FLOOR = (14.0 / 25.4) / DESIGN_SCALE   # ~14 mm real: center cockpit sole (stiffness)
WALL = SKIN                            # override the earlier WALL = h2.WALL_THICKNESS
h2.WALL_THICKNESS = SKIN               # so hull.half_inner() also uses the thin skin

# ASA + fiberglass weight model (echoed in the printout so it's tunable)
ASA_DENSITY = 1.07      # g/cm^3 (ASA filament)
# Print mass split into two independent knobs (this is how the slicer lays it down):
#   SKIN  = surface area * PERIM_SHELL  (the solid perimeter shells, printed ~100%)
#   INFILL = the remaining material volume * INFILL  (sparse lattice in thicker regions)
PERIM_SHELL = 0.5       # mm SOLID perimeter per face = 1 perimeter (set to YOUR extrusion
                        # width). The print is a glass core/mold, so 1 clean shell is enough.
INFILL = 0.12           # infill density beyond the perimeter (use GYROID -- isotropic + best shear
                        # as a sandwich core; grid is weaker/anisotropic in shear)
# Fiberglass schedule by ZONE (laminated areal mass incl. resin, kg/m^2):
GLASS_BOTTOM  = 1.2     # exterior bottom: 1708 biax (~1.2) -- tough, for beaching
GLASS_TOPSIDE = 0.4     # exterior topsides: 6 oz (1708 stays on the bottom); 1.2 to match bottom
GLASS_DECK    = 0.27    # decks/gunwale tops: 4 oz (core gives the stiffness; carbon not needed)
GLASS_INSIDE  = 0.4     # interior (cockpit only): 6 oz (~0.4; 0.27 for 4 oz)
GLASS_INTERIOR_OF = {"center": True, "bow": False,           # cockpit glassed; bow storage bare
                     "wedge_stbd": False, "wedge_port": False}  # wedges are sealed pods

NP = 61                   # points per half-profile (loft resolution, must be const)
N_GW = 2                  # bridge points across each gunwale top
N_STN_AFT = 220           # longitudinal stations for the aft pieces (x=0..BOW_SPLIT)
N_STN_BOW = 110           # longitudinal stations for the bow (x=BOW_SPLIT..stem)
EPS = 1e-6

# Dovetail (Phase 2): fore-aft tapered sliding dovetail in the upper mating wall.
# The CENTER gets the groove and each WEDGE the matching tongue, both generated
# from ONE shared contour (mating_wall_contour) so they mate exactly. The pocket
# tapers from full at the transom (tall wall) to nothing forward (short wall), so
# the wedge self-seats as it slides forward; bolts (later phase) lock the slide.
DT_DEPTH = 0.75     # max inboard depth of the dovetail pocket (in)  [was 1.25]
DT_UNDER = 0.4      # undercut half-height (back taller than mouth) -> locks +/-y
DT_MOUTH = 2.0      # pocket mouth z-height at full taper (in)        [was 3.0]
DT_TOP_GAP = 1.0    # pocket top kept this far below the sheer (in)
DT_WALL_FULL = 8.0  # wall height (sz-zc) at/above which the dovetail is full size
DT_WALL_MIN = 2.5   # wall height below which the dovetail fades to nothing
RAIL_W = 1.3        # center inner wall locally thickened to YC-RAIL_W behind groove
                    # [was 2.0; smaller dovetail needs less backing -> less overhang]
RAIL_MARGIN = 0.3   # rail z-band extends this far past the groove band

# Stern trapezoid: the mating cut line is widened by DSTERN at the transom and
# tapers back to YC at the bow split, so the center is a slight trapezoid (wider
# stern) -> its cockpit opening is wide enough for the bow to nest inside.
DSTERN = 2.0        # extra half-width at the transom (full beam +2*DSTERN there)
                    # -> stern cockpit ~4" wider than the split, so the bow nests
                    #    without needing a chamfer on its foredeck corners

# Bow aft-top-corner chamfer: bevel the bow's top outboard corners over its aft
# length so its widest sections clear the center's gunwale rail when nested. Tuned
# so the bow drops into the cockpit with positive clearance everywhere.
CHAMFER_LEN = 16.0  # aft bow length over which the chamfer fades to nothing (in)
CHAMFER_DZ = 8.0    # chamfer reaches this far down from the sheer (in)
CHAMFER_DY = 0.0    # 0 -> no chamfer: clean foredeck that matches the center gunwale.
                    # (the wider DSTERN trapezoid now gives the nesting clearance)

# Bow plan-view sheer: bulge the top-down bow outline this far (design in) past the
# straight stem->split chord at midbow. +ve = convex (full, prettier), 0 = straight,
# -ve = concave (hollow). The hull lines alone run ~0.3" hollow; this fills it out.
BOW_CONVEX = 0.6

# Foredeck transverse camber (crown) in design in. 0 = flat deck. (Was tried at 2.0
# but the centerline hump read wrong; keep the deck flat.)
BOW_CAMBER = 0.0
N_DECK = 27

# Nose radius: over the forward NOSE_ROUND inches, ease the section in along a
# quarter-ellipse down to NOSE_SC_MIN of full size. Small NOSE_ROUND keeps it a tight
# nose (not a long bullnose); NOSE_SC_MIN near 0 closes the round across -> no flat end.
NOSE_ROUND = 2.5
NOSE_RINGS = 24
NOSE_SC_MIN = 0.05
# Nose taper profile: sc = (1-f)**NOSE_POW. 0.5 = parabolic ogive (tapers from the
# start, only the very tip rounds -> NO bulbous neck). 1.0 would be a sharp cone.
NOSE_POW = 0.5

# Spray-rail fade: keep the rail full through the forward bow (it's wanted there), and
# only fade it to 0 over the LAST BOW_RAIL_FADE inches near the stem, where the section
# gets finer than the rail and it would otherwise bulge past the sheer.
BOW_RAIL_FADE = 10.0

# Bow storage compartment: hollow the bow (BOW_WALL walls) with a dome/arch opening in
# its aft face so the bow space is open to the cockpit. The bow OUTER shape is unchanged
# (it still nests). The bow therefore becomes an OPEN shell (not watertight) -- expected.
BOW_HOLLOW = True
BOW_WALL = SKIN                   # ~7 mm real shell (thin for a glassed print)
CAV_LEN = 44.0                    # real inches the storage cavity reaches forward (full
                                  # hollow -- auto-stops where the nose gets too thin)
DOME_SOLE = 0.15                  # cavity floor at this fraction up keel->deck (low = hollow
                                  # more of the floor; leaves only a thin sole over the V)

# Hollow the WEDGES into SEALED buoyancy shells (SKIN walls): subtract an inset cavity
# kept WEDGE_MARGIN clear of the mating wall so the dovetail tongues + bolts stay solid.
WEDGE_HOLLOW = True
WEDGE_MARGIN = 3.0                # design in: keep cavity this far off the mating wall (LEGACY
                                  # global slab -- replaced by local bosses below)
WEDGE_CAV_INSET = 1.5             # design in: leave this much solid at the fore/aft ends
# Only keep solid LOCAL bosses around each dovetail key + bolt; thin SKIN wall elsewhere.
WEDGE_BOSS_MARGIN = 1.6           # design in: solid kept off the mating wall AT a key/bolt
WEDGE_BOSS_HALF = 3.5             # design in: half-length of each boss along x

# Wedge-top trim (REAL inches): lop this much off the top of the wedges (flat cap)
# so the rotated wedges sit lower when nested -> smaller total bundle height for the
# car. Only the WEDGE is shortened; the center keeps full height. 0 = untrimmed.
# Assembled, this steps the outboard aft gunwale down by WEDGE_TOP_TRIM.
WEDGE_TOP_TRIM = 0.0
WATERLINE = 7.0     # real inches above the keel; the dovetail must stay above this

# --- Vertical drop-in dovetail KEYS (replace the fore-aft sliding dovetail) ---
# With USE_VKEYS the mating wall is a PLAIN flat plane; N_KEYS dovetail keys per side
# are then cut/added by boolean (add_vertical_dovetails): a flared socket in the CENTER
# and a matching tongue on the WEDGE. The wedge drops straight DOWN, the keys slide
# into their slots (sockets open at the rim), and the sideways flare (KEY_BACK >
# KEY_MOUTH) locks the wedge from pulling away. Bolts pin them from lifting.
USE_VKEYS = True
N_KEYS = 3
KEY_X = [8.0, 24.0, 40.0]   # key fore-aft stations (design x), 3 per side
KEY_DEPTH = 0.7             # tongue reach inboard past the wall (design in)
KEY_MOUTH = 2.0             # fore-aft width of the key at the wall face (design in)
KEY_BACK = 3.0             # fore-aft width at the flared back (>MOUTH => dovetail)
KEY_STUB = 0.5             # tongue stub reach outboard into the wedge body (design in)

NS = 30             # center outer-skin points (keel -> crossing)
NW = 30             # shared mating-wall contour points (center groove == wedge tongue)
NSO = 50            # wedge outer-skin points (crossing -> sheer)
NTOT_O = NS - 1 + NW  # constant center outer-half vertex count
NTOT_I = 74         # constant center inner-half vertex count

# Bolt holes (final step): above-waterline bolts pin the slid-home joints. Each hole
# is ONE shared cylinder subtracted from BOTH mating pieces, so the holes are coaxial
# and a real bolt passes straight through. All bolts sit high on the mating walls,
# above WATERLINE, in solid material.
BOLT_R = 0.22            # design-in hole radius (~0.2" real bolt clearance)
BOLT_WEDGE_X = list(KEY_X)  # a column of bolts per dovetail key, to pin it from lifting
BOLT_WEDGE_BELOW = [2.5, 7.5]  # z-offsets below sheer: 2 bolts per key -> 2x3x2 = 12
BOLT_WEDGE_IN = 2.5      # cylinder reach inboard of the mating plane (into center)
BOLT_WEDGE_OUT = 2.5     # cylinder reach outboard of the mating plane (into wedge)
BOLT_BOW_Z = [9.0, 13.0, 17.0, 20.0]  # bow<->center bolt heights -> 4 x 2 sides = 8
BOLT_BOW_HALF = 3.0      # cylinder half-length along X about the x=BOW_SPLIT face

# Transom: a solid slab closing the center's stern (the cockpit is otherwise open aft).
TRANSOM_THICK = 1.5 / DESIGN_SCALE   # 1.5" REAL thick (solid enough for an outboard clamp)
# Outboard motor cutout: notch the transom center down to NOTCH_TOP (REAL inches above
# the hull bottom at the transom) = the motor mount height. 15" short shaft -> ~17".
MOTOR_NOTCH = True
NOTCH_TOP = 17.0         # real inches above the keel/hull-bottom (motor clamp height)
NOTCH_WIDTH = 12.0       # real inches wide at the bottom (flat motor-clamp ledge)
NOTCH_FLARE = 2.0        # real inches the notch widens PER SIDE going up -> \___/ trapezoid
NOTCH_RADIUS = 0.75      # real inches: round the bottom corners (no sharp edges)


# ------------------------------------------------------------------
# 2D profile helpers (operate in the y-z section plane, starboard y>=0)
# ------------------------------------------------------------------
def resample(poly, n):
    """Resample a polyline to exactly n points by arclength (endpoints kept)."""
    pts = np.asarray(poly, float)
    if len(pts) == 1:
        return [tuple(pts[0])] * n
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    if total < 1e-9:
        return [tuple(pts[0])] * n
    t = np.linspace(0.0, total, n)
    ys = np.interp(t, cum, pts[:, 0])
    zs = np.interp(t, cum, pts[:, 1])
    return list(zip(ys.tolist(), zs.tolist()))


def cross_z(poly, yc):
    """z where a (y monotonic) profile crosses y=yc; None if it never reaches yc.
    Returns the lowest such crossing (smallest z)."""
    best = None
    for i in range(len(poly) - 1):
        y0, z0 = poly[i]
        y1, z1 = poly[i + 1]
        if (y0 - yc) * (y1 - yc) <= 0 and abs(y1 - y0) > 1e-12:
            t = (yc - y0) / (y1 - y0)
            if 0.0 <= t <= 1.0:
                z = z0 + t * (z1 - z0)
                if best is None or z < best:
                    best = z
    return best


def ycut(x):
    """Half-width of the center/wedge mating plane at station x. Widened by DSTERN
    at the transom, tapering to YC at the bow split -> the center is a slight
    trapezoid (wider stern) so the bow nests inside its cockpit."""
    return YC + DSTERN * max(0.0, 1.0 - x / BOW_SPLIT)


def chamfer_amount(x):
    """0..1 strength of the bow aft-top-corner chamfer: full at the bow split
    (widest, tightest to nest), fading to 0 over CHAMFER_LEN forward."""
    return max(0.0, min(1.0, 1.0 - (x - BOW_SPLIT) / CHAMFER_LEN))


def chamfer_profile(o, cf):
    """Bevel the top outboard corner of a bow half-profile o (keel..sheer): within
    CHAMFER_DZ of the sheer, pull y inboard up to CHAMFER_DY*cf at the sheer. Keeps
    the same point count so the loft stays consistent."""
    if cf <= 0:
        return o
    sz = max(p[1] for p in o)
    dz_zone = CHAMFER_DZ * cf
    out = []
    for (y, z) in o:
        dtop = sz - z
        if dz_zone > 1e-6 and dtop < dz_zone:
            y = y - CHAMFER_DY * cf * (1.0 - dtop / dz_zone)
        out.append((max(0.0, y), z))
    return out


# ------------------------------------------------------------------
# Sliding dovetail contour  (SHARED by center groove and wedge tongue)
# ------------------------------------------------------------------
def dovetail_params(hull, x, zc):
    """Tapered dovetail sizing at station x, or None where the wall is too short.
    Returns (depth, under, z_mb, z_mt): pocket mouth spans [z_mb, z_mt] at y=YC
    and the (taller, undercut) back spans [z_mb-under, z_mt+under] at y=YC-depth."""
    bhw, cz, shw, sz, dr, kz = hull.interp(x)
    yc = ycut(x)
    wall_h = sz - zc
    if wall_h <= DT_WALL_MIN:
        return None
    # Taper on how far the wedge extends outboard: full at the transom, -> 0 as the
    # wedge narrows forward. This makes a genuine tapered sliding dovetail that
    # wedges tight as it slides home at the transom (where the bolt also lands).
    shw0 = hull.interp(0.0)[2]
    fp = max(0.0, min(1.0, (shw - yc) / (shw0 - YC)))
    fw = min(1.0, (wall_h - DT_WALL_MIN) / (DT_WALL_FULL - DT_WALL_MIN))
    f = fp * fw
    depth = DT_DEPTH * f
    under = DT_UNDER * f
    mouth = DT_MOUTH * f
    if depth < 0.06 or mouth < 0.2:
        return None
    z_mt = min(sz - DT_TOP_GAP, sz - 0.3)
    if WEDGE_TOP_TRIM > 0:                       # keep the pocket below the wedge cut
        z_cut = hull.interp(BOW_SPLIT)[3] - WEDGE_TOP_TRIM / DESIGN_SCALE
        z_mt = min(z_mt, z_cut - under - 0.5)
    wl = kz + WATERLINE / DESIGN_SCALE           # keep the pocket above the waterline
    z_mb = max(z_mt - mouth, zc + 0.3, wl)
    if z_mt - z_mb < 0.2:
        return None
    return depth, under, z_mb, z_mt


def mating_wall_contour(hull, x, zc):
    """The shared vertical-wall contour from (YC, zc) up to (YC, sz), carrying the
    dovetail pocket. The CENTER uses it as its OUTBOARD boundary (material inboard
    -> pocket is a groove); each WEDGE uses the IDENTICAL contour as its INBOARD
    boundary (material outboard -> pocket fills as a tongue). Same points both
    sides => exact mate. Returns NW points."""
    sz = hull.interp(x)[3]
    yc = ycut(x)
    if USE_VKEYS:                                # plain flat wall; keys added by boolean
        return resample([(yc, zc), (yc, sz)], NW)
    pts = [(yc, zc)]
    dt = dovetail_params(hull, x, zc)
    if dt is not None:
        depth, under, z_mb, z_mt = dt
        zbb = max(z_mb - under, zc + 0.15)
        ztt = min(z_mt + under, sz - 0.15)
        pts += [
            (yc, z_mb),
            (yc - depth, zbb),     # undercut: back is lower...
            (yc - depth, ztt),     # ...and higher than the mouth -> locks +/-y
            (yc, z_mt),
        ]
    pts.append((yc, sz))
    return resample(pts, NW)


# ------------------------------------------------------------------
# CENTER tub cross-section
# ------------------------------------------------------------------
def center_outer_half(hull, x):
    """Outboard half-profile (keel->top, y>=0): hull skin up to the y=YC crossing,
    then the shared dovetail mating wall. Constant NTOT_O points."""
    o = hull.half_outer(x)
    yc = ycut(x)
    if max(p[0] for p in o) <= yc + EPS:
        return resample(o, NTOT_O)                  # forward: hull < cut, no wall
    zc = cross_z(o, yc)
    skin = resample([p for p in o if p[0] < yc] + [(yc, zc)], NS)  # keel..crossing
    wall = mating_wall_contour(hull, x, zc)         # crossing..sz (groove)
    return skin[:-1] + wall                         # NS-1 + NW = NTOT_O


def thick_floor_inner(hull, x):
    """Inner skin (keel..sheer) with a FLOOR-thick bottom panel (below the chine) and
    SKIN-thick topsides, blended at the chine. Replaces hull.half_inner for the center
    so the cockpit sole is stiff while the sides stay thin for a glassed print.
    (Mirrors h2.half_inner but with a per-region offset.)"""
    bhw, cz, shw, sz, dr, kz = hull.interp(x)
    ihw = hull.inner_hw(x)
    gw_zone_h = 7.0
    gw_zone_bot = sz - gw_zone_h
    dy, dz = shw - bhw, sz - cz
    slen = max(0.001, (dy * dy + dz * dz) ** 0.5)
    nx_s = dz / slen
    nx, nz = np.sin(np.radians(dr)), np.cos(np.radians(dr))
    pts = []
    for i in range(h2.N_BOTTOM + 1):                    # FLOOR-thick V-bottom (the sole)
        f = i / h2.N_BOTTOM
        y, z = f * bhw, kz + f * (cz - kz)
        pts.append((max(0.0, y - FLOOR * nx), z + FLOOR * nz))
    for i in range(1, h2.N_SIDE + 1):                   # SKIN-thick topsides
        f = i / h2.N_SIDE
        yo, zo = bhw + f * (shw - bhw), cz + f * (sz - cz)
        if zo >= gw_zone_bot:
            gf = min(1.0, max(0.0, (zo - gw_zone_bot) / gw_zone_h))
            off = SKIN + gf * (shw - ihw - SKIN)
        else:
            off = SKIN * nx_s
        pts.append((max(0.0, yo - off), zo))
    return pts


def center_inner_half(hull, x):
    """Inboard half-profile (keel->top): the inner skin (thick sole, thin topsides),
    capped at y=YC-WALL, locally stepped to y=YC-RAIL_W behind the dovetail groove so
    the groove has backing material. z-sampled to a constant NTOT_I points."""
    ii = thick_floor_inner(hull, x)
    sz = hull.interp(x)[3]
    yc = ycut(x)
    pz = np.array([p[1] for p in ii])               # z increases keel..sheer
    py = np.array([p[0] for p in ii])

    o = hull.half_outer(x)
    zb = zt = None
    if not USE_VKEYS and max(p[0] for p in o) > yc + EPS:
        dt = dovetail_params(hull, x, cross_z(o, yc))
        if dt is not None:
            _, under, z_mb, z_mt = dt
            zb = z_mb - under - RAIL_MARGIN
            zt = z_mt + under + RAIL_MARGIN

    out = []
    for z in np.linspace(float(pz[0]), sz, NTOT_I):
        yh = float(np.interp(z, pz, py))
        cap = yc - WALL
        if zb is not None and zb <= z <= zt:
            cap = yc - RAIL_W                        # thicken wall behind the groove
        out.append((min(yh, cap), float(z)))
    return out


def center_ring(hull, x):
    """Closed thick-wall ring for the center tub (port+stbd, outer+inner)."""
    oh = center_outer_half(hull, x)                    # keel..top (outboard)
    ih = center_inner_half(hull, x)                    # keel..top (inboard)
    sz = hull.interp(x)[3]

    ring = []
    ring += [(-y, z) for (y, z) in reversed(oh[1:])]   # port outer: top..(near keel)
    ring += [(y, z) for (y, z) in oh]                  # stbd outer: keel..top
    oy, iy = oh[-1][0], ih[-1][0]                      # stbd gunwale top bridge
    for i in range(1, N_GW + 1):
        f = i / (N_GW + 1)
        ring.append((oy + f * (iy - oy), sz))
    ring += [(y, z) for (y, z) in reversed(ih)]        # stbd inner: top..keel
    ring += [(-y, z) for (y, z) in ih[1:]]             # port inner: keel..top
    for i in range(1, N_GW + 1):                       # port gunwale top bridge
        f = i / (N_GW + 1)
        ring.append((-iy + f * (iy - oy), sz))
    return ring


# ------------------------------------------------------------------
# WEDGE cross-section (starboard; mirror for port)
# ------------------------------------------------------------------
def wedge_section(hull, x):
    """Closed solid wedge polygon outboard of y=YC, or None if no wedge here. Its
    inboard edge is the SHARED dovetail contour (reversed) -> a tongue that fills
    the center groove."""
    o = hull.half_outer(x)
    yc = ycut(x)
    if max(p[0] for p in o) <= yc + 0.05:
        return None
    zc = cross_z(o, yc)
    outer = resample([(yc, zc)] + [p for p in o if p[0] > yc], NSO)  # crossing..sheer
    wall = mating_wall_contour(hull, x, zc)             # shared with center
    # up the outer skin, across the gunwale top, down the mating wall (tongue):
    return list(outer) + list(reversed(wall))[:-1]      # NSO + NW-1, closes to start


# ------------------------------------------------------------------
# BOW cross-section (simplified sealed solid with a flat deck)
# ------------------------------------------------------------------
def bow_half_outer(hull, x, rail_f):
    """Like hull.half_outer but with the spray-rail bulge scaled by rail_f (0..1), so
    the bow can fade the rail out forward and the rounded nose doesn't bulb."""
    bhw, cz, shw, sz, dr, kz = hull.interp(x)
    pts = []
    for i in range(h2.N_BOTTOM + 1):
        f = i / h2.N_BOTTOM
        pts.append((f * bhw, kz + f * (cz - kz)))
    for i in range(1, h2.N_SIDE + 1):
        f = i / h2.N_SIDE
        yl = bhw + f * (shw - bhw)
        zv = cz + f * (sz - cz)
        bulge = rail_f * h2.SPRAY_RAIL_OUTWARD * np.exp(
            -0.5 * ((f - h2.SPRAY_RAIL_HEIGHT_FRAC) / 0.2) ** 2)
        pts.append((yl + bulge, zv))
    return pts


def bow_section(hull, x):
    rail_f = min(1.0, max(0.0, (LOA - x) / BOW_RAIL_FADE))     # full rail; fade near stem
    o = resample(bow_half_outer(hull, x, rail_f), NP)          # keel..stbd sheer
    # Gently convex plan-view sheer: scale each section to a (chord + sine bulge)
    # target half-width so the top-down bow outline bulges out slightly instead of
    # running hollow. 0 at the split and the stem -> still matches the center & tip.
    t = (x - BOW_SPLIT) / (LOA - BOW_SPLIT)
    sh0, sh1 = hull.interp(BOW_SPLIT)[2], hull.interp(LOA)[2]
    target = sh0 * (1 - t) + sh1 * t + BOW_CONVEX * np.sin(np.pi * t)
    cur = max(p[0] for p in o)
    if cur > 0.1:
        sc = target / cur
        o = [(y * sc, z) for (y, z) in o]
    o = chamfer_profile(o, chamfer_amount(x))   # bevel aft-top corners to clear rail
    shw, sz = o[-1]                              # stbd sheer (deck edge) of this section
    # Crowned deck: arch from the stbd sheer over the centerline to the port sheer.
    # camber tapers to 0 at the split and the stem (sin envelope) so it blends cleanly.
    camber = BOW_CAMBER * np.sin(np.pi * t)
    deck = [(shw - 2.0 * shw * (i / (N_DECK + 1)),
             sz + camber * np.sin(np.pi * (i / (N_DECK + 1))))
            for i in range(1, N_DECK + 1)]       # interior deck-arc points (port<-stbd)
    right = list(o)                              # keel..stbd sheer
    left = [(-y, z) for (y, z) in reversed(o)]   # port sheer..keel
    return right + deck + left[:-1]              # hull V + domed deck -> clean round bow


# ------------------------------------------------------------------
# Generic loft of equal-length closed sections + end caps
# ------------------------------------------------------------------
def loft(xs, sections):
    """sections: list of equal-length closed (y,z) polygons at each x in xs.
    Returns (verts, faces) for a closed manifold (sides + 2 end caps)."""
    n = len(sections[0])
    assert all(len(s) == n for s in sections), "section vertex count must be constant"

    V = []
    for x, sec in zip(xs, sections):
        for (y, z) in sec:
            V.append((x, y, z))

    F = []
    for i in range(len(xs) - 1):
        base0, base1 = i * n, (i + 1) * n
        for j in range(n):
            jn = (j + 1) % n
            a, b = base0 + j, base0 + jn
            c, d = base1 + jn, base1 + j
            F.append([a, c, b])
            F.append([a, d, c])

    start_idx = list(range(0, n))
    end_idx = list(range((len(xs) - 1) * n, len(xs) * n))
    F += ear_clip(start_idx, V, flip=True)
    F += ear_clip(end_idx, V, flip=False)
    return V, F


def loft_apex(xs, sections, apex):
    """Like loft() but the FORWARD end terminates in a single apex vertex via a triangle
    fan (not an end cap) -- for a clean, provably non-self-intersecting nose tip. The aft
    end is ear-clip capped as usual."""
    n = len(sections[0])
    assert all(len(s) == n for s in sections), "section vertex count must be constant"
    V = []
    for x, sec in zip(xs, sections):
        for (y, z) in sec:
            V.append((x, y, z))
    F = []
    for i in range(len(xs) - 1):
        base0, base1 = i * n, (i + 1) * n
        for j in range(n):
            jn = (j + 1) % n
            a, b = base0 + j, base0 + jn
            c, d = base1 + jn, base1 + j
            F.append([a, c, b])
            F.append([a, d, c])
    F += ear_clip(list(range(0, n)), V, flip=True)        # aft cap
    ai = len(V); V.append(tuple(apex))                    # stem apex vertex
    last = (len(xs) - 1) * n
    for j in range(n):                                    # fan last ring -> apex
        jn = (j + 1) % n
        F.append([last + jn, last + j, ai])
    return V, F


# ------------------------------------------------------------------
# Piece builders
# ------------------------------------------------------------------
def build_center(hull):
    xs = np.linspace(0.0, BOW_SPLIT, N_STN_AFT)
    sections = [center_ring(hull, x) for x in xs]
    return loft(xs, sections)


def build_wedge(hull, side=+1):
    """side=+1 starboard, -1 port."""
    xs_all = np.linspace(0.0, BOW_SPLIT, N_STN_AFT)
    xs, sections = [], []
    for x in xs_all:
        sec = wedge_section(hull, x)
        if sec is None:
            continue
        if side < 0:
            sec = [(-y, z) for (y, z) in sec]
        xs.append(x)
        sections.append(sec)
    # add a near-vanishing closing station just past the last real one
    return loft(np.array(xs), sections)


def build_wedge_cavity(hull, side=+1):
    """Closed inset solid for hollowing a wedge into a SEALED shell: each section is the
    wedge_section shrunk SKIN toward its centroid, then its inboard edge pulled out to
    WEDGE_MARGIN off the mating wall so the dovetail tongues + bolts stay solid. Capped
    fore/aft (WEDGE_CAV_INSET) so the shell is fully enclosed. Returns a mesh or None."""
    xs, sections = [], []
    for x in np.linspace(0.0, BOW_SPLIT, N_STN_AFT):
        if x < WEDGE_CAV_INSET or x > BOW_SPLIT - 1.0:
            continue
        sec = wedge_section(hull, x)
        if sec is None:
            continue
        yc = ycut(x)
        cy = sum(p[0] for p in sec) / len(sec)
        cz = sum(p[1] for p in sec) / len(sec)
        inset = []
        for (y, z) in sec:
            ddy, ddz = cy - y, cz - z
            d = (ddy * ddy + ddz * ddz) ** 0.5
            if d > 1e-6:
                y, z = y + ddy / d * SKIN, z + ddz / d * SKIN
            # thin SKIN wall on the mating side, except a local boss at each key/bolt station
            near_key = any(abs(x - kx) < WEDGE_BOSS_HALF for kx in KEY_X)
            margin = WEDGE_BOSS_MARGIN if near_key else SKIN
            inset.append((max(y, yc + margin), z))
        ys = [p[0] for p in inset]
        zsv = [p[1] for p in inset]
        if (max(ys) - min(ys)) < 1.2 or (max(zsv) - min(zsv)) < 1.2:
            continue                                       # too thin -> leave solid here
        if side < 0:
            inset = [(-y, z) for (y, z) in inset]
        xs.append(x)
        sections.append(inset)
    if len(xs) < 3:
        return None
    return to_trimesh(loft(np.array(xs), sections))


def build_bow(hull):
    # Main body lofts to x_nose; then a rounded nose rounds the last NOSE_ROUND inches.
    x_nose = LOA - NOSE_ROUND
    xs = list(np.linspace(BOW_SPLIT, x_nose, N_STN_BOW))
    sections = [bow_section(hull, x) for x in xs]
    base = sections[-1]                                  # full section at x_nose
    zc = 0.5 * (min(z for _, z in base) + max(z for _, z in base))  # nose center height
    # Homothetic shrink of the base section toward (0, zc); a small final ring is ear-clip
    # capped -- that handles the section's concavity (flat deck + V) cleanly, whereas a
    # triangle-fan-to-apex overlaps on a non-convex section.
    for i in range(1, NOSE_RINGS + 1):
        f = i / NOSE_RINGS
        sc = max(NOSE_SC_MIN, (1.0 - f) ** NOSE_POW)
        xs.append(x_nose + NOSE_ROUND * f)
        sections.append([(y * sc, zc + (z - zc) * sc) for (y, z) in base])
    return loft(np.array(xs), sections)


def _bow_profile_hw(hull, x):
    """The bow's stbd outer half-width vs height at station x (z increasing): replicates
    bow_section's rail-fade + convex scaling. Returns (zs, ys) arrays."""
    rail_f = min(1.0, max(0.0, (LOA - x) / BOW_RAIL_FADE))
    o = resample(bow_half_outer(hull, x, rail_f), NP)
    t = (x - BOW_SPLIT) / (LOA - BOW_SPLIT)
    sh0, sh1 = hull.interp(BOW_SPLIT)[2], hull.interp(LOA)[2]
    target = sh0 * (1 - t) + sh1 * t + BOW_CONVEX * np.sin(np.pi * t)
    cur = max(p[0] for p in o)
    if cur > 0.1:
        o = [(y * target / cur, z) for (y, z) in o]
    return np.array([p[1] for p in o]), np.array([p[0] for p in o])


def _arch(hw, z_sole, z_peak, n_top=12):
    """Closed arch section (y-z): flat sole at z_sole, vertical sides, semi-elliptical
    top peaking at z_peak. Constant point count (n_top + 3)."""
    z_spring = z_sole + 0.4 * (z_peak - z_sole)
    pts = [(hw, z_sole)]
    for k in range(n_top + 1):
        th = np.pi * k / n_top
        pts.append((hw * np.cos(th), z_spring + (z_peak - z_spring) * np.sin(th)))
    pts.append((-hw, z_sole))
    return pts


def build_bow_cavity(hull):
    """Solid for hollowing the bow into a uniform ~BOW_WALL shell that follows the FULL
    hull section -- so the V-bottom FLOOR gets hollowed too, not left solid. Each
    bow_section is inset BOW_WALL toward its centroid; lofted from ~1" AFT of the split
    (subtracting it opens the aft face for storage access) forward until the nose gets too
    thin to hollow, then tapered shut. Closed solid for the boolean."""
    x_nose = LOA - NOSE_ROUND
    xs, sections = [], []
    for x in np.linspace(BOW_SPLIT, x_nose, N_STN_BOW + 10):
        sec = bow_section(hull, x)
        cy = sum(p[0] for p in sec) / len(sec)
        cz = sum(p[1] for p in sec) / len(sec)
        inset, ok = [], True
        for (y, z) in sec:
            ddy, ddz = cy - y, cz - z
            d = (ddy * ddy + ddz * ddz) ** 0.5
            if d <= BOW_WALL + 0.1:                       # closer to centroid than the wall -> too thin
                ok = False
                break
            inset.append((y + ddy / d * BOW_WALL, z + ddz / d * BOW_WALL))
        if not ok:
            break
        ys = [p[0] for p in inset]
        zsv = [p[1] for p in inset]
        if (max(ys) - min(ys)) < 1.5 or (max(zsv) - min(zsv)) < 1.5:
            break
        xs.append(x)
        sections.append(inset)
    if len(xs) < 3:
        return None
    xs = [BOW_SPLIT - 1.2] + xs                            # aft extension -> opens the aft face
    sections = [sections[0]] + sections
    last = sections[-1]                                   # forward taper to close cleanly
    lcy = sum(p[0] for p in last) / len(last)
    lcz = sum(p[1] for p in last) / len(last)
    for f, dx in ((0.45, 1.2), (0.12, 2.4)):
        xs.append(xs[-1] + dx)
        sections.append([(lcy + (y - lcy) * f, lcz + (z - lcz) * f) for (y, z) in last])
    return to_trimesh(loft(np.array(xs), sections))


# ------------------------------------------------------------------
# Mesh assembly / export
# ------------------------------------------------------------------
def to_trimesh(vf):
    import trimesh
    V, F = vf
    m = trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F, int),
                        process=True)
    trimesh.repair.fix_normals(m)
    return m


def _nonmanifold_edge_count(m):
    """Number of edges shared by other than exactly 2 faces."""
    e = m.edges_sorted
    o = np.lexsort(e.T[::-1])
    es = e[o]
    d = np.any(es[1:] != es[:-1], axis=1)
    st = np.concatenate([[0], np.where(d)[0] + 1, [len(es)]])
    return int(np.sum(np.diff(st) != 2))


def make_manifold(m):
    """Guarantee the EXPORTED STL is a proper manifold. The boolean chain can leave
    near-coincident verts that only merge into a non-manifold edge once STL truncates
    them to float32 on reload -- so we simulate that float32 round-trip, and if it goes
    non-manifold, repair with pymeshfix (geometry/volume preserved). No-op (returns the
    original) when the piece survives the round-trip clean."""
    import os
    import trimesh
    import pymeshfix

    def _pmf(mesh):                                      # one pymeshfix pass, C-stderr silenced
        v = np.ascontiguousarray(mesh.vertices, np.float64)
        f = np.ascontiguousarray(mesh.faces, np.int32)
        saved = os.dup(2); nul = os.open(os.devnull, os.O_WRONLY)
        os.dup2(nul, 2); os.close(nul)
        try:
            vc, fc = pymeshfix.clean_from_arrays(
                v, f, joincomp=True, remove_smallest_components=False)
        finally:
            os.dup2(saved, 2); os.close(saved)
        return vc, fc, len(mesh.faces) - len(fc)

    # STL truncates to float32 on reload, which can merge near-coincident verts into a
    # non-manifold edge -- work at that precision so what we verify matches the export.
    m32 = trimesh.Trimesh(m.vertices.astype(np.float32).astype(np.float64),
                          m.faces, process=True)
    trimesh.repair.fix_normals(m32)
    _, _, resid = _pmf(m32)
    if m32.is_watertight and _nonmanifold_edge_count(m32) == 0 and resid == 0:
        return m32                                       # already a clean manifold

    # Fix a genuine non-manifold EDGE (the printability-critical defect) with one
    # pymeshfix pass; keep it only if it preserved the solid (else pymeshfix would hack
    # out real geometry -- keep the edge-manifold original, which stays watertight/slicer
    # -safe and whose print chunks are re-derived by boolean anyway).
    if not (m32.is_watertight and _nonmanifold_edge_count(m32) == 0):
        v0 = abs(m32.volume)
        vc, fc, _ = _pmf(m32)
        r = trimesh.Trimesh(vc, fc, process=True)
        trimesh.repair.fix_normals(r)
        if r.is_watertight and _nonmanifold_edge_count(r) == 0 and \
                (v0 <= 0 or abs(abs(r.volume) - v0) / v0 <= 0.03):
            return r
    return m32


def trim_wedge_mesh(hull, m):
    """Lop WEDGE_TOP_TRIM (real inches) off a wedge's top with a flat cap so it sits
    lower when nested. Cuts at a constant z (relative to the max wedge sheer); the
    center is never trimmed. Returns a watertight closed mesh."""
    if WEDGE_TOP_TRIM <= 0:
        return m
    import trimesh
    z_cut = hull.interp(BOW_SPLIT)[3] - WEDGE_TOP_TRIM / DESIGN_SCALE
    lo, hi = m.bounds[0] - 5.0, m.bounds[1] + 5.0
    ext = [hi[0] - lo[0], hi[1] - lo[1], z_cut - lo[2]]
    T = np.eye(4)
    T[:3, 3] = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + z_cut) / 2]
    box = trimesh.creation.box(extents=ext, transform=T)   # everything below z_cut
    cut = m.intersection(box)                              # manifold3d boolean (no scipy)
    trimesh.repair.fix_normals(cut)
    return cut


def _bolt_cyl(p0, p1, r=BOLT_R):
    """A closed cylinder from p0 to p1 (design units) used as a boolean drill bit."""
    import trimesh
    return trimesh.creation.cylinder(
        radius=r, segment=[np.array(p0, float), np.array(p1, float)], sections=24)


def _prism(poly_xy, z0, z1):
    """Closed watertight prism: a 2D polygon (list of (x,y)) extruded in z [z0,z1]."""
    import trimesh
    n = len(poly_xy)
    V = [(x, y, z0) for (x, y) in poly_xy] + [(x, y, z1) for (x, y) in poly_xy]
    F = []
    for i in range(n):                              # side walls
        j = (i + 1) % n
        F += [[i, j, n + j], [i, n + j, n + i]]
    for i in range(1, n - 1):                       # bottom + top caps (fan)
        F += [[0, i + 1, i], [n, n + i, n + i + 1]]
    m = trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F, int), process=True)
    trimesh.repair.fix_normals(m)
    return m


def _key_prism(hull, xk, s):
    """The dovetail KEY for station xk, side s (+1 stbd / -1 port). Same object is the
    tongue (added to the wedge) and the cutter for the socket (subtracted from center).
    Vertical (extruded in z) so the wedge drops straight down onto it; the fore-aft
    flare KEY_BACK>KEY_MOUTH locks pull-apart. Socket open at the rim (z1=sz)."""
    yc = ycut(xk)
    kz, sz = hull.interp(xk)[5], hull.interp(xk)[3]
    z0 = kz + WATERLINE / DESIGN_SCALE + 1.0        # above the waterline
    z1 = sz                                         # up to the rim -> open at top
    M, B, D, T = KEY_MOUTH / 2, KEY_BACK / 2, KEY_DEPTH, KEY_STUB
    poly = [(xk - M, s * (yc + T)), (xk + M, s * (yc + T)),   # stub out into the wedge
            (xk + M, s * yc), (xk + B, s * (yc - D)),         # mouth -> flared back
            (xk - B, s * (yc - D)), (xk - M, s * yc)]
    return _prism(poly, z0, z1)


def add_vertical_dovetails(hull, pieces):
    """Cut a flared socket in the center and add the matching tongue to each wedge, at
    every KEY_X / side. Center and wedge use the SAME prism -> they mate exactly. A
    backing boss is unioned into the center first so the socket has surrounding
    material. Returns the updated pieces dict. Keeps every piece watertight."""
    import trimesh
    out = dict(pieces)
    wedge_of = {+1: "wedge_stbd", -1: "wedge_port"}
    for xk in KEY_X:
        yc = ycut(xk)
        kz, sz = hull.interp(xk)[5], hull.interp(xk)[3]
        z0 = kz + WATERLINE / DESIGN_SCALE + 1.0
        for s in (+1, -1):
            key = _key_prism(hull, xk, s)
            # backing boss in the center wall around the socket
            yb0, yb1 = s * yc, s * (yc - (KEY_DEPTH + 0.4))
            ext = [KEY_BACK + 1.2, abs(yb1 - yb0), (sz - (z0 - 0.3))]
            T = np.eye(4)
            T[:3, 3] = [xk, 0.5 * (yb0 + yb1), 0.5 * ((z0 - 0.3) + sz)]
            boss = trimesh.creation.box(extents=ext, transform=T)
            c = out["center"].union(boss).difference(key)
            trimesh.repair.fix_normals(c)
            out["center"] = c
            w = out[wedge_of[s]].union(key)
            trimesh.repair.fix_normals(w)
            out[wedge_of[s]] = w
    return out


def add_bolt_holes(hull, pieces):
    """Drill the above-waterline bolts. Each bolt is ONE cylinder subtracted from
    BOTH mating pieces, so the holes are coaxial and a bolt passes straight through.
    Wedge<->center: axis Y, high in the gunwale-rail band. Bow<->center: axis X,
    around the upper perimeter of the x=BOW_SPLIT face. Returns (pieces, records)."""
    import trimesh
    jobs = {name: [] for name in pieces}        # piece name -> list of drill cylinders
    records = []                                # (kind, x, y, z) design units, for report/plot

    # --- wedge <-> center: 2 bolts per dovetail key, axis along Y ---
    for side, wname in ((+1, "wedge_stbd"), (-1, "wedge_port")):
        for x in BOLT_WEDGE_X:
            yc = ycut(x)
            for below in BOLT_WEDGE_BELOW:
                z = hull.interp(x)[3] - below                # below the sheer, in key band
                cyl = _bolt_cyl([x, side * (yc - BOLT_WEDGE_IN), z],
                                [x, side * (yc + BOLT_WEDGE_OUT), z])
                jobs["center"].append(cyl)
                jobs[wname].append(cyl)
                records.append(("wedge", x, side * yc, z))

    # --- bow <-> center, 4 around the upper x=BOW_SPLIT face, axis along X ---
    oo, ii = hull.half_outer(BOW_SPLIT), hull.half_inner(BOW_SPLIT)
    ozs, oys = [p[1] for p in oo], [p[0] for p in oo]
    izs, iys = [p[1] for p in ii], [p[0] for p in ii]
    for z in BOLT_BOW_Z:
        yo = float(np.interp(z, ozs, oys))
        yi = float(np.interp(z, izs, iys))
        ym = 0.5 * (yo + yi)                                # mid-wall, where both pieces share material
        for side in (+1, -1):
            cyl = _bolt_cyl([BOW_SPLIT - BOLT_BOW_HALF, side * ym, z],
                            [BOW_SPLIT + BOLT_BOW_HALF, side * ym, z])
            jobs["center"].append(cyl)
            jobs["bow"].append(cyl)
            records.append(("bow", BOW_SPLIT, side * ym, z))

    out = {}
    for name, m in pieces.items():
        for cyl in jobs[name]:
            m = m.difference(cyl)                           # manifold3d boolean
        trimesh.repair.fix_normals(m)
        out[name] = m
    return out, records


def build_transom(hull):
    """Solid transom slab closing the center's stern: the center's x=0 outer section
    (V-bottom + vertical sides + flat top at the sheer) extruded aft to TRANSOM_THICK.
    Union this into the center so the cockpit is closed at the back."""
    import trimesh
    oh = center_outer_half(hull, 0.0)                       # keel..gunwale, stbd (y>=0)
    outline = list(oh) + [(-y, z) for (y, z) in reversed(oh)][:-1]   # full closed section
    n = len(outline)
    V = [(0.0, y, z) for (y, z) in outline] + [(TRANSOM_THICK, y, z) for (y, z) in outline]
    F = []
    for i in range(n):
        j = (i + 1) % n
        F.append([i, n + j, j]); F.append([i, n + i, n + j])
    F += ear_clip(list(range(0, n)), V, flip=False)         # x=0 face
    F += ear_clip(list(range(n, 2 * n)), V, flip=True)      # x=TRANSOM_THICK face
    m = trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F, int), process=True)
    trimesh.repair.fix_normals(m)
    return m


def build_notch_box(hull):
    """Rounded-trapezoid ( \\___/ ) outboard motor cutout, extruded through the transom:
    flat NOTCH_WIDTH clamp ledge at NOTCH_TOP above the keel, sides flaring NOTCH_FLARE
    per side going up, with NOTCH_RADIUS-rounded bottom corners."""
    import trimesh
    kz = hull.interp(0.0)[5]
    sz = hull.interp(0.0)[3]
    z_notch = kz + NOTCH_TOP / DESIGN_SCALE
    wb = (NOTCH_WIDTH / 2.0) / DESIGN_SCALE
    flare = NOTCH_FLARE / DESIGN_SCALE
    r = NOTCH_RADIUS / DESIGN_SCALE
    z_top = sz + 4.0
    slope = flare / max(0.1, sz - z_notch)
    hwz = lambda z: wb + (z - z_notch) * slope          # notch half-width at height z

    def fillet(p0, p1, p2, n=7):                          # arc rounding the corner at p1
        p0, p1, p2 = (np.array(p, float) for p in (p0, p1, p2))
        v1 = p0 - p1; v2 = p2 - p1
        v1 /= np.linalg.norm(v1); v2 /= np.linalg.norm(v2)
        ang = np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0))
        d = r / np.tan(ang / 2.0)
        bis = v1 + v2; bis /= np.linalg.norm(bis)
        cen = p1 + bis * (r / np.sin(ang / 2.0))
        t1, t2 = p1 + v1 * d, p1 + v2 * d
        a1 = np.arctan2(t1[1] - cen[1], t1[0] - cen[0])
        a2 = np.arctan2(t2[1] - cen[1], t2[0] - cen[0])
        while a2 - a1 > np.pi: a2 -= 2 * np.pi
        while a1 - a2 > np.pi: a2 += 2 * np.pi
        return [(cen[0] + r * np.cos(a), cen[1] + r * np.sin(a)) for a in np.linspace(a1, a2, n)]

    A = (-hwz(z_top), z_top); B = (-wb, z_notch); C = (wb, z_notch); D = (hwz(z_top), z_top)
    poly = [A] + fillet(A, B, C) + fillet(B, C, D) + [D]   # rounded-trapezoid outline (y-z)

    x0, x1 = -0.5, TRANSOM_THICK + 0.5                    # extrude through the transom
    n = len(poly)
    V = [(x0, y, z) for (y, z) in poly] + [(x1, y, z) for (y, z) in poly]
    F = []
    for i in range(n):
        j = (i + 1) % n
        F.append([i, n + j, j]); F.append([i, n + i, n + j])
    F += ear_clip(list(range(0, n)), V, flip=False)
    F += ear_clip(list(range(n, 2 * n)), V, flip=True)
    m = trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F, int), process=True)
    trimesh.repair.fix_normals(m)
    return m


def render_bolts(hull, bolts, out_path):
    """Show every bolt's position relative to the joint and the waterline."""
    import matplotlib.pyplot as plt
    s = DESIGN_SCALE
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(17, 6.5))

    # Panel 1: stbd mating wall, side elevation (x-z) -- the 3 wedge<->center bolts.
    xs = np.linspace(0, BOW_SPLIT, 140)
    sz = [hull.interp(x)[3] for x in xs]
    zc = []
    for x in xs:
        c = cross_z(hull.half_outer(x), ycut(x))
        zc.append(c if c is not None else hull.interp(x)[3])
    ax1.fill_between([s * x for x in xs], [s * z for z in zc], [s * z for z in sz],
                     color="#cfe0f5", label="stbd mating wall")
    ax1.plot([s * x for x in xs],
             [s * (hull.interp(x)[5] + WATERLINE / DESIGN_SCALE) for x in xs],
             "b--", lw=1.2, label="waterline")
    for (kind, x, y, z) in bolts:
        if kind == "wedge" and y > 0:
            ax1.plot(s * x, s * z, "o", color="#c0392b", ms=11, mfc="none", mew=2)
    ax1.plot([], [], "o", color="#c0392b", mfc="none", mew=2, label="bolt")
    ax1.set_title("Wedge <-> center bolts  (stbd mating wall, side view)",
                  fontsize=11, fontweight="bold")
    ax1.set_xlabel("x from transom (real in)"); ax1.set_ylabel("height z (real in)")
    ax1.legend(fontsize=8, loc="lower left"); ax1.grid(alpha=0.2); ax1.set_aspect("equal")

    # Panel 2: section at the split (y-z) -- the 4 bow<->center bolts.
    o = hull.half_outer(BOW_SPLIT)
    oy, oz = [p[0] for p in o], [p[1] for p in o]
    ax2.plot([s * v for v in oy], [s * v for v in oz], "-", color="#5B8FF9", lw=2)
    ax2.plot([-s * v for v in oy], [s * v for v in oz], "-", color="#5B8FF9", lw=2,
             label="hull section @ split")
    ax2.axhline(s * (hull.interp(BOW_SPLIT)[5] + WATERLINE / DESIGN_SCALE),
                color="b", ls="--", lw=1.2, label="waterline")
    for (kind, x, y, z) in bolts:
        if kind == "bow":
            ax2.plot(s * y, s * z, "o", color="#c0392b", ms=11, mfc="none", mew=2)
    ax2.plot([], [], "o", color="#c0392b", mfc="none", mew=2, label="bolt")
    ax2.set_title("Bow <-> center bolts  (section at split x=60)",
                  fontsize=11, fontweight="bold")
    ax2.set_xlabel("beam y (real in)"); ax2.set_ylabel("height z (real in)")
    ax2.legend(fontsize=8, loc="lower center"); ax2.grid(alpha=0.2); ax2.set_aspect("equal")

    fig.suptitle("Above-waterline bolt holes (every bolt above the dashed waterline)",
                 fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(str(out_path), dpi=140, bbox_inches="tight")
    plt.close()


def report(name, m):
    d = m.bounds[1] - m.bounds[0]
    print(f"  {name:12} verts={len(m.vertices):5d} faces={len(m.faces):5d} "
          f"watertight={str(m.is_watertight):5} "
          f"size={d[0]:5.1f} x {d[1]:5.1f} x {d[2]:5.1f} in  vol={m.volume/1728:6.2f} ft^3")
    return m.is_watertight


def glass_zones(m, do_interior):
    """Split a piece's surface area (real in^2) into exterior bottom / topside / deck
    and interior, by face normal + height. Interior only if do_interior (sealed wedges
    aren't glassed inside). Rough but lets the schedule be zoned."""
    n, c, a = m.face_normals, m.triangles_center, m.area_faces
    outward = np.einsum('ij,ij->i', n, c - m.centroid) > 0               # exterior faces
    zmin, zmax = m.bounds[0][2], m.bounds[1][2]
    h = max(1e-6, zmax - zmin)
    deck = outward & (n[:, 2] > 0.5) & (c[:, 2] > zmin + 0.6 * h)
    bottom = outward & ~deck & (c[:, 2] < zmin + 0.25 * h)
    topside = outward & ~deck & ~bottom
    interior = (~outward) if do_interior else np.zeros(len(a), bool)
    s = lambda mask: float(a[mask].sum())
    return s(bottom), s(topside), s(deck), s(interior)


def estimate_weight(reals):
    """Rough built weight of the full-size ASA-printed + fiberglassed boat (REAL meshes).
    Print mass = SKIN (area*perimeter, ~solid) + INFILL (rest of volume * INFILL).
    Glass mass = zoned area * the per-zone schedule areal weights."""
    IN3_TO_CM3, IN2_TO_M2 = 16.387064, 0.00064516
    perim_in = PERIM_SHELL / 25.4
    print(f"\nWeight estimate (full size):  [ASA {ASA_DENSITY} g/cm^3, skin {PERIM_SHELL:.1f} mm, "
          f"infill {INFILL:.0%} | glass kg/m^2: bot {GLASS_BOTTOM} side {GLASS_TOPSIDE} "
          f"deck {GLASS_DECK} in {GLASS_INSIDE}]")
    print(f"  {'piece':12} {'skin':>6} {'infill':>7} {'glass':>6} {'total kg':>9}")
    tot = 0.0
    for name, m in reals.items():
        perim_vol = min(m.volume, m.area * perim_in)
        skin = perim_vol * IN3_TO_CM3 * ASA_DENSITY / 1000.0
        infl = max(0.0, m.volume - perim_vol) * IN3_TO_CM3 * ASA_DENSITY * INFILL / 1000.0
        b, t, d, i = (z * IN2_TO_M2 for z in glass_zones(m, GLASS_INTERIOR_OF.get(name, True)))
        glass = b * GLASS_BOTTOM + t * GLASS_TOPSIDE + d * GLASS_DECK + i * GLASS_INSIDE
        pt = skin + infl + glass
        tot += pt
        print(f"  {name:12} {skin:6.1f} {infl:7.1f} {glass:6.1f} {pt:9.1f}")
    print(f"  {'TOTAL':12} {'':6} {'':7} {'':6} {tot:9.1f}  ({tot*2.2046:.0f} lb)")
    return tot


# ------------------------------------------------------------------
# Previews
# ------------------------------------------------------------------
PIECE_COLORS = {
    "center": "#5B8FF9",
    "wedge_stbd": "#F6BD16",
    "wedge_port": "#E8684A",
    "bow": "#6DC8EC",
}


def _add_mesh(ax, m, color, dy=0.0, dx=0.0, alpha=0.75):
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    polys = []
    for f in m.faces[::2]:
        tri = [(m.vertices[k][0] + dx, m.vertices[k][1] + dy, m.vertices[k][2])
               for k in f]
        polys.append(tri)
    ax.add_collection3d(Poly3DCollection(polys, alpha=alpha, facecolor=color,
                                         edgecolor="#333", linewidth=0.05))


def render(pieces, out_path):
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(22, 13))
    # offsets for the exploded views
    explode = {"center": (0, 0), "wedge_stbd": (0, 16),
               "wedge_port": (0, -16), "bow": (14, 0)}

    layouts = [
        ("Assembled - Stbd Quarter", 22, -50, False),
        ("Assembled - Top Down", 88, -90, False),
        ("Assembled - Transom", 6, 180, False),
        ("Exploded - Stbd Quarter", 24, -55, True),
        ("Exploded - Top Down", 88, -90, True),
        ("Exploded - Transom", 8, 180, True),
    ]
    for idx, (title, el, az, exp) in enumerate(layouts, 1):
        ax = fig.add_subplot(2, 3, idx, projection="3d")
        for name, m in pieces.items():
            dx, dy = explode[name] if exp else (0, 0)
            _add_mesh(ax, m, PIECE_COLORS[name], dy=dy, dx=dx)
        ax.set_xlim(-6, 124)
        ax.set_ylim(-52, 52)
        ax.set_zlim(-6, 30)
        ax.view_init(elev=el, azim=az)
        ax.set_box_aspect([3.4, 2.8, 1])
        ax.set_title(title, fontsize=11, fontweight="bold")
        for pane in (ax.xaxis, ax.yaxis, ax.zaxis):
            pane.pane.fill = False

    fig.suptitle("Rev-3 Transportable Split  -  42\" center barge + 2 wedge pods + bow",
                 fontsize=15, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(str(out_path), dpi=140, bbox_inches="tight")
    plt.close()


def render_dovetail_detail(hull, pieces, out_path):
    """Two-panel dovetail check: (a) 2D y-z overlay of the center groove contour
    and the wedge tongue contour at the transom (they must coincide); (b) 3D zoom
    on the starboard joint near the transom."""
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(18, 8))

    # (a) 2D zoom on the dovetail: groove vs tongue at the transom (must coincide),
    #     plus a mid station to show the fore-aft taper.
    ax = fig.add_subplot(1, 2, 1)
    ax.set_aspect("equal")
    for x0, col, lab in ((0.0, "#11A579", "x=0 (transom, full)"),
                         (48.0, "#7B61FF", "x=48 (tapered)")):
        zc = cross_z(hull.half_outer(x0), YC)
        wall = mating_wall_contour(hull, x0, zc)        # center groove contour
        tongue = list(reversed(wall))                   # wedge tongue contour
        ax.plot([p[0] for p in wall], [p[1] for p in wall], color=col, lw=3.0,
                label=f"groove {lab}")
        ax.plot([p[0] for p in tongue], [p[1] for p in tongue], color="#E8684A",
                lw=1.3, ls="--")
    ax.axvline(YC, color="#999", lw=0.6, ls="--")
    ax.axvline(YC - WALL, color="#bbb", lw=0.5, ls=":")
    ax.axvline(YC - RAIL_W, color="#bbb", lw=0.5, ls=":")
    ax.set_xlim(YC - RAIL_W - 0.6, YC + 0.6)
    sz0 = hull.interp(0.0)[3]
    ax.set_ylim(sz0 - 7, sz0 + 0.5)
    ax.set_xlabel("beam y (in)   [mating plane y=21 dashed; rail at 19.0]")
    ax.set_ylabel("height z (in)")
    ax.set_title("Dovetail y-z: groove (solid) vs tongue (red dashed) coincide",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(True, alpha=0.2)

    # (b) 3D zoom on the starboard joint near the transom
    ax3 = fig.add_subplot(1, 2, 2, projection="3d")
    _add_mesh(ax3, pieces["center"], PIECE_COLORS["center"], alpha=0.9)
    _add_mesh(ax3, pieces["wedge_stbd"], PIECE_COLORS["wedge_stbd"], alpha=0.45)
    ax3.set_xlim(0, 10)
    ax3.set_ylim(16, 36)
    ax3.set_zlim(13, 27)
    ax3.view_init(elev=16, azim=-68)
    ax3.set_box_aspect([1.0, 2.0, 1])
    ax3.set_title("Stbd dovetail joint (transom end)", fontsize=11, fontweight="bold")
    for pane in (ax3.xaxis, ax3.yaxis, ax3.zaxis):
        pane.pane.fill = False

    fig.suptitle("Phase-2 tapered sliding dovetail detail", fontsize=14,
                 fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(str(out_path), dpi=140, bbox_inches="tight")
    plt.close()


# ------------------------------------------------------------------
# Nesting clearance check  (does the bow drop inside the center cockpit?)
# ------------------------------------------------------------------
def center_inner_clear_hw(hull, x, z):
    """Center cockpit CLEAR inner half-width at station x, height z: the hull inner
    skin, capped by the wall (ycut-WALL) and, in the dovetail band, the gunwale rail
    (ycut-RAIL_W). This is the tightest line the bow must clear."""
    ii = hull.half_inner(x)
    pz = [p[1] for p in ii]
    py = [p[0] for p in ii]
    yc = ycut(x)
    yh = float(np.interp(z, pz, py))
    cap = yc - WALL
    o = hull.half_outer(x)
    if max(p[0] for p in o) > yc + EPS:
        dt = dovetail_params(hull, x, cross_z(o, yc))
        if dt is not None:
            _, under, z_mb, z_mt = dt
            if z_mb - under - RAIL_MARGIN <= z <= z_mt + under + RAIL_MARGIN:
                cap = yc - RAIL_W
    return max(0.0, min(yh, cap))


def bow_outer_hw(hull, x, z):
    """Bow OUTER half-width at station x, height z (chamfer applied). 0 outside the
    section's z-range."""
    o = chamfer_profile(resample(hull.half_outer(x), NP), chamfer_amount(x))
    pz = [p[1] for p in o]
    py = [p[0] for p in o]
    if z < pz[0] - 1e-6 or z > pz[-1] + 1e-6:
        return 0.0
    return float(np.interp(z, pz, py))


def check_bow_nesting(hull, n_x=33, n_dz=16):
    """Place the bow wide-end at the transom, sheers flush, and measure the min
    width clearance (center inner clear - bow outer) over its footprint. Returns
    (min_clear_design, at_xb, at_dz, proud_design). proud>0 => bow sits above rim."""
    min_clr, at = 1e9, (None, None)
    proud = -1e9
    for xb in np.linspace(BOW_SPLIT, LOA - 1.0, n_x):
        xc = xb - BOW_SPLIT
        if xc < 0 or xc > BOW_SPLIT:
            continue
        szb = hull.interp(xb)[3]
        szc = hull.interp(xc)[3]
        # depth check: bow keel vs cockpit floor when rims are flush
        keelb = hull.half_outer(xb)[0][1]
        floorc = hull.half_inner(xc)[0][1]
        proud = max(proud, (szc - floorc) - (szb - keelb))  # >0: bow shallower, ok
        for dz in np.linspace(0.0, 6.0, n_dz):
            bw = bow_outer_hw(hull, xb, szb - dz)
            if bw <= 1e-6:
                continue
            cw = center_inner_clear_hw(hull, xc, szc - dz)
            clr = cw - bw
            if clr < min_clr:
                min_clr, at = clr, (xb, dz)
    return min_clr, at[0], at[1], proud


# ------------------------------------------------------------------
# Wedge flip-pack  (two mirror pods -> one compact bundle)
# ------------------------------------------------------------------
def pack_wedges(stbd, port):
    """Flip the port wedge over its fore-aft axis (y->-y, z->-z) so it lands in the
    starboard band, upside down, then stack it on the stbd wedge -> a compact slab.
    Returns (A, B_transformed, combined_bbox_dims)."""
    import trimesh
    A = stbd.copy()
    B = port.copy()
    Rx = trimesh.transformations.rotation_matrix(np.pi, [1.0, 0.0, 0.0])
    B.apply_transform(Rx)                                  # flip port upside down -> +y band
    # nestle B down onto A (spoon the two hulls), small overlap-free drop
    dz = A.bounds[1][2] - B.bounds[0][2] - 0.0
    B.apply_translation([0.0, 0.0, dz])
    lo = np.minimum(A.bounds[0], B.bounds[0])
    hi = np.maximum(A.bounds[1], B.bounds[1])
    return A, B, (hi - lo)


def render_transport_packing(hull, pieces, out_path):
    """Bow-nested-in-center clearance + wedge flip-pack, all in REAL units."""
    import matplotlib.pyplot as plt

    s = DESIGN_SCALE
    min_clr, xb_t, dz_t, proud = check_bow_nesting(hull)

    fig = plt.figure(figsize=(20, 12))

    # (1) transom y-z: center inner-clear vs bow aft section (sheers flush)
    ax1 = fig.add_subplot(2, 2, 1)
    ax1.set_aspect("equal")
    zc_c = np.linspace(hull.half_inner(0.0)[0][1], hull.interp(0.0)[3], 80)
    ci = [center_inner_clear_hw(hull, 0.0, z) for z in zc_c]
    co = [center_outer_half(hull, 0.0)]  # for outline context
    ax1.plot([s * v for v in ci], [s * z for z in zc_c], "-", color="#5B8FF9", lw=2,
             label="center inner clear")
    ax1.plot([-s * v for v in ci], [s * z for z in zc_c], "-", color="#5B8FF9", lw=2)
    szb, szc = hull.interp(BOW_SPLIT)[3], hull.interp(0.0)[3]
    zb = np.linspace(hull.half_outer(BOW_SPLIT)[0][1], szb, 80)
    bo = [bow_outer_hw(hull, BOW_SPLIT, z) for z in zb]
    zb_sh = zb - (szb - szc)                                  # drop bow so rims align
    ax1.plot([s * v for v in bo], [s * z for z in zb_sh], "-", color="#6DC8EC", lw=2,
             label="bow aft outer (chamfered)")
    ax1.plot([-s * v for v in bo], [s * z for z in zb_sh], "-", color="#6DC8EC", lw=2)
    ax1.set_title(f"Transom section: bow nested in center\n"
                  f"min width clearance = {s*min_clr:+.2f}\" "
                  f"(at bow x={xb_t:.0f}, {dz_t:.1f}\" below rim)",
                  fontsize=11, fontweight="bold")
    ax1.set_xlabel("beam (in, real)")
    ax1.set_ylabel("height (in, real)")
    ax1.legend(fontsize=8, loc="lower center")
    ax1.grid(True, alpha=0.2)

    # (2) plan: bow footprint inside center cockpit (top view)
    ax2 = fig.add_subplot(2, 2, 2)
    ax2.set_aspect("equal")
    xs = np.linspace(0, BOW_SPLIT, 80)
    ci_rim = [center_inner_clear_hw(hull, x, hull.interp(x)[3] - 0.05) for x in xs]
    ax2.fill_between([s * x for x in xs], [s * v for v in ci_rim],
                     [-s * v for v in ci_rim], color="#5B8FF9", alpha=0.25,
                     label="center cockpit opening")
    xbs = np.linspace(BOW_SPLIT, LOA - 1.0, 80)
    bow_rim = [bow_outer_hw(hull, xb, hull.interp(xb)[3] - 0.05) for xb in xbs]
    xb_plan = [s * (xb - BOW_SPLIT) for xb in xbs]            # aft end at transom
    ax2.fill_between(xb_plan, [s * v for v in bow_rim], [-s * v for v in bow_rim],
                     color="#6DC8EC", alpha=0.7, label="bow (nested)")
    ax2.set_title("Plan: bow nested inside center cockpit", fontsize=11,
                  fontweight="bold")
    ax2.set_xlabel("x from transom (in, real)")
    ax2.set_ylabel("beam (in, real)")
    ax2.legend(fontsize=8, loc="upper right")
    ax2.grid(True, alpha=0.2)

    # (3) wedge flip-pack, iso
    A, B, dims = pack_wedges(pieces["wedge_stbd"], pieces["wedge_port"])
    ax3 = fig.add_subplot(2, 2, 3, projection="3d")
    _add_mesh(ax3, A, PIECE_COLORS["wedge_stbd"], alpha=0.7)
    _add_mesh(ax3, B, PIECE_COLORS["wedge_port"], alpha=0.7)
    lo = np.minimum(A.bounds[0], B.bounds[0])
    ax3.set_xlim(lo[0], lo[0] + 62)
    ax3.set_ylim(18, 40)
    ax3.set_zlim(-2, 44)
    ax3.view_init(elev=20, azim=-60)
    ax3.set_box_aspect([3.0, 1.1, 2.0])
    ax3.set_title(f"Wedge flip-pack (port flipped onto stbd)\n"
                  f"bundle {s*dims[0]:.0f} x {s*dims[1]:.0f} x {s*dims[2]:.0f}\" real",
                  fontsize=11, fontweight="bold")
    for pane in (ax3.xaxis, ax3.yaxis, ax3.zaxis):
        pane.pane.fill = False

    # (4) text summary
    ax4 = fig.add_subplot(2, 2, 4)
    ax4.axis("off")
    cd = (pieces["center"].bounds[1] - pieces["center"].bounds[0]) * s
    bd = (pieces["bow"].bounds[1] - pieces["bow"].bounds[0]) * s
    nests = "YES" if min_clr * s >= 0.25 else "NO"
    wflat = (pieces["wedge_stbd"].bounds[1] - pieces["wedge_stbd"].bounds[0]) * s
    lines = [
        "TRANSPORT PACKING (real boat, x%.2f)" % s,
        "",
        f"Center cockpit : {cd[0]:.0f} x {cd[1]:.0f} x {cd[2]:.0f} in",
        f"Bow pod        : {bd[0]:.0f} x {bd[1]:.0f} x {bd[2]:.0f} in",
        f"Bow nests in center? {nests}  (min clearance {s*min_clr:+.2f} in)",
        f"   vertical: bow {'fits below rim' if proud>=0 else 'sits %.1f in proud'%(-s*proud)}",
        "",
        f"Single wedge   : {wflat[0]:.0f} x {wflat[1]:.1f} x {wflat[2]:.0f} in",
        f"Wedge bundle   : {s*dims[0]:.0f} x {s*dims[1]:.0f} x {s*dims[2]:.0f} in",
        f"  two wedges flat side-by-side: {wflat[0]:.0f} x {2*wflat[1]:.0f} x {wflat[2]:.0f} in",
        "",
        "Package: bow nests INSIDE center;",
        "wedges flip into a bundle that straps",
        "alongside (won't also fit in the cockpit",
        "with the bow -- bow fills the opening).",
    ]
    ax4.text(0.02, 0.98, "\n".join(lines), va="top", ha="left", family="monospace",
             fontsize=11, transform=ax4.transAxes)

    fig.suptitle("Rev-3 transport packing -- bow nesting + wedge flip-pack",
                 fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(str(out_path), dpi=140, bbox_inches="tight")
    plt.close()


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=10)
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--output-dir", default="split_out")
    args = ap.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    hull = DinghyHull()
    print("Building split pieces...")
    raw = {
        "center": build_center(hull),
        "wedge_stbd": build_wedge(hull, +1),
        "wedge_port": build_wedge(hull, -1),
        "bow": build_bow(hull),
    }

    pieces = {}
    for name, vf in raw.items():
        m = to_trimesh(vf)
        if name.startswith("wedge"):
            m = trim_wedge_mesh(hull, m)
            if WEDGE_HOLLOW:
                import trimesh
                cav = build_wedge_cavity(hull, +1 if name.endswith("stbd") else -1)
                if cav is not None:
                    m = m.difference(cav)                  # seal-hollow the buoyancy pod
                    trimesh.repair.fix_normals(m)          # (no merge_vertices: welds thin wall)
        if name == "center":
            import trimesh
            m = m.union(build_transom(hull))               # close the stern
            if MOTOR_NOTCH:
                m = m.difference(build_notch_box(hull))    # outboard motor cutout
            trimesh.repair.fix_normals(m)
        if name == "bow" and BOW_HOLLOW:
            import trimesh
            m = m.difference(build_bow_cavity(hull))       # hollow + dome storage access
            trimesh.repair.fix_normals(m)                  # (no merge_vertices: welds thin wall)
        pieces[name] = m

    if USE_VKEYS:
        print(f"Cutting {N_KEYS} vertical drop-in dovetail keys per side...")
        pieces = add_vertical_dovetails(hull, pieces)

    print("Drilling above-waterline bolt holes...")
    pieces, bolts = add_bolt_holes(hull, pieces)
    nb = {"wedge": sum(1 for b in bolts if b[0] == "wedge"),
          "bow": sum(1 for b in bolts if b[0] == "bow")}
    print(f"  {nb['wedge']} wedge<->center bolts + {nb['bow']} bow<->center bolts")

    # Final topology cleanup: the wedge boolean chain can leave a stray non-manifold
    # edge. make_manifold() repairs it (no-op on the already-clean center/bow) so every
    # exported STL is a proper manifold for slicing/printing.
    for name in pieces:
        pieces[name] = make_manifold(pieces[name])

    all_wt = True
    reals = {}
    print("\nPer-piece geometry, AFTER bolt holes (design units, before DESIGN_SCALE):")
    for name, m in pieces.items():
        wt = report(name, m)
        all_wt &= wt
        if name == "bow" and BOW_HOLLOW:
            print("                 ^ bow is a HOLLOW storage shell with a dome access "
                  "opening aft (still a clean manifold, like a cup)")
        # Export the REAL boat = design downscaled by DESIGN_SCALE
        real = m.copy()
        real.apply_scale(DESIGN_SCALE)
        real.export(str(out / f"{name}.stl"))
        reals[name] = real
        model = real.copy()
        model.apply_scale(25.4 / args.scale)   # 1:scale mm model of the real boat
        model.export(str(out / f"{name}_1to{args.scale:.0f}_mm.stl"))

    print(f"\n  All pieces watertight (after drilling): {all_wt}"
          f"  (bow is hollow w/ a dome storage opening)")

    # Composite: all 4 pieces merged in their assembled positions -> one viewable STL
    # (and a 1:scale mm version). Same coordinate frame, so this IS the whole boat.
    import trimesh
    comp = trimesh.util.concatenate(list(reals.values()))
    comp.export(str(out / "dinghy_assembled.stl"))
    cmm = comp.copy()
    cmm.apply_scale(25.4 / args.scale)
    cmm.export(str(out / f"dinghy_assembled_1to{args.scale:.0f}_mm.stl"))
    cd = comp.bounds[1] - comp.bounds[0]
    print(f"  Composite assembled: dinghy_assembled.stl  "
          f"({cd[0]:.0f} x {cd[1]:.0f} x {cd[2]:.0f} in)")

    estimate_weight(reals)

    # Fit / transport summary -- real boat (design x DESIGN_SCALE)
    def rdim(name):
        return (pieces[name].bounds[1] - pieces[name].bounds[0]) * DESIGN_SCALE
    print(f"\nTransport / fit summary (real boat, design x{DESIGN_SCALE:.2f}):")
    cd = rdim("center")
    print(f"  Center barge   : {cd[0]:.1f}\"L x {cd[1]:.1f}\"W x {cd[2]:.1f}\"H "
          f"({cd[0]/12:.1f} x {cd[1]/12:.1f} ft)")
    for w in ("wedge_stbd", "wedge_port"):
        wd = rdim(w)
        print(f"  {w:14}: {wd[0]:.1f}\"L x {wd[1]:.1f}\"W x {wd[2]:.1f}\"H")
    bd = rdim("bow")
    print(f"  Bow pod        : {bd[0]:.1f}\"L x {bd[1]:.1f}\"W x {bd[2]:.1f}\"H "
          f"(nests in {cd[0]:.0f}\" cockpit)")
    print(f"  Assembled LOA  : {LOA*DESIGN_SCALE:.0f}\"  ({LOA*DESIGN_SCALE/12:.1f} ft)  "
          f"beam {2*h2.STATIONS[0][3]*DESIGN_SCALE:.0f}\" at transom")

    # Nesting + wedge-bundle report (real units)
    s = DESIGN_SCALE
    min_clr, xb_t, dz_t, proud = check_bow_nesting(hull)
    A, B, bdims = pack_wedges(pieces["wedge_stbd"], pieces["wedge_port"])
    wflat = (pieces["wedge_stbd"].bounds[1] - pieces["wedge_stbd"].bounds[0]) * s
    print("\nNesting / bundle (real boat):")
    print(f"  Bow nests in center: {'YES' if s*min_clr >= 0.25 else 'NO'}  "
          f"(min width clearance {s*min_clr:+.2f}\" at bow x={xb_t:.0f}\", "
          f"{dz_t:.1f}\" below rim)")
    print(f"  Bow vertical: {'fits below rim' if proud >= 0 else f'sits {-s*proud:.1f}\" proud'}")
    print(f"  Wedge flip-bundle: {s*bdims[0]:.0f} x {s*bdims[1]:.0f} x {s*bdims[2]:.0f}\"  "
          f"(side-by-side flat: {wflat[0]:.0f} x {2*wflat[1]:.0f} x {wflat[2]:.0f}\")")

    if not args.no_preview:
        print("\nRendering preview...")
        render(pieces, out / "split_preview.png")
        print(f"  Saved: {out/'split_preview.png'}")
        render_dovetail_detail(hull, pieces, out / "dovetail_detail.png")
        print(f"  Saved: {out/'dovetail_detail.png'}")
        render_transport_packing(hull, pieces, out / "transport_packing.png")
        print(f"  Saved: {out/'transport_packing.png'}")
        render_bolts(hull, bolts, out / "bolts.png")
        print(f"  Saved: {out/'bolts.png'}")

    # Bolt summary (real units): confirm every bolt sits above the waterline.
    print("\nBolt holes (real boat):")
    for (kind, x, y, z) in bolts:
        wl = (hull.interp(x)[5] + WATERLINE / DESIGN_SCALE)
        flag = "OK" if z >= wl else "!! BELOW WL"
        print(f"  {kind:5} @ x={x*DESIGN_SCALE:5.1f} y={y*DESIGN_SCALE:+6.1f} "
              f"z={z*DESIGN_SCALE:5.1f}  ({z-wl:+.1f}\" above WL {flag})")

    print("\nDone.")


if __name__ == "__main__":
    main()
