# CBA build-day deck

`../herestuck_boat_build_day.pptx`, 11 slides, 16:9.

    .venv/bin/python render_views.py     # renders into docs/assets/ (shared with the site)
    .venv/bin/python deck/build_deck.py  # rebuild the .pptx

Numbers in the deck come from the geometry, not from notes: bow print times from chunk
volume over the profile's 20 mm3/s cap, support areas from `orient_chunks.stance`, dowel
and bolt counts from `manifest.csv` and the constants in `dinghy_split.py`. If any of those
change, the deck copy has to change with them.

Voice follows the *voice rules only* from `~/dev/am-docs/.claude/skills/investor-materials`
(`references/house-voice.md`): plain noun-phrase headings, no colon-subtitle formula, no
em-dashes, no "X, not Y" pairs, numbers carrying their basis inline. No AM canon, framing
or numbers cross over, which is the same line drawn for README.md and DESIGN.md.
