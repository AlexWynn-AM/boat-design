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
# Infill is ZONED by the waterline. Below it the panels take slamming and beaching, and
# the center's bottom is a 42" wide shallow V with nothing in its shape to stiffen it.
# Above it the panels are narrow and doubly curved, so they carry load in membrane action
# rather than bending and need far less from the core; the 3 mm okume version of this boat
# is rock solid in the bow and flexible across the wide flat spans for exactly that reason.
# Use GYROID, not grid: isotropic, and much better in shear as a sandwich core.
INFILL = 0.12           # below the waterline, on the pieces named in INFILL_ZONED
INFILL_TOPSIDE = 0.08   # everywhere else
# Only the CENTER earns the denser core. Its bottom is a 42" wide shallow V and its sole
# spans the full beam, so neither has any curvature to stiffen it. The bow and the wedges
# are narrow and doubly curved end to end and run lean throughout.
INFILL_ZONED = ("center",)
# Fiberglass schedule by ZONE (laminated areal mass incl. resin, kg/m^2).
# Rev-3.4: ONE FABRIC -- 6 oz plain weave everywhere, doubled on the bottom (2nd layer at
# 45 deg to the first). Was 1708 biax on the bottom + 4 oz on the deck.
#   6 oz  = 203 g/m^2 dry, ~50% fibre wet  -> 0.40 kg/m^2 laminated
# WHY NOT 1708: its 0.75 oz mat is a POLYESTER feature -- it exists to make secondary
# bonds to cured polyester, and its binder is styrene-soluble, so in EPOXY it neither
# breaks down nor carries load (random chopped fibre at ~27% fibre fraction, on a skin
# whose job is impact, not bending -- the 7 mm printed core does the bending). It is only
# ~0.09 of the old 1.2, so dropping it was never about weight. The no-mat equivalent is
# 1700 / DB170 biax; 2 x 6 oz was chosen over it for buildability: one fabric to buy, far
# easier wet-out, and it drapes over the bow flare and the printed layer lines properly.
# TRADE: 2 x 6 oz is 406 g/m^2 of fibre vs 576 for 1700, and ~0.5 mm of laminate vs ~0.85.
# That is the abrasion/puncture margin, so a beaching boat wants the keel + chine strip
# noted below rather than a thicker skin everywhere.
GLASS_BOTTOM  = 0.8     # exterior bottom: 2 x 6 oz (2nd at 45 deg) -- 0.4 for one layer
GLASS_TOPSIDE = 0.4     # exterior topsides: 6 oz
GLASS_DECK    = 0.4     # decks/gunwale tops: 6 oz (was 4 oz; core gives the stiffness)
GLASS_INSIDE  = 0.4     # interior (cockpit only): 6 oz
# BUILD NOTE: beaching abrasion is a LOCAL problem -- add a 3rd 6 oz strip (or graphite/
# epoxy) along the keel and the chines, where the boat actually drags, rather than paying
# for a heavier bottom skin over the whole 2.7 m^2. Not modelled here (local, ~0.2 kg).
# If you ever switch to polyester/vinylester, put the mat back: there it earns its place.
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

# --- Flared bow (sportfish sheer kick above the spray rail) ---------------------
# Rev-3.2. The bow topside above the spray rail is kicked OUTBOARD, hardest at the
# deck edge: the sheer moves out, the panel between rail and sheer leans out with a
# rising slope, and because the kick grows as a POWER (>1) of height the panel is
# CONCAVE relative to the straight rail->sheer chord. That is how a real flared bow
# gets its hollow -- wide dry deck edge overhanging a concave transition panel --
# instead of pinching a waist into the topside (Rev-3.1's carve-in, below, which
# read as a pinch under an overhang and is now superseded/off).
#
# No material is removed anywhere: everything at/below BOW_FLARE_F0 (spray rail lip
# and the whole bottom) is untouched, and above it y only grows. Applied to the BOW
# piece only and faded in from ZERO at the split, so the x=BOW_SPLIT interface
# section is bit-for-bit the same contour the center presents (flush mate).
BOW_FLARE_OUT = 1.5      # design in of OUTWARD sheer kick at full longitudinal blend
BOW_FLARE_EXP = 2.2      # height profile: kick ~ ((f-F0)/(1-F0))**this  (>1 => concave)
BOW_FLARE_POW = 1.5      # longitudinal blend: g = ((x-split)/(LOA-split))**this
BOW_FLARE_F0 = 0.45      # flare starts above this topside fraction (rail lip stays put)
# --- Stem guards on the kick (rev-3.2a) -----------------------------------------
# g=t**POW grows toward the stem while the sections themselves shrink to nothing, so a
# raw kick of BOW_FLARE_OUT would be a LARGER fraction of the section the finer it gets
# (~+53% of the half-beam at the last full station) -- a deck edge that keeps widening
# while the hull under it vanishes. Two independent guards keep the flare proportional:
#   CAP  - the kick may never exceed this fraction of the local (pre-kick) sheer
#          half-width, so it always reads as a flare on the section and not a shelf;
#   FADE - optional: multiply the kick by a nose fade over the last BOW_FLARE_NOSE_FADE
#          inches (0 = OFF). Rev-3.2b turned this OFF (user wants flare carried right to
#          the bow -- the faded deck edge read as "rounding back" at the stem). The fade
#          was only ever a precaution: the membrane bug it guarded against turned out to
#          be the coplanar flange boolean, and the raw loft is clean at full kick. With
#          fade off the CAP alone governs the tip: the kick shrinks in proportion to the
#          vanishing sections, so the flare persists to the nose without a shelf.
BOW_FLARE_CAP = 0.25     # kick <= this fraction of the local sheer half-width
BOW_FLARE_NOSE_FADE = 0.0  # design in of stem fade-out for the flare (0 = carry to nose)
# Legacy Rev-3.1 carve-in hollow -- superseded by the outward kick above. Code path
# kept (bow_section(..., hollow=) still honours it) but OFF by default.
BOW_FLARE_HOLLOW = 0.0   # design in of max INBOARD hollow (0 = off)
BOW_FLARE_CLAMP = 0.6    # guard: hollow_amt <= this * local y (section can never cross y=0)

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
# Where (in section height) the nose rings shrink TOWARD: 0 = keel, 0.5 = mid-height
# (old bullnose), 1.0 = the sheer -- deck edge holds full height to the tip and the
# stem rakes up to meet it (rev-3.2c, sheds water off the flared deck edge).
NOSE_Z_ANCHOR = 1.0
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
# Rev-3.4: the boss used to be a flat on/off -- full margin anywhere near a key, over the
# WHOLE section height. But a key only spans from a foot above the waterline to the rim,
# so each boss ran keel-to-sheer and ~43% of it backed nothing: 374 in^3 real per wedge.
# It now fades out below the key and past the key's ends, which also kills the two steps
# (both stress risers, and both visible on the inside of a printed pod).
WEDGE_BOSS_SKIRT = 2.0            # design in: fade the boss out over this much z BELOW the
                                  # key's own bottom (a chamfered root, not a shelf)
WEDGE_BOSS_FADE = 1.5             # design in: and over this much x past WEDGE_BOSS_HALF

# Wedge-top trim (REAL inches): lop this much off the top of the wedges (flat cap)
# so the rotated wedges sit lower when nested -> smaller total bundle height for the
# car. Only the WEDGE is shortened; the center keeps full height. 0 = untrimmed.
# Assembled, this steps the outboard aft gunwale down by WEDGE_TOP_TRIM.
WEDGE_TOP_TRIM = 0.0
# --- Design load -> waterline (rev-3.3) -----------------------------------------
# WATERLINE used to be a magic 7.0 with nothing behind it. It is now DERIVED: the hull's
# own hydrostatics are solved for the waterplane at DESIGN_LOAD_LB all-up, so every
# "must stay above the waterline" rule in this file (bolts, dovetails, the bulkhead sill)
# is tied to a stated weight instead of a guess. See report_hydrostatics().
DESIGN_LOAD_LB = 600.0      # all-up: structure + motor + battery + fuel + crew + gear.
                            # The printed+glassed structure is ~66 lb, so this is ~535 lb
                            # of everything else -- roughly 3 adults with a small outboard.
WATER_LB_PER_IN3 = 0.0361   # fresh water (salt is ~0.0370 -> very slightly less draft)
WATERLINE = 7.0     # real inches above the keel datum at the split. OVERWRITTEN by
                    # set_waterline_from_load() at the top of main(); the literal is only
                    # the fallback for importers that never call main(). At DESIGN_LOAD_LB
                    # = 600 lb it solves to ~7.0", which is where the old guess landed.

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
# Fit clearance. Rev-3.4: the socket used to be cut with the SAME prism that was unioned
# on as the tongue, i.e. a zero-clearance interference fit -- correct on paper, unbuildable
# in practice. The socket cutter is now grown KEY_CLR on every face (and its floor dropped
# the same amount) so the tongue drops in with a gap all round; the same value is used on
# the bow<->center keys. Given in REAL mm because it is a printing/fit allowance, not a
# hull dimension -- so note it does NOT shrink with --scale: a 1:10 model wants roughly
# 10x KEY_CLR_MM to fit like the real boat (see --key-clearance-mm).
#
# SIZED FOR GLASS IN THE JOINT. The mating walls are exterior surfaces -- the center has to
# float on its own and the wedge wall is the inboard skin of a sealed pod -- and a single
# 0.5 mm perimeter over 12% gyroid weeps through its layer lines, so they get coated. In
# practice that is asymmetric: a tongue is convex and takes 6 oz cloth (~0.3 mm), a socket
# is a 16 mm deep flared slot that cloth only bridges and traps air in, so sockets get neat
# or lightly thickened epoxy (~0.15 mm). ~0.45 mm of coating before tolerance. Add print
# accuracy, bond-line error across a 144-chunk assembly, and differential ASA shrink over
# the 732 mm between the first and last key -- three keys a side have to engage at once.
# 0.6 mm (rev-3.4's first pass) was swallowed by the glass alone.
# Loose is nearly free here: clearance eats the dovetail's capture margin 1:1, and the
# wedge keys still hold 9.4 mm of it at 2.0. The bolts do the clamping; the keys only have
# to resist pull-apart.
KEY_CLR_MM = 2.0            # real mm of gap per mating face
KEY_CLR = (KEY_CLR_MM / 25.4) / DESIGN_SCALE     # -> design inches

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
BOLT_WEDGE_IN = 2.5      # cylinder reach inboard of the mating plane -> straight through
                         # the center's wall into the cockpit, where the head/washer bears
# The wedge end is BLIND. A wedge is a SEALED buoyancy pod: there is no way to reach inside
# it to put a nut on, so the bolt has to thread into the wedge itself (heat-set or epoxied
# insert in the boss -- BOLT_R is a ~10 mm hole, sized for one).
# Rev-3.4: this used to be a flat 2.5" like the inboard reach, but the wedge only carries
# WEDGE_BOSS_MARGIN of solid behind the mating wall, so every one of the 12 holes ran out
# the back of its boss and into the sealed void -- 0.14 in^3 of daylight apiece. That is
# invisible to every other check in this file, because a tunnel into an internal void
# leaves a perfectly watertight manifold, and it costs BOTH things the pod is for: it
# floods, and the bolt has nothing to land on. Now derived from the boss so it can never
# outrun it again, and check_pods_sealed() asserts it every run.
BOLT_WEDGE_BACK = 0.35   # design in: solid kept BEHIND the blind hole's bottom
BOLT_WEDGE_OUT = WEDGE_BOSS_MARGIN - BOLT_WEDGE_BACK   # reach outboard, into the wedge boss
# Bow<->center bolts. With the vertical drop-in keys (BOW_KEYS) carrying the fore-aft
# lock, these are ANTI-LIFT ONLY -- like the wedge bolts -- so two heights per side is
# enough. Given as REAL inches (13" and 19" above the keel) -> design units.
BOLT_BOW_Z = [13.0 / DESIGN_SCALE, 19.0 / DESIGN_SCALE]   # -> 2 x 2 sides = 4 bolts
BOLT_BOW_HALF = 3.0      # cylinder half-length along X about the x=BOW_SPLIT face
                         # (must exceed FLANGE_T so the bolts pierce BOTH flange rings)

# --- Interface flange at the bow/center joint (bolt-grip bulkhead ring) ---------
# The bow<->center joint is two thin (SKIN) shell edges butted at x=BOW_SPLIT; 8 bolts
# through 7 mm of ASA is not enough grip. So each piece gets a bulkhead RING at the
# interface: outer boundary = that piece's own outer section (so nothing protrudes past
# the skin), inner boundary = the same contour drawn FLANGE_W inboard. The center's ring
# lives entirely in x = [60-FLANGE_T, 60] and the bow's entirely in x = [60, 60+FLANGE_T],
# so the two rings butt face-to-face at the split and never interfere.
IFACE_FLANGE = True
FLANGE_W = 2.0 / DESIGN_SCALE     # 2.0" REAL ring width, inboard from the shell
FLANGE_T = 1.5 / DESIGN_SCALE     # 1.5" REAL axial thickness (each side of the joint)
FLANGE_GAP = 0.05                 # design in: pull the ring's outer edge just inside the
                                  # skin so the union overlaps solid (no coincident faces)
FLANGE_NX = 5                     # loft stations across the flange thickness
FLANGE_STEP = 0.01                # design in: x-gap between the two cavity stations that
                                  # form the BOW ring's forward annular face. The bow's
                                  # ring is not unioned on -- it is lofted into the storage
                                  # cavity (see bow_wall_at), which is what keeps any face
                                  # from landing coplanar with the x=BOW_SPLIT mating plane.

# --- Vertical drop-in dovetail KEYS at the bow/center face (the wedge-key trick, rotated)
# Same construction as add_vertical_dovetails: ONE shared prism per key, SUBTRACTED from
# the center (socket) and UNIONED into the bow (tongue), so they mate exactly. The prism
# is extruded in Z, so the bow still assembles by dropping straight DOWN; its horizontal
# section is a dovetail flared along X -- a narrow mouth at the x=BOW_SPLIT face widening
# in y going AFT into the center -- so once seated the bow cannot be pulled forward (+x).
# The center-side socket is cut as a FULL-HEIGHT channel (open at the rim) so the tongue
# rides down it; the bow-side tongue only occupies its working z-band.
BOW_KEYS = True
BKEY_DEPTH = 0.8      # flared back reaches this far AFT of x=BOW_SPLIT (design in)
BKEY_STUB = 0.6       # tongue stub reaches this far FORWARD into the bow (design in)
BKEY_SILL = 0.15      # socket floor sits this far BELOW the tongue -> never bottoms out
BKEY_BOSS = 0.55      # local backing boss kept around each socket/tongue (design in)
# Key 1 -- LOW CENTERLINE. The point of the whole change: it locks the bottom of the joint
# BELOW the waterline, where no bolt may penetrate. Hosted by a local boss standing on the
# cockpit sole / storage sole, so the socket never reaches the watertight bottom skin.
BKEY_CTR_Z0 = 1.1     # design z of the centreline tongue's bottom
BKEY_CTR_H = 2.4      # its height
BKEY_CTR_MOUTH = 0.7  # half-width in y at the mouth
BKEY_CTR_BACK = 1.1   # half-width in y at the flared back (> MOUTH => dovetail)
# Keys 2+3 -- one per side at mid-height, hosted by the flange ring (+ an inboard boss).
BKEY_SIDE_Z0 = 9.4    # above the waterline, below the lower bolt
BKEY_SIDE_H = 3.2
BKEY_SIDE_MOUTH = 0.42
# Widened with KEY_CLR (rev-3.4): these are the SMALL keys, and clearance comes straight
# off the undercut. At BACK=0.62 the capture margin was 4.6 mm and a 2.0 mm gap would have
# left 2.6; 0.75 restores it to ~5.5 mm. The wedge and centreline keys have 11.4/9.1 mm of
# undercut and never needed the help.
BKEY_SIDE_BACK = 0.75
# Keep the key's outboard edge this far inside the flange's outer face -- measured on the
# GROWN socket, so the clearance is added in: otherwise raising KEY_CLR walks the channel
# out through the flange's own skin.
BKEY_SIDE_EDGE = 0.15 + KEY_CLR

# --- Solid BULKHEAD across the bottom of the bow/center joint (rev-3.3) ---------
# The flange ring alone leaves the bottom of the x=BOW_SPLIT seam as a thin butt joint:
# the only solid thing closing it low down was the centreline key's little boss standing
# on the sole, topping out ~5" above the keel -- i.e. UNDER the 7" waterline, and further
# under it once the boat is loaded. So the bottom of the joint is now a FULL solid web --
# a real bulkhead -- on each piece, from the keel up to BHD_TOP. Above BHD_TOP the joint
# reverts to the flange ring.
#   CENTER -> x = [BOW_SPLIT-BHD_T, BOW_SPLIT], unioned on: a BHD_TOP-high bulkhead
#             standing at the forward end of the cockpit.
#   BOW    -> x = [BOW_SPLIT, BOW_SPLIT+BHD_T], produced by CUTTING the region out of
#             build_bow_cavity rather than unioning a solid on, so no new face lands
#             coplanar with the x=BOW_SPLIT mating plane (same reasoning as bow_wall_at).
#             The bow's storage opening therefore gains a BHD_TOP sill.
BULKHEAD = True
BHD_TOP = 12.0                 # REAL inches above the keel: top of the solid web
                               # (waterline is 7", lowest bow bolt is at 13")
BHD_T = 1.0 / DESIGN_SCALE     # REAL 1.0" axial thickness EACH side -> 2.0" assembled.
                               # Deliberately != FLANGE_T so no bulkhead face can land
                               # coplanar with a flange face.
BHD_DIP = 4.0                  # REAL inches the top of the web DIPS at the centreline:
                               # the sill is an arch, BHD_TOP at the skin falling to
                               # BHD_TOP-BHD_DIP on the centreline (raised cosine over the
                               # web's full half-width). Softens the flat top edge and
                               # opens the storage hatch 4" taller in the middle, where a
                               # bag actually goes through. 0 = flat top.
BKEY_TOP_GAP = 0.2             # design in: hold every key tongue this far BELOW the LOCAL
                               # bulkhead top, so no tongue cap is coplanar with it (and
                               # no tongue stands proud of the arched sill).

# Transom: a slab closing the center's stern (the cockpit is otherwise open aft), plus a
# MOULDED CLAMP PAD standing proud of its inner face where the outboard actually grips.
#
# Rev-3.4. It used to be a flat 1.5" slab everywhere: 1175 in^3, 32% of the center's entire
# material volume, to serve a motor that only ever touches the ~20" either side of the
# notch. So the slab is thinned to a structural closure and the thickness is put back as a
# local pad that smoothsteps away in both y and z -- printed, a moulded lens costs nothing
# a flat slab doesn't.
#
# The pad is UNIONED as its own solid rather than written into the slab's forward face,
# and that is not a style choice: build_transom caps that face with ear_clip over the
# section OUTLINE, so an x carried on the outline is exact only ON the boundary and is
# linearly interpolated across the interior. A y-varying thickness written that way reads
# 1.5" at the keel vertex and 0.73" in the middle of the pad -- i.e. it thins out exactly
# where the clamp bears. Measured, before this was caught.
TRANSOM_THICK = 0.65 / DESIGN_SCALE      # REAL base slab: closes the stern, glassed both
                                         # faces; ~2x the cockpit sole, no motor load
TRANSOM_PAD_THICK = 1.5 / DESIGN_SCALE   # REAL total thickness at the clamp pad
TRANSOM_PAD = 10.0 / DESIGN_SCALE        # REAL half-width held at FULL pad thickness. The
                                         # notch is 16" wide at its top, so this is the
                                         # notch + 2" of grip a side: screws land on 1.5".
TRANSOM_BLEND = 8.0 / DESIGN_SCALE       # REAL half-width of the smoothstep out to the slab
TRANSOM_PAD_DROP = 9.0 / DESIGN_SCALE    # REAL: pad runs full this far BELOW the notch ledge
TRANSOM_PAD_FADE = 5.0 / DESIGN_SCALE    # REAL: and fades out over this much more
TRANSOM_PAD_BURY = 0.1                   # design in: the pad's faded edge sits this far
                                         # INSIDE the slab, so no face lands coplanar with
                                         # the slab's own forward face (see bow_wall_at)
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


def _smoothstep(t):
    """C1 ramp: 0 below t=0, 1 above t=1, flat-tangent at both ends."""
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def _signed_area(poly):
    """2x-free signed area of a closed (y,z) polygon: >0 CCW, <0 CW."""
    P = np.asarray(poly, float)
    Q = np.roll(P, -1, axis=0)
    return 0.5 * float(np.sum(P[:, 0] * Q[:, 1] - Q[:, 0] * P[:, 1]))


def offset_poly(poly, d, miter=3.0):
    """TRUE offset of a closed (y,z) contour: every vertex slides along its own miter
    bisector so each EDGE ends up exactly d from where it started, measured along that
    edge's own normal. d > 0 offsets INWARD, d < 0 outward. The vertex count is
    preserved, so the result still lofts as a quad strip against its input.

    Rev-3.4. This replaces the old shrink-toward-the-centroid trick (see inset_contour).
    A radial shrink only leaves a wall of d where the centroid ray happens to hit the
    skin square; on a panel the ray grazes -- the wedge's outer skin, the bow's flat
    foredeck -- the wall collapses to d*cos(theta). Measured on rev-3.2 that put ~1-4 mm
    of material where 7 mm was asked for (0.02 mm at the wedge's forward end), which is
    why the 1:10 test print came out with the wedge skins and the bow deck missing: at
    print scale those walls were a fraction of one extrusion width and the slicer simply
    dropped them."""
    P = np.asarray(poly, float)
    n = len(P)
    sgn = 1.0 if _signed_area(P) > 0 else -1.0    # CCW -> interior is left of each edge
    E = np.roll(P, -1, axis=0) - P                # edge i runs P[i] -> P[i+1]
    L = np.linalg.norm(E, axis=1)
    good = L > 1e-12
    N = np.zeros_like(E)
    N[good] = sgn * np.column_stack([-E[good, 1], E[good, 0]]) / L[good, None]
    for i in range(n):                            # zero-length edges inherit a normal
        if not good[i]:
            N[i] = N[i - 1]
    Nprev = np.roll(N, 1, axis=0)                 # edges (i-1) and i meet at vertex i
    c = np.clip(np.sum(Nprev * N, axis=1), -1.0, 1.0)
    B = Nprev + N
    bl = np.linalg.norm(B, axis=1)
    U = np.where(bl[:, None] > 1e-9, B / np.maximum(bl, 1e-9)[:, None], N)
    # |t| = d / cos(half the turn) -> the bisector reach that puts BOTH edges d away
    t = np.where(bl > 1e-9, d / np.sqrt(np.maximum(0.5 * (1.0 + c), 1e-9)), d)
    t = np.clip(t, -abs(miter * d), abs(miter * d))   # miter limit at spikes
    return [tuple(q) for q in (P + U * t[:, None])]


def _points_inside(pts, poly):
    """Even-odd ray test: per-point True if it lies inside the closed polygon."""
    P = np.asarray(poly, float)
    A, B = P, np.roll(P, -1, axis=0)
    Q = np.asarray(pts, float)
    y, z = Q[:, 0][:, None], Q[:, 1][:, None]
    y0, z0 = A[None, :, 0], A[None, :, 1]
    y1, z1 = B[None, :, 0], B[None, :, 1]
    straddle = (z0 > z) != (z1 > z)
    dz = np.where(np.abs(z1 - z0) < 1e-15, 1e-15, z1 - z0)
    yx = y0 + (z - z0) * (y1 - y0) / dz
    return (np.sum(straddle & (y < yx), axis=1) % 2) == 1


def _crossing_mask(poly):
    """Per-vertex True for every vertex of an edge that crosses a non-adjacent edge."""
    P = np.asarray(poly, float)
    n = len(P)
    A = P
    R = np.roll(P, -1, axis=0) - P
    p, r = A[:, None, :], R[:, None, :]
    q, sv = A[None, :, :], R[None, :, :]
    rxs = r[..., 0] * sv[..., 1] - r[..., 1] * sv[..., 0]
    qp = q - p
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (qp[..., 0] * sv[..., 1] - qp[..., 1] * sv[..., 0]) / rxs
        u = (qp[..., 0] * r[..., 1] - qp[..., 1] * r[..., 0]) / rxs
    hit = ((np.abs(rxs) > 1e-12) & (t > 1e-9) & (t < 1 - 1e-9)
           & (u > 1e-9) & (u < 1 - 1e-9))
    i = np.arange(n)
    gap = np.abs(i[:, None] - i[None, :])
    hit &= ~((gap <= 1) | (gap == n - 1))
    e = hit.any(axis=1) | hit.any(axis=0)         # edge i is involved in a crossing
    return e | np.roll(e, 1)                      # ...so flag both of its endpoints


def _self_intersects(poly):
    """True if any two non-adjacent edges of the closed polygon cross."""
    return bool(_crossing_mask(poly).any())


def _dist_to_poly(pts, poly):
    """Per-point distance from each of pts to the closed polyline `poly`."""
    P = np.asarray(poly, float)
    A, B = P, np.roll(P, -1, axis=0)
    AB = B - A
    den = np.maximum(np.sum(AB * AB, axis=1), 1e-12)
    Q = np.asarray(pts, float)
    t = np.clip(np.sum((Q[:, None, :] - A[None, :, :]) * AB[None, :, :], axis=2)
                / den[None, :], 0.0, 1.0)
    proj = A[None, :, :] + t[:, :, None] * AB[None, :, :]
    return np.linalg.norm(Q[:, None, :] - proj, axis=2).min(axis=1)


def _bridge_runs(O, bad):
    """Replace each circular run of flagged vertices by a straight chord between the two
    sound vertices bracketing it. The run's own shape is thrown away -- that is the
    point: the cavity stops short of the pinch and the pinch stays solid."""
    n = len(O)
    if bad.all():
        return O
    O = O.copy()
    start = int(np.argmin(bad))                   # scan from a vertex we know is sound
    order = [(start + k) % n for k in range(n)]
    k = 0
    while k < n:
        if not bad[order[k]]:
            k += 1
            continue
        j = k
        while j < n and bad[order[j]]:
            j += 1
        a, b = O[order[k - 1]], O[order[j % n]]   # order[0] is sound, so k >= 1 here
        m = j - k
        for t in range(m):
            O[order[k + t]] = a + (b - a) * ((t + 1) / (m + 1.0))
        k = j
    return O


def repair_inset(O, poly, d, tol=0.5, passes=14):
    """Make a raw offset usable: flag every vertex that folded outside `poly` or ended up
    closer than tol*d to it, bridge those runs, repeat until clean.

    offset_poly is exact but it folds wherever the section pinches to less than 2d
    across -- the wedge's bottom corner where the outer skin runs into the mating plane,
    the bow's deck-edge corner under the wide flange inset. Those folds are always LOCAL,
    so throwing the whole station away (and leaving the piece solid there) would be far
    worse than bridging them. Returns a list of the same length, or None if the section
    is genuinely too thin to hollow. tol also acts as the minimum-wall rule: anything
    that would come out thinner than tol*d is left solid instead.

    The flag set is STICKY and every pass re-bridges the RAW offset through it. Bridging
    in place instead let the region oscillate -- a chord's own endpoints become the next
    pass's crossings, the runs shuffle one vertex along, and the loop never settles (the
    center's flange contour did exactly that, so the ring silently failed to build). A
    monotone mask, dilated whenever a pass adds nothing new, always terminates."""
    O0 = np.asarray(O, float)
    n = len(O0)
    O = O0.copy()
    acc = np.zeros(n, bool)
    for _ in range(passes):
        sd = _dist_to_poly(O, poly) * np.where(_points_inside(O, poly), 1.0, -1.0)
        # too thin / folded outside, OR caught up in a miter spike that crosses itself
        bad = (sd < tol * d) | _crossing_mask(O)
        if not bad.any():
            break
        new = acc | bad
        if (new == acc).all():                    # stuck: widen the bridges by a vertex
            new = new | np.roll(new, 1) | np.roll(new, -1)
        if new.sum() > 0.75 * n:
            return None
        acc = new
        O = _bridge_runs(O0, acc)
    else:
        return None
    out = [tuple(q) for q in O]
    return out if offset_ok(out, poly, d) else None


def offset_inward(poly, d, tol=0.5):
    """True inward offset of a closed (y,z) contour by d, pinch-repaired. Same vertex
    count as `poly` (so it lofts as a quad strip against it). None if too thin."""
    return repair_inset(offset_poly(poly, d), poly, d, tol)


def offset_ok(inner, outer, d):
    """Is `inner` a usable inward offset of `outer` by d? Every vertex has to land inside
    `outer` and the result has to stay a simple loop -- that is what catches the two ways
    an offset goes bad on these sections: a miter that overshoots back out through the
    skin, and a neck narrower than 2d where the two walls' offsets pass through each
    other. A False here means "this station is too thin to hollow", not a bug."""
    if len(inner) != len(outer) or d <= 0:
        return False
    ai, ao = _signed_area(inner), _signed_area(outer)
    if ai * ao <= 0 or abs(ai) >= abs(ao):
        return False
    if not _points_inside(np.asarray(inner, float), outer).all():
        return False
    return not _self_intersects(inner)


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
    wl = waterline_z(hull)                       # keep the pocket above the waterline
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
def flare_bump(f):
    """Smooth 0..1 envelope for the concave bow flare over the topside fraction f
    (0 = chine, 1 = sheer). ZERO at/below BOW_FLARE_F0 (the spray-rail panel and its
    lip are untouched -> the rail stays proud), peaks at 1 midway between F0 and the
    sheer (f ~ 0.72), and returns to ZERO at f = 1 so the SHEER WIDTH IS UNCHANGED."""
    if f <= BOW_FLARE_F0:
        return 0.0
    return float(np.sin(np.pi * (f - BOW_FLARE_F0) / (1.0 - BOW_FLARE_F0)) ** 2)


# how much the guard actually had to clamp, worst case (design in) -- reported by main()
FLARE_CLAMP_MAX = 0.0
# how much BOW_FLARE_CAP had to trim off the kick, worst case (design in)
FLARE_CAP_MAX = 0.0


def bow_half_outer(hull, x, rail_f, hollow=0.0):
    """Like hull.half_outer but (a) the spray-rail bulge is scaled by rail_f (0..1) so
    the bow can fade the rail out forward and the rounded nose doesn't bulb, and (b) the
    topside above the rail is pulled INBOARD by up to `hollow` design inches -> a concave
    (hollow) flare that sheds climbing spray instead of feeding it onto the deck.

    The hollow is applied on top of the rail bulge, so the rail lip stays proud; it is
    zero at f<=BOW_FLARE_F0 and zero again at the sheer, so neither the chine nor the
    sheer half-width moves. z is untouched, so the half-section stays z-monotonic and
    therefore cannot self-intersect; y is additionally clamped >0 by BOW_FLARE_CLAMP."""
    global FLARE_CLAMP_MAX
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
        y = yl + bulge
        if hollow > 0.0:
            want = hollow * flare_bump(f)
            if want > 0.0:
                lim = BOW_FLARE_CLAMP * y          # guard: never eat into the centerline
                if want > lim:
                    FLARE_CLAMP_MAX = max(FLARE_CLAMP_MAX, want - lim)
                    want = lim
                y -= want
        pts.append((y, zv))
    return pts


def bow_flare_g(x):
    """Longitudinal blend of the bow flare: EXACTLY 0 at x=BOW_SPLIT (so the bow's
    aft face is the unmodified contour the center presents -> flush mate) growing to 1
    at the stem."""
    t = max(0.0, min(1.0, (x - BOW_SPLIT) / (LOA - BOW_SPLIT)))
    return t ** BOW_FLARE_POW


def flare_out_at(hull, x, o, out):
    """The EFFECTIVE outward sheer kick at station x for the (pre-kick) half-profile o,
    after the two stem guards. Returns design inches.

      1. nose FADE  -- optional (BOW_FLARE_NOSE_FADE > 0): multiply by a rail_f-style
         factor over the last BOW_FLARE_NOSE_FADE inches. OFF by default (rev-3.2b):
         the flare carries to the nose and the CAP alone governs the tip.
      2. CAP        -- clamp to BOW_FLARE_CAP * (local sheer half-width). o[-1] is the
         sheer point and is the widest point of the half-section, so this bounds the
         deck-edge kick to a fixed FRACTION of the section however fine it gets.

    Both are no-ops aft of the nose (fade off / sections far too wide for the cap to
    bite), so nothing changes over the body of the bow -- and the kick is exactly 0
    at x = BOW_SPLIT because `out` is already 0 there."""
    global FLARE_CAP_MAX
    if out <= 0.0:
        return 0.0
    if BOW_FLARE_NOSE_FADE > 0.0:
        fade_f = min(1.0, max(0.0, (LOA - x) / BOW_FLARE_NOSE_FADE))
    else:
        fade_f = 1.0
    faded = out * fade_f
    cap = BOW_FLARE_CAP * max(0.0, o[-1][0])
    if faded > cap:
        FLARE_CAP_MAX = max(FLARE_CAP_MAX, faded - cap)
        faded = cap
    return faded


def flare_kick(hull, x, o, out):
    """SPORTFISH FLARE: kick the topside OUTBOARD, hardest at the deck edge.

    For every point of the half-profile o (keel..sheer) whose topside height fraction
    f = (z-cz)/(sz-cz) is above BOW_FLARE_F0:

        y += out * ((f - F0) / (1 - F0)) ** BOW_FLARE_EXP

    with `out` = flare_out_at(...) = BOW_FLARE_OUT * bow_flare_g(x) design inches AFTER
    the stem guards (nose fade + cap) -- see flare_out_at. Because the exponent is
    > 1 the kick starts flat just off the spray rail and accelerates toward the sheer,
    so the panel bows INSIDE the straight rail->sheer chord: that curvature IS the
    concavity, obtained by moving the sheer OUT rather than by carving the middle IN.
    Nothing is ever moved inboard, the rail lip and everything below it (f <= F0) is
    untouched, and z is untouched -> the profile stays z-monotonic and single-valued.

    Note f is recovered from z, which is exactly the parameter bow_half_outer lofted
    the topside on (z is linear in f there and neither resample nor the convex plan
    scaling touches z), so this is the same f -- just usable AFTER those steps."""
    out = flare_out_at(hull, x, o, out)            # stem guards: nose fade + cap
    if out <= 0.0:
        return o                                   # x=BOW_SPLIT: returns o untouched
    cz, sz = hull.interp(x)[1], hull.interp(x)[3]
    dz = sz - cz
    if dz <= 1e-9:
        return o
    span = 1.0 - BOW_FLARE_F0
    kicked = []
    for (y, z) in o:
        f = (z - cz) / dz
        if f > BOW_FLARE_F0:
            u = min(1.0, (f - BOW_FLARE_F0) / span)
            y = y + out * u ** BOW_FLARE_EXP
        kicked.append((y, z))
    return kicked


def chord_hollow(hull, x):
    """How concave the flared panel actually is at station x, in design inches: the max
    perpendicular distance by which the profile falls INSIDE the straight chord drawn
    from the f=BOW_FLARE_F0 point (just above the spray rail) to the sheer. This is the
    number the eye reads as 'hollow flare' -- with the outward kick it is produced with
    NO inboard movement at all."""
    zs, ys = _bow_profile_hw(hull, x)
    cz, sz = hull.interp(x)[1], hull.interp(x)[3]
    z0 = cz + BOW_FLARE_F0 * (sz - cz)
    band = [(y, z) for y, z in zip(ys, zs) if z >= z0 - 1e-9]
    if len(band) < 3:
        return 0.0
    y0 = float(np.interp(z0, zs, ys))
    p0 = np.array([y0, z0])
    p1 = np.array([band[-1][0], band[-1][1]])
    d = p1 - p0
    n = float(np.hypot(*d))
    if n < 1e-9:
        return 0.0
    d = d / n
    worst = 0.0
    for (y, z) in band:
        v = np.array([y, z]) - p0
        # signed offset: +ve = point is INBOARD of the chord (hollow)
        off = d[1] * v[0] - d[0] * v[1]
        worst = max(worst, -off if d[1] > 0 else off)
    return float(worst)


def bow_section(hull, x, hollow=None, out=None):
    rail_f = min(1.0, max(0.0, (LOA - x) / BOW_RAIL_FADE))     # full rail; fade near stem
    if hollow is None:
        hollow = BOW_FLARE_HOLLOW * bow_flare_g(x)             # 0 at the split
    if out is None:
        out = BOW_FLARE_OUT * bow_flare_g(x)                   # 0 at the split
    o = resample(bow_half_outer(hull, x, rail_f, hollow), NP)  # keel..stbd sheer
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
    # Flare AFTER the plan scaling (so that logic is untouched and the flare is a true
    # added width) and BEFORE the deck, so the foredeck is built from the FLARED sheer
    # point and widens toward the stem on its own. In the rounded nose (build_bow) the
    # last full section is shrunk homothetically, so the flare shrinks with it -- no lip.
    o = flare_kick(hull, x, o, out)
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


def wedge_boss_margin(hull, x, z):
    """Solid kept off the mating wall at (x, z) inside a wedge: WEDGE_BOSS_MARGIN over the
    band a dovetail key actually occupies, SKIN everywhere else, smoothstepped between.
    The key's own bottom is waterline+1 (see _key_prism), and the bolts through it sit
    BOLT_WEDGE_BELOW under the sheer -- both well inside the full-margin band."""
    if not KEY_X:
        return SKIN
    fz = _smoothstep((z - (waterline_z(hull) + 1.0 - WEDGE_BOSS_SKIRT)) / WEDGE_BOSS_SKIRT)
    dx = min(abs(x - kx) for kx in KEY_X)
    fx = 1.0 - _smoothstep((dx - WEDGE_BOSS_HALF) / WEDGE_BOSS_FADE)
    return SKIN + (WEDGE_BOSS_MARGIN - SKIN) * fz * fx


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
            break
        yc = ycut(x)
        # thin SKIN wall on the mating side, except a local boss at each key/bolt station
        inset = [(max(y, yc + wedge_boss_margin(hull, x, z)), z)   # TRUE SKIN wall all round
                 for (y, z) in offset_poly(sec, SKIN)]
        inset = repair_inset(inset, sec, SKIN)             # bridge the bottom-corner pinch
        if inset is None:
            break                                          # forward end: too thin to hollow
        ys = [p[0] for p in inset]
        zsv = [p[1] for p in inset]
        if (max(ys) - min(ys)) < 1.2 or (max(zsv) - min(zsv)) < 1.2:
            break                                          # too thin -> solid from here on
        if side < 0:
            inset = [(-y, z) for (y, z) in inset]
        xs.append(x)
        sections.append(inset)
    if len(xs) < 3:
        return None
    # Taper the forward end shut instead of stopping on a butt face. The old loop
    # `continue`d past thin stations and then lofted straight across the gap, which put
    # cavity where the wedge is a sliver; breaking + tapering leaves that tip solid.
    last = sections[-1]
    lcy = sum(p[0] for p in last) / len(last)
    lcz = sum(p[1] for p in last) / len(last)
    for f, dx in ((0.45, 0.5), (0.12, 1.0)):
        xs.append(xs[-1] + dx)
        sections.append([(lcy + (y - lcy) * f, lcz + (z - lcz) * f) for (y, z) in last])
    return to_trimesh(loft(np.array(xs), sections))


def build_bow(hull):
    # Main body lofts to x_nose; then a rounded nose rounds the last NOSE_ROUND inches.
    x_nose = LOA - NOSE_ROUND
    xs = list(np.linspace(BOW_SPLIT, x_nose, N_STN_BOW))
    sections = [bow_section(hull, x) for x in xs]
    base = sections[-1]                                  # full section at x_nose
    zlo = min(z for _, z in base)
    zhi = max(z for _, z in base)
    # z-anchor of the nose shrink. Rev-3.2c: anchored at the SHEER (NOSE_Z_ANCHOR=1) so
    # the deck edge -- and the flare it carries -- stays at full height to the very tip
    # (raked-stem look, sheds water); the keel side sweeps up into the stem. The old
    # mid-height anchor (0.5) pulled the deck edge down into a bullnose that read as
    # "rounding back" at the bow.
    za = zlo + NOSE_Z_ANCHOR * (zhi - zlo)
    # Homothetic shrink of the base section toward (0, za); a small final ring is ear-clip
    # capped -- that handles the section's concavity (flat deck + V) cleanly, whereas a
    # triangle-fan-to-apex overlaps on a non-convex section.
    for i in range(1, NOSE_RINGS + 1):
        f = i / NOSE_RINGS
        sc = max(NOSE_SC_MIN, (1.0 - f) ** NOSE_POW)
        xs.append(x_nose + NOSE_ROUND * f)
        sections.append([(y * sc, za + (z - za) * sc) for (y, z) in base])
    return loft(np.array(xs), sections)


def _bow_profile_hw(hull, x):
    """The bow's stbd outer half-width vs height at station x (z increasing): replicates
    bow_section's rail-fade + convex scaling + flare kick. Returns (zs, ys) arrays."""
    rail_f = min(1.0, max(0.0, (LOA - x) / BOW_RAIL_FADE))
    o = resample(bow_half_outer(hull, x, rail_f,
                                BOW_FLARE_HOLLOW * bow_flare_g(x)), NP)
    t = (x - BOW_SPLIT) / (LOA - BOW_SPLIT)
    sh0, sh1 = hull.interp(BOW_SPLIT)[2], hull.interp(LOA)[2]
    target = sh0 * (1 - t) + sh1 * t + BOW_CONVEX * np.sin(np.pi * t)
    cur = max(p[0] for p in o)
    if cur > 0.1:
        o = [(y * target / cur, z) for (y, z) in o]
    o = flare_kick(hull, x, o, BOW_FLARE_OUT * bow_flare_g(x))   # same order as bow_section
    return np.array([p[1] for p in o]), np.array([p[0] for p in o])


def flare_kicks_at(hull, x):
    """(raw, effective) outward sheer kick at station x in DESIGN inches -- i.e. before
    and after the stem guards in flare_out_at. Used by the reports and the renders so
    they quote the kick the hull actually carries, not the un-guarded BOW_FLARE_OUT*g."""
    rail_f = min(1.0, max(0.0, (LOA - x) / BOW_RAIL_FADE))
    o = resample(bow_half_outer(hull, x, rail_f, BOW_FLARE_HOLLOW * bow_flare_g(x)), NP)
    t = (x - BOW_SPLIT) / (LOA - BOW_SPLIT)
    sh0, sh1 = hull.interp(BOW_SPLIT)[2], hull.interp(LOA)[2]
    target = sh0 * (1 - t) + sh1 * t + BOW_CONVEX * np.sin(np.pi * t)
    cur = max(p[0] for p in o)
    if cur > 0.1:
        o = [(y * target / cur, z) for (y, z) in o]
    raw = BOW_FLARE_OUT * bow_flare_g(x)
    return raw, flare_out_at(hull, x, o, raw)


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


def bow_wall_at(hull, x):
    """Local bow shell-wall thickness (radial inset of the storage cavity) at station x.

    BOW_WALL everywhere EXCEPT over the interface flange span x = BOW_SPLIT ..
    BOW_SPLIT+FLANGE_T, where the wall is thickened to FLANGE_GAP+FLANGE_W so the
    bolt-grip bulkhead RING is produced by the same loft that hollows the shell.

    WHY: the ring used to be a separate solid unioned on (build_iface_flange), and its
    aft cap sat EXACTLY in the plane x=BOW_SPLIT -- coplanar with the shell's own aft
    face. manifold3d resolved that coincidence with ~36 zero-area triangles which, once
    the STL round-trips through float32, collapse into non-manifold edges; make_manifold
    then had to call pymeshfix, and pymeshfix bridged the thin nose shell and the storage
    opening with the big flat membranes seen on the foredeck. Building the ring INTO the
    cavity produces the identical solid (the ring's inner boundary IS this inset, the same
    offset taken off the same contour) with no boolean and no coplanar faces,
    so the repair pass has nothing left to patch."""
    if IFACE_FLANGE and BOW_SPLIT - EPS <= x <= BOW_SPLIT + FLANGE_T + EPS:
        return FLANGE_GAP + FLANGE_W
    return BOW_WALL


def build_bow_cavity(hull):
    """Solid for hollowing the bow into a uniform ~BOW_WALL shell that follows the FULL
    hull section -- so the V-bottom FLOOR gets hollowed too, not left solid. Each
    bow_section is offset inward by bow_wall_at(x) (that inset carries the
    interface flange ring, see bow_wall_at); lofted from ~1" AFT of the split (subtracting
    it opens the aft face for storage access) forward until the nose gets too thin to
    hollow, then tapered shut. Closed solid for the boolean."""
    x_nose = LOA - NOSE_ROUND
    # The forward taper below appends up to +3.6" past the last kept station, so stop the
    # scan early enough that the cavity closes BEFORE the nose rings begin (x_nose): the
    # rings shrink the hull toward the SHEER (NOSE_Z_ANCHOR), while the taper shrinks
    # toward the section centroid -- past x_nose those diverge and the cavity tip would
    # punch out through the underside of the raked stem (rev-3.2c bug: a slit at the tip).
    cav_end = x_nose - 3.7
    xs_scan = list(np.linspace(BOW_SPLIT, cav_end, N_STN_BOW + 10))
    if IFACE_FLANGE:
        # explicit stations either side of the ring's forward face so the wall STEPS back
        # to BOW_WALL there (this pair of rings is the ring's front annular face)
        xs_scan += [BOW_SPLIT + FLANGE_T, BOW_SPLIT + FLANGE_T + FLANGE_STEP]
        xs_scan = sorted(set(xs_scan))
    xs, sections = [], []
    for x in xs_scan:
        wall = bow_wall_at(hull, x)
        sec = bow_section(hull, x)
        inset = offset_inward(sec, wall)                  # TRUE wall, incl. under the deck
        if inset is None:
            break                                          # section too thin to hollow
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
    cav = to_trimesh(loft(np.array(xs), sections))
    if BULKHEAD:
        # Take the low part of the joint back OUT of the cavity -> the bow keeps solid
        # material there = its half of the bulkhead, and the storage opening gets a
        # BHD_TOP sill. The cutter starts well AFT of the cavity's own aft end
        # (BOW_SPLIT-1.2) so the difference leaves no face at x=BOW_SPLIT.
        import trimesh
        cav = cav.difference(bulkhead_cutter(hull, BOW_SPLIT - 2.5, BOW_SPLIT + BHD_T))
        trimesh.repair.fix_normals(cav)
    return cav


# ------------------------------------------------------------------
# INTERFACE FLANGE  (bolt-grip bulkhead ring at the bow/center joint, x=BOW_SPLIT)
# ------------------------------------------------------------------
def iface_contour(hull, x, piece):
    """The full closed outer section (y-z) of `piece` at station x: hull V both sides,
    up to the sheer, closed across the top by the deck line at sz. At x=BOW_SPLIT the
    center's and the bow's contours are the SAME curve (the hull outer half-section --
    no mating wall there, and the bow flare blends in from zero), which is why the
    two flange rings mate flush. Only the sampling differs."""
    if piece == "bow":
        return bow_section(hull, x)
    oh = center_outer_half(hull, x)                    # keel..gunwale top, stbd (y>=0)
    sz = hull.interp(x)[3]
    shw = oh[-1][0]
    deck = [(shw - 2.0 * shw * (i / (N_DECK + 1)), sz) for i in range(1, N_DECK + 1)]
    return list(oh) + deck + [(-y, z) for (y, z) in reversed(oh)][:-1]


def inset_contour(poly, d):
    """Shrink a closed (y,z) contour by a TRUE d -- perpendicular to the local edge, not
    toward the centroid (rev-3.4; see offset_poly for why the centroid version was wrong).
    Same vertex count, so the ring still lofts as a quad strip against `poly`. Returns
    None if d is too big for this section."""
    return offset_inward(poly, d)


def _poly_area(poly):
    a = 0.0
    for i in range(len(poly)):
        y0, z0 = poly[i]
        y1, z1 = poly[(i + 1) % len(poly)]
        a += y0 * z1 - y1 * z0
    return 0.5 * a


def loft_ring(xs, outers, inners, closed=True):
    """Closed manifold tube swept along xs from an (outer, inner) section pair.

    closed=True  -> the section is an ANNULUS (outer and inner are closed loops); used for
                    the BOW ring, whose section really is a closed hoop (it has a deck).
    closed=False -> the section is an open BAND: outer/inner are matching OPEN paths and
                    the band is closed off by a wall at each of the two path ends. Used for
                    the CENTER, which is an open tub -- its flange is a U, NOT a hoop, so
                    nothing spans the cockpit at deck height to block the bow dropping in.

    outers[k]/inners[k] must have the same, constant vertex count and index correspondence."""
    n = len(outers[0])
    m = 2 * n
    V = []
    for x, o, i in zip(xs, outers, inners):
        V += [(x, y, z) for (y, z) in o]
        V += [(x, y, z) for (y, z) in i]
    F = []
    last_j = n if closed else n - 1
    for k in range(len(xs) - 1):
        b0, b1 = k * m, (k + 1) * m
        for j in range(last_j):
            jn = (j + 1) % n
            F += [[b0 + j, b1 + jn, b0 + jn], [b0 + j, b1 + j, b1 + jn]]          # outer skin
            F += [[b0 + n + j, b0 + n + jn, b1 + n + jn],                          # inner bore
                  [b0 + n + j, b1 + n + jn, b1 + n + j]]
        if not closed:                                    # wall closing each open band end
            for j, flip in ((0, False), (n - 1, True)):
                a, bb, c, d = b0 + j, b1 + j, b1 + n + j, b0 + n + j
                F += ([[a, c, bb], [a, d, c]] if flip else [[a, bb, c], [a, c, d]])
    for b, flip in ((0, True), ((len(xs) - 1) * m, False)):                        # end caps
        for j in range(last_j):
            jn = (j + 1) % n
            a, bb, c, d = b + j, b + jn, b + n + jn, b + n + j
            F += ([[a, c, bb], [a, d, c]] if flip else [[a, bb, c], [a, c, d]])
    return V, F


def _center_band_idx(hull, x):
    """Indices into iface_contour(...,'center') that walk the HULL path only -- port sheer
    -> keel -> stbd sheer -- skipping the deck-line points. The center's flange follows
    this open path, so its ring is a U with nothing across the top."""
    k = len(center_outer_half(hull, x))
    total = k + N_DECK + (k - 1)
    return list(range(k + N_DECK, total)) + list(range(0, k))


def _contour_hw(poly, z):
    """Starboard half-width of a closed (y,z) contour at height z."""
    r = [p for p in poly if p[0] >= 0.0]
    zs = np.array([p[1] for p in r])
    ys = np.array([p[0] for p in r])
    o = np.argsort(zs)
    return float(np.interp(z, zs[o], ys[o]))


def flange_band(hull, z):
    """(y_inner, y_outer) of the flange ring material that BOTH rings share at height z,
    intersected over the whole flange x-span (the hull tapers, so the bow ring sits a
    little inboard of the center ring). A bolt centred in this band is buried in solid
    flange for its entire length. Returns None if the rings don't overlap at this z."""
    lo, hi = -1e9, 1e9
    spans = [("center", np.linspace(BOW_SPLIT - FLANGE_T, BOW_SPLIT, FLANGE_NX)),
             ("bow", np.linspace(BOW_SPLIT, BOW_SPLIT + FLANGE_T, FLANGE_NX))]
    for piece, xs in spans:
        for x in xs:
            base = iface_contour(hull, x, piece)
            oi = inset_contour(base, FLANGE_GAP + FLANGE_W)
            oo = inset_contour(base, FLANGE_GAP)
            if oi is None or oo is None:
                return None
            lo = max(lo, _contour_hw(oi, z))
            hi = min(hi, _contour_hw(oo, z))
    return (lo, hi) if hi - lo > 2.2 * BOLT_R else None


def build_iface_flange(hull, piece):
    """The bolt-grip bulkhead ring for `piece` at the bow/center interface.

      center -> occupies x = [BOW_SPLIT-FLANGE_T, BOW_SPLIT]
      bow    -> occupies x = [BOW_SPLIT, BOW_SPLIT+FLANGE_T]

    Neither crosses x=BOW_SPLIT, so the assembled pieces never interfere. The ring's
    outer boundary follows the piece's OWN local outer section (pulled FLANGE_GAP inside
    the skin) so nothing protrudes past the hull and the union always overlaps solid
    shell material; the inner boundary is that contour drawn FLANGE_W further inboard.
    Returns a closed watertight mesh (or None if the section is too small)."""
    if piece == "bow":
        xs = list(np.linspace(BOW_SPLIT, BOW_SPLIT + FLANGE_T, FLANGE_NX))
    else:
        xs = list(np.linspace(BOW_SPLIT - FLANGE_T, BOW_SPLIT, FLANGE_NX))
    outers, inners = [], []
    for x in xs:
        base = iface_contour(hull, x, piece)
        o = inset_contour(base, FLANGE_GAP)
        i = inset_contour(base, FLANGE_GAP + FLANGE_W)
        if o is None or i is None:
            return None
        ao, ai = _poly_area(o), _poly_area(i)
        if ao * ai <= 0 or abs(ai) >= abs(ao):        # inner flipped/ballooned -> unsafe
            return None
        if piece == "center":                         # drop the deck line -> open U band
            idx = _center_band_idx(hull, x)
            o = [o[j] for j in idx]
            i = [i[j] for j in idx]
        outers.append(o)
        inners.append(i)
    return to_trimesh(loft_ring(np.array(xs), outers, inners, closed=(piece == "bow")))


# ------------------------------------------------------------------
# BOTTOM BULKHEAD  (solid web closing the low part of the bow/center joint)
# ------------------------------------------------------------------
def bhd_z_top(hull):
    """Design z of the bulkhead's top edge AT THE SKIN = BHD_TOP real inches above the
    keel at the split. This is the high point of the arch; bhd_top_at() gives the local
    height anywhere across the beam. Solid web below, flange ring above."""
    return hull.interp(BOW_SPLIT)[5] + BHD_TOP / DESIGN_SCALE


def _bhd_profile(hull):
    """(z_top, y_edge): the arch's high point and the stbd half-width of the web there.
    Cached -- it costs an iface_contour + inset_contour and is asked for per vertex."""
    c = _bhd_profile._cache.get(id(hull))
    if c is None:
        o = inset_contour(iface_contour(hull, BOW_SPLIT, "center"), FLANGE_GAP)
        zt = bhd_z_top(hull)
        c = (zt, _contour_hw(o, zt) if o is not None else 0.0)
        _bhd_profile._cache[id(hull)] = c
    return c


_bhd_profile._cache = {}


def bhd_top_at(hull, y):
    """Design z of the bulkhead's top edge at beam y -- the arched sill. A raised cosine
    over the web's full half-width: BHD_TOP at the skin, falling BHD_DIP at y=0, and
    flat (zero slope) at both ends so it fairs into the hull with no corner."""
    zt, yw = _bhd_profile(hull)
    if BHD_DIP <= 0.0 or yw <= 0.0:
        return zt
    u = min(1.0, abs(y) / yw)
    return zt - (BHD_DIP / DESIGN_SCALE) * 0.5 * (1.0 + np.cos(np.pi * u))


def bhd_top_curve(hull, n=120):
    """The arched sill sampled across the beam, as (ys, zs) -- for the renders."""
    _, yw = _bhd_profile(hull)
    ys = np.linspace(-yw, yw, n)
    return ys, np.array([bhd_top_at(hull, y) for y in ys])


def clip_below_curve(poly, f, n=64):
    """Clip a closed (y,z) contour to the region z <= f(y), where f is a gentle
    single-valued curve of y. Sutherland-Hodgman first (the hull section crosses the
    sill exactly twice, so the result is one simple polygon closed by a straight chord),
    then that chord is replaced by n samples of f itself -- so the cut edge IS the arch,
    not a secant of it. The two chord endpoints are excluded from the resampling, so no
    duplicate/collinear vertex reaches ear_clip."""
    g = lambda y, z: z - f(y)
    out, cross = [], []
    m = len(poly)
    for i in range(m):
        y0, z0 = poly[i]
        y1, z1 = poly[(i + 1) % m]
        g0, g1 = g(y0, z0), g(y1, z1)
        if g0 <= 0.0:
            out.append((y0, z0))
        if (g0 <= 0.0) != (g1 <= 0.0):
            t = g0 / (g0 - g1)
            yc = y0 + t * (y1 - y0)
            out.append((yc, f(yc)))
            cross.append(len(out) - 1)
    if len(out) < 3 or len(cross) != 2:
        return None
    k = len(out)
    ci = next((i for i in cross if (i + 1) % k in cross), None)
    if ci is None:
        return None
    ya, yb = out[ci][0], out[(ci + 1) % k][0]
    arc = [(y, f(y)) for y in np.linspace(ya, yb, n + 2)[1:-1]]
    return out[:ci + 1] + arc + out[ci + 1:]


def build_bulkhead_center(hull):
    """The CENTER's half of the bulkhead: the center's own outer section at x=BOW_SPLIT
    (pulled FLANGE_GAP inside the skin so the union always overlaps solid shell and
    nothing protrudes past the hull) clipped to z <= bhd_z_top and extruded aft over
    x = [BOW_SPLIT-BHD_T, BOW_SPLIT]. Taken at BOW_SPLIT because the hull only WIDENS
    going aft, so the prism stays inside the shell over its whole span. Ear-clip capped
    (the section is non-convex -- the spray rail bulges out below the clip height), so a
    triangle fan would self-overlap. Returns None if the section is too small."""
    base = iface_contour(hull, BOW_SPLIT, "center")
    o = inset_contour(base, FLANGE_GAP)
    if o is None:
        return None
    poly = clip_below_curve(o, lambda y: bhd_top_at(hull, y))
    if poly is None:
        return None
    xs = np.array([BOW_SPLIT - BHD_T, BOW_SPLIT])
    return to_trimesh(loft(xs, [poly, poly]))


def bulkhead_cutter(hull, x0, x1, n=64):
    """Everything below the arched sill over x = [x0, x1]: a slab, wider than the hull,
    whose top edge follows bhd_top_at. Subtracted from the BOW's hollowing cavity, so the
    bow simply keeps its material there -- the bulkhead is lofted-in, never unioned on."""
    zt, yw = _bhd_profile(hull)
    z0 = hull.interp(BOW_SPLIT)[5] - 6.0
    ymax = 2.0 * max(st[3] for st in h2.STATIONS)
    poly = [(-ymax, z0), (ymax, z0), (ymax, zt)]
    poly += [(y, bhd_top_at(hull, y))                     # arch, endpoints excluded so no
             for y in np.linspace(yw, -yw, n + 2)[1:-1]]  # vertex lands on the flat ends
    poly += [(-ymax, zt)]
    return to_trimesh(loft(np.array([x0, x1]), [poly, poly]))


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

    def _pmf(mesh, joincomp=True):                       # one pymeshfix pass, C-stderr silenced
        v = np.ascontiguousarray(mesh.vertices, np.float64)
        f = np.ascontiguousarray(mesh.faces, np.int32)
        saved = os.dup(2); nul = os.open(os.devnull, os.O_WRONLY)
        os.dup2(nul, 2); os.close(nul)
        try:
            vc, fc = pymeshfix.clean_from_arrays(
                v, f, joincomp=joincomp, remove_smallest_components=False)
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
    #
    # The growth guard is separate and much tighter than the shrink one, because ADDING
    # volume is pymeshfix's signature failure here: joincomp=True bridges any deep narrow
    # slot or opening it decides is a crack. That is what put the flat membranes on the
    # rev-3.2 foredeck, and (rev-3.4) what was silently FILLING the centreline bow-key
    # channel in the center -- +8.8 in^3 on a 5080 in^3 tub, only 0.17%, so a symmetric
    # 3% test waved it straight through and the bow then had nowhere to seat its key.
    if not (m32.is_watertight and _nonmanifold_edge_count(m32) == 0):
        v0 = abs(m32.volume)
        worst = 0.0
        # joincomp=False FIRST: joining components is exactly the pass that bridges a
        # slot, and none of these pieces is meant to gain one.
        for joincomp in (False, True):
            vc, fc, _ = _pmf(m32, joincomp=joincomp)
            r = trimesh.Trimesh(vc, fc, process=True)
            trimesh.repair.fix_normals(r)
            dv = (abs(r.volume) - v0) / v0 if v0 > 0 else 0.0
            if r.is_watertight and _nonmanifold_edge_count(r) == 0 and -0.03 <= dv <= 1e-4:
                return r
            worst = max(worst, dv)
        if worst > 1e-4:
            print(f"  .. pymeshfix wanted to ADD {worst*v0:.2f} in^3 ({100*worst:.2f}%) to "
                  f"this piece -- that is a bridged slot, not a repair, so it is refused; "
                  f"keeping the full-precision mesh (the export-scale pass is the one that "
                  f"gates the .stl)")
        return m                                         # full precision, not the f32 sim
    return m32


# ------------------------------------------------------------------
# PRINT ORIENTATION  (scale models only)
# ------------------------------------------------------------------
def print_ready_transform(m, tol=0.3, max_slender=2.2, keep=120):
    """Rotation + drop that stands a piece on whichever face gives the biggest first-layer
    contact patch, tie-broken against falling over.

    A hull has no flat face, which does not matter for the real boat -- slice_for_print.py
    cuts it into bed-sized chunks and every chunk gets flat cut faces from the grid -- but
    a scale model is printed whole and has to sit on something. In the boat's own
    coordinates nothing does: the foredeck looks flat because BOW_CAMBER is 0, yet it
    carries the sheer spring, rising 2.5 design inches from the split to the stem. Laid
    deck-down at 1:10 the bow touches the plate over 2 mm^2 and stands 5 mm off it at the
    far end. Standing it on the x=BOW_SPLIT face is worse: the three key tongues reach
    BKEY_DEPTH proud of that plane, so it balances on them.

    Candidate down-directions are the convex hull's face normals, scored by the area that
    lands within `tol` of the plate. Anything taller than max_slender times its shortest
    footprint side is skipped as tippy, unless nothing else has any contact at all. The
    sheer is a curve, not a facet, so the residual is a fraction of a millimetre: use a
    brim or raft as well."""
    import trimesh
    h = m.convex_hull
    order = np.argsort(-h.area_faces)[:keep]
    best = (np.eye(4), -1.0, None)
    fallback = (np.eye(4), -1.0, None)
    seen = []
    for d in h.face_normals[order]:
        if any(float(np.dot(d, e)) > 0.999 for e in seen):
            continue
        seen.append(d)
        T = trimesh.geometry.align_vectors(d, [0.0, 0.0, -1.0])
        q = m.copy()
        q.apply_transform(T)
        T[2, 3] -= q.bounds[0][2]                       # drop it onto z = 0
        zc, nn, aa = q.triangles_center[:, 2], q.face_normals, q.area_faces
        area = float(aa[(nn[:, 2] < -0.9) & (zc < q.bounds[0][2] + tol)].sum())
        ext = q.extents
        if area > fallback[1]:
            fallback = (T, area, ext)
        if ext[2] > max_slender * min(ext[0], ext[1]):  # would print as a tower
            continue
        if area > best[1]:
            best = (T, area, ext)
    return best if best[1] > 0 else fallback


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


def _key_prism(hull, xk, s, clr=0.0):
    """The dovetail KEY for station xk, side s (+1 stbd / -1 port). Shape is shared by the
    tongue (clr=0, unioned into the wedge) and the socket cutter (clr=KEY_CLR, subtracted
    from the center) -- the cutter is the tongue grown clr on every face, so the two still
    mate on the same geometry but with a real gap instead of an interference fit.
    Vertical (extruded in z) so the wedge drops straight down onto it; the fore-aft
    flare KEY_BACK>KEY_MOUTH locks pull-apart. Socket open at the rim (z1=sz)."""
    yc = ycut(xk)
    kz, sz = hull.interp(xk)[5], hull.interp(xk)[3]
    z0 = waterline_z(hull) + 1.0 - clr              # above the waterline; floor relieved
    z1 = sz                                         # up to the rim -> open at top
    M, B, D, T = KEY_MOUTH / 2, KEY_BACK / 2, KEY_DEPTH, KEY_STUB
    poly = [(xk - M, s * (yc + T)), (xk + M, s * (yc + T)),   # stub out into the wedge
            (xk + M, s * yc), (xk + B, s * (yc - D)),         # mouth -> flared back
            (xk - B, s * (yc - D)), (xk - M, s * yc)]
    if clr > 0:
        poly = offset_poly(poly, -clr)              # grow every face outward by clr
    return _prism(poly, z0, z1)


def add_vertical_dovetails(hull, pieces):
    """Cut a flared socket in the center and add the matching tongue to each wedge, at
    every KEY_X / side. Center and wedge use the same prism, the center's grown by
    KEY_CLR -> they mate with a uniform gap instead of line-to-line. A
    backing boss is unioned into the center first so the socket has surrounding
    material. Returns the updated pieces dict. Keeps every piece watertight."""
    import trimesh
    out = dict(pieces)
    wedge_of = {+1: "wedge_stbd", -1: "wedge_port"}
    for xk in KEY_X:
        yc = ycut(xk)
        kz, sz = hull.interp(xk)[5], hull.interp(xk)[3]
        z0 = waterline_z(hull) + 1.0
        for s in (+1, -1):
            key = _key_prism(hull, xk, s)                    # the tongue, exact size
            socket = _key_prism(hull, xk, s, clr=KEY_CLR)    # ...grown -> the pocket
            # backing boss in the center wall around the socket
            yb0, yb1 = s * yc, s * (yc - (KEY_DEPTH + 0.4 + KEY_CLR))
            ext = [KEY_BACK + 1.2, abs(yb1 - yb0), (sz - (z0 - 0.3))]
            T = np.eye(4)
            T[:3, 3] = [xk, 0.5 * (yb0 + yb1), 0.5 * ((z0 - 0.3) + sz)]
            boss = trimesh.creation.box(extents=ext, transform=T)
            c = out["center"].union(boss).difference(socket)
            trimesh.repair.fix_normals(c)
            out["center"] = c
            w = out[wedge_of[s]].union(key)
            trimesh.repair.fix_normals(w)
            out[wedge_of[s]] = w
    return out


def _bow_key_poly(yk, mouth, back, clr=0.0):
    """Horizontal (x,y) section of a bow<->center key: a dovetail flared along X. Narrow
    mouth (+/-mouth) at the x=BOW_SPLIT face, widening to +/-back at x=BOW_SPLIT-BKEY_DEPTH
    (AFT, inside the center) -> the bow cannot be pulled forward. A BKEY_STUB stub runs
    forward of the face so the tongue has a root in the bow. Same vertex order as
    _key_prism, just with the roles of x and y swapped. clr>0 grows every face outward by
    clr -> the center-side channel, which is how the tongue gets a fit gap."""
    poly = [(BOW_SPLIT + BKEY_STUB, yk - mouth), (BOW_SPLIT + BKEY_STUB, yk + mouth),
            (BOW_SPLIT, yk + mouth), (BOW_SPLIT - BKEY_DEPTH, yk + back),
            (BOW_SPLIT - BKEY_DEPTH, yk - back), (BOW_SPLIT, yk - mouth)]
    return offset_poly(poly, -clr) if clr > 0 else poly


def _key_top(hull, yk, back):
    """Top of a key tongue that has to fill its channel right up through the bulkhead:
    the LOWEST point of the arched sill over the key's own footprint, held BKEY_TOP_GAP
    below it. Taking the minimum keeps the tongue from standing proud of the arch, and
    the gap keeps its cap out of the sill plane."""
    ys = np.linspace(yk - back, yk + back, 9)
    return min(bhd_top_at(hull, y) for y in ys) - BKEY_TOP_GAP


def bow_key_specs(hull):
    """The three drop-in keys on the bow/center face, sized against the ACTUAL local
    material (flange ring + sole), in design units. Each spec carries the key section plus
    the local backing boss that guarantees surrounding material for the socket."""
    specs = []

    # --- key 1: low centreline, below the waterline, standing on the sole ---
    sole = max(thick_floor_inner(hull, x)[0][1]                 # cockpit sole top, y=0
               for x in (BOW_SPLIT - BKEY_DEPTH - BKEY_BOSS, BOW_SPLIT))
    z0 = max(BKEY_CTR_Z0, sole + 0.35)
    if BULKHEAD:
        # The key now lives INSIDE the bulkhead, so it needs no boss of its own (there is
        # solid web all round it) and it is run the full height of the web: the center's
        # socket is cut as a full-height channel, so a short tongue would leave that
        # channel open through the top of the bulkhead.
        specs.append(dict(
            name="centre", yk=0.0, mouth=BKEY_CTR_MOUTH, back=BKEY_CTR_BACK,
            z0=z0, z1=_key_top(hull, 0.0, BKEY_CTR_BACK), boss_y=None, boss_z=None))
    else:
        specs.append(dict(
            name="centre", yk=0.0, mouth=BKEY_CTR_MOUTH, back=BKEY_CTR_BACK,
            z0=z0, z1=z0 + BKEY_CTR_H,
            boss_y=(-(BKEY_CTR_BACK + BKEY_BOSS), BKEY_CTR_BACK + BKEY_BOSS),
            boss_z=(min(sole - 0.2, z0 - BKEY_SILL - 0.4), z0 + BKEY_CTR_H + BKEY_BOSS)))

    # --- keys 2+3: one per side at mid-height, inside the flange ring ---
    z0 = BKEY_SIDE_Z0
    band = flange_band(hull, z0)                                # narrowest point of the key
    if band is not None:
        y_out = band[1] - BKEY_SIDE_EDGE                        # stay inside the skin
        yk = y_out - BKEY_SIDE_BACK
        z1 = z0 + BKEY_SIDE_H
        if BULKHEAD:                            # run them up to the top of the web too,
            z1 = max(z1, _key_top(hull, yk, BKEY_SIDE_BACK))   # so their channels fill it
        for s in (+1, -1):
            specs.append(dict(
                name=f"side{'S' if s > 0 else 'P'}", yk=s * yk,
                mouth=BKEY_SIDE_MOUTH, back=BKEY_SIDE_BACK,
                z0=z0, z1=z1,
                # boss grows INBOARD only -- outboard is the hull skin, which must not move
                boss_y=tuple(sorted((s * y_out,
                                     s * (yk - BKEY_SIDE_BACK - BKEY_BOSS)))),
                boss_z=(z0 - BKEY_SILL - 0.4, z1 + BKEY_BOSS)))
    return specs


def _key_boss(spec, x0, x1):
    """Local backing block for one key, spanning x0..x1."""
    import trimesh
    y0, y1 = spec["boss_y"]
    z0, z1 = spec["boss_z"]
    T = np.eye(4)
    T[:3, 3] = [0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1)]
    return trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0], transform=T)


def add_bow_keys(hull, pieces):
    """Cut a full-height flared channel in the CENTER and add the matching tongue to the
    BOW at every key station. Center and bow use the same prism section, the center's
    grown by KEY_CLR -> a uniform fit gap. A backing boss is unioned into each piece
    FIRST so the socket is surrounded
    by material and never reaches the watertight skin. Returns (pieces, specs)."""
    import trimesh
    out = dict(pieces)
    sz = hull.interp(BOW_SPLIT)[3]
    for spec in bow_key_specs(hull):
        poly = _bow_key_poly(spec["yk"], spec["mouth"], spec["back"])
        chan_poly = _bow_key_poly(spec["yk"], spec["mouth"], spec["back"], clr=KEY_CLR)
        has_boss = spec["boss_y"] is not None      # a key buried in the bulkhead needs none
        # CENTER: boss, then a channel open at the rim so the tongue can ride down it
        chan = _prism(chan_poly, spec["z0"] - BKEY_SILL - KEY_CLR, sz + 1.0)
        c = out["center"]
        if has_boss:
            c = c.union(_key_boss(spec, BOW_SPLIT - BKEY_DEPTH - BKEY_BOSS, BOW_SPLIT))
        c = c.difference(chan)
        trimesh.repair.fix_normals(c)
        out["center"] = c
        # BOW: boss, then the tongue (only its working z-band)
        tongue = _prism(poly, spec["z0"], spec["z1"])
        b = out["bow"]
        if has_boss:
            b = b.union(_key_boss(spec, BOW_SPLIT, BOW_SPLIT + BKEY_STUB + BKEY_BOSS))
        b = b.union(tongue)
        trimesh.repair.fix_normals(b)
        out["bow"] = b
    return out, bow_key_specs(hull)


def min_key_undercut():
    """The smallest dovetail undercut on the boat, in design inches.

    This is the HARD CEILING on any fit gap. Clearance grows the socket on every face, so
    it eats undercut 1:1; once the gap reaches the undercut the socket is wider at its
    mouth than the tongue is at its back and the key lifts straight out -- it stops being
    a dovetail at all. It also does not scale: the undercut shrinks with the model while a
    'scaled-up' clearance does not, which is exactly the trap this guards."""
    u = [(KEY_BACK - KEY_MOUTH) / 2]
    if BOW_KEYS:
        u += [BKEY_CTR_BACK - BKEY_CTR_MOUTH, BKEY_SIDE_BACK - BKEY_SIDE_MOUTH]
    return min(u)


def check_pods_sealed(hull):
    """Worst hole-into-cavity overlap for the wedge bolts, in^3 REAL. Must be zero: each
    one is a blind hole in a sealed buoyancy pod. Nothing else in this file can catch a
    breach -- watertight and manifold both stay True when a hole opens into an internal
    void -- so this is the check that has to be run."""
    cav = build_wedge_cavity(hull, +1)
    if cav is None:
        return 0.0
    worst = 0.0
    for x in BOLT_WEDGE_X:
        yc = ycut(x)
        for below in BOLT_WEDGE_BELOW:
            z = hull.interp(x)[3] - below
            cyl = _bolt_cyl([x, yc - BOLT_WEDGE_IN, z], [x, yc + BOLT_WEDGE_OUT, z])
            worst = max(worst, cav.intersection(cyl).volume)
    return worst * DESIGN_SCALE ** 3


def check_key_sweep(pieces, n=7, lift=26.0):
    """Assembly-path check: lift the finished bow straight up in n steps from seated to
    fully clear and boolean-intersect it with the finished center at each step. Every step
    must be ~zero volume, or some tongue/boss fouls the center on the way down. Returns
    (max_overlap_in3, at_dz)."""
    worst, at, steps = -1.0, 0.0, []
    for dz in np.linspace(0.0, lift, n):
        b = pieces["bow"].copy()
        b.apply_translation([0.0, 0.0, dz])
        try:
            inter = pieces["center"].intersection(b)
            v = 0.0 if (inter.is_empty or len(inter.faces) == 0) else abs(inter.volume)
        except Exception:
            v = 0.0                                   # empty boolean -> no overlap
        if not np.isfinite(v):
            v = 0.0
        steps.append((dz, v))
        if v > worst:
            worst, at = v, dz
    return max(worst, 0.0), at, steps


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
        if IFACE_FLANGE:
            band = flange_band(hull, z)
            if band is not None:
                ym = 0.5 * (band[0] + band[1])              # centre of the shared flange ring
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


def transom_pad_thick_at(y, z, z_ledge):
    """Total transom thickness the clamp pad aims for at (y, z): TRANSOM_PAD_THICK over the
    pad, smoothstepping down to just inside the base slab in y (outboard of TRANSOM_PAD)
    and in z (below the notch ledge). Both fades are C1, so the pad reads as a moulded lens
    on the inside of the transom rather than a bonded-on block."""
    fy = 1.0 - _smoothstep((abs(y) - TRANSOM_PAD) / TRANSOM_BLEND)
    fz = _smoothstep((z - (z_ledge - TRANSOM_PAD_DROP - TRANSOM_PAD_FADE))
                     / TRANSOM_PAD_FADE)
    base = TRANSOM_THICK - TRANSOM_PAD_BURY
    return base + (TRANSOM_PAD_THICK - base) * fy * fz


def build_transom_pad(hull, ny=61, nz=29):
    """The outboard clamp pad: a closed grid solid whose forward face is the height field
    transom_pad_thick_at(y, z) and whose back face is buried inside the slab. Unioned into
    the center AFTER build_transom, BEFORE the notch is cut (so the notch goes through the
    pad too and leaves the two clamp landings either side of it)."""
    import trimesh
    kz = hull.interp(0.0)[5]
    sz = hull.interp(0.0)[3]
    z_ledge = kz + NOTCH_TOP / DESIGN_SCALE
    ys = np.linspace(-(TRANSOM_PAD + TRANSOM_BLEND), TRANSOM_PAD + TRANSOM_BLEND, ny)
    # stop a hair below the sheer so the pad's top face is NOT coplanar with the transom's
    z0 = z_ledge - TRANSOM_PAD_DROP - TRANSOM_PAD_FADE
    zs = np.linspace(z0, sz - 0.02, nz)
    x_back = 0.15                                           # inside the slab, ahead of x=0
    V = []
    for y in ys:                                            # front face, then back face
        for z in zs:
            V.append((transom_pad_thick_at(y, z, z_ledge), y, z))
    for y in ys:
        for z in zs:
            V.append((x_back, y, z))
    N = ny * nz
    idx = lambda i, j, back: (N if back else 0) + i * nz + j
    F = []
    quad = lambda a, b, c, d: F.extend(([a, b, c], [a, c, d]))
    for i in range(ny - 1):
        for j in range(nz - 1):
            quad(idx(i, j, 0), idx(i, j + 1, 0), idx(i + 1, j + 1, 0), idx(i + 1, j, 0))
            quad(idx(i, j, 1), idx(i + 1, j, 1), idx(i + 1, j + 1, 1), idx(i, j + 1, 1))
    for i in range(ny - 1):                                 # bottom / top edge walls
        quad(idx(i, 0, 0), idx(i + 1, 0, 0), idx(i + 1, 0, 1), idx(i, 0, 1))
        quad(idx(i, nz - 1, 0), idx(i, nz - 1, 1), idx(i + 1, nz - 1, 1), idx(i + 1, nz - 1, 0))
    for j in range(nz - 1):                                 # port / stbd edge walls
        quad(idx(0, j, 0), idx(0, j, 1), idx(0, j + 1, 1), idx(0, j + 1, 0))
        quad(idx(ny - 1, j, 0), idx(ny - 1, j + 1, 0), idx(ny - 1, j + 1, 1), idx(ny - 1, j, 1))
    m = trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F, int), process=True)
    trimesh.repair.fix_normals(m)
    return m


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

    x0, x1 = -0.5, max(TRANSOM_THICK, TRANSOM_PAD_THICK) + 0.5   # through slab AND pad
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
             [s * waterline_z(hull) for _ in xs],
             "b--", lw=1.2, label=f"waterline ({WATERLINE:.1f}\" @ {DESIGN_LOAD_LB:.0f} lb)")
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
    ax2.axhline(s * waterline_z(hull),
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


# ------------------------------------------------------------------
# HYDROSTATICS  (displacement vs waterplane -> the derived waterline)
# ------------------------------------------------------------------
def _env_profile(hull, x):
    """Outer ENVELOPE half-profile (zs ascending, ys) at design station x -- the surface
    the water actually sees, not the printed material. Aft of the split that is the raw
    hull section; forward of it the bow's own profile, which carries the plan taper, the
    convexity and the flare that bow_section applies on top of the base lines."""
    if x <= BOW_SPLIT:
        o = hull.half_outer(x)
        return np.array([p[1] for p in o]), np.array([p[0] for p in o])
    return _bow_profile_hw(hull, x)


def _env_stations(hull, n=240):
    """Cached (xs, profiles) for the whole envelope -- the bisection below asks for these
    a few dozen times and _bow_profile_hw is not cheap."""
    c = _env_stations._cache.get((id(hull), n))
    if c is None:
        xs = np.linspace(0.0, LOA - 0.5, n)
        c = (xs, [_env_profile(hull, x) for x in xs])
        _env_stations._cache[(id(hull), n)] = c
    return c


_env_stations._cache = {}


def displacement_lb(hull, z, n=240):
    """Displacement in REAL pounds with the static waterplane at DESIGN height z.
    Immersed half-section area is integrated over height at each station, doubled for
    both sides, integrated over the length, then scaled by DESIGN_SCALE**3."""
    xs, profs = _env_stations(hull, n)
    area = []
    for (zs, ys) in profs:
        zlo = zs.min()
        if z <= zlo:
            area.append(0.0)
            continue
        zz = np.linspace(zlo, min(z, zs.max()), 60)
        area.append(2.0 * np.trapezoid(np.interp(zz, zs, ys), zz))
    return float(np.trapezoid(area, xs)) * DESIGN_SCALE ** 3 * WATER_LB_PER_IN3


def waterplane_for_load(hull, lb, n=240):
    """Design z of the waterplane that displaces `lb`. Plain bisection -- displacement is
    monotonic in z, and 60 halvings of a 24" bracket is well past float precision."""
    xs, profs = _env_stations(hull, n)
    lo = min(zs.min() for (zs, _) in profs)
    hi = max(zs.max() for (zs, _) in profs)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if displacement_lb(hull, mid, n) < lb:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


_WATERLINE_Z = None      # design z of the derived waterplane (set by set_waterline_from_load)


def set_waterline_from_load(hull, lb=None):
    """Solve for the static waterplane at `lb` all-up and adopt it as THE waterline for
    every rule in this file. Also refreshes WATERLINE so labels and printouts quote the
    derived number rather than the old literal."""
    global _WATERLINE_Z, WATERLINE
    _WATERLINE_Z = waterplane_for_load(hull, DESIGN_LOAD_LB if lb is None else lb)
    WATERLINE = (_WATERLINE_Z - hull.interp(BOW_SPLIT)[5]) * DESIGN_SCALE
    return _WATERLINE_Z


def waterline_z(hull):
    """Design z of the static waterplane -- a HORIZONTAL plane.

    The old code took "WATERLINE inches above the LOCAL keel" at every station, but the
    keel carries ~13" of rocker, so that surface is not a waterline at all: amidships it
    sat ~1" BELOW the real one, which made the "above the waterline" rules there quietly
    too lax. Everything now references this single plane instead."""
    if _WATERLINE_Z is not None:
        return _WATERLINE_Z
    return hull.interp(BOW_SPLIT)[5] + WATERLINE / DESIGN_SCALE


def report_hydrostatics(hull, hull_lb):
    """Draft / displacement table for the real boat, and what the derived waterline and
    the bulkhead sill actually correspond to in pounds. Static, level trim, upright."""
    s = DESIGN_SCALE
    wz = waterline_z(hull)
    sheer = hull.interp(BOW_SPLIT)[3] * s
    print(f"\nHydrostatics (real boat, fresh water @ {WATER_LB_PER_IN3} lb/in^3, "
          f"static + level trim):")
    print(f"  DESIGN_LOAD_LB = {DESIGN_LOAD_LB:.0f} lb all-up  ->  waterplane at "
          f"z = {wz*s:.2f}\" real  ->  WATERLINE = {WATERLINE:.2f}\"")
    print(f"  {'all-up lb':>10}  {'waterplane z':>13}  {'freeboard':>10}  "
          f"{'vs sill @skin':>13}  {'vs sill @ctr':>12}")
    zt = bhd_z_top(hull) * s if BULKHEAD else None
    zc = bhd_top_at(hull, 0.0) * s if BULKHEAD else None
    loads = [hull_lb, hull_lb + 200, hull_lb + 400, DESIGN_LOAD_LB,
             hull_lb + 600, hull_lb + 750, hull_lb + 900]
    for lb in sorted(set(round(v) for v in loads)):
        z = waterplane_for_load(hull, lb) * s
        tag = "  <- DESIGN_LOAD" if abs(lb - DESIGN_LOAD_LB) < 1 else \
              ("  <- bare hull" if abs(lb - hull_lb) < 1 else "")
        cols = f"  {lb:10.0f}  {z:12.2f}\"  {sheer-z:9.1f}\""
        if BULKHEAD:
            cols += f"  {zt-z:+12.1f}\"  {zc-z:+11.1f}\""
        print(cols + tag)
    print(f"  reserve: bare hull floats at {waterplane_for_load(hull, hull_lb)*s:.2f}\"; "
          f"swamped to the sheer ({sheer:.1f}\") it would displace "
          f"{displacement_lb(hull, sheer/s):.0f} lb")
    if BULKHEAD:
        print(f"  the {BHD_TOP:.0f}\" sill is reached at {displacement_lb(hull, zt/s):.0f} lb "
              f"all-up; the {BHD_TOP-BHD_DIP:.0f}\" centreline dip at "
              f"{displacement_lb(hull, zc/s):.0f} lb")
    print("  (level trim assumed. Crew aft trims the stern down, but the joint is at "
          f"x={BOW_SPLIT*s:.0f}\" of {LOA*s:.0f}\" -- forward of amidships -- so it GAINS "
          "margin in that case.)")


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


def _volume_below(m, z):
    """Material volume of `m` below height z, by boolean. Falls back to the whole volume."""
    import trimesh
    lo, hi = m.bounds
    if z <= lo[2]:
        return 0.0
    if z >= hi[2]:
        return float(m.volume)
    box = trimesh.creation.box(bounds=np.array(
        [[lo[0] - 1, lo[1] - 1, lo[2] - 1], [hi[0] + 1, hi[1] + 1, z]]))
    try:
        return float(m.intersection(box).volume)
    except Exception:
        return float(m.volume)


def estimate_weight(reals, wl):
    """Rough built weight of the full-size ASA-printed + fiberglassed boat (REAL meshes).
    Print mass = SKIN (area*perimeter, ~solid) + INFILL (rest of volume * the zoned rate).
    Glass mass = zoned area * the per-zone schedule areal weights. `wl` is the real-scale
    waterline height that splits the two infill zones."""
    IN3_TO_CM3, IN2_TO_M2 = 16.387064, 0.00064516
    perim_in = PERIM_SHELL / 25.4
    print(f"\nWeight estimate (full size):  [ASA {ASA_DENSITY} g/cm^3, skin {PERIM_SHELL:.1f} mm, "
          f"infill {INFILL:.0%} below the waterline / {INFILL_TOPSIDE:.0%} above "
          f"| glass kg/m^2: bot {GLASS_BOTTOM} side {GLASS_TOPSIDE} "
          f"deck {GLASS_DECK} in {GLASS_INSIDE}]")
    print(f"  {'piece':12} {'skin':>6} {'infill':>7} {'glass':>6} {'total kg':>9}")
    tot = 0.0
    for name, m in reals.items():
        perim_vol = min(m.volume, m.area * perim_in)
        skin = perim_vol * IN3_TO_CM3 * ASA_DENSITY / 1000.0
        core = max(0.0, m.volume - perim_vol)                 # what the lattice fills
        f_lo = (_volume_below(m, wl) / m.volume
                if (name in INFILL_ZONED and m.volume > 0) else 0.0)
        rate = INFILL * f_lo + INFILL_TOPSIDE * (1.0 - f_lo)  # volume-weighted zone blend
        infl = core * IN3_TO_CM3 * ASA_DENSITY * rate / 1000.0
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


def _shaded_mesh(ax, m, base="#6DC8EC", light=(0.45, 0.75, 0.5), alpha=1.0):
    """Draw EVERY face of m with simple diffuse shading -- unlike _add_mesh (which drops
    half the faces for speed) this renders a solid surface, so concave curvature reads."""
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import matplotlib.colors as mc
    L = np.array(light, float); L /= np.linalg.norm(L)
    sh = np.clip(np.einsum('ij,j->i', m.face_normals, L), 0.0, 1.0)
    rgb = np.array(mc.to_rgb(base))
    cols = np.clip(0.25 + 0.85 * sh[:, None], 0, 1) * rgb[None, :]
    tris = m.vertices[m.faces]
    pc = Poly3DCollection(tris, facecolors=np.clip(cols, 0, 1), edgecolor="none",
                          alpha=alpha)
    pc.set_zsort("average")
    ax.add_collection3d(pc)


def render_bow_flare(hull, out_path):
    """Half-sections (y vs z, REAL inches) at 4 bow stations for four flare strengths,
    with the spray rail, the flare start f=F0 and the 7" waterline marked. The straight
    (OUT=0) case is the dashed reference: everything at/below the rail lies exactly on
    top of it, and the topside above it swings progressively outboard to a wider deck
    edge -- bowing INSIDE the rail->sheer chord (thin grey) = the concave panel."""
    import matplotlib.pyplot as plt
    s = DESIGN_SCALE
    stations = (66.0, 78.0, 90.0, 100.0)
    variants = ((0.0, "--", 1.6, "#9aa4ae", "OUT 0.0 (straight flare)"),
                (1.0, "-", 1.7, "#5fa8d3", "OUT 1.0"),
                (BOW_FLARE_OUT, "-", 2.6, "#0b6fa4",
                 f"OUT {BOW_FLARE_OUT:.2f} (THIS BUILD)"),
                (2.25, ":", 2.2, "#c0392b", "OUT 2.25"))

    fig, axes = plt.subplots(2, 4, figsize=(20, 11.5))
    for col_i, x in enumerate(stations):
        bhw, cz, shw, sz, dr, kz = hull.interp(x)
        first = (col_i == 0)
        z0 = cz + BOW_FLARE_F0 * (sz - cz)                 # flare start (just above rail)
        for row, ax in enumerate(axes[:, col_i]):
            for OUT, ls, lw, col, lab in variants:
                half = bow_section(hull, x, out=OUT * bow_flare_g(x))[:NP]  # keel..sheer
                ax.plot([s * p[0] for p in half], [s * p[1] for p in half],
                        ls, lw=lw, color=col, label=lab if first and row == 0 else None)
                if OUT == BOW_FLARE_OUT:                   # rail->sheer chord of the build
                    zs = [p[1] for p in half]
                    y0 = float(np.interp(z0, zs, [p[0] for p in half]))
                    ax.plot([s * y0, s * half[-1][0]], [s * z0, s * half[-1][1]],
                            "-", lw=0.9, color="#444",
                            label="rail->sheer chord (panel is hollow inside it)"
                            if first and row == 0 else None)
                    sheer_y, sheer_z = half[-1]
            z_rail = cz + h2.SPRAY_RAIL_HEIGHT_FRAC * (sz - cz)
            ax.axhline(s * z_rail, color="#e08a00", lw=1.0, ls="-.",
                       label="spray rail" if first and row == 0 else None)
            ax.axhline(s * z0, color="#e08a00", lw=0.7, ls=":",
                       label="flare starts (f=%.2f)" % BOW_FLARE_F0
                       if first and row == 0 else None)
            ax.axhline(s * waterline_z(hull), color="#1f77b4", lw=1.2, ls="--",
                       label=f'waterline ({WATERLINE:.1f}" @ {DESIGN_LOAD_LB:.0f} lb)'
                       if first and row == 0 else None)
            ax.axhline(s * cz, color="#bbb", lw=0.7)
            ax.set_aspect("equal")
            ax.grid(alpha=0.22)
            if row == 1:                                   # zoom on the flared panel
                base = bow_section(hull, x, out=0.0)[:NP]
                y_rail = float(np.interp(z_rail, [p[1] for p in base],
                                         [p[0] for p in base]))
                y_hi = sheer_y + max(0.0, 2.25 - BOW_FLARE_OUT) * bow_flare_g(x)
                pad = 0.9
                ax.set_ylim(s * (z_rail - pad), s * (sz + pad))
                ax.set_xlim(s * (min(y_rail, y_hi) - 2.2 * pad), s * (y_hi + pad))
                ax.set_xlabel("half-beam y (real in)")
                ax.set_title("zoom: rail -> deck edge", fontsize=9)
            else:
                raw_kick, kick = flare_kicks_at(hull, x)   # before / after the stem guards
                guard = "" if abs(raw_kick - kick) < 1e-9 else \
                    f" (raw {s*raw_kick:.2f}\", nose fade x{kick/max(raw_kick,1e-9):.2f})"
                ax.set_title(f"x = {x:.0f} design  ({s*x:.0f}\" real)\n"
                             f"g = {bow_flare_g(x):.3f}   sheer +{s*kick:.2f}\" real{guard}\n"
                             f"hollow {s*chord_hollow(hull, x):.2f}\"",
                             fontsize=10, fontweight="bold")
    axes[0, 0].set_ylabel("height z (real in)")
    axes[1, 0].set_ylabel("height z (real in)")
    axes[0, 0].legend(fontsize=8, loc="upper left")
    fig.suptitle("Flared bow -- the SHEER kicks outboard (concavity comes from the "
                 "curvature of the kick, not from carving material away).\n"
                 "Spray rail and everything below it are untouched; the whole flare is "
                 "ZERO at the x=60 split.", fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(str(out_path), dpi=140, bbox_inches="tight")
    plt.close()


def _bow_deck_edge(hull, out_val, n=56):
    """The starboard deck-edge (sheer) line of the bow as built, for flare strength
    out_val, INCLUDING the rounded nose rings -- so the plan outline is the real one."""
    x_nose = LOA - NOSE_ROUND
    xs = list(np.linspace(BOW_SPLIT, x_nose, n))
    secs = [bow_section(hull, x, out=out_val * bow_flare_g(x)) for x in xs]
    pts = [(x, sec[NP - 1][0], sec[NP - 1][1]) for x, sec in zip(xs, secs)]
    base = secs[-1]
    zc = 0.5 * (min(z for _, z in base) + max(z for _, z in base))
    ye, ze = base[NP - 1]
    for i in range(1, NOSE_RINGS + 1):                     # homothetic nose shrink
        f = i / NOSE_RINGS
        sc = max(NOSE_SC_MIN, (1.0 - f) ** NOSE_POW)
        pts.append((x_nose + NOSE_ROUND * f, ye * sc, zc + (ze - zc) * sc))
    return pts


def render_bow_flare_3d(hull, bow, out_path):
    """Three views that make the flare READ:
      (a) bow-on from dead ahead, camera just below deck level -> the topsides splay out
          as they rise and the deck edge overhangs;
      (b) forward quarter at deck height -> the concave panel under the deck edge;
      (c) plan view of the foredeck outline, flared vs straight overlaid.
    In (a)/(b) the grey dashed line is where the deck edge WAS with a straight flare."""
    import matplotlib.pyplot as plt
    s = DESIGN_SCALE
    lo, hi = bow.bounds
    edge_new = _bow_deck_edge(hull, BOW_FLARE_OUT)
    edge_old = _bow_deck_edge(hull, 0.0)

    def edges(ax, both_sides):
        for pts, col, ls, lw, lab in ((edge_old, "#e04b2a", "--", 1.9,
                                       "straight-flare deck edge (was)"),
                                      (edge_new, "#0b3d5c", "-", 2.4,
                                       f"flared deck edge (OUT={BOW_FLARE_OUT:.2f})")):
            for sgn in ((1, -1) if both_sides else (1,)):
                ax.plot([p[0] for p in pts], [sgn * p[1] for p in pts],
                        [p[2] for p in pts], ls, color=col, lw=lw,
                        label=lab if sgn == 1 else None)

    def setup(ax, ylim, elev, azim, zoom):
        ax.set_xlim(lo[0] - 1, hi[0] + 1)
        ax.set_ylim(*ylim)
        ax.set_zlim(lo[2] - 1, hi[2] + 1)
        ax.view_init(elev=elev, azim=azim)
        ax.set_box_aspect([hi[0] - lo[0], ylim[1] - ylim[0], hi[2] - lo[2]], zoom=zoom)
        ax.set_axis_off()

    fig = plt.figure(figsize=(21, 7.4))

    # (a) dead ahead, camera a little below the deck. The head-on SILHOUETTE is set by
    # the (unflared) x=60 aft face, so the flare is shown by overlaying the body plan:
    # at each forward station the flared section (blue) stands outboard of the straight
    # one (red) at the deck and bows inside the chord below it.
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    ax = fig.add_subplot(1, 3, 1, projection="3d")
    ax.set_proj_type("ortho")
    for xst in (66.0, 72.0, 78.0, 84.0, 90.0, 96.0, 102.0):
        h_new = bow_section(hull, xst, out=BOW_FLARE_OUT * bow_flare_g(xst))[:NP]
        h_old = bow_section(hull, xst, out=0.0)[:NP]
        # the sliver the flare ADDS, both sides -> the kick is visible even where the
        # two curves are only a fraction of an inch apart
        poly = [(xst, y, z) for (y, z) in h_new] + \
               [(xst, y, z) for (y, z) in reversed(h_old)]
        for sgn in (1, -1):
            ax.add_collection3d(Poly3DCollection(
                [[(x, sgn * y, z) for (x, y, z) in poly]],
                facecolor="#0b6fa4", alpha=0.55, edgecolor="none"))
        for half, col, ls, lw in ((h_old, "#e04b2a", "--", 1.3),
                                  (h_new, "#0b3d5c", "-", 2.0)):
            ys = [p[0] for p in half] + [-p[0] for p in reversed(half)]
            zs = [p[1] for p in half] + [p[1] for p in reversed(half)]
            ax.plot([xst] * len(ys), ys, zs, ls, color=col, lw=lw)
    edges(ax, True)
    setup(ax, (-22, 22), elev=5, azim=2, zoom=1.3)
    ax.set_title("(a) Bow-on, dead ahead, camera just below deck level\n"
                 "body plan x=66..102 (ortho): every topside splays OUT as it rises;\n"
                 "shaded sliver = width the flare ADDS, widest at the deck edge",
                 fontsize=10, fontweight="bold")
    ax.legend(fontsize=8, loc="lower center")

    # (b) forward quarter, deck height
    ax = fig.add_subplot(1, 3, 2, projection="3d")
    ax.computed_zorder = False            # draw the guide lines ON TOP of the solid
    _shaded_mesh(ax, bow, "#8fbcd9", light=(0.34, 0.64, 0.69))
    pts = edge_new                                 # only the flared edge is visible here
    ax.plot([p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts],
            "-", color="#0b3d5c", lw=2.4, label="flared deck edge (overhangs the panel)")
    rail = []                                        # spray-rail line = bottom of the panel
    for x in np.linspace(BOW_SPLIT, LOA - NOSE_ROUND, 40):
        cz, sz = hull.interp(x)[1], hull.interp(x)[3]
        zr = cz + h2.SPRAY_RAIL_HEIGHT_FRAC * (sz - cz)
        half = bow_section(hull, x)[:NP]
        rail.append((x, float(np.interp(zr, [p[1] for p in half],
                                        [p[0] for p in half])), zr))
    ax.plot([p[0] for p in rail], [p[1] for p in rail], [p[2] for p in rail],
            "-", color="#e08a00", lw=2.0, label="spray rail (untouched by the flare)")
    setup(ax, (-22, 22), elev=8, azim=38, zoom=1.5)
    ax.set_title("(b) Forward quarter, deck height\n"
                 "the shadowed panel between spray rail and deck edge is the concavity",
                 fontsize=10, fontweight="bold")
    ax.legend(fontsize=8, loc="lower left")

    # (c) plan view of the foredeck outline (real inches)
    ax = fig.add_subplot(1, 3, 3)
    xs_n = [s * p[0] for p in edge_new]
    ys_n = [s * p[1] for p in edge_new]
    xs_o = [s * p[0] for p in edge_old]
    ys_o = [s * p[1] for p in edge_old]
    ax.fill_between(xs_n, ys_n, [-y for y in ys_n], color="#0b6fa4", alpha=0.16, lw=0)
    ax.plot(xs_n, ys_n, "-", color="#0b3d5c", lw=2.4, label="flared foredeck")
    ax.plot(xs_n, [-y for y in ys_n], "-", color="#0b3d5c", lw=2.4)
    ax.plot(xs_o, ys_o, "--", color="#e04b2a", lw=1.9, label="straight flare")
    ax.plot(xs_o, [-y for y in ys_o], "--", color="#e04b2a", lw=1.9)
    ax.axvline(s * BOW_SPLIT, color="#888", lw=1.0, ls=":")
    ax.text(s * BOW_SPLIT + 0.4, 0.0, "x=60 split\n(flare = 0, faces mate)",
            fontsize=8, va="center", color="#555")
    imax = max(range(len(xs_n)), key=lambda i: ys_n[i] - ys_o[i])
    ax.annotate(f"+{ys_n[imax]-ys_o[imax]:.2f}\" per side",
                xy=(xs_n[imax], ys_n[imax]), xytext=(xs_n[imax] - 9, ys_n[imax] + 5.5),
                fontsize=9, fontweight="bold", color="#0b3d5c",
                arrowprops=dict(arrowstyle="->", color="#0b3d5c", lw=1.2))
    ax.set_aspect("equal")
    ax.grid(alpha=0.25)
    ax.set_xlabel("x aft->stem (real in)")
    ax.set_ylabel("half-beam (real in)")
    if BOW_FLARE_NOSE_FADE > 0.0:
        ax.axvline(s * (LOA - BOW_FLARE_NOSE_FADE), color="#e08a00", lw=1.0, ls="-.")
        ax.text(s * (LOA - BOW_FLARE_NOSE_FADE) - 0.6, -s * 13.5,
                f"nose fade starts\n(last {s*BOW_FLARE_NOSE_FADE:.0f}\": flare eases "
                f"to 0)", fontsize=7.5, ha="right", color="#a06a00")
    ax.set_title("(c) Foredeck plan outline -- flared vs straight\n"
                 "the deck edge stays kicked out to the nose (cap-governed at the tip)",
                 fontsize=10, fontweight="bold")
    ax.legend(fontsize=8, loc="lower left")

    xk, (rk, ek) = max(((x, flare_kicks_at(hull, x))
                        for x in np.linspace(BOW_SPLIT, LOA - NOSE_ROUND, 120)),
                       key=lambda p: p[1][1])
    fig.suptitle(f"Flared bow (Rev-3.2): sheer kicked OUT up to "
                 f"{ek*s:.2f}\" real (peak at x={xk*s:.0f}\"), height profile "
                 f"u^{BOW_FLARE_EXP} above f={BOW_FLARE_F0:.2f}, longitudinal g=t^"
                 f"{BOW_FLARE_POW}, capped at {BOW_FLARE_CAP:.2f} x sheer half-width "
                 f"(carried to the nose, no stem fade)\n"
                 f"-- zero at the x=60 split, no material removed",
                 fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.92])
    plt.savefig(str(out_path), dpi=140, bbox_inches="tight")
    plt.close()


def _plane_segs(m, normal, origin):
    """Line segments where mesh m crosses a plane (n,2,3), or an empty array."""
    import trimesh
    try:
        segs = trimesh.intersections.mesh_plane(
            m, plane_normal=np.array(normal, float), plane_origin=np.array(origin, float))
    except Exception:
        return np.zeros((0, 2, 3))
    return np.asarray(segs) if len(segs) else np.zeros((0, 2, 3))


def render_iface_flange(hull, pieces, bolts, out_path):
    """Cutaway of the bow/center interface flange: transverse sections cut through each
    ring (showing the ring + the drilled bolt holes) and a plan cut at a bolt height
    showing one bolt tunnelling straight through BOTH rings across x=BOW_SPLIT."""
    import matplotlib.pyplot as plt
    s = DESIGN_SCALE
    zb = BOLT_BOW_Z[1]
    xc_cut = BOW_SPLIT - FLANGE_T * 0.5      # mid of the center ring
    xb_cut = BOW_SPLIT + FLANGE_T * 0.5      # mid of the bow ring

    fig = plt.figure(figsize=(20, 7.0))

    for k, (name, xcut, col, ttl) in enumerate((
            ("center", xc_cut, PIECE_COLORS["center"],
             f"CENTER ring  (cut at x={xc_cut:.1f} design)"),
            ("bow", xb_cut, PIECE_COLORS["bow"],
             f"BOW ring  (cut at x={xb_cut:.1f} design)")), 1):
        ax = fig.add_subplot(1, 3, k)
        for a, b in _plane_segs(pieces[name], (1, 0, 0), (xcut, 0, 0))[:, :, 1:]:
            ax.plot([s * a[0], s * b[0]], [s * a[1], s * b[1]], "-", color=col, lw=1.3)
        base = iface_contour(hull, BOW_SPLIT, "bow")
        inn = inset_contour(base, FLANGE_GAP + FLANGE_W)
        ax.plot([s * p[0] for p in inn] + [s * inn[0][0]],
                [s * p[1] for p in inn] + [s * inn[0][1]], "--", color="#c0392b", lw=1.0,
                label=f"ring inner bound (FLANGE_W={FLANGE_W*s:.1f}\" real)")
        for (kind, _x, y, z) in bolts:
            if kind == "bow":
                ax.plot(s * y, s * z, "o", ms=9, mfc="none", mew=1.8, color="#111")
        ax.plot([], [], "o", ms=9, mfc="none", mew=1.8, color="#111", label="bolt hole")
        ax.axhline(s * waterline_z(hull), color="#1f77b4", ls="--", lw=1.0,
                   label=f'waterline ({WATERLINE:.1f}" @ {DESIGN_LOAD_LB:.0f} lb)')
        if BULKHEAD:
            _by, _bz = bhd_top_curve(hull)
            ax.plot(s * _by, s * _bz, "-", color="#e67e22", lw=1.8,
                    label=f'arched bulkhead sill ({BHD_TOP:.0f}" at the skin, '
                          f'{BHD_DIP:.0f}" dip) -- solid web below')
        ax.set_aspect("equal"); ax.grid(alpha=0.22)
        ax.set_title(ttl, fontsize=10, fontweight="bold")
        ax.set_xlabel("beam y (real in)")
        if k == 1:
            ax.set_ylabel("height z (real in)")
        ax.legend(fontsize=8, loc="lower center")

    # plan cut at a bolt height: both rings + the through-bolt tunnel
    ax = fig.add_subplot(1, 3, 3)
    for name in ("center", "bow"):
        for a, b in _plane_segs(pieces[name], (0, 0, 1), (0, 0, zb))[:, :, :2]:
            ax.plot([s * a[0], s * b[0]], [s * a[1], s * b[1]], "-",
                    color=PIECE_COLORS[name], lw=1.3)
    ax.axvline(s * BOW_SPLIT, color="#111", lw=1.2, ls="--", label="split x=60 (design)")
    for xx, lbl in ((s * (BOW_SPLIT - FLANGE_T), "center ring aft face"),
                    (s * (BOW_SPLIT + FLANGE_T), "bow ring fwd face")):
        ax.axvline(xx, color="#888", lw=0.8, ls=":")
    for (kind, _x, y, z) in bolts:
        if kind == "bow" and abs(z - zb) < 1e-6:
            ax.plot([s * (BOW_SPLIT - BOLT_BOW_HALF), s * (BOW_SPLIT + BOLT_BOW_HALF)],
                    [s * y, s * y], "-", color="#c0392b", lw=2.2)
    ax.plot([], [], "-", color="#c0392b", lw=2.2,
            label=f"bolt axis @ z={zb*s:.1f}\" real")
    ymb = max(y for (k, _x, y, z) in bolts if k == "bow" and abs(z - zb) < 1e-6)
    ax.axhspan(s * (ymb - BOLT_R), s * (ymb + BOLT_R), color="#c0392b", alpha=0.12,
               label=f"drilled hole (2R = {2*BOLT_R*s:.2f}\" real)")
    ax.annotate("center ring", (s * (BOW_SPLIT - FLANGE_T * 0.5), s * (ymb + 1.4)),
                ha="center", fontsize=8, color=PIECE_COLORS["center"])
    ax.annotate("bow ring", (s * (BOW_SPLIT + FLANGE_T * 0.5), s * (ymb + 1.4)),
                ha="center", fontsize=8, color="#2b8fb8")
    ax.set_xlim(s * (BOW_SPLIT - 2.4 * FLANGE_T), s * (BOW_SPLIT + 2.4 * FLANGE_T))
    ymax = max(abs(y) for (k, _x, y, z) in bolts if k == "bow")
    ax.set_ylim(s * (ymax - 4.0), s * (ymax + 3.0))            # zoom on the stbd joint
    ax.set_aspect("equal"); ax.grid(alpha=0.22)
    ax.set_title(f"Plan cut at z={zb*s:.1f}\" real, STBD joint\n"
                 f"-- one bolt through BOTH rings", fontsize=10, fontweight="bold")
    ax.set_xlabel("x from transom (real in)"); ax.set_ylabel("beam y (real in)")
    ax.legend(fontsize=8, loc="upper right")

    fig.suptitle(f"Interface flange: {FLANGE_W*s:.1f}\" wide x {FLANGE_T*s:.1f}\" thick "
                 f"bulkhead ring on EACH side of the x=60 joint "
                 f"({2*FLANGE_T*s:.1f}\" of bolt grip, was ~{2*SKIN*s:.2f}\")"
                 + (f"  --  plus a SOLID web below the arched sill "
                    f"({BHD_T*s:.1f}\" each side; {BHD_TOP:.0f}\" at the skin, "
                    f"{BHD_TOP-BHD_DIP:.0f}\" on the centreline), all of it ABOVE the "
                    f"waterline" if BULKHEAD else ""),
                 fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.92])
    plt.savefig(str(out_path), dpi=140, bbox_inches="tight")
    plt.close()


def render_bow_keys(hull, pieces, keys, out_path):
    """The vertical drop-in keys at the bow/center face: the bow's aft face (tongues +
    storage opening), the center's forward face (full-height channels through the flange),
    and a 3D exploded view of the joint."""
    import matplotlib.pyplot as plt
    import trimesh
    s = DESIGN_SCALE
    wl = s * waterline_z(hull)

    fig = plt.figure(figsize=(21, 7.4))

    for k, (name, xcut, col, ttl) in enumerate((
            ("bow", BOW_SPLIT + BKEY_STUB * 0.5, PIECE_COLORS["bow"],
             "BOW aft face -- tongues + storage opening\n(section at "
             f"x={BOW_SPLIT + BKEY_STUB*0.5:.1f} design, looking forward)"),
            ("center", BOW_SPLIT - BKEY_DEPTH * 0.5, PIECE_COLORS["center"],
             "CENTER forward face -- full-height drop-in channels\n(section at "
             f"x={BOW_SPLIT - BKEY_DEPTH*0.5:.1f} design, looking forward)")), 1):
        ax = fig.add_subplot(1, 3, k)
        for a, b in _plane_segs(pieces[name], (1, 0, 0), (xcut, 0, 0))[:, :, 1:]:
            ax.plot([s * a[0], s * b[0]], [s * a[1], s * b[1]], "-", color=col, lw=1.4)
        for sp in keys:
            w = sp["back"] if name == "center" else sp["mouth"]
            z0, z1 = (sp["z0"] - BKEY_SILL, hull.interp(BOW_SPLIT)[3]) if name == "center" \
                else (sp["z0"], sp["z1"])
            ax.add_patch(plt.Rectangle((s * (sp["yk"] - w), s * z0), s * 2 * w,
                                       s * (z1 - z0), fill=False, ls="--", lw=1.4,
                                       ec="#c0392b"))
        ax.plot([], [], "--", color="#c0392b", lw=1.4,
                label="key channel" if name == "center" else "key tongue")
        ax.axhline(wl, color="#1f77b4", ls="--", lw=1.1,
                   label=f'waterline ({WATERLINE:.1f}" @ {DESIGN_LOAD_LB:.0f} lb)')
        if BULKHEAD:
            _by, _bz = bhd_top_curve(hull)
            ax.plot(s * _by, s * _bz, "-", color="#e67e22", lw=1.8,
                    label=f'arched bulkhead sill ({BHD_TOP:.0f}"/{BHD_TOP-BHD_DIP:.0f}" real)')
        for (kind, _x, y, z) in getattr(render_bow_keys, "_bolts", []):
            if kind == "bow":
                ax.plot(s * y, s * z, "o", ms=8, mfc="none", mew=1.6, color="#111")
        ax.plot([], [], "o", ms=8, mfc="none", mew=1.6, color="#111", label="bolt")
        ax.set_aspect("equal"); ax.grid(alpha=0.22)
        ax.set_title(ttl, fontsize=10, fontweight="bold")
        ax.set_xlabel("beam y (real in)")
        if k == 1:
            ax.set_ylabel("height z (real in)")
        ax.legend(fontsize=8, loc="lower center")

    # 3D exploded view of the joint
    ax = fig.add_subplot(1, 3, 3, projection="3d")
    def clip(m, x0, x1):
        lo, hi = m.bounds
        T = np.eye(4); T[:3, 3] = [0.5 * (x0 + x1), 0, 0.5 * (lo[2] + hi[2])]
        b = trimesh.creation.box(
            extents=[x1 - x0, 2.2 * max(abs(lo[1]), abs(hi[1])), hi[2] - lo[2] + 2],
            transform=T)
        try:
            return m.intersection(b)
        except Exception:
            return m
    cj = clip(pieces["center"], BOW_SPLIT - 5.0, BOW_SPLIT)
    bj = clip(pieces["bow"], BOW_SPLIT - BKEY_DEPTH - 0.1, BOW_SPLIT + 5.0)
    bj.apply_translation([7.0, 0.0, 5.0])                     # explode fwd + up
    _shaded_mesh(ax, cj, PIECE_COLORS["center"], light=(0.5, 0.55, 0.67))
    _shaded_mesh(ax, bj, PIECE_COLORS["bow"], light=(0.5, 0.55, 0.67))
    ax.set_xlim(BOW_SPLIT - 6, BOW_SPLIT + 13)
    ax.set_ylim(-23, 23)
    ax.set_zlim(-1, 30)
    ax.view_init(elev=18, azim=38)
    ax.set_box_aspect([19, 46, 31], zoom=1.5)
    ax.set_axis_off()
    ax.set_title("Joint exploded -- bow lifted up & forward off its channels",
                 fontsize=10, fontweight="bold")

    fig.suptitle("Bow<->center vertical drop-in dovetail keys: 1 centreline key "
                 "(spanning the below-waterline zone, where no bolt may go) + 1 per side"
                 + ("\nall three run right up to the arched bulkhead sill, so no channel "
                    "is left open through the web" if BULKHEAD else ""),
                 fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.91])
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
    ap.add_argument("--key-clearance-mm", type=float, default=None,
                    help=f"per-face fit gap on every dovetail key/socket, in REAL mm "
                         f"(default {KEY_CLR_MM}). It does NOT shrink with --scale -- but "
                         f"do NOT just multiply it by N for a 1:N model either: the "
                         f"undercut DOES shrink, and a gap bigger than it stops the keys "
                         f"locking. The default already lands near 0.2 mm at 1:10, which "
                         f"is a normal FDM slip fit. Every run prints the capture left.")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--output-dir", default="split_out")
    args = ap.parse_args()

    global KEY_CLR
    if args.key_clearance_mm is not None:
        KEY_CLR = (args.key_clearance_mm / 25.4) / DESIGN_SCALE
    clr_mm = KEY_CLR * DESIGN_SCALE * 25.4

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    und_mm = min_key_undercut() * DESIGN_SCALE * 25.4
    gap_m, und_m = clr_mm / args.scale, und_mm / args.scale
    print(f"Dovetail key fit gap: {clr_mm:.2f} mm per face on the real boat "
          f"(= {gap_m:.2f} mm at 1:{args.scale:.0f}; clearance does NOT scale)")
    print(f"  smallest key undercut {und_mm:.1f} mm real / {und_m:.2f} mm at "
          f"1:{args.scale:.0f}  ->  capture left {und_mm-clr_mm:.1f} mm real, "
          f"{und_m-gap_m:.2f} mm on the model")
    if gap_m >= und_m:
        print(f"  !! at 1:{args.scale:.0f} the gap EXCEEDS the undercut -- the keys would "
              f"NOT lock. Do not scale the clearance up for a model.")
    elif gap_m < 0.10:
        print(f"  !! {gap_m:.2f} mm is below a printable fit at 1:{args.scale:.0f}; "
              f"~0.2 mm wants --key-clearance-mm {0.2*args.scale:.0f}")

    hull = DinghyHull()
    # Derive the waterline BEFORE any geometry is built -- dovetail_params, _key_prism and
    # the bolt rules all read waterline_z().
    _wz = set_waterline_from_load(hull)
    print(f"Design load {DESIGN_LOAD_LB:.0f} lb all-up -> waterline z={_wz*DESIGN_SCALE:.2f}\" "
          f"real (WATERLINE={WATERLINE:.2f}\")")
    print("Building split pieces...")
    raw = {
        "center": build_center(hull),
        "wedge_stbd": build_wedge(hull, +1),
        "wedge_port": build_wedge(hull, -1),
        "bow": build_bow(hull),
    }

    pieces = {}
    flange_vol = {}
    bhd_vol = {}
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
            m = m.union(build_transom_pad(hull))           # + the outboard clamp pad
            if MOTOR_NOTCH:
                m = m.difference(build_notch_box(hull))    # outboard motor cutout
            trimesh.repair.fix_normals(m)
        if name == "bow" and BOW_HOLLOW:
            import trimesh
            m = m.difference(build_bow_cavity(hull))       # hollow + dome storage access
            trimesh.repair.fix_normals(m)                  # (no merge_vertices: welds thin wall)
        if IFACE_FLANGE and name in ("center", "bow"):
            # Bolt-grip bulkhead ring at the x=BOW_SPLIT joint.
            #   BOW    -- the ring is ALREADY there: build_bow_cavity thickened the shell
            #             wall to FLANGE_GAP+FLANGE_W over x=60..60+FLANGE_T (bow_wall_at),
            #             so the ring is the rim of the storage opening, lofted rather than
            #             unioned. Unioning a separate ring used to put its aft cap exactly
            #             coplanar with the shell's aft face at x=BOW_SPLIT, and the
            #             zero-area slivers that produced were what dragged pymeshfix in
            #             (-> membranes on the foredeck). We only measure it here.
            #   CENTER -- still a genuine union: the center is a solid tub, not a shell, so
            #             its U-band ring has no cavity to be lofted into, and its aft
            #             (x=BOW_SPLIT-FLANGE_T) cap is coplanar with nothing.
            # Both land before add_bolt_holes, so the bolts drill through them.
            import trimesh
            fl = build_iface_flange(hull, name)
            if fl is None:
                print(f"  !! interface flange for {name} could not be built")
            elif name == "bow":
                flange_vol[name] = fl.volume          # lofted into the cavity; nothing to do
            else:
                m = m.union(fl)
                trimesh.repair.fix_normals(m)
                flange_vol[name] = fl.volume
        if BULKHEAD and name == "center":
            # The CENTER's half of the bottom bulkhead. (The BOW's half is already there:
            # build_bow_cavity cut this region out of the hollowing cavity, so the bow
            # simply kept its material -- nothing is unioned on that side.)
            import trimesh
            bh = build_bulkhead_center(hull)
            if bh is None:
                print("  !! center bulkhead could not be built")
            else:
                m = m.union(bh)
                trimesh.repair.fix_normals(m)
                bhd_vol[name] = bh.volume
        pieces[name] = m

    if USE_VKEYS:
        print(f"Cutting {N_KEYS} vertical drop-in dovetail keys per side...")
        pieces = add_vertical_dovetails(hull, pieces)

    bkeys = []
    if BOW_KEYS:
        print("Cutting vertical drop-in dovetail keys at the bow/center face...")
        pieces, bkeys = add_bow_keys(hull, pieces)
        for s in bkeys:
            print(f"  {s['name']:7} y={s['yk']*DESIGN_SCALE:+6.2f}\" "
                  f"z={s['z0']*DESIGN_SCALE:5.2f}..{s['z1']*DESIGN_SCALE:5.2f}\" real  "
                  f"mouth {2*s['mouth']*DESIGN_SCALE:.2f}\" -> back "
                  f"{2*s['back']*DESIGN_SCALE:.2f}\" over {BKEY_DEPTH*DESIGN_SCALE:.2f}\" of x")

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
    export_wt = True
    reals = {}
    print("\nPer-piece geometry, AFTER bolt holes (design units, before DESIGN_SCALE):")
    for name, m in pieces.items():
        wt = report(name, m)
        all_wt &= wt
        if name == "bow" and BOW_HOLLOW:
            print("                 ^ bow is a HOLLOW storage shell with a dome access "
                  "opening aft (still a clean manifold, like a cup)")
        # Export the REAL boat = design downscaled by DESIGN_SCALE.
        # make_manifold has to run AGAIN here: it simulates the float32 round-trip an STL
        # performs, and that has to be done at the EXPORT scale -- a vertex pair that is
        # distinct in design units can still collapse once multiplied by DESIGN_SCALE.
        real = make_manifold(m.copy().apply_scale(DESIGN_SCALE))
        rwt = real.is_watertight and _nonmanifold_edge_count(real) == 0
        export_wt &= rwt
        if not rwt:
            print(f"  !! {name}.stl is NOT a clean manifold at export scale")
        real.export(str(out / f"{name}.stl"))
        reals[name] = real
        model = real.copy()
        model.apply_scale(25.4 / args.scale)   # 1:scale mm model of the real boat
        model.export(str(out / f"{name}_1to{args.scale:.0f}_mm.stl"))
        # ...and the same model stood on its best face, ready to slice (see
        # print_ready_transform: in boat coordinates none of these pieces sits flat)
        pr = out / "print_ready"
        pr.mkdir(exist_ok=True)
        T, area, ext = print_ready_transform(model)
        flat = model.copy()
        flat.apply_transform(T)
        flat.export(str(pr / f"{name}_1to{args.scale:.0f}_mm.stl"))
        print(f"    print-ready: {area:6.0f} mm^2 on the plate, "
              f"{ext[0]:.0f} x {ext[1]:.0f} x {ext[2]:.0f} mm")

    print(f"\n  All pieces watertight (after drilling): {all_wt}"
          f"  (bow is hollow w/ a dome storage opening)")
    print(f"  All EXPORTED .stl clean manifolds at real scale: {export_wt}")

    if BOW_FLARE_OUT > 0:
        _hull_f = DinghyHull()
        _xs = np.linspace(BOW_SPLIT, LOA - NOSE_ROUND, 120)
        _ch = max(chord_hollow(_hull_f, x) for x in _xs)
        _xk, (_rk, _ek) = max(((x, flare_kicks_at(_hull_f, x)) for x in _xs),
                              key=lambda p: p[1][1])
        print(f"\nFlared bow: sheer kicked OUT up to {_ek*DESIGN_SCALE:.2f}\" real "
              f"(peak at x={_xk*DESIGN_SCALE:.0f}\" real), above f={BOW_FLARE_F0:.2f} of the "
              f"topside, height profile u^{BOW_FLARE_EXP}, blended g=t^{BOW_FLARE_POW} "
              f"(EXACTLY 0 at the split)."
              f"\n  Stem guard: kick capped at {BOW_FLARE_CAP:.2f} x local sheer half-width "
              f"(trimmed at most {FLARE_CAP_MAX*DESIGN_SCALE:.3f}\" real); "
              + (f"nose fade over last {BOW_FLARE_NOSE_FADE*DESIGN_SCALE:.0f}\" real."
                 if BOW_FLARE_NOSE_FADE > 0 else "carried to the nose (no stem fade).")
              + "".join(f"\n    x={x*DESIGN_SCALE:5.1f}\" real: kick "
                        f"{flare_kicks_at(_hull_f, x)[1]*DESIGN_SCALE:.2f}\" "
                        f"(un-guarded {flare_kicks_at(_hull_f, x)[0]*DESIGN_SCALE:.2f}\")"
                        for x in (78.0, 90.0, 100.0, LOA - NOSE_ROUND))
              + f"\n  Panel concavity vs the rail->sheer chord: up to "
                f"{_ch*DESIGN_SCALE:.2f}\" real (no material removed anywhere)")
    if BOW_FLARE_HOLLOW > 0:
        print(f"\nLegacy carve-in hollow: {BOW_FLARE_HOLLOW*DESIGN_SCALE:.2f}\" real max "
              f"inboard; guard clamped at most {FLARE_CLAMP_MAX*DESIGN_SCALE:.3f}\" real")
    if BOW_KEYS and bkeys:
        sw, sw_dz, sw_steps = check_key_sweep(pieces)
        print(f"Bow drop-in sweep check (bow lifted straight up, boolean-intersected with "
              f"the center at each step):")
        print("   " + "  ".join(f"dz={dz*DESIGN_SCALE:4.1f}\":{v*DESIGN_SCALE**3:6.4f}"
                                for dz, v in sw_steps))
        print(f"  max overlap {sw*DESIGN_SCALE**3:.4f} in^3 (at dz="
              f"{sw_dz*DESIGN_SCALE:.1f}\" real) -> "
              f"{'CLEAR' if sw*DESIGN_SCALE**3 < 0.05 else '*** FOULS ***'}")
    if IFACE_FLANGE and flange_vol:
        print(f"Interface flange rings ({FLANGE_W*DESIGN_SCALE:.1f}\" wide x "
              f"{FLANGE_T*DESIGN_SCALE:.1f}\" thick real, butted at x=BOW_SPLIT):")
        for n, v in flange_vol.items():
            print(f"  {n:8}: +{v*DESIGN_SCALE**3/1728:.3f} ft^3 of ring stock "
                  f"(x {'60..%.1f' % (BOW_SPLIT+FLANGE_T) if n=='bow' else '%.1f..60' % (BOW_SPLIT-FLANGE_T)} design)")
    if BULKHEAD:
        _kz = hull.interp(BOW_SPLIT)[5]
        _zt = bhd_z_top(hull)
        _wl = waterline_z(hull)
        _zc = bhd_top_at(hull, 0.0)
        print(f"Bottom bulkhead at the x=BOW_SPLIT joint: solid web from the keel up to "
              f"{BHD_TOP:.1f}\" real, {BHD_T*DESIGN_SCALE:.1f}\" thick each side "
              f"({2*BHD_T*DESIGN_SCALE:.1f}\" assembled):")
        print(f"  top of the web sits {(_zt-_wl)*DESIGN_SCALE:+.1f}\" above the "
              f"{WATERLINE:.1f}\" waterline and {(BOLT_BOW_Z[0]-_zt)*DESIGN_SCALE:.1f}\" "
              f"below the lowest bow bolt")
        if BHD_DIP > 0:
            print(f"  arched sill: {BHD_DIP:.1f}\" dip on the centreline -> "
                  f"{_zc*DESIGN_SCALE:.1f}\" real there ({(_zc-_wl)*DESIGN_SCALE:+.1f}\" "
                  f"vs the waterline); hatch is {BHD_DIP:.0f}\" taller mid-beam")
        for n, v in bhd_vol.items():
            print(f"  {n:8}: +{v*DESIGN_SCALE**3/1728:.3f} ft^3 of web (unioned)")
        print(f"  bow     : lofted in via build_bow_cavity -> the storage opening now "
              f"sits on that sill")

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

    _hull_kg = estimate_weight(reals, waterline_z(hull) * DESIGN_SCALE)
    report_hydrostatics(hull, _hull_kg * 2.2046)

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
        render_bow_flare(hull, out / "bow_flare_compare.png")
        print(f"  Saved: {out/'bow_flare_compare.png'}")
        render_bow_flare_3d(hull, pieces["bow"], out / "bow_flare_3d.png")
        print(f"  Saved: {out/'bow_flare_3d.png'}")
        if IFACE_FLANGE:
            render_iface_flange(hull, pieces, bolts, out / "iface_flange.png")
            print(f"  Saved: {out/'iface_flange.png'}")
        if BOW_KEYS and bkeys:
            render_bow_keys._bolts = bolts
            render_bow_keys(hull, pieces, bkeys, out / "bow_keys.png")
            print(f"  Saved: {out/'bow_keys.png'}")

    # Bolt summary (real units): confirm every bolt sits above the waterline.
    breach = check_pods_sealed(hull)
    print(f"\nWedge bolts are BLIND in the pod: {BOLT_WEDGE_OUT*DESIGN_SCALE:.2f}\" deep, "
          f"{BOLT_WEDGE_BACK*DESIGN_SCALE:.2f}\" of solid behind them (threaded insert; a "
          f"sealed pod has no nut side).")
    print(f"  buoyancy pod breach check: {breach:.4f} in^3  "
          f"{'SEALED' if breach < 1e-4 else '*** HOLE INTO THE POD ***'}")

    print("\nBolt holes (real boat):")
    for (kind, x, y, z) in bolts:
        wl = waterline_z(hull)
        flag = "OK" if z >= wl else "!! BELOW WL"
        print(f"  {kind:5} @ x={x*DESIGN_SCALE:5.1f} y={y*DESIGN_SCALE:+6.1f} "
              f"z={z*DESIGN_SCALE:5.1f}  ({z-wl:+.1f}\" above WL {flag})")

    print("\nDone.")


if __name__ == "__main__":
    main()
