# Adversarial review 2 — pre-EXECUTE spec/plan review (second pass)

## Blockers

**1. `_NODE_CSS` and `_WRAP_CHARS` unassigned.** `_WRAP_CHARS` at line 812 must go in
`_constants.py` with `_wrap_label`; `_NODE_CSS` at line 802 must go in `_renderer.py`.
Both were missing from all task ranges. Fix: T2 range extended to include `_WRAP_CHARS`;
T6 range starts at line 802 to include `_NODE_CSS`.

## Concerns

**2. T7 dead alias.** `_node_render_h as _nh` imported from `_renderer` after already being
imported from `_constants`. Fix: dropped.

## Nits

**3. Stale prose references.** Comments/error strings in smoke_test.py and
diagram_render_check.py still name `mermaid_layout.py`. Optional cleanup in T10.

## Resolution

All blockers and concerns addressed in spec/plan v3. DAG acyclicity confirmed.
