# NARRATIVE & PLAYBOOKS

Review whether the source contributes a narrative variation, and record a
one-line decision (`new: <name>` | `none`) in the run spec. Additions here are
**guidance-only** — they change how authors *reason*, not the engine.

## Three kinds of contribution

Read `references/principles/narrative-arc.md` and decide which (if any) applies:

- **Archetype** — a whole non-persuasion structure, distinct from the classic
  pyramid/SCQA/story arc. The **reference-runbook** archetype is the model
  (`narrative-arc.md` §"参考型叙事：运行手册 / 工作手册"): a runbook/worksheet deck
  reads as reference, not argument. Add a new archetype section only for a
  genuinely new structure.
- **Convention** — a reusable discipline *within* a mode. The two persuasion
  conventions are the model (`narrative-arc.md` §"说服型的两条『诚实』约定"): the
  **so-what netline** (every reasoning card ends `Therefore/Result` + a
  conclusion) and the **illustrative-data honesty banner** (estimated numbers
  carry a disclaimer). Name a new convention when the source shows a repeatable
  integrity/rhythm habit.
- **Authoring playbook** — a *workflow* the source's construction reveals, harvested
  into `references/playbooks/` (as the multi-file + shared-CSS + print-combiner
  workflow became `playbooks/print-combiner-playbook.md`).

## Guidance-only — defer the engine

Adding a section to `narrative-arc.md` or a playbook is guidance. **Do not** in
this step change a validator, an enum, or a `page_type` — those are engine-level
public-interface changes. If the source *implies* one (e.g. a new archetype
wants a density-rule branch or a new `page_type`), **defer it**: add a heading in
`docs/backlog.md` describing the engine change, and have the run-spec criterion
cite that anchor (`(deferred: <anchor>)`). (That is exactly how the
reference-runbook archetype's engine work was staged before later specs picked
it up.)

## Record the decision

Write one line into the run spec: `narrative: new archetype "<name>"` /
`narrative: new convention "<name>"` / `narrative: new playbook "<name>"` /
`narrative: none`. The grep gate is that the diff for this step touches only
docs (no validator/enum), and any deferral has a live `docs/backlog.md` anchor.
