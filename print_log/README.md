# print_log

The record of what has physically been printed. Moved here from
`~/Desktop/dinghy-print/` on 2026-09-01 so there is exactly ONE copy under
version control — a second copy on the Desktop is how two parts both ended up
being #004.

| file | what it is |
|---|---|
| `STATUS.txt` | **The record.** Per-chunk state: done / on a plate / unconfirmed / not printed. |
| `PLATE_TONIGHT.txt` | The current (or last) overnight plate, and how to tell those parts apart. |
| `START_HERE.txt` | Orientation for the whole print set: order, machines, presets, totals. |

Rules that keep this honest:

- Update `STATUS.txt` when a part comes off the bed, not later.
- Label every chunk in Sharpie **before** it leaves the plate. Mirror twins are
  identical in every measurement the toolchain can make — bounding box to
  0.000 mm, volume to 0.04% — so handedness is unrecoverable once unlabelled.
- One job on the USB stick at a time.

The STLs, G-code and per-piece PROFILE.txt files stay in `~/Desktop/dinghy-print/`
(too large for git). They are regenerable from `slice_for_print.py`; this log is not.
