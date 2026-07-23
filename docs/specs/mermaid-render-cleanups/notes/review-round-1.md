# Review round 1 — merged findings (adversarial + quality-engineer)

## Adversarial
**1. Dummy-chain final segment over-copies `source_marker`, flipping `bidir`.** `scripts/mermaid_render/layout/_layered.py:193`. Fix: copy only `target_marker`. → FIXED.
**2. No render-level arrowhead test for migrated state/req/arch writers.** `scripts/mermaid_render/layout/statediagram.py:443`. Fix: add render assertion. → FIXED (TestWriterMigrationRendersArrowheads).
**3. Label cap bounds node/group widths too, undocumented.** `scripts/mermaid_render/layout/_strategies.py:4610`. Fix: state in spec. → FIXED (AC5 note).
**4. Plan status stale.** `docs/specs/mermaid-render-cleanups/plan.md:3`. Fix: set Done. → FIXED.
**5. Census claim inaccurate (test default-reliance).** `docs/specs/mermaid-render-cleanups/spec.md:132`. Fix: correct assumption + plan list. → FIXED.

## Quality-engineer
**1. `_marker_kind` inline copies un-absorbed (weaker contract).** `scripts/mermaid_render/layout/_routing.py:811`. Fix: route through `_marker_kind`. → FIXED (routing + strategies bridge).
**2. `_marker_kind` raises on unknown string.** `scripts/mermaid_render/layout/_constants.py:243`. Fix: total coercion. → FIXED (try/except → NONE).
**3. Two derivation branches unexercised.** `tests/test_edge_marker_derivation.py`. Fix: add cases. → FIXED (bidir short-circuit + str-kind).
