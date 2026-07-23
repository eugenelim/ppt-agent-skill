# Backlog — open items by spec

Single index of **open** work across every spec in `docs/specs/`. Each item
names the spec, the Acceptance Criterion (where one applies), what's blocking
it, and how it gets unblocked. Closed/shipped work is **not** kept here — see
each spec's Changelog and [`product/changelog.md`](product/changelog.md).

This is the tactical **backlog**: per-instance, no pack-side source after first
install — it's yours to curate. It is distinct from the **product roadmap**
(strategy, not a work index) at [`product/roadmap.md`](product/roadmap.md).
"Roadmap" = direction; "backlog" = the work/deferral index.

Deferred acceptance criteria point here by **anchor**: a spec criterion written
`- [ ] <outcome> (deferred: <anchor>)` means `<anchor>` resolves to a heading in
this file (GitHub heading-slug rules — lowercase, spaces become hyphens). The
deferral lives here, version-controlled and greppable, not in a PR comment that
rots. See `CONVENTIONS.md` § 4 (Spec metadata contract).

## How this file is maintained

- Every spec records its own `Status:` field and `Acceptance Criteria`
  checkboxes. This file aggregates the **open** items so they're visible in one
  place — it is not the source of truth.
- When an AC closes or a spec ships, update the spec first, then **remove** the
  now-closed item here in the same change (closed work lives in the spec
  Changelog / `product/changelog.md`, not here).
- When a new spec lands with open ACs, add a section here.
- If an item here is no longer accurate against the underlying spec, trust the
  spec and fix this file.

---

## class-diagram-marker-semantics

### class-diagram-marker-clearance

**Deferred from AC:** Route paths for class edges shortened by `MarkerSpec.clearance`
so the marker tip lands at the card face rather than inside it.
Spec sets `clearance=0.0` as default; Assumptions specify 12.0 (triangle/diamond) /
9.0 (open arrow) as the intended values.
Blocked on: setting non-zero clearance in `_class_rel_markers()` and reading
`MarkerSpec.clearance` in `_route_edges()` to shorten the polyline endpoints.
Unblocked by: a dedicated routing-geometry spec (can be light-mode; single file change).

### class-diagram-route-clip

**Deferred from AC:** Route entry/exit points clipped to actual class-card bounding rect.
Pre-existing routing clips to `_Node` bounds; no regression observed. Deferred until
a fixture demonstrates visible overshoot that needs explicit clamping.

### class-diagram-label-segment

**Deferred from AC:** Edge labels placed on longest stable segment (≥40 px).
Pre-existing label placement uses midpoint of the polyline. Deferred until label-overlap
regression is observed in the fixture gallery.

---

## sequence-renderer-correctness-pass

### seq-corr-box-unsupported-fixture

**Deferred from AC-R.2:** `sequence-box-unsupported.mmd` fixture — box grouping
visual fidelity vs mmdc. The `box` directive is parsed but the outer box label and
fill are not rendered. Blocked on a box-semantics spec. Unblocked by writing a
dedicated `sequence-box` spec.

### seq-corr-create-destroy-fixture

**Deferred from AC-R.2:** `sequence-create-destroy.mmd` fixture — `create` / `destroy`
participant lifecycle markers require non-trivial geometry changes (participant appears
or disappears mid-diagram). Deferred to a dedicated lifecycle spec.

### seq-corr-single-participant-fragment-long-header

**Deferred from AC-R.2 / P2#5:** `sequence-single-participant-fragment-long-header.mmd` —
single-participant override for fragment headers wider than the natural canvas. Blocked
on investigation of the exact layout rule in mmdc.

### seq-corr-height-hint-gallery-metadata

`height_hint` is tested in T2 (AC-2.5) but is not tracked per-fixture in
`gallery/metadata.json`. Follow-up: add a `height_hint` column to the per-fixture
provenance row so CI can detect height-scaling regressions.

### seq-corr-mmdc-data-et-selectors

T11 describes extracting `<g data-et="participant">` counts from mmdc SVG. The
exact attribute names depend on mmdc 11.15's output schema. Blocked on a probe of
mmdc's actual SVG output to confirm selectors. Unblocked by running mmdc on a
sample sequence diagram and inspecting the SVG.

---

## diagram-consistency-system

- **Discovered (not an AC deferral): planning `chart_refs` never resolve, so planning
  smoke fixtures fail at baseline.** `planning_validator.resource_exists` looks up a
  `chart_refs` value as a per-name file (`references/charts/<chart_type>.md`), but chart
  recipes live in *grouped* files (`references/charts/{basic,advanced,complex}.md`), so
  any planning packet carrying `chart_refs` / `resource_ref.chart` fails resolution —
  which is why `smoke_skill.py`'s `planning-validator-{low,mid-low,high,dashboard}` cases
  are red at baseline (independent of the outline/style failures). The
  `reference-runbook-archetype` planning fixtures work around this with a `chart_free()`
  helper. Unblocked by teaching `resource_exists` to resolve a `chart_type` against the
  grouped recipe files (e.g. an index), then dropping `chart_free`.

## reference-runbook-page-types

### smoke-skill-pre-existing-fixture-drift

**Discovered (not an AC deferral): `smoke_skill.py` pre-existing fixture drift.**
`tools/smoke_skill.py` exits non-zero on `main` (independent of the
reference-runbook page_type work — verified by running it against the pre-change
tree): its fixtures + the `tpl-style-phase1` invocation reference files that no
longer exist — `references/charts/kpi.md` / `references/charts/metric-row.md`
(charts were consolidated into `basic.md` / `advanced.md` / `complex.md`) and
`references/styles/runtime-style-rules.md` (also referenced at
`references/cli-cheatsheet.md:275`; no `runtime-*` file exists under
`references/styles/`). The `reference-runbook-page-types` change adds **zero**
net-new `smoke_skill` failures and its own new-type router assertions pass. Out
of scope for that spec (unrelated chart/style file structure). Unblocked by a
follow-up that regenerates the smoke fixtures + `cli-cheatsheet` against the
current `charts/` and `styles/` file set (or restores the missing files).

- **Discovered (not an AC deferral): `page_type` value-set duplicated across seven
  sites with no shared constant.** The planning `page_type` enum is copy-pasted
  across three Python modules (`planning_validator.VALID_PAGE_TYPES`,
  `contract_validator.NON_DASHBOARD_PAGE_TYPES` + the `validate_html` chrome set,
  `visual_qa` + `smoke_skill` header/footer sets) plus two playbooks and
  `references/prompts.md` — see [[ppt-page-type-enum-consumers]]. Every enum edit
  re-runs the same seven-site drift risk. Unblocked by exporting `VALID_PAGE_TYPES`
  (and the chrome-required subset) from `planning_validator` and importing it into
  `contract_validator` / `visual_qa` / `smoke_skill`, collapsing three of the seven
  code sites to one. Out of scope for `reference-runbook-page-types` (which added
  both values to every site in lockstep as the spec's *Always do* demanded).

## owasp-llm-agentic-security

Security hardening items deferred from the 2026-07-04 OWASP LLM Top 10 + Agentic Skills Top 10 review.

- **no-sandbox-container-isolation (AST06 / ASI02):** Puppeteer scripts launch with `--no-sandbox` (needed in
  non-userns environments). The portable mitigation is an OS-level container with `seccomp`/`AppArmor` profiles.
  Fix: wrap the Puppeteer render step in a minimal container that provides the kernel namespace; remove
  `--no-sandbox` inside the container. Unblocked by: adding a Docker or OCI container spec for the render
  step and documenting it in SKILL.md Step 6.

## render-visual-check-and-diagram-routing

- **render-gate-live-e2e-qa:** the gate's live end-to-end QA (render a real fixture deck
  through `--with-visual-qa`) was not run in the implementing environment (puppeteer not
  installed; a live install triggers `npm ci`). Covered instead by unit tests
  (`test_render_gate.py`: freshness, exit-code mapping via stubbed subprocess,
  node-degradation decision). Fix: run the live e2e once in an environment with
  puppeteer present.

## mermaid-source-bridge

### mermaid-source-bridge-ac3-visual-qa

**AC3 (deferred: mermaid-source-bridge-ac3-visual-qa):** CSS variable inheritance
check — render `mermaid_layout.py` fragment via `html2png.py` under three `style.json`
variants (dark/light/editorial) and confirm `visual_qa.py` returns non-FAIL. Blocked
on `diagram-consistency-system` shipping its recipe family CSS overrides (the themed
`:root` variable set that the fragment inherits from). Test stub is at
`docs/specs/mermaid-source-bridge/notes/ac3-deferred-test.sh`. Unblocked when the
`diagram-consistency-system` spec status reaches `Implementing` and its styled output
is available in the repo.

## fragment-to-slide-assembler

- **Discovered (not an AC deferral): no reusable script to assemble a `mermaid_layout.py` fragment into a full slide HTML page.** An ad-hoc `gen_slides.py` was written on the fly during a diagram session to: read fragment files, inject the deck's `:root` CSS variables, create a `1280×720` slide body with title bar, two-column content grid (diagram + annotation cards), and `transform:scale(N)` wrapper. `mermaid_layout.py` emits fragments only; `html_packager.py` consumes complete slide HTML and cannot wrap a fragment. Unblocked by creating `scripts/assemble_diagram_slide.py [--fragment path] [--style style.json] [--title "..."] [--annotation annotation.md] [--output slide.html]` — a repeatable, tested script that replaces the ad-hoc approach. Also: `gen_slides.py` hardcoded `frag_h=344` which diverged from actual fragment dimensions after group/canvas height fixes; the assembler should auto-read `width/height` from the fragment's outermost div style.

## mermaid-render-rearchitecture

### vendor-bundle-checksum-gate

**Deferred (not an AC deferral):** Add a CI step that hashes
`scripts/mermaid_render/vendor/dom-to-svg.bundle.js` and asserts it matches a
pinned SHA-256 in the repo. Currently the byte-parity test
(`test_mermaid_render_vendor_bundle_parity`) guards against drift between
`scripts/vendor/` and `scripts/mermaid_render/vendor/`, but neither the source
bundle nor the copy is pinned to a known-good hash. Unblocked by adding a small
`tools/check_bundle_hash.py` + updating CI to run it.

### differential-parity-test

**Deferred (not an AC deferral):** Render a corpus of canonical Mermaid diagrams
through `mermaid_render.to_svg()` and diff against golden SVGs produced by the
pre-rearchitecture `html2svg.py` pipeline. Guards against silent behavioral
regression in the adapter wiring. Unblocked by establishing a golden baseline;
requires Playwright + Chromium in CI (add to `render-scripts` job or a new
`render-parity` job).

<!-- Add one section per spec with open work, e.g.:

## <spec-name>

- **AC<N> (deferred: <anchor>):** <what's open> — blocked on <X>; unblocked by <Y>.

-->

## seq-geometry-fix

Deferred items from the sequenceDiagram geometry fix spec
(`docs/specs/seq-geometry-fix/spec.md`).

### self-loop-finalization-pass

**Deferred from `renderer-hardening-2026-07` AC-P0.3:** Remove the provisional
`max(0, lx_face - extent)` / `max(0, y_face - extent)` clamping in
`_routing.py` self-loop geometry and replace it with a post-layout finalization
pass that normalizes all provisional negative coordinates to canvas-positive
before rendering. Until the finalization pass exists, removing the clamping
produces negative SVG path coordinates that overflow the canvas left edge.
Unblocked by adding a finalization pass after `_assign_coordinates` that
offsets the entire layout so all coordinates are ≥ `CANVAS_PAD`.

### strategies-module-split

**Deferred from `flowchart-pipeline-finish` Task 5:** `scripts/mermaid_render/layout/_strategies.py`
will grow past ~3,500 lines after `_compile_flowchart` is added. The module
should be split into at least `_pipeline.py` (compile/validate/dispatch) and
`_diagram_types.py` (per-type renderers: sequence, Gantt, ER, class, etc.).
The `CONVENTIONS.md` line-count exception for `mermaid_layout/` is stale (the
package moved to `mermaid_render/`) and should be updated at split time.
Unblocked by any future PR that needs to modify `_strategies.py`.

### seq-variable-height-rows-playwright

**Deferred from `seq-variable-height-rows`:** Replace the Pillow font-metrics
measurement in `_note_row_h()` (`_MEASURER.layout(...)`) with a Playwright
text-measurement call that returns the actual rendered line count at the exact
note width. The accumulator architecture (`_row_h_list` / `_row_top_list`) is
already in place; only `_note_row_h` needs to call `page.evaluate()` and return
the measured height. Unblocked by adding a shared Playwright page handle to
`_layout_lifeline`'s call site (or a separate pre-render measurement pass).


## sequence-rendering-fix

Deferred items from the sequenceDiagram rendering fix spec
(`docs/specs/sequence-rendering-fix/spec.md`).

### seq-mmdc-oracle-comparison

**Deferred from `sequence-rendering-fix` AC (Validation four-status model):** The `mmdc_oracle` status field in `ValidationResult` defaults to `"unvalidated"` and is displayed as a grey badge. Computing a real oracle comparison requires: running `mmdc` on each diagram, comparing our SVG geometry to mmdc's SVG (participant positions, lifeline x-coords, activation bar extents), and classifying the result as `pass`/`warning`/`fail`. Unblocked once the `SequenceGeometry` return value (T7 in `sequence-rendering-fix`) is stable enough to compare against parsed mmdc SVG coordinates.

---

## mermaid-p3 — Deferred items

### backlog-mermaid-p3-compound-layout

**Deferred from `mermaid-p3` Stage 4:** Replace the rank-flattening + group-pushing path with
recursive compound layout. Implement group tree, edge partitioning, innermost-first compilation,
proxy-node expansion, boundary gate routing. Remove default reliance on `_apply_inner_direction_positions`,
`_separate_groups_lr/tb`, `_push_nonmembers_out_of_groups_lr`. Required invariants: descendants inside
ancestors, sibling groups non-overlapping, local direction edges predominantly horizontal/vertical,
cross-boundary edges through gates only, deterministic output.

### backlog-mermaid-p3-scene-bounds

**Deferred from `mermaid-p3` Stage 5 (partially shipped):** Visible-geometry ownership is done
(`scene_bounds.py`: `element_visible_bounds`, `scene_visible_bounds`, `validate_scene`).
Remaining: replace raw transform strings (`Element.transform: str`) with typed
`Translate/Scale/Rotate/Matrix` classes.

### backlog-mermaid-p3-infra

**Deferred from `mermaid-p3` Stage 12 (partially shipped):** Theme token infrastructure
(`resolve_tokens()`), `to_png()` rasterizing native SVG, and `validate()` routing through
`RenderRequest` are done. Remaining: wire `to_html()` and `to_svg()`/`to_png()` through
`RenderRequest` — they currently call `_dispatch(...)` / `render_svg_result(...)` directly
rather than through the request object. Also faithful-mode propagation and output-sizing polish.

### backlog-mermaid-p3-class-compiler

**Deferred from `mermaid-p3` Task 7:** Implement `_compile_classdiagram()` that parses `class X { members }`
syntax and returns a `FinalizedLayout` with `NodeLayout.member_layouts` populated. Required to
complete Stage 3 FinalizedLayout authority for classDiagram. Until this exists, classDiagram
continues using `_class_topology_scene()` with mutable models.

## mermaid-fidelity-hardening

### mmdc-geometry-capture

**Deferred from `mermaid-fidelity-hardening` ACs 14 and 16:** Extend the reference adapter to extract per-entity bounding boxes and group geometry from real mmdc SVG renders. Currently reference observations carry no geometry data (geometry is empty/None). Unblocked when mmdc is available.

### browser-geometry-capture

**Deferred from `mermaid-fidelity-hardening` AC 15:** Extend the reference adapter to sample connector paths (edge routing geometry) via Playwright. Unblocked when Playwright + Chromium are available in the capture environment.

### browser-probing

**Deferred from `mermaid-fidelity-hardening` AC 20:** Extract exact Mermaid/mmdc/Node/Playwright/Chromium version provenance by probing the live environment at capture time. Unblocked when browser environment is available in CI.

---

## mermaid-test-perf-pass2

### playwright-gated-snapshot-verification

**Deferred from `mermaid-test-perf-pass2` AC-C3, AC-F1, AC-F4, AC-J1:** These ACs require a
live Playwright+Chromium environment to verify:

- **AC-C3**: `mermaid_render.to_png(FLOWCHART_SRC)` output is byte-identical before and after
  the networkidle → domcontentloaded change in `_to_png_from_svg_string`.
- **AC-F1**: A normal snapshot run launches exactly one `BrowserSession`; `SnapshotRasterSession`
  creates a fresh `BrowserContext+Page` per render (one `new_context` call per `render_html` call).
- **AC-F4**: Snapshot baselines captured before this PR pass against renders using
  `set_content+domcontentloaded` — confirmed locally (36 of 38 ran pass; 2 pre-existing
  sequence-basic failures unrelated).
- **AC-J1**: `pytest --run-snapshots-quick tests/test_snapshots.py` collects exactly 42 items
  (the conftest filter selects the 42; within-test skips for no-baseline fixtures are expected).

Unblocked when playwright/Chromium are available in CI. Add a CI job step that runs
`pytest --run-snapshots-quick tests/test_snapshots.py` and asserts exit code 0 (excluding
the pre-existing sequence-basic failures via `-k "not sequence-basic"`).

### batch-mmdc

**Deferred from `mermaid-test-perf-pass2` Item I:** Batch live mmdc reference rendering in
`test_oracle.py` to reduce subprocess spawning overhead. Currently each `--run-external-reference`
oracle comparison spawns one mmdc process per fixture. Batching (pipe multiple fixtures through one
mmdc invocation) requires multi-process coordination and is complex enough to deserve its own spec.
Unblocked by writing a dedicated `batch-mmdc` spec when the oracle latency becomes a CI bottleneck.

### gpu-benchmark

**Deferred from `mermaid-test-perf-pass2` Item K:** Benchmark `--disable-gpu` vs. hardware-GPU
render path on CI. Cannot benchmark without a benchmarking setup that measures Chromium render
time per-fixture. Unblocked when CI has a stable timing baseline and playwright/Chromium are
available in the benchmark environment. Candidate: add a `--benchmark` flag to `pytest --run-snapshots`
that emits per-fixture render times via `time.perf_counter` around `session.render_html`.

### xdist-snapshot-guard

**Deferred from `mermaid-test-perf-pass2` AC-B1:** Behavioral test for the snapshot xdist guard —
verify that `pytest --run-snapshots -n 2` raises `pytest.UsageError`. Requires `pytest-xdist`
installed; currently not in requirements. The conftest guard code is present (structural AC-B1 met);
only the behavioral assertion is deferred. Unblocked by adding `pytest-xdist` to dev requirements
and writing a subprocess test that asserts `rc != 0` and `"not xdist-safe"` in stderr.

---

### backlog-compound-elk-ac1-ac3

**Deferred from `compound-layout-elk-first-class` AC1–AC3:** AC1 (empty subgraph non-origin
placement), AC2 (groups-complex member containment), and AC3 (inner-direction LR ordering) require
ELK (Node.js + elkjs 0.12.0) to verify. The implementation code (`elk_adapter.py` per-group
`elk.direction`, empty-group minimum size, `_strategies.py` `_elk_grp_bboxes` population) is
shipped; the tests are written and marked `@requires_elk`. Unblocked by installing elkjs:
`npm ci --prefix scripts/mermaid_render/layout` and re-running
`pytest tests/test_compound_layout.py -m requires_elk`.

---

### state-diagram-local-cycle-routing

**Deferred from `state-compiler-recursive` req 9:** Cycle-back transitions (e.g. `Authenticating → Idle`,
`Processing → Active`, `Failed → Idle`) should be routed around the smallest relevant state set rather
than through the global rightmost lanes. The Python Sugiyama A\* router handles them as back-edges
but does not constrain the path to local subgraph columns. Fix requires extending `_routing.py` to
accept per-edge column-confinement hints or using per-subgraph routing passes. Unblocked after the
`_routing.py` refactor decouples back-edge detection from global lane assignment.

---

### state-diagram-cross-scope-clip

**Resolved** (spec `docs/specs/state-diagram-cross-scope-clip/`). `_Edge.src_group` tags cross-scope
exit edges (e.g. `Processing → Done`) with the composite's group ID. `_compile_flowchart()` now calls
`_clip_cross_scope_exit_waypoints()` after `_route_edges()` and before `_build_routed_edges_ir()`,
clipping the routed path's start point to the composite group's bounding-box boundary. `_grp_bboxes`
is computed before routing in both the ELK and Python paths, so the clip runs against stable bboxes.
