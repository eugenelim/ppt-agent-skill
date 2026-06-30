# Reference architecture

> **Normative.** This document is this repo's *golden path* — the stack, the
> internal building blocks, the component stereotypes, and the cross-cutting
> standards that new work is expected to **conform to**. A feature's low-level
> design (in its plan) reads this as steering: it names which building blocks it
> reuses and which standards it follows, and it justifies any deviation.
>
> This is the **normative** sibling of [`overview.md`](overview.md). `overview.md`
> *describes* how the code is organized today; `reference.md` *prescribes* how
> new code should be shaped. When the two disagree, that gap is either drift to
> fix or a decision to record.

## Constraints

*What the architecture must respect, no matter the feature.*

- **Technical constraints.**
  - **Python 3.8+ is the primary runtime** — all orchestration, validation, and
    PPTX generation live in `scripts/*.py`. Third-party Python deps are kept
    minimal: `python-pptx` (OOXML shape generation) and `lxml` (SVG/XML
    parsing).
  - **Node.js 18+ is a secondary runtime, used only for the HTML→SVG step**
    (`scripts/html2svg.py` shells out to `node` with Puppeteer + the
    `dom-to-svg` bundle, esbuild-packaged). These JS deps **auto-install on
    first run** — there is no `package.json` and no manual `npm install` in the
    golden path.
  - **No deployment platform.** This is a local CLI / agent-skill pipeline that
    produces files, not a deployed service. The work-loop infra preflight has no
    deploy target to read here.
  - **Fixed 1280×720 canvas, `overflow:hidden`.** Slide geometry is
    pipeline-critical (it maps to the PPTX EMU grid in `scripts/svg2pptx.py`);
    designs do not change it.
- **Organizational / process constraints.** This repo follows the
  agent-ready-repo conventions — the plan→execute→verify→review work-loop,
  spec-driven changes under `docs/specs/`, and the Source-of-truth table in
  [`AGENTS.md`](../../AGENTS.md). Cross-step JSON schema versions are
  centralized in `scripts/workflow_versions.py` — that file is the single source
  of truth; do not hardcode version numbers elsewhere.
- **Constraints you cannot change in a single feature.** The forward-only step
  order (Steps 1, 3, and 6 are non-skippable per [`SKILL.md`](../../SKILL.md));
  the JSON-contract handoff between steps; and the CSS prohibition list in
  [`references/pipeline-compat.md`](../../references/pipeline-compat.md) (e.g. no
  `background-clip:text`, no `mask-image`) that would break SVG conversion.

## Solution strategy

*The few decisions that explain most of the codebase.*

- **Architectural style.** A **linear, content-first pipeline**: research →
  outline → planning → design → render. Each step emits a **typed JSON
  deliverable** that the next step consumes, and rendering is deliberately the
  *last* stage so content is validated before any design effort is spent. The
  canonical step order and entry points live in [`SKILL.md`](../../SKILL.md).
- **Key technology decisions.**
  - **Python for orchestration + PPTX (`python-pptx`)** — chosen so the final
    `.pptx` is built from native OOXML shapes and stays editable in PowerPoint,
    rather than embedding flat images.
  - **Node + Puppeteer + `dom-to-svg` for HTML→SVG** — chosen because it
    preserves text as editable `<text>` elements through to the PPTX; it is kept
    behind an auto-install shim so Python remains the single entry point.
  - **JSON-as-contract between steps**, gated by validators
    (`scripts/planning_validator.py`, `scripts/contract_validator.py`) — chosen
    so each step is independently validatable and drift between steps fails fast.
  - **Resource library as data, not code** — styles, layouts, blocks, and charts
    live as declarative markdown under `references/` and are routed by field, so
    design choices are reasoned about declaratively instead of hardcoded.
- **Quality-goal strategy.** *Editability* of the final artifact is preserved
  end-to-end (HTML→SVG→PPTX keeps text as text). *Robustness* is delivered by
  graceful degradation: no Node → emit `preview.html` only; no image generation
  → fall back to CSS-only decoration.

## Building-block view / component catalogue

*The reusable building blocks and stereotypes new code reuses rather than
reinvents.* All executable code lives under `scripts/`; see
[`scripts/README.md`](../../scripts/README.md) for the per-script index.

- **Component stereotypes.**
  - **Validator** — gates a step's JSON against a schema/contract and is allowed
    to block the pipeline (`planning_validator.py`, `contract_validator.py`,
    `milestone_check.py`). A new gate is "a new Validator."
  - **Pipeline executor** — transforms one artifact into the next, forward only
    (`html_packager.py`, `html2svg.py`, `svg2pptx.py`, `html2png.py`,
    `png2pptx.py`).
  - **Harness / router** — fills prompts and routes resources without owning
    pipeline state (`prompt_harness.py`, `resource_loader.py`,
    `subagent_logger.py`).
  - **Reference resource** — declarative markdown data, not logic
    (`references/styles/`, `layouts/`, `blocks/`, `charts/`, `page-templates/`,
    `principles/`, `playbooks/`).
- **Reusable building blocks (reach for these first).**
  - `scripts/workflow_versions.py` — the single source of truth for schema
    version constants.
  - `scripts/resource_loader.py` — `menu` / `resolve` resource routing; reads a
    page's declared needs and loads the matching reference file.
  - `scripts/prompt_harness.py` — `{{PLACEHOLDER}}` filling plus `--inject-file`
    for embedding playbooks/schemas/style into a prompt.
- **Composition rules.** Steps flow **forward only**; each step reads the
  upstream JSON and a validator runs before the next step begins. Resource files
  are routed by field — `layout_hint` → `references/layouts/`, `card_type` →
  `references/blocks/`, `chart_type` → `references/charts/`, `page_type` →
  `references/page-templates/`. **Maintenance scripts (`check_skill.py`,
  `smoke_skill.py`) are not part of runtime dispatch** — they are author-time
  checks only.

## Crosscutting concepts / standards

*The standards every component conforms to.*

- **Error handling & degradation.** Blocking points are marked `[STOP]` in
  `SKILL.md` (e.g. Step 1 waits for the user's research answers — no
  auto-decision). The pipeline senses capability at start and degrades rather
  than failing: missing Node → `preview.html` only; missing image generation →
  CSS-only decoration.
- **Observability.** `scripts/subagent_logger.py` records subagent stage
  stdout/stderr and stage notes to the runtime log — the place to read ground
  truth for a pipeline run.
- **Style consistency.** Every generated HTML page references CSS custom
  properties (`:root { --accent-1: … }`) — **no hardcoded colors**. Swapping one
  `style.json` recolors every page, and the variable indirection keeps the
  SVG→PPTX mapping predictable.
- **Configuration & state.** `.claude/settings.local.json` holds harness
  settings; `.agentbundle-state.toml` tracks installed packs (committed). Runtime
  per-spec state under `docs/specs/**/state.json` is gitignored scratch.
- **Testing standards.** Author-time checks live under `scripts/` and their
  one-liners belong in [`AGENTS.md`](../../AGENTS.md):
  - `python scripts/check_skill.py` — doc↔code contract-drift check.
  - `python scripts/smoke_skill.py` — minimal Step 3/4 end-to-end smoke
    (validators + `visual_qa` + `resource_loader` + `prompt_harness`).
  - `python scripts/smoke_test.py [--phase N] [--style ID]` — phased smoke test.
  - `scripts/visual_qa.py` provides the dual-layer assertion (planning JSON vs.
    rendered HTML). Smoke artifacts land in `tests/smoke-results/` (gitignored).
