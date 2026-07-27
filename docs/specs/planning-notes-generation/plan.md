# Plan: planning-notes-generation

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

Add two pure functions to `scripts/assemble_planning.py`: `derive_notes_entry()`
(single-page notes text derivation) and `build_notes_from_pages()` (deck-level
assembly). Both are zero-LLM, zero-dependency, deterministic from planning
fields. Then modify `proof_worksheet.build()` to call `build_notes_from_pages()`
and write the notes.json at `deck_dir / f"{deck_dir.name}-notes.json"` when
absent.

The riskiest part is the `build()` signature change — it now has a side effect
(file write) beyond the worksheet HTML. The "only if absent" guard prevents
overwriting user-refined notes.

## Constraints

- Python 3.8+ stdlib only; no new dependencies (docs/architecture/reference.md).
- notes.json schema: `schema_version: "1"` — must match `html_packager.build_notes_stub()`.
- `html_packager.py` is read-only for this spec.

## Construction tests

**Integration tests:** none beyond per-task tests.
**Manual verification:** run `python3 scripts/proof_worksheet.py <deck_dir>` on a
deck with planning files; confirm `<deck_dir.name>-notes.json` appears with
non-empty `notes` strings and correct `slide_number` values.

## Design (LLD)

### Data & schema

Notes entry: `{"slide_number": int, "title": str, "notes": str}`. The `notes`
field is 1–3 plain-text sentences. No Markdown, no HTML. Traces to: AC1–AC4.

Notes file: `{"schema_version": "1", "_comment": "...", "slides": [...]}`.
Identical to `html_packager.build_notes_stub()` output schema; compatible with
`html_packager.build_preview()`'s `--notes` consumer. Traces to: AC4–AC5.

### Component / module decomposition

- `scripts/assemble_planning.py` — adds `derive_notes_entry()` and
  `build_notes_from_pages()`. These are public functions, importable by
  `proof_worksheet.py`. No changes to existing `assemble_page()`.
- `scripts/proof_worksheet.py` — `build()` gains one new side effect: writes
  the notes.json when absent. `render_worksheet()` is unchanged here (it
  changes in the `proof-notes-display` spec).

### Behavior & rules

`derive_notes_entry(page, prev_page=None)`:
1. Extract `slide_number` (int), `title` (str), `page_goal` (str), `narrative_role`
   (str), `audience_takeaway` (str) from page.
2. Find the anchor card's `headline` (first card with `role == "anchor"`).
3. Assemble notes text as 1–3 plain-text sentences:
   - Sentence 1: "This slide answers: {page_goal}." (when page_goal present).
   - Sentence 2: Bridge sentence — when prev_page, "Follows '{prev_title}'";
     when first slide, uses narrative_role to describe opening context.
   - Sentence 3: "Key point: {audience_takeaway or anchor_headline}."
     (when either present).
4. Return `{"slide_number": slide_number, "title": title, "notes": notes_text}`.

`build_notes_from_pages(pages, deck_slug)`:
1. Sort pages by `slide_number`.
2. Call `derive_notes_entry(page, prev_page)` for each, threading `prev_page`.
3. Return `{"schema_version": "1", "_comment": "...", "slides": [entries]}`.

`proof_worksheet.build()`:
1. Load pages (existing).
2. Compute notes_path = `deck_dir / f"{deck_dir.name}-notes.json"`.
3. If notes_path does not exist:
   a. Import `build_notes_from_pages` from `assemble_planning`.
   b. Call `build_notes_from_pages(pages, deck_dir.name)`.
   c. Write JSON to notes_path (utf-8).
4. Write worksheet HTML (existing).
5. Return out_path (existing).

### Failure, edge cases & resilience

- `page_goal`, `narrative_role`, `audience_takeaway`, `headline` may be absent,
  `None`, or `""` — all handled with `str(val or "")` fallback; notes text is
  built from whichever fields are present.
- `prev_page` is `None` for the first slide — bridge sentence is omitted or uses
  `narrative_role` as an opening description.
- If `pages` is empty, `build_notes_from_pages` returns a valid file with
  `slides: []`.
- If `build_notes_from_pages` raises during `build()`, log to stderr and proceed
  — worksheet HTML is always written; notes.json is best-effort.

## Tasks

### T1: derive_notes_entry() and build_notes_from_pages() — tests green

**Depends on:** none
**Touches:** scripts/assemble_planning.py, tests/test_assemble_planning.py, docs/product/DESIGN.md

**Tests:**
- `test_derive_notes_entry_first_slide`: first slide (prev_page=None), full
  fields — notes is non-empty, contains page_goal substring.
- `test_derive_notes_entry_subsequent_slide`: page with prev_page — notes
  contains prev slide title reference.
- `test_derive_notes_entry_minimal_fields`: page with only anchor headline
  (no page_goal, no narrative_role) — notes is non-empty.
- `test_derive_notes_entry_empty_page`: page with no goal, no headline — notes
  may be empty string (not an error).
- `test_derive_notes_entry_no_html_tags`: notes text contains no HTML tag patterns
  (no `<` followed by a letter or `/`). A valid page_goal like "revenue < 5%" must
  not trip this check — the test looks for `<[a-zA-Z]` and `</`, not bare `<`.
- `test_build_notes_from_pages_schema`: returns dict with `schema_version == "1"`,
  `"slides"` list, `"_comment"` string.
- `test_build_notes_from_pages_count`: N pages → N slides entries, each with
  `slide_number`, `title`, `notes` keys.
- `test_build_notes_from_pages_order`: pages passed in reverse order — output
  slides are sorted by `slide_number`.
- `test_derive_notes_entry_covers_two_components`: page with all three source
  fields populated (`page_goal`, `narrative_role`, prev_page, anchor headline) —
  derived notes contains the page_goal substring AND either the prev slide title
  or the anchor headline substring (≥2 of 3 components present).

**Approach:**
1. Add `derive_notes_entry(page: dict, prev_page: dict | None = None) -> dict`
   to `assemble_planning.py` after `assemble_page()`.
2. Add `build_notes_from_pages(pages: list[dict], deck_slug: str) -> dict`
   to `assemble_planning.py` after `derive_notes_entry()`.
3. Add pytest tests to `tests/test_assemble_planning.py`.
4. In `docs/product/DESIGN.md` §Planning-time Speaker Notes, update the source-field
   description from "each slide's `body`, `headline`, and narrative role in the
   outline" to "each slide's `page_goal`, `narrative_role`, `audience_takeaway`,
   and anchor card `headline` in the planning JSON".

**Done when:** `python3 -m pytest tests/test_assemble_planning.py -x -q` exits 0
with all new tests passing.

### T2: proof_worksheet.build() writes notes.json — tests green

**Depends on:** T1
**Touches:** scripts/proof_worksheet.py, tests/test_proof_worksheet.py

**Tests (goal-based):**
- `check("build() writes notes.json alongside worksheet", ...)`
  — after `PW.build(deck)`, `(deck / f"{deck.name}-notes.json").is_file()` is True.
- `check("notes.json has correct schema", ...)` — schema_version == "1", slides
  list length matches page count.
- `check("build() does not overwrite existing notes.json", ...)` — pre-write a
  stub with sentinel content, call build(), confirm sentinel content unchanged.
- `check("isolation: notes.json is outside runtime/proof/ but is the one sanctioned exception", ...)`
  — the isolation check is updated to allow exactly the `<deck-slug>-notes.json`
  write at deck root, all other new files still under `runtime/proof/`.

**Approach:**
1. In `proof_worksheet.py`, import `build_notes_from_pages` from `assemble_planning`
   (inside the function to avoid circular import risk; use a try/except to degrade
   gracefully if the import fails).
2. In `build()`, after `load_pages()`, compute `notes_path`; if absent, call
   `build_notes_from_pages(pages, deck_dir.name)` and write JSON.
3. Update the module docstring to state that `build()` writes one additional
   artifact at deck root: `<deck-slug>-notes.json` (when absent).
4. Update the isolation test in `tests/test_proof_worksheet.py` to allow the
   `<deck-slug>-notes.json` file at deck root (amend `every new file is under
   runtime/proof/` to permit this one exception).
5. Add the three notes.json checks to `tests/test_proof_worksheet.py`'s `main()`.

**Done when:** `python3 tests/test_proof_worksheet.py` exits 0 with all new
checks passing, including the three notes.json checks.

## Rollout

Pure local-file side effect; no infra, no migration, no deployment sequencing.
Reversible: delete the generated notes.json to reset to the html_packager stub
behavior. The `build()` "write if absent" guard makes this idempotent.

## Risks

- `build_notes_from_pages` import in `proof_worksheet.py` creates a cross-script
  dependency. Both live in `scripts/`; no circular dependency (proof_worksheet
  doesn't import from itself). Mitigation: lazy import inside `build()` with a
  try/except that degrades to skipping notes.json write.

## Changelog

- 2026-07-27: initial plan
