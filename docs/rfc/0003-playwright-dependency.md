# RFC-0003: Add `playwright` as a shipped runtime dependency

- **Status:** Accepted
- **Author:** eugenelim
- **Approver:** eugenelim *(single-maintainer repo — self-approval at standard weight)*
- **Date opened:** 2026-07-19
- **Date closed:** 2026-07-19
- **Decision weight:** standard
- **Related:** `docs/specs/playwright-export-migration/spec.md`

---

## Reviewer brief

- **Decision:** Add `playwright==1.61.0` to the shipped `requirements.txt` (and consequently to `requirements-dev.txt` which does `-r requirements.txt`), replacing the previous Puppeteer+Node.js runtime that the skill auto-installed via `npm ci` on first use.
- **Recommended outcome:** Accept — `playwright` is a stable, pip-installable package (latest: 1.61.0 at time of writing) that bundles its own Node.js driver and Chromium provisioning tool, eliminating the npm + Node.js system requirement from every adopter environment. This is a pure replacement, not an additive dependency.
- **Change if accepted:** Add `playwright==1.61.0` to `requirements.txt`; implement the full migration described in `docs/specs/playwright-export-migration/spec.md`; delete `package.json` and `package-lock.json`.
- **Affected surface:** `requirements.txt` (shipped), `requirements-dev.txt` (inherits via `-r`), four `scripts/` browser-spawning scripts, `tools/diagram_render_check.py`.
- **Stakes:** Reversible by reverting `requirements.txt` and the four scripts. Irreversible artifact: `scripts/vendor/dom-to-svg.bundle.js` committed; this can be rebuilt at any time with `npm ci` + esbuild if the recipe is documented (recorded in `notes/playwright-export-migration/bundle-recipe.md`).
- **Review focus:** (1) Whether `playwright` is an acceptable size addition to the shipped payload (wheel ~4MB + Chromium ~120MB provisioned separately via `playwright install chromium`). (2) Whether pinning `==1.61.0` is appropriate given this is a rolling-release library.

---

## The ask

**Recommendation:** Add `playwright==1.61.0` to `requirements.txt`. The Puppeteer/Node.js runtime is replaced, not supplemented.

**Why now:** A prior refactor (`skill-payload-refactor`) cleanly separated the shipped payload from dev tools. The Puppeteer bootstrap (runs `npm ci` at adopter runtime, downloads Chromium, writes `node_modules/`) is the last system-Node dependency in the adopter path and the primary blocker for installing the skill in pip-only or agentic environments (Claude, Codex, etc.).

**Decision table:**

| ID | Question | Recommendation | Why |
|---|---|---|---|
| D1 | Add `playwright` to shipped `requirements.txt`? | **Yes** | Single pip dep replaces npm + puppeteer + dom-to-svg + esbuild; no system Node required |
| D2 | Pin to `==1.61.0`? | **Yes** | Consistent with how `lxml`, `Pillow`, `python-pptx` are pinned; Playwright pins a specific Chromium build per release so sub-pixel render determinism depends on the version |
| D3 | Remove `package.json` + `package-lock.json`? | **Yes** | Node is gone from the adopter path; bundle rebuild recipe documented in `notes/`; dev-only re-build is a one-time manual step |

**Not in scope:** Changing any rendering behavior beyond what the Chromium version change produces; new features in the render pipeline.

---

## Accepted

Accepted 2026-07-19 by eugenelim. Follow-on: implement `docs/specs/playwright-export-migration/spec.md`.
