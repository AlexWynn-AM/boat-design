# Bambu Studio presets

The tuned presets for printing this boat, saved so the settings live with the
geometry instead of only on one laptop.

## Install

Copy into the Bambu Studio user preset directory, then restart it:

```
~/Library/Application Support/BambuStudio/user/<your-id>/process/     macOS
%APPDATA%\BambuStudio\user\<your-id>\process\                         Windows
```

`boatASA_filament.json` goes in `filament/` alongside. Drop the
`boatASA_process_` prefix when you copy: Bambu matches on the `name` field, so
the files should end up as `boatASA-12.json`, `boatASA-8.json` and
`boatASA.json`.

## Which preset for which folder

| folder | preset |
| --- | --- |
| `bow/` | `boatASA-8` |
| `wedge_stbd/`, `wedge_port/` | `boatASA-8` |
| `center/` chunks #045..#092 | `boatASA-12` |
| `center/` chunks #093..#109 | `boatASA-8` |

Filament preset is `boatASA` throughout.

Each piece folder carries a `PROFILE.txt` repeating this alongside the rest of
its settings, so you do not have to come back here at the machine.

## What is in them

Process, inheriting `0.24mm Draft @BBL X1C`:

```
wall_loops             1          one perimeter; the print is a glass substrate
sparse_infill_pattern  gyroid     isotropic, and far better in shear as a core
sparse_infill_density  12% or 8%  the only difference between the two presets
infill_wall_overlap    25%
top_shell_layers       3
top_shell_thickness    0          let the layer count govern, not a thickness floor
bottom_shell_layers    3
brim_type              outer_only
brim_width             8 mm
```

Filament, inheriting `Generic ASA`:

```
nozzle_temperature              270 C  (also on the initial layer)
filament_max_volumetric_speed   16 mm3/s
```

## Two things to know

**Brim and bottom shells were not in the original preset.** They were being set
per plate, which is exactly how a chunk ends up printed without a brim. They are
in the preset now. Everything else is byte-identical to the tuned original.

**These are 0.4 nozzle presets**, and with no 0.6 to swap to, the volumetric cap
is the only speed lever on the job. It is already boosted: stock Generic ASA is
12 mm3/s at 260 C, this profile is 16 at 270.

There is room left. The ASA base allows 28.6 and the filament's temperature
range tops out at 280, so 20 mm3/s at 275-280 C is reachable:

```
12 mm3/s   446 h    stock
16 mm3/s   334 h    this profile
20 mm3/s   267 h    the remaining headroom
```

Validate before committing to it. Run Bambu's max volumetric speed test and look
for under-extrusion on the fast passes. Too high shows up as thin, gappy walls,
and on a one-perimeter print the wall is the whole part. The preset is left at
the 16 you tested rather than a number nobody has run.
