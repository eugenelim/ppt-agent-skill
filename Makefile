# Makefile for ppt-agent-skill mermaid renderer test targets.
#
# Parity targets run browser-free and complete in under 60 seconds on a
# standard CI worker. Browser targets require `playwright install chromium`.

.PHONY: parity-fast parity-browser eight-case-ci help

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

## eight-case-ci: Run the eight-case parity gate (spec eight-case-parity-ci-and-cleanup).
##   Covers the 8 scoped fixtures across output × presentation × backend plus the
##   hard-failure-condition gate suite. ELK-required lanes need Node + elkjs:
##     npm install --prefix scripts/mermaid_render/layout
##   Without elkjs the ELK-required lanes skip cleanly. Writes structured
##   artifacts to test-artifacts/ (gitignored).
eight-case-ci:
	python3 -m pytest -m eight_case --timeout=120 -q

help:
	@grep -E '^## ' Makefile | sed 's/^## //'
