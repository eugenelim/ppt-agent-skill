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

## claude-design-absorption

- **Follow-up (not an AC deferral): visual QA of the 5 new diagram recipes + 2 style mocks.**
  `spectrum-marker` / `iceberg` / `force-field` / `before-after` / `causal-loop` are
  hand-placed SVG geometry; `lint_diagram_recipes.py` verifies markers/colors/pipeline-safety
  but **cannot** catch mis-aligned coordinates or off-canvas labels. Same for the two new
  gallery mocks (`editorial_paper.html`, `schematic_blueprint.html`). Unblocked by rendering
  each at 1280×720 (html2png / a browser) and eyeballing, ideally via a fresh-eyes subagent.
- **Follow-up: regenerate PNGs for the two new styles.** The 26 existing styles ship committed
  `<style_id>.png` thumbnails; the two new styles have HTML mocks only (tiles render from the
  HTML iframe, so the gallery is correct). Unblocked by `python3 scripts/gallery.py --screenshots`
  where puppeteer is available.
- **Note:** the work-loop post-diff `adversarial-reviewer` REVIEW pass was not run in-session
  (shipped on green mechanical gates + the addressed pre-EXECUTE review). A diff review before
  merge is recommended.

<!-- Add one section per spec with open work, e.g.:

## <spec-name>

- **AC<N> (deferred: <anchor>):** <what's open> — blocked on <X>; unblocked by <Y>.

-->
