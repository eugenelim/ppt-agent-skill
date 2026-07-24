# Makefile for ppt-agent-skill mermaid renderer test targets.
#
# Parity targets run browser-free and complete in under 60 seconds on a
# standard CI worker. Browser targets require `playwright install chromium`.

.PHONY: parity-fast parity-browser help

## parity-fast: Run browser-free parity checks (AC1 fast job).
##   Covers: parser, semantic, FinalizedLayout validation, determinism,
##   geometry invariants, node overlap, containment, boundary-endpoint,
##   route-obstacle, marker/cardinality, backend metadata, import boundaries.
parity-fast:
	python3 -m pytest tests/ -m parity_fast --timeout=60 -q

## parity-browser: Run pinned browser/reference suite (AC2, sequential).
##   Requires: playwright install chromium
##   --workers=1 prevents unsafe parallel xdist mode for browser tests.
parity-browser:
	python3 -m pytest --run-browser tests/ -m browser -p no:xdist -q

help:
	@grep -E '^## ' Makefile | sed 's/^## //'
