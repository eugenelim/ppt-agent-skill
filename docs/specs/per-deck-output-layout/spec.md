# Spec: Per-deck output layout convention

Mode: full (risk trigger fired — public-interface change: the skill's output
layout is a contract consumed by users and the render pipeline)

- **Status:** Shipped

## Objective

Give every generated PowerPoint its own folder under `ppt-output/`, instead of
dumping all decks flat into `ppt-output/` where a second run overwrites the
first. Formalize this by relocating the pipeline's per-run root, `OUTPUT_DIR`,
from `./ppt-output/` to `./ppt-output/<deck-slug>/`. Everything downstream
(the nested `slides/` HTML folder, `svg/`, `images/`, `runtime/`, the JSON
snapshots, `preview.html`, the `.pptx` files) already resolves relative to
`OUTPUT_DIR`, so it nests under the deck folder automatically.

## Background / why this is safe with no code change

The whole pipeline is parameterized on `OUTPUT_DIR` as its per-run root — every
`prompt_harness.py` invocation and render command in
`references/cli-cheatsheet.md` is written `OUTPUT_DIR/<subpath>`. Relocating
`OUTPUT_DIR` one level deeper therefore requires **no command edits**.

The nested-`OUTPUT_DIR` layout is already exercised: the smoke test runs the
full pipeline with `OUTPUT_DIR = ppt-output/e2e-test/` (`scripts/smoke_test.py`).
Audit of the **per-deck render path** (the only scripts that receive an
`OUTPUT_DIR`-relative path) confirms the extra level is tolerated:
- `html_packager.py`, `svg2pptx.py`, `png2pptx.py` — operate only on the dirs
  passed as arguments; nesting is transparent.
- `html2svg.py` — pins its work dir to the project root (`__file__.parent.parent`),
  independent of the slides path.
- `html2png.py` — `get_dep_dir` walks up ≤5 levels for a dir named `ppt-output`;
  from `ppt-output/<deck>/slides` that is 2 hops and returns the shared
  `ppt-output/` (puppeteer installs once, reused across decks).

The gallery/tooling scripts (`gallery.py`, `diagram_gallery.py`, `build_hero.py`)
are **out of the per-deck path** — they never receive `OUTPUT_DIR`; they hardcode
`ppt-output/style-gallery`, `ppt-output/diagram-gallery`, `ppt-output/e2e-test`,
which become siblings of the deck folders. Unaffected, no change.

## The convention

- **`OUTPUT_ROOT`** = `<cwd>/ppt-output/` — the shared parent for all decks
  and for the tooling/gallery dirs.
- **`OUTPUT_DIR`** = `OUTPUT_ROOT/<deck-slug>/` — one folder per PowerPoint;
  the per-run root all existing pipeline commands already target.
- **`<deck-slug>`** — a short, human-readable slug derived from the topic:
  - Romanize or translate a CJK topic to a concise English phrase, then
    kebab-case it: lowercase, replace each run of non-`[a-z0-9]` with a single
    `-`, trim leading/trailing `-`. Charset `[a-z0-9-]`, ≤40 chars.
  - **Resolve once**, as soon as the topic is known (before the Step 0/1
    interview), and reuse the same `OUTPUT_DIR` for the entire run.
  - **New deck vs. resume:** on a genuinely new deck whose slug collides with an
    existing folder, append `-2`, `-3`, … On a resume or cross-conversation
    re-entry of an in-progress deck, **reuse the existing folder — match, do not
    dedup** (dedup would scatter the resumed run into an empty sibling while the
    real artifacts stay in the original). To locate it, scan
    `OUTPUT_ROOT/<slug>*` and reuse the folder whose artifacts match the run —
    the first run may itself have been deduped to `<slug>-2`, so re-deriving the
    bare slug is not enough.
- Numbered per-page HTML stays in the nested `OUTPUT_DIR/slides/` folder.
- **Everything a run writes nests under `OUTPUT_DIR`** — not just the artifacts
  above but any per-run scratch or build toolchain the run produces: the
  high-res `png/`, and (only when the ad-hoc native-PPTX build path is used) a
  `pptx-work/` dir carrying its own `node_modules`. None of it may land at
  `OUTPUT_ROOT` or the project root.
- Tooling/gallery dirs (`style-gallery/`, `diagram-gallery/`, `e2e-test/`) stay
  as siblings under `OUTPUT_ROOT` — they are not decks.

## Acceptance Criteria

- [x] `SKILL.md` 路径约定 table defines `OUTPUT_ROOT` and the relocated
  `OUTPUT_DIR`, and states the slug rule (derivation + kebab normalization,
  charset, new-vs-resume dedup, resolve-once timing). The existing timing
  sentence "在 Step 1 完成后立即确定" (`SKILL.md:37`) is **replaced** by the
  topic-known/before-interview timing — no contradictory statement left behind.
- [x] `SKILL.md` 输出目录结构 shows the `ppt-output/<deck-slug>/…` nesting with
  `slides/` nested under the deck folder, and `style-gallery/` as a shared
  sibling under `ppt-output/`. Since this block also carries the deferred
  filename drift (see Boundaries), it points at `cli-cheatsheet.md` as the
  authority for exact artifact filenames.
- [x] `references/cli-cheatsheet.md` intro states `OUTPUT_DIR =
  ppt-output/<deck-slug>/`; every command remains valid **unchanged**.
- [x] `docs/architecture/overview.md` reflects the per-deck layout in **both**
  the tree-diagram line (`:36`) and the runtime-output prose section (`:81-86`),
  including the tooling siblings.
- [x] `README.md` and `README_EN.md` output-location lines reflect the per-deck
  folder.
- [x] `git grep` confirms `OUTPUT_ROOT`, `<deck-slug>`, and the resume/dedup rule
  are present in `SKILL.md`, and the per-deck folder appears in
  `README.md`, `README_EN.md`, and `overview.md`. (Primary acceptance evidence.)
- [x] `python3 scripts/check_skill.py` still exits 0 — regression guard that the
  doc↔code contract (script names, prompt-var coverage, interview contract) was
  not broken. It does **not** validate the new convention text.
- [x] No `scripts/*.py` logic is changed.

## Boundaries

**Out of scope (noted for follow-up, not fixed here):**
- Stale docstring examples in `scripts/*.py` (`html_packager.py` usage line;
  `milestone_check.py --output-dir` default help).
- Pre-existing SKILL.md-vs-cli-cheatsheet artifact-naming drift for `outline.json`
  vs `outline.txt` and `presentation.pptx` vs `presentation-{png,svg}.pptx`. The
  输出目录结构 block edited for nesting shares this drift; it is neutralized by
  pointing that block at `cli-cheatsheet.md` as the filename authority rather than
  half-correcting it. (The `planning.json` vs `planning/planningN.json` drift was
  **reconciled** to the per-page path — SKILL.md `:155`/structure block — under
  [planning-gate-mandatory](../planning-gate-mandatory/spec.md), since the gate
  runs on that path.)
- `docs/CHARTER.md`'s "writes files to `ppt-output/`" — accurate at the parent
  level, left as-is.

**Never do:**
- Add a slug-computing script or any new logic under `scripts/` — the agent
  derives the slug and sets `OUTPUT_DIR`, exactly as it sets `ppt-output/` today.
- Add a new top-level directory. `OUTPUT_ROOT` stays `ppt-output/`.

**Ask first:**
- Relocating the shared puppeteer install location (currently resolves to
  `ppt-output/` via `html2png.py get_dep_dir` / project root via `html2svg.py`).

## Testing Strategy

Goal-based verification (grep is primary; check_skill is a regression guard):
1. `git grep -n 'OUTPUT_ROOT' SKILL.md` and `git grep -n '<deck-slug>' SKILL.md`
   are non-empty; the resume/dedup rule text is present in `SKILL.md`.
2. `git grep -n 'deck-slug\|<deck' README.md README_EN.md docs/architecture/overview.md`
   is non-empty (per-deck folder documented in each).
3. `git grep -n '在 Step 1 完成后立即确定' SKILL.md` is **empty** (contradicting
   line removed).
4. `python3 scripts/check_skill.py` exits 0.
5. `git diff --name-only` touches only `SKILL.md`, `references/cli-cheatsheet.md`,
   `docs/architecture/overview.md`, `README.md`, `README_EN.md`, and this spec —
   no `scripts/`.

## Assumptions

- Deck slugs are agent-derived per run; no script computes them (the agent sets
  `OUTPUT_DIR` and passes it to every command, exactly as it does `ppt-output/`
  today).

## Field reconciliation (2026-07-01)

Checked against a real Claude-Desktop run (the Synchrony engagement). It showed
exactly the collision this spec targets — two decks in one `ppt-output/`, one
flat at the root and a second improvised into its own `migration-workbenches-
blueprint/` subfolder — confirming the per-deck direction. It also surfaced two
artifacts not originally enumerated: `png/` (canonical, from `html2png`) and, on
the ad-hoc native-PPTX path, a `pptx-work/` dir with its own `node_modules`.
Both are covered by the "everything a run writes nests under `OUTPUT_DIR`" rule
added above. The `pptx-work/node_modules` isolation angle is carried by
[deck-run-isolation](../deck-run-isolation/spec.md).
