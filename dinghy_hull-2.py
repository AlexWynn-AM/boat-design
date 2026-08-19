#!/usr/bin/env python3
"""
dinghy_hull.py - Parametric 9ft ASA-Core Planing Dinghy Hull Generator

Generates STL files and preview renders of a planing dinghy hull with:
- Parametric station-based hull definition
- Sigmoid spray rail integrated into topsides
- Wide gunwale seats with wall thickness
- Bow locker with nose platform and bulkhead with U-cutout
- Solid transom

Usage:
    python dinghy_hull.py                    # Generate STL + preview
    python dinghy_hull.py --scale 10         # 1:10 scale model (mm)
    python dinghy_hull.py --no-preview       # STL only, no plots

Requirements:
    pip install numpy trimesh matplotlib

Design parameters are at the top of the file. Edit and re-run.
"""

import numpy as np
import argparse
from pathlib import Path

# ============================================================
# DESIGN PARAMETERS - Edit these
# ============================================================

# Hull stations: (x_from_transom_in, bottom_half_beam, chine_z, sheer_half_beam, sheer_z, deadrise_deg)
# x=0 is the transom, x increases toward the bow
STATIONS = [
    (0,    30.0,  2.6,  34.0,  22.0,   5),   # transom: full 5ft bottom
    (12,   30.0,  2.6,  34.0,  22.0,   5),   # maintain full width
    (24,   29.0,  2.8,  33.5,  22.0,   6),   # begin taper
    (36,   27.0,  3.0,  32.0,  22.0,   8),
    (54,   22.0,  3.0,  28.0,  22.5,  12),   # midships
    (72,   16.0,  4.0,  21.0,  23.0,  14),
    (90,    8.0,  7.0,  12.0,  24.0,  18),
    (105,   2.0, 12.0,   4.5,  25.0,  25),
    (108,   0.5, 14.0,   1.5,  25.5,  30),   # stem
]

LOA = 108           # inches (9 ft)
GUNWALE_DEPTH = 8.0 # inches (width of gunwale sitting surface)
WALL_THICKNESS = 0.75  # inches (hull panel wall thickness)

# Spray rail
SPRAY_RAIL_OUTWARD = 1.5   # inches outboard bulge at rail
SPRAY_RAIL_HEIGHT_FRAC = 0.35  # fraction up topside where rail peaks

# Bow locker
BULKHEAD_X = 78.0   # inches from transom (= 30" from stem)
U_HALF_WIDTH = 10.5  # inches (half-width of U-cutout)
U_DEPTH = 12.0       # inches (depth of U-cutout from top)
U_RADIUS = 4.5       # inches (radius of rounded U bottom)

# Mesh resolution
N_STATIONS = 60     # longitudinal stations
N_BOTTOM = 12       # points along bottom half-section
N_SIDE = 10         # points along topside half-section
N_GW = 2            # points across gunwale top
N_U_CURVE = 12      # points on U-cutout curve
N_NOSE = 20         # stations for nose platform


# ============================================================
# HULL GEOMETRY ENGINE
# ============================================================

class DinghyHull:
    def __init__(self):
        self.sta_x = np.array([s[0] for s in STATIONS])
        self.sta_bhw = np.array([s[1] for s in STATIONS])
        self.sta_cz = np.array([s[2] for s in STATIONS])
        self.sta_shw = np.array([s[3] for s in STATIONS])
        self.sta_sz = np.array([s[4] for s in STATIONS])
        self.sta_dr = np.array([s[5] for s in STATIONS])
        self.sta_kz = self.sta_cz - self.sta_bhw * np.tan(np.radians(self.sta_dr))

    def interp(self, x):
        """Interpolate hull geometry at any longitudinal position."""
        return (
            np.interp(x, self.sta_x, self.sta_bhw),
            np.interp(x, self.sta_x, self.sta_cz),
            np.interp(x, self.sta_x, self.sta_shw),
            np.interp(x, self.sta_x, self.sta_sz),
            np.interp(x, self.sta_x, self.sta_dr),
            np.interp(x, self.sta_x, self.sta_kz),
        )

    def inner_hw(self, x):
        """Inner gunwale half-width at station x."""
        _, _, shw, _, _, _ = self.interp(x)
        return max(0.5, shw - GUNWALE_DEPTH)

    def half_outer(self, x):
        """Outer hull half-section (keel to sheer), starboard side."""
        bhw, cz, shw, sz, dr, kz = self.interp(x)
        pts = []
        for i in range(N_BOTTOM + 1):
            f = i / N_BOTTOM
            pts.append((f * bhw, kz + f * (cz - kz)))
        for i in range(1, N_SIDE + 1):
            f = i / N_SIDE
            yl = bhw + f * (shw - bhw)
            zv = cz + f * (sz - cz)
            bulge = SPRAY_RAIL_OUTWARD * np.exp(
                -0.5 * ((f - SPRAY_RAIL_HEIGHT_FRAC) / 0.2) ** 2
            )
            pts.append((yl + bulge, zv))
        return pts

    def half_inner(self, x):
        """Inner hull half-section (keel to sheer), starboard side."""
        bhw, cz, shw, sz, dr, kz = self.interp(x)
        ihw = self.inner_hw(x)
        gw_zone_h = 7.0
        gw_zone_bot = sz - gw_zone_h
        dy, dz = shw - bhw, sz - cz
        slen = max(0.001, np.sqrt(dy**2 + dz**2))
        nx_s = dz / slen

        pts = []
        # Bottom inner
        for i in range(N_BOTTOM + 1):
            f = i / N_BOTTOM
            y = f * bhw
            z = kz + f * (cz - kz)
            nx = np.sin(np.radians(dr))
            nz = np.cos(np.radians(dr))
            pts.append((max(0, y - WALL_THICKNESS * nx), z + WALL_THICKNESS * nz))
        # Topside inner
        for i in range(1, N_SIDE + 1):
            f = i / N_SIDE
            yo = bhw + f * (shw - bhw)
            zo = cz + f * (sz - cz)
            gw_d = shw - ihw
            if zo >= gw_zone_bot:
                gf = min(1, max(0, (zo - gw_zone_bot) / gw_zone_h))
                off = WALL_THICKNESS + gf * (gw_d - WALL_THICKNESS)
            else:
                off = WALL_THICKNESS * nx_s
            pts.append((max(0, yo - off), zo))
        return pts

    def build_ring(self, x):
        """Build closed wall cross-section ring at station x."""
        o_stbd = self.half_outer(x)
        i_stbd = self.half_inner(x)
        _, _, shw, sz, _, _ = self.interp(x)
        ihw = self.inner_hw(x)

        ring = []
        # Port outer (sheer down to keel)
        ring.extend([(-y, z) for y, z in reversed(o_stbd[1:])])
        # Starboard outer (keel up to sheer)
        ring.extend(o_stbd)
        # Starboard gunwale top
        oy, iy = o_stbd[-1][0], i_stbd[-1][0]
        for i in range(1, N_GW + 1):
            f = i / (N_GW + 1)
            ring.append((oy + f * (iy - oy), sz))
        # Starboard inner (sheer down to keel)
        ring.extend(list(reversed(i_stbd)))
        # Port inner (keel up to sheer)
        ring.extend([(-y, z) for y, z in i_stbd[1:]])
        # Port gunwale top
        for i in range(1, N_GW + 1):
            f = i / (N_GW + 1)
            ring.append((-iy + f * (-oy + iy), sz))
        return ring

    def _hull_wall_hw_at_z(self, z):
        """Half-width of hull wall at height z at the bulkhead station."""
        bhw, cz, shw, sz, dr, kz = self.interp(BULKHEAD_X)
        if z <= kz:
            return 0
        elif z <= cz:
            fr = (z - kz) / (cz - kz) if (cz - kz) > 0 else 1
            return fr * bhw
        else:
            fr = min(1, (z - cz) / (sz - cz)) if (sz - cz) > 0 else 1
            return bhw + fr * (shw - bhw)

    def _u_cutout_hw_at_z(self, z):
        """Half-width of U-cutout opening at height z. Returns 0 below cutout."""
        _, _, _, sz, _, _ = self.interp(BULKHEAD_X)
        z_curve_top = sz - (U_DEPTH - U_RADIUS)
        z_curve_bottom = sz - U_DEPTH

        if z >= z_curve_top:
            return U_HALF_WIDTH  # in straight vertical part or above
        elif z >= z_curve_bottom:
            # In curved part: elliptical arc
            z_center = sz - U_DEPTH + U_RADIUS
            dz = z - z_center
            if abs(dz) > U_RADIUS:
                return 0
            return U_HALF_WIDTH * np.sqrt(max(0, 1 - (dz / U_RADIUS) ** 2))
        return 0  # below cutout

    def build_bulkhead_quads(self):
        """Build bulkhead as horizontal quad strips with U-cutout.
        
        Returns list of (y_left, y_right, z_bottom, z_top) tuples.
        Each quad is a simple rectangle, trivially meshed as 2 triangles.
        The U-cutout is formed by splitting strips into port/starboard halves.
        """
        _, cz, _, sz, _, kz = self.interp(BULKHEAD_X)

        n_strips = 300
        z_vals = np.linspace(kz + 0.3, sz, n_strips + 1)
        quads = []

        for i in range(n_strips):
            z_bot = z_vals[i]
            z_top = z_vals[i + 1]
            z_mid = (z_bot + z_top) / 2

            hw = self._hull_wall_hw_at_z(z_mid)
            u_hw = self._u_cutout_hw_at_z(z_mid)

            if hw <= 0.1:
                continue

            if u_hw <= 0.1:
                # No cutout: full width strip
                quads.append((-hw, hw, z_bot, z_top))
            elif u_hw >= hw - 0.1:
                # Cutout wider than hull: no material
                continue
            else:
                # Split: port and starboard solid regions
                quads.append((-hw, -u_hw, z_bot, z_top))
                quads.append((u_hw, hw, z_bot, z_top))

        return quads


# ============================================================
# MESH BUILDER
# ============================================================

def ear_clip(indices, verts, flip=False):
    """Ear-clipping triangulation for a 2D polygon (projected to y-z plane)."""
    pts = np.array([(verts[i][1], verts[i][2]) for i in indices])
    n = len(pts)

    def cross2(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def point_in_tri(p, a, b, c):
        d1, d2, d3 = cross2(p, a, b), cross2(p, b, c), cross2(p, c, a)
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))

    area = sum(
        pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
        for i in range(n)
    )
    ccw = area > 0

    rem = list(range(n))
    tris = []
    safe = 0
    while len(rem) > 3 and safe < n * n * 3:
        safe += 1
        found = False
        for idx in range(len(rem)):
            ip = rem[(idx - 1) % len(rem)]
            ic = rem[idx]
            ine = rem[(idx + 1) % len(rem)]
            c = cross2(pts[ip], pts[ic], pts[ine])
            if (ccw and c <= 1e-10) or (not ccw and c >= -1e-10):
                continue
            ok = all(
                k in (ip, ic, ine) or not point_in_tri(pts[k], pts[ip], pts[ic], pts[ine])
                for k in rem
            )
            if ok:
                if flip:
                    tris.append([indices[ine], indices[ic], indices[ip]])
                else:
                    tris.append([indices[ip], indices[ic], indices[ine]])
                rem.pop(idx)
                found = True
                break
        if not found:
            ip, ic, ine = rem[0], rem[1], rem[2]
            if flip:
                tris.append([indices[ine], indices[ic], indices[ip]])
            else:
                tris.append([indices[ip], indices[ic], indices[ine]])
            rem.pop(1)

    if len(rem) == 3:
        i0, i1, i2 = rem
        if flip:
            tris.append([indices[i2], indices[i1], indices[i0]])
        else:
            tris.append([indices[i0], indices[i1], indices[i2]])
    return tris


def build_mesh(hull):
    """Build complete triangle mesh for the dinghy hull."""
    x_vals = np.linspace(0, LOA, N_STATIONS)

    # Determine ring size
    test_ring = hull.build_ring(0)
    n_ring = len(test_ring)
    n_half = 1 + N_BOTTOM + N_SIDE  # points in one half-section
    n_outer = 2 * n_half - 1  # full outer profile point count

    # --- Hull wall vertices ---
    verts = []
    for x in x_vals:
        ring = hull.build_ring(x)
        assert len(ring) == n_ring, f"Ring at x={x:.1f} has {len(ring)} pts, expected {n_ring}"
        for y, z in ring:
            verts.append((x, y, z))

    # --- Hull wall faces ---
    faces = []
    for i in range(N_STATIONS - 1):
        for j in range(n_ring):
            jn = (j + 1) % n_ring
            v0 = i * n_ring + j
            v1 = i * n_ring + jn
            v2 = (i + 1) * n_ring + jn
            v3 = (i + 1) * n_ring + j
            faces.append([v0, v2, v1])
            faces.append([v0, v3, v2])

    # --- Thick transom slab ---
    # The transom is the outer hull profile at x=0, extruded inward
    # to TRANSOM_THICKNESS. Built as horizontal quad strips like the bulkhead.
    TRANSOM_THICKNESS = 0.75  # inches (~19mm)
    x_transom_outer = 0.0
    x_transom_inner = TRANSOM_THICKNESS

    # Build transom as horizontal strips spanning the outer hull profile
    _, cz_t, _, sz_t, _, kz_t = hull.interp(0)
    n_transom_strips = 120
    zt_vals = np.linspace(kz_t + 0.1, sz_t, n_transom_strips + 1)

    for i in range(n_transom_strips):
        zt_bot = zt_vals[i]
        zt_top = zt_vals[i + 1]
        zt_mid = (zt_bot + zt_top) / 2

        # Hull half-width at this height (use half_outer profile)
        bhw_t, cz_t2, shw_t, sz_t2, dr_t, kz_t2 = hull.interp(0)
        if zt_mid <= kz_t2:
            hw_t = 0
        elif zt_mid <= cz_t2:
            fr = (zt_mid - kz_t2) / (cz_t2 - kz_t2) if (cz_t2 - kz_t2) > 0 else 1
            hw_t = fr * bhw_t
        else:
            fr = min(1, (zt_mid - cz_t2) / (sz_t2 - cz_t2)) if (sz_t2 - cz_t2) > 0 else 1
            hw_t = bhw_t + fr * (shw_t - bhw_t)
            # Add spray rail bulge
            bulge = SPRAY_RAIL_OUTWARD * np.exp(
                -0.5 * ((fr - SPRAY_RAIL_HEIGHT_FRAC) / 0.2) ** 2)
            hw_t += bulge

        if hw_t <= 0.1:
            continue

        qs = len(verts)
        # 8 vertices: outer face (x=0) and inner face (x=thickness)
        verts.append((x_transom_outer, -hw_t, zt_bot))  # 0
        verts.append((x_transom_outer, hw_t, zt_bot))    # 1
        verts.append((x_transom_outer, hw_t, zt_top))    # 2
        verts.append((x_transom_outer, -hw_t, zt_top))   # 3
        verts.append((x_transom_inner, -hw_t, zt_bot))   # 4
        verts.append((x_transom_inner, hw_t, zt_bot))    # 5
        verts.append((x_transom_inner, hw_t, zt_top))    # 6
        verts.append((x_transom_inner, -hw_t, zt_top))   # 7

        # Outer face (-x normal, facing aft)
        faces.append([qs+0, qs+1, qs+2])
        faces.append([qs+0, qs+2, qs+3])
        # Inner face (+x normal, facing cockpit)
        faces.append([qs+4, qs+6, qs+5])
        faces.append([qs+4, qs+7, qs+6])
        # Top
        faces.append([qs+3, qs+2, qs+6])
        faces.append([qs+3, qs+6, qs+7])
        # Bottom
        faces.append([qs+0, qs+5, qs+1])
        faces.append([qs+0, qs+4, qs+5])
        # Port side
        faces.append([qs+0, qs+3, qs+7])
        faces.append([qs+0, qs+7, qs+4])
        # Starboard side
        faces.append([qs+1, qs+5, qs+6])
        faces.append([qs+1, qs+6, qs+2])

    # --- Nose platform (self-contained closed slab) ---
    # The platform is a separate solid slab positioned to overlap slightly
    # into the hull inner wall. This guarantees no gaps in the slicer without
    # requiring shared vertices or coplanar face management. The slicer
    # handles the boolean intersection of overlapping solids cleanly.
    PLATFORM_THICKNESS = 0.4  # inches (~10mm)
    OVERLAP = 0.25  # inches (~6mm) overlap past hull inner wall surface

    # Use the hull ring stations in the nose zone for consistent x-spacing
    nose_ring_indices = [i for i, x in enumerate(x_vals) if x >= BULKHEAD_X]
    n_nose = len(nose_ring_indices)

    # For each station, compute the platform edge position:
    # Top edge: at sz, y = inner_hw (from hull geometry) + OVERLAP outboard
    # Bottom edge: at sz - thickness, y = hull wall y at that z + OVERLAP outboard
    # The OVERLAP pushes the slab edge slightly into the hull wall.

    nose_top_port = len(verts)
    for ri in nose_ring_indices:
        x = x_vals[ri]
        _, _, _, sz, _, _ = hull.interp(x)
        ihw = hull.inner_hw(x)
        verts.append((x, -(ihw + OVERLAP), sz))

    nose_top_stbd = len(verts)
    for ri in nose_ring_indices:
        x = x_vals[ri]
        _, _, _, sz, _, _ = hull.interp(x)
        ihw = hull.inner_hw(x)
        verts.append((x, ihw + OVERLAP, sz))

    nose_bot_port = len(verts)
    for ri in nose_ring_indices:
        x = x_vals[ri]
        inner_pts = hull.half_inner(x)
        inner_ys = [p[0] for p in inner_pts]
        inner_zs = [p[1] for p in inner_pts]
        _, _, _, sz, _, _ = hull.interp(x)
        bot_z = sz - PLATFORM_THICKNESS
        wall_y = float(np.interp(bot_z, inner_zs, inner_ys))
        verts.append((x, -(wall_y + OVERLAP), bot_z))

    nose_bot_stbd = len(verts)
    for ri in nose_ring_indices:
        x = x_vals[ri]
        inner_pts = hull.half_inner(x)
        inner_ys = [p[0] for p in inner_pts]
        inner_zs = [p[1] for p in inner_pts]
        _, _, _, sz, _, _ = hull.interp(x)
        bot_z = sz - PLATFORM_THICKNESS
        wall_y = float(np.interp(bot_z, inner_zs, inner_ys))
        verts.append((x, wall_y + OVERLAP, bot_z))

    for i in range(n_nose - 1):
        # Top surface (normals up)
        pt0 = nose_top_port + i; pt1 = nose_top_port + i + 1
        st0 = nose_top_stbd + i; st1 = nose_top_stbd + i + 1
        faces.append([pt0, st0, st1])
        faces.append([pt0, st1, pt1])

        # Bottom surface (normals down)
        pb0 = nose_bot_port + i; pb1 = nose_bot_port + i + 1
        sb0 = nose_bot_stbd + i; sb1 = nose_bot_stbd + i + 1
        faces.append([pb0, sb1, sb0])
        faces.append([pb0, pb1, sb1])

        # Port edge (connects top port to bottom port)
        faces.append([pt0, pt1, pb1])
        faces.append([pt0, pb1, pb0])

        # Starboard edge (connects top stbd to bottom stbd)
        faces.append([st0, sb1, st1])
        faces.append([st0, sb0, sb1])

    # Front edge of platform (at first nose station, facing aft / -x)
    faces.append([nose_top_port, nose_bot_port, nose_bot_stbd])
    faces.append([nose_top_port, nose_bot_stbd, nose_top_stbd])

    # Back edge of platform (at bow tip) - close the slab
    last = n_nose - 1
    pt_last = nose_top_port + last
    st_last = nose_top_stbd + last
    pb_last = nose_bot_port + last
    sb_last = nose_bot_stbd + last
    faces.append([pt_last, st_last, sb_last])
    faces.append([pt_last, sb_last, pb_last])

    # --- Bow fill wedge ---
    # At the bow tip, the hull inner walls form a V below the nose platform.
    # This creates a visible void when viewed from the front. Fill it with
    # a solid wedge from the platform bottom down to the inner keel.
    # Only needed where inner walls are close (ihw < ~2"), roughly x > 95".

    BOW_FILL_MIN_X = 106.0  # inches from transom (~2" from stem)
    bow_fill_indices = [ri for ri in nose_ring_indices if x_vals[ri] >= BOW_FILL_MIN_X]

    bow_fill_start_idx = len(verts)
    bow_fill_stations = []

    for ri in bow_fill_indices:
        x = x_vals[ri]
        inner_pts = hull.half_inner(x)
        inner_ys = [p[0] for p in inner_pts]
        inner_zs = [p[1] for p in inner_pts]
        _, _, _, sz_v, _, _ = hull.interp(x)
        bot_z = sz_v - PLATFORM_THICKNESS
        wall_y = float(np.interp(bot_z, inner_zs, inner_ys))

        # Inner keel z: the bottommost point of the inner hull section
        keel_inner_z = inner_zs[0]
        keel_inner_y = inner_ys[0]  # should be ~0

        qs = len(verts)
        verts.append((x, -(wall_y + OVERLAP), bot_z))   # 0: top port
        verts.append((x, (wall_y + OVERLAP), bot_z))     # 1: top stbd
        verts.append((x, 0.0, keel_inner_z))             # 2: bottom center
        bow_fill_stations.append(qs)

    # Loft between adjacent stations
    for k in range(len(bow_fill_stations) - 1):
        s0 = bow_fill_stations[k]
        s1 = bow_fill_stations[k + 1]
        # Each station has 3 verts: port(+0), stbd(+1), keel(+2)
        p0, s0s, k0 = s0, s0+1, s0+2
        p1, s1s, k1 = s1, s1+1, s1+2

        # Top face (between port and stbd edges, platform bottom level)
        faces.append([p0, s0s, s1s])
        faces.append([p0, s1s, p1])

        # Port face (port edge down to keel)
        faces.append([p0, p1, k1])
        faces.append([p0, k1, k0])

        # Stbd face (stbd edge down to keel)
        faces.append([s0s, k0, k1])
        faces.append([s0s, k1, s1s])

    # Close the aft end (first station)
    s0 = bow_fill_stations[0]
    faces.append([s0, s0+2, s0+1])

    # Close the fwd end (last station)
    sn = bow_fill_stations[-1]
    faces.append([sn, sn+1, sn+2])

    # --- Bulkhead with U-cutout (thick quad strips) ---
    BULKHEAD_THICKNESS = 0.4  # inches (~10mm)
    bkh_quads = hull.build_bulkhead_quads()
    x_front = BULKHEAD_X - BULKHEAD_THICKNESS / 2
    x_back = BULKHEAD_X + BULKHEAD_THICKNESS / 2

    for y_left, y_right, z_bot, z_top in bkh_quads:
        qs = len(verts)
        # 8 vertices: 4 on front face, 4 on back face
        # Front face (cockpit side)
        verts.append((x_front, y_left, z_bot))    # 0
        verts.append((x_front, y_right, z_bot))   # 1
        verts.append((x_front, y_right, z_top))   # 2
        verts.append((x_front, y_left, z_top))    # 3
        # Back face (locker side)
        verts.append((x_back, y_left, z_bot))     # 4
        verts.append((x_back, y_right, z_bot))    # 5
        verts.append((x_back, y_right, z_top))    # 6
        verts.append((x_back, y_left, z_top))     # 7

        # Front face (-x normal)
        faces.append([qs+0, qs+2, qs+1])
        faces.append([qs+0, qs+3, qs+2])
        # Back face (+x normal)
        faces.append([qs+4, qs+5, qs+6])
        faces.append([qs+4, qs+6, qs+7])
        # Top face (+z normal)
        faces.append([qs+3, qs+7, qs+6])
        faces.append([qs+3, qs+6, qs+2])
        # Bottom face (-z normal)
        faces.append([qs+0, qs+1, qs+5])
        faces.append([qs+0, qs+5, qs+4])
        # Left face (-y normal)
        faces.append([qs+0, qs+4, qs+7])
        faces.append([qs+0, qs+7, qs+3])
        # Right face (+y normal)
        faces.append([qs+1, qs+2, qs+6])
        faces.append([qs+1, qs+6, qs+5])

    return np.array(verts), np.array(faces)


# ============================================================
# VISUALIZATION
# ============================================================

def render_preview(mesh, output_path):
    """Generate 6-view preview PNG."""
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(24, 16))
    views = [
        (1, "Starboard Quarter", 25, -50),
        (2, "Transom", 5, 180),
        (3, "Bow", 10, 0),
        (4, "Top Down", 85, -90),
        (5, "Interior", 35, -130),
        (6, "Bow Quarter", 20, -20),
    ]

    for idx, title, el, az in views:
        ax = fig.add_subplot(2, 3, idx, projection="3d")
        polys = [[mesh.vertices[f[k]] for k in range(3)] for f in mesh.faces[::3]]
        ax.add_collection3d(
            Poly3DCollection(
                polys, alpha=0.7, edgecolor="#AAA", linewidth=0.05, facecolor="#C0D0E0"
            )
        )
        ax.set_xlim(0, 110)
        ax.set_ylim(-40, 40)
        ax.set_zlim(-5, 30)
        ax.view_init(elev=el, azim=az)
        ax.set_box_aspect([3.5, 2, 1])
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False

    fig.suptitle(
        f"9ft ASA-Core Planing Dinghy — {GUNWALE_DEPTH:.0f}\" Gunwales — "
        f"{LOA - BULKHEAD_X:.0f}\" Bow Locker",
        fontsize=15,
        fontweight="bold",
    )
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close()


def render_bulkhead(hull, output_path):
    """Generate bulkhead cross-section preview."""
    import matplotlib.pyplot as plt

    quads = hull.build_bulkhead_quads()
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_aspect("equal")

    for y_left, y_right, z_bot, z_top in quads:
        rect_y = [y_left, y_right, y_right, y_left, y_left]
        rect_z = [z_bot, z_bot, z_top, z_top, z_bot]
        ax.fill(rect_y, rect_z, alpha=0.3, color="steelblue")
        ax.plot(rect_y, rect_z, "-", color="steelblue", linewidth=0.5)

    # Draw U-cutout outline
    _, _, _, sz, _, _ = hull.interp(BULKHEAD_X)
    u_angles = np.linspace(0, np.pi, 40)
    u_y = U_HALF_WIDTH * np.cos(u_angles)
    u_z = (sz - U_DEPTH + U_RADIUS) - U_RADIUS * np.sin(u_angles)
    ax.plot(u_y, u_z, "r-", linewidth=2, alpha=0.7, label="U-cutout")
    ax.plot([-U_HALF_WIDTH, -U_HALF_WIDTH], [sz, sz - U_DEPTH + U_RADIUS],
            "r-", linewidth=2, alpha=0.7)
    ax.plot([U_HALF_WIDTH, U_HALF_WIDTH], [sz, sz - U_DEPTH + U_RADIUS],
            "r-", linewidth=2, alpha=0.7)
    ax.plot([-U_HALF_WIDTH, U_HALF_WIDTH], [sz, sz], "r-", linewidth=2, alpha=0.7)

    ax.set_title(
        f"Bulkhead at x={BULKHEAD_X:.0f}\" — "
        f"{2*U_HALF_WIDTH:.0f}\"W x {U_DEPTH:.0f}\"D U-Cutout, {U_RADIUS:.0f}\"R\n"
        f"Built from {len(quads)} horizontal quad strips",
        fontsize=12, fontweight="bold",
    )
    ax.set_xlabel("Beam (in)")
    ax.set_ylabel("Height (in)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.2)
    plt.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close()


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Generate dinghy hull STL")
    parser.add_argument("--scale", type=float, default=10, help="Scale factor (default: 10 = 1:10)")
    parser.add_argument("--no-preview", action="store_true", help="Skip PNG preview generation")
    parser.add_argument("--output-dir", type=str, default=".", help="Output directory")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("Building hull geometry...")
    hull = DinghyHull()

    print("Generating mesh...")
    verts, faces = build_mesh(hull)

    try:
        import trimesh
        mesh = trimesh.Trimesh(vertices=verts, faces=faces)
        trimesh.repair.fix_normals(mesh)

        dims = mesh.bounds[1] - mesh.bounds[0]
        print(f"  Vertices: {len(mesh.vertices)}")
        print(f"  Faces: {len(mesh.faces)}")
        print(f"  Watertight: {mesh.is_watertight}")
        print(f"  Size: {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} in")
        print(f"        {dims[0]/12:.1f} x {dims[1]/12:.1f} x {dims[2]/12:.1f} ft")

        # Full-size STL (inches)
        full_path = out / "dinghy_full_size.stl"
        mesh.export(str(full_path))
        print(f"\nExported: {full_path}")

        # Scaled model STL (mm)
        scale = args.scale
        mesh_scaled = mesh.copy()
        mesh_scaled.apply_scale(25.4 / scale)
        scaled_path = out / f"dinghy_1to{scale:.0f}_mm.stl"
        mesh_scaled.export(str(scaled_path))
        d = mesh_scaled.bounds[1] - mesh_scaled.bounds[0]
        print(f"Exported: {scaled_path}")
        print(f"  Model size: {d[0]:.0f} x {d[1]:.0f} x {d[2]:.0f} mm")

    except ImportError:
        print("trimesh not installed, exporting raw STL...")
        # Fallback: write binary STL manually
        _write_stl(verts, faces, out / "dinghy_full_size.stl")

    if not args.no_preview:
        try:
            print("\nGenerating previews...")
            render_preview(mesh, out / "dinghy_preview.png")
            render_bulkhead(hull, out / "dinghy_bulkhead.png")
            print(f"Saved: {out / 'dinghy_preview.png'}")
            print(f"Saved: {out / 'dinghy_bulkhead.png'}")
        except Exception as e:
            print(f"Preview generation failed: {e}")

    print("\nDone!")
    print(f"\nDesign summary:")
    print(f"  LOA: {LOA/12:.0f} ft ({LOA}\")")
    print(f"  BOA at transom: {2*STATIONS[0][3]:.0f}\" ({2*STATIONS[0][3]/12:.1f} ft)")
    print(f"  Freeboard: {STATIONS[0][4]:.0f}\"")
    print(f"  Gunwale width: {GUNWALE_DEPTH:.0f}\"")
    print(f"  Bow locker: {LOA - BULKHEAD_X:.0f}\"")
    print(f"  U-cutout: {2*U_HALF_WIDTH:.0f}\"W x {U_DEPTH:.0f}\"D, {U_RADIUS:.0f}\"R")
    print(f"  Spray rail: {SPRAY_RAIL_OUTWARD:.1f}\" outboard at {SPRAY_RAIL_HEIGHT_FRAC*100:.0f}% height")


def _write_stl(verts, faces, path):
    """Fallback binary STL writer (no trimesh needed)."""
    import struct
    with open(path, "wb") as f:
        f.write(b"\0" * 80)  # header
        f.write(struct.pack("<I", len(faces)))
        for face in faces:
            v0, v1, v2 = verts[face[0]], verts[face[1]], verts[face[2]]
            e1 = v1 - v0
            e2 = v2 - v0
            n = np.cross(e1, e2)
            norm = np.linalg.norm(n)
            if norm > 0:
                n = n / norm
            f.write(struct.pack("<3f", *n))
            f.write(struct.pack("<3f", *v0))
            f.write(struct.pack("<3f", *v1))
            f.write(struct.pack("<3f", *v2))
            f.write(struct.pack("<H", 0))
    print(f"Exported: {path}")


if __name__ == "__main__":
    main()
