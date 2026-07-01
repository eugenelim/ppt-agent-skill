# Spec: Planning content gate — reject skeleton cards

Mode: full (bug fix in a validation gate — a public/contract interface of the
Step-4 flow)

- **Status:** Shipped

## Objective

Close the hole that let a **skeleton `planning.json`** (cards carrying only
`card_type` + `headline`, no real content) pass the Step-4 planning gate. The
gate is `scripts/planning_validator.py`; today its per-card substance check
(`validate_card`) accepts a card as non-empty **if it merely has a headline**,
and it does **not** recognize `items` — the field real `list`/`data`/`diagram`/
`timeline`/`comparison` cards actually store content in. So a content-hollow
card validates clean and flows into HTML generation as a skeleton slide.

## Evidence (field run, Synchrony engagement)

A real deck's cards used content field `items`/`body`; a second, hand-built deck
had cards with only `card_type` + `headline` — the skeleton the user hit. The
current gate's `has_body/has_data/has_chart` check never inspects `items`, and a
headline alone satisfies the "not empty" test — so nothing flags the skeleton.
(Separately: those field decks were built off-pipeline and never ran this gate at
all — see Boundaries.)

## Change

In `planning_validator.validate_card`, replace the headline-satisfies-content
logic with a real substance check:

- Recognize `items` as content (add `has_items`), alongside the existing
  `body` / `data_points` / `chart`.
- Treat a card whose payload is a **needed image** (`image.needed == true`) as
  having content (covers `image_hero` and any image-driven card).
- A card with **only a headline and none of the above** is a **skeleton** →
  `error` (`skeleton card — only a headline, no body/items/data/chart/image
  content`). A card with neither headline nor content stays `empty card payload`.

No schema field is added or renamed; only the substance test changes.

**Content-signal grounding (why this set is complete, not a false-positive risk).**
The canonical planning schema (per `references/prompts/step4/tpl-page-html.md` and
the planning playbook) carries card content in exactly `body` / `data_points` /
`chart` / `image`; `items` is the lightweight/field-run schema's content field.
No card type — including `quote`, `data_highlight`, `tag_cloud`, `people`,
`process`, `matrix_chart` — stores content in a bespoke field the check misses:
a `quote`'s text lives in `body`, a `data_highlight`'s number in `data_points`/
`chart`. So **headline-only is intended-invalid for every card type**, and the
signal set `{body, items, data_points, chart, image.needed}` has no false-positive
surface across the 13 `VALID_CARD_TYPES`.

**`image.needed` × `image_policy=decorate_only`.** On a `decorate_only` page,
`image.needed=true` is independently rejected by the existing image-policy check,
so an image-only card there still errors (via that check) rather than passing as
non-skeleton — no card slips through. Image-as-content only meaningfully applies
where `image_policy != decorate_only`; no fixture exercises a decorate_only
image-only card.

## Acceptance Criteria

- [x] `validate_card` recognizes `items` as content and flags a headline-only
  card as a skeleton `error`.
- [x] A card with `items` (and no `body`) validates clean (no skeleton error) —
  the regression the old check missed.
- [x] A card whose only payload is a needed image is not flagged skeleton.
- [x] No skeleton false-positive on any fixture density: `smoke_skill` output
  contains **zero** `skeleton` errors, and its planning-validation errors are
  byte-identical to baseline (verified by stashing the change). NOTE:
  `smoke_skill` does **not** exit 0 on this machine — it has **pre-existing,
  unrelated** failures (`resources.chart_refs not found: kpi/metric-row`, missing
  `references/styles/runtime-style-rules.md`) present at baseline; those are not
  in scope here.
- [x] New test `scripts/test_planning_content_gate.py` covers skeleton-rejected,
  items-accepted, and image-accepted; `python3 -m py_compile` + the test pass;
  `python3 scripts/check_skill.py` exits 0.

## Boundaries

**Out of scope (surfaced, not fixed here):** the field runs produced planning on
a **lightweight schema** (`card_type`/`headline`/`items`/`body`, no
`card_id`/`role`/`card_style`/`content_budget`/`image`) via custom build scripts
that **bypass `planning_validator.py` entirely**. This fix hardens the gate; it
only bites when the gate is actually run. Making the pipeline *always* run the
gate (or hardening the lightweight/custom-build path) is a separate decision for
the user — flagged, not decided here.

**Never do:** add/rename a schema field; change any other card check.

## Testing Strategy

Verification mode: TDD.
1. `scripts/test_planning_content_gate.py`, driving the real `validate_page`
   entry with `refs_dir=None` (isolates the substance rule): baseline fixture
   clean; strip a `text` card's content → skeleton error; give that card `items`
   → skeleton error gone; card with `image.needed` → no skeleton error.
2. `python3 scripts/smoke_skill.py` (fixture pages of every density still clean).
3. `python3 scripts/check_skill.py` exits 0.
