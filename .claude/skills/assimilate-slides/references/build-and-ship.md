# BUILD MOCKS · GALLERY · HERO · GATES · SHIP

## The two-mock convention

The gallery shows **two** mocks per style (convention owned by the
`regenerate-hero-image` work; `scripts/gallery.py`'s `gallery_face(sid)` selects
between them):

- **`<id>.cover.html` — the cover mock.** A title/cover-view slide. `gallery_face`
  promotes it to the **gallery card thumbnail + the hero collage tile**, so the
  whole wall reads as uniform covers.
- **`<id>.html` — the detailed mock.** A content-dense slide showcasing the
  style's primitives. It is the **spec deliverable + the `smoke_test` fixture**
  and is always kept.

Both are 1280×720 and pipeline-safe.

- **New style** → build **both** (`<id>.cover.html` + `<id>.html`).
- **Primitives-only on an existing style** → the cover already exists; build or
  refresh the **detailed** mock to demonstrate the new primitives + icons. (Give
  a primitives-demo a clear filename if it is a *separate* fixture from the
  style's canonical detailed mock; otherwise extend the detailed mock.)

## Mock construction rules

- `<body>` is `width:1280px; height:720px; overflow:hidden; position:relative`.
- Define the deck palette/fonts as `:root` custom properties; everything binds
  to them (recolor with `:root`).
- **Pipeline-safe** — none of the forbidden techniques in
  `references/pipeline-compat.md` (`mask-image`, `conic-gradient`,
  `background-image:url()`, `background-clip:text`, `mix-blend-mode`,
  `::before`/`::after` visual `content:`, SVG `<text>`). Real `<div>`/`<table>`,
  SVG `<line>`/`<polygon>`/`<path>`, HTML-overlay labels.
- **Icons inline** — paste `<svg>` verbatim (`icon_search.py <c> --snippet`).

## Regenerate the gallery index

```bash
python3 scripts/gallery.py                # rebuild ppt-output/style-gallery/index.html
python3 scripts/gallery.py --screenshots  # + PNG per gallery_face (needs puppeteer)
```

`gallery.py` auto-discovers styles; the index picks up the new/updated mock via
`gallery_face` (cover preferred). Confirm it runs without error.

## PDF export (deterministic, pixel-1:1)

To export a mock or a whole deck to PDF, use **`scripts/build_pdf.py`** — never
improvise. It renders with the bundled Puppeteer and **screenshots the exact
viewport**, then wraps the PNG into a PDF with the already-present **Pillow**, so
the PDF is **1:1 with the HTML render** (the reason the pipeline screenshots
rather than using a print export).

```bash
python3 scripts/build_pdf.py ppt-output/style-gallery/<mock>.html   # one slide → one-page PDF
python3 scripts/build_pdf.py <a.html> <b.html> --out deck.pdf        # multi-page PDF
python3 scripts/build_pdf.py --deck ppt-output/<deck-dir>            # a deck's slides → one PDF
```

**Banned for PDF (all rasterize wrong, drift from the render, or add a
dependency):** WeasyPrint, `pdf2svg`, `img2pdf`, and Chrome's `page.pdf()` print
export. Vector/selectable text is *not* the goal here — guaranteed visual
fidelity is; `page.pdf()`'s print path is not guaranteed 1:1 with the screen
render. If a PNG→PDF is ever needed without a browser, use present **Pillow**
(`Image.save(..., "PDF")`), never `img2pdf`.

## Hero prompt (Ask first — never automatic)

**Prompt the maintainer**: "Refresh the hero collage?" Regenerating
`docs/assets/hero-*.png` is their call. If **yes**:

1. Ensure the style id is in `tools/build_hero.py` CATEGORIES (coverage:
   reuse `gallery.py`'s `collect_all_styles()` and diff against the union of
   CATEGORIES `ids` — every real id present exactly once).
2. `python3 scripts/gallery.py --screenshots` then `python3 tools/build_hero.py`
   (needs the per-style PNGs + puppeteer).

If **no**, note it in the run spec and leave the collage.

## Gates

Run all four; each must pass:

```bash
python3 tools/smoke_test.py --style <style_id>   # style JSON + mock pipeline-safety + typography
python3 tools/lint_diagram_recipes.py            # block recipes (5 markers, no forbidden, CSS-var)
python3 tools/check_skill.py                     # product-surface doc↔code contract
python3 scripts/icon_search.py --validate          # icon catalog↔files + inline-safety
```

Note: `check_skill.py` guards the shipped product surface and does **not** scan
`.claude/skills/**`. This skill's own verification is: frontmatter is
agentskills.io-compliant (grep the pinned key set + the one-sentence trigger),
every path it names resolves (`test -f`/`test -d` sweep), and a **trace-through**
maps each step to the artifact a prior assimilation produced.

## Ship

1. **Final scrub pass** — re-run the §39 identifier checklist
   (`ingest-and-classify.md`) against the **full diff** (`git diff`); record
   `scrub: clear`. A leaked identifier blocks ship.
2. **Mark the run spec Shipped** — set `Status: Shipped`; every Acceptance
   Criterion is `[x]` or carries `(deferred: <docs/backlog.md anchor>)`.
3. **Doc-drift lint** —
   `python3 .claude/skills/work-loop/scripts/lint-spec-status.py` (the work-loop
   skill's status lint) to confirm the metadata invariants.

Each assimilation run authors its own generic per-run spec at the start (via
`new-spec`, named for the *output* — never the source) and closes it here.
