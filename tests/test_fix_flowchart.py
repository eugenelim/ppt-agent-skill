"""Regression tests for flowchart renderer fixes.

Four fixes:
  1. Mermaid v11 @{ shape: ... } attribute syntax not parsed.
  2. <--> bidirectional edges not producing marker-start arrowhead.
  3. Cylinder ([(text)]) rendered as plain rounded-rect instead of drum SVG.
  4. Self-loop finalization pass — no negative SVG path coordinates.
"""
import re
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


# ---------------------------------------------------------------------------
# Fix 4: Self-loop finalization pass — no negative SVG path coordinates
# ---------------------------------------------------------------------------

def _neg_path_coords(svg: str) -> list:
    """Return list of negative numbers found in SVG <path d=...> attributes."""
    neg = []
    for d_attr in re.findall(r'd="([^"]+)"', svg):
        for tok in re.split(r"[MLCQAZz,\s]+", d_attr):
            try:
                v = float(tok)
                if v < -0.5:          # -0.5 tolerance for float rounding
                    neg.append(v)
            except ValueError:
                pass
    return neg


def test_self_loop_tb_left_face_no_negative_coords():
    """TB flowchart with two self-loops on the same node (left-face lane_idx=1).

    With CANVAS_PAD=48 and lane_num=1 → extent = 32+20 = 52 > 48, so without
    the finalization pass the left-face loop would produce a negative x coordinate.
    The finalization pass must shift all nodes right so loop_x >= CANVAS_PAD.
    """
    src = (
        "flowchart TD\n"
        "    A[\"Wide label node that forces large node width\"] --> A\n"
        "    A --> A\n"   # second self-loop → lane_idx=1 → left face
    )
    html = _render(src)
    neg = _neg_path_coords(html)
    assert not neg, f"Negative SVG path coordinates after finalization: {neg}"


def test_self_loop_lr_top_face_no_negative_coords():
    """LR flowchart with a self-loop on the top face.

    In LR mode top-face is lane_idx=0.  With a wide label, extent can exceed
    CANVAS_PAD.  The finalization pass must prevent loop_y from going negative.
    """
    src = (
        "flowchart LR\n"
        "    A[\"A very wide label that increases extent beyond canvas pad\"] --> A\n"
        "    A --> A\n"   # second self-loop → top-face used twice, forcing lane_num>0
    )
    html = _render(src)
    neg = _neg_path_coords(html)
    assert not neg, f"Negative SVG path coordinates after finalization: {neg}"


def test_self_loop_finalization_offset_helper():
    """Unit-test _finalize_self_loop_offsets returns positive offsets when needed."""
    from scripts.mermaid_render.layout._constants import _Node, _Edge, CANVAS_PAD, BASE_LOOP_EXTENT, LOOP_LANE_GAP
    from scripts.mermaid_render.layout._routing import _finalize_self_loop_offsets

    # Simulate a node at x=CANVAS_PAD (minimum after _assign_coordinates) with
    # one left-face self-loop (lane_idx=1, lane_num=0 but odd → left face).
    # extent = BASE_LOOP_EXTENT = 32; with lane_num=0 for the second loop, extent=32.
    # For lane_idx=1 (odd → left face), extent=32+0=32 < CANVAS_PAD=48.
    # So no offset should be needed for this case.
    n = _Node(id="A", label="A", shape="rect")
    n.x = CANVAS_PAD
    n.y = CANVAS_PAD
    n.width = 80
    e0 = _Edge(src="A", dst="A", label="")
    e1 = _Edge(src="A", dst="A", label="")

    dx, dy = _finalize_self_loop_offsets({"A": n}, [e0, e1], "TB", canvas_pad=CANVAS_PAD)
    # extent for lane_idx=1 (left face, lane_num=0) = BASE_LOOP_EXTENT = 32
    # loop_x = CANVAS_PAD - 32 = 16 >= 0 but < CANVAS_PAD
    # dx = CANVAS_PAD - (CANVAS_PAD - 32) = 32
    assert dx >= 0, "dx must be non-negative"
    assert dy == 0, "TB self-loops only shift x (left face)"

    # With a large lane_num making extent > CANVAS_PAD, dx must be positive.
    e2 = _Edge(src="A", dst="A", label="")
    e3 = _Edge(src="A", dst="A", label="")
    dx2, dy2 = _finalize_self_loop_offsets({"A": n}, [e0, e1, e2, e3], "TB", canvas_pad=CANVAS_PAD)
    # lane_idx=3 → lane_num=1 → extent=BASE_LOOP_EXTENT+LOOP_LANE_GAP=52 > CANVAS_PAD=48
    # loop_x = CANVAS_PAD - 52 = -4 → dx2 = CANVAS_PAD - (-4) = 52
    assert dx2 >= CANVAS_PAD, f"dx2={dx2} should offset enough for lane_num=1 extent"
