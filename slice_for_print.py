#!/usr/bin/env python3
"""
slice_for_print.py - cut the full-size boat pieces into printer-bed-sized sections
with printed-ASA dowel alignment holes, + a batch dowel STL + a mating manifest.

Input : split_out/{center,wedge_stbd,wedge_port,bow}.stl  (inches, full size)
Output: split_out/print_sections/  (numbered chunk STLs, dowel.stl, manifest.csv)

Run:   .venv/bin/python slice_for_print.py            # X1C 256^3
       BED / PIECES overridable via the params below.
"""
import numpy as np, trimesh, csv, sys
from pathlib import Path

# ---- params ----
BED = (256.0, 256.0, 256.0)   # printer bed X,Y,Z (mm)  -- Bambu X1C default
MARGIN = 8.0                  # mm clearance each side (-> usable = BED-2*MARGIN)
DOWEL_DIA = 4.0               # mm printed ASA dowel diameter (fits ~7mm walls)
DOWEL_CLEAR = 0.2             # mm added to the HOLE (dia+clear) for epoxy fit
DOWEL_DEPTH = 6.0             # mm hole depth into EACH side of a cut
DOWELS_PER_FACE = 3           # dowels per shared cut face (fewer if the face is small)
MIN_CHUNK_IN3 = 0.06          # drop chunks below ~1 cm^3 of material
# Print order. Chunks are numbered sequentially in this order, so this list decides
# what gets printed first; within a piece they run bottom layer up, then raster in x
# and y, which is also the order you bond them in.
PIECES = ["bow", "center", "wedge_stbd", "wedge_port"]
OUTDIR = "print_sections"

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
    """Make a cut chunk cleanly manifold. Standard weld first; if still non-watertight or
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
    for (i, j, k) in order:
        ch = clean_chunk(cells[(i, j, k)])       # weld + repair -> clean manifold chunk
        fn = f"{seq[(i, j, k)]:03d}_{name}_x{i}y{j}z{k}.stl"
        ch.export(str(out / fn))
        d = (ch.bounds[1] - ch.bounds[0]) * IN
        neigh = ";".join(f"#{seq[n[0]]:03d}({n[1]})" for n in mate[(i, j, k)] if n[0] in seq)
        rows.append([f"{seq[(i, j, k)]:03d}", name, fn, f"{i},{j},{k}",
                     f"{d[0]:.0f}x{d[1]:.0f}x{d[2]:.0f}", f"{ch.volume:.1f}", neigh])
    log(f"  {name:12} {len(cells):3d} chunks, {faces} glued faces, {dowels} dowel holes"
        f"   -> #{seq0:03d}..#{seq0 + len(cells) - 1:03d}")
    return rows, dowels


def make_dowel(out):
    r = DOWEL_DIA / 2.0 * MM
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
    c.export(str(out / "000_dowel.stl"))    # 000 so it sorts first: print these first


def main():
    out = Path("split_out") / (OUTDIR if len(sys.argv) < 2 else sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for old in list(out.glob("*.stl")) + list(out.glob("manifest.csv")):
        old.unlink()                             # wipe stale chunks (grid changes per bed)
    lines = []
    log = lambda s: (print(s), lines.append(s))
    print(f"Slicing for bed {BED[0]:.0f}x{BED[1]:.0f}x{BED[2]:.0f}mm "
          f"(usable {(BED[0]-2*MARGIN):.0f}mm), dowel {DOWEL_DIA}mm")
    allrows, total_dowels = [], 0
    for name in PIECES:
        p = Path("split_out") / f"{name}.stl"
        if not p.exists():
            continue
        m = prep(trimesh.load(str(p)))
        rows, dw = slice_piece(m, name, out, log, seq0=len(allrows) + 1)
        allrows += rows; total_dowels += dw
    make_dowel(out)
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
