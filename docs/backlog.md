# Backlog — tombstone

All open items have migrated to [`workspace.toml`](../workspace.toml) `[backlog].open`.

This file is kept only so that `(deferred: <anchor>)` references in spec ACs
continue to resolve. Each heading below corresponds to a slug in `workspace.toml`.
The content lives there; edit it there.

Closed/shipped work remains in each spec's Changelog and
[`product/changelog.md`](product/changelog.md).

---

## sequence-renderer-correctness-pass

### seq-corr-box-unsupported-fixture

→ `workspace.toml` slug: `seq-corr-box-unsupported-fixture`

### seq-corr-create-destroy-fixture

→ `workspace.toml` slug: `seq-corr-create-destroy-fixture`

### seq-corr-single-participant-fragment-long-header

→ `workspace.toml` slug: `seq-corr-single-participant-fragment-long-header`

### seq-corr-height-hint-gallery-metadata

→ `workspace.toml` slug: `seq-corr-height-hint-gallery-metadata`

### seq-corr-mmdc-data-et-selectors

→ `workspace.toml` slug: `seq-corr-mmdc-data-et-selectors`

---

## diagram-consistency-system

→ `workspace.toml` slug: `diagram-consistency-system-chart-refs`

## reference-runbook-page-types

### smoke-skill-pre-existing-fixture-drift

→ `workspace.toml` slug: `smoke-skill-pre-existing-fixture-drift`

## owasp-llm-agentic-security

→ `workspace.toml` slug: `no-sandbox-container-isolation`

## render-visual-check-and-diagram-routing

→ `workspace.toml` slug: `render-gate-live-e2e-qa`

## mermaid-source-bridge

### mermaid-source-bridge-ac3-visual-qa

→ `workspace.toml` slug: `mermaid-source-bridge-ac3-visual-qa`

## fragment-to-slide-assembler

→ `workspace.toml` slug: `fragment-to-slide-assembler`

## mermaid-render-rearchitecture

### differential-parity-test

→ Absorbed into ini-002 item 13: `docs/specs/mermaid-parity-ci-and-maintainability-cleanup`

---

## seq-geometry-fix

### strategies-module-split

→ Absorbed into ini-002 item 13: `docs/specs/mermaid-parity-ci-and-maintainability-cleanup`

### seq-variable-height-rows-playwright

→ `workspace.toml` slug: `seq-variable-height-rows-playwright`

## sequence-rendering-fix

### seq-mmdc-oracle-comparison

→ `workspace.toml` slug: `seq-mmdc-oracle-comparison`

---

## mermaid-p3

### backlog-mermaid-p3-compound-layout

→ Absorbed into ini-002 item 5: `docs/specs/mermaid-recursive-compound-layout`

## mermaid-fidelity-hardening

### mmdc-geometry-capture

→ Absorbed into ini-002 item 2: `docs/specs/mmdc-browser-geometry-capture`

### browser-geometry-capture

→ Absorbed into ini-002 item 2: `docs/specs/mmdc-browser-geometry-capture`

### browser-probing

→ Absorbed into ini-002 item 2: `docs/specs/mmdc-browser-geometry-capture`

---

## mermaid-test-perf-pass2

### playwright-gated-snapshot-verification

→ Absorbed into ini-002 item 13: `docs/specs/mermaid-parity-ci-and-maintainability-cleanup`

### batch-mmdc

→ Absorbed into ini-002 item 2: `docs/specs/mmdc-browser-geometry-capture`

### gpu-benchmark

→ `workspace.toml` slug: `gpu-benchmark`

### xdist-snapshot-guard

→ `workspace.toml` slug: `xdist-snapshot-guard`

---

### backlog-compound-elk-ac1-ac3

→ `workspace.toml` slug: `backlog-compound-elk-ac1-ac3`

---

### state-diagram-local-cycle-routing

→ `workspace.toml` slug: `state-diagram-local-cycle-routing`

---

### state-diagram-cross-scope-clip

**Resolved** (spec `docs/specs/state-diagram-cross-scope-clip/`). `_Edge.src_group` tags cross-scope
exit edges with the composite's group ID. `_compile_flowchart()` now calls
`_clip_cross_scope_exit_waypoints()` after `_route_edges()` and before `_build_routed_edges_ir()`,
clipping the routed path's start point to the composite group's bounding-box boundary.
