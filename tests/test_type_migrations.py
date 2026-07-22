"""Content-level tests for Stage 6 type migrations.

Each of the 12 newly-implemented PARTIAL builders is tested for:
- SVG is produced (not empty, contains <svg> tag)
- Key content identifiers appear in the SVG (diagram-type data attrs)
- No foreignObject wrapper
- Valid output structure
"""
from __future__ import annotations

import os
import re
from unittest.mock import patch

import pytest

from scripts.mermaid_render.native_svg import dispatch_native
from scripts.mermaid_render import dispatch_native_result


# ── sequenceDiagram ───────────────────────────────────────────────────────────

_SEQUENCE_SRC = """\
sequenceDiagram
    participant Alice
    participant Bob
    Alice->>Bob: Hello Bob
    Bob-->>Alice: Hi Alice
    Note over Alice,Bob: A conversation
"""


def test_sequence_produces_svg():
    svg = dispatch_native(_SEQUENCE_SRC)
    assert "<svg" in svg
    assert "foreignObject" not in svg


def test_sequence_contains_actors():
    svg = dispatch_native(_SEQUENCE_SRC)
    assert "Alice" in svg
    assert "Bob" in svg


def test_sequence_data_diagram_type():
    result = dispatch_native_result(_SEQUENCE_SRC)
    assert result.diagram_type == "sequencediagram"
    assert result.svg is not None


# ── erDiagram ─────────────────────────────────────────────────────────────────

_ER_SRC = """\
erDiagram
    CUSTOMER {
        string name PK
        string email
    }
    ORDER {
        int id PK
        date placed FK
    }
    CUSTOMER ||--o{ ORDER : places
"""


def test_er_produces_svg():
    svg = dispatch_native(_ER_SRC)
    assert "<svg" in svg
    assert "foreignObject" not in svg


def test_er_contains_entities():
    svg = dispatch_native(_ER_SRC)
    assert "CUSTOMER" in svg
    assert "ORDER" in svg


def test_er_has_relation_edge():
    svg = dispatch_native(_ER_SRC)
    assert "<line" in svg  # relation edges rendered as SceneLine


# ── gantt ─────────────────────────────────────────────────────────────────────

_GANTT_SRC = """\
gantt
    title Project Plan
    dateFormat YYYY-MM-DD
    section Phase 1
        Design   :done, t1, 2024-01-01, 7d
        Build    :active, t2, after t1, 14d
    section Phase 2
        Test     :t3, after t2, 7d
        Deploy   :milestone, t4, after t3, 1d
"""


def test_gantt_produces_svg():
    svg = dispatch_native(_GANTT_SRC)
    assert "<svg" in svg
    assert "foreignObject" not in svg


def test_gantt_contains_task_labels():
    svg = dispatch_native(_GANTT_SRC)
    assert "Design" in svg or "Build" in svg or "Test" in svg


def test_gantt_has_task_elements():
    svg = dispatch_native(_GANTT_SRC)
    assert 'data-task' in svg or 'semantic_role' in svg or 'rect' in svg.lower()


# ── quadrantChart ─────────────────────────────────────────────────────────────

_QUADRANT_SRC = """\
quadrantChart
    title Product Matrix
    x-axis Low Effort --> High Effort
    y-axis Low Value --> High Value
    quadrant-1 Do Now
    quadrant-2 Schedule
    quadrant-3 Reassess
    quadrant-4 Ignore
    Feature A: [0.2, 0.8]
    Feature B: [0.7, 0.6]
    Feature C: [0.4, 0.3]
"""


def test_quadrant_produces_svg():
    svg = dispatch_native(_QUADRANT_SRC)
    assert "<svg" in svg
    assert "foreignObject" not in svg


def test_quadrant_contains_labels():
    svg = dispatch_native(_QUADRANT_SRC)
    assert "Feature A" in svg or "Feature B" in svg


def test_quadrant_has_data_points():
    svg = dispatch_native(_QUADRANT_SRC)
    assert 'data-label' in svg or 'circle' in svg.lower()


# ── pie ───────────────────────────────────────────────────────────────────────

_PIE_SRC = """\
pie showData
    title Browser Share
    "Chrome" : 63.5
    "Firefox" : 14.2
    "Safari" : 12.8
    "Other" : 9.5
"""


def test_pie_produces_svg():
    svg = dispatch_native(_PIE_SRC)
    assert "<svg" in svg
    assert "foreignObject" not in svg


def test_pie_contains_slice_labels():
    svg = dispatch_native(_PIE_SRC)
    assert "Chrome" in svg or "Firefox" in svg or "Safari" in svg


def test_pie_has_path_elements():
    svg = dispatch_native(_PIE_SRC)
    assert "<path" in svg


# ── xychart-beta ──────────────────────────────────────────────────────────────

_XY_SRC = """\
xychart-beta
    title "Monthly Sales"
    x-axis [Jan, Feb, Mar, Apr, May]
    y-axis "Revenue ($K)" 0 --> 100
    bar [45, 62, 78, 55, 90]
    line [40, 58, 72, 50, 85]
"""


def test_xychart_produces_svg():
    svg = dispatch_native(_XY_SRC)
    assert "<svg" in svg
    assert "foreignObject" not in svg


def test_xychart_has_bars():
    svg = dispatch_native(_XY_SRC)
    assert "<rect" in svg


def test_xychart_contains_axis_labels():
    svg = dispatch_native(_XY_SRC)
    assert "Jan" in svg or "Feb" in svg or "Mar" in svg


# ── block-beta ────────────────────────────────────────────────────────────────

_BLOCK_SRC = """\
block-beta
    columns 3
    A["Input"] B["Process"] C["Output"]
    A --> B --> C
"""


def test_block_produces_svg():
    svg = dispatch_native(_BLOCK_SRC)
    assert "<svg" in svg
    assert "foreignObject" not in svg


def test_block_contains_block_labels():
    svg = dispatch_native(_BLOCK_SRC)
    assert "Input" in svg or "Process" in svg or "Output" in svg


def test_block_has_edges():
    svg = dispatch_native(_BLOCK_SRC)
    assert 'data-src' in svg or '<line' in svg


# ── packet-beta ───────────────────────────────────────────────────────────────

_PACKET_SRC = """\
packet-beta
    0-15: "Source Port"
    16-31: "Destination Port"
    32-63: "Sequence Number"
    64-95: "Acknowledgment Number"
"""


def test_packet_produces_svg():
    svg = dispatch_native(_PACKET_SRC)
    assert "<svg" in svg
    assert "foreignObject" not in svg


def test_packet_contains_field_labels():
    svg = dispatch_native(_PACKET_SRC)
    assert "Source Port" in svg or "Destination Port" in svg


def test_packet_has_field_rects():
    svg = dispatch_native(_PACKET_SRC)
    assert 'data-label' in svg or "<rect" in svg


# ── kanban ────────────────────────────────────────────────────────────────────

_KANBAN_SRC = """\
kanban
    todo["To Do"]
        t1["Write tests"]
        t2["Review PR"]
    in-progress["In Progress"]
        t3["Implement feature"]
    done["Done"]
        t4["Deploy v1.0"]
"""


def test_kanban_produces_svg():
    svg = dispatch_native(_KANBAN_SRC)
    assert "<svg" in svg
    assert "foreignObject" not in svg


def test_kanban_contains_column_labels():
    svg = dispatch_native(_KANBAN_SRC)
    assert "To Do" in svg or "In Progress" in svg or "Done" in svg


def test_kanban_has_task_cards():
    svg = dispatch_native(_KANBAN_SRC)
    assert "Write tests" in svg or "Deploy v1.0" in svg


# ── journey ───────────────────────────────────────────────────────────────────

_JOURNEY_SRC = """\
journey
    title My Work Day
    section Morning
        Wake up: 3: Me
        Check email: 2: Me
        Stand-up: 4: Me, Team
    section Afternoon
        Deep work: 5: Me
        Review: 3: Me, Lead
"""


def test_journey_produces_svg():
    svg = dispatch_native(_JOURNEY_SRC)
    assert "<svg" in svg
    assert "foreignObject" not in svg


def test_journey_contains_task_names():
    svg = dispatch_native(_JOURNEY_SRC)
    assert "Wake up" in svg or "Deep work" in svg or "Check email" in svg


def test_journey_has_score_colors():
    svg = dispatch_native(_JOURNEY_SRC)
    assert "<rect" in svg or "fill" in svg


# ── requirementDiagram ────────────────────────────────────────────────────────

_REQ_SRC = """\
requirementDiagram
    requirement auth_req {
        id: REQ-001
        text: Users must authenticate
        risk: High
    }
    functionalRequirement login_req {
        id: REQ-002
        text: Provide login page
    }
    element auth_system {
        type: subsystem
    }
    auth_system - satisfies -> auth_req
    login_req - refines -> auth_req
"""


def test_requirement_produces_svg():
    svg = dispatch_native(_REQ_SRC)
    assert "<svg" in svg
    assert "foreignObject" not in svg


def test_requirement_contains_node_names():
    svg = dispatch_native(_REQ_SRC)
    assert "auth_req" in svg or "login_req" in svg or "auth_system" in svg


def test_requirement_has_relation_edges():
    svg = dispatch_native(_REQ_SRC)
    assert 'data-rel-type' in svg or '<line' in svg


# ── gitGraph ──────────────────────────────────────────────────────────────────

_GIT_SRC = """\
gitGraph
    commit id: "init"
    branch feature/auth
    checkout feature/auth
    commit id: "add-login"
    commit id: "add-logout"
    checkout main
    merge feature/auth id: "merge-auth"
    commit id: "release" tag: "v1.0" type: HIGHLIGHT
"""


def test_gitgraph_produces_svg():
    svg = dispatch_native(_GIT_SRC)
    assert "<svg" in svg
    assert "foreignObject" not in svg


def test_gitgraph_has_commit_circles():
    svg = dispatch_native(_GIT_SRC)
    assert "<circle" in svg


def test_gitgraph_contains_branch_lanes():
    svg = dispatch_native(_GIT_SRC)
    assert "main" in svg or "feature" in svg or "lane" in svg.lower()


# ── Cross-type structural invariants ──────────────────────────────────────────

_ALL_STAGE6_SOURCES = [
    ("sequencediagram", _SEQUENCE_SRC),
    ("erdiagram", _ER_SRC),
    ("gantt", _GANTT_SRC),
    ("quadrantchart", _QUADRANT_SRC),
    ("pie", _PIE_SRC),
    ("xychart-beta", _XY_SRC),
    ("block-beta", _BLOCK_SRC),
    ("packet-beta", _PACKET_SRC),
    ("kanban", _KANBAN_SRC),
    ("journey", _JOURNEY_SRC),
    ("requirementdiagram", _REQ_SRC),
    ("gitgraph", _GIT_SRC),
]


@pytest.mark.parametrize("dtype,src", _ALL_STAGE6_SOURCES)
def test_all_stage6_types_have_viewbox(dtype, src):
    svg = dispatch_native(src)
    assert "viewBox=" in svg, f"{dtype}: missing viewBox attribute"


@pytest.mark.parametrize("dtype,src", _ALL_STAGE6_SOURCES)
def test_all_stage6_types_have_diagram_type_attr(dtype, src):
    result = dispatch_native_result(src)
    assert result.diagram_type == dtype, (
        f"Expected diagram_type={dtype!r}, got {result.diagram_type!r}"
    )


@pytest.mark.parametrize("dtype,src", _ALL_STAGE6_SOURCES)
def test_all_stage6_types_deterministic(dtype, src):
    svg1 = dispatch_native(src)
    svg2 = dispatch_native(src)
    assert svg1 == svg2, f"{dtype}: non-deterministic output"


@pytest.mark.parametrize("dtype,src", _ALL_STAGE6_SOURCES)
def test_all_stage6_types_no_nan(dtype, src):
    svg = dispatch_native(src)
    assert "NaN" not in svg, f"{dtype}: NaN in output"
    assert "Infinity" not in svg, f"{dtype}: Infinity in output"
