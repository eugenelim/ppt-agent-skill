"""Derivation contract for _Edge.arrow / _Edge.bidir (arrow-semantics-cleanup).

The legacy `arrow: bool` / `bidir: bool` fields were removed; both are now
read-only properties derived from the canonical source_marker / target_marker.
See docs/specs/mermaid-render-cleanups/spec.md (Derivation contract).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mermaid_render.layout._constants import _Edge, MarkerSpec, MarkerKind, _marker_kind


def _spec(kind, end):
    return MarkerSpec(kind=kind, end=end)


class TestEdgeArrowBidirDerivation:
    def test_plain_arrow(self):
        e = _Edge(src="A", dst="B",
                  source_marker=_spec(MarkerKind.NONE, "SOURCE"),
                  target_marker=_spec(MarkerKind.ARROW, "TARGET"))
        assert e.arrow is True
        assert e.bidir is False

    def test_bidirectional(self):
        e = _Edge(src="A", dst="B",
                  source_marker=_spec(MarkerKind.ARROW, "SOURCE"),
                  target_marker=_spec(MarkerKind.ARROW, "TARGET"))
        assert e.arrow is True
        assert e.bidir is True

    def test_no_arrow(self):
        # Defaults: both markers NONE.
        e = _Edge(src="A", dst="B")
        assert e.arrow is False
        assert e.bidir is False

    def test_class_aggregation_source_only(self):
        # Aggregation diamond sits at the SOURCE end; no target marker.
        e = _Edge(src="A", dst="B",
                  source_marker=_spec(MarkerKind.HOLLOW_DIAMOND, "SOURCE"),
                  target_marker=_spec(MarkerKind.NONE, "TARGET"))
        assert e.arrow is False   # no target-end arrowhead
        assert e.bidir is False   # diamond is not a plain ARROW

    def test_class_dependency_target_only(self):
        e = _Edge(src="A", dst="B",
                  source_marker=_spec(MarkerKind.NONE, "SOURCE"),
                  target_marker=_spec(MarkerKind.OPEN_ARROW, "TARGET"))
        assert e.arrow is True    # target-end marker present
        assert e.bidir is False   # OPEN_ARROW at target, no source marker

    def test_no_arrow_kwargs_accepted(self):
        # Removed fields must not be constructor kwargs anymore.
        import pytest
        with pytest.raises(TypeError):
            _Edge(src="A", dst="B", arrow=True)  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            _Edge(src="A", dst="B", bidir=True)  # type: ignore[call-arg]


class TestMarkerKindCoercion:
    def test_markerspec(self):
        assert _marker_kind(MarkerSpec(kind=MarkerKind.ARROW, end="TARGET")) == MarkerKind.ARROW

    def test_bare_markerkind(self):
        assert _marker_kind(MarkerKind.OPEN_ARROW) == MarkerKind.OPEN_ARROW

    def test_str(self):
        # Markers are polymorphic across the pipeline; str must coerce.
        assert _marker_kind(MarkerKind.ARROW.value) == MarkerKind.ARROW

    def test_none(self):
        assert _marker_kind(None) == MarkerKind.NONE

    def test_bare_markerkind_edge_property(self):
        # An _Edge whose target_marker is a bare MarkerKind still derives arrow.
        e = _Edge(src="A", dst="B", target_marker=MarkerKind.ARROW)  # type: ignore[arg-type]
        assert e.arrow is True

    def test_markerspec_with_str_valued_kind(self):
        # MarkerSpec.kind carried as a raw str must still coerce (N3).
        assert _marker_kind(MarkerSpec(kind=MarkerKind.ARROW.value, end="TARGET")) == MarkerKind.ARROW

    def test_unknown_str_degrades_to_none(self):
        # Total coercion: an unrecognised string does not raise.
        assert _marker_kind("not-a-marker") == MarkerKind.NONE

    def test_bidir_requires_both_ends_arrow(self):
        # source=ARROW but target≠ARROW must NOT read as bidir (short-circuit arm).
        e = _Edge(src="A", dst="B",
                  source_marker=_spec(MarkerKind.ARROW, "SOURCE"),
                  target_marker=_spec(MarkerKind.NONE, "TARGET"))
        assert e.bidir is False
        assert e.arrow is False


class TestWriterMigrationRendersArrowheads:
    """Render-level guard for the writers migrated from arrow=True to markers:
    a directed edge must still produce an arrowhead in the rendered output."""

    def test_state_directed_transition_has_arrowhead(self):
        from mermaid_render.layout import _dispatch
        html = _dispatch("stateDiagram-v2\n  A --> B\n", None, 800)
        assert "<polygon" in html, "directed state transition lost its arrowhead"

    def test_arch_directed_edge_has_arrowhead(self):
        from mermaid_render.layout._strategies import _layout_architecture
        src = "architecture-beta\n  service a(server)[A]\n  service b(server)[B]\n  a --> b"
        html = _layout_architecture(src, "LR", 1200)
        assert "<polygon" in html, "directed architecture edge lost its arrowhead"

    def test_arch_undirected_edge_has_no_arrowhead(self):
        from mermaid_render.layout._strategies import _layout_architecture
        src = "architecture-beta\n  service a(server)[A]\n  service b(server)[B]\n  a -- b"
        html = _layout_architecture(src, "LR", 1200)
        assert "<polygon" not in html, "undirected architecture edge should have no arrowhead"
