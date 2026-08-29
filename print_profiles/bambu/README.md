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
nozzle_temperature              275 C  (also on the initial layer)
filament_max_volumetric_speed   16 mm3/s
```

## Two things to know

**Brim and bottom shells were not in the original preset.** They were being set
per plate, which is exactly how a chunk ends up printed without a brim. They are
in the preset now. Everything else is byte-identical to the tuned original.

**These are 0.4 nozzle presets**, and with no 0.6 to swap to, the volumetric cap
is the only speed lever on the job. It is already boosted: stock Generic ASA is
12 mm3/s at 260 C, this profile is 16 at 270.

**Neither the cap nor the temperature has been print-tested yet.** Treat both as
starting points, not settings.

The cap is genuinely what governs. This process profile asks for 24 mm3/s on
outer walls and 27.6 on inner walls and sparse infill, so a 16 cap throttles
every one of those moves to about 58% of profile speed. Anything up to roughly
27 converts into time almost linearly:

```
12 mm3/s   446 h    stock
16 mm3/s   334 h    this profile
20 mm3/s   267 h    the remaining headroom
```

Temperature is set to 275 C. ASA's usual guidance for interlayer strength is
265-280 C, 5-10 C above the 260-270 default, and an enclosure makes the top of
that range safer because the part cools slowly enough for polymer chains to
diffuse across the layer interface. That matters more here than usual: these
chunks print at one perimeter, so the wall is the entire part and its weak axis
is Z. 280 C is left on the table deliberately, since it is the top of the
filament's stated range with no margin and too hot degrades adhesion much as too
cold does.

Run the max volumetric speed calibration at 275 C before committing. It takes
about 20 minutes against a 334 hour job. Under-extrusion does not fail loudly
here, it thins every wall slightly across all 149 chunks. Set the cap to the
tested figure less about 10%, and change one thing at a time.
