#!/usr/bin/env python3
"""
slice_for_print.py - cut the full-size boat pieces into printer-bed-sized sections
with printed-ASA dowel alignment holes, + a batch dowel STL + a mating manifest.

Input : split_out/{center,wedge_stbd,wedge_port,bow}.stl  (INCHES, full size)
Output: split_out/print_sections/  (numbered chunk STLs, dowel.stl, manifest.csv)
        Chunks are written in MILLIMETRES: STL carries no units and slicers assume
        mm, so exporting the inch geometry directly imports at 1/25.4 size.

Run:   .venv/bin/python slice_for_print.py                      # Bambu X1C, 256^3
       .venv/bin/python slice_for_print.py --printer coreone   # Prusa Core One
       PRINTERS / PIECES overridable via the params below.
"""
import numpy as np, trimesh, csv, argparse
from pathlib import Path
import json
import dinghy_split as ds          # print constants live there; keep one copy of each

# ---- printers ----
# The bed drives the chunk grid, so changing printer re-cuts the whole boat: the two
# targets share no chunk files and each gets its own output directory. Everything else
# that differs between them lives here too, because a piece's PROFILE.txt is meant to be
# read at the machine, with neither this file nor the presets README to hand.
PRINTERS = {
    "x1c": dict(
        label="Bambu Lab X1C",
        bed=(256.0, 256.0, 256.0),
        outdir="print_sections_x1c",
        presets="print_profiles/bambu",
        filament="print_profiles/bambu/boatASA_filament.json",
        preset12="boatASA-12", preset8="boatASA-8",
        flow_default=16.0, temp_default=275, flow_max=20.0,
        printer_line="X1C, and it must be ENCLOSED. ASA warps and splits in open air.",
        nozzle_line=("0.4. With no 0.6 to swap to, the volumetric cap below is the\n"
                     "               only speed lever on this job."),
        layer_line="0.24 mm.",
        bed_line="ENCLOSURE DOOR SHUT and chamber warm before the first layer.",
        flow_note=(
  "  Not print-tested yet: run the max volumetric speed calibration at {temp} C\n"
  "  before committing to it. For reference, Bambu ship 18 for their own ASA on\n"
  "  an X1C with a 0.4 nozzle and 18 at 275 C for ASA-CF; Generic ASA sits at 12\n"
  "  only because the filament is unknown. {flow:.0f} is above their figure, so it needs\n"
  "  the test rather than the catalogue behind it.\n"
  "\n"
  "  It governs the whole job. This process asks for 24 mm3/s on outer walls\n"
  "  and 27.6 on inner walls and infill, so the cap throttles every one of\n"
  "  those moves:"),
    ),
    "coreone": dict(
        label="Prusa Core One",
        bed=(250.0, 220.0, 270.0),
        outdir="print_sections_coreone",
        presets="print_profiles/prusa",
        filament="print_profiles/prusa/boatASA.ini",
        preset12="boatASA-12", preset8="boatASA-8",
        flow_default=16.0, temp_default=275, flow_max=24.0,
        printer_line=("Core One. It is enclosed as shipped, which is what ASA needs;\n"
                      "               keep the door and the top lid on for every chunk."),
        nozzle_line=("0.4 high-flow, as shipped. Unlike the X1C this machine takes a\n"
                     "               0.6 HF nozzle in a two-minute swap, and that is the one\n"
                     "               change that roughly halves the 400-plus hours. Take it\n"
                     "               unless you need the 0.4 surface, which on a glassed core\n"
                     "               you do not."),
        layer_line="0.25 mm with the 0.4 nozzle, 0.32 mm if you fit the 0.6.",
        bed_line=("smooth or textured PEI, 105 C. ASA grips smooth PEI hard, so use a\n"
                  "               separator on it, or print on textured and accept the finish:\n"
                  "               these faces get abraded for epoxy anyway."),
        flow_note=(
  "  This figure was carried over from the Bambu profile and has been tested on\n"
  "  neither machine. Treat it as a starting point. The Core One's high-flow\n"
  "  hotend has more headroom than the X1C's stock one, so the calibration is\n"
  "  worth running properly: it takes 20 minutes against a job of this length,\n"
  "  and the cap governs every move in the profile.\n"
  "\n"
  "  Fitting a 0.6 HF nozzle moves more than the cap does: roughly double the\n"
  "  flow, and a single wall laid at about 0.68 mm instead of 0.50, which bonds\n"
  "  better and costs about 3 kg of ASA over the whole boat:"),
    ),
}
PRINTER = "x1c"                # default target; --printer selects another

# ---- params ----
BED = PRINTERS[PRINTER]["bed"]  # printer bed X,Y,Z (mm); set from PRINTERS in main()
MARGIN = 8.0                  # mm clearance each side (-> usable = BED-2*MARGIN)
DOWEL_DIA = 4.0               # mm printed ASA dowel diameter (fits ~7mm walls)
DOWEL_CLEAR = 0.2             # mm added to the HOLE (dia+clear) for epoxy fit
DOWEL_SHRINK = 0.0            # mm off the PRINTED DOWEL only, never the hole. This is the
                              # fit knob: the dowel is the cheap half of the joint (~50 g
                              # and a few hours for all 784), so tune the fit by reprinting
                              # dowels rather than by reopening holes in 149 chunks.
                              # Raise it if they bind, and reprint 000_dowel.stl alone.
DOWEL_DEPTH = 6.0             # mm hole depth into EACH side of a cut
DOWELS_PER_FACE = 3           # dowels per shared cut face (fewer if the face is small)
MIN_CHUNK_IN3 = 0.06          # drop chunks below ~1 cm^3 of material
# Print order. Chunks are numbered sequentially in this order, so this list decides
# what gets printed first; within a piece they run bottom layer up, then raster in x
# and y, which is also the order you bond them in.
PIECES = ["bow", "center", "wedge_stbd", "wedge_port"]
OUTDIR = PRINTERS[PRINTER]["outdir"]      # per printer: the grid differs, so the files do
FLOW = FLOW_MAX = TEMP = None             # from the saved filament preset; set in main()
WL = None                     # real-scale waterline; set in main(). Chunks reaching below
                              # it get the denser infill (slam, beaching, wide shallow V).

MM = 1.0 / 25.4               # mm -> inch (STLs are in inches)
IN = 25.4


def prep(m):
    m = m.copy()
    if not m.is_watertight:
        trimesh.repair.fill_holes(m); m.merge_vertices(); trimesh.repair.fix_normals(m)
    if not m.is_watertight:                                 # robust fallback
        import pymeshfix
        v = np.asarray(m.vertices, dtype=np.float64); f = np.asarray(m.faces, dtype=np.int32)
        v2, f2 = pymeshfix.clean_from_arrays(v, f, remove_smallest_components=False)
        m = trimesh.Trimesh(vertices=v2, faces=f2); m.merge_vertices(); trimesh.repair.fix_normals(m)
    return m


def _nm_edges(m):
    e = np.sort(m.edges, axis=1)
    _, c = np.unique(e, axis=0, return_counts=True)
    return int((c != 2).sum())


def clean_chunk(ch):
    """Make a cut chunk cleanly manifold. CALL THIS AT EXPORT SCALE (mm), never in the
    inch working space: it simulates the float32 round-trip an STL performs, and a vertex
    pair that is distinct in inches can still collapse once multiplied by 25.4. Repairing
    in inches and then scaling produced three non-manifold chunks out of 149.

    Standard weld first; if still non-watertight or
    non-manifold (boolean/dowel slivers at high res), repair at float32 precision then
    pymeshfix, keeping the repair if it preserves the chunk volume (<=15% -- a small tile
    that gets glued + glassed tolerates a sliver repair)."""
    ch.merge_vertices(); ch.update_faces(ch.unique_faces())
    ch.update_faces(ch.nondegenerate_faces()); ch.remove_unreferenced_vertices()
    if ch.is_watertight and _nm_edges(ch) == 0:
        return ch
    m32 = trimesh.Trimesh(ch.vertices.astype(np.float32).astype(np.float64),
                          ch.faces, process=True)
    trimesh.repair.fix_normals(m32)
    if m32.is_watertight and _nm_edges(m32) == 0:
        return m32
    import pymeshfix
    v0 = abs(ch.volume)
    v = np.ascontiguousarray(m32.vertices, np.float64); f = np.ascontiguousarray(m32.faces, np.int32)
    vc, fc = pymeshfix.clean_from_arrays(v, f, joincomp=True, remove_smallest_components=False)
    r = trimesh.Trimesh(vc, fc); r.merge_vertices(); trimesh.repair.fix_normals(r)
    if r.is_watertight and _nm_edges(r) == 0 and (v0 <= 0 or abs(abs(r.volume) - v0) / v0 <= 0.15):
        return r                                          # tolerate a sliver repair (tile is glued+glassed)
    return ch                                            # best effort


def box(lo, hi):
    ext = hi - lo
    T = np.eye(4); T[:3, 3] = (lo + hi) / 2.0
    return trimesh.creation.box(extents=ext, transform=T)


def grid_cuts(a0, a1, usable):
    n = max(1, int(np.ceil((a1 - a0) / usable / 1.02)))    # 2% tol -> no sliver rows
    return np.linspace(a0, a1, n + 1)


def dowel_points(mesh, axis, plane, a_lo, a_hi, b_lo, b_hi, n):
    """n material points on the plane (axis=cut normal, 0/1/2), spread across it."""
    ai, bi = [k for k in (0, 1, 2) if k != axis]
    grid = []
    for a in np.arange(a_lo + 0.3, a_hi - 0.3, 0.35):      # ~9mm grid in inches
        for b in np.arange(b_lo + 0.3, b_hi - 0.3, 0.35):
            p = [0, 0, 0]; p[axis] = plane; p[ai] = a; p[bi] = b
            grid.append(p)
    if not grid:
        return []
    grid = np.array(grid)
    inside = mesh.contains(grid + np.eye(3)[axis] * 0.02) & mesh.contains(grid - np.eye(3)[axis] * 0.02)
    cand = grid[inside]
    if len(cand) == 0:
        return []
    # farthest-point spread
    picks = [cand[np.argmax(cand[:, ai])]]
    while len(picks) < min(n, len(cand)):
        d = np.min([np.linalg.norm(cand - p, axis=1) for p in picks], axis=0)
        picks.append(cand[np.argmax(d)])
    return picks


def slice_piece(mesh, name, out, log, seq0=1):
    lo, hi = mesh.bounds
    ux, uy, uz = [(b - 2 * MARGIN) * MM for b in BED]
    xc, yc, zc = grid_cuts(lo[0], hi[0], ux), grid_cuts(lo[1], hi[1], uy), grid_cuts(lo[2], hi[2], uz)
    cells = {}   # (i,j,k) -> mesh
    for i in range(len(xc) - 1):
        for j in range(len(yc) - 1):
            for k in range(len(zc) - 1):
                clo = np.array([xc[i], yc[j], zc[k]]); chi = np.array([xc[i + 1], yc[j + 1], zc[k + 1]])
                try:
                    ch = mesh.intersection(box(clo, chi))
                except Exception:
                    continue
                if ch.is_empty or ch.volume < MIN_CHUNK_IN3:
                    continue
                cells[(i, j, k)] = ch
    # dowel holes on shared faces between kept cells
    hole_r = (DOWEL_DIA + DOWEL_CLEAR) / 2.0 * MM
    dep = DOWEL_DEPTH * MM
    faces = 0; dowels = 0; mate = {c: [] for c in cells}
    for (i, j, k) in list(cells):
        for axis, nb, plane, (a0, a1), (b0, b1) in [
            (0, (i + 1, j, k), xc[i + 1], (yc[j], yc[j + 1]), (zc[k], zc[k + 1])),
            (1, (i, j + 1, k), yc[j + 1], (xc[i], xc[i + 1]), (zc[k], zc[k + 1])),
            (2, (i, j, k + 1), zc[k + 1], (xc[i], xc[i + 1]), (yc[j], yc[j + 1]))]:
            if nb not in cells:
                continue
            pts = dowel_points(mesh, axis, plane, a0, a1, b0, b1, DOWELS_PER_FACE)
            if not pts:
                continue
            faces += 1
            n1 = np.eye(3)[axis]
            for p in pts:
                p = np.array(p)
                cyl = trimesh.creation.cylinder(radius=hole_r, segment=[p - n1 * dep, p + n1 * dep], sections=16)
                for c in (cells[(i, j, k)], cells[nb]):
                    pass
                try:
                    cells[(i, j, k)] = cells[(i, j, k)].difference(cyl)
                    cells[nb] = cells[nb].difference(cyl)
                    dowels += 1
                except Exception:
                    continue
            mate[(i, j, k)].append((nb, len(pts))); mate[nb].append(((i, j, k), len(pts)))
    # export, numbered in print order: bottom layer first, then raster in x and y. That
    # is also the bonding order, so chunk N only ever glues to chunks already printed.
    order = sorted(cells, key=lambda c: (c[2], c[0], c[1]))
    seq = {c: seq0 + n for n, c in enumerate(order)}
    rows = []
    low = []                                     # chunks reaching below the waterline
    for (i, j, k) in order:
        raw = cells[(i, j, k)]
        if WL is not None and name in ds.INFILL_ZONED and raw.bounds[0][2] < WL:
            low.append(seq[(i, j, k)])           # zone test belongs in the inch working space
        # EXPORT IN MILLIMETRES. Everything upstream is in inches, because the hull is
        # drawn in inches, but an STL carries no units and every slicer assumes mm, so an
        # inch-scale chunk imports at 1/25.4 size. Scale BEFORE cleaning so the repair
        # runs at the scale the file will actually carry.
        ch = raw.copy()
        ch.apply_scale(IN)
        ch = clean_chunk(ch)                     # weld + repair -> clean manifold chunk
        fn = f"{seq[(i, j, k)]:03d}_{name}_x{i}y{j}z{k}.stl"
        ch.export(str(out / name / fn))
        d = ch.bounds[1] - ch.bounds[0]          # already mm
        neigh = ";".join(f"#{seq[n[0]]:03d}({n[1]})" for n in mate[(i, j, k)] if n[0] in seq)
        rows.append([f"{seq[(i, j, k)]:03d}", name, fn, f"{i},{j},{k}",
                     f"{d[0]:.0f}x{d[1]:.0f}x{d[2]:.0f}",
                     f"{ch.volume / IN ** 3:.1f}", neigh])
    log(f"  {name:12} {len(cells):3d} chunks, {faces} glued faces, {dowels} dowel holes"
        f"   -> #{seq0:03d}..#{seq0 + len(cells) - 1:03d}")
    return rows, dowels, low


PROFILE = """{title}
{rule}
{n} chunks, files {lo}..{hi}   |   {dowels} dowels   |   ~{kg:.1f} kg ASA
Print time roughly {h4:.0f} h at the profile's {flow:.0f} mm3/s cap.

SETTINGS
  Printer      {printer_line}
  Filament     boatASA: {temp} C, {flow:.0f} mm3/s cap. Stock Generic ASA is 260 C
               and slower, so this is already the boosted profile.
  Nozzle       {nozzle_line}
  Preset       {preset}   ({presets}/ in the repo)
  Layer        {layer_line}
  Units        the STLs are in mm. Import at 100%, do not rescale.
  Bed          {bed_line}
  Walls        1 perimeter at 0.5 mm extrusion width. The print is a glass
               substrate, not a finish surface, so one clean wall is enough.
  INFILL       {infill}
               GYROID, not grid. It is isotropic and much better in shear,
               which is the whole job of the core in a 7 mm sandwich wall.
  Overlap      infill/wall 25%.
  Top/bottom   3 layers each, top shell thickness floor set to 0.
  Brim         outer, 6 to 8 mm. Every chunk wants it.

ORDER
  Print 000_dowel.stl first, in the folder above this one.
  Then work up in file order. The numbering runs bottom layer first, so a
  chunk only ever bonds to lower-numbered neighbours that are already printed.
  manifest.csv in the folder above names which chunks each one mates to.

DOWELS
  Holes are {hole:.1f} mm for {dow:.1f} mm printed dowels, 6 mm deep each side.
  Dry-fit before glue. Abrade and solvent-wipe the faces: the ASA to epoxy
  bond is the least forgiving joint on the boat.
  If they bind, do NOT open the holes: that obsoletes every chunk. Raise
  DOWEL_SHRINK in slice_for_print.py and reprint 000_dowel.stl on its own.

FLOW  --  {flow:.0f} mm3/s at {temp} C
{flownote}

{table}

  KEEP LOOKING AS THE PARTS GET BIGGER. Under-extrusion does not fail
  loudly: it thins every wall slightly, and on a one-perimeter print the
  wall is the entire part. The early bow chunks are small, so they ask less
  of the hotend than a 240 mm center chunk running long infill passes will.
  Check the top surface and the wall against strong light. Gaps between
  adjacent extrusions, a wall you can see through, or a grainy top face
  mean back the cap off.
{extra}"""


def read_preset(P):
    """Cap and nozzle temperature out of the saved filament preset, so the time estimates
    in every PROFILE.txt track the profile actually being run. Bambu presets are JSON with
    every value in a list; PrusaSlicer presets are flat key = value ini."""
    f = Path(P["filament"])
    try:
        if f.suffix == ".json":
            d = json.load(open(f))
            return (float(d["filament_max_volumetric_speed"][0]),
                    int(float(d["nozzle_temperature"][0])))
        kv = {}
        for line in f.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1); kv[k.strip()] = v.strip()
        return float(kv["filament_max_volumetric_speed"]), int(float(kv["temperature"]))
    except Exception:
        return P["flow_default"], P["temp_default"]


def write_profile(out, name, title, lo, hi, n, dowels, kg, infill, extra="", preset=""):
    P = PRINTERS[PRINTER]
    hours = lambda f: kg * 1e6 / ds.ASA_DENSITY / f / 3600.0
    caps = sorted({12.0, FLOW, FLOW_MAX})
    table = ("        " + "        ".join(f"{f:.0f} mm3/s   {hours(f):.0f} h" for f in caps)
             + "\n        (hours for this folder, not for the whole boat)")
    (out / name / "PROFILE.txt").write_text(PROFILE.format(
        title=title, rule="=" * len(title), n=n, lo=lo, hi=hi, dowels=dowels,
        kg=kg, h4=hours(FLOW), flow=FLOW, flowmax=FLOW_MAX, temp=TEMP, table=table,
        flownote=P["flow_note"].format(flow=FLOW, temp=TEMP),
        printer_line=P["printer_line"], nozzle_line=P["nozzle_line"],
        layer_line=P["layer_line"], bed_line=P["bed_line"], presets=P["presets"],
        hole=DOWEL_DIA + DOWEL_CLEAR, dow=DOWEL_DIA - DOWEL_SHRINK,
        infill=infill, extra=extra, preset=preset))


def make_dowel(out):
    r = (DOWEL_DIA - DOWEL_SHRINK) / 2.0 * MM
    L = (2.2 * DOWEL_DEPTH) * MM
    c = trimesh.creation.cylinder(radius=r, height=L, sections=24)
    # lead-in chamfers: intersect with a double-cone-ish; simple: slice tiny cones off ends
    cham = DOWEL_DIA * 0.3 * MM
    for z in (L / 2, -L / 2):
        cone = trimesh.creation.cone(radius=r + cham, height=cham * 2, sections=24)
        T = np.eye(4)
        if z > 0:
            T[:3, 3] = [0, 0, z - cham]
        else:
            cone.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
            T[:3, 3] = [0, 0, z + cham]
        cone.apply_transform(T)
        try:
            c = c.intersection(cone) if False else c   # keep simple/robust
        except Exception:
            pass
    c.apply_scale(IN)                      # mm for the slicer, like the chunks
    c.export(str(out / "000_dowel.stl"))   # 000 so it sorts first: print these first


TITLES = {"bow": "BOW", "center": "CENTER BARGE",
          "wedge_stbd": "STARBOARD WEDGE POD", "wedge_port": "PORT WEDGE POD"}
EXTRA = {
 "bow": "\nThe bow is narrow and doubly curved, so it carries load in membrane action\n"
        "rather than bending. Its shape does the work a denser core would, which is\n"
        "why it runs lean all the way through.\n",
 "center": "\nThe center is the flexible one. Its bottom is a 42 inch wide shallow V and\n"
           "its sole spans the full beam, so nothing in the shape stiffens them. That is\n"
           "what the denser core and the 14 mm sole are both for.\n",
}


def tight_note(rows):
    """Name the chunk with the least room on the plate. A chunk can be turned on the bed,
    so the test is its sorted bounding box against the sorted usable envelope, not axis
    for axis. Worth printing first: if anything is going to foul the skirt, know early."""
    env = sorted(b - 2 * MARGIN for b in BED)
    worst, slack = None, 1e9
    for r in rows:
        d = sorted(float(v) for v in r[4].split("x"))
        sl = min(e - v for e, v in zip(env, d))
        if sl < slack:
            worst, slack = r, sl
    if worst is None or slack > 6.0:
        return ""
    return (f"\nTightest on the plate is #{worst[0]}: {worst[4]} mm against a "
            f"{env[2]:.0f}x{env[1]:.0f}x{env[0]:.0f} mm usable\nenvelope, about {slack:.0f} mm of "
            f"room at its worst axis (the manifest rounds to whole mm).\nPlate that one first.\n")


def verify_exports(out, log):
    """Check every STL that was actually written, and repair any that is not a clean
    manifold. This runs on the exported bytes rather than on the in-memory mesh, which is
    the only thing that matters to a slicer, and it catches what clean_chunk cannot:
    clean_chunk feeds pymeshfix a mesh it has already run fix_normals over, and on a
    non-manifold input that scrambles winding enough to defeat the repair. Re-running it
    on the reloaded file, untouched, fixes those. Returns the number repaired."""
    import pymeshfix
    fixed, failed = 0, []
    for f in sorted(out.glob("*/*.stl")) + sorted(out.glob("*.stl")):
        m = trimesh.load(str(f))
        if m.is_watertight and _nm_edges(m) == 0 and m.body_count == 1:
            continue
        v0 = abs(m.volume)
        vc, fc = pymeshfix.clean_from_arrays(
            np.ascontiguousarray(m.vertices, np.float64),
            np.ascontiguousarray(m.faces, np.int32),
            joincomp=True, remove_smallest_components=False)
        r = trimesh.Trimesh(vc, fc); r.merge_vertices(); trimesh.repair.fix_normals(r)
        ok = (r.is_watertight and _nm_edges(r) == 0 and r.body_count == 1
              and (v0 <= 0 or abs(abs(r.volume) - v0) / v0 <= 0.02))
        if ok:
            r.export(str(f)); fixed += 1
        else:
            failed.append(f.name)
    if fixed:
        log(f"  repaired {fixed} exported chunk(s) that were not clean manifolds")
    if failed:
        log(f"  !! STILL NOT CLEAN: {', '.join(failed)}")
    else:
        log("  every exported STL verified: watertight, manifold, single body")
    return fixed


def main():
    global WL, PRINTER, BED, OUTDIR, FLOW, FLOW_MAX, TEMP
    ap = argparse.ArgumentParser(
        description="Cut the full-size boat pieces into printer-bed-sized sections.")
    ap.add_argument("outdir", nargs="?", default=None,
                    help="subdirectory under split_out/ (default: the printer's own)")
    ap.add_argument("--printer", default=PRINTER, choices=sorted(PRINTERS),
                    help="target printer; the bed size re-cuts every chunk")
    args = ap.parse_args()
    PRINTER = args.printer
    P = PRINTERS[PRINTER]
    BED, OUTDIR = P["bed"], (args.outdir or P["outdir"])
    FLOW, TEMP = read_preset(P)
    FLOW_MAX = P["flow_max"]
    _h = ds.DinghyHull()
    WL = ds.set_waterline_from_load(_h) * ds.DESIGN_SCALE
    out = Path("split_out") / OUTDIR
    out.mkdir(parents=True, exist_ok=True)
    for old in (list(out.glob("*.stl")) + list(out.glob("manifest.csv"))
                + list(out.glob("*/*.stl")) + list(out.glob("*/PROFILE.txt"))):
        old.unlink()                             # wipe stale chunks (grid changes per bed)
    for name in PIECES:
        (out / name).mkdir(exist_ok=True)
    lines = []
    log = lambda s: (print(s), lines.append(s))
    print(f"Slicing for {P['label']}: bed {BED[0]:.0f}x{BED[1]:.0f}x{BED[2]:.0f}mm "
          f"(usable {BED[0]-2*MARGIN:.0f}x{BED[1]-2*MARGIN:.0f}x{BED[2]-2*MARGIN:.0f}mm), "
          f"dowel {DOWEL_DIA}mm -> split_out/{OUTDIR}/")
    allrows, total_dowels = [], 0
    for name in PIECES:
        p = Path("split_out") / f"{name}.stl"
        if not p.exists():
            continue
        m = prep(trimesh.load(str(p)))
        seq0 = len(allrows) + 1
        rows, dw, low = slice_piece(m, name, out, log, seq0=seq0)
        allrows += rows; total_dowels += dw
        hi = seq0 + len(rows) - 1
        perim = min(m.volume, m.area * ds.PERIM_SHELL / 25.4)
        core = max(0.0, m.volume - perim)
        f_lo = (ds._volume_below(m, WL) / m.volume
                if (name in ds.INFILL_ZONED and m.volume > 0) else 0.0)
        rate = ds.INFILL * f_lo + ds.INFILL_TOPSIDE * (1 - f_lo)
        kg = (perim + core * rate) * 16.387064 * ds.ASA_DENSITY / 1000.0
        if len(low) == len(rows):
            inf = f"{ds.INFILL:.0%} for every chunk in this folder."
        elif not low:
            inf = f"{ds.INFILL_TOPSIDE:.0%} for every chunk in this folder."
        else:
            inf = (f"{ds.INFILL:.0%} for #{min(low):03d}..#{max(low):03d}, then "
                   f"{ds.INFILL_TOPSIDE:.0%} for #{max(low)+1:03d}..#{hi:03d}.\n"
                   f"               The split is the waterline: everything reaching below it\n"
                   f"               takes slamming and beaching loads.")
        preset = (f"{P['preset12']} for the {ds.INFILL:.0%} chunks, {P['preset8']} for the rest"
                  if low and len(low) != len(rows) else
                  (P["preset12"] if low else P["preset8"]))
        write_profile(out, name, TITLES.get(name, name.upper()), f"#{seq0:03d}",
                      f"#{hi:03d}", len(rows), dw, kg, inf,
                      EXTRA.get(name, "") + tight_note(rows), preset=preset)
    make_dowel(out)
    verify_exports(out, log)
    with open(out / "manifest.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seq", "piece", "file", "grid_ijk", "bbox_mm", "vol_in3",
                    "mates_to(dowels)"])
        w.writerows(allrows)
    print(f"\nTOTAL: {len(allrows)} chunk STLs + 000_dowel.stl  |  {total_dowels} dowels")
    print(f"Print in filename order: 000_dowel first, then #001 upward. Within each piece "
          f"the numbering runs bottom layer up, so a chunk only ever bonds to lower-numbered "
          f"neighbours (mates_to in the manifest names them).")
    print(f"Output: {out}/  (manifest.csv)")


if __name__ == "__main__":
    main()
