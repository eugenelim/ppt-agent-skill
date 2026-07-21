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

## diagram-consistency-system

- **Discovered (not an AC deferral): style-gallery mock HTML variable-naming drift.**
  The mock decks under `ppt-output/style-gallery/*.html` use an ad-hoc CSS-variable
  vocabulary (`--accent`, `--bg-base`, `--line-soft`, `--display-font`) instead of
  the canonical set the real pipeline injects from `style.json`
  (`--accent-1..4`, `--card-bg-from/to`, `--font-primary`; see
  `page-html-playbook.md` Phase 6). Diagram recipes correctly target the canonical
  set, so they theme correctly under the real pipeline but render low-contrast if
  fed a gallery mock's `:root`. Out of scope for this spec (diagrams + QA + §E
  contradiction). Unblocked by a follow-up that regenerates the gallery mocks
  against the canonical variable set, or documents the mocks as non-canonical.
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

## slide-intent-review

- **Discovered (not an AC deferral): the review gate (and the whole Step-4 planning
  chain) is honor-system, not mechanically enforced.** The soft-token defect that let
  the model skip Step 4.5 is fixed in wording (matched Step 1's `[STOP]` pattern +
  de-optionalized the cheatsheet; `check_step45_review_gate` pins it). But wording is
  still adherence-based: real runs (Agentic-RAG, OSS onboarding) skipped straight from
  interview to slide HTML, so `planning/*.json` was never persisted and Step 4.5 had no
  artifact to run on. A hook is **not portable** — it lives in the consumer's
  `settings.json`, not the installed skill. Unblocked by a follow-up that bakes the gate
  into the skill's *own* export scripts (`html_packager.py` / `html2svg.py` /
  `svg2pptx.py` refuse to produce the deliverable unless `planning/*.json` exists,
  passes `planning_validator`, and a `runtime/.review-consent` marker is present) — the
  one mechanical enforcement that travels with the skill. Out of scope for the
  soft-token bug-fix.
- **Discovered (not an AC deferral): Step 4 planning-persistence is skippable.** Step 4's
  PageAgent flow + `planning_validator` "强制闸门" are documented but not enforced; the
  model can plan in-context and emit `slides/*.html` directly. Same root cause and same
  fix as the item above (export-script gate); tracked together.

## proof-gate-enforcement

- **Deferred: make the marker truly mechanical via the export scripts.** Shipped:
  `proof_gate.py` records a `runtime/proof/gate.json` decision marker and `--check`
  hard-fails pre-render; `SKILL.md` Step 5c runs it. But this is still *prose-invoked*
  (a model that skips Step 4.5 can skip the `--check` too). The portable, unskippable
  form is the **export-script gate** already tracked under `slide-intent-review` above:
  `html_packager.py` / `html2svg.py` / `svg2pptx.py` refuse to produce the deliverable
  unless `gate.json` (serving as / aliasing the `runtime/.review-consent` marker) is
  present. `gate.json` is the marker that follow-up should consume — track together.
- **Deferred: formal-acceptance wiring in `milestone_check.py`.** If `milestone_check`
  is ever wired into Step 6 as a run acceptance gate, add a `gate_status` check to
  `check_preview` / `check_step5` so a proof-skipped deck also fails acceptance
  post-render. Dropped from this spec because `milestone_check` stages are post-render
  and currently unwired from the flow (see spec Assumptions / plan Declined patterns).

## owasp-llm-agentic-security

Security hardening items deferred from the 2026-07-04 OWASP LLM Top 10 + Agentic Skills Top 10 review.


- **no-sandbox-container-isolation (AST06 / ASI02):** Puppeteer scripts launch with `--no-sandbox` (needed in
  non-userns environments). The portable mitigation is an OS-level container with `seccomp`/`AppArmor` profiles.
  Fix: wrap the Puppeteer render step in a minimal container that provides the kernel namespace; remove
  `--no-sandbox` inside the container. Unblocked by: adding a Docker or OCI container spec for the render
  step and documenting it in SKILL.md Step 6.

- **proof-gate-harness-hook (Nit 7):** `proof_gate.py --decision render-direct` is self-attested (model can write
  it without presenting the choice). The truly unskippable form requires a harness `PreToolUse` hook in
  `settings.json` that fires before `html_packager.py`/`html2svg.py` and checks `gate.json`. Track together
  with the `slide-intent-review` export-script gate above.

## render-visual-check-and-diagram-routing

- **render-gate-automated-invocation:** the render-completeness gate
  (`milestone_check.py 4 --with-visual-qa`: PNG-per-slide + freshness + `visual_qa`
  batch) is invoked by a **prose** render-done step in SKILL.md; a future HTML-only
  fan-out that skips both Stage 3 and the gate invocation would reproduce the original
  failure (nothing runs the check). The gate itself is mechanical and cannot be fooled;
  only its *invocation* is discretionary. Fix: wire the gate into an automated seam — a
  render-driver step or a harness `PreToolUse` hook before the Step-6 export scripts
  (track with `proof-gate-harness-hook` above). Deliberately deferred: spec AC B accepts
  "naming the invocation point" as the fix for this loop.
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

## diagram-polish

### recipe-example-updates

- **AC-9 (deferred: recipe-example-updates):** Update `references/blocks/diagram-architecture.md`
  recipe examples to use `:::external` on external system nodes and `|` separator on
  tech-annotated nodes. Not blocking — conventions are documented in `diagram.md`; recipe
  examples are illustrative. Unblocked anytime; low-risk recipe-only edit.

## fragment-to-slide-assembler

- **Discovered (not an AC deferral): no reusable script to assemble a `mermaid_layout.py` fragment into a full slide HTML page.** An ad-hoc `gen_slides.py` was written on the fly during a diagram session to: read fragment files, inject the deck's `:root` CSS variables, create a `1280×720` slide body with title bar, two-column content grid (diagram + annotation cards), and `transform:scale(N)` wrapper. `mermaid_layout.py` emits fragments only; `html_packager.py` consumes complete slide HTML and cannot wrap a fragment. Unblocked by creating `scripts/assemble_diagram_slide.py [--fragment path] [--style style.json] [--title "..."] [--annotation annotation.md] [--output slide.html]` — a repeatable, tested script that replaces the ad-hoc approach. Also: `gen_slides.py` hardcoded `frag_h=344` which diverged from actual fragment dimensions after group/canvas height fixes; the assembler should auto-read `width/height` from the fragment's outermost div style.

## mermaid-layout-refactor

### mermaid-layout-package-split

**Deferred from spec mermaid-layout-refactor (not an AC deferral):** Split
`scripts/mermaid_layout.py` (2,476 lines) into a `scripts/mermaid_layout/` package with
sub-modules (`_constants.py`, `_parser.py`, `_layout.py`, `_routing.py`, `_renderer.py`,
`_strategies.py`). Deferred because it requires careful handling of `python3
scripts/mermaid_layout.py` CLI invocation (package `__main__.py`) and the direct-import
contract used by `scripts/test_diagram_qa.py` (`from mermaid_layout import _dispatch, ...`).
Unblocked after the test suite (AC-TEST) is established — the tests act as the safety net
for a structural split that cannot easily be undone.

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

### lift-seam-adr

**Deferred (not an AC deferral):** Write an ADR documenting the lift seam: what
`mermaid_render/` depends on (stdlib + playwright, nothing else), how a consumer
would move the package to a standalone repo, and what the shim compatibility
contract guarantees. Unblocked anytime; editorial only.

<!-- Add one section per spec with open work, e.g.:

## <spec-name>

- **AC<N> (deferred: <anchor>):** <what's open> — blocked on <X>; unblocked by <Y>.

-->

## c4-layout-engine

### c4-boundary-visual-rendering

C4 boundary/group boxes (`Enterprise_Boundary`, `System_Boundary`, etc.) are
currently parsed (member tracking only) but not rendered as visual containers.
The `groups` dict is threaded through to `_render_c4_fragment` for future use.

Also: the current parser closes boundary stacks on `)`, but Mermaid C4 closes
with `}`. This latent bug has no output effect today (boundaries not rendered),
but must be fixed before visual boundary rendering ships.

### c4-boundary-closing-syntax

The `_layout_c4` parser pops the `boundary_stack` on a line starting with `)`.
Mermaid's C4 syntax closes boundaries with `}`. This produces wrong
`item.boundary` attribution for elements inside boundaries in diagrams that use
the correct `}` closing syntax. Fix together with `c4-boundary-visual-rendering`.

### c4-edge-geometry-parity

Current edge rendering uses a conventional center-ray rectangle intersection.
Mermaid 11.15's `getIntersectPoint()` computes slope using the rectangle's
top-left corner, but places the resulting intersection point at the center —
producing slightly different edge attachment points from a mathematically
conventional center-ray approach. The first relationship renders as a straight
line; subsequent ones use a quadratic Bézier with control point
`(sx + (ex-sx)/4, sy + (ey-sy)/2)`. Exact pixel parity with mmdc screenshots
requires porting the Mermaid algorithm directly.

### c4-icon-map-orphan

`_C4_ICON_MAP` in `scripts/mermaid_render/layout/_constants.py` is now dead —
`_strategies.py` no longer imports it after the C4 renderer was decoupled. Remove
it in a future `_constants.py`-touching pass.

## seq-geometry-fix

Deferred items from the sequenceDiagram geometry fix spec
(`docs/specs/seq-geometry-fix/spec.md`).

### seq-activation-y-tracking

**Implemented** in `docs/specs/seq-geometry-fix-p2/spec.md` (SEQ-006/007).
Two-pass approach: `_event_y` assigns exact y per message; `_act_spans_v2`
computes activation spans from `_last_msg_y` at activate/deactivate events.
Activation-aware message endpoints via `_msg_endpoints` / `_act_bounds_at`.

### seq-message-endpoint-activation

**Implemented** in `docs/specs/seq-geometry-fix-p2/spec.md` (SEQ-007).
See `seq-activation-y-tracking` above.

### seq-per-fragment-bounds

**Implemented** in `docs/specs/seq-geometry-fix-p2/spec.md` (SEQ-008).
`_frag_parts` tracks msg src/dst, note pids, and activate/deactivate pids
during block-span prepass. `_frag_x_bounds()` uses per-fragment participant set.

### seq-variable-height-rows

**Implemented** in `docs/specs/seq-variable-height-rows/spec.md`. Two-pass
heuristic accumulator: note row heights are estimated from character count ×
5.5 px / note width; all downstream y-positions (messages, activation bars,
fragment rects, canvas height) use per-row prefix sums. Pixel-accurate
Playwright text measurement was declined (browser startup cost in the hot
path) and is tracked below.

### self-loop-finalization-pass

**Deferred from `renderer-hardening-2026-07` AC-P0.3:** Remove the provisional
`max(0, lx_face - extent)` / `max(0, y_face - extent)` clamping in
`_routing.py` self-loop geometry and replace it with a post-layout finalization
pass that normalizes all provisional negative coordinates to canvas-positive
before rendering. Until the finalization pass exists, removing the clamping
produces negative SVG path coordinates that overflow the canvas left edge.
Unblocked by adding a finalization pass after `_assign_coordinates` that
offsets the entire layout so all coordinates are ≥ `CANVAS_PAD`.

### adt-pure-python-layout

**Deferred from `flowchart-pipeline-finish` spec:** Record the decision to use
only pure-Python algorithms for graph layout (no Dagre, ELK, NetworkX, Graphviz,
PyGraphviz, pydot, subprocess-based layout engines) as a formal Architecture
Decision Record in `docs/adr/`. The constraint itself is enforced in the spec
and by AST import tests (Task 12); this item tracks creating the accompanying
rationale document (tradeoffs: portability vs algorithm maturity, no Node.js
runtime dependency, deterministic output). Unblocked when `docs/adr/` has an
ADR-format record titled "Pure-Python Layout Engine".

### strategies-module-split

**Deferred from `flowchart-pipeline-finish` Task 5:** `scripts/mermaid_render/layout/_strategies.py`
will grow past ~3,500 lines after `_compile_flowchart` is added. The module
should be split into at least `_pipeline.py` (compile/validate/dispatch) and
`_diagram_types.py` (per-type renderers: sequence, Gantt, ER, class, etc.).
The `CONVENTIONS.md` line-count exception for `mermaid_layout/` is stale (the
package moved to `mermaid_render/`) and should be updated at split time.
Unblocked by any future PR that needs to modify `_strategies.py`.

### seq-variable-height-rows-playwright

**Deferred from `seq-variable-height-rows`:** Replace the character-count
heuristic in `_note_row_h()` with a Playwright text-measurement call that
returns the actual rendered line count at the exact note width. The
accumulator architecture (`_row_h_list` / `_row_top_list`) is already in
place; only `_note_row_h` needs to call `page.evaluate()` and return the
measured height. Unblocked by adding a shared Playwright page handle to
`_layout_lifeline`'s call site (or a separate pre-render measurement pass).


## sequence-rendering-fix

Deferred items from the sequenceDiagram rendering fix spec
(`docs/specs/sequence-rendering-fix/spec.md`).

### seq-mmdc-oracle-comparison

**Deferred from `sequence-rendering-fix` AC (Validation four-status model):** The `mmdc_oracle` status field in `ValidationResult` defaults to `"unvalidated"` and is displayed as a grey badge. Computing a real oracle comparison requires: running `mmdc` on each diagram, comparing our SVG geometry to mmdc's SVG (participant positions, lifeline x-coords, activation bar extents), and classifying the result as `pass`/`warning`/`fail`. Unblocked once the `SequenceGeometry` return value (T7 in `sequence-rendering-fix`) is stable enough to compare against parsed mmdc SVG coordinates.
