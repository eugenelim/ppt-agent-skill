# INGEST · SCRUB · CLASSIFY

## 1. Acquire the source

The source is a **local folder/file path** or a **URL**.

- **Local folder** — glob for `*.html`/`*.css`, `*.pptx`, `*.pdf`, `*.svg`,
  `*.png`/`*.jpg`. A folder may mix formats (a deck export + its assets).
- **URL** — fetch the page with WebFetch; for a hosted `.pptx`/`.pdf`, download
  it locally first, then read as below. If web fetch is unavailable, say so and
  ask for a local copy — never guess the content.

Put **all** analysis output in the gitignored `.context/` scratch (a throwaway
analyzer script + its stdout). Nothing raw or identifying is ever written to a
committed file.

## 2. Read each format for *reusable form*

You want palette, typography, layout grammar, primitive structures, and icon
*ideas* — not content.

**Use the bundled probe — do not improvise a parser.** Run
`python3 scripts/deck_probe.py <file|dir> [--labels]` (redirect into `.context/`).
It extracts *reusable form* deterministically with **only already-present deps**
(`python-pptx`, `lxml`, stdlib): for a `.pptx` — per-slide shape composition,
top fonts, focus/fill colors, **dense-diagram slides** (architecture-canvas
candidates), and **image-heavy discard candidates**; for `.html`/`.css` — `:root`
custom properties, font stacks, and the hex palette. `--labels` also prints short
text labels for icon-concept spotting (scrub before any commit).

- **HTML/CSS** — read the stylesheet: `:root` custom properties, font stacks +
  `@font-face`/Google-Fonts imports, the color set, radius/shadow/border rules,
  and the repeated block structures (cards, bands, tables, diagrams).
- **PPTX** — use `python-pptx`. A scratch analyzer (see the pattern in a prior
  run's `.context/analyze_deck.py`) enumerates, per slide: layout name; shape
  types (`AUTO_SHAPE`/`FREEFORM`/`LINE`/`PICTURE`/`TABLE`/`GROUP`); run fonts
  (`run.font.name`) and font colors; solid fill colors; picture area vs. slide
  area; text char count. Aggregate: **top fonts** (→ typography), **top colors**
  (→ palette + focus color), **dense `AUTO_SHAPE`/`FREEFORM`/`LINE` slides**
  (→ diagram/architecture primitives), **`FREEFORM` clusters** (→ icon ideas).
- **PDF** — read pages (harness page-read or render to images); treat as
  image + extracted text; same palette/type/layout read.
- **Images / SVG** — read visually for palette, layout, and icon ideas. For SVG,
  study the *concept* each glyph expresses; you will **redraw**, never copy.

### Dependency discipline (no ad-hoc installs)

The single biggest source of non-determinism here is an agent `pip install`ing a
random library to open a format. **Don't.** The sanctioned toolchain is:
`python-pptx` + `lxml` (PPTX, already declared), stdlib + `deck_probe.py`
(HTML/CSS), Pillow (already present, for hero collage), and the harness's own
viewer for **PDF / images / SVG** (it renders them — read by eye). If a format
has no bundled tool, **read it with the harness, never install a renderer/parser**
(no `pymupdf`, `pdf2image`, `cairosvg`, `unoconv`, …). Adding a runtime dependency
is a `Never do` boundary for this skill. `deck_probe.py` uses poppler
(`pdftotext`/`pdfinfo`) for a source PDF only if it is *already* on the machine,
never installing it.

For PDF **output** (exporting mocks/decks), the sanctioned tool is
`scripts/build_pdf.py` (Puppeteer screenshot + present-Pillow, pixel-1:1);
**never** WeasyPrint / `pdf2svg` / `img2pdf` / a `page.pdf()` print export — see
`build-and-ship.md`.

## 3. Scrub — the §39 identifier checklist (mandatory, before any write)

Reproduce reusable form only. Run this checklist over everything you'll carry
forward and again against the final diff at ship (`build-and-ship.md`). Each
class → replace with a neutral placeholder (`Acme`, `Program`, `example.com`):

- deck / file name
- client / customer name
- employer / vendor name
- project or deck **code-name**
- personal names
- emails
- internal URLs / hostnames
- ticket / issue IDs
- product / offering names
- any verbatim confidential body text

Record the pass in the run spec (`scrub: clear` per class). A single leaked
identifier is a Blocker. This applies to the spec and plan too — name the source
only generically (e.g. "a maintainer-supplied engineering session deck").

## 4. Discard slides with no reusable form

Image-only covers, section dividers, and photo collages carry no reusable
structure. Heuristic: **picture-area-fraction > ~0.55 and text < ~120 chars →
discard** (also drop pure photo collages even above the text floor). Record them
generically in the run spec ("N image-only divider/cover slides discarded"),
never their content.

## 5. Classify — three decisions, recorded in the run spec

**a. Absorption shape.** Compare palette + typography + decoration DNA (radius,
shadow, line-art vs. filled, focus-color discipline) against the existing styles
(`references/styles/index.md` panorama + decision matrix, and the board files):

- **New style** — distinct palette/type/DNA with no existing match → mint one
  (`extract-style.md`, full path).
- **Restyle** — you are *intentionally* re-skinning an existing style to the
  source's language (as `schematic_blueprint`'s runbook restyle did).
- **Primitives-only** — the source's *style* already matches an existing one
  (same palette/type/line-art grammar); mint **no** style, map to it, and go
  straight to primitives/icons. (This is the common case for a deck that shares
  an existing style's look.)

**b. Board category.** One of the five enum values, by base tone: dark ground →
`dark_professional`; white/light premium → `light_premium`; saturated multi-hue →
`vibrant`; oriental/cultural → `cultural_oriental`; earthy/retro → `natural_retro`.

**c. Narrative type.** Persuasion (SCQA/pyramid, argument cards) · reference-
runbook (worksheet/checklist/RACI/schedule) · other (e.g. an offering/solution
session). Drives `narrative-and-playbooks.md` in step 7.

Write a short **Classification** block into the run spec: shape + matched style
(if any) + category + narrative type + discard list + scrub-clear line.
