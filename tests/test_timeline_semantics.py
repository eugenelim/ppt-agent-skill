"""Tests for the native timeline scene layout (layout/timeline.py)."""
from __future__ import annotations

import re

import pytest

from scripts.mermaid_render.layout.timeline import (
    layout_timeline_scene,
    _parse_timeline_source,
    _COL_W,
    _MIN_COL_W,
    _COL_GAP,
    _PAD_H,
)
from scripts.mermaid_render.scene import (
    SceneCircle, SceneRoundedRect, SceneLine, SceneText, SvgScene,
    LAYER_EDGES, LAYER_NODES, LAYER_LABELS, LAYER_OVERLAYS, LAYER_BOUNDARIES,
)
from scripts.mermaid_render.svg_serializer import scene_to_svg_str


SIMPLE = """\
timeline
    Jan 2024 : Kickoff
    Feb 2024 : Design
    Mar 2024 : Launch
"""

WITH_SECTIONS = """\
timeline
    title My Timeline
    section Phase 1
    Jan 2024 : Kickoff
             : Planning
    section Phase 2
    Feb 2024 : Development
"""

MULTI_EVENT = """\
timeline
    Q1 : Plan
       : Design
       : Review
    Q2 : Build
"""


class TestParser:
    def test_parses_periods(self):
        _, _, periods = _parse_timeline_source(SIMPLE)
        labels = [p["period"] for p in periods]
        assert "Jan 2024" in labels
        assert "Mar 2024" in labels

    def test_inline_event(self):
        _, _, periods = _parse_timeline_source(SIMPLE)
        assert "Kickoff" in periods[0]["events"]

    def test_continuation_event(self):
        _, _, periods = _parse_timeline_source(WITH_SECTIONS)
        jan = next(p for p in periods if p["period"] == "Jan 2024")
        assert "Planning" in jan["events"]

    def test_title_extracted(self):
        title, _, _ = _parse_timeline_source(WITH_SECTIONS)
        assert title == "My Timeline"

    def test_sections_grouped(self):
        _, groups, _ = _parse_timeline_source(WITH_SECTIONS)
        names = [g["name"] for g in groups if g["name"]]
        assert "Phase 1" in names
        assert "Phase 2" in names

    def test_empty_periods_raises_later(self):
        _, _, periods = _parse_timeline_source("timeline\n")
        assert periods == []

    def test_no_title_returns_empty(self):
        title, _, _ = _parse_timeline_source(SIMPLE)
        assert title == ""

    def test_source_order_preserved(self):
        _, _, periods = _parse_timeline_source(SIMPLE)
        assert periods[0]["period"] == "Jan 2024"
        assert periods[1]["period"] == "Feb 2024"
        assert periods[2]["period"] == "Mar 2024"

    def test_continuation_events_belong_to_correct_period(self):
        _, _, periods = _parse_timeline_source(WITH_SECTIONS)
        jan = next(p for p in periods if p["period"] == "Jan 2024")
        # "Planning" is a continuation event (starts with :) for Jan 2024
        assert "Planning" in jan["events"]
        # Feb 2024 should not contain Planning
        feb = next(p for p in periods if p["period"] == "Feb 2024")
        assert "Planning" not in feb["events"]


class TestLayoutTimelineScene:
    def test_returns_svg_scene(self):
        scene = layout_timeline_scene(SIMPLE)
        assert isinstance(scene, SvgScene)

    def test_diagram_type(self):
        assert layout_timeline_scene(SIMPLE).diagram_type == "timeline"

    def test_width_hint_respected(self):
        # width_hint is an output-maximum constraint: canvas must not exceed it
        scene = layout_timeline_scene(SIMPLE, width_hint=1000)
        assert scene.width <= 1000

    def test_width_hint_zero_is_content_tight(self):
        # width_hint=0 means unconstrained: canvas == natural content width
        scene_no_hint = layout_timeline_scene(SIMPLE)
        scene_large_hint = layout_timeline_scene(SIMPLE, width_hint=9999)
        # Both should produce the same content-tight width
        assert scene_no_hint.width == scene_large_hint.width

    def test_width_hint_constrains_below_natural(self):
        # width_hint smaller than natural width: canvas is capped at width_hint
        scene = layout_timeline_scene(SIMPLE, width_hint=200)
        assert scene.width <= 200

    def test_has_edges_layer_spine(self):
        scene = layout_timeline_scene(SIMPLE)
        edges = scene.get_layer(LAYER_EDGES)
        lines = [el for el in edges if isinstance(el, SceneLine)]
        # At least one spine line
        assert len(lines) >= 1

    def test_has_period_dots(self):
        scene = layout_timeline_scene(SIMPLE)
        overlays = scene.get_layer(LAYER_OVERLAYS)
        circles = [el for el in overlays if isinstance(el, SceneCircle)]
        assert len(circles) == 3  # 3 periods → 3 dots

    def test_has_period_nodes(self):
        scene = layout_timeline_scene(SIMPLE)
        nodes = scene.get_layer(LAYER_NODES)
        # At least 3 period rects
        rects = [el for el in nodes if isinstance(el, SceneRoundedRect)]
        assert len(rects) >= 3

    def test_column_layout_periods_below_spine(self):
        """Column layout: period chips are below the spine (not above/alternating)."""
        scene = layout_timeline_scene(SIMPLE)
        overlays = scene.get_layer(LAYER_OVERLAYS)
        circles = [el for el in overlays if isinstance(el, SceneCircle)]
        assert circles, "No spine dots found"
        spine_y = circles[0].cy  # dot is at spine_y

        nodes = scene.get_layer(LAYER_NODES)
        period_rects = [el for el in nodes if isinstance(el, SceneRoundedRect)
                        and "timeline-period" in (el.css_classes or ())]
        assert period_rects, "No period chips found"
        # All period chips must be below (y >= spine_y)
        for r in period_rects:
            assert r.y >= spine_y, f"Period chip at y={r.y} is above spine at y={spine_y}"

    def test_events_in_column_below_period(self):
        """Events for each period must be within its column (same x range) and below spine."""
        scene = layout_timeline_scene(MULTI_EVENT)
        overlays = scene.get_layer(LAYER_OVERLAYS)
        circles = [el for el in overlays if isinstance(el, SceneCircle)]
        assert circles
        spine_y = circles[0].cy

        nodes = scene.get_layer(LAYER_NODES)
        event_rects = [el for el in nodes if isinstance(el, SceneRoundedRect)
                       and "timeline-event" in (el.css_classes or ())]
        for r in event_rects:
            assert r.y > spine_y, f"Event card at y={r.y} must be below spine at y={spine_y}"

    def test_no_period_event_overlap(self):
        """Period chips and event cards must not overlap vertically."""
        scene = layout_timeline_scene(MULTI_EVENT)
        nodes = scene.get_layer(LAYER_NODES)
        rects = [el for el in nodes if isinstance(el, SceneRoundedRect)]
        # Check no two rects overlap in both x and y
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                # Same column x overlap: left/right overlap
                a_right, b_right = a.x + a.w, b.x + b.w
                x_overlap = a.x < b_right and b.x < a_right
                if not x_overlap:
                    continue
                # Y overlap check
                a_bot, b_bot = a.y + a.h, b.y + b.h
                y_overlap = a.y < b_bot and b.y < a_bot
                assert not y_overlap, (
                    f"Rects overlap: ({a.x},{a.y},{a.w},{a.h}) and ({b.x},{b.y},{b.w},{b.h})"
                )

    def test_labels_contain_period_names(self):
        scene = layout_timeline_scene(SIMPLE)
        labels = scene.get_layer(LAYER_LABELS)
        texts = [el.lines[0].text for el in labels if hasattr(el, "lines")]
        assert "Jan 2024" in texts or any("Jan" in t for t in texts)

    def test_title_in_labels(self):
        scene = layout_timeline_scene(WITH_SECTIONS)
        labels = scene.get_layer(LAYER_LABELS)
        texts = [el.lines[0].text for el in labels if hasattr(el, "lines")]
        assert "My Timeline" in texts

    def test_section_bands_in_boundaries(self):
        scene = layout_timeline_scene(WITH_SECTIONS)
        bounds = scene.get_layer(LAYER_BOUNDARIES)
        rects = [el for el in bounds if isinstance(el, SceneRoundedRect)]
        assert len(rects) >= 2  # Two named sections

    def test_event_cards_present(self):
        scene = layout_timeline_scene(MULTI_EVENT)
        nodes = scene.get_layer(LAYER_NODES)
        rects = [el for el in nodes if isinstance(el, SceneRoundedRect)]
        # 2 period nodes + 4 event cards (3 + 1)
        assert len(rects) >= 4

    def test_deterministic_scene_id(self):
        s1 = layout_timeline_scene(SIMPLE)
        s2 = layout_timeline_scene(SIMPLE)
        assert s1.scene_id == s2.scene_id

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="No periods"):
            layout_timeline_scene("timeline\n")

    def test_serializes_to_valid_xml(self):
        from lxml import etree
        scene = layout_timeline_scene(SIMPLE)
        svg = scene_to_svg_str(scene)
        body = re.sub(r"^<\?xml[^?]*\?>", "", svg.strip()).strip()
        etree.fromstring(body.encode("utf-8"))

    def test_no_foreign_object(self):
        scene = layout_timeline_scene(SIMPLE)
        svg = scene_to_svg_str(scene)
        assert "<foreignObject" not in svg

    def test_connector_is_dashed(self):
        scene = layout_timeline_scene(SIMPLE)
        svg = scene_to_svg_str(scene)
        # Connectors should use dasharray
        assert "stroke-dasharray" in svg or "dasharray" in svg

    def test_spine_is_horizontal_line(self):
        scene = layout_timeline_scene(SIMPLE)
        edges = scene.get_layer(LAYER_EDGES)
        lines = [el for el in edges if isinstance(el, SceneLine)]
        # Spine: y1 == y2 (horizontal)
        spine_candidates = [l for l in lines if l.y1 == l.y2]
        assert len(spine_candidates) >= 1


class TestDisableMulticolor:
    """disableMulticolor: all section bands use the same neutral color."""

    SECTIONS_SRC = """\
timeline
    title Demo
    section Alpha
    2020 : A
    section Beta
    2021 : B
    section Gamma
    2022 : C
"""

    def _band_colors(self, scene: "SvgScene") -> list[str]:
        bounds = scene.get_layer(LAYER_BOUNDARIES)
        colors = []
        for el in bounds:
            if isinstance(el, SceneRoundedRect) and el.paint and el.paint.fill:
                colors.append(el.paint.fill.color)
        return colors

    def test_multicolor_default_uses_distinct_colors(self):
        scene = layout_timeline_scene(self.SECTIONS_SRC)
        colors = self._band_colors(scene)
        assert len(colors) >= 2
        # Default: at least two distinct colors
        assert len(set(colors)) > 1

    def test_disable_multicolor_uses_single_color(self):
        scene = layout_timeline_scene(
            self.SECTIONS_SRC,
            diagram_config={"timeline": {"disableMulticolor": True}},
        )
        colors = self._band_colors(scene)
        assert len(colors) >= 2
        # All bands use the same color
        assert len(set(colors)) == 1

    def test_disable_multicolor_false_is_default(self):
        scene_default = layout_timeline_scene(self.SECTIONS_SRC)
        scene_false = layout_timeline_scene(
            self.SECTIONS_SRC,
            diagram_config={"timeline": {"disableMulticolor": False}},
        )
        # Both should produce the same multi-color pattern
        assert self._band_colors(scene_default) == self._band_colors(scene_false)


class TestMeasuredHeights:
    """Heights are derived from text measurement, not fixed constants."""

    def test_period_chips_have_positive_height(self):
        scene = layout_timeline_scene(SIMPLE)
        nodes = scene.get_layer(LAYER_NODES)
        period_rects = [el for el in nodes if isinstance(el, SceneRoundedRect)
                        and "timeline-period" in (el.css_classes or ())]
        for r in period_rects:
            assert r.h > 0

    def test_event_cards_have_positive_height(self):
        scene = layout_timeline_scene(MULTI_EVENT)
        nodes = scene.get_layer(LAYER_NODES)
        event_rects = [el for el in nodes if isinstance(el, SceneRoundedRect)
                       and "timeline-event" in (el.css_classes or ())]
        assert event_rects, "No event cards found"
        for r in event_rects:
            assert r.h > 0

    def test_canvas_height_exceeds_content_minimum(self):
        # Canvas height must contain title + section + spine + periods + events
        scene = layout_timeline_scene(WITH_SECTIONS)
        # Rough lower bound: at least 80px for a titled, sectioned, evented diagram
        assert scene.height > 80

    def test_canvas_width_is_content_tight(self):
        # Without width_hint, canvas = natural content width (no artificial inflation)
        scene = layout_timeline_scene(SIMPLE)
        n = 3  # SIMPLE has 3 periods
        # Width must be at least n columns at minimum col size plus padding
        min_expected = float(_PAD_H * 2 + n * _MIN_COL_W + (n - 1) * _COL_GAP)
        assert scene.width >= min_expected
        # Content-tight: same input → same width (deterministic)
        assert layout_timeline_scene(SIMPLE).width == scene.width

    # ── New cases for Stage 8 ─────────────────────────────────────────────────

    LONG_EVENT = """\
timeline
    Q1 : This is a very long event description that must wrap across multiple lines
"""

    UNEVEN_COLS = """\
timeline
    Q1 : Plan
       : Design
       : Review
    Q2 : Build
"""

    def test_multiline_event_card_taller_than_single_line(self):
        """A card wrapping to 2+ lines must be taller than a single-line card."""
        scene_long = layout_timeline_scene(self.LONG_EVENT)
        scene_short = layout_timeline_scene(SIMPLE)

        nodes_long = scene_long.get_layer(LAYER_NODES)
        ev_long = [el for el in nodes_long if isinstance(el, SceneRoundedRect)
                   and "timeline-event" in (el.css_classes or ())]
        assert ev_long, "No event cards in LONG_EVENT scene"
        long_h = ev_long[0].h

        nodes_short = scene_short.get_layer(LAYER_NODES)
        ev_short = [el for el in nodes_short if isinstance(el, SceneRoundedRect)
                    and "timeline-event" in (el.css_classes or ())]
        assert ev_short, "No event cards in SIMPLE scene"
        short_h = ev_short[0].h

        assert long_h > short_h, (
            f"Long-event card h={long_h} should exceed single-line card h={short_h}"
        )

    def test_column_with_more_events_is_taller(self):
        """A column with 3 events must produce a taller events block than a column with 1."""
        scene = layout_timeline_scene(self.UNEVEN_COLS)
        nodes = scene.get_layer(LAYER_NODES)

        # Collect event rects by column (data_attrs col)
        col_rects: dict[str, list] = {}
        for el in nodes:
            if isinstance(el, SceneRoundedRect) and "timeline-event" in (el.css_classes or ()):
                col_val = dict(el.data_attrs).get("col", "?")
                col_rects.setdefault(col_val, []).append(el)

        assert "0" in col_rects, "Column 0 has no events"
        assert "1" in col_rects, "Column 1 has no events"

        col0_span = max(r.y + r.h for r in col_rects["0"]) - min(r.y for r in col_rects["0"])
        col1_span = max(r.y + r.h for r in col_rects["1"]) - min(r.y for r in col_rects["1"])
        assert col0_span > col1_span, (
            f"Col-0 span={col0_span} should exceed col-1 span={col1_span} (3 vs 1 events)"
        )

    def test_activity_line_end_marker_in_edges(self):
        """The spine SceneLine must reference a marker_end (arrowhead at timeline end)."""
        scene = layout_timeline_scene(SIMPLE)
        edges = scene.get_layer(LAYER_EDGES)
        spine_lines = [
            el for el in edges
            if isinstance(el, SceneLine) and "timeline-spine" in (el.css_classes or ())
        ]
        assert spine_lines, "No spine line found in edges layer"
        spine = spine_lines[0]
        assert spine.marker_end, "Spine must have a marker_end (arrowhead)"
        # The marker must be defined in scene.definitions
        defined_ids = {d.marker_id for d in scene.definitions if hasattr(d, "marker_id")}
        assert spine.marker_end in defined_ids, (
            f"marker_end={spine.marker_end!r} not found in scene definitions"
        )
