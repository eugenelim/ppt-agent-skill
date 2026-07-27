# Plan: proof-notes-display

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

Add an optional `notes_by_slide: dict[int, str] | None = None` parameter to
`render_worksheet()` and thread it through to `render_page()`. In `render_page()`,
after the card table and before the `render_aux()` block, emit a `<div
class="facilitation">` section when a non-empty notes string exists for that slide.
Modify `build()` to load the notes.json and build `notes_by_slide` before calling
`render_worksheet()`. CSS for the facilitation section goes in
`assets/proof/proof.css`.

The riskiest part is adding a parameter to `render_worksheet()` without breaking
the direct calls in `tests/test_proof_worksheet.py` — handled by making it
optional with `None` default.

## Constraints

- Python 3.8+ stdlib only; no new dependencies.
- `render_worksheet()` positional parameter order (`deck_dir`, `pages`, `as_of`)
  is preserved; `notes_by_slide` is the fourth optional param.
- No empty placeholder row: facilitation section omitted entirely when notes absent.
- HTML-escape via existing `esc()` helper — no new escape logic.

## Construction tests

**Integration tests:** none beyond per-task tests.
**Manual verification:** run `python3 scripts/proof_worksheet.py <deck_dir>` on a
deck with a pre-populated notes.json; open the output HTML; confirm each slide
shows a Facilitation section.

## Design (LLD)

### Component / module decomposition

- `render_page(page, notes_by_slide=None)` — gains optional parameter; emits
  Facilitation `<div>` when notes present.
- `render_worksheet(deck_dir, pages, as_of, notes_by_slide=None)` — passes
  `notes_by_slide` through to each `render_page()` call.
- `build(deck_dir, as_of=None)` — after writing notes.json (planning-notes-generation),
  loads it back and builds `notes_by_slide: dict[int, str]`.
- `assets/proof/proof.css` — adds `.facilitation` CSS rule.

### State & control flow

```
build(deck_dir, as_of)
  → load_pages()
  → write notes.json if absent (planning-notes-generation)
  → load notes.json if present → notes_by_slide
  → render_worksheet(deck_dir, pages, as_of, notes_by_slide)
      → render_page(page, notes_by_slide)  # for each page
          → ... card table ...
          → if notes_by_slide.get(slide_no):
                <div class="facilitation">…</div>
          → render_aux(page)
```

### Behavior & rules

HTML structure for the Facilitation section (inserted after the card `<table>`,
before `render_aux()`):

```html
<div class="facilitation">
  <span class="fac-label">Facilitation</span>
  <p class="fac-notes">{{esc(notes_text)}}</p>
</div>
```

CSS (in `assets/proof/proof.css`):
```css
.facilitation { margin: 0.5rem 0 0; padding: 0.5rem 0.75rem; border-left: 3px solid #888; background: #f5f5f5; }
.fac-label { font-weight: 600; font-size: 0.75rem; text-transform: uppercase; color: #666; display: block; margin-bottom: 0.25rem; }
.fac-notes { margin: 0; font-size: 0.875rem; color: #333; white-space: pre-wrap; }
```

### Failure, edge cases & resilience

- notes.json absent → `notes_by_slide = None` → no Facilitation section; no error.
- notes.json malformed JSON → `build()` logs to stderr, proceeds without notes
  (same pattern as other best-effort reads in `build()`).
- Slide number in notes.json has no matching page → entry is silently ignored.
- `notes` value is empty string → treated as absent; no Facilitation section.

## Tasks

### T3: render_page() Facilitation section — tests green

**Depends on:** spec:planning-notes-generation/T2
**Touches:** scripts/proof_worksheet.py, assets/proof/proof.css, tests/test_proof_worksheet.py

**Tests:**
- `check("Facilitation section present when notes provided")` — call
  `render_page(page, notes_by_slide={1: "Test note."})` directly, confirm
  `class="facilitation"` and "Test note." in output.
- `check("Facilitation section absent when notes_by_slide is None")` — call
  `render_page(page, None)`, confirm `class="facilitation"` absent.
- `check("Facilitation section absent when slide has no entry")` — call
  `render_page(page, {99: "other"})` for slide 1, confirm absent.
- `check("notes text is HTML-escaped in Facilitation")` — call with notes
  containing `<script>`, confirm `&lt;script&gt;` (or similar) in output,
  no bare `<script>`.
- `check("render_worksheet notes_by_slide=None unchanged output")` — call
  `render_worksheet(deck, pages, None, None)`, confirm output matches
  existing determinism test result.

**Approach:**
1. Add `notes_by_slide: dict[int, str] | None = None` parameter to
   `render_page(page, notes_by_slide=None)`.
2. In `render_page()`, after the card table block and before
   `if idx == total - 1: body.append(render_aux(page))`, insert:
   ```python
   if idx == total - 1 and notes_by_slide:
       note = notes_by_slide.get(int(slide_no or 0), "")
       if note:
           body.append(
               '<div class="facilitation">'
               '<span class="fac-label">Facilitation</span>'
               f'<p class="fac-notes">{esc(note)}</p>'
               '</div>'
           )
   ```
3. Add `notes_by_slide: dict[int, str] | None = None` to `render_worksheet()`;
   pass it in each `render_page()` call.
4. Add `.facilitation`, `.fac-label`, `.fac-notes` rules to
   `assets/proof/proof.css`.
5. Add checks to `tests/test_proof_worksheet.py`.

**Done when:** `python3 tests/test_proof_worksheet.py` exits 0 with all new
Facilitation checks passing.

### T4: build() loads notes.json and passes to render_worksheet() — tests green

**Depends on:** T3, spec:planning-notes-generation/T2
**Touches:** scripts/proof_worksheet.py, tests/test_proof_worksheet.py

**Tests (goal-based):**
- `check("build() passes notes to worksheet when notes.json present")` — write
  a notes.json with one non-empty notes entry, call `build()`, read HTML,
  confirm `class="facilitation"` present.
- `check("build() omits Facilitation when notes.json absent")` — no notes.json,
  call `build()`, confirm `class="facilitation"` absent from HTML.
- `check("build() with notes.json is deterministic")` — call twice, confirm
  byte-identical.
- `check("build() degrades gracefully on malformed notes.json")` — write a
  notes.json with bad JSON (not valid JSON), call `build()`, capture stderr,
  confirm exit is clean (no uncaught exception), stderr contains a warning
  message, `class="facilitation"` absent from HTML.
- `check("build() handles malformed entries — skips bad, keeps good")` —
  write a notes.json with: one null `slide_number` entry, one non-dict entry
  (a bare string), and one valid entry; confirm build() succeeds and only the
  valid entry's Facilitation renders.

**Approach:**
1. In `build()`, after writing notes.json (planning-notes-generation T2), add:
   ```python
   notes_by_slide: dict[int, str] = {}
   if notes_path.exists():
       try:
           nj = json.loads(notes_path.read_text(encoding="utf-8"))
           for entry in (nj.get("slides") or []):
               try:
                   n = str(entry.get("notes") or "").strip()
                   if n:
                       notes_by_slide[int(entry["slide_number"])] = n
               except (TypeError, AttributeError, ValueError):
                   pass  # skip malformed entry; keep good ones
       except (ValueError, OSError) as exc:
           print(f"proof_worksheet: notes.json unreadable ({exc}); proceeding without notes", file=sys.stderr)
           notes_by_slide = {}
   out_path.write_text(render_worksheet(deck_dir, pages, as_of, notes_by_slide or None), encoding="utf-8")
   ```
2. Update module docstring: `build()` reads notes.json when present; output
   determinism depends on planning inputs and notes.json content.
3. Add checks to `tests/test_proof_worksheet.py`.

**Done when:** `python3 tests/test_proof_worksheet.py` exits 0 with all new
wiring checks passing.

## Rollout

Pure local-file read; no infra, no migration. The `notes_by_slide=None` default
keeps all existing `build()` and `render_worksheet()` callers unchanged.

## Risks

- Placing the Facilitation section after the card table and before `render_aux()`
  requires care around the `idx == total - 1` guard (spillover). Facilitation
  only renders on the last part of a multi-part slide — same placement as
  `render_aux()`. This is correct: notes apply to the whole slide, not each part.

## Changelog

- 2026-07-27: initial plan
