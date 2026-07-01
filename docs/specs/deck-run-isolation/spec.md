# Spec: Deck-run isolation for concurrent same-cwd runs

Mode: full (risk triggers: concurrency-correctness on a public interface;
touches a render-pipeline script)

- **Status:** Shipped

## Objective

Make the per-deck folder (`OUTPUT_DIR = ppt-output/<deck-slug>/`, from
[per-deck-output-layout](../per-deck-output-layout/spec.md)) a **true isolation
boundary**, so two runs in the same working directory (no git worktree) never
collide — neither on the deck folder itself, nor on temporary render state that
currently escapes the folder. Follows the requirement: "the deck layout should
cover inputs and outputs so temporary state won't collide either."

## Background — the two remaining collision points

The earlier audit found the deck folder already contains all per-run *content*
(planning/slides/png/svg/images/runtime/*.txt) and `html2png.py`'s temp. Two
leaks remain:

1. **Deck-folder allocation is check-then-act.** The slug is deterministic from
   the topic and the folder is created with `mkdir -p` (succeeds on existing),
   so two simultaneous same-topic runs both see "no folder" and pick the same
   `<slug>`, then clobber each other's artifacts.
2. **`html2svg.py` writes fixed-name temp to the shared project root.**
   `.dom2svg_tmp.js`, `.fallback_tmp.js`, `.pdf_tmp/`, and `.bundle_entry.js`
   are written at `work_dir` (the skill repo root, shared across all runs), so
   two concurrent SVG renders overwrite each other's temp scripts / PDF scratch.
   These temp files **must sit next to the shared `node_modules`** (Node resolves
   `require()` by walking up from the script's directory), so they are made
   *unique per invocation* rather than relocated under the deck folder.

The shared `dom-to-svg.bundle.js` and `node_modules/puppeteer` are a deliberate
cross-run **cache** (≈55 MB) and stay shared — not per-deck.

A **third surface** shows up in field runs (the Synchrony engagement): an ad-hoc
**native-PPTX build path** — a `pptx-work/` dir with its own `node_modules` and a
`create_schematic_blueprint_deck.mjs`-style builder, bypassing `svg2pptx`. It is
**not a skill script**, so there is nothing to patch here; the isolation it needs
is simply that `pptx-work/` lives *under* `OUTPUT_DIR` (guaranteed by
[per-deck-output-layout](../per-deck-output-layout/spec.md)'s "everything a run
writes nests here" rule), not at `OUTPUT_ROOT`. If this path is ever promoted into
a real skill script, it inherits the same per-invocation-temp discipline applied
to `html2svg.py` below.

## Changes

- **Atomic deck-folder claim (convention, agent-driven — no script).** In
  `SKILL.md`'s slug rule, replace "`mkdir -p` at first write" with: claim
  `OUTPUT_DIR` using a bare `mkdir` (no `-p`, so it **fails on EEXIST**); on
  failure try `<slug>-2`, `<slug>-3`, … each via the same atomic `mkdir`; the
  first successful `mkdir` is the claim. Resume still scans `OUTPUT_ROOT/<slug>*`
  and reuses the matching folder (match, don't claim-new).
- **Per-invocation temp isolation in `html2svg.py`.** Allocate one unique temp
  dir per `convert()` call — `tempfile.mkdtemp(dir=work_dir, prefix=".h2svg-")`
  — and write every per-invocation temp file inside it (dom-to-svg convert
  script, pdf2svg fallback script, `pdf_tmp/` PDFs, and the esbuild bundle-entry
  file). Remove the temp dir in a `finally`. The temp dir is a **direct child of
  `work_dir`**, so `node_modules` resolution (walk-up) is unchanged.
- **`.gitignore`** ignores `.h2svg-*/` (crash-orphan safety net; normal runs
  self-clean).

## Acceptance Criteria

- [x] `SKILL.md` slug rule states the atomic `mkdir` claim (fail-on-exists →
  `-2`/`-3`, bounded to `-99`); the old "`mkdir -p` 创建" no longer implies a
  non-atomic claim.
- [x] `scripts/html2svg.py` allocates one `tempfile.mkdtemp(dir=work_dir,
  prefix=".h2svg-")` per `convert()` and writes all per-invocation temp inside
  it; no fixed-name temp (`.dom2svg_tmp.js`, `.fallback_tmp.js`, `.pdf_tmp`,
  `.bundle_entry.js`) is written directly at `work_dir`; the dir is removed in a
  `finally`.
- [x] The shared cache is untouched: `dom-to-svg.bundle.js` and
  `node_modules/` stay at `work_dir` (project root).
- [x] `.gitignore` ignores `.h2svg-*`.
- [x] Unit test proves two `convert()`-scoped temp allocations yield **distinct,
  co-existing** dirs under `work_dir` (the collision property) and that the
  helper cleans up, **and** guards the callers via a source scan (no fixed-name
  temp at `work_dir`; temp allocated under `run_tmp`) so a regression can't hide.
- [x] `python3 -m py_compile scripts/html2svg.py` and the new test pass;
  `python3 scripts/check_skill.py` still exits 0.

## Boundaries

**Never do:** move `node_modules`/`dom-to-svg.bundle.js` under the deck folder
(defeats the 55 MB shared-cache design); add a new dependency.

**Out of scope (residual, noted):**
- Concurrent *first-run* `npm install puppeteer` and concurrent *first* esbuild
  bundle build both write the shared cache and can race in a narrow window (only
  when the cache is absent). Closing that needs an install/build lock — deferred.
- **Concurrent resume of the *same* in-progress deck.** The atomic `mkdir` closes
  the *new-deck* claim race, but the resume path (scan `OUTPUT_ROOT/<slug>*`,
  reuse the matching folder) is check-then-act and is not serialized. Resume
  assumes a **single writer** per deck; two runs resuming the same deck at once
  is out of scope.
- **Native-PPTX toolchain (`pptx-work/node_modules`).** Not a skill script, so
  not patched here; its isolation rests on per-deck-output-layout nesting it
  under `OUTPUT_DIR`. If promoted to a skill script it inherits the html2svg
  per-invocation-temp discipline. Its concurrent first-`npm install` shares the
  same narrow cache-population residual as puppeteer above.

## Testing Strategy

Verification mode: TDD for the temp-dir helper (the collision property);
goal-based for the rest.
1. New test `scripts/test_html2svg_tmp_isolation.py`: call the run-temp allocator
   twice, assert two distinct existing dirs under a given `work_dir`, distinct
   from each other, then assert cleanup removes them.
2. `python3 -m py_compile scripts/html2svg.py`.
3. `git grep -n '.h2svg-' .gitignore` non-empty; `git grep` shows no
   `work_dir / "\.dom2svg_tmp` / `\.fallback_tmp` / `\.pdf_tmp` / `\.bundle_entry`
   at `work_dir` in `html2svg.py`.
4. `git grep` confirms the atomic-`mkdir` claim wording in `SKILL.md`.
5. `python3 scripts/check_skill.py` exits 0.
