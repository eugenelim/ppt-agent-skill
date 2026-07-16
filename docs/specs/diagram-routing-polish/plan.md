# Diagram Routing Polish — plan

Status: Executing

## Task list

### T0 — Add `_node_render_h` helper (shared by T1, T2, T3, T4)
**Verification:** TDD  
**Depends on:** none  
**Touches:** `scripts/mermaid_layout.py`

Tests:
- Node with single-line label → returns `NODE_H`.
- Node with 3-line label → returns `NODE_H + (3-1)*18 = NODE_H + 36`.
- Node with tech label (has `|`) → returns `NODE_H + 16`.
- Node with icon → returns `NODE_H + 20`.

Approach: Add `_node_render_h(n: _Node) -> int` below `_wrap_label`. This function becomes the **single source of truth** — T2 will replace the duplicate inline `extra_h` in `_render_graph_fragment` with a call to it:
```python
def _node_render_h(n: _Node) -> int:
    if "|" in n.label:
        main_label, _ = n.label.split("|", 1)
    else:
        main_label = n.label
    main_label = main_label.strip()
    lines = _wrap_label(main_label)
    extra_h = max(0, (len(lines) - 1) * 18)
    if n.icon:
        extra_h = max(extra_h, 20)
    if "|" in n.label:
        extra_h += 16
    return NODE_H + extra_h
```
Note: uses `n.icon` (field on `_Node`) not `_load_icon(n.icon)` (so a missing icon file still contributes to height — intentional, since icon space is reserved at parse time).

### T1 — Fix `_SPEC_RE` bracket-in-quoted-label (Bug 4)
**Verification:** TDD  
**Depends on:** none  
**Touches:** `scripts/mermaid_layout.py`

Tests:
- `_parse_spec('NODE["name\\n[inner]"]')` → label == `'name\n[inner]'`.
- `_parse_spec('A["Simple"]')` → label == `'Simple'` (existing behavior preserved).
- `_parse_spec('A[unquoted]')` → label == `'unquoted'` (unquoted path still works).

Approach: Add `rect_q`, `round_q`, `cylinder_q` alternatives to `_SPEC_RE` using `"[^"]+"` delimiter, listed BEFORE the bracket-terminated variants:
```python
_SPEC_RE = re.compile(
    r'^(?P<id>[A-Za-z_][A-Za-z0-9_\-\.]*)'
    r'(?:'
    r'\[\((?P<cylinder_q>"[^"]*")\)\]'    # [("quoted")]
    r'|\[\((?P<cylinder>[^\)]*)\)\]'      # [(unquoted)]
    r'|\(\((?P<circle>[^\)]*)\)\)'        # ((circle))
    r'|\["(?P<rect_q>[^"]*)"\]'           # ["quoted rect"]
    r'|\[(?P<rect>[^\[\]]*)\]'            # [rect]
    r'|\("(?P<round_q>[^"]*)"\)'          # ("quoted round")
    r'|\((?P<round>[^\(\)]*)\)'           # (round)
    r'|\{(?P<diamond>[^\{\}]*)\}'         # {diamond}
    r'|>(?P<flag>[^\]]*)\]'              # >flag]
    r')?'
)
```
Update `_parse_spec` loop to include `rect_q`, `round_q`, `cylinder_q` mapped to shapes `rect`, `round`, `cylinder`.

### T2 — Fix group bounding box + canvas height (Bugs 5 & 6)
**Verification:** TDD  
**Depends on:** T0 (`_node_render_h` must exist)  
**Touches:** `scripts/mermaid_layout.py`

Tests:
- Build a node with 3-line label (height=92px); group should have `gh >= 92 + GROUP_PAD_Y_TOP + GROUP_PAD_Y_BOT`.
- `_layout_graph_topology` with a 3-line node at last rank → canvas_h > `CANVAS_PAD*2 + (max_rank+1)*(NODE_H+RANK_GAP)`.

Approach:
In `_render_graph_fragment`:
- Replace `max(n.y + NODE_H for n in mbrs)` with `max(n.y + _node_render_h(n) for n in mbrs)` in group `gh` calculation.
- Replace the inline `extra_h` / `node_h` block (lines ~714-719) with `node_h = _node_render_h(n)` — single source of truth.

In `_layout_graph_topology`, AFTER width-hint scaling and BEFORE calling `_render_graph_fragment`:
```python
real_nodes = [n for n in nodes.values() if not n.is_dummy]
canvas_h = max((n.y + _node_render_h(n) for n in real_nodes), default=CANVAS_PAD) + CANVAS_PAD
```
Then pass this corrected `canvas_h` to `_render_graph_fragment`.

### T3 — `flowchart LR` direction support (Bug 7 + Bug 8)
**Verification:** TDD  
**Depends on:** T0 (`_node_render_h` for variable-pitch LR), T4 (T4 rewrites `_route_edges` arrowhead calls; T3 adds LR branches to the same function — do T4 first to avoid same-function collision)  
**Touches:** `scripts/mermaid_layout.py`

Tests:
- `_dispatch("flowchart LR\nA-->B-->C", None, 800)`: node A's `left` < node B's `left` (rank grows rightward).
- `_dispatch("flowchart LR\nA[\"line1\\nline2\"]-->B", None, 800)`: node B's `top` > node A's `top` + `NODE_H` (no y-overlap even with multi-line A... wait, A is a 2-line node in col=0 but B should be col=0 too if they're at different ranks — actually in LR, rank→X, col→Y. A is rank=0, col=0 and B is rank=1, col=0 — same col but different x. So y-overlap concern is for nodes at same rank with different cols).

Let me reconsider: in LR layout, nodes at the same rank have the same X, but different cols have different Y. Multi-line nodes in the same rank (same X, different col positions) could overlap in Y if we use fixed pitch. The test:
- `_dispatch("flowchart LR\nA[\"line1\\nline2\"]-->C\nB[\"line1\\nline2\\nline3\"]-->C", None, 800)`: nodes A and B are at rank=0, different cols. Check that B's `top` > A's `top` + actual rendered height of A.

Approach: Direction-aware `_assign_coordinates(nodes, direction)`:
```python
def _assign_coordinates(nodes: dict[str, _Node], direction: str = "TB") -> tuple[int, int]:
    is_lr = direction.upper() in ("LR", "RL")
    if not is_lr:
        col_pitch = NODE_W + COL_GAP
        row_pitch = NODE_H + RANK_GAP
        for n in nodes.values():
            n.x = CANVAS_PAD + n.col * col_pitch
            n.y = CANVAS_PAD + n.rank * row_pitch
        max_col = max(n.col for n in nodes.values())
        max_rank = max(n.rank for n in nodes.values())
        canvas_w = CANVAS_PAD * 2 + (max_col + 1) * col_pitch - COL_GAP
        canvas_h = CANVAS_PAD * 2 + (max_rank + 1) * row_pitch - RANK_GAP
        return canvas_w, canvas_h
    else:
        # LR: rank→X (fixed pitch), col→Y (variable pitch via _node_render_h)
        max_rank = max(n.rank for n in nodes.values())
        rank_pitch = NODE_W + RANK_GAP
        for n in nodes.values():
            n.x = CANVAS_PAD + n.rank * rank_pitch
        # Variable Y pitch: accumulate col heights
        col_to_nodes: dict[int, list] = {}
        for n in nodes.values():
            col_to_nodes.setdefault(n.col, []).append(n)
        y_cursor = CANVAS_PAD
        for col in sorted(col_to_nodes):
            col_h = max(_node_render_h(n) for n in col_to_nodes[col])
            for n in col_to_nodes[col]:
                n.y = y_cursor
            y_cursor += col_h + COL_GAP
        canvas_w = CANVAS_PAD * 2 + (max_rank + 1) * rank_pitch - RANK_GAP
        canvas_h = y_cursor + CANVAS_PAD - COL_GAP
        return canvas_w, canvas_h
```

Direction-aware `_route_edges(nodes, edges, canvas_w, direction="TB")`:
- Compute LR bottom-lane y: `bottom_lane_y = max(n.y + _node_render_h(n) for n in nodes.values() if not n.is_dummy) + 32` (mirrors right_lane_x pattern, no extra param needed).
- For LR forward edges (`is_lr and not reversed and rank_gap >= 0`): exit right of src, enter left of dst; fan in height dimension using `_node_render_h`; horizontal Bézier with control points at 1/3 and 2/3 of horizontal span.
- For LR back-edges: bottom-lane bypass: `M sx sy V bottom_lane_y H dx V dy`.

Thread `direction`: `_layout_graph_topology` → passes `direction` to both `_assign_coordinates` and `_render_graph_fragment`. Add `direction="TB"` param to `_render_graph_fragment`; inside, pass to `_route_edges(nodes, edges, canvas_w, direction)`.

For LR fan distribution (concern 5): pass actual node height to `_fan_offset`:
```python
# LR fan-out: distribute across src height
out_h = _node_render_h(s)
out_offset = _fan_offset(out_idx, len(out_list), node_w=out_h, pad=16)
```

### T4 — Fix `right_lane_x` + `_arrowhead` proportions (AC-6, AC-7)
**Verification:** TDD  
**Depends on:** none  
**Touches:** `scripts/mermaid_layout.py`

Tests:
- Nodes at max x=300, NODE_W=160: `right_lane_x >= 300+160+32 = 492`.
- `_arrowhead(100,100,0,1)` (no extra kwargs) → half-width == 4 (parse polygon points: base is 8px back, wing ±4px perp).
- `_arrowhead(100,100,0,1, back=10, half_w=5)` → half-width == 5.
- `_arrowhead(100,100,0,1, back=10, half_w=6)` → half-width == 6 (lifeline preserved value).

Approach:
- Update `_arrowhead(tip_x, tip_y, dx, dy, back=8, half_w=4)`: use params directly instead of hardcoded 10/6.
- Update `right_lane_x`: `right_lane_x = max((n.x + NODE_W for n in nodes.values() if not n.is_dummy), default=canvas_w) + 32`.
- Update `_route_edges` arrowhead calls: for thick edges pass `back=10, half_w=5`; for normal edges use defaults.
  ```python
  ah_kw = {"back": 10, "half_w": 5} if e.style == "thick" else {}
  ah = _arrowhead(x2, y2, dx, dy, **ah_kw) if e.arrow else None
  ```
- Update `_layout_lifeline` arrowhead calls (~lines 1149, 1155) to pass explicit `back=10, half_w=6` to preserve existing size.

### T5 — Edge label perpendicular offset + rotation (AC-8)
**Verification:** TDD  
**Depends on:** T4 (arrowhead/route_edges changes mean T5 adds to same function)  
**Touches:** `scripts/mermaid_layout.py`

Tests:
- Vertical forward edge (x1==x2, y2>y1): `spec["rot"] == 90`, `spec["lx"] == mid_x + 14` (right perpendicular).
- Near-horizontal forward edge (large dx, small dy): `spec["rot"] == 0`, `spec["ly"] < mid_y` (offset above line).

Approach: In the forward Bézier block of `_route_edges` (TB mode):
```python
edge_dx = float(x2 - x1)
edge_dy = float(y2 - y1)
edge_len = math.hypot(edge_dx, edge_dy) or 1.0
# Right perpendicular (90deg CW from direction)
perp_x = edge_dy / edge_len
perp_y = -edge_dx / edge_len
LABEL_PERP = 14
lx = int(mid_x + perp_x * LABEL_PERP)
ly = int(mid_y + perp_y * LABEL_PERP)
rot = 90 if abs(edge_dy) > abs(edge_dx) * 1.5 else 0
```

Also add `rot` to back-edge and self-loop result dicts (rot=0 for those).

Update `_render_graph_fragment` label rendering:
```python
rot = spec.get("rot", 0)
rot_part = f" rotate({rot}deg)" if rot else ""
parts.append(
    f'<span ... style="... transform:translate(-50%,-50%){rot_part};">'
)
```

### T6 — Node shadow + `diagram.md` colour-role section (AC-9)
**Verification:** TDD + Goal-based  
**Depends on:** none  
**Touches:** `scripts/mermaid_layout.py`, `references/blocks/diagram.md`

Tests:
- `_render_graph_fragment` output contains `box-shadow:var(--node-shadow,none)` in a node div.
- `grep -c "\-\-node-shadow" references/blocks/diagram.md` > 0 (in the CSS contract block).
- `grep -c "节点颜色角色" references/blocks/diagram.md` > 0.

Approach:
- In `_render_graph_fragment` node div: add `box-shadow:var(--node-shadow,none); `.
- In `diagram.md` `.diagram{}` block: add `--node-shadow: var(--card-shadow, none);`.
- Append "节点颜色角色 / Semantic colour-role guidance" section after "Mermaid 渲染器语义标注".

### T7 — Update `architect-diagram` SKILL.md (AC-10)
**Verification:** Goal-based  
**Depends on:** none  
**Touches:** `~/.claude/skills/architect-diagram/SKILL.md`

Done when: `:::external` in file; `--node-accent` NOT in file.

Approach: In Step 7 self-check, append a "PPT rendering conventions" sub-note (3-4 lines) listing `:::external`, `|`, `%% title:` as PPT-specific extensions. No colour variable names.

### T8 — New tests: `test_mermaid_routing_polish()` (AC-11)
**Verification:** TDD (red stubs first)  
**Depends on:** T0–T7 (tests cover all ACs)  
**Touches:** `scripts/test_diagram_qa.py`

Tests (≥10 checks):
1. `_parse_spec('NODE["name\\n[inner]"]')` → label contains `[inner]` (AC-1)
2. `_node_render_h` for 3-line node > NODE_H (AC-2)
3. Group box `gh` ≥ tallest node height in group (AC-2)
4. `canvas_h` > fixed formula when multi-line nodes present (AC-3)
5. LR diagram: node A left < node B left (AC-4)
6. LR diagram with multi-line node: no y-overlap (AC-5)
7. `right_lane_x` ≥ max node right edge + 32 (AC-6)
8. Normal arrowhead half-width == 4 (AC-7)
9. Thick arrowhead half-width == 5 (AC-7)
10. Vertical edge label `rot == 90` (AC-8)
11. Node div contains `--node-shadow` (AC-9)
12. `translate(-50%,-50%)` in edge label style (AC-8)

## Declined patterns (plan)

- Tempted to implement same-rank (rank_gap==0) orthogonal routing: declining — this case never fires in production (confirmed by adversarial review).
- Tempted to change `_arrowhead` positional defaults globally: declining — use `back`/`half_w` keyword params; lifeline call sites pass explicit values to stay unchanged.
- Tempted to merge T3 and T5 (both edit `_route_edges`): declining — T3 adds direction handling (structural) and T5 adds label offset (additive); doing T3 first prevents merge conflict.
- Tempted to also handle `flowchart RL` (right-to-left): declining — RL diagrams are rare; LR covers the user's case; RL can follow later.

## Resolve-vs-surface disposition record

All open items resolved with referent (see spec.md for full record).
