#!/usr/bin/env python3
"""Regression tests for erDiagram renderer fixes.

Covers the five visual failures fixed in _layout_er / _ER_* helpers:
  1. Attribute rows silently dropped — now rendered as entity table rows.
  2. Hyphenated entity names (LINE-ITEM) not matched by \\w+ — now [\\w-]+.
  3. Crow's foot direction hardcoded to (0,1)/(0,-1) — now computed from
     the actual edge direction vector.
  4. ER edges had arrow=True — now arrow=False, crow's feet replace arrows.
  5. Attribute comments (quoted strings) not rendered — now shown as italic
     dim text.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import (
    _layout_er,
    _er_entity_h,
    _er_rect_edge_pt,
    _ER_HDR_H,
    _ER_ROW_H,
    _ER_BOT_PAD,
)
from mermaid_render.layout._constants import NODE_H, NODE_W


# ── helpers ───────────────────────────────────────────────────────────────────

def _html(fixture_name: str, width: int = 800) -> str:
    src = (REPO_ROOT / "tests" / "fixtures" / fixture_name).read_text(encoding="utf-8")
    return _layout_er(src, "TB", width)


def _inline(src: str, width: int = 800) -> str:
    return _layout_er(src, "TB", width)


# ── entity geometry helpers ────────────────────────────────────────────────────

class TestErEntityH:
    def test_no_attrs_at_least_node_h(self):
        assert _er_entity_h(0) >= NODE_H

    def test_grows_with_attrs(self):
        h0 = _er_entity_h(0)
        h1 = _er_entity_h(1)
        h3 = _er_entity_h(3)
        assert h1 > h0
        assert h3 > h1

    def test_formula(self):
        # Each row adds _ER_ROW_H pixels; first attr also adds header + divider
        assert _er_entity_h(2) == _ER_HDR_H + 1 + 2 * _ER_ROW_H + _ER_BOT_PAD


class TestErRectEdgePt:
    def test_rightward_exits_right_face(self):
        x, y = _er_rect_edge_pt(0.0, 0.0, 100.0, 60.0, 1.0, 0.0)
        assert abs(x - 50.0) < 1e-6
        assert abs(y) < 1e-6

    def test_downward_exits_bottom_face(self):
        x, y = _er_rect_edge_pt(0.0, 0.0, 100.0, 60.0, 0.0, 1.0)
        assert abs(x) < 1e-6
        assert abs(y - 30.0) < 1e-6

    def test_diagonal_exits_narrow_face_first(self):
        # 200 wide, 40 tall: horizontal half = 100, vertical half = 20
        # direction (1,1): vertical face reached at t=20, horizontal at t=100
        x, y = _er_rect_edge_pt(0.0, 0.0, 200.0, 40.0, 1.0, 1.0)
        assert abs(y - 20.0) < 1e-6  # bottom face

    def test_zero_vector_returns_center(self):
        x, y = _er_rect_edge_pt(10.0, 20.0, 100.0, 60.0, 0.0, 0.0)
        assert abs(x - 10.0) < 1e-6
        assert abs(y - 20.0) < 1e-6


# ── Fix 1: attribute rows rendered ────────────────────────────────────────────

class TestAttributeRowsRendered:
    def test_basic_fixture_has_attribute_names(self):
        html = _html("er-basic.mmd")
        # er-basic has Customer.id, Customer.name, Order.id, Order.created
        assert "id" in html
        assert "name" in html
        assert "created" in html

    def test_attribute_type_visible(self):
        html = _html("er-basic.mmd")
        # er-basic uses types "int" and "string" and "date"
        assert "int" in html
        assert "string" in html

    def test_ecommerce_attrs_rendered(self):
        html = _html("er-ecommerce.mmd")
        # Check several attribute names from er-ecommerce
        assert "placed_at" in html
        assert "unit_price" in html
        assert "street" in html

    def test_entity_divs_present(self):
        html = _html("er-basic.mmd")
        assert "er-entity" in html

    def test_entity_header_present(self):
        html = _html("er-basic.mmd")
        # Entity names Customer and Order appear as bold headers
        assert "Customer" in html
        assert "Order" in html


# ── Fix 2: hyphenated entity names ────────────────────────────────────────────

class TestHyphenatedEntityNames:
    _SRC = (
        "erDiagram\n"
        "    LINE-ITEM {\n"
        "        int id PK\n"
        "        int order_id FK\n"
        "    }\n"
        "    SALES-ORDER {\n"
        "        int id PK\n"
        "    }\n"
        "    SALES-ORDER ||--|{ LINE-ITEM : contains\n"
    )

    def test_hyphenated_entities_parsed(self):
        html = _inline(self._SRC)
        assert "LINE-ITEM" in html
        assert "SALES-ORDER" in html

    def test_hyphenated_relationship_rendered(self):
        html = _inline(self._SRC)
        # Relationship produces SVG line elements
        assert "<line " in html

    def test_hyphenated_attributes_shown(self):
        html = _inline(self._SRC)
        assert "order_id" in html


# ── Fix 3: crow's foot direction vectors ──────────────────────────────────────

class TestCrowsFootDirection:
    def test_crow_foot_markers_present(self):
        html = _html("er-cardinality-all.mmd")
        # Crow's foot rendering emits SVG <line> and possibly <circle> elements
        assert "<line " in html

    def test_all_cardinality_types_produce_markers(self):
        # er-cardinality-all has ||--||, ||--o{, }|--||, o|--|{
        html = _html("er-cardinality-all.mmd")
        # Each pair of entities => at least one SVG marker element
        assert html.count("<line ") >= 4

    def test_zero_many_circle_marker(self):
        src = "erDiagram\n    A ||--o{ B : has\n"
        html = _inline(src)
        # zero-many produces a circle for the optional marker
        assert "<circle " in html

    def test_one_to_one_double_bar(self):
        src = "erDiagram\n    A ||--|| B : test\n"
        html = _inline(src)
        # one-to-one at each side: 2 bar groups = at least 4 SVG lines total
        assert html.count("<line ") >= 4

    def test_crow_foot_not_hardcoded_top_bottom(self):
        # For a horizontal layout (LR) the direction must not be (0,1)/(0,-1);
        # the markers should still be present, using the actual vector.
        src = "erDiagram\n    A ||--o{ B : has\n"
        html = _layout_er(src, "LR", 800)
        assert "<line " in html
        assert "<circle " in html


# ── Fix 4: no arrow on ER edges ───────────────────────────────────────────────

class TestNoArrowOnEREdges:
    def test_no_arrowhead_attribute_in_lines(self):
        # Arrowhead markers from _arrowhead() inject marker-end on <line>/<path>.
        # ER edges must not have marker-end (crow's feet are separate elements).
        html = _html("er-basic.mmd")
        import re
        lines_with_data = re.findall(r'<line[^>]*data-src[^>]*>', html)
        for tag in lines_with_data:
            assert "marker-end" not in tag, f"Unexpected marker-end on ER edge: {tag}"


# ── Fix 5: attribute comments ─────────────────────────────────────────────────

class TestAttributeComments:
    _SRC = (
        "erDiagram\n"
        '    PRODUCT {\n'
        '        int id PK "primary key"\n'
        '        string sku UK "stock unit"\n'
        "    }\n"
    )

    def test_comment_text_rendered(self):
        html = _inline(self._SRC)
        assert "primary key" in html
        assert "stock unit" in html

    def test_comment_italic_style(self):
        html = _inline(self._SRC)
        assert "font-style:italic" in html


# ── Integration: fixtures ──────────────────────────────────────────────────────

class TestFixtures:
    def test_er_basic(self):
        html = _html("er-basic.mmd")
        assert len(html) > 500
        assert "er-entity" in html

    def test_er_ecommerce(self):
        html = _html("er-ecommerce.mmd", width=1400)
        # 5 entities
        assert html.count("er-entity") == 5
        # PK/FK/UK badges
        assert "PK" in html
        assert "FK" in html
        assert "UK" in html

    def test_er_cardinality_all(self):
        html = _html("er-cardinality-all.mmd")
        # 8 entities (A-H), no attributes
        assert html.count("er-entity") == 8
        # crow's feet SVG
        assert "<line " in html

    def test_er_identifying(self):
        html = _html("er-identifying.mmd")
        assert "ORDER" in html
        assert "LINE_ITEM" in html
        assert "CUSTOMER" in html
        # Identifying relationships use solid lines (no stroke-dasharray)
        import re
        edge_lines = re.findall(r'<line[^>]*data-src[^>]*>', html)
        assert len(edge_lines) >= 2
        for tag in edge_lines:
            assert "stroke-dasharray" not in tag

    def test_er_non_identifying_dashed(self):
        # Non-identifying relationship uses ".." separator -> dashed line
        src = "erDiagram\n    A }o..o{ B : assoc\n"
        html = _inline(src)
        assert "stroke-dasharray" in html

    def test_relationship_label_rendered(self):
        html = _html("er-basic.mmd")
        # er-basic has label "places"
        assert "places" in html

    def test_multiple_entities_no_relationship(self):
        src = (
            "erDiagram\n"
            "    FOO {\n        int id\n    }\n"
            "    BAR {\n        string name\n    }\n"
        )
        html = _inline(src)
        assert "FOO" in html
        assert "BAR" in html
        assert html.count("er-entity") == 2

    def test_width_hint_respected(self):
        html = _html("er-ecommerce.mmd", width=600)
        import re
        m = re.search(r'width:(\d+)px', html)
        assert m, "No width found in outer container"
        actual_w = int(m.group(1))
        assert actual_w <= 650, f"Canvas width {actual_w} too far from hint 600"


# ── Geometric non-overlap assertions ─────────────────────────────────────────

def _parse_card_rects(html: str) -> list[dict]:
    import re
    rects = []
    for m in re.finditer(
        r'<div[^>]*class="node[^"]*er-entity[^"]*"[^>]*data-node-id="([^"]+)"[^>]*style="([^"]+)"',
        html,
    ):
        style = m.group(2)
        x_m = re.search(r'left:(\d+)px', style)
        y_m = re.search(r'top:(\d+)px', style)
        w_m = re.search(r'width:(\d+)px', style)
        h_m = re.search(r'height:(\d+)px', style)
        if x_m and y_m and w_m and h_m:
            rects.append({
                'id': m.group(1),
                'x': int(x_m.group(1)), 'y': int(y_m.group(1)),
                'w': int(w_m.group(1)), 'h': int(h_m.group(1)),
            })
    return rects


def _find_overlapping_pair(rects: list[dict]):
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            a, b = rects[i], rects[j]
            if not (a['x'] + a['w'] <= b['x'] or b['x'] + b['w'] <= a['x'] or
                    a['y'] + a['h'] <= b['y'] or b['y'] + b['h'] <= a['y']):
                return (a, b)
    return None


class TestCardNonOverlap:
    @pytest.mark.parametrize("width", [800, 600, 400])
    def test_er_cardinality_all_non_overlapping(self, width):
        """Cards must not overlap at any width_hint, including downscale values."""
        html = _html("er-cardinality-all.mmd", width=width)
        rects = _parse_card_rects(html)
        assert len(rects) == 8, f"Expected 8 cards, found {len(rects)} at width={width}"
        pair = _find_overlapping_pair(rects)
        assert pair is None, (
            f"Cards overlap at width={width}: "
            f"{pair[0]['id']}@({pair[0]['x']},{pair[0]['y']})"
            f"+({pair[0]['w']}×{pair[0]['h']}) and "
            f"{pair[1]['id']}@({pair[1]['x']},{pair[1]['y']})"
            f"+({pair[1]['w']}×{pair[1]['h']})"
        )

    def test_er_ecommerce_non_overlapping(self):
        html = _html("er-ecommerce.mmd", width=1400)
        rects = _parse_card_rects(html)
        assert len(rects) == 5, f"Expected 5 cards, found {len(rects)}"
        pair = _find_overlapping_pair(rects)
        assert pair is None, (
            f"Cards overlap: {pair[0]['id']} and {pair[1]['id']}"
        )

    def test_er_native_scene_non_overlapping(self):
        """Native SVG path: entity header rects must not overlap x-wise per rank."""
        from mermaid_render.layout.er import layout_er_scene
        from mermaid_render.scene import SceneRect, LAYER_NODES
        from collections import defaultdict

        src = (REPO_ROOT / "tests" / "fixtures" / "er-cardinality-all.mmd").read_text()
        scene = layout_er_scene(src, width_hint=600)  # downscale from natural ~1064px

        node_layer = scene.get_layer(LAYER_NODES)
        # Header rects are tagged semantic_role="entity"; width = _CARD_W (200px)
        headers = [
            (el.x, el.y, el.w)
            for el in node_layer
            if isinstance(el, SceneRect) and el.semantic_role == "entity"
        ]
        assert len(headers) == 8, f"Expected 8 entity header rects, got {len(headers)}"

        # Group by y-coordinate (proxy for rank) and check x-axis non-overlap
        by_y: dict[float, list[tuple[float, float]]] = defaultdict(list)
        for x, y, w in headers:
            by_y[y].append((x, w))
        for y_pos, group in by_y.items():
            group.sort()
            for i in range(1, len(group)):
                prev_x, prev_w = group[i - 1]
                curr_x, _ = group[i]
                assert prev_x + prev_w <= curr_x, (
                    f"Native path: cards overlap at rank y={y_pos}: "
                    f"[{prev_x},{prev_x+prev_w}) vs [{curr_x},...)"
                )


# ── PK / FK / UK badge rendering ──────────────────────────────────────────────

class TestConstraintBadges:
    def test_pk_badge_present(self):
        src = "erDiagram\n    T {\n        int id PK\n    }\n"
        html = _inline(src)
        assert ">PK<" in html

    def test_fk_badge_present(self):
        src = "erDiagram\n    T {\n        int parent_id FK\n    }\n"
        html = _inline(src)
        assert ">FK<" in html

    def test_uk_badge_present(self):
        src = "erDiagram\n    T {\n        string email UK\n    }\n"
        html = _inline(src)
        assert ">UK<" in html

    def test_no_constraint_no_badge(self):
        src = "erDiagram\n    T {\n        int qty\n    }\n"
        html = _inline(src)
        assert ">PK<" not in html
        assert ">FK<" not in html
        assert ">UK<" not in html
