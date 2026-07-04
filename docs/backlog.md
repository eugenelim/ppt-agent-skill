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
`scripts/smoke_skill.py` exits non-zero on `main` (independent of the
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

<!-- Add one section per spec with open work, e.g.:

## <spec-name>

- **AC<N> (deferred: <anchor>):** <what's open> — blocked on <X>; unblocked by <Y>.

-->
