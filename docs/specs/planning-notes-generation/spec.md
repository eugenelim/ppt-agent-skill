# Spec: planning-notes-generation

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** none
- **Brief:** none
- **Discovery:** none
- **Contract:** none
- **Shape:** service

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

At Step 4.5 (proof worksheet), the planning skill derives speaker notes from
each slide's structured planning data and writes them to `<deck-slug>-notes.json`
at the deck root (one level up from `planning/`). A presenter reads these notes
in the worksheet before any LLM render cost is incurred, rather than receiving
an empty stub after rendering. Notes capture: what question this slide answers,
what to say to bridge from the previous slide, and the key point the audience
must leave with.

`proof_worksheet.build()` gains one sanctioned write outside `runtime/proof/`:
the notes.json at `deck_dir / f"{deck_dir.name}-notes.json"`. This is the same
path `html_packager.py` uses when it writes its empty stub — `build()` pre-populates
it so the packager finds content rather than generating a blank template.

## Boundaries

### Always do

- Derive notes text deterministically from planning fields only — no LLM call,
  no network, no randomness.
- Use the existing `schema_version: "1"` notes.json format (matching
  `html_packager.build_notes_stub()`).
- Skip writing the notes.json if the file already exists at the target path
  (the user may have refined it manually).
- HTML-escape notes text in any context where it flows into HTML.

### Ask first

- Any change to the `schema_version` or the top-level notes.json key structure.
- Any change to how `html_packager.py` writes or reads notes.json.

### Never do

- Add a new Python dependency.
- Call an LLM to generate notes text.
- Overwrite an existing `<deck-slug>-notes.json` file.
- Write notes.json to any path other than `deck_dir / f"{deck_dir.name}-notes.json"`.
- Modify `html_packager.py` (the downstream consumer is complete).

## Testing Strategy

- **TDD** for `derive_notes_entry()` and `build_notes_from_pages()` — pure
  functions with compressible invariants (structure of output dict, non-empty
  notes text when input has content). Tests in `tests/test_assemble_planning.py`.
- **Goal-based check** for `proof_worksheet.build()` writing notes.json — verify
  the file exists at the expected path after `build()` runs on a minimal deck
  fixture. Checked in `tests/test_proof_worksheet.py`.

## Acceptance Criteria

- [x] `derive_notes_entry(page, prev_page=None)` in `scripts/assemble_planning.py`
  returns a dict with keys `slide_number` (int), `title` (str), `notes` (str).
- [x] `notes` is a non-empty plain-text string (no Markdown, no HTML tags) when
  `page_goal` or anchor card `headline` is present in `page`.
- [x] `notes` covers at least two of: (a) what question the slide answers (from
  `page_goal`), (b) bridge from the previous slide (from `narrative_role`
  context), (c) key point for the audience (from anchor `headline` or
  `audience_takeaway`). A test asserts that at least two of these components
  are recognisably present in the derived text when all three source fields
  are populated.
- [x] `build_notes_from_pages(pages, deck_slug)` in `scripts/assemble_planning.py`
  returns `{"schema_version": "1", "_comment": <str>, "slides": <list>}` with
  one entry per page, in page order.
- [x] `proof_worksheet.build()` writes `deck_dir / f"{deck_dir.name}-notes.json"`
  when the file does not yet exist.
- [x] `proof_worksheet.build()` does not overwrite an existing notes.json file.
- [x] All existing `tests/test_assemble_planning.py` tests continue to pass
  unchanged.
- [x] `tests/test_proof_worksheet.py` is updated in the same PR: the write-set
  isolation check is amended to allow the one sanctioned deck-root write
  (`<deck-slug>-notes.json`), and three new notes.json checks are added (file
  written, correct schema, no overwrite).
- [x] `proof_worksheet.py` module docstring is updated to reflect that `build()`
  now writes one additional artifact (`<deck-slug>-notes.json`) at the deck root
  when the file is absent.
- [x] `docs/product/DESIGN.md` §Planning-time Speaker Notes source-field description
  is updated from "each slide's `body`, `headline`, and narrative role in the
  outline" to "each slide's `page_goal`, `narrative_role`, `audience_takeaway`,
  and anchor card `headline` in the planning JSON".

## Assumptions

- Technical: Python 3.8+ runtime; no new dependencies (source: docs/architecture/reference.md)
- Technical: notes.json schema is `{schema_version: "1", _comment, slides: [{slide_number, title, notes}]}` (source: probe — `build_notes_stub()` output)
- Technical: `html_packager.py` writes notes.json at `Path(output_path).parent / f"{deck_slug}-notes.json"` only when absent (source: html_packager.py:604-609)
- Technical: planning pages carry `page_goal`, `narrative_role`, `title`, `audience_takeaway`, `cards[].role == "anchor"`, `cards[].headline` (source: planning_validator.py)
- Technical: `proof_worksheet.build()` signature is `(deck_dir: Path, as_of: str | None = None) -> Path` (source: probe — inspect.signature)
- Technical: notes.json path convention: `deck_dir / f"{deck_dir.name}-notes.json"` matches `html_packager.py` derivation where `deck_slug = slides_dir.parent.name` (source: html_packager.py:563,604)
- Process: spec-driven development; CONVENTIONS.md governs spec metadata (source: docs/CONVENTIONS.md)
