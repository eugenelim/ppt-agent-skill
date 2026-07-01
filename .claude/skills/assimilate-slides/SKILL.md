---
name: assimilate-slides
description: Use when a maintainer wants to absorb external slides into the skill's assets — an HTML/PPTX/PDF deck or loose images/SVGs, from a local folder or a URL — extracting a matched-or-new visual style, reusable block primitives, idea-level redrawn icons, and any narrative variations, then building gated gallery mocks. Triggers on "assimilate this deck", "absorb these slides", "turn this PPTX into a style", "extract primitives/icons from these slides".
metadata:
  internal: true
  audience: repo-maintainers
---

# Skill: assimilate-slides

Turn a pile of source slides into first-class skill assets — the process that
produced `graphite_gold` and `schematic_blueprint`, generalized and made
repeatable. It **scrubs every identifier first**, then extracts *reusable form
only*: a style, block primitives, redrawn icons, and any narrative variation —
each landing in its canonical home and passing the mechanical gates.

## When to invoke

A maintainer has source slides (a folder or a URL) and wants their reusable
design language in the skill. Run this **inside `work-loop`** (light mode by
default; full mode if a risk trigger fires) — this skill is the *domain
procedure*, `work-loop` is the *discipline*. Each run authors its own generic
per-run spec and ends by marking it Shipped.

**Non-negotiable (AGENTS.md §39):** reproduce only reusable form — layout,
palette, type, primitives, icon *ideas*. Strip the source's identity from every
committed artifact (spec, plan, recipes, icons, mocks, commit messages). No
client / employer / project / product name, no deck code-name, no verbatim
confidential text. Ever.

## Progressive disclosure

The spine below is thin. Depth lives in this skill's `references/` (linked per
step), loaded on demand. Repo machinery it drives lives under the repo's own
`references/…`, `scripts/…`, and `ppt-output/…`.

## The procedure

Run the steps in order; each names its canonical home and its gate.

1. **INGEST.** Acquire the source from a local folder or a URL, then run the
   bundled deterministic probe — `python3 scripts/deck_probe.py <file|dir>
   [--labels]` — for HTML/CSS + PPTX reusable form; read PDF/images/SVG with the
   harness viewer. **Use only already-present deps (`python-pptx`, `lxml`, stdlib,
   Pillow); never `pip install` a parser/renderer.** Dump analysis to the
   gitignored `.context/` scratch, never to a committed file.
   → [`references/ingest-and-classify.md`](references/ingest-and-classify.md)

2. **SCRUB & DISCARD.** Run the §39 identifier checklist over everything you'll
   carry forward; replace identifiers with neutral placeholders. Discard slides
   with no reusable form — image-only covers/dividers and photo collages
   (area-fraction + low-text heuristic).
   → [`references/ingest-and-classify.md`](references/ingest-and-classify.md)

3. **CLASSIFY.** Decide the shape of the absorption: **new style** vs. **restyle
   of an existing one** vs. **primitives-only (style already covered)**; the
   board **category** (`dark_professional` / `light_premium` / `vibrant` /
   `cultural_oriental` / `natural_retro`); and the **narrative type** (persuasion
   vs. reference-runbook vs. other). Record the decision in the run spec.
   → [`references/ingest-and-classify.md`](references/ingest-and-classify.md)

4. **EXTRACT STYLE.** For a new style, author the 15-key style JSON + an N-point
   styling spec in the board file. For a match, map to the existing style and
   record *why* — **do not mint a duplicate**. Then update every index counter
   and row.
   → [`references/extract-style.md`](references/extract-style.md)

5. **EXTRACT PRIMITIVES.** Lift the source's reusable UI structures into a
   paste-ready, CSS-variable-themed, pipeline-safe block recipe (fixed 5-marker
   section order). Prefer extending an existing block family (auto-linted);
   register a standalone file in `blocks/README.md` + the lint target list.
   → [`references/extract-primitives.md`](references/extract-primitives.md)

6. **EXTRACT ICONS.** Redraw — idea-level, never traced — the icon concepts the
   source leans on into the searchable SVG library; add catalog entries; validate.
   → [`references/extract-icons.md`](references/extract-icons.md)

7. **NARRATIVE & PLAYBOOKS.** Review `principles/narrative-arc.md` and the
   playbooks for a new archetype, convention, or authoring pattern. Additions are
   **guidance-only**; engine-level enum/`page_type` changes are deferred to
   `docs/backlog.md`. Record a one-line decision (`new: <name>` | `none`).
   → [`references/narrative-and-playbooks.md`](references/narrative-and-playbooks.md)

8. **BUILD MOCKS.** Build the two 1280×720 pipeline-safe mocks per the gallery's
   two-mock convention — a cover mock `<id>.cover.html` (the gallery face + hero
   thumbnail) and a detailed mock `<id>.html` (spec deliverable + `smoke_test`
   fixture). Regenerate the gallery index.
   → [`references/build-and-ship.md`](references/build-and-ship.md)

9. **HERO PROMPT.** Ask the maintainer whether to refresh the hero collage —
   never automatic. If yes, ensure the style is in `build_hero.py` CATEGORIES
   and regenerate.
   → [`references/build-and-ship.md`](references/build-and-ship.md)

10. **GATES & SHIP.** Run `smoke_test.py --style <id>`, `lint_diagram_recipes.py`,
    `check_skill.py`, `icon_search.py --validate`; re-run the scrub checklist
    against the final diff; mark the run spec **Shipped**.
    → [`references/build-and-ship.md`](references/build-and-ship.md)

## Anti-patterns to refuse

- **Committing anything that identifies the source.** The whole skill is
  gated on §39; a leaked name is a Blocker, not a nit.
- **Minting a new style when the source matches an existing one.** Classify
  honestly; a restyle or primitives-only run touches far less.
- **Minting a validator `card_type`/`page_type`** for new primitives — load via
  `block_refs`; defer engine changes to `docs/backlog.md`.
- **`pip install`-ing a parser/renderer to open a format.** Use `deck_probe.py`
  + the sanctioned toolchain; read unsupported formats with the harness viewer.
- **Improvising PDF export** (WeasyPrint, `pdf2svg`, `img2pdf`, or Chrome's
  `page.pdf()` print path). Use `scripts/build_pdf.py` — Puppeteer screenshot +
  Pillow — the only path that is **pixel-1:1 with the HTML** and adds no dep.
- **Tracing icons.** Redraw the *idea*; never byte-copy a source glyph.
- **Referencing icons via `url()`/`<img>`** — inline the `<svg>` verbatim.
- **Auto-refreshing the hero collage.** It is a maintainer prompt.
- **Declaring done before the gates + the final scrub pass are green.**
