#!/usr/bin/env python3
"""
orient_chunks.py - stand each printed chunk on the flat cut face that prints best.

This is a POST-PROCESS on an existing slice_for_print.py run, not part of it, and it is
deliberately kept out of slice_for_print.py: chunks have already been printed from that
script, so it must stay byte-identical to the version that produced them. Re-running the
slicer would re-do 149 boolean cuts and every dowel subtraction, and there is no reason to
put the parts already on the shelf through that.

What it changes: the ROTATION each chunk STL is written in. Nothing else. Every transform
here has entries of exactly 0 and +-1, which in IEEE754 makes each output coordinate either
a copy or a sign flip of an input coordinate -- so the float32 STL round-trip is lossless
and the solid on the plate is the same solid, to the bit. --verify re-reads every file and
proves that rather than asserting it. Already-printed chunks stay valid: they are the same
part, just described from a different corner.

Why bother: slice_piece cuts and exports in the boat's own frame, and a hull in its own
frame mostly lies curved-side-down. Measured over the whole set below.

Run:   .venv/bin/python orient_chunks.py                     # split_out/print_sections_x1c
       .venv/bin/python orient_chunks.py <dir> [--dry-run] [--force]
"""
import numpy as np, trimesh, csv, sys, shutil
from pathlib import Path

# ---- params ----
TOL = 0.15            # mm: a face within this of the plate counts as first-layer contact
ANGLE = 40.0          # deg from horizontal: a down-face shallower than this wants support
SLENDER = 8.0         # height / shortest footprint side before a stance is charged for being
                      # tippy. NOT dinghy_split's 2.2: that number sizes a compact scale
                      # model, and a chunk cut out of a 7 mm skin is a slab, so its only
                      # support-free stance is always on edge. Measured over the set, 63 of
                      # 149 chunks have a best stance above 2.2 and nearly all of them are
                      # fine -- 36 mm thick, 210 mm long, 229 tall, on 29 cm^2 of brimmed
                      # contact. A hard veto at 2.2 bought that stability for 17926 cm^2 of
                      # support, which is a bad trade on a part whose whole job is to be a
                      # glassing substrate.
PLATE_W = 0.25        # mm^2 of overhang that one mm^2 of first-layer contact is worth. ASA
                      # lifts off the plate more readily than it sags, so contact gets to
                      # outvote a little overhang -- but only a little, hence the cap.
PLATE_CAP = 5000.0    # mm^2: contact past this earns nothing more
BORE_W = 50.0         # mm^2 charged per dowel bore left horizontal. A horizontal bore has to
                      # bridge its own roof, and the droop goes INTO a 4.2 mm hole carrying
                      # 0.2 mm of clearance. Standing a chunk on a cut face makes that face's
                      # bores vertical for free, so this usually costs nothing and just
                      # breaks ties the right way.
TIP_W = 1000.0        # mm^2 of overhang charged per unit of slenderness ABOVE SLENDER.
                      # Soft on purpose: past the threshold this is a trade, not a veto, so
                      # a stance only loses on height when it was not saving much support
                      # anyway. At this weight a chunk saving 500 cm^2 still stands up at
                      # 15:1, and one saving 1 cm^2 lies back down at 8.4:1.
TOO_TALL = 1e6        # hard reject: will not fit the bed at all
WATCH_SLENDER = 6.0   # stances flagged in the profile as wanting extra brim
WATCH_PLATE = 1000.0  # mm^2 of contact below which a stance is flagged the same way
BED_FALLBACK = (240.0, 240.0, 240.0)   # usable X1C envelope, if the real one cannot be read
GRID_TOL = 1.02       # slice_for_print.grid_cuts divides a piece by usable*1.02, so a chunk
                      # is allowed to run 2% over the usable envelope -- #134 is 240.7 mm
                      # against a 240 mm usable, and that was a deliberate call, not a bug.
                      # A stance has to be judged by the same rule the cutter used, or the
                      # check rejects chunks in the very axis they were cut to fit.
SUPPORT_CM2 = 5.0     # residual overhang above which a chunk gets listed as wanting support

# Boat-frame face that ends up on the plate -> the rotation that puts it there. Written out
# as exact 0/+-1 entries rather than built from rotation_matrix(pi/2, ...), whose cos(pi/2)
# leaves a 6e-17 residue that would jitter every vertex off its cut plane and cost the
# losslessness the docstring claims. One canonical rotation per face and no spin about z, so
# the label alone is the whole transform and the manifest can carry it in one column.
ROTS = {                                          # identity first: ties keep the boat frame
    "-z (as cut)": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    "+z":          [[1, 0, 0], [0, -1, 0], [0, 0, -1]],
    "+x":          [[0, 0, 1], [0, 1, 0], [-1, 0, 0]],
    "-x":          [[0, 0, -1], [0, 1, 0], [1, 0, 0]],
    "+y":          [[1, 0, 0], [0, 0, 1], [0, -1, 0]],
    "-y":          [[1, 0, 0], [0, 0, -1], [0, 1, 0]],
}
ROTS = {k: np.array(v, dtype=float) for k, v in ROTS.items()}
for _k, _R in ROTS.items():                       # a mirrored "rotation" would invert the part
    assert abs(np.linalg.det(_R) - 1.0) < 1e-12, _k


def rotated(m, R):
    """m turned by R, with topology untouched. Built by hand rather than by apply_transform
    so nothing re-welds or re-winds: same faces, same vertex order, coordinates permuted and
    sign-flipped only."""
    return trimesh.Trimesh(vertices=np.asarray(m.vertices) @ R.T,
                           faces=np.asarray(m.faces), process=False)


def stance(m):
    """(overhang mm^2, first-layer contact mm^2, slenderness) for a mesh resting on its own
    lowest z. Overhang is downward-facing area shallower than ANGLE from horizontal and not
    already lying on the plate -- the same measure a slicer's threshold angle applies, so
    the number is what support would actually have to be built under."""
    zmin = float(m.bounds[0][2])
    n, a, tri = m.face_normals, m.area_faces, m.triangles
    slope = 90.0 - np.degrees(np.arcsin(np.clip(np.abs(n[:, 2]), 0.0, 1.0)))
    on_plate = (tri[:, :, 2].max(axis=1) - zmin) < TOL
    ovh = float(a[(n[:, 2] < -1e-6) & (slope < ANGLE) & ~on_plate].sum())
    e = m.extents
    return ovh, float(a[on_plate].sum()), float(e[2]) / max(1e-9, float(min(e[0], e[1])))


def envelope(out):
    """Usable bed envelope for the folder being oriented, read from slice_for_print's
    PRINTERS so the number has one home. It matters because a rotation can swing a chunk's
    long side onto a short bed axis: on the cubic X1C that is impossible and the check never
    fires, but the Core One is 250 x 220 x 270, so a chunk cut 234 mm long in x genuinely
    does not fit the 204 mm of usable y. Falls back to the X1C cube if slice_for_print will
    not import -- it is edited far more often than this file is run."""
    try:
        import slice_for_print as sp
        for P in sp.PRINTERS.values():
            if P["outdir"] == out.name:
                b, m = P["bed"], sp.MARGIN
                return tuple((x - 2 * m) * GRID_TOL for x in b), P["label"]
        print(f"  no printer in slice_for_print.py writes to {out.name}")
    except Exception as e:
        print(f"  could not read the bed from slice_for_print.py ({e})")
    print(f"  assuming the X1C envelope {BED_FALLBACK}")
    return tuple(x * GRID_TOL for x in BED_FALLBACK), "assumed X1C"


def choose(m, bores, env):
    """Pick a stance. `bores` is the chunk's (axis, count) dowel list. Cost is in mm^2 of
    overhang throughout: the contact bonus, the bore charge and the height charge are all
    converted into that currency by the weights above, so every candidate reduces to one
    comparable number and the trade between them is visible rather than hidden in a veto."""
    best = None
    for label, R in ROTS.items():
        r = rotated(m, R)
        ovh, plate, slender = stance(r)
        horiz = sum(c for ax, c in bores if abs(R[2, ax]) < 0.5)
        cost = (ovh - PLATE_W * min(plate, PLATE_CAP) + BORE_W * horiz
                + TIP_W * max(0.0, slender - SLENDER))
        if np.any(r.extents > np.array(env) + 1e-6):
            cost += TOO_TALL                       # will not fit the bed this way up at all
        if best is None or cost < best[0]:
            best = (cost, label, R, ovh, plate, horiz, slender, r)
    return best


def bore_axes(rows):
    """Dowel bore axis per chunk, recovered from the manifest rather than re-derived: two
    chunks that share a face differ in exactly one grid index, and that index is the axis the
    cut normal -- and so the bore -- runs along."""
    ijk = {r["seq"]: tuple(int(v) for v in r["grid_ijk"].split(",")) for r in rows}
    out = {}
    for r in rows:
        b = []
        for tok in filter(None, r["mates_to(dowels)"].split(";")):
            nb, cnt = tok.split("("); nb = nb.lstrip("#"); cnt = int(cnt.rstrip(")"))
            if nb not in ijk:
                continue
            d = [i for i in range(3) if ijk[nb][i] != ijk[r["seq"]][i]]
            if len(d) == 1:
                b.append((d[0], cnt))
        out[r["seq"]] = b
    return out


NOTE = """
ORIENTATION  --  already applied, do not re-orient
  Every chunk in this folder was exported standing on the flat cut face that
  prints best, by orient_chunks.py. Import it and print it as it lands: do not
  auto-orient it, and do not rotate it back to look like the boat. It is the
  same solid either way, only described from a different corner, so nothing
  about the fit or the dowels changes.
  The `orient` column in manifest.csv names which boat-frame face is on the
  plate, if you need to work out which way round a chunk goes at the bench.
  `-z (as cut)` means it was already sitting the best way up.

SUPPORT
  {support}
  Where support IS needed, what is left is broad shallow ceiling, not sharp
  tails, so: type normal(auto), threshold angle 30, "on build plate only" OFF
  (these overhangs sit over the part, not over the plate), and "support
  critical regions only" OFF -- that setting looks for cantilevers and sharp
  tails and will walk straight past a 7-degree roof.
{watch}"""


def verify(out, arch):
    """Prove the parts did not change. For every chunk, look for a rotation in ROTS that
    carries the archived vertex array onto the current one with np.array_equal -- exact
    equality, not a tolerance. That can be demanded because every entry of every R is 0 or
    +-1, so each output coordinate is a copy or a sign flip of an input coordinate and the
    float32 an STL stores round-trips it untouched. Faces are compared index for index, so
    the topology is checked too. A tolerance-based check would pass on a mesh that had been
    quietly re-welded; this will not."""
    rows = list(csv.DictReader(open(out / "manifest.csv")))
    bad = []
    for r in rows:
        a = trimesh.load(str(arch / r["piece"] / r["file"]), process=False)
        b = trimesh.load(str(out / r["piece"] / r["file"]), process=False)
        va, vb = np.asarray(a.vertices), np.asarray(b.vertices)
        ok = (np.array_equal(np.asarray(a.faces), np.asarray(b.faces)) and va.shape == vb.shape
              and any(np.array_equal(va @ R.T, vb) for R in ROTS.values()))
        if not ok:
            bad.append(r["file"])
    print(f"verify {out}  vs  {arch}")
    if bad:
        print(f"  !! {len(bad)} chunk(s) are NOT a pure rotation of the archived part:")
        for f in bad[:10]:
            print(f"       {f}")
        return 1
    print(f"  all {len(rows)} chunks are the archived solid exactly, rotated and nothing else:")
    print(f"  identical faces, identical vertex count, vertices equal bit for bit under one")
    print(f"  of the six rotations. Anything already printed is still the right part.")
    return 0


def newest_archive(out):
    c = sorted(Path("split_out/archive").glob(f"{out.name}__pre-orient_*"))
    return c[-1] if c else None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    out = Path(args[0] if args else "split_out/print_sections_x1c")
    dry = "--dry-run" in flags
    if "--verify" in flags:
        arch = Path(args[1]) if len(args) > 1 else newest_archive(out)
        if arch is None or not arch.exists():
            sys.exit(f"no archive to verify against under split_out/archive/")
        sys.exit(verify(out, arch))
    man = out / "manifest.csv"
    if not man.exists():
        sys.exit(f"no manifest at {man} -- run slice_for_print.py first")
    rows = list(csv.DictReader(open(man)))
    arch = newest_archive(out)
    if "orient" in rows[0]:
        # Already oriented. Orienting again would search the six stances from the frame the
        # chunk is ALREADY in, so the winning transform would compose with the one baked in
        # and land outside the labelled six -- geometrically harmless, but the manifest
        # would then name a face that is not the one on the plate, which is worse than
        # useless at the bench. So a re-run always starts from the archived original.
        if "--force" not in flags:
            sys.exit(f"{man} already has an orient column: this folder has been oriented.\n"
                     f"Pass --force to redo it from the archive (needed after changing the "
                     f"weights above).")
        if arch is None:
            sys.exit("--force needs the pre-orient archive to restore from, and there is none")
        print(f"  --force: restoring the as-cut chunks from {arch} first")
        for f in arch.glob("*/*.stl"):
            shutil.copy2(f, out / f.parent.name / f.name)
        shutil.copy2(arch / "manifest.csv", man)
        for f in arch.glob("*/PROFILE.txt"):
            shutil.copy2(f, out / f.parent.name / f.name)
        rows = list(csv.DictReader(open(man)))
    if arch is None and not dry:
        sys.exit(f"refusing to rewrite {out} with no archive of it under split_out/archive/ "
                 f"-- chunks have been printed from this folder and the STLs are the record "
                 f"of what came off the plate. Copy it there first.")
    bores = bore_axes(rows)

    print(f"Orienting {out}  ({len(rows)} chunks){'  [DRY RUN]' if dry else ''}")
    env, plabel = envelope(out)
    print(f"  bed: {plabel}, usable {env[0]:.0f} x {env[1]:.0f} x {env[2]:.0f} mm")
    was = now = 0.0
    horiz_total = 0
    kept = 0
    per_piece = {}
    watch = []                                    # tall or lightly-seated stances, reported
    for r in rows:
        f = out / r["piece"] / r["file"]
        m = trimesh.load(str(f), process=False)
        v0, f0, vol0 = len(m.vertices), len(m.faces), abs(m.volume)
        before = stance(m)[0]
        cost, label, R, ovh, plate, nh, slender, rm = choose(m, bores.get(r["seq"], []), env)
        if cost >= TOO_TALL:                      # cannot happen: identity fits by construction
            print(f"  !! {r['file']}: no stance fits this bed, left as cut")
            label, R, rm = "-z (as cut)", ROTS["-z (as cut)"], m
            ovh, plate, slender = stance(m)
        was += before; now += ovh; horiz_total += nh
        if slender > WATCH_SLENDER or plate < WATCH_PLATE:
            watch.append((r["seq"], slender, plate / 100.0))
        kept += (label == "-z (as cut)")
        d = rm.bounds[1] - rm.bounds[0]
        r["orient"] = label
        r["bbox_mm"] = f"{d[0]:.0f}x{d[1]:.0f}x{d[2]:.0f}"
        per_piece.setdefault(r["piece"], []).append((r["seq"], ovh / 100.0))
        # The solid must be untouched: same topology, same volume, and -- because every
        # entry of R is 0 or +-1 -- coordinates that are copies and sign flips of the
        # originals, hence exactly representable in the float32 an STL stores.
        assert (len(rm.vertices), len(rm.faces)) == (v0, f0), r["file"]
        assert vol0 <= 0 or abs(abs(rm.volume) - vol0) / vol0 < 1e-9, r["file"]
        if not dry:
            rm.export(str(f))
    print(f"  support area over the whole set: {was/100:8.0f} cm^2 as cut"
          f"  ->  {now/100:.0f} cm^2 oriented   ({(1-now/max(was,1e-9))*100:.0f}% less)")
    print(f"  {kept}/{len(rows)} chunks were already sitting the best way up")
    print(f"  {horiz_total} dowel bore ends left horizontal (they bridge; see PROFILE.txt)")
    if watch:
        print(f"  {len(watch)} chunk(s) stand tall or seat lightly -- brim these hard:")
        for seq, sl, pl in sorted(watch, key=lambda t: -t[1])[:10]:
            print(f"      #{seq}  {sl:.1f}:1 tall, {pl:.0f} cm^2 on the plate")

    if dry:
        print("  dry run: nothing written")
        return

    with open(man, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    for piece, lst in per_piece.items():
        need = sorted([(s, c) for s, c in lst if c >= SUPPORT_CM2], key=lambda t: -t[1])
        if not need:
            sup = ("OFF for every chunk in this folder. Standing them on a cut face\n"
                   "  removed the overhangs; there is nothing left to hold up.")
        else:
            names = ", ".join(f"#{s} ({c:.0f} cm2)" for s, c in need[:12])
            more = "" if len(need) <= 12 else f", and {len(need)-12} more"
            sup = (f"OFF for every chunk in this folder EXCEPT {len(need)} of {len(lst)}:\n"
                   f"  {names}{more}.\n"
                   f"  Those are the chunks whose skin curves away on more than one side, so\n"
                   f"  no flat face gets all of it. Everything else prints support-free.")
        w = sorted([x for x in watch if x[0] in {s_ for s_, _ in lst}], key=lambda t: -t[1])
        if not w:
            wtxt = ""
        else:
            wtxt = ("\nBRIM THESE HARD\n"
                    "  Each of these is either standing on edge or sitting on very little\n"
                    "  plate -- which is exactly what buys most of them a support-free\n"
                    "  print, so it is a stance worth keeping rather than a fault. Give\n"
                    "  them the full 8 mm brim, keep the door shut, and watch the first\n"
                    "  layer rather than walking away from it:\n"
                    + "".join("    #%s   %s\n" % (
                        q, (f"{sl:.1f}:1 tall, on {pl:.0f} cm2 of plate" if sl > WATCH_SLENDER
                            else f"seated on only {pl:.0f} cm2 of plate"))
                        for q, sl, pl in w))
        p = out / piece / "PROFILE.txt"
        if p.exists():
            t = p.read_text()
            t = t.split("\nORIENTATION  --")[0].rstrip() + "\n" + NOTE.format(support=sup, watch=wtxt)
            p.write_text(t)
    print(f"  manifest.csv + {len(per_piece)} PROFILE.txt updated")


if __name__ == "__main__":
    main()
