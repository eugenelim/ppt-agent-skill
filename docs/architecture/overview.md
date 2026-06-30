# Architecture Overview

> The map of this repository. Read this first when exploring. Updated whenever
> the directory layout or major dependencies change. For the *normative* golden
> path (what new code must conform to), see [`reference.md`](reference.md).

## What this repo is

A Claude Code **skill**: a research-first, content-driven pipeline that turns a
one-line prompt into a professional presentation (HTML pages → editable vector
PPTX). It is **not** a deployed service — it is a set of Markdown instructions
(`SKILL.md` + `references/`) driving a Python script toolchain (`scripts/`).

## Layout

```
.
├── SKILL.md              # the skill itself — the 6-step pipeline + entry points (Python is invoked from here)
├── AGENTS.md             # canonical agent context (CLAUDE.md is a symlink)
├── README.md / README_EN.md  # human-facing intro + 26-style preview gallery
├── ATTRIBUTIONS.md       # third-party credits
├── scripts/              # ALL executable code — 18 Python scripts (see scripts/README.md)
├── references/           # declarative resource library (data, not logic) the skill routes into prompts
│   ├── styles/           # 26 styles across 5 boards (dark / light / vibrant / cultural / natural)
│   ├── layouts/          # 10 Bento-grid layouts
│   ├── blocks/           # card / block types
│   ├── charts/           # chart definitions (basic / advanced / complex)
│   ├── page-templates/   # cover / toc / section / end page templates
│   ├── principles/       # design principles (cognitive load, hierarchy, failure modes, …)
│   ├── playbooks/        # per-step execution checklists
│   ├── design-runtime/   # runtime design rules (css-weapons, data→visual mappings, specs)
│   ├── prompts/          # prompt templates (also prompts.md)
│   ├── pipeline-compat.md # CSS prohibition list that keeps HTML safely convertible to SVG
│   └── *.md              # typography, bento-grid, style-system, method, cli-cheatsheet
├── assets/               # logo, hero images, architecture diagram
├── ppt-output/           # runtime output dir (gitignored except style-gallery/)
├── tests/                # smoke-results/ (gitignored run artifacts)
├── docs/
│   ├── CHARTER.md        # mission, scope, principles
│   ├── CONVENTIONS.md    # how we work
│   ├── architecture/     # this directory — overview.md (map) + reference.md (golden path)
│   ├── specs/            # feature specs and plans
│   ├── adr/ · rfc/       # decisions (frozen) and proposals (governance)
│   ├── product/          # roadmap, changelog
│   └── guides/           # user-facing docs (Diátaxis)
├── tools/                # agentbundle adapter tooling (installed)
└── .claude/              # agent skills / agents / commands (installed)
```

## The two layers

This repo has a deliberate split between **instructions** and **execution**:

- **`SKILL.md` + `references/`** are the *instructions* — the 6-step pipeline
  (research → outline → planning → design → render) and the declarative resource
  library the agent reasons over. No logic lives here; it is data and prose.
- **`scripts/`** is the *execution* — the Python that validates each step's JSON,
  fills prompts, routes resources, and runs the HTML→SVG→PPTX render. The agent
  shells out to these; they hold the contracts.

The forward-only data flow and the component stereotypes (Validator, Pipeline
executor, Harness/router, Reference resource) are described normatively in
[`reference.md`](reference.md).

## Scripts you'll see (`scripts/`)

Full index in [`scripts/README.md`](../../scripts/README.md). The recurring kinds:

- **Validators / gates** — `planning_validator.py`, `contract_validator.py`,
  `milestone_check.py` (block a step until its JSON conforms).
- **Pipeline executors** — `html_packager.py`, `html2svg.py`, `svg2pptx.py`,
  `html2png.py`, `png2pptx.py` (transform one artifact into the next).
- **Harness / routing** — `prompt_harness.py`, `resource_loader.py`,
  `subagent_logger.py`.
- **Shared constants** — `workflow_versions.py` (single source of truth for
  schema versions).
- **Author-time maintenance** (not part of runtime dispatch) — `check_skill.py`
  (doc↔code drift), `smoke_skill.py`, `smoke_test.py`, `visual_qa.py`,
  `gallery.py`, `build_hero.py`.

## Runtime output (`ppt-output/`)

A pipeline run materializes its deliverables here (per the cwd): `outline.json`,
`planning.json`, `style.json`, `slides/` (per-page HTML), `svg/`, `preview.html`,
and the final `.pptx`. Everything under `ppt-output/` is gitignored **except**
`style-gallery/` (the committed 26-style preview used by the README).

## Where to start

1. Read [`docs/CHARTER.md`](../CHARTER.md) — the project's mission and scope.
2. Read this file (the map), then [`reference.md`](reference.md) (the golden path).
3. Read [`SKILL.md`](../../SKILL.md) — the 6-step pipeline is the heart of the repo.
4. Skim [`scripts/README.md`](../../scripts/README.md) to see how the steps are
   gated and rendered.
5. Browse `references/styles/` and `references/layouts/` to see the design
   resource library the skill routes over.
