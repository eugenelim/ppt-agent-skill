# Spec: fragment-to-slide-assembler

Mode: light

- **Status:** Implementing
- **Owner:** eugenelim

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

A standalone CLI (`scripts/assemble_diagram_slide.py`) that takes either a
pre-rendered HTML/SVG fragment or a `.mmd` source file and assembles it into
a single presentation-ready HTML slide, with optional title, annotation, and
style overrides. No new modules or abstraction layers — single file only.

## Acceptance criteria

1. `--fragment PATH` loads a pre-rendered fragment; `--source PATH` renders a
   `.mmd` file via `_dispatch`; providing both or neither is an error.
2. `--style PATH` loads `css_variables` from a JSON file and passes the dict
   to `render_page(..., theme=css_variables)`; omitting `--style` uses adaptive
   theme (`theme=None`).
3. `--title TEXT` inserts `<h1 class="slide-title">TEXT</h1>` above the diagram.
4. `--annotation TEXT` inserts `<p class="slide-annotation">TEXT</p>` below the diagram.
5. When title or annotation is present, minimal CSS for those classes (inheriting
   CSS vars) is injected as a `<style>` block in the fragment.
6. Output HTML begins with `<!-- dims: WxH -->` where W and H are the integer
   width and height from the SVG `viewBox`, or `0x0` if not found.
7. `--output PATH` writes the file; no `--output` writes to stdout.
8. `--width INT` (default 1200) passes the width hint to `_dispatch`.

## Task list

- [x] Create `docs/specs/fragment-to-slide-assembler/spec.md` (this file)
- [ ] Implement `scripts/assemble_diagram_slide.py`
- [ ] Add `tests/test_assemble_diagram_slide.py` with unit tests covering all ACs
- [ ] All tests pass via `python3 -m pytest tests/test_assemble_diagram_slide.py`
- [ ] End-to-end smoke: `--source tests/fixtures/flowchart-diamond-branch.mmd --title "Test" --annotation "Caption"`
