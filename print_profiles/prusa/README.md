# PrusaSlicer presets (Prusa Core One)

The same profile as the Bambu one next door, in PrusaSlicer form: one perimeter,
gyroid core, 8% or 12%, hot ASA with a raised volumetric cap.

## Which chunks to feed it

**For the boat currently being printed: `split_out/print_sections_x1c/bow_prusa/`.**

That boat was started on the X1C, so its chunks are cut on the X1C's 240 mm grid
and carry the X1C dowel pattern. `bow_prusa/` is the subset of those that fits
the Core One's smaller plate, already placed for it. They bond to what is already
on the shelf exactly as designed. Its `PLACEMENT.txt` has the settings and the
four chunks that need watching.

Do **not** run `--printer coreone` for that boat. It re-cuts the hull on the Core
One's own 234 x 204 grid, so every chunk is a different solid with dowels in
different places and none of it mates with anything already printed:

```sh
.venv/bin/python slice_for_print.py --printer coreone   # only for a boat printed
                                                        # entirely on a Core One
```

The Core One's usable plate is 234 x 204 mm inside the 8 mm brim against the
X1C's 234 x 234, so only the short axis differs. That is why most X1C chunks fit
it unchanged and a whole separate cut is rarely worth the incompatibility.

## Install

Copy the three files into the PrusaSlicer user preset directories, then restart
it. The preset name is the file name, so do not rename them.

```
~/Library/Application Support/PrusaSlicer/print/     boatASA-12.ini, boatASA-8.ini
~/Library/Application Support/PrusaSlicer/filament/  boatASA.ini
```

Windows uses `%APPDATA%\PrusaSlicer\`, Linux `~/.config/PrusaSlicer/`.

Each preset starts with `inherits = `, naming the stock preset it modifies. If
PrusaSlicer refuses the preset, the installed system profile is named something
else: open the nearest stock one in the GUI, check its name in the Print
Settings dropdown, and edit that line to match. `0.25mm DRAFT @COREONE` is the
0.4 nozzle draft profile; with a 0.6 nozzle fitted, inherit its 0.32 mm draft
equivalent instead.

## Which preset for which folder

| folder | preset |
| --- | --- |
| `bow_prusa/`, `bow/` | `boatASA-8` |
| `wedge_stbd/`, `wedge_port/` | `boatASA-8` |
| `center/` low chunks, up to the waterline | `boatASA-12` |
| `center/` chunks above it | `boatASA-8` |

Each folder carries its own note naming that split by chunk number, so you do
not have to come back here at the machine: `PROFILE.txt` in the piece folders,
`PLACEMENT.txt` in `bow_prusa/`. Filament preset is `boatASA` throughout.

## What is in them

Print, inheriting `0.25mm DRAFT @COREONE`:

```
perimeters                  1        one perimeter; the print is a glass substrate
perimeter_extrusion_width   0.5      the whole wall, so it is set explicitly
fill_pattern                gyroid   isotropic, and far better in shear as a core
fill_density                12% / 8% the only difference between the two presets
infill_overlap              25%
top_solid_layers            3
top_solid_min_thickness     0        let the layer count govern, not a thickness floor
bottom_solid_layers         3
brim_type                   outer_only
brim_width                  8 mm
```

Filament, inheriting `Generic ASA`:

```
temperature                     275 C  (also on the first layer)
filament_max_volumetric_speed   16 mm3/s
```

## Three things to know

**Neither the cap nor the temperature has been print-tested**, on this machine
or on the Bambu. Run the max volumetric speed calibration at 275 C, set the cap
to the tested figure less about 10%, and change one thing at a time. Under-
extrusion does not fail loudly here: it thins every wall slightly across all
chunks, and on a one-perimeter print the wall is the entire part.

**The 0.6 HF nozzle is the real speed lever.** The Nextruder swaps nozzles in a
couple of minutes, which the X1C profile could not assume, and it is worth more
than any cap tuning: roughly double the flow, so roughly half of a 400-hour job.
It costs weight. The wall goes from 0.5 mm to about 0.68, and the mass model
puts that at +3.0 kg of ASA, 19.5 to 22.5 kg, or about 6.6 lb on the finished
boat. A glassed core does not need the 0.4 surface finish, so the trade is time
against weight and nothing else.

**Leave "ensure vertical shell thickness" alone unless you check its effect.** A
hull has almost no vertical wall, so on sloped surfaces that setting decides how
much solid infill backs up the single perimeter. It is on by default in both
slicers, so the Bambu profile carries it too and the weight model is calibrated
with it on. Turning it off saves mass and risks pinholes in the substrate; if
you try it, slice one center chunk both ways and compare the material figure
before committing.
