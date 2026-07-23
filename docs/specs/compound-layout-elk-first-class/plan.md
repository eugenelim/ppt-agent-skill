# Plan: Compound Layout — ELK First-Class Subgraphs

## Task 1: [elk_adapter.py] Per-compound-node elk.direction

**Approach:** In `_to_elk_json`, the group loop builds `g_node`. Currently all groups inherit `shared_layout_opts` which has the root-level `elk.direction`. Override it per group with the group's own `local_direction`.

**Done when:** ELK JSON for the `flowchart-inner-direction` fixture has `"elk.direction": "RIGHT"` on the Pipeline compound node.

**Tests:**
```python
# test_elk_adapter.py or inline
g = LayoutGroup(id="p", parent_id=None, label="Pipeline", label_width=80, label_height=20,
                padding=16, local_direction="LR", minimum_width=0, minimum_height=0)
elk_json = _to_elk_json(LayoutGraph(nodes=[], groups=[g], edges=[], direction="TB"))
# The "p" child should have elk.direction=RIGHT in its layoutOptions
p_child = next(c for c in elk_json["children"] if c["id"] == "p")
assert p_child["layoutOptions"]["elk.direction"] == "RIGHT"
```

## Task 2: [elk_adapter.py] Empty-group minimum size

**Approach:** After building `g_node`, check if `group_children = children_by_parent.setdefault(g.id, [])` is empty. If so, set `g_node["width"]` and `g_node["height"]` to ensure the group renders as a visible labeled box.

Minimum width: `max(80 + 2*_GROUP_PAD_X, g.label_width + 2*_GROUP_PAD_X)`
Minimum height: `pad_top + _GROUP_PAD_Y_BOT`

**Done when:** ELK JSON for the empty group in `flowchart-empty-subgraph` has `"width"` and `"height"` set.

**Tests:**
```python
g = LayoutGroup(id="empty", parent_id=None, label="Empty Group", label_width=80,
                label_height=20, padding=16, local_direction="TB", minimum_width=0, minimum_height=0)
elk_json = _to_elk_json(LayoutGraph(nodes=[], groups=[g], edges=[], direction="TB"))
empty_child = next(c for c in elk_json["children"] if c["id"] == "empty")
assert "width" in empty_child and empty_child["width"] > 0
assert "height" in empty_child and empty_child["height"] > 0
```

## Task 3: [_strategies.py] Remove _has_inner_direction guard

**Approach:** Delete lines that check `_has_inner_direction` and raise an exception. The variable computation can remain but is now informational only.

**Done when:** `_compile_flowchart` does not raise for `flowchart-inner-direction` and proceeds to the ELK path (confirmed by `_elk_metadata_algo == "ELK-layered"` in the result, or by checking that `_use_elk` is True for that fixture).

**Tests:** No stub needed — functional test in task 5.

## Task 4: [_strategies.py] Populate _elk_grp_bboxes from ELK result

**Approach:**
1. In the `try` block, after `_elk_result = _layout_with_elk(...)` and the node x/y copy loop, add:
   ```python
   _elk_grp_bboxes = {
       gid: [gl.boundary_bounds.x, gl.boundary_bounds.y,
             gl.boundary_bounds.x + gl.boundary_bounds.w,
             gl.boundary_bounds.y + gl.boundary_bounds.h]
       for gid, gl in _elk_result.group_layouts.items()
   }
   ```

2. In `if _use_elk:` block, replace the large block (lines ~5197–5238) that calls `_compute_group_bboxes` and does containment expansion with:
   ```python
   _grp_bboxes = _elk_grp_bboxes or {}
   _elk_pad = int(_init_cfg.get("diagram_padding", CANVAS_PAD))
   _all_x1 = [n.x + (n.width or NODE_W) for n in nodes.values() if not n.is_dummy]
   _all_y1 = [n.y + _node_render_h(n) for n in nodes.values() if not n.is_dummy]
   for _b in _grp_bboxes.values():
       _all_x1.append(_b[2])
       _all_y1.append(_b[3])
   canvas_w = (int(max(_all_x1)) + _elk_pad) if _all_x1 else _elk_pad * 2
   canvas_h = (int(max(_all_y1)) + _elk_pad) if _all_y1 else _elk_pad * 2
   ```

**Done when:** `_grp_bboxes` on the ELK path comes from ELK result, not from `_compute_group_bboxes`. Verified by checking that empty groups have non-zero bounds in the FinalizedLayout.

**Tests:**
```python
# Integration test: empty group has non-zero bbox
layout = _compile_flowchart(EMPTY_SUBGRAPH_SRC, ...).layout
assert "_g0" in layout.group_layouts  # Empty group
gl = layout.group_layouts["_g0"]
assert gl.boundary_bounds.w > 0
assert gl.boundary_bounds.h > 0
assert not (gl.boundary_bounds.x == 0 and gl.boundary_bounds.y == 0)  # not at origin
```

## Task 5: [tests] Strengthen and fix compound layout tests

**Approach:**

### New tests (add to `TestGroupRegressions`):

```python
def test_empty_subgraph_groups_non_overlapping(self):
    """Both groups rendered with non-zero area; neither at origin; no overlap."""
    from mermaid_render.layout._strategies import _compile_flowchart
    with open(FIXTURE_EMPTY_SUBGRAPH) as f:
        src = f.read()
    layout = _compile_flowchart(src, 900, None).layout
    gls = list(layout.group_layouts.values())
    assert len(gls) >= 2
    for gl in gls:
        b = gl.boundary_bounds
        assert b.w > 0 and b.h > 0
        assert not (b.x == 0 and b.y == 0), "group at canvas origin"
    # No pairwise overlap
    for i, g1 in enumerate(gls):
        for g2 in gls[i+1:]:
            b1, b2 = g1.boundary_bounds, g2.boundary_bounds
            x_overlap = b1.x < b2.x + b2.w and b2.x < b1.x + b1.w
            y_overlap = b1.y < b2.y + b2.h and b2.y < b1.y + b1.h
            assert not (x_overlap and y_overlap), "groups overlap"

def test_groups_complex_member_containment(self):
    """Each group contains all its declared member nodes."""
    from mermaid_render.layout._strategies import _compile_flowchart
    with open(FIXTURE_GROUPS_COMPLEX) as f:
        src = f.read()
    layout = _compile_flowchart(src, 900, None).layout
    for gid, gl in layout.group_layouts.items():
        b = gl.boundary_bounds
        for mid in gl.member_ids:
            if mid not in layout.node_layouts:
                continue
            nb = layout.node_layouts[mid].outer_bounds
            assert b.x <= nb.x and nb.x + nb.w <= b.x + b.w, f"{mid} x outside {gid}"
            assert b.y <= nb.y and nb.y + nb.h <= b.y + b.h, f"{mid} y outside {gid}"
```

### Updated tests:

`TestTBInnerLROuter.test_tb_inner_members_same_x`: ELK may place P, Q, R at the same x (TB inner in LR outer). Keep this test.

`TestNestedGroupAsUnit.test_inner_members_at_same_y_as_outer_direct`: ELK LR-outer layout puts items in layers; A,B (inside Inner) may have y offset relative to C,D. Relax to: "all items are within the vertical span of Outer group" — i.e., they're all contained in Outer's boundary. Or remove and replace with a containment check.

**Done when:** `pytest tests/test_compound_layout.py` exits 0.
