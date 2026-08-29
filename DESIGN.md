# Engineering design

## Source geometry and coordinates

The geometry is built in design inches. `x = 0` is the transom and x increases toward the stem at `x = 108`. `y` is transverse and `z` is vertical. The complete mesh is multiplied by `DESIGN_SCALE = 0.90` for the real-boat exports, so lengths become 90% of the design coordinates and volumes and displacement become 72.9% of their design-space values.

`dinghy_split.py` imports `dinghy_hull-2.py` by file path because the filename contains a hyphen. It then replaces that module's `STATIONS` before constructing `DinghyHull`; the base file is not edited. Each Rev-3 station is a tuple of:

```text
(x from transom, bottom half-beam, chine z,
 sheer half-beam, sheer z, deadrise degrees)
```

The ten overridden stations run from x = 0 to 108 in. The plan places the 42 in sheer width at x = 60 rather than x = 72, so the bow interface falls at the same station as the nominal 42 in center width. The transom remains 68 in wide in design space. The source cross-section sampling is increased to 30 bottom samples and 37 topside samples.

`DinghyHull.interp()` linearly interpolates bottom half-beam, chine elevation, sheer half-beam, sheer elevation, deadrise, and keel elevation along x. Keel elevation is derived at the input stations as:

```text
keel_z = chine_z - bottom_half_beam * tan(deadrise)
```

For each starboard half-section, the bottom is a straight line from keel to chine. The topside is a line from chine to sheer plus a Gaussian spray-rail bulge. The base rail has 1.5 in outward amplitude, is centred at 0.35 of the topside height, and uses a 0.2 profile width. Port geometry is mirrored from starboard.

The split program further shapes the bow. It pulls the plan width toward a convex sheer target (`BOW_CONVEX = 0.6` design in), fades the spray rail only through the final 10 design inches, and applies an outward flare above 0.45 of topside height. The flare grows with height to power 2.2 and longitudinally to power 1.5, is exactly zero at the split, and is capped at 0.25 of local sheer half-width near the stem. The current run reports a maximum real sheer kick of 1.05 in and up to 0.67 in of concavity relative to the rail-to-sheer chord. The final 2.5 design inches use 24 shrinking rings, with scale exponent 0.5 and minimum section scale 0.05, anchored at the sheer.

## Section construction and lofting

Every primary part is constructed directly as a closed solid. The Rev-2 monolith is not watertight, so the code does not cut the four-piece assembly from that older mesh.

Profiles are resampled by arc length to fixed vertex counts before lofting. `loft()` places an equal-length closed y-z polygon at every x station, connects corresponding vertices with pairs of triangles, and ear-clips both end caps. Fixed point correspondence matters: it produces continuous quad strips without having to remesh between changing section topologies. `loft_apex()` is available for a single-vertex end, though the current bow instead closes a small final ring because a fan to one apex can overlap on the concave flat-deck/V-bottom section.

### Center barge

The center uses 220 stations between x = 0 and x = 60 design inches. Each section combines the original lower hull inside the cut line with vertical mating walls and the open cockpit interior. The 14 mm real sole is generated separately from the 7 mm real sides. The cut line widens by `DSTERN = 2.0` design inches per half at the transom and tapers to `YC = 21.0` at the bow split, creating enough cockpit width for the bow to nest.

The aft end receives a separately built transom. Its base slab is 0.65 in real, while a smoothly blended local clamp pad reaches 1.5 in real total thickness. The motor cutout places its ledge 17.0 in above the bottom, is 12.0 in wide there, widens 2.0 in per side, and rounds its lower corners at 0.75 in.

### Wedge pods

Each wedge section is the region between the center mating plane and the original hull skin. Starboard is built first and port is its y-mirror. Sections continue until the hull reaches the cut line, forming triangular planforms from the transom to the split.

Each solid wedge is hollowed by subtracting a closed inset cavity. The cavity begins 1.5 design inches from the aft cap, stops before the wedge becomes too thin, and tapers through 45% and 12% copies of its final usable section rather than extending a cavity through the forward sliver. This leaves a sealed 7 mm shell. The mating-side cavity normally leaves the same skin thickness, but smoothly increases to a 1.6 design in solid boss around each key and bolt. The boss is full within 3.5 design inches of a key, fades for another 1.5 in in x, and fades over 2.0 in below the key rather than making keel-to-sheer blocks and abrupt internal steps.

### Bow

The outer bow is lofted from the split to the start of the rounded nose and then through the shrinking nose rings. It has a flat foredeck (`BOW_CAMBER = 0`). A cavity is subtracted for storage, reaching up to 44 real inches forward but stopping automatically when the nose is too thin. Its sole lies 0.15 of the distance from keel to deck. The aft opening is a closed arch profile with a semi-elliptical top.

The bow is a hollow, manifold shell with an aft access opening and is not a sealed pod. Near the joint, the cavity offset is increased so the bow-side flange ring is part of the cavity loft. Earlier code unioned a separate ring whose aft cap was coplanar with the shell face. Float32 STL conversion collapsed the resulting zero-area triangles, and the repair pass could bridge the thin shell and opening with unwanted membranes.

## True-offset walls

The current wall algorithm is `offset_poly()` followed by `repair_inset()`.

`offset_poly(poly, d)` determines polygon winding, computes the inward unit normal for each edge, and moves every vertex along the bisector of its two adjacent edge normals. The bisector distance is divided by the cosine of half the turn so both displaced edges are the requested normal distance `d` from their originals. A 3d miter limit prevents excessive spikes. Vertex count and ordering are retained, which allows the inner and outer contours to loft as corresponding strips.

The former approach scaled each vertex toward the section centroid, producing a variable wall offset. It gives thickness `d` only where the centroid ray meets the panel normally; at an oblique panel, the normal thickness becomes approximately `d cos(theta)`. Measurements cited in the code found about 1--4 mm where 7 mm was requested, falling to 0.02 mm at the wedge's forward end. At 1:10, those regions were below an extrusion width, so the slicer omitted wedge skins and the bow deck.

An exact offset can still fold when the source section pinches to less than twice the requested offset, especially at the wedge bottom/mating-plane corner and under the wide bow flange inset. `repair_inset()` handles these local failures:

1. It flags offset vertices outside the original polygon, closer than `tol * d` to it, or involved in a non-adjacent edge crossing. The default tolerance is 0.5.
2. It replaces each contiguous flagged run with evenly spaced points along the chord between the nearest sound vertices. The pinched region is thus left solid.
3. It accumulates a sticky bad-vertex mask and repeats for up to 14 passes. If a pass finds nothing new, the mask grows by one neighbour on each side. This monotonic behaviour avoids oscillation in which the endpoints of one repair become crossings on the next pass.
4. It rejects the inset if more than 75% of vertices would be bridged, the pass limit is reached, winding or area is invalid, a vertex remains outside, or a self-intersection remains. Rejection means the section is too thin to hollow and is left solid; it is not treated as a mesh error.

## Joint design

### Wedge-to-center joints

The implemented joint uses discrete vertical keys. The older continuous fore-aft sliding-dovetail constants remain in the file but are bypassed by `USE_VKEYS = True`. Each center side receives three sockets open through the rim, and each wedge receives the corresponding tongue. In horizontal section, the tongue is 2.0 design inches wide at the wall and flares to 3.0 in at its 0.7 in inboard back. A 0.5 in stub roots it in the wedge. The flare captures transverse pull-apart loads while allowing the pod to lower vertically.

Two transverse bolt holes are cut at each key, 2.5 and 7.5 design inches below the local sheer. One shared cylinder is subtracted from both pieces, guaranteeing coaxial holes. There are 12 wedge bolts across the two sides. Holes are about 0.44 design inches in diameter (`BOLT_R = 0.22`) and all are checked against the derived horizontal waterplane. On the wedge side they terminate blindly in the local solid boss, with 0.32 real inches of backing left behind the 1.12 in real blind depth.

### Bow-to-center joint

Three keys lock the bow against forward separation while preserving straight-down assembly. Their horizontal section is narrow at the x = 60 face and flares aft into the center. The center channels continue to the rim; bow tongues occupy only their working height.

The low centerline key starts at 0.99 in real and runs to the local arched bulkhead top, 7.83 in real in the current run. Its real mouth is 1.26 in wide, its back is 1.98 in wide, and the flare extends 0.72 in aft. It is surrounded by the solid bottom bulkhead. The port and starboard keys start at 8.46 in real and extend to 11.57 in; each has a 0.76 in real mouth and 1.35 in back over the same 0.72 in depth. They sit in the flange band.

Four longitudinal bolt holes cross the interface at real z = 13 and 19 in, one on each side at each height. These bolts only prevent lift; the keys carry the fore-aft lock.

The butt joint is reinforced in two ways:

- Each shell has a 2.0 in real-wide flange ring extending 1.5 in axially away from the mating face. The rings stay inside the outer contour and butt at the split, providing grip length around the upper interface.
- Each shell has a 1.0 in thick solid lower web, making a 2.0 in assembled bulkhead. It reaches to 12.0 in real at the sides and dips smoothly to 8.0 in at the centerline. At the 600 lb design load, the side sill is 5.0 in above the waterline and the center dip is 1.0 in above it. The lowest bow bolt is 1.0 in above the side sill.

### Fit clearance

Tongues are generated at nominal size. Socket cutters use the same profiles grown outward by `KEY_CLR`, including a correspondingly lower floor. The default is a 2.0 mm real gap on every mating face and is shared by wedge and bow keys.

The code sizes this for fiberglassed mating walls: two 0.5 mm print perimeters plus two approximately 0.5 mm laminates already consume about 2 mm before print accuracy, accumulated bond-line error, or differential ASA shrink is considered. The previous 0.6 mm allowance could be consumed by glass alone. Clearance reduces dovetail capture one for one, but at 2.0 mm the wedge keys retain 9.4 mm of capture. The smaller bow-side keys use a 0.75 design in back specifically to retain about 5.5 mm of capture after clearance. Bolts clamp the interfaces, so the keys need capture rather than a press fit.

`--key-clearance-mm` is expressed as a real manufacturing allowance and is intentionally not divided by `--scale`, so the default 2.0 mm becomes 0.20 mm on a 1:10 model.

This gap is the model-scale value. Preserving a 2 mm gap on the model would exceed the available undercut. The allowance covers a tolerance stack absent from the model: laminate in the joint, bond lines across a chunked print, and differential shrink over the 732 mm between the first and last wedge key. The dovetail undercut shrinks with the rest of the model. `min_key_undercut()` returns the smallest undercut on the boat, 7.5 mm real and 0.75 mm at 1:10 on the bow side keys. Clearance grows the socket on every face, consuming undercut one for one. With a 2 mm model gap, the capture margin is -1.25 mm and every key lifts straight out. `main()` prints the margin at both scales on every run and warns when the gap exceeds the undercut or falls below a printable fit.

## Hydrostatics

Hydrostatics use the exterior envelope rather than material volume. Aft of the split the envelope is `DinghyHull.half_outer()`; forward it is the fully modified bow profile, including plan convexity and flare.

At a trial horizontal waterplane, the code samples 240 longitudinal stations. At each station it interpolates half-width over 60 z samples from the local keel to the waterplane, integrates for half-section area, doubles for port and starboard, then integrates section area over x. The design volume is multiplied by `DESIGN_SCALE**3` and by 0.0361 lb/in3 for fresh water. `waterplane_for_load()` uses 60 bisection iterations over the full hull-height bracket.

The derived waterplane is a single horizontal z value. An older “waterline above local keel” rule incorrectly followed approximately 13 in of keel rocker. The current calculation replaces that rule. `set_waterline_from_load()` runs before geometry construction because key, bolt, and sill rules depend on it.

For `DESIGN_LOAD_LB = 600`, the current generator reports waterplane z = 7.00 in real, 13.7 in freeboard at the split sheer, and `WATERLINE = 6.99` in above the split keel datum. The calculation assumes upright static flotation and level trim. It reports 2,263 lb displacement at the 20.7 in split sheer, a 1,208 lb load at the 12 in side sill, and a 717 lb load at the 8 in center sill.

## Weight model

The weight estimate operates on the scaled real meshes. ASA material is divided into:

```text
solid perimeter volume = min(mesh volume, mesh area * 0.5 mm)
infill volume          = max(0, mesh volume - perimeter volume) * 0.12
```

Both use an ASA density of 1.07 g/cm3. The calculation models slicer behaviour; it does not treat every generated 7 or 14 mm wall as solid.

Face normals, triangle centroids, and height divide surface area into exterior bottom, exterior topside, deck, and optional interior zones. Bottom is charged at 0.8 kg/m2 laminated mass; topside, deck, and included interior at 0.4 kg/m2. Only the center receives the interior-glass charge. The zone classifier is deliberately described in code as rough.

The present result is:

| Piece | Perimeter ASA | Infill ASA | Glass | Total |
| --- | ---: | ---: | ---: | ---: |
| Center | 3.7 kg | 6.7 kg | 3.4 kg | 13.8 kg |
| Starboard wedge | 1.6 kg | 2.3 kg | 0.8 kg | 4.8 kg |
| Port wedge | 1.6 kg | 2.3 kg | 0.8 kg | 4.8 kg |
| Bow | 2.2 kg | 2.6 kg | 1.0 kg | 5.8 kg |
| Total |  |  |  | 29.1 kg / 64 lb |

At that estimated bare-hull weight, the static level waterplane is 1.51 in real.

## Mesh verification

The main program performs checks after all hollowing, unions, keys, and bolt cuts:

- **Piece topology:** `report()` checks `trimesh.is_watertight` for each finished piece. The bow passes because a cup-like shell can be a closed manifold even though its storage mouth is open to its cavity. The check does not classify the bow as a sealed pod.
- **Manifold cleanup:** `make_manifold()` constructs and normal-fixes a float32-precision copy, checks watertightness and edge incidence, and can invoke `pymeshfix` when that copy is not clean. A repaired result is accepted only within the function's volume-change guards; repairs which appear to bridge a slot are refused. The wedge boolean chain is the usual reason for this final pass.
- **Export-scale manifold check:** each part is scaled by `DESIGN_SCALE`, passed through `make_manifold()` again to simulate the float32 STL round trip, and required to be watertight with zero edges whose incidence count differs from two. This catches vertex pairs which were distinct in design coordinates but collapse at export scale.
- **Bow drop-in sweep:** the finished bow is lifted vertically through seven positions from seated to 26 design inches. At each step it is boolean-intersected with the finished center. Less than 0.05 real in3 maximum overlap is reported as clear. The current result is 0.0000 in3 at every sampled position.
- **Buoyancy-pod seal:** every starboard wedge bolt cylinder is intersected with the independently generated wedge cavity. The worst real overlap must be zero. This check is necessary because a blind hole opened into an internal void can leave the outer mesh watertight and manifold while still flooding the pod. The current result is 0.0000 in3; less than `1e-4` is labelled `SEALED`.
- **Bolt waterline report:** every bolt center is printed with its distance above the derived waterplane. The current geometry reports all 16 holes above it.
- **Offset validation:** every inset must preserve vertex count and winding, have smaller area, remain inside its source polygon, and contain no self-intersection. Locally unrepairable thin sections remain solid.

`slice_for_print.py` adds a second level of per-chunk cleanup after bed-grid intersection and dowel booleans. It first welds and removes duplicate or degenerate faces, then retries at float32 precision, and finally permits a `pymeshfix` repair only if the result is watertight, has no non-manifold edges, and changes volume by no more than 15%. If none qualifies, it retains the best-effort original chunk for inspection rather than silently substituting a materially different repair.
