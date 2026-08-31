# Parametric split dinghy

This repository generates mesh geometry for a 9 ft parametric planing dinghy. Export applies `DESIGN_SCALE = 0.90` uniformly, producing a real boat 97 in (8.1 ft) long and 61 in wide at the transom. The intended build prints the geometry in ASA as a light core and mould surface, then covers it with fiberglass and epoxy. The generated boat separates into four pieces sized for car transport.

The source geometry uses inches. Full-size STL files are exported in inches; the model STLs are converted to millimetres at the requested 1:N scale.

## Split architecture

The four generated pieces are:

- `center`: a 54.0 x 41.4 x 21.9 in open center barge running from the transom to the split. It is a usable floating tub by itself. Its mating cut forms a slight trapezoid, 46 in wide in design coordinates at the transom and 42 in wide at the bow split. After export scaling, its maximum width is 41.4 in.
- `wedge_stbd` and `wedge_port`: sealed buoyancy pods carrying the original outboard bottom, spray-railed topside, and gunwale surfaces. Each is about 53.8 x 11.7 x 19.0 in after scaling and tapers to the 42 in design beam at the split.
- `bow`: a 43.9 x 37.8 x 22.8 in nose section. It is hollowed as a storage shell with a domed aft access opening. The mesh is a clean manifold like a cup, but the storage opening means the bow is not a sealed buoyancy chamber in the current configuration.

For transport, the bow drops into the center cockpit. The current geometry reports 0.71 in of minimum width clearance, with the bow below the rim. The two wedges flip together into a reported 54 x 12 x 38 in bundle. Laid flat side by side, they occupy 54 x 23 x 19 in.

## Joints

All four pieces assemble vertically. The center has open-top dovetail sockets and the removable pieces carry matching tongues:

- Each wedge has three vertical drop-in keys at design x = 8, 24, and 40 in. Their sideways flare prevents the pod pulling away from the center. Two bolts at each key prevent lift, for 12 wedge-to-center bolts total.
- The bow has three drop-in keys in its aft face: one low centerline key in the solid bottom bulkhead and one side key on each side. The keys prevent forward separation. Four bow-to-center bolts, two heights on each side, prevent lift.

Sockets are grown by a 2.0 mm real gap on every mating face. The gap accommodates fiberglass in the joint, print and assembly error, and differential ASA shrink. Bolts clamp the joint. The keys capture its geometry.

At the bow split, both pieces carry a 2.0 in wide by 1.5 in thick interface-flange ring, with the two rings butting face to face. A solid bottom bulkhead extends from the keel to a 12.0 in sill on each side of the joint; each half is 1.0 in thick, making the assembled web 2.0 in thick. The sill dips 4.0 in at the centerline, to 8.0 in, for a taller storage opening while remaining 1.0 in above the derived design waterline.

The wedge bolt holes are blind because the sealed pods have no accessible nut side. The design retains 0.32 in of solid material behind their 1.12 in real depth and expects a heat-set or epoxied threaded insert.

## Install

Python dependencies are not pinned in this repository. Create a local environment and install the packages imported by the four programs:

```sh
uv venv
uv pip install numpy trimesh matplotlib manifold3d pymeshfix rtree
```

`manifold3d` supplies the boolean operations used to union, subtract, and intersect meshes. `pymeshfix` is the repair fallback, and `rtree` supports spatial queries used when placing print-section dowels.

## Generate the boat

```sh
.venv/bin/python dinghy_split.py
```

`dinghy_split.py` accepts:

- `--scale N`: export an additional 1:N model in millimetres. The default is `10`. This does not change the full-size real-boat STLs.
- `--key-clearance-mm MM`: set the per-face dovetail fit gap in real millimetres. The default is `2.0`. This manufacturing allowance is deliberately not divided by `--scale` and must not be multiplied by `N` for a 1:N model. The undercut that makes a dovetail hold scales down. A gap larger than the undercut leaves the socket wider at its mouth than the tongue is at its back, allowing the key to lift straight out. The default becomes 0.20 mm on a 1:10 model, a normal FDM slip fit. Every run prints the capture margin left at both scales and warns when the gap is out of range.
- `--no-preview`: skip PNG rendering while still building and checking the meshes.
- `--output-dir PATH`: write generator outputs somewhere other than `split_out/`.

Examples:

```sh
.venv/bin/python dinghy_split.py --no-preview
.venv/bin/python dinghy_split.py --scale 5
.venv/bin/python dinghy_split.py --scale 10 --key-clearance-mm 3   # a little looser on the model
```

The program prints the actual piece dimensions, calculated weight, hydrostatics, bolt positions, transport clearances, and verification results on every run.

## Outputs

With the defaults, `split_out/` receives:

- Full-size inch STLs: `center.stl`, `wedge_stbd.stl`, `wedge_port.stl`, and `bow.stl`.
- 1:10 millimetre STLs: the same names with `_1to10_mm` appended.
- `dinghy_assembled.stl` and `dinghy_assembled_1to10_mm.stl`: concatenated four-piece assemblies for viewing. They retain the individual shells rather than boolean-unioning them into one solid.
- `print_ready/`: the same 1:N model STLs rotated onto whichever face gives the largest first-layer contact and dropped to z = 0. A hull has no flat face. The foredeck carries no camber but does carry the sheer spring, rising 2.5 design inches from the split to the stem, so a bow laid deck-down at 1:10 touches the plate over about 2 mm2 and stands 5 mm off it at the far end. Standing it on the x = 60 mating face is worse, because the three key tongues reach 1.8 mm proud of that plane. Slice these as-is and add a brim; the residual is a few tenths of a millimetre of sheer curvature. The full-size boat does not need this, since `slice_for_print.py` cuts it into bed-sized chunks whose cut faces are flat.
- Preview images, unless `--no-preview` is used: `split_preview.png`, `dovetail_detail.png`, `transport_packing.png`, `bolts.png`, `bow_flare_compare.png`, `bow_flare_3d.png`, `iface_flange.png`, and `bow_keys.png`.

Two optional post-processors use the default `split_out/` path:

```sh
.venv/bin/python render_explainers.py
.venv/bin/python slice_for_print.py
```

`render_explainers.py` writes `dovetail_clean.png` and `packing_clean.png`.

`slice_for_print.py` reads the four full-size inch STLs and divides them into bed-sized chunks, using an 8 mm margin on every side. It writes numbered chunk STLs in millimetres, `000_dowel.stl`, a `PROFILE.txt` per piece, and `manifest.csv`.

`--printer` selects the target. The bed size sets the cutting grid, so each printer gets its own output directory and the two chunk sets are **not interchangeable** — a chunk from one has its dowels in places the other's neighbours do not:

| target | bed | output |
| --- | --- | --- |
| `x1c` (default) | 256 x 256 x 256 mm | `split_out/print_sections_x1c/` |
| `coreone` | 250 x 220 x 270 mm | `split_out/print_sections_coreone/` |

Pick one target per boat and stay on it. A second machine does not need a second cut: the Core One's usable plate is 234 x 204 mm against the X1C's 234 x 234, so only the short axis differs and most X1C chunks fit it as they are. `split_out/print_sections_x1c/bow_prusa/` is that subset for the bow of the boat currently being printed, already placed for the smaller plate, with a `PLACEMENT.txt` recording which chunks were rotated and which eight do not fit at all. Feed a second printer from there rather than re-cutting.

```sh
.venv/bin/python slice_for_print.py                      # Bambu X1C
.venv/bin/python slice_for_print.py --printer coreone    # Prusa Core One
.venv/bin/python slice_for_print.py --printer coreone my_sections
```

A positional argument overrides only the subdirectory name. Slicer presets for both machines are in `print_profiles/`, and each piece's `PROFILE.txt` names the preset, infill split, and print order for that folder. The remaining slicing parameters are constants at the top of `slice_for_print.py`, not CLI options. The current cutter uses 4.0 mm ASA dowels, adds 0.2 mm to the hole diameter, drills 6.0 mm into each side of a cut, and requests up to three dowels per shared face. It clears stale STL and manifest files from the selected sections directory before writing a new set.

## Print and fiberglass specification

The generated real-boat wall targets are 7 mm for sides, topsides, decks, and shells, and 14 mm for the center cockpit sole. The transom is a 0.65 in base closure with a local motor-clamp pad reaching 1.5 in total thickness. The default transom notch is 12.0 in wide at its lower ledge, flares 2.0 in per side, has 0.75 in lower-corner radii, and places the ledge 17.0 in above the transom bottom for a short-shaft motor.

The weight model assumes:

- ASA density: 1.07 g/cm3.
- One 0.5 mm solid perimeter per face.
- 12% gyroid infill beyond the solid perimeter. Gyroid is specified because the printed material acts as a sandwich core and needs comparatively isotropic shear behaviour.
- Exterior bottom: two layers of 6 oz plain weave, the second at 45 degrees; modelled laminated areal mass 0.8 kg/m2.
- Exterior topsides and decks: one layer of 6 oz plain weave; 0.4 kg/m2.
- Center cockpit interior: one layer of 6 oz plain weave; 0.4 kg/m2. The sealed wedge interiors and bow-storage interior are not included in the interior-glass schedule.
- Approximately 50% fibre fraction after wet-out, giving 0.40 kg/m2 laminated mass for one 203 g/m2 dry layer.

The current calculation reports a 29.1 kg (64 lb) total, comprising a 13.8 kg center, two 4.8 kg wedges, and a 5.8 kg bow. The estimate comes from mesh volume, surface classification, perimeter, infill, and glass schedule. Slicer settings and the finished laminate control the real mass.

For a beaching boat, the source recommends a local third 6 oz strip, or graphite/epoxy, along the keel and chines instead of increasing the entire bottom laminate. That local reinforcement is estimated in the comment as about 0.2 kg and is not included in the model. The specified schedule assumes epoxy. The comments explicitly reject the chopped-strand mat in 1708 for epoxy; if changing to polyester or vinylester, restore mat appropriate to that resin system.

## Key parameters

These defaults are defined in the constants block at the top of [`dinghy_split.py`](dinghy_split.py). Values labelled “real” are finished dimensions after `DESIGN_SCALE`; others are design-space values unless the code converts them.

| Parameter | Default | Purpose |
| --- | ---: | --- |
| `LOA` | 108 in design / 97.2 in real | Hull length |
| `DESIGN_SCALE` | 0.90 | Uniform scale applied at real-boat export |
| `YC` | 21.0 in | Nominal center half-width at the bow split |
| `DSTERN` | 2.0 in | Extra design half-width at the center transom |
| `BOW_SPLIT` | 60.0 in design / 54.0 in real | Center-to-bow interface station |
| `SKIN` | 7 mm real | Shell and side wall target |
| `FLOOR` | 14 mm real | Center cockpit sole target |
| `DESIGN_LOAD_LB` | 600 lb | All-up load used to derive the waterline |
| `N_KEYS`, `KEY_X` | 3; 8, 24, 40 in design | Wedge keys per side and their stations |
| `KEY_CLR_MM` | 2.0 mm per face | Real fit gap for wedge and bow key sockets |
| `FLANGE_W`, `FLANGE_T` | 2.0 x 1.5 in real | Bow-joint ring width and per-piece thickness |
| `BHD_TOP`, `BHD_T`, `BHD_DIP` | 12.0, 1.0, 4.0 in real | Bottom web height, thickness per side, and center dip |
| `PERIM_SHELL`, `INFILL` | 0.5 mm; 12% | ASA mass-model and print assumptions |

Engineering details and verification logic are described in [DESIGN.md](DESIGN.md).

## Author

Alex Wynn, [MIT Center for Bits and Atoms](https://cba.mit.edu/people/awynn) and [Adiabatic Machines](https://adiabaticmachines.com/team/). The boat is a personal project and is not the work of either organisation.
