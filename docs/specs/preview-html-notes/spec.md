# Spec: preview-html-notes

**Mode:** full (public-interface change — `build_preview()` signature, `main()` CLI; new output file `notes.json`)

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** iframe `sandbox=""` must be preserved; no new Python dependencies; notes panel must live in the outer wrapper (not inside iframes)
- **Contract:** `scripts/html_packager.py::build_preview()`, `scripts/html_packager.py::main()`, `scripts/html_packager.py::build_notes_stub()`
- **Shape:** feature

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Add speaker notes as a separate deliverable artifact alongside the preview HTML:

1. **`notes.json` stub** — auto-generated as `<deck-slug>-notes.json` in the deck output directory when the file does not already exist; presenters fill it in.
2. **`--notes PATH`** — CLI flag to embed a filled-in notes.json into the HTML; notes are stored as `data-notes="..."` on each iframe.
3. **Notes panel** — a dismissible overlay panel inside the stage div that shows the active slide's notes; toggled by pressing `N` or clicking the "Notes" button in the controls bar.

## Acceptance Criteria

- [x] AC1 — **`notes.json` stub generation.** `main()` writes `<deck-slug>-notes.json` in the same directory as the output HTML (`Path(output_path).parent`), if the file does not already exist. The stub has the shape:
  ```json
  {
    "schema_version": "1",
    "_comment": "Fill in facilitation notes here; pass --notes to html_packager.py to embed them.",
    "slides": [
      { "slide_number": 1, "title": "Introduction", "notes": "" },
      ...
    ]
  }
  ```
  `title` is derived from `_slide_title(content, i+1)` for each slide. Existing files are never overwritten (idempotent — second run must leave the file byte-identical).

- [x] AC2 — **`--notes PATH` CLI flag.** `main()` accepts `--notes PATH`; reads the JSON; validates that `schema_version == "1"` and `slides` is a list; exits non-zero with a clear message if the file is missing, the JSON is malformed, or `schema_version != "1"`. The loaded notes list is passed to `build_preview()` as the `notes` parameter.

- [x] AC3 — **`data-notes` attributes.** `build_preview(slides, title, notes=None)` accepts an optional `notes` parameter (a `list[dict]` from notes.json, or `None`). For each iframe, if a matching entry exists (matched by 1-indexed `slide_number`) and its `notes` text is non-empty after stripping whitespace, inject `data-notes="<html-escaped>"` on the iframe using `html.escape(..., quote=True)`. Otherwise omit the attribute. Per-entry shape is validated defensively: non-dict entries are skipped; missing `slide_number` or non-numeric values skip the entry (no crash); missing `notes` key or non-string value uses `""` as the fallback.

  HTML-escaping is the XSS defense — it must be tested with special chars:
  `notes = "line1\n<b>\"&x\"</b>"` must produce
  `data-notes="line1\n&lt;b&gt;&quot;&amp;x&quot;&lt;/b&gt;"` in the output.

- [x] AC4 — **Notes panel HTML.** The output HTML contains a `<div id="notesPanel" class="notes-panel">` element placed as the last child **inside** `<div id="stage">` (not a sibling of it). This ensures `position: absolute` resolves against the stage. Properties:
  - `position: absolute; bottom: 0; right: 0`
  - `min-width: 320px; max-width: 40%; max-height: 60%; overflow-y: auto`
  - Dark semi-transparent background (`rgba(15, 15, 15, 0.92)`), white text, `font-size: 13px; line-height: 1.5`
  - Hidden by default; shown/hidden via `.notes-panel.open { display: block }`
  - `z-index: 10` — layers above iframes (`position: absolute`) but below the jump modal (`z-index: 40`)
  - The stage already has `position: relative` — confirm it is retained.

- [x] AC5 — **Notes panel JS behaviour.** The JS wrapper:
  - `updateNotes(i)` reads `frames[i].dataset.notes` (or `""` if absent) and sets `notesPanel.textContent`; if the text is empty, also removes `.open` from `notesPanel`.
  - `updateNotes(i)` is called at the end of `show(i)`.
  - `toggleNotes()`: reads notes for `cur` frame; if empty, returns without action; otherwise calls `notesPanel.classList.toggle('open')`.
  - `N` key calls `toggleNotes()`; "Notes" button click also calls `toggleNotes()`.

- [x] AC6 — **"Notes" button in controls bar.** A `<button class="utility-btn" id="notesBtn">Notes</button>` is added to the right nav-group in the controls bar (after the counter).

- [x] AC7 — **`N` key binding in DESIGN.md.** The keyboard shortcuts table `N` row annotation changes from `[planned: preview-html-notes]` to `[current]`. The Speaker Notes section and notes panel UX subsection advance from `[planned: preview-html-notes]` to `[current]`. Controls layout right-group comment updated to show Notes button as `[current]`.

- [x] AC8 — **iframe sandbox invariant preserved.** Every iframe retains exactly `sandbox=""`. `allow-same-origin` does not appear in the output.

- [x] AC9 — **Tests pass.** All existing `test_html_packager.py` checks pass. New assertions added:
  ```python
  # AC3: data-notes injection and HTML escaping
  assert 'data-notes="Welcome everyone."' in html_with_notes
  assert 'data-notes=' not in html_no_notes
  # Escaping: <b>"&x"</b> must be escaped
  assert '&lt;b&gt;' in html_special
  assert '<b>' not in html_special  # raw < absent from data-notes context

  # AC4: notes panel inside stage
  assert 'id="notesPanel"' in html
  stage_idx = html.index('id="stage"')
  panel_idx = html.index('id="notesPanel"')
  controls_idx = html.index('class="controls"')
  assert stage_idx < panel_idx                  # panel after stage open tag
  # Panel must be before stage close + controls open (ensures nesting)
  assert panel_idx < html.index('</div>\n<div class="controls"')  # panel inside stage

  # AC5/AC6: N key and Notes button
  assert "=== 'n'" in html or '=== "n"' in html
  assert 'id="notesBtn"' in html

  # AC8: sandbox invariant (existing test)
  assert 'sandbox=""' in html
  assert 'allow-same-origin' not in html
  ```

- [x] AC10 — **`build_notes_stub()` is a testable public function.** `html_packager.py` exports `build_notes_stub(slides: list[str]) -> dict` so tests can call it directly. The returned dict matches the notes.json schema.

## Testing Strategy

Verification mode: TDD for unit tests; goal-based checks for CLI behaviour.

**TDD tests** (add to `tests/test_html_packager.py`):
- `build_notes_stub()` returns correct schema with correct per-slide titles
- `build_preview()` with notes: `data-notes` injected, panel present, N key present
- `build_preview()` without notes: no `data-notes` attribute
- HTML-escaping of special chars in notes
- Panel is inside the stage div

**Goal-based CLI checks (all 27 recorded PASS):**
1. ✅ First run: HTML output created, notes stub created (`<deck-slug>-notes.json`)
2. ✅ Stub schema_version=1, slides list, 2 entries, correct titles, correct `_comment` literal
3. ✅ Idempotency: second run leaves stub byte-identical, no "Created notes stub" in stdout
4. ✅ `--notes /tmp/missing.json` → exit non-zero, stderr "not found"
5. ✅ `--notes <malformed.json>` → exit non-zero, stderr "malformed"
6. ✅ `--notes <schema_version=2.json>` → exit non-zero
7. ✅ `--notes <slides={}.json>` → exit non-zero
8. ✅ `--notes <[...].json>` (array, not object) → exit non-zero, stderr "object"
9. ✅ `--notes <valid-notes.json>` → exit 0, `data-notes="Welcome text"` in HTML
10. ✅ JS: `updateNotes`, `toggleNotes`, `notesPanel.textContent`, N key binding — all present in generated HTML

## Boundaries

**In scope:** `scripts/html_packager.py`; `tests/test_html_packager.py`; `docs/product/DESIGN.md`.

**Out of scope:** Print/PDF (D4), any slide HTML files, AGENTS.md, planning-time JSON.

**Never do:**
- Add `allow-same-origin` to the iframe sandbox
- Add a new Python import that requires a `requirements.txt` change
- Read from or write to notes inside iframe content (all notes panel logic lives in outer wrapper)
- Overwrite an existing notes.json
- Change the `title` default in `build_preview()` — keep `"PPT Preview"`

**Ask first:**
- If notes text contains Markdown and the design wants it rendered as HTML rather than plain text.

## Assumptions

1. Notes are plain text (not Markdown) for this deliverable.
2. `slide_number` in notes.json is 1-indexed and matched exactly — no fuzzy title matching.
3. The `--notes` flag is optional; omitting it produces a preview HTML with no notes panel content (panel element still present but always hidden).
4. `deck_slug` is available in `main()` as `slides_dir.parent.name`; the notes stub path is `Path(output_path).parent / f"{deck_slug}-notes.json"` — same directory as the output HTML. When `-o /tmp/t.html` is used, the stub lands in `/tmp/`; on the default path both are in `slides_dir.parent`.
