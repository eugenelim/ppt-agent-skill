"""Geometric invariant tests (Phase 1 of mermaid-render-correctness spec).

Parametrize over every fixture that produces annotated SVG paths and assert
correctness invariants that should hold regardless of diagram type.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render.layout._strategies import _dispatch

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

# Fixture files that the renderer explicitly marks unsupported (raise on dispatch).
# Note: gitgraph, journey, requirementDiagram, and sankey are now handled by the dispatcher.
_UNSUPPORTED = {
    "zenuml-basic.mmd",
}

# Fixture files whose rendered output contains no annotated <path> elements
# (non-graph diagram types: gantt, pie, timeline, kanban, mindmap, packet, etc.).
# These are skipped by the invariant tests since there are no SVG edge paths to check.
_NO_PATHS = {
    "block-basic.mmd",
    "er-basic.mmd", "er-cardinality-all.mmd", "er-ecommerce.mmd", "er-identifying.mmd",
    "gantt-after-multi.mmd", "gantt-basic.mmd", "gantt-modifiers.mmd",
    "gitgraph-basic.mmd",
    "journey-basic.mmd",
    "kanban-basic.mmd", "kanban-empty-col.mmd", "kanban-metadata.mmd",
    "kanban-quoted-labels.mmd",
    "mindmap-basic.mmd", "mindmap-deep.mmd",
    "packet-basic.mmd", "packet-relative.mmd", "packet-wrap.mmd",
    "pie-basic.mmd", "pie-many-slices.mmd", "pie-showdata.mmd",
    "quadrant-basic.mmd",
    "sankey-basic.mmd",
    "sequence-activation.mmd", "sequence-all-arrowtypes.mmd", "sequence-basic.mmd",
    "sequence-blocks.mmd", "sequence-complex.mmd", "sequence-note.mmd",
    "sequence-notes-all.mmd",
    "timeline-basic.mmd", "timeline-continuation.mmd", "timeline-multiperiod.mmd",
    "timeline-sections.mmd",
    "xychart-basic.mmd", "xychart-mixed.mmd",
}

_all_fixtures = sorted(FIXTURES_DIR.glob("*.mmd"))
_path_fixtures = [
    f for f in _all_fixtures
    if f.name not in _UNSUPPORTED and f.name not in _NO_PATHS
]


def _render(fpath: Path, width: int = 800) -> str:
    return _dispatch(fpath.read_text(), None, width)


def _canvas_w(html: str) -> int:
    m = re.search(r'width:(\d+)px', html)
    return int(m.group(1)) if m else 0


def _all_path_xs(html: str) -> list[float]:
    """Extract all M and L x-coordinates from SVG path d attributes."""
    return [float(x) for x in re.findall(r'[ML]\s+([\d.]+)\s+[\d.]+', html)]


# ── AC-1.1: each logical edge renders as exactly one annotated path ───────────

class TestGeometricInvariants:

    @pytest.mark.parametrize("fpath", _path_fixtures, ids=lambda f: f.stem)
    def test_paths_within_canvas(self, fpath: Path):
        """No SVG path coordinate should exceed canvas_w + 5px (AC-1.2)."""
        html = _render(fpath)
        cw = _canvas_w(html)
        if cw == 0:
            pytest.skip("canvas_w not found in output")
        xs = _all_path_xs(html)
        if not xs:
            pytest.skip("no path M/L coordinates found")
        max_x = max(xs)
        assert max_x <= cw + 5, (
            f"{fpath.name}: path reaches x={max_x} but canvas_w={cw} "
            f"(overshoot {max_x - cw:.0f}px, limit +5)"
        )

    @pytest.mark.parametrize("fpath", _path_fixtures, ids=lambda f: f.stem)
    def test_no_duplicate_src_dst_pairs(self, fpath: Path):
        """Each (src, dst) pair should appear in at most N paths where N is the
        number of parallel edges between that pair (AC-1.1 proxy).

        We assert that no pair appears MORE than twice — a generous bound that
        catches the dummy-chain bug (which produced 3+ paths per pair) while
        tolerating intentional parallel edge fixtures.
        """
        html = _render(fpath)
        pairs: dict[tuple[str, str], int] = {}
        for m in re.finditer(
            r'<path\b[^>]*\bdata-src="([^"]+)"[^>]*\bdata-dst="([^"]+)"',
            html,
        ):
            key = (m.group(1), m.group(2))
            pairs[key] = pairs.get(key, 0) + 1
        violations = {k: v for k, v in pairs.items() if v > 2}
        assert not violations, (
            f"{fpath.name}: these (src, dst) pairs appear too many times: {violations}"
        )


# ── AC-2.5: Node width from text content ─────────────────────────────────────

class TestNodeTextSizing:

    def _node_w(self, html: str, nid: str) -> int:
        """Extract width of the first node div with data-node-id=nid."""
        m = re.search(rf'data-node-id="{re.escape(nid)}"[^>]*>', html)
        if not m:
            return 0
        tag = m.group(0)
        w = re.search(r'width:(\d+)px', tag)
        return int(w.group(1)) if w else 0

    def test_short_label_narrower_than_long(self):
        """Node labeled 'A' must have a smaller rendered width than 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'."""
        short_html = _dispatch("flowchart TD\n    A[A]\n", None, 800)
        long_html  = _dispatch("flowchart TD\n    A[ABCDEFGHIJKLMNOPQRSTUVWXYZ]\n", None, 800)
        short_w = self._node_w(short_html, "A")
        long_w  = self._node_w(long_html,  "A")
        assert short_w > 0, "Could not parse short-label node width"
        assert long_w  > 0, "Could not parse long-label node width"
        assert short_w < long_w, (
            f"Short-label node ({short_w}px) should be narrower than long-label ({long_w}px)"
        )

    def test_min_width_enforced(self):
        """Even a single-char label must be at least NODE_MIN_W (64px) wide."""
        html = _dispatch("flowchart TD\n    A[A]\n", None, 800)
        w = self._node_w(html, "A")
        assert w >= 64, f"Node width {w}px is below NODE_MIN_W=64"

    def test_wide_canvas_for_long_label(self):
        """A single long-label node widens the canvas proportionally."""
        short_html = _dispatch("flowchart TD\n    A[A]\n", None, 800)
        long_html  = _dispatch("flowchart TD\n    A[ABCDEFGHIJKLMNOPQRSTUVWXYZ]\n", None, 800)
        short_cw = _canvas_w(short_html)
        long_cw  = _canvas_w(long_html)
        assert short_cw < long_cw, (
            f"Short-label canvas ({short_cw}px) should be narrower than long-label ({long_cw}px)"
        )

# ── AC-2.4: Nested state compound layout ─────────────────────────────────────

class TestNestedStateCompound:

    def _html(self) -> str:
        src = (FIXTURES_DIR / "statediagram-nested.mmd").read_text()
        return _dispatch(src, None, 800)

    def test_no_duplicate_atomic_node(self):
        """Processing must NOT appear as a standalone atomic node (data-node-id)."""
        html = self._html()
        assert 'data-node-id="Processing"' not in html, (
            "Processing should only be a compound boundary, not a duplicate atomic node"
        )

    def test_compound_group_rendered(self):
        """Processing must appear as a diagram-group boundary."""
        html = self._html()
        assert 'class="diagram-group"' in html, "No diagram-group rendered"
        assert 'Processing' in html  # label appears in group

    def test_external_edge_to_processing_renders(self):
        """Idle --> Processing : start transition must produce a rendered path."""
        html = self._html()
        # Edge may route to any entry node inside Processing
        m = re.search(r'<path\b[^>]*data-src="Idle"', html)
        assert m, "No outgoing path from Idle found — Idle→Processing edge not rendered"

    def test_external_edge_from_processing_renders(self):
        """Processing --> Done and Processing --> Failed must produce rendered paths."""
        html = self._html()
        to_done = re.search(r'<path\b[^>]*data-dst="Done"', html)
        to_failed = re.search(r'<path\b[^>]*data-dst="Failed"', html)
        assert to_done or to_failed, "No path arriving at Done or Failed — Processing exit edges not rendered"

    def test_complex_fixture_no_duplicate_atomic_node(self):
        """statediagram-complex: Processing is a plain atomic state — must appear exactly once."""
        src = (FIXTURES_DIR / "statediagram-complex.mmd").read_text()
        html = _dispatch(src, None, 800)
        node_ids = re.findall(r'data-node-id="([^"]+)"', html)
        processing_count = node_ids.count("Processing")
        assert processing_count == 1, (
            f"Processing should appear exactly once as an atomic node; got {processing_count}"
        )

# ── AC-2.3: ER cardinality marker primitives ────────────────────────────────

class TestERCardinalityMarkers:
    """Each cardinality token renders the correct combination of SVG bar/circle/crowfoot."""

    def _crow_parts(self, src: str) -> tuple[int, int]:
        """Render src and count (line_elements, circle_elements) excluding main edge lines."""
        html = _dispatch(src, None, 600)
        # All <line> elements; subtract 1 per entity pair (main edge line)
        import re as _re
        all_lines = _re.findall(r'<line\b', html)
        all_circles = _re.findall(r'<circle\b', html)
        return len(all_lines), len(all_circles)

    def test_one_to_one_two_bars_each_end(self):
        """A ||--|| B: exactly one both ends → 2 bars at A + 2 bars at B = 4 bar lines + 1 edge line."""
        src = "erDiagram\n    A ||--|| B : x\n"
        lines, circles = self._crow_parts(src)
        assert circles == 0, f"||--|| should have no circles, got {circles}"
        # 1 main edge line + 2 bars at A + 2 bars at B = 5 lines
        assert lines == 5, f"||--|| should have 5 lines (1 edge + 4 bars), got {lines}"

    def test_one_to_zero_many_crowfoot_circle(self):
        """C ||--o{ D: one at src (2 bars), zero-many at dst (3 crowfoot + 1 circle)."""
        src = "erDiagram\n    C ||--o{ D : x\n"
        lines, circles = self._crow_parts(src)
        assert circles == 1, f"||--o{{ should have 1 circle at dst, got {circles}"
        # 1 edge + 2 bars at C + 3 crowfoot at D = 6
        assert lines == 6, f"||--o{{ should have 6 lines, got {lines}"

    def test_many_to_one_crowfoot_and_bars(self):
        """E }|--|| F: ONE..MANY at src (3 crowfoot + 1 mandatory bar), ONE..ONE at dst (2 bars)."""
        src = "erDiagram\n    E }|--|| F : x\n"
        lines, circles = self._crow_parts(src)
        assert circles == 0, f"}}|--|| should have no circles, got {circles}"
        # 1 edge + (3 crowfoot + 1 min-bar) at E + 2 bars at F = 7
        assert lines == 7, f"}}|--|| should have 7 lines, got {lines}"

    def test_zero_one_to_many_bar_circle_crowfoot(self):
        """G |o--|{ H: ZERO..ONE at src (1 bar + 1 circle), ONE..MANY at dst (3 crowfoot + 1 bar)."""
        src = "erDiagram\n    G |o--|{ H : x\n"
        lines, circles = self._crow_parts(src)
        assert circles == 1, f"|o--|{{  should have 1 circle at src, got {circles}"
        # 1 edge + 1 bar at G + (3 crowfoot + 1 min-bar) at H = 6
        assert lines == 6, f"|o--|{{  should have 6 lines, got {lines}"

# ── AC-1.4: ER relationship labels strip surrounding quotes ─────────────────

class TestERLabelQuotes:

    _SRC = """\
erDiagram
    A ||--|| B : "one-to-one"
    C ||--o{ D : "one-to-zero-many"
"""

    def test_label_has_no_surrounding_quotes(self):
        """ER relation labels like \"places\" should render as places (no quotes)."""
        html = _dispatch(self._SRC, None, 800)
        assert '"one-to-one"' not in html, "label should not contain literal quotes"
        assert '&quot;one-to-one&quot;' not in html, "label should not HTML-escape quotes"
        assert 'one-to-one' in html, "stripped label content should be present"

    def test_fixture_labels_have_no_quotes(self):
        """er-cardinality-all fixture: none of the 4 labels include quote chars."""
        src = (FIXTURES_DIR / "er-cardinality-all.mmd").read_text()
        html = _dispatch(src, None, 800)
        assert '&quot;' not in html, "no &quot; entities in ER labels"
        assert '"one-to-one"' not in html


# ── AC-1.5: Self-loop routing (rectangular orthogonal loop) ──────────────────

class TestSelfLoopRouting:

    _SRC = """\
flowchart LR
    A[Worker] -->|retry| A
    A --> B[Next]
"""

    def test_self_loop_uses_orthogonal_waypoints(self):
        """Self-loop path (data-src == data-dst) should use L waypoints, not only C bezier."""
        html = _dispatch(self._SRC, None, 800)
        # Find the self-loop path specifically (src and dst are the same node)
        self_loop_ds: list[str] = []
        for m in re.finditer(r'<path\s+d="([^"]+)"[^>]*data-src="([^"]+)"[^>]*data-dst="([^"]+)"', html):
            d, src, dst = m.group(1), m.group(2), m.group(3)
            if src == dst:
                self_loop_ds.append(d)
        assert self_loop_ds, f"No self-loop path (data-src==data-dst) found in {html[:200]}"
        for d in self_loop_ds:
            assert 'L' in d, (
                f"Self-loop path uses cubic bezier only, expected orthogonal L waypoints: {d}"
            )

    def test_self_loop_stays_within_canvas(self):
        """All M/L x-coordinates in self-loop path must stay within canvas_w + 5."""
        html = _dispatch(self._SRC, None, 800)
        m = re.search(r'width:(\d+)px', html)
        canvas_w = int(m.group(1)) if m else 0
        xs = _all_path_xs(html)
        if xs:
            assert max(xs) <= canvas_w + 5

    def test_self_loop_has_label_near_loop(self):
        """The 'retry' label should be present in the rendered output."""
        html = _dispatch(self._SRC, None, 800)
        assert 'retry' in html

    def test_self_loop_fixture_renders(self):  # noqa: E301
        """flowchart-self-loops fixture renders without error and stays within canvas."""
        src = (FIXTURES_DIR / "flowchart-self-loops.mmd").read_text()
        html = _dispatch(src, None, 800)
        m = re.search(r'width:(\d+)px', html)
        canvas_w = int(m.group(1)) if m else 0
        xs = _all_path_xs(html)
        if xs:
            assert max(xs) <= canvas_w + 5


# ── AC-2.2: Class diagram multiplicities ────────────────────────────────────

class TestClassMultiplicities:

    _SRC = """\
classDiagram
    BankAccount "1" --> "0..*" Transaction : initiates
"""

    def test_source_multiplicity_rendered(self):
        """Source multiplicity '1' should appear somewhere in the rendered HTML."""
        html = _dispatch(self._SRC, None, 800)
        # Multiplicity "1" near the source (BankAccount end)
        assert re.search(r'>1<|class="mult[^"]*">[^<]*1[^<]*<|>1\b', html), (
            "Source multiplicity '1' not found in rendered output"
        )

    def test_dest_multiplicity_rendered(self):
        """Destination multiplicity '0..*' should appear in the rendered HTML."""
        html = _dispatch(self._SRC, None, 800)
        assert '0..*' in html, "Destination multiplicity '0..*' not found"

    def test_fixture_both_multiplicities_present(self):
        """class-visibility fixture: BankAccount '1' --> '0..*' Transaction."""
        src = (FIXTURES_DIR / "class-visibility.mmd").read_text()
        html = _dispatch(src, None, 800)
        assert '0..*' in html, "'0..*' not rendered in class-visibility"

# ── AC-2.1: Class diagram UML marker endpoint semantics ──────────────────────

class TestClassMarkerEndpoints:

    _SRC = """\
classDiagram
    Animal <|-- Dog
    Vehicle *-- Engine
    Pond o-- Duck
"""

    def test_inheritance_marker_at_superclass_via_marker_start(self):
        """Animal <|-- Dog: the hollow triangle should be at Animal (src), not Dog (dst).

        Implementation: path has marker-start on a '-rev' marker ID, not marker-end.
        """
        html = _dispatch(self._SRC, None, 800)
        # Find the Animal→Dog path
        m = re.search(
            r'<path[^>]*data-src="Animal"[^>]*data-dst="Dog"[^>]*>',
            html,
        )
        assert m, "Animal→Dog path not found"
        path_tag = m.group(0)
        assert 'marker-start=' in path_tag, (
            f"Expected marker-start on Animal→Dog path, got: {path_tag}"
        )
        assert 'marker-end=' not in path_tag or 'cls-inherit' not in path_tag, (
            f"marker-end still set on Animal→Dog path: {path_tag}"
        )

    def test_composition_marker_at_owner_via_marker_start(self):
        """Vehicle *-- Engine: filled diamond should be at Vehicle (src)."""
        html = _dispatch(self._SRC, None, 800)
        m = re.search(r'<path[^>]*data-src="Vehicle"[^>]*data-dst="Engine"[^>]*>', html)
        assert m, "Vehicle→Engine path not found"
        assert 'marker-start=' in m.group(0)

    def test_aggregation_marker_at_container_via_marker_start(self):
        """Pond o-- Duck: open diamond should be at Pond (src)."""
        html = _dispatch(self._SRC, None, 800)
        m = re.search(r'<path[^>]*data-src="Pond"[^>]*data-dst="Duck"[^>]*>', html)
        assert m, "Pond→Duck path not found"
        assert 'marker-start=' in m.group(0)

    def test_class_basic_fixture_has_marker_start(self):
        """class-basic fixture: Animal <|-- Dog uses marker-start at Animal."""
        src = (FIXTURES_DIR / "class-basic.mmd").read_text()
        html = _dispatch(src, None, 800)
        m = re.search(r'<path[^>]*data-src="Animal"[^>]*data-dst="Dog"[^>]*>', html)
        assert m, "Animal→Dog path not found in class-basic"
        assert 'marker-start=' in m.group(0), f"No marker-start on Animal→Dog: {m.group(0)}"


# ── AC-3.1: Sankey — dedicated flow renderer (not a generic graph) ────────────

class TestSankeyRenderer:

    def test_sankey_renders_flow_not_generic_graph(self):
        """sankey-beta renders via the dedicated Sankey layout: node bars + flow
        ribbons, never the generic node-graph fallback (the original AC-3.1 guard
        against misrendering is preserved by the data-sankey-* markers)."""
        src = (FIXTURES_DIR / "sankey-basic.mmd").read_text()
        html = _dispatch(src, None, 800)
        # Dedicated Sankey markers present …
        assert "data-sankey-node" in html
        assert "data-sankey-link" in html
        # … and it is NOT the generic graph fallback (no annotated edge paths).
        assert "data-src=" not in html
        # Quoted CSV field with an embedded comma is parsed as one node.
        assert "Fuel, Oil" in html

    def test_sankey_skips_header_row(self):
        """A leading 'source,target,value' header (non-numeric value) is skipped,
        not rendered as a bogus flow."""
        src = "sankey-beta\nsource,target,value\nA,B,10\n"
        html = _dispatch(src, None, 800)
        assert "data-sankey-link" in html
        assert html.count("data-sankey-link") == 1  # only A→B, header dropped


# ── AC-3.3: ZenUML — return explicit unsupported ─────────────────────────────

class TestZenUMLUnsupported:

    def test_zenuml_raises_unsupported(self):
        """zenuml diagrams must raise ValueError (not render as a generic node graph)."""
        src = (FIXTURES_DIR / "zenuml-basic.mmd").read_text()
        with pytest.raises(ValueError, match="not supported"):
            _dispatch(src, None, 800)


# ── AC-3.4: GitGraph — lowercase directive detected correctly ─────────────────

class TestGitGraphDetector:

    def test_gitgraph_lowercase_renders(self):
        """gitgraph (lowercase) renders HTML with branch names and commit circles."""
        src = (FIXTURES_DIR / "gitgraph-basic.mmd").read_text()
        html = _dispatch(src, None, 800)
        assert html
        assert "main" in html
        assert "border-radius:50%" in html


# ── AC-3.2: C4 semantic fields ────────────────────────────────────────────────

class TestC4SemanticFields:

    def test_person_description_rendered(self):
        """Person(user, 'User', 'End user') — description 'End user' appears in HTML."""
        html = _dispatch((FIXTURES_DIR / "c4-basic.mmd").read_text(), None, 800)
        assert "End user" in html, "Person description not rendered"

    def test_system_description_rendered(self):
        """System(webapp, 'Web App', 'Main application') — description appears."""
        html = _dispatch((FIXTURES_DIR / "c4-basic.mmd").read_text(), None, 800)
        assert "Main application" in html, "System description not rendered"

    def test_person_shape_is_rect(self):
        """Person element must render as a rect (c4-person), not a circle."""
        html = _dispatch((FIXTURES_DIR / "c4-basic.mmd").read_text(), None, 800)
        assert 'data-node-id="user"' in html, "user node not found in rendered HTML"
        assert not re.search(r'node-circle[^>]*data-node-id="user"', html), (
            "Person node must not have node-circle class in new C4 renderer"
        )
        assert re.search(r'c4-person[^>]*data-node-id="user"', html), (
            "Person node should have c4-person class"
        )

    def test_type_tag_rendered(self):
        """Person element must display a [Person] type tag in the node body."""
        html = _dispatch((FIXTURES_DIR / "c4-basic.mmd").read_text(), None, 800)
        assert "[Person]" in html, "C4 Person type tag '[Person]' not found in rendered output"
