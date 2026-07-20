"""Regression tests for flowchart renderer fixes.

Three bugs fixed:
  1. Mermaid v11 @{ shape: ... } attribute syntax not parsed.
  2. <--> bidirectional edges not producing marker-start arrowhead.
  3. Cylinder ([(text)]) rendered as plain rounded-rect instead of drum SVG.
"""
import pytest

from scripts.mermaid_render.layout._parser import _parse_spec, _parse_graph_source
from scripts.mermaid_render.layout._strategies import _dispatch


def _render(src: str) -> str:
    return _dispatch(src, None, 400)


# ---------------------------------------------------------------------------
# Fix 1: Mermaid v11 @{ shape: ... } attribute syntax
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spec,expected_shape,expected_label", [
    # Basic shapes by Mermaid v11 name
    ("A@{ shape: cyl }", "cylinder", "A"),
    ("A@{ shape: cylinder }", "cylinder", "A"),
    ("A@{ shape: diam }", "diamond", "A"),
    ("A@{ shape: diamond }", "diamond", "A"),
    ("A@{ shape: circle }", "circle", "A"),
    ("A@{ shape: hex }", "hexagon", "A"),
    ("A@{ shape: stadium }", "stadium", "A"),
    ("A@{ shape: rect }", "rect", "A"),
    ("A@{ shape: rounded }", "round", "A"),
    # Label override
    ('A@{ shape: cyl, label: "Users DB" }', "cylinder", "Users DB"),
    ("A@{ shape: diamond, label: 'OK?' }", "diamond", "OK?"),
    # Unknown shape falls back to rect
    ("A@{ shape: xyzzy }", "rect", "A"),
])
def test_new_shape_syntax(spec, expected_shape, expected_label):
    """_parse_spec must handle the Mermaid v11 @{ shape: ..., label: ... } syntax."""
    nid, label, shape = _parse_spec(spec)
    assert nid == "A"
    assert shape == expected_shape, f"shape mismatch for {spec!r}: got {shape!r}"
    assert label == expected_label, f"label mismatch for {spec!r}: got {label!r}"


def test_new_shape_syntax_in_diagram():
    """Full round-trip: @{ shape: } node spec survives _parse_graph_source."""
    src = [
        "flowchart LR\n",
        '    DB@{ shape: cyl, label: "Users DB" }\n',
        "    API\n",
        "    DB --> API\n",
    ]
    nodes, edges, groups = _parse_graph_source(src)
    assert "DB" in nodes, "node DB not found"
    assert nodes["DB"].shape == "cylinder"
    assert nodes["DB"].label == "Users DB"


def test_new_shape_syntax_html():
    """@{ shape: cyl } in a flowchart must produce node-cylinder HTML."""
    src = 'flowchart LR\n    DB@{ shape: cyl, label: "Store" }\n'
    html = _render(src)
    assert "node-cylinder" in html, "node-cylinder class not found in rendered HTML"


# ---------------------------------------------------------------------------
# Fix 2: <--> bidirectional edges render marker-start
# ---------------------------------------------------------------------------

def test_bidirectional_edge_parsed():
    """<--> must produce a single edge with bidir=True."""
    src = ["flowchart LR\n", "    A <--> B\n"]
    nodes, edges, groups = _parse_graph_source(src)
    assert len(edges) == 1
    e = edges[0]
    assert e.src == "A" and e.dst == "B"
    assert e.bidir is True, "<--> edge must have bidir=True"


def test_unidirectional_edge_not_bidir():
    """Regular --> edges must have bidir=False."""
    src = ["flowchart LR\n", "    A --> B\n"]
    nodes, edges, groups = _parse_graph_source(src)
    assert len(edges) == 1
    assert edges[0].bidir is False


def test_bidirectional_edge_svg_markers():
    """SVG output for <--> must include both marker-end and marker-start on the path."""
    src = "flowchart LR\n    A[Client] <--> B[Server]\n"
    html = _render(src)
    assert "marker-end" in html, "marker-end missing from bidirectional edge"
    assert "marker-start" in html, "marker-start missing from bidirectional edge"


# ---------------------------------------------------------------------------
# Fix 3: Cylinder shape renders drum SVG (ellipse caps)
# ---------------------------------------------------------------------------

def test_cylinder_parse_spec():
    """[(text)] must parse to cylinder shape."""
    nid, label, shape = _parse_spec("I[(Cylinder)]")
    assert shape == "cylinder"
    assert label == "Cylinder"


def test_cylinder_svg_overlay():
    """Cylinder node HTML must contain <ellipse> elements for the drum caps."""
    src = "flowchart TD\n    I[(Database)]\n"
    html = _render(src)
    assert "<ellipse" in html, "cylinder node must contain <ellipse> SVG elements"
    # Must have at least two ellipses (top cap + bottom arc)
    ellipse_count = html.count("<ellipse")
    assert ellipse_count >= 2, f"expected >=2 ellipses, got {ellipse_count}"


def test_cylinder_html_structure():
    """Cylinder node must have node-cylinder CSS class and SVG overlay."""
    src = "flowchart TD\n    DB[(Datastore)]\n"
    html = _render(src)
    assert "node-cylinder" in html, "node-cylinder CSS class missing"
    assert "<svg" in html, "<svg> overlay missing from cylinder"
