#!/usr/bin/env python3
"""Clean renders of the generated geometry, for the docs site and the build-day deck.

Both consumers read docs/assets/, so there is one renderer and one set of files.

Two things matplotlib does wrong here unless you make it behave:

  DEPTH. It sorts polygons by depth WITHIN a Poly3DCollection, then draws collections in
  the order added, so N meshes as N collections ignores depth BETWEEN them and they punch
  through each other. Everything goes into ONE merged collection so the sort is global.
  Each hollow shell's near wall then covers its own interior and parts read solid, with no
  back-face culling (culling instead makes thin-walled chunks read as open crates).

  DECIMATION. Cutting a curved thin-walled mesh to a few hundred faces makes long thin
  triangles with scrambled normals, which shades as dark shards. Keep the budget generous
  and run fix_normals after any decimation.

Run:  .venv/bin/python render_views.py
"""
import numpy as np, trimesh, csv, re, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from pathlib import Path
from PIL import Image

REPO = Path(__file__).resolve().parent
OUT = REPO / "docs/assets"
SPLIT = REPO / "split_out"
ARCH = SPLIT / "archive/print_sections_x1c__pre-orient_2026-08-31"
LIGHT = np.array([-0.38, -0.72, 0.58]); LIGHT /= np.linalg.norm(LIGHT)
PAL = {"center": "#3F6FA3", "bow": "#3FA39B", "wedge_stbd": "#E0A53A", "wedge_port": "#D9694A"}


def shade(m, rgb, amb=0.40):
    lam = np.clip(m.face_normals @ LIGHT, 0, 1) * (1 - amb) + amb
    return np.clip(np.asarray(matplotlib.colors.to_rgb(rgb), float)[None, :] * lam[:, None], 0, 1)


def dec(m, n):
    if len(m.faces) <= n:
        return m
    s = m.simplify_quadric_decimation(face_count=n)
    trimesh.repair.fix_normals(s)
    return s


def solid(mc, fn, elev=20, azim=-62, figsize=(15, 7)):
    t, c, v = [], [], []
    for m, col in mc:
        t.append(m.triangles); c.append(shade(m, col)); v.append(m.vertices)
    fig = plt.figure(figsize=figsize); ax = fig.add_subplot(111, projection="3d")
    ax.add_collection3d(Poly3DCollection(np.concatenate(t), facecolors=np.concatenate(c),
                                         edgecolors="none", linewidths=0, zsort="average"))
    p = np.vstack(v); lo, hi = p.min(0), p.max(0)
    ctr = (lo + hi) / 2; s = (hi - lo).max() / 2
    ax.set_xlim(ctr[0]-s, ctr[0]+s); ax.set_ylim(ctr[1]-s, ctr[1]+s); ax.set_zlim(ctr[2]-s, ctr[2]+s)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=elev, azim=azim); ax.set_axis_off()
    fig.subplots_adjust(0, 0, 1, 1)
    fig.savefig(OUT / fn, dpi=200, transparent=True, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    im = Image.open(OUT / fn); im.crop(im.split()[-1].getbbox()).save(OUT / fn)
    print("wrote", fn, Image.open(OUT / fn).size, flush=True)


def load(name, faces):
    return dec(trimesh.load(str(SPLIT / f"{name}.stl")), faces)


OUT.mkdir(parents=True, exist_ok=True)

# the assembled hull. Decimating this hard shatters it, so keep it dense.
solid([(dec(trimesh.load(str(SPLIT / "dinghy_assembled.stl")), 120000), "#3F6FA3")],
      "hero.png", elev=17, figsize=(15, 6.2))

# the four transportable pieces
parts = []
for name, off in (("center", [0,0,0]), ("bow", [30,0,0]),
                  ("wedge_stbd", [0,26,0]), ("wedge_port", [0,-26,0])):
    m = load(name, 60000); m.apply_translation(off); parts.append((m, PAL[name]))
solid(parts, "four_pieces.png", elev=24, azim=-60, figsize=(15, 6.6))

# one wedge lifted off the barge, which is what shows the drop-in dovetail keys
w = load("wedge_stbd", 60000); w.apply_translation([0, 13, 15])
solid([(load("center", 80000), PAL["center"]), (w, PAL["wedge_stbd"])],
      "joint.png", elev=17, azim=-74, figsize=(15, 7))

# the bow exploded along the grid it is actually cut on. A named colormap ran to near
# white at one end and vanished on a light page, so ramp between mid-tone stops instead.
STOPS = np.array([[0.14, 0.31, 0.48], [0.24, 0.56, 0.61], [0.79, 0.64, 0.15]])
rows = [r for r in csv.DictReader(open(SPLIT / "print_sections_x1c/manifest.csv"))
        if r["piece"] == "bow"]
ijk = {r["seq"]: tuple(map(int, re.search(r"x(\d+)y(\d+)z(\d+)", r["file"]).groups())) for r in rows}
mid = np.array(list(ijk.values())).mean(axis=0); imax = max(v[0] for v in ijk.values())
GAP = np.array([34.0, 30.0, 30.0])            # mm of daylight per grid step
chunks = []
for r in rows:
    m = trimesh.load(str(ARCH / "bow" / r["file"])); trimesh.repair.fix_normals(m)
    m.apply_translation((np.array(ijk[r["seq"]]) - mid) * GAP)
    t = ijk[r["seq"]][0] / max(1, imax) * (len(STOPS) - 1)
    i0 = int(np.clip(np.floor(t), 0, len(STOPS) - 2)); f = t - i0
    chunks.append((m, tuple(STOPS[i0] * (1 - f) + STOPS[i0 + 1] * f)))
solid(chunks, "bow_chunks.png", figsize=(15, 7.4))
print("done ->", OUT)
