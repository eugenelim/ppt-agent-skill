# Spec: planning.json schema compliance

Mode: light (no risk trigger fired — docs + a self-contained test harness; no
security boundary, no structural/public-code interface, no new runtime dep,
nothing destructive). Spec + plan pre-approved by the user.

- **Status:** Shipped

## Objective

Make the Step 4 page-planning skill *aware of the full `planning_validator.py`
schema* so per-page planning subagents emit **zero-ERROR** `planning.json` on
the first pass, instead of burning tokens in validator→fix→re-validate loops.
The validator is the single source of truth; the playbook is the contract the
planning subagent reads (`tpl-page-planning.md` injects it verbatim as
`{{PLAYBOOK}}`).

**Two layers deliver this.** (1) *Awareness* — the playbook documents every
error class so a hand-authoring model gets it right. (2) *Structure-by-
construction* — a deterministic assembler (`scripts/assemble_planning.py`) lets
the subagent emit only judgment fields and fills all mechanical scaffolding from
the validator's own constants, so the ~55 per-page error classes become
unreachable (mechanical ones eliminated, judgment ones fail-fast as a single
`AssemblyError` naming the field). The assembler is the **default path**;
hand-authoring is the documented fallback for pages the payload contract can't
express. This is the skill-side analogue of structured outputs: it shrinks what
the model is trusted to type rather than relying on constrained decoding (which
a skill running in the harness doesn't get, and which couldn't enforce the
cross-field rules anyway).

## What "schema compliance" means (the definition this spec ratifies)

A payload is **compliant** iff `scripts/planning_validator.py` accepts it with
**zero ERRORs** (WARNs are allowed) under the current schema constants. That
decomposes into nine invariant categories, which together cover all 58
`result.error(...)` sites in the validator:

1. **Structural presence** — required top-level fields; `cards[]` non-empty;
   `density_contract` with all 9 fields; `director_command` / `decoration_hints`
   / `resources` / `workflow_metadata` objects; `source_guidance` on content.
2. **Enum conformance** — every constrained field draws from its closed set:
   `page_type`, `narrative_archetype`, `density_label`, `deck_bias`,
   `image_policy`, `decoration_budget`, `overflow_strategy`, content
   `layout_hint`, card `role` / `card_type` / `card_style`, `chart.chart_type`,
   `image.usage`, `image.placement`.
3. **Type conformance** — `body` is `list[str]`; `data_points` is `list[obj]`;
   `slide_number` int; `visual_weight` int in **[1,9]**; `content_budget` dict;
   `density_contract` numeric fields positive ints.
4. **Content sufficiency** — every card carries a content signal
   (body | items | data_points | chart | image.needed); no skeleton
   (headline-only) cards; no empty cards.
5. **Budget / density coherence** — cards ≤ `max_cards`; charts ≤ `max_charts`;
   `content_budget.body_max_lines` ≤ `max_lines_per_card`; `density_label`
   within `[page_lower_bound, page_upper_bound]`; `deck_bias` floors; dashboard
   constraints (content-only, `mixed-grid`/`t-shape`, `decorate_only`).
6. **Card-composition invariants** — exactly one `anchor` card; a content page
   with ≥2 cards uses ≥2 distinct `card_style`s.
7. **Resource resolvability** — `page_template` and every `*_ref` resolve to a
   real file under `references/` (`card_type`/`chart_type` enum values are NOT
   file stems).
8. **Image-contract coherence** — `needed=true` ⇒ usage/placement/
   content_description/source_hint set + valid enums; `needed=false` ⇒ those
   null; `image_policy` gates.
9. **Cross-page invariants** (deck-level; a scope-gated per-page agent's only
   levers are a correct `narrative_archetype` and faithful density) — unique
   `slide_number`s; no 3 consecutive `high`/`dashboard` unless
   `reference_runbook`; a `dashboard` page needs non-dashboard neighbors.

## Acceptance Criteria

- [x] AC1 — Every one of the 58 validator ERROR sites is mapped to one of the 9
  categories, and each error *class* has a triggering fixture in the harness
  that makes the validator fire (proves the failure surface is fully known). A
  coverage tripwire asserts `len(ERROR_CLASSES) == count(result.error() sites)`.
- [x] AC2 — A golden reference deck (multi-page, exercising content + cover +
  dashboard + reference pages) validates with **zero ERRORs**.
- [x] AC3 — Every error class maps to a documented anchor in the playbook; the
  harness asserts the anchor text is present (proves the skill is *aware*, and
  guards against future guidance deletion).
- [x] AC4 — The two reference-material defects are fixed: `visual_weight`
  documented as **1-9** (not 1-10); the copy-paste card skeleton no longer
  hardcodes `body_max_lines:5` in a way that errors on non-`medium` pages.
- [x] AC5 — Newly-documented gaps are closed in the playbook: `image.usage` /
  `image.placement` enums; full `chart_type` enum; "exactly one anchor";
  "≥2 card_styles on multi-card content pages"; dashboard neighbor-transition.
- [x] AC6 — The harness runs green via `pytest tests/` and is wired into CI.
- [x] AC7 — `scripts/assemble_planning.py` assembles a validated `planning.json`
  from a minimal judgment-only payload, importing the validator's constants (no
  drift), auto-capping/filling mechanical fields, dropping unresolvable refs
  (including per-card `resource_ref`), and self-validating; an AssemblyError-free
  payload can never yield a **per-page** validator ERROR (cross-page category 9
  is deck-level and out of scope), and judgment errors fail fast with the field
  named. Covered by `tests/test_assemble_planning.py`.
- [x] AC8 — The assembler is wired into the planning prompt/playbook as the
  default generation path, with hand-authoring preserved as an explicit fallback.

## Boundaries (what this does NOT change)

- The validator's rules/constants are **not** changed — it is the oracle. If the
  harness disagrees with the validator, the harness/docs are wrong, not it.
- No change to the orchestration flow, other Step 4 stages, or HTML generation.
- Cross-page invariants (category 9) are documented as deck-level; this spec
  does not add cross-page coordination to the per-page agent (out of scope,
  blocked by the ASI03 scope gate).

## Testing strategy

Goal-based + golden-fixture. `tests/test_planning_schema_compliance.py` drives
`planning_validator` directly from a single table
`ERROR_CLASSES = [(id, category, mutate(base), expected_error_substr,
[doc_anchor_substrs])]`. One table proves three things per class: the validator
fires (AC1), and the playbook documents it (AC3). A separate golden deck proves
AC2. Run: `pytest tests/test_planning_schema_compliance.py -q`.

## Assumptions

- The validator's `VALID_*` sets and `DENSITY_DEFAULTS` are the authoritative
  enum/budget source — the harness imports them rather than re-listing, so it
  can never drift from the validator.
- Playbook anchor checks are substring/keyword based (intentionally coarse):
  they guard "the guidance still exists", not its exact wording.
