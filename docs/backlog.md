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

- **Follow-up: regenerate PNG thumbnails for the two new styles + refresh the hero composites.**
  The existing styles ship committed `<style_id>.png` thumbnails and category `hero-*.png`
  composites; the two new styles have HTML mocks only (gallery tiles render from the HTML
  iframe, so the gallery index is correct), and `hero-all.png` / `hero-light-premium.png` still
  render the old tile set (and their README alt-text still reads the old per-category counts).
  Unblocked by `python3 scripts/gallery.py --screenshots` + `python3 scripts/build_hero.py`
  where puppeteer is available. (Visual QA of the 5 new recipes + 2 mocks and the post-diff
  adversarial review were completed in the authoring session — both clean.)

## schematic-blueprint-runbook-restyle

Proposals discovered while restyling `schematic_blueprint` + extracting the runbook
primitives (not AC deferrals — these cross the planning **public interface**, so
they need the full-mode spec path rather than a light-mode ride-along). The
narrative-archetype *guidance* shipped in this PR (`principles/narrative-arc.md`
§参考型叙事 + outline-playbook pointer); making the **engine** honor it needs:

- **Inline section-divider `page_type`.** Add a `section-marker` page_type (lightweight
  §NN + kicker + rule) distinct from today's full-page `section`, so reference decks
  can divide inline. Blocked on: `page_type` enum + `references/page-templates/` +
  validators are contract-bound. Unblocked by a spec updating all three together.
- **`reference_runbook` argumentation strategy + archetype-aware skeleton.** Add a
  `reference_runbook` value to the outline `论证策略` enum and branch the mandatory
  skeleton (the "every Part opens with a full-page section" + "no 3 consecutive high
  density" rules) on archetype, so the density/rhythm override documented in
  `narrative-arc.md` is actually enforced. Blocked on: outline-playbook枚举 is parsed
  downstream. Unblocked by a spec touching the playbook + its parser/validators.
- **`persistent_chrome` deck flag.** A deck-level flag that renders masthead + footer
  on every content page (orientation for reference docs). Blocked on: new deck-level
  field + page-html playbook support. Unblocked by a spec wiring the flag end-to-end.
- **Back-matter reference page types.** First-class RACI / glossary / gates / escalation
  reference sections (vs a CTA finale). Blocked on: same page_type enum contract as
  the first item. Unblocked by the same spec.

- **Gate gap (mechanical, low-risk): fold the pseudo-element warning into the diagram
  recipe lint too.** This PR added a `::before`/`::after`-with-`content` **warning** to
  `smoke_test.py` (gallery mocks); the same lossy-fallback risk applies to `blocks/*.md`
  recipe HTML, which `lint_diagram_recipes.py` does not yet check. Unblocked by adding
  the equivalent scan to the recipe lint.

<!-- Add one section per spec with open work, e.g.:

## <spec-name>

- **AC<N> (deferred: <anchor>):** <what's open> — blocked on <X>; unblocked by <Y>.

-->
