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

**These are 0.4 nozzle presets.** The parent is `0.24mm Draft @BBL X1C`, which is
the 0.4 profile. A 0.6 nozzle cuts the job from roughly 430 hours to 260, but it
needs re-deriving from a 0.6 parent, and the 16 mm3/s volumetric cap should come
up with it.
