# Plan: mermaid-source-bridge

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

Eight files change in one PR. The strategy is **T1 first** (core layout engine,
graph-topology strategy) because everything else depends on it: T2–T3 extend its
strategy dispatch; T7 (full gate + smoke tests) validates it end-to-end. T4
(validator), T5 (worksheet), and T6 (SKILL.md + template docs) are independent of
T1 and can land in any order.

T1 is the hardest piece: the six-step algorithm (parse → cycle-break → longest-path
rank → 8-pass barycenter → integer coordinate assignment → orthogonal edge routing) is
conceptually clean but requires discipline to keep deterministic — all arithmetic stays
in integer pixels, no float division. Determinism (AC8) is verified by two-call
byte-identical output check rather than structural inspection.

T2–T3 add the remaining 12+ directive types by extending T1's strategy dispatch
function. They share the parser from T1; each adds its own layout function (lifeline
for sequenceDiagram, entity-relation for erDiagram, etc.) returning the same HTML
fragment contract.

**AC3** (CSS variable inheritance via `html2png.py` + `visual_qa.py` under three style
variants) is flagged in T7 as requiring `diagram-consistency-system` to ship first. The
test stub is written in `notes/ac3-deferred-test.sh`; it runs green once the recipe
family's themed CSS overrides are available. AC3 does **not** block shipping AC1/2/4–9.

**Declined patterns (pre-mortem).**
- Tempted to split `mermaid_layout.py` into `mermaid_parser.py` + `mermaid_render.py`
  — declining; one script one CLI is the spec boundary; internal helpers can be module-level
  functions without a second file.
- Tempted to use `networkx` or `pygments` for graph traversal or tokenisation —
  declining; no new pip dependency is a hard spec constraint.
- Tempted to force gantt/pie/sequence through the graph-topology six-step algorithm —
  declining; the spec defines per-type rendering strategies for good reason; forcing
  timeline-structured data into a DAG produces nonsense.
- Tempted to add a mermaid_source extraction helper that reads the source document at
  render time — declining; spec §Never-do: the render agent never re-reads source
  documents; extraction happens at planning time only.
- Tempted to cache layout results between CLI calls — declining; determinism is the
  goal, not speed; caching adds state that breaks the determinism guarantee.

**Resolve-vs-surface disposition.**
- "Is AC3 blocked by `diagram-consistency-system`?" → resolved against the spec's
  Constrained-by note: "render-path wiring cannot be exercised until the recipe family
  ships." T8 notes the blocker; it does not block T1–T7 or AC1/2/4–9.
- "Which CSS variables does the layout engine use?" → resolved against spec Appendix
  §A (full set derived from `blocks/diagram.md`). No unresolved domain claim.
- "What Mermaid directive strings trigger each strategy?" → resolved against spec
  strategy table (16+ types, case-insensitive match on first non-whitespace line).
- "Node/edge cap thresholds" → 64/128/16 per spec §Algorithm §Cap. No escalation.

---

## Constraints

- `pipeline-compat.md` — arrowheads as `<polygon>`, connectors as `<div>`/SVG
  `<line>`/`<path>`, all labels HTML (never SVG `<text>`), no `mask-image`, no CSS
  border-triangles, no `::before`/`::after` visual content, no `stroke-dashoffset`.
- `blocks/diagram.md` CSS-variable theming contract — all colors via CSS variables
  from spec Appendix §A. Only hardcoded hex permitted: `#22c55e` (trend up) and
  `#ef4444` (trend down) in chart types only.
- `mermaid_layout.py` — pure Python, no new `pip` dependency, O(N²) worst-case,
  under 2 seconds for any input at the cap.
- `DIAG-SRC-01` starts as WARN — never promote to FAIL in this PR (spec §Never-do).
- Constrained by `diagram-consistency-system` — AC3 render-path wiring deferred.
  All other ACs are independent.

---

## Construction tests

Goal-based CLI smoke calls and greps per task. Summary:

**Determinism (T1, T7):**
```bash
printf 'flowchart TB\n  A[Ingest] --> B[Process]\n  B --> C[Store]' > /tmp/det-fixture.mmd
O1=$(python3 scripts/mermaid_layout.py --source @/tmp/det-fixture.mmd)
O2=$(python3 scripts/mermaid_layout.py --source @/tmp/det-fixture.mmd)
[ "$O1" = "$O2" ] && echo PASS_DETERMINISM
```

**Pipeline-safety (T1, T7):**
```bash
printf 'flowchart TB\n  A-->B' > /tmp/test.mmd
python3 scripts/mermaid_layout.py --source @/tmp/test.mmd > /tmp/frag.html
grep -q '<text'                    /tmp/frag.html && echo FAIL_SVG_TEXT   || echo PASS
grep -qE 'border-(left|right|top|bottom):[^;]*transparent' /tmp/frag.html && echo FAIL_CSS_TRI || echo PASS
grep -q '::before\|::after'        /tmp/frag.html && echo FAIL_PSEUDO     || echo PASS
grep -q 'stroke-dashoffset'        /tmp/frag.html && echo FAIL_DASHOFFSET || echo PASS
grep -qP '#[0-9a-fA-F]{3,8}'       /tmp/frag.html && echo WARN_HARDCODED_HEX
grep -q '<polygon'                 /tmp/frag.html && echo PASS_ARROWHEAD  || echo FAIL
```

**Cap enforcement (T1, T7):**
```bash
# 65 nodes → exit 1  (range(64) produces N0..N64 = 65 distinct nodes)
python3 -c "print('flowchart TB'); [print(f'  N{i}-->N{i+1}') for i in range(64)]" > /tmp/cap65.mmd
python3 scripts/mermaid_layout.py --source @/tmp/cap65.mmd; [ $? -eq 1 ] && echo PASS_CAP_FAIL
# 64 nodes → exit 0  (range(63) produces N0..N63 = 64 distinct nodes)
python3 -c "print('flowchart TB'); [print(f'  N{i}-->N{i+1}') for i in range(63)]" > /tmp/cap64.mmd
python3 scripts/mermaid_layout.py --source @/tmp/cap64.mmd; [ $? -eq 0 ] && echo PASS_CAP_OK
```

**Validator DIAG-SRC-01 (T4, T7):**
```bash
# WARN fires on empty mermaid_source
echo '{"page_type":"content","slide_number":1,"title":"T","cards":[{"card_id":"c1",
  "card_type":"diagram","diagram_type":"flowchart","headline":"H","role":"anchor",
  "body":["x"],"diagram_source":{"origin":"source_document","mermaid_source":"",
  "fence_index":0}}],"director_command":{},"decoration_hints":{},
  "source_guidance":{},"resources":{"block_refs":["diagram-process-flow"]}}' > /tmp/p.json
python3 scripts/planning_validator.py /tmp/p.json 2>&1 | grep -q 'DIAG-SRC-01' && echo WARN_FIRES

# No DIAG-SRC-01 on valid mermaid_source
# (substitute valid mermaid_source string and confirm no WARN)
```

**Proof worksheet (T5, T7):**
```bash
# Card with diagram_source emits fenced code block in worksheet HTML
python3 scripts/proof_worksheet.py /tmp/test-deck/ 2>/dev/null | grep -qF '```mermaid' && echo PASS
# Card without diagram_source does not emit fenced block
# (confirm no false-positive on a plain diagram card)
```

**Gate non-regression (T7):**
```bash
python3 scripts/smoke_skill.py && python3 scripts/check_skill.py && python3 scripts/smoke_test.py
```

---

## Design (LLD)

### Design decisions

- **Single script, strategy dispatch.** `mermaid_layout.py` has one `main()` / CLI
  entry point. It detects the Mermaid directive from the first non-whitespace line
  and dispatches to one of four internal strategy functions:
  `_layout_graph_topology()`, `_layout_lifeline()`, `_layout_structured_relation()`,
  `_layout_chart()`. Direct `if/elif` on the lowercased directive — no registry, no
  class hierarchy, no dynamic dispatch.

- **Integer coordinates throughout.** All x/y positions are integer pixel values
  computed in layout steps 1–5; no float division. The only float in the codebase is
  the barycenter mean (divided by N predecessors), immediately rounded to `int`.
  This is the determinism guarantee: no floating-point rounding drift between runs on
  different CPUs.

- **CSS custom properties as inline style.** The `.diagram.mermaid-layout` root
  element carries all spacing variables as `style=""`. The fragment is self-contained:
  paste it into any HTML page that defines the deck's `:root` CSS variables and it
  renders correctly. No external stylesheet required from the fragment.

- **Single SVG overlay.** One `<svg>` element, absolutely positioned over the
  container, `pointer-events: none`. All edges live inside it. This avoids per-edge
  SVG elements and the z-index complexity they bring.

- **Invisible dummy nodes.** Dummy nodes (inserted for multi-rank edges in Step 3)
  are emitted as `width:0; height:0; overflow:hidden` divs; their coordinates are
  used only as Bezier control points. They carry no visual CSS.

- **Spec Appendix §A is the CSS variable contract.** The script's output block at the
  top of `_render_html_fragment()` emits exactly those variable declarations. Any
  new visual property that needs a CSS variable must go through the spec Appendix
  first (Boundaries §Ask-first), not directly into the script.

---

## Tasks

### T1: Core layout engine — parser + graph-topology strategy

**Depends on:** none
**Touches:** `scripts/mermaid_layout.py` (new file)
**Mode:** TDD + goal-based check

Implements the full `mermaid_layout.py` script for the **graph-topology strategy**:
`flowchart`, `graph`, `stateDiagram-v2`, `stateDiagram`. This covers the six-step
algorithm (spec §Algorithm), the CLI interface, cap enforcement, and the HTML
fragment output contract.

**Tests:**

*Parser correctness (TDD stubs first):*
- Fixture `"flowchart TB\n  A[Ingest] --> B\n  B --> C[Store]\n"` → `nodes=[A,B,C]`,
  `edges=[(A→B),(B→C)]`, `groups=[]`
- Fixture with subgraph → node-to-group membership asserted
- Fixture with cycle (`A --> B\n  B --> A`) → back-edge marked `reversed=True`; no
  infinite loop
- Node shape detection: `[rect]`, `(round)`, `{diamond}`, `[(cylinder)]`,
  `((circle))` → shape enum asserted per bracket pattern

*Rank assignment:*
- Linear chain A→B→C→D → ranks [0,1,2,3]
- Diverging fan A→B, A→C, B→D, C→D → D rank = 2 (longest path)
- Multi-rank edge A→D (rank gap 3) → 2 dummy nodes inserted

*Crossing minimisation:*
- After 8 barycenter passes, same fixture produces identical column order on two
  calls (determinism check)

*Pipeline-safety greps (from Construction tests above)*

*Cap enforcement:*
- 65-node fixture exits 1
- 64-node fixture exits 0 with valid HTML

*CLI:*
- `--source @file.mmd` reads file content
- `--direction LR` overrides graph direction
- `--output /tmp/x.html` writes to file; stdout when absent

**Approach:**
1. Write `_parse_mermaid()` — tokenise directive, node declarations (bracket-type
   shape detection), edge declarations (style + arrowhead + label), subgraph
   push/pop. Return `nodes`, `edges`, `groups` dataclasses.
2. Write `_break_cycles()` — DFS back-edge detection; flip back-edges to
   `reversed=True`.
3. Write `_assign_ranks()` — longest-path over reverse topological order; dummy
   node insertion for gap > 1.
4. Write `_minimize_crossings()` — 8-pass barycenter (4× forward + 4× backward);
   sort nodes within each rank by barycenter; return `col_index` per node.
5. Write `_assign_coordinates()` — integer pixel x/y from `col_index × (node_w +
   h_gap)` and `rank × (node_h + v_gap)`; canvas width/height computed.
6. Write `_route_edges()` — adjacent-rank edges as cubic Bezier (bottom-centre →
   top-centre); back/multi-rank edges as orthogonal right-lane. Fan-in/fan-out
   distribution per spec §Step6.
7. Write `_render_html_fragment()` — emit the `<div class="diagram mermaid-layout">`
   container, node divs, SVG overlay. All colors as CSS variables per Appendix §A.
8. Wire `main()` with argparse; dispatch to `_layout_graph_topology()` for
   `flowchart`/`graph`/`stateDiagram*`.
9. Exit 0 on success; exit 1 on parse error, cap exceeded, or unrecognised directive
   with no fallback.

**Done when:** parser tests pass; determinism check passes; pipeline-safety greps all
pass; cap enforcement (64/65) correct; `python3 scripts/mermaid_layout.py --source
'flowchart TB\n  A-->B\n  B-->C'` exits 0 and emits valid HTML with `<polygon>` and
`var(--edge)`.

---

### T2: Structured diagram strategies (sequenceDiagram, erDiagram, classDiagram)

**Depends on:** T1 (parser infrastructure + strategy dispatch pattern)
**Touches:** `scripts/mermaid_layout.py`
**Mode:** goal-based check

> **sequenceDiagram resolution:** The spec's original Ask-first list included
> "Adding sequenceDiagram support" but the strategy table includes it and the user
> resolved "no phasing, deliver all types." The Ask-first entry has been removed from
> the spec. `sequenceDiagram` is in scope for T2.

Adds three strategy functions to `mermaid_layout.py`:

- `_layout_lifeline()` for `sequenceDiagram`: participants as vertical columns,
  messages as horizontal arrows with activation boxes, alt/loop blocks as labelled
  horizontal bands.
- `_layout_structured_relation()` for `erDiagram`: entities as nodes, relationships as
  labeled edges with cardinality markers (`||--o{` etc.), grouped by entity rank using
  the longest-path algorithm from T1.
- `_layout_hierarchical()` for `classDiagram`: inheritance edges rank upward;
  association/composition edges horizontal; method/attribute lists inside node divs.

All three reuse `_render_html_fragment()`'s node/SVG overlay contract from T1.

**Tests:**
- `python3 scripts/mermaid_layout.py --source 'sequenceDiagram\n  Alice->>Bob: hi\n
  Bob-->>Alice: hello'` exits 0; output contains `class="node"` for Alice + Bob and
  `class="message"` (or edge equiv)
- `python3 scripts/mermaid_layout.py --source 'erDiagram\n  CUSTOMER ||--o{ ORDER : places'`
  exits 0; output contains two node divs and one edge path
- `python3 scripts/mermaid_layout.py --source 'classDiagram\n  Animal <|-- Dog'` exits 0;
  output contains two node divs and one inheritance edge

**Done when:** all three fixtures exit 0; pipeline-safety greps pass on each output.

---

### T3: All remaining diagram types

**Depends on:** T1 (strategy dispatch)
**Touches:** `scripts/mermaid_layout.py`
**Mode:** goal-based check

Adds layout functions for all remaining directive types in the spec strategy table:
`gantt`, `timeline`, `quadrantChart`, `pie`/`pie showData`, `xychart-beta`, `mindmap`,
`block-beta`, `packet-beta`, `kanban`, `architecture-beta`, `C4Context`/`C4Container`/
`C4Component`.

Strategy families:
- **Timeline layout** (`gantt`, `timeline`): horizontal time axis, tasks/events as
  horizontal bars or points
- **Grid layout** (`quadrantChart`): 2×2 fixed grid with plotted data points
- **Chart layout** (`pie`, `xychart-beta`): donut/pie segments or bar/line axes
- **Radial tree** (`mindmap`): root at center, branches by depth
- **Grid block** (`block-beta`): declared rows/columns
- **Bit-field** (`packet-beta`): fixed-width horizontal cells
- **Column layout** (`kanban`): vertical card stacks in labeled columns
- **Zone-node** (`architecture-beta`): named zone containers with nodes and edges
- **C4 layered** (`C4Context`/`C4Container`/`C4Component`): boundary boxes with
  system/component nodes and relationships

For directive types not in the strategy table (`gitGraph`, `journey`,
`requirementDiagram`): attempt graph-topology fallback; exit 1 on parse failure.

**Tests:**
- One fixture per directive family exits 0 and emits `<div class="diagram mermaid-layout">`
- Pipeline-safety greps pass on each output (no SVG `<text>`, no hardcoded hex, etc.)
- `gitGraph` fixture: exit 1 acceptable (graph-topology fallback; complex git branching
  likely fails the parser)

**Done when:** at least one fixture per strategy family exits 0; pipeline-safety greps
pass; total directive coverage matches the spec strategy table.

---

### T4: planning_validator.py — DIAG-SRC-01 check

**Depends on:** none
**Touches:** `scripts/planning_validator.py`
**Mode:** goal-based check

Adds `validate_diagram_source()` function and wires it into `validate_page()` (after
the existing `validate_diagram_routing()` call at line 641).

Check logic:
- Fires only when `card_type == "diagram"` AND `card.get("diagram_source")` is present
- Checks `mermaid_source` is a non-empty string beginning with a recognised Mermaid directive
  (case-insensitive first token from the spec strategy table; no `---` frontmatter tolerated
  since stored source has frontmatter already stripped)
- Checks `fence_index` is an integer when `origin == "source_document"`
- Emits WARN on any failure (never FAIL/ERROR)

Known directives for the check: `flowchart`, `graph`, `sequenceDiagram`,
`stateDiagram-v2`, `stateDiagram`, `erDiagram`, `classDiagram`, `gantt`, `timeline`,
`quadrantChart`, `pie`, `xychart-beta`, `mindmap`, `block-beta`, `packet-beta`,
`kanban`, `architecture-beta`, `C4Context`, `C4Container`, `C4Component`, `gitGraph`,
`journey`, `requirementDiagram`.

**Tests:**
- Empty `mermaid_source` → WARN containing `DIAG-SRC-01`
- `mermaid_source` starting with unknown string `"notadiagram TB"` → WARN
- Missing `fence_index` when `origin == "source_document"` → WARN
- Valid `mermaid_source = "flowchart TB\n  A-->B"` with `fence_index: 0` → no
  DIAG-SRC-01 WARN
- `diagram_source` absent on a `card_type: diagram` card → no DIAG-SRC-01 (not
  triggered)
- Card with `card_type: text` and `diagram_source` present → no DIAG-SRC-01 (only
  fires on `card_type: diagram`)

**Done when:** all six test cases pass; `planning_validator.py` gates still exit 0 on
existing valid planning fixtures.

---

### T5: proof_worksheet.py — mermaid_source display block

**Depends on:** none
**Touches:** `scripts/proof_worksheet.py`
**Mode:** goal-based check

Modifies `render_card_row()` to append a `mermaid_source` display block when
`diagram_source.mermaid_source` is present on the card.

Placement: after the existing `image` block in `content_bits` (line ~180), before the
`status` cell is assembled. The block is a `<pre class="mermaid-src">` containing the
escaped mermaid source wrapped in a fenced code marker so the reviewer sees the exact
topology.

```python
ds = card.get("diagram_source")
if isinstance(ds, dict) and isinstance(ds.get("mermaid_source"), str) and ds["mermaid_source"].strip():
    src_ref = ds.get("source_ref") or ""
    fence_idx = ds.get("fence_index")
    label = f"mermaid fence {fence_idx}" if isinstance(fence_idx, int) else "mermaid"
    if src_ref:
        label += f" from {src_ref}"
    content_bits.append(
        f'<pre class="mermaid-src"><code>```mermaid\n{esc(ds["mermaid_source"].strip())}\n```</code></pre>'
    )
```

A small CSS rule for `.mermaid-src` is added to the worksheet's `<style>` block:
`font-size:11px; background:#f5f5f5; padding:4px 8px; border-radius:4px; margin-top:4px;
overflow-x:auto; white-space:pre;`.

**Tests:**
- Card with `diagram_source.mermaid_source = "flowchart TB\n  A-->B"` → worksheet
  HTML contains `` ```mermaid `` and the source text
- Card with `diagram_source` present but `mermaid_source` empty → no
  `.mermaid-src` block emitted (guarded by the `.strip()` check)
- Card without `diagram_source` → no `.mermaid-src` block (no regression)
- `is_chart()` not modified
- `card_rows()` not modified — the `.mermaid-src` display block is an annotation
  outside the row-count budget; it renders inside a `<pre>` with fixed height and
  `overflow-x:auto`. If future work uses `card_rows()` for overflow detection on
  diagram cards, the mermaid_source line count should be folded in at that point.

**Done when:** greps confirm fenced code block present for valid source, absent when
empty/missing; existing worksheet snapshots for non-diagram cards unchanged.

---

### T6: SKILL.md + orchestrator template — extraction fork documentation

**Depends on:** none (the CLI interface is fully pinned in spec §CLI interface; the
template documents the spec contract, not T1's implementation)
**Touches:** `SKILL.md`, `references/prompts/step4/tpl-page-orchestrator.md`
**Mode:** goal-based check

**SKILL.md — Step 3 extraction fork:**
Add a subsection to Step 3 (`### Step 3: 大纲策划`) documenting the Mermaid fence
extraction decision:
- When source documents are present, enumerate every Mermaid fence (by `fence_index`)
- Each fence the planner decides to use becomes a separate outline item (one fence →
  one slide candidate)
- Record `mermaid_source` on each outline item (passthrough to Step 4)
- Frontmatter stripping rule: strip config frontmatter (`layout:`, `theme:`, etc.);
  promote `title:` to headline if unset; keep directive + topology

**SKILL.md — Step 4 planning:**
Add a note to Step 4 (`### Step 4: 内容分配 + 策划稿`) documenting the `diagram_source`
field:
- When the outline item carries `mermaid_source`, write it into
  `diagram_source.mermaid_source` in the planning card JSON
- `diagram_source` is additive — does not replace `card_type`, `diagram_type`, or
  `block_refs` routing

**tpl-page-orchestrator.md — render-path integration:**
Add a pre-render check note (in Stage 2: HTML section) documenting that for
`card_type: diagram` cards:
1. Check `diagram_source.mermaid_source` in the card JSON
2. If present: write `mermaid_source` to `/tmp/diag-src.mmd`, then run
   `python3 SKILL_DIR/scripts/mermaid_layout.py --source @/tmp/diag-src.mmd --output
   /tmp/diagram-fragment.html` (the `@file` form avoids shell-quoting hazards with
   embedded newlines); on exit 0 embed fragment; on exit 1 fall back to ad-hoc path
3. If absent: use existing ad-hoc path (no regression)

**Tests:**
- `grep -n "mermaid_source\|diagram_source\|fence_index" SKILL.md` returns hits in the
  Step 3 and Step 4 sections
- `grep -n "mermaid_layout.py\|diagram_source" references/prompts/step4/tpl-page-orchestrator.md`
  returns hits in the Stage 2 section
- `grep -n "strip.*frontmatter\|frontmatter.*strip\|title.*headline" SKILL.md` — stripping rule documented

**Done when:** both files contain the documented extraction fork and render-path
integration; no existing mandatory content removed.

---

### T7: Full gate pass + smoke tests + README update

**Depends on:** T1, T2, T3, T4, T5, T6
**Touches:** `docs/specs/README.md` (status update), read-only verification of all above
**Mode:** goal-based check

Runs the full AC coverage checklist:
- AC1: `python3 scripts/mermaid_layout.py --source 'flowchart TB\n  A-->B'` exits 0 with HTML fragment
- AC2: Pipeline-safety greps (no SVG `<text>`, no CSS triangles, etc.)
- AC4: DIAG-SRC-01 validator check fires WARN on malformed; silent on valid
- AC5: Worksheet fenced block present/absent per fixture
- AC6: SKILL.md greps for Step 3 + Step 4 extraction fork
- AC7: Orchestrator template grep for render-path integration
- AC8: Determinism — two-call byte-identical check
- AC9: Update `docs/specs/README.md` mermaid-source-bridge row and `spec.md` line 3
  `Status:` from `Draft` → `Implementing`

Gate commands:
```bash
python3 scripts/smoke_skill.py && \
python3 scripts/check_skill.py && \
python3 scripts/smoke_test.py
```

**AC3 (deferred: mermaid-source-bridge-ac3-visual-qa):** Blocked on
`diagram-consistency-system` shipping its recipe family CSS overrides. The test stub
written to `notes/ac3-deferred-test.sh`:
```bash
printf 'flowchart TB\n  A[Ingest] --> B[Process]\n  B --> C[Store]' > /tmp/test.mmd
python3 scripts/mermaid_layout.py --source @/tmp/test.mmd --output /tmp/frag.html
# Then embed /tmp/frag.html in a minimal wrapper with deck :root CSS variables and run:
python3 scripts/html2png.py /tmp/frag-wrapper.html /tmp/frag.png
python3 scripts/visual_qa.py /tmp/frag.png  # must return non-FAIL
```
This stub can be run once the recipe family ships. AC3 is tracked in `docs/backlog.md`
under the `mermaid-source-bridge-ac3-visual-qa` anchor.

**Done when:** AC1/2/4–9 all pass; AC3 stub written; gate commands exit 0; README and
spec header updated to `Implementing`.

---

## Rollout

New script + planning-schema extension + four playbook/reference edits. No data
migration, no flag. Reversible by revert. Existing planning JSON files without
`diagram_source` are unaffected (field is optional; validator WARN-only). Existing
render pipeline unchanged for cards without `diagram_source` (explicit fallback in the
orchestrator template).

Deployment sequencing: T1 (core engine) → T2/T3 (remaining strategies) in parallel →
T4/T5/T6 (validator/worksheet/docs, can land with T1) → T7 (full gate). All in one PR.

AC3 (visual QA under recipe variants) is left as a follow-up task tracked in
`notes/ac3-deferred-test.sh`; it unblocks when `diagram-consistency-system` ships.

---

## Risks

- **Algorithm determinism breaks on edge cases.** Graphs with tied barycenter values
  (two nodes exactly equal weight) could sort differently across Python's `sort()` on
  dict iteration order. Mitigation: use `key=lambda n: (barycenter[n], n.id)` — the
  node ID as a stable tiebreaker throughout.
- **Cap threshold produces confusing truncation.** A 65-node diagram silently exits 1
  with no partial output; the planner doesn't know why the render agent fell back.
  Mitigation: the exit-1 stderr message names the cap and suggests splitting the
  diagram.
- **`mermaid_source` contains shell-special characters.** When the orchestrator passes
  `mermaid_source` via `--source "..."` on the command line, embedded newlines or
  quotes can break the shell. Mitigation: the `--source @file` form writes
  `mermaid_source` to a tempfile first; document this pattern in the orchestrator
  template.
- **sequenceDiagram parser complexity.** `alt/loop/opt` blocks, activation boxes, and
  notes-over produce significantly more complex parse state than flowchart. If the
  sequenceDiagram parser is under-specified, the T2 fixture tests will fail early.
  Mitigation: start with the simplest possible lifeline layout (participants +
  messages only, no boxes) that passes the fixture; log exit 1 for complex constructs.
- **Proof worksheet row-count estimator.** `card_rows()` in `proof_worksheet.py`
  estimates card height for chunk layout. Adding `mermaid_source` to the display does
  not change `card_rows()` — this is intentional (the code block is a display
  annotation, not a content card row). If future work uses `card_rows()` for overflow
  detection on diagram cards, this will need revisiting. Noted in `card_rows()` code.

---

## Changelog

- 2026-07-16: initial plan.
