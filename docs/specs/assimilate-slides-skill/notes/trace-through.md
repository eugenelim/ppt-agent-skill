# Trace-through — does the written procedure reproduce the two prior assimilations?

The non-circular verification for "the `assimilate-slides` procedure is
followable by a fresh agent": every SKILL.md step maps to a concrete artifact
the two prior assimilations actually produced. If a step had no prior artifact,
it would be unproven prose; none do (ICONS is the deliberate generalization —
the library did not exist for either prior run).

| SKILL step | `graphite_gold` (advisory brief) | `schematic_blueprint` (delivery runbook) |
| --- | --- | --- |
| 1 INGEST | dark consulting deck: print HTML + nav index + shared `css/styles.css` | engineering-delivery runbook (editorial technical doc) |
| 2 SCRUB & DISCARD | "enforce no-PII" (commit `bfa921b`); neutral placeholders | reproduced form only; no client identifiers |
| 3 CLASSIFY | **new style**, `dark_professional`, persuasion (SCQA/pyramid) | **restyle** of `schematic_blueprint`, `light_premium`, reference-runbook |
| 4 EXTRACT STYLE + INDEX | `dark.md §8` JSON + 11-pt styling spec; header 7→8; `index.md` panorama 28→29 + matrix | `light.md` restyled JSON + `§10` styling spec; index rows updated |
| 5 EXTRACT PRIMITIVES | `blocks/advisory-brief.md` (A reasoning cards / B ranked lists+bands / C chrome) + `README` companion + lint target | `blocks/worksheet.md` (A tables/worksheets / B checklist+status / C chrome) + `README` + lint target |
| 6 EXTRACT ICONS | — (library post-dates it) | — (library post-dates it) |
| 7 NARRATIVE & PLAYBOOKS | two persuasion **conventions** in `narrative-arc.md` (so-what netline; honesty banner) + `playbooks/print-combiner-playbook.md` | reference-runbook **archetype** section in `narrative-arc.md`; engine enum/`page_type` deferred to backlog (later picked up) |
| 8 BUILD MOCK | `style-gallery/graphite_gold.html` (1280×720, pipeline-safe) | `style-gallery/schematic_blueprint.html` |
| 9 HERO PROMPT | (deferred to backlog — the exact gap this PR + the hero branch close) | (same) |
| 10 GATES & SHIP | `smoke_test --style graphite_gold`, `lint_diagram_recipes`, `check_skill`; spec **Shipped** | same three gates; spec **Shipped** |

**Conclusion:** every procedural step is backed by a real prior artifact, so the
procedure is not speculative — it is the extraction of an already-run process.
The two net-new capabilities (the icon library, and the hero prompt as a
first-class step) are exercised by *this* PR's dogfood run
(`docs/specs/architecture-diagram-primitives/`), which is the manual-QA proof
that the procedure produces gate-passing output end to end.
