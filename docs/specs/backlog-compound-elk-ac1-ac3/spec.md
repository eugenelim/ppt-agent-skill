# Spec: Compound ELK inner-direction fix (AC1–AC3)

Mode: light (no risk trigger fired)

**Status:** Shipped

## Objective

Fix two bugs in `tests/test_compound_layout.py`:

1. The `requires_elk` pytest mark is defined as `pytest.mark.skipif(...)`, which creates a `skipif` mark — so `-m requires_elk` deselects all tests. Replace it with a proper named mark registered in `conftest.py`.

2. ELK compound layout ignores per-group `direction` (uses `INCLUDE_CHILDREN` with the outer direction for all nodes). Four tests fail as a result. Fix by calling `_recursive_group_layout` as a post-processing step on the ELK path when any group has a different inner direction.

## Acceptance Criteria

- [x] AC1: `pytest tests/test_compound_layout.py -m requires_elk -v` selects and runs exactly 2 tests (both pass).
- [x] AC2: `pytest tests/test_compound_layout.py -v` shows 0 failures (24+ pass, some may skip).
- [x] AC3: `pytest tests/ -x --ignore=tests/test_snapshots.py` shows 0 failures (no regressions).

## Task list

1. Register `requires_elk` in `tests/conftest.py` + add skip logic for when ELK is absent.
2. Change `tests/test_compound_layout.py` line 35: `requires_elk = pytest.mark.requires_elk`.
3. Add inner-direction post-processing to the ELK path in `scripts/mermaid_render/layout/_pipeline.py`.
