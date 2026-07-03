# Plan: slide-intent-review

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

Add one self-contained, deterministic script — `scripts/proof_worksheet.py` —
that reads a deck's `planning/*.json` (+ `outline.json`) and renders a one-up
**slide-intent worksheet** HTML with a pinned deck-overview index, styled by an
owned `assets/proof/proof.css` (a muted `schematic_blueprint` derivative). It is a
pure serializer: field mapping (SHOWN / meta / collapsed / omitted), a
source-presence status column, a density over-budget flag, and priority-ordered
spillover. No LLM, no network, no writes outside `OUTPUT_DIR/runtime/proof/`. The
riskiest part is **isolation** (nothing may leak into the style/gallery surface)
and **spillover determinism** — both are pinned by fixture tests. Finally,
`SKILL.md` gains a Step 4.5 consent gate documenting the Review-vs-Render choice;
this is a docs change that reuses the existing structured-UI mechanism without
joining the Step-0 interview-anchor contract.

## Constraints

- `AGENTS.md` — keep the diff minimal; no new top-level dependency; touch only
  what the feature requires.
- The existing planning gate (`planning_validator.py`) and its `page_type` /
  `card_type` enums are read-only inputs — the proof consumes them, changes
  nothing.
- `docs/architecture/reference.md` / `overview.md` — `workflow_versions.py` is the
  single source of truth for version constants; the proof path leaves it untouched.

## Construction tests

**Integration tests:** the render's write-set is a subset of `runtime/proof/`, and
`gallery.py collect_all_styles()` returns the known style id-set (isolation);
`check_skill.py` exits 0.
**Manual verification:** render the worksheet for a real deck under
`ppt-output/`, open it, confirm stale facts and un-sourced claims are visible and
the density `⚠` fires on an at-budget page.

## Design (LLD)

Stack: Python 3 + Jinja2 3.1.6 (already present), rendered as static HTML;
consumes the `planning`/`outline` JSON contracts owned by
`scripts/planning_validator.py` and `workflow_versions.py`.

### Design decisions
- **Deterministic serializer, not a style.** The worksheet renders the *plan*
  (known, fixed data), never a mock of the bespoke slide (decided at render time)
  — so it is coherent to render deterministically with zero LLM. Traces to: AC1.
- **Owned, frozen chrome derived from `schematic_blueprint`.** Hand-authored
  `proof.css` rather than importing the live style JSON, so editing a deck style
  can't drift the review chrome, and the gallery never sees it. Rejected: reusing
  the style JSON (couples + pollutes the gallery). Traces to: AC8, AC9.
- **Template inline in the script** (mirrors `gallery.py`'s self-contained
  precedent). Traces to: AC1.
- **Source status = presence only, derived solely from `data_points`.** The marker
  fires only on a non-empty `data_points` (● if any entry is a dict with a truthy
  `source`, else ○; no marker when empty). The required page-level `source_guidance`
  is shown separately in the meta. No date field exists, so no freshness verdict.
  Traces to: AC4.
- **As-of date is an explicit arg, never `date.today()`.** Preserves the
  byte-identical determinism AC. Traces to: AC1, AC9.

### Data & schema
- **Reads:** `planning/*.json` (page: `slide_number`, `page_type`,
  `narrative_role`, `narrative_archetype`, `title`, `page_goal`,
  `audience_takeaway` (optional), `density_label`, `density_contract.max_cards`,
  `density_contract.max_charts`, `layout_hint`, `source_guidance` (required on
  content pages), `cards[]`; card: `role`, `card_type`, `card_style`,
  `argument_role`, `headline`, `body`, `items`, `data_points` (strings **or**
  dicts; a `source` sub-key is optional/unvalidated), `chart`, `image`);
  `outline.json` `cover.title`.
- **Inputs (CLI):** optional `--as-of DATE` (explicit; no clock read); optional
  `--pdf`. `narrative_archetype` for the deck header is taken from the
  lowest-`slide_number` page.
- **Writes:** `OUTPUT_DIR/runtime/proof/<deck-slug>-intent.html` only.
- **No schema change; no `workflow_metadata`; no version bump.** Traces to: AC11.

### Component / module decomposition
- New: `scripts/proof_worksheet.py` (serializer + inline template + CLI),
  `assets/proof/proof.css` (owned chrome), `scripts/test_proof_worksheet.py`.
- Reused: `.gitignore` `ppt-output/*` for scratch isolation; deck-slug =
  `OUTPUT_DIR` folder name.
- Doc: `SKILL.md` Step 4.5 section; `references/cli-cheatsheet.md` entry.

### Failure, edge cases & resilience
- Missing `outline.json` / `cover.title` → deck title falls back to deck-slug.
- Missing optional `audience_takeaway` → takeaway falls back to the guaranteed
  `page_goal`.
- A page with `workflow_metadata` stamped at an old version → the proof ignores
  it (read-only); no gate impact (matches the "old planning.json opens fine" AC).
- Oversized page → continuation card; content fields never dropped (matches the
  spillover AC).
- Plain-string `data_points`, or a data card with no `source` → `○` (un-sourced);
  a card with no data/claims → no marker (matches the source-status AC).
- `--as-of` omitted → header renders no date; clock never read.

### Dependencies & integration
- Optional: `build_pdf.py` / `html2png.py` (already present) can turn the
  worksheet HTML into a PDF contact sheet — an optional task, not required for v1.

## Tasks

### T1: owned proof chrome `assets/proof/proof.css`

**Depends on:** none
**Touches:** assets/proof/proof.css

**Tests:**
- Goal-based: file exists at `assets/proof/proof.css`; contains no
  `schematic_blueprint` purple accent hex (`#a100ff`/`#6e00b0`); retains status
  colors (`--warn` amber, `--ok` green); carries no `style_id`; is not under
  `references/styles/`.

**Approach:**
- Hand-author a monochrome worksheet stylesheet from `schematic_blueprint`'s
  token language (white paper, hard black hairlines, mono field labels, black
  header bars, `Fraunces` italic accent, zero shadow/radius); drop the purple,
  keep amber/green as the source-status palette.

**Done when:** the goal-based checks pass and `gallery.py collect_all_styles`
count is unchanged.

### T2: serializer + one-up worksheet + pinned index (`scripts/proof_worksheet.py`)

**Depends on:** T1
**Touches:** scripts/proof_worksheet.py

**Tests:**
- TDD (`scripts/test_proof_worksheet.py`, fixture from
  `smoke_skill.build_content_page_fixture`): the SHOWN field set renders with
  correct placement; source status fires only on non-empty `data_points` — `●` when
  any entry is a dict with a truthy `source`, else `○`, and **no marker** for a card
  with empty/absent `data_points`. Because the shared builder only emits empty
  `data_points` (non-chart cards) or sourced dicts (chart cards), the `○` and
  plain-string cases use **locally-constructed card variants appended to the fixture
  page** (a source-less dict card and a string-`data_points` card). `source_guidance`
  renders in the meta; the meta strip shows `layout_hint`, `density_label`, and a `⚠`
  when `len(cards) == max_cards` or chart count `== max_charts`, where a chart is a
  dict with a non-empty string `chart_type` (stricter than the validator's
  any-string count); art-direction fields render collapsed; routing fields absent; deck
  title from `outline.cover.title` (and deck-slug fallback), per-card heading from
  `page.title`; `narrative_archetype` in the header from the lowest-`slide_number`
  page; takeaway falls back `audience_takeaway`→`page_goal`.
- TDD: two renders of the same input + args are byte-identical; card/field
  ordering comes only from `slide_number` and the explicit field list (a
  reserialized input with reordered keys renders identically); no LLM/network
  import path is reachable; with no `--as-of`, no date and no clock read.

**Approach:**
- Load pages via the same wrapped/single/bare acceptance `planning_validator`
  uses; sort by `slide_number`; iterate cards and fields by an explicit ordered
  list (never raw `dict`/`set` iteration); map each page/card through the
  SHOWN/meta/collapsed/omitted classification; emit one-up cards + a pinned index
  (`№`, `title`, `density`, flag count, jump link) into an inline Jinja template
  linking `assets/proof/proof.css`; write to
  `runtime/proof/<deck-slug>-intent.html`. Accept optional `--as-of` (rendered
  verbatim; no default clock read).

**Done when:** the fixture tests are green and the worksheet opens in a browser
with the SHOWN set, meta strip, status column, and index present.

### T3: priority-ordered spillover

**Depends on:** T2
**Touches:** scripts/proof_worksheet.py, scripts/test_proof_worksheet.py

**Tests:**
- TDD: an oversized fixture page produces a continuation card `№ · 2/2`; all
  content fields (headline/body/items/data/source) are present across the cards;
  art-direction fields are the first to collapse; output is deterministic.

**Approach:**
- Deterministic Python chunking by field priority (content never truncated;
  art-direction/metadata collapses first; overflow → continuation card). No CSS
  auto-pagination.

**Done when:** the spillover tests are green and no content field is ever dropped.

### T4: isolation + determinism guard tests

**Depends on:** T2, T3
**Touches:** scripts/test_proof_worksheet.py

**Verification-only:** this task adds no production code — isolation is a property
of T2's write path. The implementing task for the isolation AC is T2; T4 pins it.

**Tests:**
- Goal-based/integration: the render's write-set is a subset of `runtime/proof/`
  (nothing under `references/styles/`, `ppt-output/style-gallery/`, or `slides/`);
  `gallery.py collect_all_styles()` returns the known style id-set (asserted
  against the current inventory constant, not an unpinned before/after);
  `planning_validator` behavior unchanged.

**Approach:**
- Capture the write-set during a render into a temp `OUTPUT_DIR` and assert the
  subset; assert `collect_all_styles()` id-set equals the known inventory.

**Done when:** the isolation suite is green and `check_skill.py` exits 0.

### T5: SKILL.md Step 4.5 consent gate + docs

**Depends on:** T2
**Touches:** SKILL.md, references/cli-cheatsheet.md

**Tests:**
- Goal-based: `SKILL.md` contains a Step 4.5 section with the Review-vs-Render
  options, the exact warning text, the `grounding_mode` + size default heuristic,
  and the "once per deck / not in the Step-0 interview contract" notes;
  `cli-cheatsheet.md` documents `proof_worksheet.py`; `check_skill.py` exits 0.

**Approach:**
- Document the gate (structured-UI mechanism, text fallback) as a new Step 4.5
  between Step 4 and Step 5c; record the not-in-scope items (not a gallery/
  deliverable style; no auto staleness date; two-up considered-and-declined;
  HTML-title reuse deferred) and the read-only-worksheet rule.

**Done when:** the grep checks pass and `check_skill.py` is green.

### Deferred / optional — outside the AC-closing set

The tasks below trace to no Acceptance Criterion; the spec's "done" is closed by
T1–T5. They ship only if separately prioritized.

#### T6 (optional): PDF contact sheet

**Depends on:** T2
**Touches:** scripts/proof_worksheet.py

**Tests:**
- Goal-based: a `--pdf` flag routes the worksheet HTML through the existing
  `build_pdf.py`/`html2png.py` path to `runtime/proof/<deck-slug>-intent.pdf`.

**Approach:**
- Reuse the existing puppeteer→Pillow pipeline; no new dependency.

**Done when:** the flag produces a PDF under `runtime/proof/` and is off by
default.

## Rollout

- **Delivery:** additive and reversible — a new opt-in review step + one script +
  one CSS asset; removing them restores prior behavior. No data migration, no
  published artifact.
- **Infrastructure:** none.
- **External-system integration:** none.
- **Deployment sequencing:** T1 → T2 → T3 → T4; T5 (docs) after T2; T6 optional.

## Risks

- **Isolation regressions** — a future edit could place proof assets under
  `references/styles/`; the T4 guard test and the `Never do` boundary defend
  against it.
- **Content gate mistaken for a full-fidelity gate** — the worksheet reviews the
  *plan*, not render-time phrasing; SKILL.md states this known limitation so
  authors still eyeball the final render for wording.
- **Spillover over-truncation** — mitigated by the T3 invariant that content
  fields are never dropped.

## Changelog

- 2026-07-03: initial plan.
- 2026-07-03: implemented T1–T5 (T6 PDF deferred). Status → Done; spec → Shipped, all ACs met.
