#!/bin/sh
# Render the Markdown docs to PDF.  Requires pandoc and weasyprint:
#   brew install pandoc weasyprint
# Usage: ./make_pdf.sh [README.md DESIGN.md ...]   (defaults to both)
set -eu
cd "$(dirname "$0")"
DOCS=${*:-"README.md DESIGN.md"}

CSS=$(mktemp -t boatpdf).css
cat > "$CSS" <<'CSSEOF'
@page {
  size: letter;
  margin: 20mm 18mm 18mm 18mm;
  @bottom-center { content: counter(page); font: 9pt/1 "Helvetica Neue", sans-serif; color: #888; }
  @top-right     { content: string(doctitle); font: 8.5pt/1 "Helvetica Neue", sans-serif; color: #aaa; }
}
html { font-size: 10.5pt; }
body {
  font-family: "Charter", "Georgia", "Times New Roman", serif;
  line-height: 1.5; color: #1a1a1a; hyphens: auto; text-align: justify;
}
header#title-block-header { display: none; }   /* pandoc's metadata title, not ours */
h1 { string-set: doctitle content(); font-size: 22pt; line-height: 1.15;
     margin: 0 0 1.2em; font-weight: 600; letter-spacing: -0.01em; }
h2 { font-size: 14pt; margin: 2em 0 0.6em; font-weight: 600;
     border-bottom: 0.5pt solid #d8d8d8; padding-bottom: 0.25em; }
h3 { font-size: 11.5pt; margin: 1.5em 0 0.4em; font-weight: 600; }
h1, h2, h3 { break-after: avoid; text-align: left; }
p, ul, ol, table, pre { break-inside: avoid-page; }
p { margin: 0 0 0.75em; orphans: 2; widows: 2; }
ul, ol { margin: 0 0 0.85em; padding-left: 1.3em; }
li { margin-bottom: 0.3em; }
code, pre, kbd { font-family: "SF Mono", "Menlo", "Consolas", monospace; }
code { font-size: 0.86em; background: #f4f4f4; padding: 0.08em 0.3em; border-radius: 2px; }
pre { background: #f7f7f7; border: 0.5pt solid #e2e2e2; border-radius: 3px;
      padding: 0.7em 0.9em; font-size: 8.6pt; line-height: 1.42;
      overflow-wrap: break-word; white-space: pre-wrap; text-align: left; margin: 0 0 1em; }
pre code { background: none; padding: 0; font-size: inherit; }
table { border-collapse: collapse; width: 100%; font-size: 9pt; margin: 0 0 1.1em; text-align: left; }
th { border-bottom: 1pt solid #333; padding: 0.42em 0.55em; font-weight: 600;
     text-align: left; font-family: "Helvetica Neue", sans-serif; font-size: 8.5pt;
     text-transform: uppercase; letter-spacing: 0.04em; }
td { border-bottom: 0.5pt solid #e4e4e4; padding: 0.42em 0.55em; vertical-align: top; }
td:nth-child(n+2) { font-variant-numeric: tabular-nums; }
a { color: #14507a; text-decoration: none; }
blockquote { margin: 0 0 1em; padding-left: 0.9em; border-left: 2pt solid #ddd; color: #444; }
hr { border: none; border-top: 0.5pt solid #ddd; margin: 1.6em 0; }
CSSEOF

for f in $DOCS; do
  out="${f%.md}.pdf"
  pandoc "$f" --from=gfm --to=html5 --standalone --metadata title="${f%.md}" \
    | weasyprint - "$out" --stylesheet "$CSS" --quiet
  printf '%s -> %s\n' "$f" "$out"
done
rm -f "$CSS"
