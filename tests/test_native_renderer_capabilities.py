"""Tests for the native renderer capability registry.

Asserts NativeRendererSpec structure and that FULL/PARTIAL directives
produce real semantic output (not stubs). NOT_IMPLEMENTED and UNSUPPORTED
directives must raise.

Stage 13 additions:
- Task A: semantic assertion upgrade — source_label_present, node_count, shape_role
  parameterized over every PARTIAL/FULL registry entry.
- Task B: fixture capability matrix — 22 gallery fixtures across 19 diagram types.
"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.mermaid_render.scene import (
    NativeParityLevel,
    NativeRendererSpec,
    NATIVE_RENDERER_REGISTRY,
)
from scripts.mermaid_render.native_svg import NativeRenderError

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ── Registry structure tests ──────────────────────────────────────────────────

def test_native_renderer_spec_is_frozen():
    spec = NativeRendererSpec(directive="test", parity=NativeParityLevel.PARTIAL)
    with pytest.raises((AttributeError, TypeError)):
        spec.directive = "other"  # type: ignore[misc]


def test_registry_contains_known_directives():
    for d in (
        "flowchart", "graph", "statediagram-v2", "statediagram",
        "classdiagram", "timeline", "mindmap",
        "architecture-beta", "c4context", "c4container", "c4component",
    ):
        assert d in NATIVE_RENDERER_REGISTRY, f"Missing directive in registry: {d}"


def test_registry_contains_newly_implemented_directives():
    for d in (
        "sequencediagram", "erdiagram", "gantt", "quadrantchart", "pie",
        "xychart-beta", "block-beta", "packet-beta", "kanban", "journey",
        "requirementdiagram", "gitgraph",
    ):
        assert d in NATIVE_RENDERER_REGISTRY, f"Missing directive in registry: {d}"
        assert NATIVE_RENDERER_REGISTRY[d].parity == NativeParityLevel.PARTIAL, (
            f"Expected {d} to be PARTIAL, got {NATIVE_RENDERER_REGISTRY[d].parity}"
        )


def test_registry_contains_unsupported_directives():
    assert NATIVE_RENDERER_REGISTRY["sankey-beta"].parity == NativeParityLevel.UNSUPPORTED
    assert NATIVE_RENDERER_REGISTRY["zenuml"].parity == NativeParityLevel.UNSUPPORTED


def test_native_parity_level_has_four_members():
    members = {m.value for m in NativeParityLevel}
    assert "full" in members
    assert "partial" in members
    assert "not-implemented" in members
    assert "unsupported" in members


def test_flowchart_is_partial():
    assert NATIVE_RENDERER_REGISTRY["flowchart"].parity == NativeParityLevel.PARTIAL


def test_classdiagram_is_partial():
    assert NATIVE_RENDERER_REGISTRY["classdiagram"].parity == NativeParityLevel.PARTIAL


# ── PARTIAL directives produce real semantic output ───────────────────────────

_PARTIAL_FIXTURES = [
    ("flowchart", "flowchart LR\n  A[Node A] -->|edge label| B[Node B]"),
    ("graph", "graph TD\n  A --> B\n  B --> C"),
    ("statediagram-v2", "stateDiagram-v2\n  [*] --> Active\n  Active --> [*]"),
    ("classdiagram", "classDiagram\n  class Animal {\n    +name : string\n  }\n  Animal <|-- Dog"),
]


@pytest.mark.parametrize("directive,src", _PARTIAL_FIXTURES)
def test_partial_directive_produces_svg_not_stub(directive, src):
    """PARTIAL directives must produce real SVG output, not a stub."""
    from scripts.mermaid_render import to_svg

    with patch.dict(os.environ, {"MERMAID_RENDER_SVG_BACKEND": "native"}):
        # experimental=True needed for classdiagram (experimental); no-op for implemented types
        result = to_svg(src, experimental=True)

    assert result, f"Empty SVG for {directive}"
    assert "<svg" in result, f"No <svg> tag for {directive}"
    assert "foreignObject" not in result, f"<foreignObject> in {directive} output"
    assert "html" not in result.lower().split("<svg")[0], f"HTML wrapper in {directive} output"


@pytest.mark.parametrize("directive,src", [
    ("flowchart", "flowchart LR\n  A[Alpha] --> B[Beta]"),
    ("graph", "graph TD\n  X[Xray] --> Y[Yankee]"),
])
def test_partial_directive_contains_source_labels(directive, src):
    """Source node labels must appear in the SVG output."""
    from scripts.mermaid_render import to_svg

    with patch.dict(os.environ, {"MERMAID_RENDER_SVG_BACKEND": "native"}):
        result = to_svg(src)

    # Each node label should appear in the SVG
    for label in ("Alpha", "Beta") if directive == "flowchart" else ("Xray", "Yankee"):
        assert label in result, f"Label {label!r} missing from {directive} SVG output"


# ── Newly-implemented PARTIAL directives produce SVG ─────────────────────────

_NEWLY_IMPLEMENTED_FIXTURES = [
    ("sequencediagram", "sequenceDiagram\n  Alice->>Bob: Hello"),
    ("erdiagram", "erDiagram\n  PERSON { string name }"),
    ("gantt", "gantt\n  title G\n  section A\n    Task1 :t1, 2024-01-01, 7d"),
    ("quadrantchart", "quadrantChart\n  x-axis Low --> High\n  y-axis Low --> High"),
    ("pie", "pie\n  title Pets\n  \"Dogs\" : 386"),
    ("xychart-beta", "xychart-beta\n  x-axis [a, b, c]\n  y-axis 0 --> 10\n  bar [5, 3, 8]"),
    ("block-beta", "block-beta\n  A B C"),
    ("packet-beta", "packet-beta\n  0-7: Source Port"),
    ("kanban", "kanban\n  column1\n    item1[Task 1]"),
    ("journey", "journey\n  title My day\n  section Go\n    Task: 5: Me"),
    ("requirementdiagram", "requirementDiagram\n  requirement req1 {\n    id: 1\n    text: Example\n  }"),
    ("gitgraph", "gitGraph\n  commit"),
]


@pytest.mark.parametrize("directive,src", _NEWLY_IMPLEMENTED_FIXTURES)
def test_newly_implemented_directives_produce_svg(directive, src):
    """Stage 6 PARTIAL types must produce real SVG output, not raise."""
    from scripts.mermaid_render.native_svg import dispatch_native

    with patch.dict(os.environ, {"MERMAID_RENDER_SVG_BACKEND": "native"}):
        result = dispatch_native(src)

    assert result, f"Empty result for {directive}"
    assert "<svg" in result, f"No <svg> tag for {directive}"
    assert "foreignObject" not in result, f"<foreignObject> in {directive} output"


@pytest.mark.parametrize("directive,src", [
    ("sankey-beta", "sankey-beta\n  A,B,10"),
    ("zenuml", "zenuml\n  title Hello"),
])
def test_unsupported_directives_raise(directive, src):
    from scripts.mermaid_render.native_svg import dispatch_native

    with pytest.raises((NativeRenderError, ValueError)):
        dispatch_native(src)


# ── Registry all-coverage: no directive is missing ───────────────────────────

def test_all_known_directives_have_registry_entry():
    from scripts.mermaid_render.layout._constants import _KNOWN_DIRECTIVES

    # These additional directives should also be registered
    registered = set(NATIVE_RENDERER_REGISTRY.keys())
    for d in _KNOWN_DIRECTIVES:
        assert d in registered, (
            f"Directive {d!r} in _KNOWN_DIRECTIVES but missing from NATIVE_RENDERER_REGISTRY"
        )


# ── Task A: Semantic assertion upgrade — parameterized over registry ──────────
#
# Covers every PARTIAL/FULL type.  Each entry proves three semantic properties:
#   1. source_label_present — at least one expected label appears in SVG text
#   2. node_count           — total SVG element count >= expected minimum
#   3. shape_role           — at least one expected SVG shape tag is present

_REGISTRY_SEMANTIC_PARAMS = [
    # (directive, src, min_elements, expected_labels, expected_shape_tags)
    ("flowchart",         "flowchart LR\n  A[Alpha] --> B[Beta]",                               10, ["Alpha", "Beta"],  ["rect", "path"]),
    ("graph",             "graph TD\n  A --> B",                                                  8, ["A"],              ["rect", "path"]),
    ("statediagram-v2",   "stateDiagram-v2\n  [*] --> Active\n  Active --> [*]",                  8, ["Active"],         ["path"]),
    ("statediagram",      "stateDiagram\n  [*] --> A\n  A --> [*]",                               8, ["A"],              ["path"]),
    ("classdiagram",      "classDiagram\n  class Animal {\n    +name : string\n  }",              8, ["Animal"],         ["rect"]),
    ("timeline",          "timeline\n  title My Timeline\n  2020 : Launch",                       8, ["My Timeline"],    ["line", "text", "rect"]),
    ("mindmap",           "mindmap\n  root((Root))\n    Item A",                                   8, ["Root"],           ["circle", "path", "rect"]),
    ("architecture-beta", "architecture-beta\n  service svc(internet)[Svc]",                      5, ["Svc"],            ["rect"]),
    ("c4context",         "C4Context\n  Person(p, \"User\")\n  System(s, \"App\")",              10, ["User"],           ["path", "rect"]),
    ("c4container",       "C4Container\n  Container(c, \"API\", \"Python\")",                     5, ["API"],            ["rect"]),
    ("c4component",       "C4Component\n  Component(cp, \"Svc\", \"Python\")",                    5, ["Svc"],            ["rect"]),
    ("sequencediagram",   "sequenceDiagram\n  Alice->>Bob: Hello",                               10, ["Alice", "Bob"],   ["line", "text"]),
    ("erdiagram",         "erDiagram\n  PERSON { string name }",                                   8, ["PERSON"],         ["rect"]),
    ("gantt",             "gantt\n  title G\n  section A\n    Task1 :t1, 2024-01-01, 7d",         8, ["Task1"],          ["rect"]),
    ("quadrantchart",     "quadrantChart\n  x-axis Low --> High\n  y-axis Low --> High\n  P: [0.5, 0.7]", 8, ["P"],    ["rect"]),
    ("pie",               "pie\n  title Pets\n  \"Dogs\" : 386",                                   8, ["Dogs"],           ["path", "rect"]),
    ("xychart-beta",      "xychart-beta\n  x-axis [a, b, c]\n  y-axis 0 --> 10\n  bar [5, 3, 8]", 8, ["a", "b"],       ["line", "rect"]),
    ("block-beta",        "block-beta\n  A B C",                                                   8, ["A"],              ["rect"]),
    ("packet-beta",       "packet-beta\n  0-7: Source Port",                                       8, ["Source Port"],   ["rect"]),
    ("kanban",            "kanban\n  column1\n    item1[Task 1]",                                  8, ["Task 1"],         ["rect"]),
    ("journey",           "journey\n  title My day\n  section Go\n    Task: 5: Me",               8, ["My day"],         ["rect"]),
    ("requirementdiagram","requirementDiagram\n  requirement req1 {\n    id: 1\n    text: Example\n  }", 8, ["req1"],    ["rect"]),
    ("gitgraph",          "gitGraph\n  commit\n  commit id: \"second\"",                           8, ["second"],        ["line", "circle"]),
]


def test_registry_semantic_params_cover_all_partial_full():
    """Every PARTIAL/FULL registry entry has a row in _REGISTRY_SEMANTIC_PARAMS."""
    covered = {p[0] for p in _REGISTRY_SEMANTIC_PARAMS}
    for directive, spec in NATIVE_RENDERER_REGISTRY.items():
        if spec.parity in (NativeParityLevel.FULL, NativeParityLevel.PARTIAL):
            assert directive in covered, (
                f"Directive {directive!r} (parity={spec.parity.value}) "
                f"missing from _REGISTRY_SEMANTIC_PARAMS"
            )


@pytest.mark.parametrize(
    "directive,src,min_elements,expected_labels,expected_shape_tags",
    _REGISTRY_SEMANTIC_PARAMS,
    ids=[p[0] for p in _REGISTRY_SEMANTIC_PARAMS],
)
def test_registry_directive_semantic_assertions(
    directive, src, min_elements, expected_labels, expected_shape_tags
):
    """Stage 13 Task A: every PARTIAL/FULL directive passes three semantic checks.

    Checks:
    - source_label_present: at least one expected label appears in SVG
    - node_count: total SVG element count >= expected minimum
    - shape_role: at least one expected shape tag is present in the SVG
    """
    import xml.etree.ElementTree as ET
    from scripts.mermaid_render.native_svg import dispatch_native

    svg = dispatch_native(src)
    assert svg and "<svg" in svg, f"{directive}: empty or missing SVG"

    root = ET.fromstring(svg)
    all_elements = list(root.iter())
    all_tags = {el.tag.split("}")[-1] for el in all_elements}

    # source_label_present: check rendered text nodes, not raw SVG string
    text_content = " ".join(
        el.text or ""
        for el in all_elements
        if el.tag.split("}")[-1] in ("text", "tspan")
    )
    assert any(label in text_content for label in expected_labels), (
        f"{directive}: none of {expected_labels!r} found in <text>/<tspan> content; "
        f"got text_content={text_content[:200]!r}"
    )
    assert len(all_elements) >= min_elements, (
        f"{directive}: element count {len(all_elements)} < {min_elements}"
    )
    assert any(tag in all_tags for tag in expected_shape_tags), (
        f"{directive}: none of {expected_shape_tags!r} in SVG tags {all_tags}"
    )


# ── Task B: Fixture capability matrix — 22 fixtures across 19 diagram types ──
#
# Each row: (directive, fixture_filename, min_elements, expected_labels,
#            expected_shape_tags, skip_reason)
# skip_reason is a string when the fixture is known experimental, else None.

_FIXTURE_MATRIX = [
    ("flowchart",          "flowchart-diamond-branch.mmd", 20, ["Start", "Valid Input"], ["rect", "path"], None),
    ("sequencediagram",    "sequence-basic.mmd",           20, ["Client", "Server"],     ["line", "text"],  None),
    ("erdiagram",          "er-basic.mmd",                 15, ["Customer", "Order"],    ["rect"],          None),
    ("gantt",              "gantt-basic.mmd",              15, ["Task A", "Phase 1"],    ["rect"],          None),
    ("pie",                "pie-basic.mmd",                15, ["Chrome"],               ["path", "rect"],  None),
    ("kanban",             "kanban-basic.mmd",             15, ["Write tests"],           ["rect"],          None),
    ("timeline",           "timeline-basic.mmd",           20, ["Product Timeline", "2020"], ["rect", "text", "line"], None),
    ("mindmap",            "mindmap-basic.mmd",            20, ["Platform"],             ["path", "rect"],  None),
    ("gitgraph",           "gitgraph-basic.mmd",           25, ["init"],                ["line", "circle"], None),
    ("journey",            "journey-basic.mmd",            30, ["Make tea"],             ["rect"],          None),
    ("quadrantchart",      "quadrant-basic.mmd",           15, ["Feature A"],            ["rect"],          None),
    ("requirementdiagram", "requirement-basic.mmd",        30, ["test_req"],             ["rect"],          None),
    ("architecture-beta",  "architecture-basic.mmd",       15, ["API Gateway"],          ["rect"],          None),
    ("c4context",          "c4-basic.mmd",                 20, ["User"],                ["path", "rect"],  None),
    ("classdiagram",       "class-basic.mmd",              10, ["Animal"],               ["rect"],          None),
    ("block-beta",         "block-basic.mmd",              10, ["Process"],              ["rect"],          None),
    ("packet-beta",        "packet-basic.mmd",             15, ["Source Port"],          ["rect"],          None),
    ("erdiagram",          "er-cardinality-all.mmd",       25, ["A", "B"],               ["rect"],          None),
    ("pie",                "pie-many-slices.mmd",          20, None,                     ["path"],          None),
    ("kanban",             "kanban-metadata.mmd",          20, None,                     ["rect"],          None),
    ("xychart-beta",       "xychart-basic.mmd",            20, None,                     ["line", "rect"],  None),
    ("statediagram-v2",    "statediagram-basic.mmd",       15, ["Done", "Idle"],         ["path"],          None),
]


def _matrix_id(row):
    return f"{row[0]}/{row[1]}"


@pytest.mark.parametrize(
    "directive,fixture_filename,min_elements,expected_labels,expected_shape_tags,skip_reason",
    _FIXTURE_MATRIX,
    ids=[_matrix_id(r) for r in _FIXTURE_MATRIX],
)
def test_fixture_capability_matrix(
    directive, fixture_filename, min_elements, expected_labels, expected_shape_tags, skip_reason
):
    """Stage 13 Task B: fixture capability matrix — 22 gallery fixtures, 19 diagram types.

    Fixtures with skip_reason are skipped (experimental — not blocking CI).
    Checks: node_count, source_label_present, shape_role.
    """
    if skip_reason:
        pytest.skip(skip_reason)

    import xml.etree.ElementTree as ET
    from scripts.mermaid_render.native_svg import dispatch_native

    fixture_path = FIXTURES_DIR / fixture_filename
    assert fixture_path.exists(), (
        f"fixture {fixture_filename!r} not found in {FIXTURES_DIR} — "
        "committed fixtures must not be deleted (update _FIXTURE_MATRIX if renamed)"
    )

    src = fixture_path.read_text(encoding="utf-8")
    svg = dispatch_native(src)
    assert svg and "<svg" in svg, f"{directive}: empty/missing SVG for {fixture_filename}"

    root = ET.fromstring(svg)
    all_elements = list(root.iter())
    all_tags = {el.tag.split("}")[-1] for el in all_elements}

    assert len(all_elements) >= min_elements, (
        f"{directive}/{fixture_filename}: element count {len(all_elements)} < {min_elements}"
    )
    if expected_labels is not None:
        text_content = " ".join(
            el.text or ""
            for el in all_elements
            if el.tag.split("}")[-1] in ("text", "tspan")
        )
        assert any(label in text_content for label in expected_labels), (
            f"{directive}/{fixture_filename}: none of {expected_labels!r} in "
            f"<text>/<tspan> content; got {text_content[:200]!r}"
        )
    assert any(tag in all_tags for tag in expected_shape_tags), (
        f"{directive}/{fixture_filename}: none of {expected_shape_tags!r} in SVG tags {all_tags}"
    )
