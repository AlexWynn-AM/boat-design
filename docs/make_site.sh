#!/bin/sh
# Render the Markdown docs into the GitHub Pages site.  Requires pandoc:
#   brew install pandoc
# Usage: docs/make_site.sh
#
# index.html is hand-authored and is NOT touched here. design.html and reference.html are
# generated from DESIGN.md and README.md so the site cannot drift from the source docs:
# edit the Markdown at the repo root, then re-run this. chunks.html is generated straight
# from the manifest and the STLs by render_chunk_map.py -- edit that, not the page.
set -eu
cd "$(dirname "$0")/.."
REPO=https://github.com/AlexWynn-AM/boat-design/blob/main

render() {   # render <source.md> <out.html> <title> <flag>
  pandoc "$1" \
    --from=gfm --to=html5 --standalone \
    --template=docs/page.template.html \
    --toc --toc-depth=3 \
    --metadata title="$3" \
    --metadata source="$1" \
    --metadata "$4"=true \
    --output "docs/$2"

  # Repoint the Markdown's own cross-links: sibling docs go to their rendered pages, and
  # source files go to GitHub, since neither resolves inside the published site.
  sed -i '' \
    -e 's|href="DESIGN\.md"|href="design.html"|g' \
    -e 's|href="README\.md"|href="reference.html"|g' \
    -e "s|href=\"\\([a-zA-Z0-9_]*\\.py\\)\"|href=\"$REPO/\\1\"|g" \
    -e "s|href=\"\\(split_out/[^\"]*\\)\"|href=\"$REPO/\\1\"|g" \
    "docs/$2"
  echo "  docs/$2  <- $1"
}

echo "Rendering site:"
render DESIGN.md design.html    "Engineering design"       is-design
render README.md reference.html "Reference"                is-reference

# chunks.html is not Markdown: it is built from split_out/print_sections_x1c/manifest.csv
# and the chunk geometry, so it cannot drift from the parts it documents.
if [ -x .venv/bin/python ]; then
  .venv/bin/python render_chunk_map.py
else
  echo "  skipped docs/chunks.html (no .venv; run: .venv/bin/python render_chunk_map.py)"
fi

echo "Done. Preview with:  python3 -m http.server -d docs 8000"
