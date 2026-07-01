# Diagram taxonomy — research-grounded, ratified

Survey of leading diagram taxonomies (Mermaid.js, draw.io/diagrams.net,
Lucidchart, Visio; C4, UML, 4+1, ArchiMate; PM + presentation-concept sets),
consolidated into the set of **genuinely distinct construction recipes** for a
1280×720 slide generator. "Variant of" = same recipe, restyled — free at render
time.

## Ratified families & recipes (16 distinct + 6 SVG-metaphor shapes)

### Family 1 — Process & flow
| id | type | when to use | primitives |
|----|------|-------------|-----------|
| `flowchart` | Flowchart / process flow (also UML Activity) | step/decision logic, workflows | rect/diamond/oval nodes, directed arrows, branches |
| `swimlane` | Swimlane / cross-functional (also BPMN) | flow + WHO does each step | lane bands, nodes-in-lanes, cross-lane arrows |
| `sequence` | Sequence / interaction (also C4 Dynamic) | time-ordered messages between actors/services | lifelines, activation boxes, horizontal labeled arrows |
| `state-machine` | State machine | object/UI/protocol lifecycle | state nodes, guard-labeled edges, initial/final, loop-back |
| `data-flow` | Data-flow diagram (DFD) | how data moves; threat-model/system analysis | process circles, data-store rects, external squares, flow arrows |

### Family 2 — Architecture views
| id | type | when to use | primitives |
|----|------|-------------|-----------|
| `architecture-component` | Component / logical (C4 Context/Container/Component, UML Component) | software components/layers + dependencies | boxes, ports, dependency arrows, layer bands |
| `architecture-deployment` | Deployment / infrastructure / network (C4 Deployment, cloud, topology) | runtime→node mapping, cloud, network | grouped-container node boxes (nesting), hosted artifacts, links |
| `er-data-model` | ER / data model (also UML Class) | DB schema, domain/code model | entity tables w/ attribute lists, cardinality-labeled edges |

### Family 3 — Project management & planning
| id | type | when to use | primitives |
|----|------|-------------|-----------|
| `gantt` | Gantt / roadmap / milestone | schedules, roadmaps, sprints | time x-axis, task-row bars, milestone diamonds, dep arrows |
| `dependency-network` | Network / dependency (PERT/CPM) | critical path, prerequisite graph | task nodes, directed dep arrows, critical-path highlight |
| `org-tree` | Org chart / tree / WBS (also TreeView) | hierarchy, team, work breakdown | parent-child nodes, top-down/L-R edges |
| `kanban` | Kanban board | WIP by stage | status columns, card stacks, optional swimrows |

### Family 4 — Concept & relationship
| id | type | when to use | primitives |
|----|------|-------------|-----------|
| `mind-map` | Mind map / concept map | radial topic hierarchy, brainstorming | central node, radial children, curved branches |
| `matrix-quadrant` | Matrix / quadrant (2×2+, SWOT, RACI, risk) | prioritization, positioning, assignment | labeled axes, quadrant regions, plotted items / filled cells |
| `venn` | Venn / Euler | set overlap, shared properties | overlapping circles, labeled regions |

### Family 5 — SVG-metaphor shapes (fixed geometry, no auto-layout)
`pyramid` (+ pillar/stair) · `funnel` · `cycle` (+ flywheel) · `hub-spoke` ·
`onion` (concentric) · `fishbone` (Ishikawa).

## Variant map (free — no separate recipe)
BPMN/cross-functional→`swimlane`; roadmap/milestone→`gantt`; PERT→`dependency-network`;
WBS/org→`org-tree`; concept-map→`mind-map`; SWOT/risk/RACI→`matrix-quadrant`;
stair/pillar→`pyramid`; flywheel→`cycle`; C4 ctx/container/component→`architecture-component`;
C4 deployment/network→`architecture-deployment`; UML activity→`flowchart`; UML class→`er-data-model`;
UML sequence→`sequence`; UML state→`state-machine`.

## v2 additions — thinking / modeling recipes (spec: claude-design-absorption)

Additive to Family 4 (Concept & relationship). All bind to the same theming contract,
pass `lint_diagram_recipes.py`, and route via the `diagram-concept` block_ref. None
re-home an existing id.

| id | type | when to use | primitives |
|----|------|-------------|-----------|
| `spectrum-marker` | Spectrum / continuum with marked position | one-axis range of options + current/recommended marker | axis line, ticks, open (current) + filled-accent (recommended) circles, intent arrow |
| `iceberg` | Iceberg model | visible surface vs hidden depth (culture, systems, cost) | waterline, ~10% above / ~90% below polygons, HTML labels |
| `force-field` | Force-field analysis (Lewin) | driving vs restraining forces for a change | center change axis, length-encoded arrows both sides |
| `before-after` | Before → after / gap bridge | as-is vs to-be, gap analysis, transformation | current[neutral] / bridge-arrow / future[accent] columns |
| `causal-loop` | Causal-loop diagram (systems) | reinforcing (R) / balancing (B) feedback loops | variable nodes, `<path>` directed edges, +/− polarity, R/B label |

Variants of `matrix-quadrant` (same recipe, no separate lint entry; registered as
routable `diagram_type` aliases): `consultant-2x2` (BCG/McKinsey 2×2 scenario matrix —
double-ended axes, named cells, one focal cell, Jobs-minimal axis labels) and
`quadrant-trajectory` (2×2 with a current→target movement arrow).

Line-art rendering of any recipe is a **theme property**, not a separate recipe — a style
with `decorations.diagram_mode: "lineart"` rebinds the theming-contract vars to a
stroke-only regime (see `blocks/diagram.md` 线稿模式). Default styles render filled.

## Explicitly out of scope (scope-creep flags from survey)
Sankey (data-flow-volume chart, belongs to charts/), Wardley map (niche strategy),
GitGraph (dev tooling), ArchiMate full layered view (enterprise-architect niche).
Revisit per demand.

## Mapping to existing repo state (backward-compat)
`blocks/diagram.md` `diagram_type` enum today = pyramid | flowchart | hub-spoke |
layers | cycle. **All five keep same-named recipes** — `pyramid`/`hub-spoke`/`cycle`
in the concept family, `flowchart` in process-flow, and `layers` as a
layered-stack recipe in the architecture family (NOT renamed to
`architecture-component`; `architecture-component` is a distinct, additional
recipe). `timeline` block → extended by `gantt`. All new ids are purely additive;
no existing value re-homes to a different recipe.

## Sources
Mermaid syntax reference https://mermaid.js.org/intro/syntax-reference.html ·
draw.io types https://www.drawio.com/docs/diagram-types/ ·
Visio templates https://support.microsoft.com/en-us/visio/featured-visio-templates-and-diagrams ·
Lucidchart https://lucid.co/blog/top-diagram-types ·
C4 https://c4model.com/diagrams ·
UML 14 types https://www.archimetric.com/navigating-uml-an-overview-of-the-14-diagram-types-and-their-relevance-in-agile-environments/ ·
4+1 https://en.wikipedia.org/wiki/4%2B1_architectural_view_model ·
InfoDiagram presentation concepts https://blog.infodiagram.com/2020/02/key-visual-diagram-structures-processes-in-powerpoint.html ·
Lucidchart swimlane https://www.lucidchart.com/pages/tutorial/swimlane-diagram
