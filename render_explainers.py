#!/usr/bin/env python3
"""
render_explainers.py - clean explainer figures for the Rev-3 split dinghy.

Produces two clear diagrams that supersede the busy dovetail_detail.png /
transport_packing.png that dinghy_split.py emits:

  split_out/dovetail_clean.png - exploded + assembled cross-section of the sliding
                                 dovetail (center groove <-> wedge tongue) + a 3D
                                 zoom of the real parts pulled apart.
  split_out/packing_clean.png  - the two transport loads: (1) center with the bow
                                 nested inside, (2) the two wedges flipped into a
                                 bundle. Orthographic, labelled, real inches.

Run after (or independently of) dinghy_split.py:
    .venv/bin/python render_explainers.py
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from pathlib import Path

import dinghy_split as ds

hull = ds.DinghyHull()
S = ds.DESIGN_SCALE
OUT = Path("split_out")
OUT.mkdir(exist_ok=True)


def render_dovetail():
    """Vertical drop-in dovetail keys: horizontal cross-section through a key (the
    dovetail flare), a side elevation showing all keys down the joint, and a 3D zoom
    with the wedge lifted to reveal a tongue/socket pair."""
    xk = ds.KEY_X[0]
    yc = ds.ycut(xk)
    M, B, D, T = ds.KEY_MOUTH / 2, ds.KEY_BACK / 2, ds.KEY_DEPTH, ds.KEY_STUB
    # key (tongue) profile in the x-y plane, real inches, stbd side
    tongue = [((xk - M) * S, (yc + T) * S), ((xk + M) * S, (yc + T) * S),
              ((xk + M) * S, yc * S), ((xk + B) * S, (yc - D) * S),
              ((xk - B) * S, (yc - D) * S), ((xk - M) * S, yc * S)]
    socket = [((xk - M) * S, yc * S), ((xk + M) * S, yc * S),
              ((xk + B) * S, (yc - D) * S), ((xk - B) * S, (yc - D) * S)]   # cut into center
    xL, xR = (xk - B - 1.4) * S, (xk + B + 1.4) * S
    yIn, yOut = (yc - D - 1.4) * S, (yc + 2.2) * S
    crect = [(xL, yIn), (xR, yIn), (xR, yc * S), (xL, yc * S)]
    wrect = [(xL, yc * S), (xR, yc * S), (xR, yOut), (xL, yOut)]
    shift = lambda poly, g: [(x, y + g) for (x, y) in poly]

    fig = plt.figure(figsize=(15, 8.5))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1])

    # --- top row: horizontal cross-section (looking DOWN on the joint) ---
    for col, (title, g) in enumerate([("EXPLODED (wedge lifted)", 2.4 * S), ("ASSEMBLED", 0.0)]):
        ax = fig.add_subplot(gs[0, col]); ax.set_aspect("equal")
        ax.add_patch(MPoly(crect, fc="#9ec5f0", ec="#2b6cb0", lw=1.6))
        ax.add_patch(MPoly(socket, fc="white", ec="#2b6cb0", lw=1.4, ls="--"))     # socket
        ax.add_patch(MPoly(shift(wrect, g), fc="#f6cf5b", ec="#b8860b", lw=1.6))
        ax.add_patch(MPoly(shift(tongue, g), fc="#f3c33a", ec="#b8860b", lw=1.6))  # tongue
        ax.text(xL + 0.2, yIn + 0.3, "CENTER", color="#1a4e8a", fontweight="bold", fontsize=10)
        ax.text(xL + 0.2, yOut + g - 0.6, "WEDGE", color="#8a5a00", fontweight="bold", fontsize=10)
        if g > 0:
            ax.annotate(f"flare: back {ds.KEY_BACK:.1f}\" >\nmouth {ds.KEY_MOUTH:.1f}\"\n=> locks pull-apart",
                        xy=((xk + B) * S, (yc - D) * S), xytext=(xR - 0.2, yIn + 0.4),
                        fontsize=8, color="#333", ha="right", arrowprops=dict(arrowstyle="->", color="#333"))
            ax.text((xk) * S, yOut + g + 0.5, "socket open at rim ->\nwedge drops straight down",
                    ha="center", fontsize=8, color="#8a5a00")
        ax.set_xlim(xL - 0.3, xR + 0.3); ax.set_ylim(yIn - 0.4, yOut + g + 1.8)
        ax.set_xlabel("fore-aft x (real in)"); ax.set_title(title, fontsize=11, fontweight="bold")
        if col == 0: ax.set_ylabel("beam y (real in)")
        ax.grid(alpha=0.15)

    # --- bottom-left: side elevation (x-z), all keys down the joint ---
    axs = fig.add_subplot(gs[1, 0]); axs.set_aspect("equal")
    xs = np.linspace(0, ds.BOW_SPLIT, 140)
    szz = np.array([hull.interp(x)[3] for x in xs]) * S
    zcz = np.array([(ds.cross_z(hull.half_outer(x), ds.ycut(x)) or hull.interp(x)[3]) for x in xs]) * S
    axs.fill_between(xs * S, zcz, szz, color="#cfe0f5", ec="#2b6cb0", lw=1.2, label="mating wall (stbd)")
    axs.plot(xs * S, np.array([hull.interp(x)[5] for x in xs]) * S + ds.WATERLINE, "b--", lw=1, label="waterline")
    for i, kx in enumerate(ds.KEY_X):
        z0 = (hull.interp(kx)[5] + ds.WATERLINE / S + 1.0) * S
        z1 = hull.interp(kx)[3] * S
        axs.add_patch(MPoly([((kx - B) * S, z0), ((kx + B) * S, z0),
                             ((kx + B) * S, z1), ((kx - B) * S, z1)], fc="#f3c33a", ec="#b8860b", lw=1.4,
                            label="dovetail key" if i == 0 else None))
        axs.annotate("", xy=((kx) * S, z1 - 0.3), xytext=((kx) * S, z1 + 3.5),
                     arrowprops=dict(arrowstyle="-|>", color="#b8860b", lw=2))
    axs.text(ds.BOW_SPLIT * S * 0.5, szz.max() + 4.2, "wedge drops DOWN onto the keys", ha="center",
             fontsize=9, color="#8a5a00", fontweight="bold")
    axs.set_xlim(-2, ds.BOW_SPLIT * S + 2); axs.set_ylim(0, szz.max() + 6)
    axs.set_xlabel("fore-aft x (real in)"); axs.set_ylabel("height z (real in)")
    axs.set_title(f"{ds.N_KEYS} vertical keys down the joint (side view)", fontsize=11, fontweight="bold")
    axs.legend(fontsize=8, loc="lower right"); axs.grid(alpha=0.15)

    # --- bottom-right: 3D, real meshes at one key, wedge lifted ---
    ax3 = fig.add_subplot(gs[1, 1], projection="3d")
    pieces = ds.add_vertical_dovetails(hull, {
        "center": ds.to_trimesh(ds.build_center(hull)),
        "wedge_stbd": ds.to_trimesh(ds.build_wedge(hull, +1)),
        "wedge_port": ds.to_trimesh(ds.build_wedge(hull, -1))})
    ctr, wdg = pieces["center"], pieces["wedge_stbd"]
    szk = hull.interp(xk)[3]

    def patch(m, dz):
        out = []
        for f in m.faces:
            c = m.vertices[f].mean(0)
            if (xk - 5) <= c[0] <= (xk + 5) and (szk - 9) < c[2] + dz < (szk + 7):
                out.append([(m.vertices[k][0], m.vertices[k][1], m.vertices[k][2] + dz) for k in f])
        return out

    ax3.add_collection3d(Poly3DCollection(patch(ctr, 0), facecolor="#9ec5f0", edgecolor="#2b6cb0", lw=.2, alpha=.97))
    ax3.add_collection3d(Poly3DCollection(patch(wdg, 6), facecolor="#f3c33a", edgecolor="#b8860b", lw=.2, alpha=.97))
    ax3.set_xlim(xk - 5, xk + 5); ax3.set_ylim(yc - 4, yc + 8); ax3.set_zlim(szk - 9, szk + 8)
    ax3.view_init(16, -62); ax3.set_box_aspect([1.3, 1.4, 1.4])
    ax3.set_title("3D: wedge lifted up (tongue clears socket)", fontsize=11, fontweight="bold")
    for pa in (ax3.xaxis, ax3.yaxis, ax3.zaxis):
        pa.pane.fill = False
    fig.suptitle(f"Vertical drop-in dovetail keys  -  {ds.N_KEYS} per side, "
                 f"{ds.KEY_DEPTH*S:.2f}\" deep, flare {ds.KEY_MOUTH*S:.1f}\"->{ds.KEY_BACK*S:.1f}\"",
                 fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(str(OUT / "dovetail_clean.png"), dpi=120, bbox_inches="tight")
    plt.close()


def render_packing():
    xs = np.linspace(0, ds.BOW_SPLIT, 60)
    chw = np.array([ds.ycut(x) for x in xs]) * S
    xr = xs * S
    xb = np.linspace(ds.BOW_SPLIT, ds.LOA - ds.NOSE_ROUND, 40)
    bhw = np.array([max(p[0] for p in ds.bow_section(hull, x)) for x in xb]) * S
    bxr = (xb - ds.BOW_SPLIT) * S
    whw = np.array([hull.interp(x)[2] - ds.ycut(x) for x in xs]) * S
    cL, cW = xr[-1], 2 * chw.max()
    cH = (hull.interp(0)[3] - hull.interp(0)[5]) * S
    wL, wW, wH = 53.1, whw.max(), 19.0

    fig = plt.figure(figsize=(14, 7))
    fig.suptitle("Transport = 2 compact loads  (both fit the GLC, < 30\" tall)",
                 fontsize=15, fontweight="bold")

    ax1 = fig.add_subplot(2, 2, 1); ax1.set_aspect("equal")
    ax1.fill_between(xr, chw, -chw, color="#dbe9fb", ec="#2b6cb0", lw=2, label="center hull")
    ax1.fill_between(bxr, bhw, -bhw, color="#9ed0a8", ec="#2f855a", lw=1.6, alpha=0.9,
                     label="bow (nested inside)")
    ax1.set_title("LOAD 1 - top view:  center, bow nested inside", fontsize=11, fontweight="bold")
    ax1.legend(fontsize=8, loc="upper right"); ax1.set_xlim(-2, cL + 2); ax1.set_ylim(-cW / 2 - 3, cW / 2 + 3)
    ax1.set_xlabel("length (real in)"); ax1.grid(alpha=0.15)
    ax1.annotate(f"{cL:.0f}\" long", (cL / 2, -cW / 2 - 1.5), ha="center", fontsize=9)
    ax1.annotate(f"{cW:.0f}\" wide", (-1.5, 0), rotation=90, va="center", fontsize=9)

    ax2 = fig.add_subplot(2, 2, 3); ax2.set_aspect("equal")
    ax2.add_patch(Rectangle((-cW / 2, 0), cW, cH, fc="#dbe9fb", ec="#2b6cb0", lw=2))
    ax2.add_patch(Rectangle((-cW / 2 + 1.5, 1), cW - 3, cH - 1, fc="none", ec="#999", lw=1, ls="--"))
    ax2.text(0, cH + 1.2, "bow tucks in here", ha="center", fontsize=8, color="#2f855a")
    ax2.set_title(f"LOAD 1 - end view:  {cW:.0f}\"W x {cH:.0f}\"H", fontsize=11, fontweight="bold")
    ax2.set_xlim(-cW / 2 - 3, cW / 2 + 3); ax2.set_ylim(-2, cH + 4)
    ax2.set_xlabel("width (real in)"); ax2.grid(alpha=0.15)

    ax3 = fig.add_subplot(1, 2, 2); ax3.set_aspect("equal")
    ax3.fill_between(xr, cW / 2 * np.ones_like(xr), cW / 2 - whw, color="#fbe6a6", ec="#b8860b", lw=1.8)
    ax3.fill_between(xr, cW / 2 - wW - whw[::-1], (cW / 2 - wW) * np.ones_like(xr),
                     color="#f4c95d", ec="#b8860b", lw=1.8)
    ax3.text(cL * 0.5, cW / 2 - wW * 0.45, "wedge", ha="center", fontsize=9, color="#7a5b00")
    ax3.text(cL * 0.5, cW / 2 - wW * 1.55, "wedge (flipped)", ha="center", fontsize=9, color="#7a5b00")
    ax3.set_title(f"LOAD 2 - 2 wedges flip into a bundle\n~{wL:.0f}\"L x {2*wW:.0f}\"W x {wH:.0f}\"H",
                  fontsize=11, fontweight="bold")
    ax3.set_xlim(-2, cL + 2); ax3.set_xlabel("length (real in)"); ax3.set_ylabel("width (real in)")
    ax3.grid(alpha=0.15)
    ax3.annotate("two triangles flip together\n-> compact slab", (cL * 0.5, cW / 2 - wW),
                 ha="center", fontsize=8, color="#555")

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(str(OUT / "packing_clean.png"), dpi=120, bbox_inches="tight")
    plt.close()


if __name__ == "__main__":
    render_dovetail()
    render_packing()
    print("Saved split_out/dovetail_clean.png and split_out/packing_clean.png")
