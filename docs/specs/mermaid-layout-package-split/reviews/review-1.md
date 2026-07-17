# Adversarial review 1 — pre-EXECUTE spec/plan review

## Blockers

**1. Import cycle `_renderer ⇄ _routing`.** `_node_render_h` called from `_route_edges` and `_assign_coordinates`; placing it in `_renderer.py` creates cycle. Fix: move measurement cluster to `_constants.py`.

**2. Missing path-string consumers.** `scripts/diagram_render_check.py:280` and `references/prompts/step4/tpl-page-orchestrator.md:56` hardcode `mermaid_layout.py`. Fix: add to AC-CONSUMERS + boundary.

**3. AC-SIZE contradiction.** AC stated "no exception needed" while spec also said `_strategies.py` ~1,250 lines is a tracked exception. Fix: reword AC-SIZE to acknowledge the exception.

## Concerns

**4. `test_diagram_qa.py` unlisted.** Coverage via AC-SMOKE. Fix: list as known consumer.

**5. CONVENTIONS.md not updated.** No task/AC. Fix: added to T10 + AC-CONVENTIONS.

**6. Status values wrong.** spec: `In progress` → `Approved`; plan: `In progress` → `Drafting`.

## Nits

**7. Plan T7 stream-of-consciousness.** Cleaned up.

**8. Wrong symbol names.** `_SHAPE_MAP` → `_SPEC_SHAPE_MAP`; `_CLASS_RE` → `_CSS_CLASS_RE`.

## Resolution

All blockers, concerns, and nits addressed in spec/plan v2.
