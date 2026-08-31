# Documentation site

The GitHub Pages site for this repository. Live at
<https://alexwynn-am.github.io/boat-design/> once Pages is enabled.

## Enabling it

Repository **Settings -> Pages -> Build and deployment**, source **Deploy from a branch**,
branch `main`, folder `/docs`. No Actions workflow and no build step: the site is plain
static files. `.nojekyll` is present so GitHub serves them as written rather than running
them through Jekyll.

## What is generated and what is not

| File | Source |
| --- | --- |
| `index.html` | Hand-authored. Edit directly. |
| `design.html` | Generated from `../DESIGN.md` |
| `reference.html` | Generated from `../README.md` |
| `assets/*.png` | Generated from the STLs by `../render_views.py` |
| `style.css`, `page.template.html` | Hand-authored |

    ./docs/make_site.sh                    # regenerate design.html + reference.html
    .venv/bin/python render_views.py       # regenerate assets/ from split_out/*.stl
    python3 -m http.server -d docs 8000    # preview at localhost:8000

Editing `design.html` or `reference.html` by hand is wasted work: the next `make_site.sh`
overwrites them. Edit the Markdown at the repo root instead.

`make_site.sh` also repoints the Markdown's own cross-links, which do not resolve in a
published site: sibling `.md` links become the rendered pages, and links to `.py` files and
to `split_out/` become GitHub URLs.

## Numbers

Figures on `index.html` are copied from the generated docs and from the print pipeline, so
they can drift if the geometry changes. The ones to re-check after a regeneration are the
piece dimensions and masses (`DESIGN.md`, weight model), the bolt and dowel counts, the
chunk count, and the support areas from `orient_chunks.py`.
