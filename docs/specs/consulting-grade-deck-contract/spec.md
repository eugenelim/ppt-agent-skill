# Spec: consulting-grade deck contract

- **Status:** Draft
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** RFC-0001, RFC-0002
- **Brief:** none
- **Discovery:** article crosswalk + repository contract audit (2026-08-26)
- **Contract:** none
- **Shape:** data
- **Source:** [How to Build a McKinsey-Style PowerPoint with AI](https://medium.com/@2315610426/how-to-build-a-mckinsey-style-powerpoint-with-ai-8-simple-rules-for-consulting-grade-slides-a58c009dcb72)

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Make the skill's existing consulting-grade behaviors operate as one explicit,
testable contract across outline, planning, evidence review, and rendering.
The contract adopts the article's eight rules where they fit the repository's
narrative model, while preserving the distinct behavior of non-persuasive decks.

The principal behavior change is **title reuse in this feature**. For an
applicable slide, the outline's audience-facing page title carries the same
proposition as its internal `page_goal`; planning copies that title into the
existing top-level `title`; and HTML renders that existing `title` without
inventing or rewriting a second title. No `action_title` field is introduced.

The other changes strengthen chart evidence, name the existing story/evidence/
design review sequence, and publish a functional-template inventory without
adding page types or components.

## Article-rule crosswalk

| Article rule | Existing owner | Change in this feature |
| --- | --- | --- |
| Story before PowerPoint | Phase 1 outline + Phase 2 outline QA | Name this the **Story pass**; retain archetype routing and title-sequence review. |
| Action/conclusion titles | `page_title` → planning `title`; `page_goal` | Make title reuse an end-to-end contract for the applicable arcs below. |
| One primary task per slide | Phase 2 check #5; one-sentence `page_goal` | Preserve the existing gate and register it in the consulting crosswalk. |
| Match visual form to the information relationship | data-type visual mapping + Step 4 design questions | Register existing selectors as the canonical relationship-to-form route. |
| Charts are evidence, not decoration | chart recipes, `argument_role`, `data_points`, `source_guidance` | Add chart-to-claim review and warning-first numeric-source checks. |
| Use spacing for hierarchy before decoration | visual-hierarchy, composition, design specs, taste gate | Register these existing principles; no visual-system change. |
| Reuse functional page templates | `page_type`, `narrative_role`, `card_type`, `chart_type`, resource refs | Publish the functional-template inventory below; add no new types. |
| Review story, evidence, then design | outline QA, planning/proof review, PageAgent visual review | Make the three passes explicit and ordered; evidence remains mandatory for render-direct. |

## Title reuse contract

`page_goal` remains the internal statement of what the slide must establish.
The outline page heading remains the audience-facing title. On applicable pages,
the title may be shortened for scanability but must preserve the `page_goal`'s
actor, direction, and implication. A topic label is not equivalent. Planning
must copy the approved outline title into `planning.title` verbatim. On
`content`/`toc`, HTML uses that exact text in `h1.page-title`; free-layout pages
(`cover`/`section`/`end`) use it as the exact primary visible heading, although
the element may differ. The browser `<title>` may add the existing mechanical
`Slide {NN} - ` prefix, but may not semantically rewrite the planning title.

| Narrative route | Required title behavior |
| --- | --- |
| `pyramid` | Thesis-first cover. Argumentative content, close, and CTA pages use a conclusion, recommendation, or requested-action title equivalent to `page_goal`. |
| `hybrid` | Same title contract as `pyramid`. |
| `sparkline` | Hook-first cover remains exempt from answer-first wording. Internal argumentative pages use claim titles; the close names the transformed state or quantified request. |
| `status` | Cover retains entity + period + verdict. Content pages use verdict titles that state status, variance, risk, decision, or next commitment—not metric-topic labels. |
| Discovery readout | Evidence pages state an observation; synthesis pages mark the statement as an observation or hypothesis; opportunity pages remain tentative; the closing page may be an open anchoring question. It must not be rewritten as a recommendation. |
| `reference` | Exempt. Navigation and retrieval labels remain the governing title contract. |
| `facilitation` | Exempt. Session objectives and atomic activity instructions remain the governing title contract. |
| `informational` | Exempt. Learning objectives, module labels, recaps, and action guidance remain the governing title contract. |

Navigation surfaces—`toc`, `section`, `section-marker`, `reference`, and a purely
ceremonial `end`—are exempt from title/`page_goal` proposition equivalence.
Cover behavior follows its route-specific rule above. The implementation may
not infer applicability from planning `narrative_archetype`, whose current
two-value contract serves density routing rather than the seven-value narrative
paradigm; applicability is decided and repaired while the outline still carries
`叙事范式` and discovery-readout signals.

## Evidence contract

### Preserve existing evidence-boundary semantics

`source_guidance.strictness` remains the page-level evidence-boundary prose it
is today; this feature does not reinterpret it as a grounding-mode enum. The
Evidence pass reads `grounding_mode` from the already validated requirements
artifact. Per-point traceability stays in the existing `data_points[].source`:

- G1/G2 numeric points use a non-empty real source string.
- An intentionally invented G3 numeric point uses one of the closed illustrative
  sentinels: `Illustrative — unverified` or `示意稿·未经核实` (optional surrounding
  square brackets; English comparison is case-insensitive; Unicode dash and
  whitespace are normalized).
- A real source remains allowed in a G3 deck when the point is actually sourced;
  the sentinel is only for intentionally illustrative values.

No new planning field or workflow-version bump is required.

### Warning-first checks

- **EVID-DATA-01 (WARN):** a non-object `data_points[]` entry cannot carry the
  required label/value/source contract and is not auditable.
- **EVID-SRC-01 (WARN):** a numeric-like object entry has an empty, missing, or
  non-string `source`. A real citation and either closed illustrative sentinel
  both satisfy this mechanical presence check; the Evidence pass decides whether
  that source kind is valid for the deck's grounding mode.
- Numeric-like includes a real integer/float (excluding booleans) or a trimmed
  string that is a measurement: optional comparison/sign, optional currency,
  digits with optional grouping/decimal, then optional magnitude/percent/unit.
  `42`, `42%`, `$2.4M`, and `3 hours` qualify; `Q3`, `Phase 2`, `ID-42`, and
  `TG-A` do not. Empty data points and nonnumeric categories do not trigger
  EVID-SRC-01.
- The warnings are additive: existing planning files remain loadable, and the
  validator adds no new ERROR in this feature.
- Promotion to ERROR is explicitly deferred until a later change has a fixture
  audit, a measured warning baseline, and an approved compatibility decision.

### Chart-to-claim review

Every chart must support, qualify, or falsify the page proposition expressed by
`title`/`page_goal`. The evidence pass checks semantic alignment, appropriate
chart form, readable unit/baseline/timeframe, and source status. A semantically
unrelated chart is removed or replaced, not retained as decoration. This is an
agent-review judgment, not a string-similarity validator.

## Three-pass review contract

The passes are ordered and use existing pipeline machinery:

1. **Story pass** — Phase 2 outline QA checks narrative route, one-slide focus,
   title/goal equivalence where applicable, title-sequence coherence, transitions,
   and route-appropriate opening/closing behavior.
2. **Evidence pass** — after all planning JSON exists and before the Review/
   Render choice, inspect validator results and planning content for source
   warnings, chart-to-claim alignment, units/baselines/timeframes, and G3 labels.
   Repair planning before continuing. `render-direct` skips the user-facing
   worksheet only; it never skips this internal pass.
3. **Design pass** — PageAgent Stage 3 retains its minimum two screenshot-review
   rounds and `visual_qa.py` gate, checking hierarchy, spacing, legibility,
   overflow, and cross-page consistency.

Reviewed planning is immutable during rendering. PageAgent Stage 1 validates and
hands off the already reviewed planning file; it does not regenerate or rewrite
it. A need to change planning returns the page to the planning wave, then reruns
the Evidence pass before HTML resumes. No new review service, consent state, or
proof artifact is introduced.

## Functional-template inventory

| Consulting function | Existing route |
| --- | --- |
| Cover | `page_type: cover` |
| Contents / orientation | `page_type: toc`; `narrative_role: toc | opening | orientation` |
| Section navigation | `page_type: section | section-marker`; transition roles where applicable |
| Executive summary | Early `信息姿态: 结论页` behavior under Phase 2 check #23; no new role or template |
| Analysis / evidence | `narrative_role: evidence | comparison | framework | process | case | quote` plus existing blocks/layouts |
| Chart / quantitative proof | `card_type` + `chart.chart_type` + chart resource refs |
| Recommendation / decision request | `narrative_role: close | cta`, advisory patterns, and route-specific closing rules |
| Timeline / process | `narrative_role: process` + timeline/process cards, charts, diagrams, and layout refs |
| Appendix / back matter | `page_type: reference` and reference-runbook patterns |
| Ceremonial close | `page_type: end`; route-specific closing title rules |

The inventory is documented in the Step 4 planning selector next to the existing
page-type and resource-routing rules. It creates no page type, narrative role,
card type, chart type, component, or branded template.

## Boundaries

### Always do

- Reuse the existing outline title and planning `title`; never create a parallel
  action-title field.
- Preserve the `page_goal` as internal intent even when its proposition is reused
  in the audience-facing title.
- Apply route-specific language: claim, verdict, observation, hypothesis, open
  question, instruction, or navigation label as appropriate.
- Run the evidence pass for both Review-first and render-direct flows.
- Keep reviewed planning unchanged through PageAgent render stages; return to
  planning and rerun Evidence if its content must change.
- Keep all new validator findings warning-only.
- Keep legacy planning files readable.

### Ask first

- Promoting either evidence warning to ERROR.
- Adding or changing a planning-schema field, workflow version, page type,
  narrative role, card type, or narrative-archetype enum.
- Changing the proof-gate consent choices or adding a new review artifact.
- Applying answer-first title rules to `reference`, `facilitation`, or
  `informational` decks.

### Never do

- Add a `mckinsey` narrative arc or encode a consulting firm's brand identity.
- Add `action_title`, a dedicated executive-summary page type, or article-shaped
  template types.
- Rewrite a discovery hypothesis as a proven conclusion or recommendation.
- Use an unverified G3 number without an explicit illustrative marker.
- Add a dependency, top-level directory, visual style, branded template, or
  preview-HTML change.
- Modify accepted RFC bodies; this spec records the user-authorized choice to
  proceed without a new RFC.

## Testing strategy

- **Title routing and preservation:** construction tests inspect all applicable
  route examples, exemptions, outline QA wording, planning-copy instructions,
  and HTML-title preservation. Page Review statically compares normalized
  primary-heading and browser-title text against `planning.title`, allowing only
  the mechanical browser prefix. Include negative cases for topic labels and for
  wrongly answer-first reference/facilitation/informational/discovery pages.
- **Evidence warnings:** TDD around `planning_validator.py` covers object and
  non-object entries, the closed measurement grammar, false-positive labels,
  missing/non-string sources, real sources, and illustrative sentinels. Separate
  Evidence-pass cases cover G1/G2/G3 source-kind decisions. Baseline fixtures
  continue to validate with zero ERROR.
- **Three-pass contract:** goal-based checks ensure `SKILL.md` names all passes in
  order, render-direct cannot skip evidence review, and the render wave cannot
  overwrite reviewed planning.
- **Functional inventory:** goal-based checks ensure every inventory row points
  to an existing enum or reference path; no enum count changes.
- **Integration:** `tools/check_skill.py`, focused planning tests,
  `tools/smoke_skill.py`, and the normal fast suite remain green.

## Acceptance criteria

- [ ] `narrative-arc.md`, Phase 1, and Phase 2 define the title matrix above,
  including discovery-readout epistemic language and all exemptions.
- [ ] Phase 2 evaluates the actual outline page titles—not a proxy that reads
  only `page_goal`—and repairs topic labels before FINALIZE.
- [ ] Step 4 copies the approved outline page title into planning `title` and
  carries `page_goal` separately; HTML uses that planning title unchanged.
- [ ] No `action_title` or other duplicate title field exists.
- [ ] `source_guidance.strictness` retains its existing evidence-boundary
  semantics; the Evidence pass reads grounding mode from validated requirements.
- [ ] `planning_validator.py` emits stable EVID-DATA-01 and EVID-SRC-01 warnings
  under the exact conditions above and adds no evidence-related ERROR.
- [ ] The planning/evidence guidance requires every chart to support, qualify,
  or falsify the page proposition and to expose units, baseline/timeframe, and
  source status where applicable.
- [ ] `SKILL.md` names Story → Evidence → Design as the mandatory order and makes
  evidence review mandatory in render-direct mode.
- [ ] PageAgent rendering does not rewrite reviewed planning; a planning change
  returns to the Evidence pass before rendering continues.
- [ ] Page Review compares normalized visible primary-heading text and browser
  `<title>` against `planning.title`, permitting only the existing mechanical
  slide-number prefix in `<title>`.
- [ ] The functional-template inventory is present in the Step 4 selector and
  references only existing types and resources.
- [ ] Existing one-slide-focus, visual-form, spacing-hierarchy, and visual-review
  rules remain authoritative and are linked from the crosswalk rather than
  duplicated into new systems.
- [ ] Existing planning files remain loadable; warning rollout does not change
  workflow-version constants or validator success semantics.
- [ ] `python tools/check_skill.py`, focused tests, `python tools/smoke_skill.py`,
  and `pytest tests/` pass in the supported environment.

## Assumptions

- Technical — verified: outline page title and `page_goal` already exist as
  separate fields, and planning `title` is already rendered downstream; title
  reuse therefore needs authoring/preservation rules, not a renderer field or
  `html_packager.py` change.
- Technical — verified: `data_points[].source` and `source_guidance.strictness`
  already exist; `strictness` carries evidence-boundary prose, while the
  validator currently checks only that `source_guidance` is an object and does
  not validate per-point sources.
- Technical — verified: the seven-value `叙事范式` exists only in the outline
  contract, while planning `narrative_archetype` is a separate two-value density
  signal. Title applicability is therefore resolved at outline time.
- Technical — verified: story, proof/planning, and visual-review mechanisms
  already exist; this feature composes and tightens them rather than adding a
  fourth stage.
- Product — confirmed 2026-08-26: implement title reuse in this spec; adopt the
  action-title, evidence, three-pass, and functional-inventory recommendations;
  accept all declined additions.
- Process — confirmed 2026-08-26: skip a new RFC. RFC-0001 and RFC-0002 remain
  accepted constraints and their frozen bodies are not edited.

## References

- [`docs/rfc/0001-narrative-philosophy-routing.md`](../../rfc/0001-narrative-philosophy-routing.md)
- [`docs/rfc/0002-audience-type-routing.md`](../../rfc/0002-audience-type-routing.md)
- [`docs/specs/narrative-philosophy-routing/spec.md`](../narrative-philosophy-routing/spec.md)
- [`docs/specs/slide-intent-review/spec.md`](../slide-intent-review/spec.md)
- [`references/principles/narrative-arc.md`](../../../references/principles/narrative-arc.md)
- [`references/playbooks/outline-phase2-playbook.md`](../../../references/playbooks/outline-phase2-playbook.md)
- [`references/playbooks/step4/page-planning-playbook.md`](../../../references/playbooks/step4/page-planning-playbook.md)
