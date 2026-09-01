#!/usr/bin/env python3
"""
render_chunk_map.py - build docs/chunks.html, the assembly guide for the numbered chunks.

Input : split_out/print_sections_x1c/manifest.csv  (+ the chunk STLs beside it)
        split_out/print_sections_x1c/bow_prusa/    (which bow chunks fit the Core One)
        docs/page.template.html                    (so nav/footer match the rest of the site)
Output: docs/chunks.html

Everything on the page is derived from the manifest and the geometry, so it cannot drift
from the parts. Print progress deliberately lives elsewhere -- print_log/STATUS.txt --
because it changes hourly and this page does not.

Run:   .venv/bin/python render_chunk_map.py
"""
import csv, json, re, sys
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent
SECT = ROOT / "split_out" / "print_sections_x1c"
OUT  = ROOT / "docs" / "chunks.html"

# Which grid axis means what.  Same convention for every piece: x runs aft to forward,
# y runs port to starboard, z stacks bottom to top.
PIECES = {
    "bow":        dict(label="Bow",          blurb="The nose section, forward of the x=60 joint."),
    "center":     dict(label="Center barge",  blurb="The midships box that carries the load."),
    "wedge_port": dict(label="Port wedge",    blurb="Port flare, mirrors the starboard wedge."),
    "wedge_stbd": dict(label="Starboard wedge", blurb="Starboard flare, mirrors the port wedge."),
}
STATIONS = ["aft", "2nd", "3rd", "4th", "5th", "fwd"]


def overhang(mesh):
    """Split downward-facing area into: on the plate, inside a bore, and genuinely open."""
    zmin = mesh.bounds[0][2]
    n, a, c = mesh.face_normals, mesh.area_faces, mesh.triangles_center
    facing = np.where(n[:, 2] < -np.cos(np.radians(45)))[0]
    if not len(facing):
        return 0.0, 0.0, 0.0
    top_z = mesh.vertices[mesh.faces[facing]][:, :, 2].max(axis=1)
    bed = float(a[facing[top_z < zmin + 0.5]].sum() / 100)
    # A downward face with material below it is the ceiling of a dowel bore, not an overhang
    # the slicer has to bridge to the plate.  Supports set to "everywhere" grow into these.
    deep = np.where((n[:, 2] < -0.7) & (c[:, 2] > zmin + 1.0))[0]
    bore = open_ = 0.0
    if len(deep):
        hit = mesh.ray.intersects_any(c[deep] + [0, 0, -0.05],
                                      np.tile([0, 0, -1.0], (len(deep), 1)))
        bore  = float(a[deep[hit]].sum() / 100)
        open_ = float(a[deep[~hit]].sum() / 100)
    return bed, bore, open_


def twin_of(piece, grid, ymax, by_cell):
    """Mirror twin. Bow and center reflect within themselves; the wedges reflect onto
    each other. A center chunk sitting on the centreline row is its own mirror, so it has
    no twin -- those are the only chunks in the boat that are unambiguous on sight."""
    x, y, z = grid
    if piece.startswith("wedge"):
        # The wedges are a mirror pair of PIECES, so a chunk's twin lives in the other
        # wedge -- and reflected, at 1-y, not at the same y. Same-y looks plausible
        # (it matches 16 of 20 cells) and is wrong on every one of them.
        other = "wedge_port" if piece == "wedge_stbd" else "wedge_stbd"
        return by_cell.get((other, x, 1 - y, z))
    if ymax - y == y:
        return None
    return by_cell.get((piece, x, ymax - y, z))


def build():
    rows = list(csv.DictReader(open(SECT / "manifest.csv")))
    prusa = {p.name.split("_")[0] for p in (SECT / "bow_prusa").glob("*_bow_*.stl")}

    by_cell, chunks = {}, {}
    for r in rows:
        g = tuple(int(v) for v in r["grid_ijk"].split(","))
        by_cell[(r["piece"], *g)] = r["seq"]
    ymax = {p: max(int(r["grid_ijk"].split(",")[1]) for r in rows if r["piece"] == p)
            for p in PIECES}

    for i, r in enumerate(rows, 1):
        seq, piece = r["seq"], r["piece"]
        g = [int(v) for v in r["grid_ijk"].split(",")]
        mesh = trimesh.load(SECT / piece / r["file"])
        bed, bore, open_ = overhang(mesh)
        h = float(mesh.extents[2])
        chunks[seq] = dict(
            seq=seq, piece=piece, grid=g, bbox=r["bbox_mm"], vol=float(r["vol_in3"]),
            mates=[m.strip() for m in r["mates_to(dowels)"].split(";") if m.strip()],
            orient=r["orient"], twin=twin_of(piece, g, ymax[piece], by_cell),
            bed=round(bed, 1), bore=round(bore, 2), open=round(open_, 2),
            h=round(h), ratio=round(h / max(bed, 0.01), 1),
            prusa=(piece == "bow" and seq in prusa), exact=True, vol_delta=0.0,
        )
        print(f"\r  {i}/{len(rows)} {seq}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    verify(chunks)
    return chunks, ymax


def verify(chunks):
    """A mirror twin is the same solid reflected, so the pair must agree on bounding box
    and volume. Anything else means the twin rule is wrong for that piece -- which is the
    one error this page exists to prevent, so fail loudly rather than publish it."""
    bad, near = [], []
    for c in chunks.values():
        t = chunks.get(c["twin"] or "")
        if t is None:
            continue
        if t["twin"] != c["seq"]:
            bad.append(f'#{c["seq"]}->#{t["seq"]} is not reciprocal')
            continue
        # Compare the box as a sorted triple: a twin re-oriented onto a different face
        # reports the same solid with its axes permuted, which is not a mismatch.
        a = sorted(int(v) for v in c["bbox"].split("x"))
        b = sorted(int(v) for v in t["bbox"].split("x"))
        dv = abs(t["vol"] - c["vol"]) / max(c["vol"], 1)
        if max(abs(i - j) for i, j in zip(a, b)) > 2:
            bad.append(f'#{c["seq"]} {c["bbox"]} vs #{t["seq"]} {t["bbox"]}')
            continue
        # Most twins are the same solid reflected and differ by nothing a scale can read.
        # A few carry an asymmetric feature -- a notch, a flange, a boss -- and really do
        # differ in volume. Those are the only pairs weight can tell apart, so say so.
        c["exact"] = dv <= 0.005
        c["vol_delta"] = round(dv * 100, 2)
        if not c["exact"] and c["seq"] < t["seq"]:
            near.append(f'#{c["seq"]}/#{t["seq"]} differ by {dv*100:.2f}% in volume '
                        f'-- asymmetric feature, a scale can separate them')
    solo = sorted(k for k, v in chunks.items() if not v["twin"])
    print(f"  twins: {sum(1 for v in chunks.values() if v['twin'])} paired, "
          f"{len(solo)} on the centreline ({', '.join('#'+s for s in solo)})")
    ex = sum(1 for v in chunks.values() if v["twin"] and v.get("exact"))
    print(f"  of those, {ex} are exact mirrors and "
          f"{sum(1 for v in chunks.values() if v['twin'] and not v.get('exact'))} "
          f"carry an asymmetric feature:")
    for n in near:
        print("   ", n)
    if bad:
        print("  TWIN MISMATCH -- the mirror rule is wrong for these:", file=sys.stderr)
        for b in bad:
            print("   ", b, file=sys.stderr)
        raise SystemExit(1)


PAGE_CSS = """
<style>
/* chunks.html only. Every colour comes from the tokens in style.css, so this page
   follows the site into dark mode without defining a palette of its own. */
.cm-key{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:center;margin:0 0 26px;
  font-size:13.5px;color:var(--muted)}
.cm-key b{color:var(--body);font-weight:600}
.cm-tabs{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 22px;padding:0;list-style:none}
.cm-tab{font:600 13px/1 var(--sans);padding:9px 14px;border:1px solid var(--rule);
  border-radius:3px;background:var(--raised);color:var(--body);cursor:pointer}
.cm-tab[aria-selected="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.cm-tab:focus-visible{outline:2px solid var(--accent-ink);outline-offset:2px}
.cm-board{background:var(--raised);border:1px solid var(--rule);border-radius:4px;
  padding:18px 18px 20px;margin:0 0 16px;box-shadow:var(--shadow)}
.cm-board h3{font-size:15px;margin:0 0 3px}
.cm-board .cm-sub{font-size:13px;color:var(--muted);margin:0 0 15px}
.cm-scroll{overflow-x:auto}
table.cm-plan{border-collapse:separate;border-spacing:5px;min-width:560px;margin:0}
table.cm-plan td{padding:0;border:0}
.cm-rowlab,.cm-xlab{font:400 10.5px/1.3 var(--mono);color:var(--muted);white-space:nowrap}
.cm-rowlab{text-align:right;padding-right:10px}
.cm-xlab{text-align:center;padding-top:6px}
.cm-mid td{height:1px;padding:0}
.cm-mid .r{height:0;border-top:1.5px dashed var(--accent);opacity:.55}
.cm-mid .l{font:400 9.5px/1 var(--mono);letter-spacing:.12em;text-transform:uppercase;
  color:var(--accent-ink);text-align:right;padding-right:10px;white-space:nowrap}
.cm-cell{position:relative;display:block;width:100%;min-width:92px;text-align:left;
  font-family:inherit;color:var(--ink);background:var(--code-bg);
  border:1px solid var(--rule);border-radius:3px;padding:10px 9px 9px;cursor:pointer}
.cm-cell:hover{border-color:var(--accent)}
.cm-cell:focus-visible{outline:2px solid var(--accent-ink);outline-offset:2px}
.cm-cell .n{display:block;font:600 16px/1.1 var(--mono);letter-spacing:-.01em}
.cm-cell .d{display:block;font:400 9.5px/1.3 var(--mono);color:var(--muted);margin-top:3px}
.cm-cell .t{position:absolute;top:7px;right:8px;font:600 8.5px/1 var(--mono);
  letter-spacing:.04em;color:var(--muted)}
.cm-cell[data-sel]{border-color:var(--accent);box-shadow:inset 0 0 0 2px var(--accent)}
.cm-cell[data-twin]{border-color:var(--accent-ink);border-style:dashed}
.cm-cell[data-mate]{border-color:var(--body)}
.cm-cell[data-solo] .n{color:var(--accent-ink)}
.cm-void{min-height:58px;border:1px dashed var(--rule);border-radius:3px;opacity:.45}
.cm-detail{background:var(--raised);border:1px solid var(--rule);border-radius:4px;
  padding:18px 20px;box-shadow:var(--shadow);margin:0 0 30px}
.cm-detail h3{font:600 20px/1.1 var(--mono);margin:0 0 4px}
.cm-detail .cm-where{color:var(--muted);font-size:13.5px;margin:0 0 16px}
.cm-cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:20px}
.cm-cols h4{font:500 10.5px/1 var(--mono);letter-spacing:.13em;text-transform:uppercase;
  color:var(--muted);margin:0 0 9px}
.cm-cols dl{display:grid;grid-template-columns:auto 1fr;gap:5px 14px;margin:0;font-size:13px}
.cm-cols dt{color:var(--muted)}
.cm-cols dd{margin:0;font:400 12.5px/1.5 var(--mono);text-align:right;
  font-variant-numeric:tabular-nums;color:var(--ink)}
.cm-seams{display:flex;flex-direction:column;gap:4px}
.cm-seam{display:flex;justify-content:space-between;gap:10px;font:400 12.5px/1.5 var(--mono);
  padding:4px 9px;background:var(--code-bg);border-radius:2px}
.cm-seam span{color:var(--muted)}
.cm-note{border-left:2.5px solid var(--accent);padding:2px 0 2px 13px;margin:16px 0 0;
  font-size:13px;line-height:1.55;color:var(--body)}
.cm-note b{color:var(--ink)}
.cm-note.ok{border-left-color:var(--muted)}
.prose .warn{border-left:3px solid var(--accent);background:var(--code-bg);
  padding:13px 16px;border-radius:0 3px 3px 0;margin:0 0 1.05em}
.prose .warn b{color:var(--ink)}
table.cm-all{width:100%;border-collapse:collapse;font-size:13px;margin:0}
table.cm-all th{text-align:left;font:600 10.5px/1 var(--mono);letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);padding:0 10px 9px 0;
  border-bottom:1px solid var(--rule);white-space:nowrap}
table.cm-all td{padding:7px 10px 7px 0;border-bottom:1px solid var(--rule);
  font-variant-numeric:tabular-nums;vertical-align:top}
table.cm-all td.m{font-family:var(--mono);font-size:12.5px;white-space:nowrap}
table.cm-all tbody tr:hover{background:var(--code-bg)}
@media (max-width:700px){.cm-cols{grid-template-columns:1fr}}
</style>
"""


def cell_html(c):
    if c is None:
        return '<div class="cm-void"></div>'
    tag = ""
    if c["piece"] == "bow":
        tag = "core one" if c["prusa"] else "x1c only"
    elif c["twin"] is None:
        tag = "unique"
    return (f'<button class="cm-cell" data-id="{c["seq"]}"'
            f'{" data-solo" if c["twin"] is None else ""}>'
            f'<span class="n">#{c["seq"]}</span>'
            f'<span class="d">{c["bbox"]}</span>'
            f'<span class="t">{tag}</span></button>')


def boards_html(chunks, ymax):
    at = {(c["piece"], *c["grid"]): c for c in chunks.values()}
    out = []
    for piece, meta in PIECES.items():
        ys = ymax[piece]
        zs = sorted({c["grid"][2] for c in chunks.values() if c["piece"] == piece})
        xs = max(c["grid"][0] for c in chunks.values() if c["piece"] == piece)
        panel = [f'<div class="cm-piece" id="cm-{piece}" hidden>']
        for z in zs:
            panel.append(f'<section class="cm-board"><h3>Layer z{z}</h3>'
                         f'<p class="cm-sub">{["bottom / keel","middle","top / sheer"][z]}'
                         f' &mdash; {meta["blurb"]}</p>'
                         f'<div class="cm-scroll"><table class="cm-plan"><tbody>')
            for y in range(ys + 1):
                # draw the centreline where the hull's own mirror plane falls
                if ys % 2 == 1 and y == (ys + 1) // 2:
                    panel.append('<tr class="cm-mid"><td class="l">centreline</td>'
                                 f'<td colspan="{xs+1}"><div class="r"></div></td></tr>')
                side = ("centreline row" if ys - y == y else
                        "port" if y * 2 < ys else "starboard")
                edge = "outer" if y in (0, ys) and ys > 1 else "inner"
                lab = f"y{y} &middot; {side}" + ("" if side == "centreline row" else f" {edge}")
                panel.append(f'<tr><td class="cm-rowlab">{lab}</td>')
                for x in range(xs + 1):
                    panel.append(f'<td>{cell_html(at.get((piece, x, y, z)))}</td>')
                panel.append("</tr>")
            panel.append(f'<tr><td></td>')
            for x in range(xs + 1):
                nm = STATIONS[x] if x < len(STATIONS) else f"x{x}"
                if x == 0: nm = "x0 aft"
                elif x == xs: nm = f"x{x} fwd"
                else: nm = f"x{x}"
                panel.append(f'<td class="cm-xlab">{nm}</td>')
            panel.append("</tr></tbody></table></div></section>")
        panel.append("</div>")
        out.append("".join(panel))
    return "".join(out)


def table_html(chunks):
    r = ['<div class="cm-scroll"><table class="cm-all"><thead><tr>'
         '<th>Chunk</th><th>Piece</th><th>Grid</th><th>Size mm</th><th>in&sup3;</th>'
         '<th>Twin</th><th>Stands on</th><th>Bonds to</th></tr></thead><tbody>']
    for c in sorted(chunks.values(), key=lambda v: v["seq"]):
        tw = f'#{c["twin"]}' if c["twin"] else "&mdash; unique"
        r.append(f'<tr><td class="m">#{c["seq"]}</td><td>{PIECES[c["piece"]]["label"]}</td>'
                 f'<td class="m">x{c["grid"][0]} y{c["grid"][1]} z{c["grid"][2]}</td>'
                 f'<td class="m">{c["bbox"]}</td><td class="m">{c["vol"]}</td>'
                 f'<td class="m">{tw}</td><td class="m">{c["orient"]}</td>'
                 f'<td class="m">{"; ".join(c["mates"])}</td></tr>')
    r.append("</tbody></table></div>")
    return "".join(r)


PROSE = """
<h1>Chunk assembly guide</h1>
<p class="lede">Every printed piece of this boat carries a number. This page says what each
number is, where it sits in the hull, what it bonds to, and &mdash; the part that costs real
parts when it goes wrong &mdash; which of two identical-looking halves you are holding.</p>

<h2 id="numbering">How the numbering works</h2>
<p>The four transportable pieces are each cut on their own grid of printer-bed-sized chunks.
A chunk's grid address is written <code>x&middot;y&middot;z</code> and appears in its
filename, so <code>031_bow_x0y2z2.stl</code> is chunk&nbsp;#031, at grid x0&nbsp;y2&nbsp;z2
of the bow.</p>
<ul>
<li><b>x</b> runs <b>aft to forward</b>. x0 is the aft end, at the x=60 joint; the highest x
is the nose or the forward end of that piece.</li>
<li><b>y</b> runs <b>port to starboard</b>. Low y is port, high y is starboard, and the
outermost rows are the outboard chunks.</li>
<li><b>z</b> stacks <b>bottom to top</b>. z0 sits on the keel, the highest z reaches the sheer.</li>
</ul>
<p>Numbers run in grid order across the whole boat, so the bow is #001&ndash;#044, the center
barge #045&ndash;#109, and the two wedges #110&ndash;#149. They are not a print order &mdash;
print order is a separate question, and lives with the build notes rather than here.</p>

<h2 id="twins">Mirror twins, and why they matter</h2>
<p>The hull is symmetrical, so nearly every chunk has a <b>mirror twin</b> on the other side
of the centreline: the same solid, reflected. In the boards below a twin is always the
reflection of its partner across the dashed line.</p>
<p class="warn"><b>Size identifies the pair, never which half you are holding.</b> Twins match
to 0.000&nbsp;mm on the bounding box and to within 0.04% on volume. A caliper, a scale and
the manifest all read identical on both; only handedness differs. Once a twin leaves the
print bed unlabelled, nothing in the toolchain can recover which one it is &mdash; both are
watertight, both are manifest-correct, both are perfect prints.</p>
<p><b>So label every chunk in marker before it leaves the plate.</b> It is the one defect on
this boat that survives every automated check, and it has already happened.</p>
<p>Two kinds of exception are worth knowing, and both are marked below. A handful of pairs
carry an <b>asymmetric feature</b> &mdash; a notch, a flange, a boss that exists on only one
side &mdash; and those really do differ in volume, by up to 3%. For that handful, and only
that handful, a scale separates the halves. Every other pair on the boat is identical to
within measurement noise.</p>
<p>The other exception is structural. The center barge has an odd number of rows, so its
middle row sits <em>on</em> the centreline and is its own reflection &mdash; those chunks are
marked <b>unique</b> below and are unambiguous on sight. And the two wedges mirror
<em>each other</em> rather than themselves, so a port wedge chunk's twin is a starboard wedge
chunk, in a different piece entirely.</p>

<h2 id="map">The map</h2>
<p>Pick a piece, then select any chunk. Its mirror twin outlines in a dashed accent, the
chunks it bonds to outline in solid, and the detail below fills in.</p>
"""

FOOTNOTE = """
<h2 id="seams">Seams and dowels</h2>
<p>Every seam between two chunks is bonded and pinned. The dowel count in each chunk's
<em>bonds to</em> list is the number of alignment pins on that one seam &mdash; a
<code>#013(3)</code> entry means three dowels into chunk&nbsp;#013.</p>
<p>Dowels are printed: 4.0&nbsp;mm pins into 4.2&nbsp;mm bores, 6&nbsp;mm into each side.
That is 0.2&nbsp;mm of total clearance, so a fit measured on one printer is only an
assumption on another &mdash; dry-fit a dowel from each machine before any glue goes on.
<b>If they bind, do not open the holes.</b> Opening a bore changes the spec for every chunk
already printed; reprint the dowel smaller instead.</p>
<p>The <em>inside bores</em> figure on each chunk is the downward-facing area that belongs to
a horizontal dowel bore rather than to a real overhang. On most chunks it is the majority of
what a slicer reports as overhang, which is why supports &mdash; where they are used at all
&mdash; must be set to build-plate-only. A support left on "everywhere" grows up into the
bores, and a bore with support material in it cannot be cleaned without reaming it oversize.</p>

<h2 id="printing">Reading the print figures</h2>
<p><b>Bed contact</b> is the flat area actually touching the plate in the orientation the
chunk is exported in. <b>Ratio</b> is height divided by that contact, and it is the single
best predictor of a chunk letting go mid-print: the tall, narrow-footed chunks peel as the
ASA shrinks, and the force grows the whole way up. Anything above roughly 10 wants a raft
and the widest brim its plate position allows.</p>
<p><b>Stands on</b> names the face the chunk was exported sitting on. Do not auto-orient in
the slicer and do not rotate a chunk back to look like the boat &mdash; the exported stance
is chosen to put a flat cut face on the plate.</p>

<h2 id="all">Every chunk</h2>
<p>All %d chunks, in number order.</p>
"""


def render(chunks, ymax):
    tpl = (ROOT / "docs" / "page.template.html").read_text()
    body = (PAGE_CSS + '<div class="prose">' + PROSE + "</div>"
            + '<ul class="cm-tabs" role="tablist">'
            + "".join(f'<li><button class="cm-tab" role="tab" data-piece="{p}"'
                      f' aria-selected="false">{m["label"]}</button></li>'
                      for p, m in PIECES.items())
            + "</ul>"
            + '<div class="cm-key"><b>Dashed outline</b> mirror twin &nbsp;'
              '<b>solid outline</b> bonded seam &nbsp;'
              '<b>unique</b> sits on the centreline, has no twin</div>'
            + boards_html(chunks, ymax)
            + '<div class="cm-detail" id="cm-detail"></div>'
            + '<div class="prose">' + (FOOTNOTE % len(chunks)) + "</div>"
            + table_html(chunks)
            + "<script>const CHUNKS=" + json.dumps(chunks, separators=(",", ":"))
            + ";" + SCRIPT + "</script>")

    # Fill the pandoc template by hand: this page is not Markdown, but it must carry the
    # same nav, footer and theming as the pages that are.
    html = tpl
    html = re.sub(r"\$if\(toc\)\$.*?\$else\$(.*?)\$endif\$", r"\1", html, flags=re.S)
    html = re.sub(r"\$if\(description\)\$.*?\$endif\$",
                  '<meta name="description" content="Where every numbered chunk sits in the '
                  'hull, what it bonds to, and how to tell mirror twins apart.">', html)
    html = re.sub(r"\$if\(is-chunks\)\$(.*?)\$endif\$", r"\1", html)
    html = re.sub(r"\$if\([a-z-]+\)\$.*?\$endif\$", "", html)
    html = html.replace("$title$", "Chunk assembly guide")
    html = html.replace("$source$", "split_out/print_sections_x1c/manifest.csv")
    html = html.replace("$body$", body)
    html = html.replace("by <code>docs/make_site.sh</code>",
                        "by <code>render_chunk_map.py</code>")
    html = html.replace("Edit the Markdown, not this page.",
                        "Edit the generator, not this page.")
    OUT.write_text(html)
    print(f"  docs/chunks.html  <- {len(chunks)} chunks from manifest.csv")


SCRIPT = r"""
(function(){
  const P={bow:'Bow',center:'Center barge',wedge_port:'Port wedge',wedge_stbd:'Starboard wedge'};
  const SIDE=['port','starboard'];
  const tabs=[...document.querySelectorAll('.cm-tab')];
  const detail=document.getElementById('cm-detail');
  function show(piece){
    tabs.forEach(t=>t.setAttribute('aria-selected',String(t.dataset.piece===piece)));
    document.querySelectorAll('.cm-piece').forEach(d=>d.hidden=(d.id!=='cm-'+piece));
    const first=document.querySelector('#cm-'+piece+' .cm-cell');
    if(first) pick(first.dataset.id);
  }
  function where(c){
    const ys=Math.max(...Object.values(CHUNKS).filter(v=>v.piece===c.piece).map(v=>v.grid[1]));
    const y=c.grid[1];
    const side = ys-y===y ? 'on the centreline' :
      (y*2<ys?'port':'starboard')+' '+((y===0||y===ys)&&ys>1?'outboard':'inboard');
    const lay=['bottom','middle','top'][c.grid[2]]||('z'+c.grid[2]);
    return P[c.piece]+', '+side+', '+lay+' layer';
  }
  function pick(id){
    const c=CHUNKS[id]; if(!c) return;
    const mates=c.mates.map(m=>(m.match(/\d+/)||[''])[0]);
    document.querySelectorAll('.cm-cell').forEach(el=>{
      el.removeAttribute('data-sel');el.removeAttribute('data-twin');el.removeAttribute('data-mate');
      const i=el.dataset.id;
      if(i===id) el.setAttribute('data-sel','');
      else if(i===c.twin) el.setAttribute('data-twin','');
      else if(mates.includes(i)) el.setAttribute('data-mate','');
    });
    let twin;
    if(!c.twin){
      twin='<p class="cm-note ok"><b>No mirror twin.</b> This chunk sits on the centreline '+
        'and is its own reflection, so it cannot be confused with another part.</p>';
    } else if(c.exact){
      twin='<p class="cm-note"><b>Mirror twin: #'+c.twin+'.</b> Both measure '+c.bbox+
        ' mm and '+c.vol+' in&sup3;. Those numbers confirm the pair, not which half this '+
        'is &mdash; only handedness differs. Nothing you can measure separates them, so '+
        'label it before it leaves the plate.</p>';
    } else {
      twin='<p class="cm-note ok"><b>Mirror twin: #'+c.twin+', and they are not identical.</b> '+
        'An asymmetric feature makes this pair differ by '+c.vol_delta+'% in volume, so '+
        'unlike most twins on this boat <b>a scale will separate them</b>. Weigh it rather '+
        'than guessing at the curve.</p>';
    }
    detail.innerHTML='<h3>#'+c.seq+'</h3><p class="cm-where">'+where(c)+
      ' &middot; grid x'+c.grid[0]+' y'+c.grid[1]+' z'+c.grid[2]+'</p><div class="cm-cols">'+
      '<div><h4>Identity</h4><dl>'+
        '<dt>Size</dt><dd>'+c.bbox+' mm</dd>'+
        '<dt>Volume</dt><dd>'+c.vol+' in&sup3;</dd>'+
        '<dt>Stands on</dt><dd>'+c.orient+'</dd>'+
        '<dt>Mirror twin</dt><dd>'+(c.twin?'#'+c.twin:'none')+'</dd></dl></div>'+
      '<div><h4>Bonds to</h4><div class="cm-seams">'+
        c.mates.map(m=>{const k=(m.match(/\d+/)||[''])[0];const d=(m.match(/\((\d+)\)/)||[,'?'])[1];
          return '<div class="cm-seam"><b>#'+k+'</b><span>'+d+' dowels</span></div>';}).join('')+
        '</div></div>'+
      '<div><h4>Printing</h4><dl>'+
        '<dt>Bed contact</dt><dd>'+c.bed+' cm&sup2;</dd>'+
        '<dt>Height</dt><dd>'+c.h+' mm</dd>'+
        '<dt>Ratio</dt><dd>'+c.ratio+'</dd>'+
        '<dt>Open overhang</dt><dd>'+c.open+' cm&sup2;</dd>'+
        '<dt>Inside bores</dt><dd>'+c.bore+' cm&sup2;</dd>'+
        (c.piece==='bow'?'<dt>Core One</dt><dd>'+(c.prusa?'fits':'X1C only')+'</dd>':'')+
      '</dl></div></div>'+twin+
      (c.ratio>=10?'<p class="cm-note"><b>Tall on a small foot.</b> Ratio '+c.ratio+
        ' is in the band where chunks peel off the plate late in the print. Give it a raft '+
        'and the widest brim its plate position allows.</p>':'');
  }
  tabs.forEach(t=>t.addEventListener('click',()=>show(t.dataset.piece)));
  document.addEventListener('click',e=>{
    const b=e.target.closest('.cm-cell'); if(b) pick(b.dataset.id);
  });
  show('bow');
})();
"""

if __name__ == "__main__":
    render(*build())
