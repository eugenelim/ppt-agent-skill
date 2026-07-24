"""Browser-gated integration tests for the geometry capture pipeline.

These tests require:
  - Playwright installed: pip install playwright
  - Chromium installed: playwright install chromium
  - mmdc 11.15.0 CLI available

Run with: pytest tests/test_browser_capture.py --run-browser -v

All tests here are gated with @pytest.mark.browser so they are skipped
in the default test run.
"""
from __future__ import annotations

import pytest

try:
    import playwright  # type: ignore[import-untyped]
    _HAVE_PLAYWRIGHT = True
except ImportError:
    _HAVE_PLAYWRIGHT = False

from tools.mermaid_fidelity.models import ComparisonStatus, ReferenceDiagram
from tools.mermaid_fidelity.oracle_contract import FIXTURE_MINIMUMS, FixtureMinimums


# ── sample fixtures for integration testing ────────────────────────────────────

_SAMPLE_FIXTURES: list[tuple[str, str, str]] = [
    (
        "flowchart-basic",
        "flowchart",
        "flowchart LR\n  A[Start] --> B[End]\n",
    ),
    (
        "er-basic",
        "er",
        "erDiagram\n  CUSTOMER ||--o{ ORDER : places\n",
    ),
]


# ── helper ─────────────────────────────────────────────────────────────────────

def _validate_against_manifest(diagram: ReferenceDiagram, fixture_stem: str) -> list[str]:
    """Validate diagram counts against FIXTURE_MINIMUMS.

    Returns a list of failure messages (empty = pass).
    """
    minimums = FIXTURE_MINIMUMS.get(fixture_stem, FixtureMinimums())
    failures = []
    if len(diagram.nodes) < minimums.min_entities:
        failures.append(
            f"{fixture_stem}: expected >= {minimums.min_entities} nodes, "
            f"got {len(diagram.nodes)}"
        )
    if len(diagram.groups) < minimums.min_groups:
        failures.append(
            f"{fixture_stem}: expected >= {minimums.min_groups} groups, "
            f"got {len(diagram.groups)}"
        )
    if len(diagram.edges) < minimums.min_relations:
        failures.append(
            f"{fixture_stem}: expected >= {minimums.min_relations} edges, "
            f"got {len(diagram.edges)}"
        )
    return failures


# ── integration tests ──────────────────────────────────────────────────────────

@pytest.mark.browser
@pytest.mark.skipif(not _HAVE_PLAYWRIGHT, reason="playwright not installed")
class TestBrowserCaptureIntegration:
    """Full pipeline integration tests — require a browser."""

    def test_capture_returns_reference_diagram(self):
        """Single fixture should produce a ReferenceDiagram (AC1)."""
        from tools.mermaid_fidelity.capture.runner import BatchRunner

        runner = BatchRunner()
        results = runner.render_all([_SAMPLE_FIXTURES[0]], use_cache=False)
        assert len(results) == 1
        assert isinstance(results[0], ReferenceDiagram)

    def test_capture_all_fixtures(self):
        """All sample fixtures pass manifest minimums (AC2)."""
        from tools.mermaid_fidelity.capture.runner import BatchRunner

        runner = BatchRunner()
        results = runner.render_all(_SAMPLE_FIXTURES, use_cache=False)
        assert len(results) == len(_SAMPLE_FIXTURES)

        all_failures = []
        for diag, (stem, _, _) in zip(results, _SAMPLE_FIXTURES):
            all_failures.extend(_validate_against_manifest(diag, stem))

        assert not all_failures, "\n".join(all_failures)

    def test_single_browser_session(self):
        """BatchRunner uses one browser context for all fixtures (AC8).

        We verify this indirectly: all fixtures complete without error
        in a single call (which internally uses one context).
        """
        from tools.mermaid_fidelity.capture.runner import BatchRunner

        runner = BatchRunner()
        results = runner.render_all(_SAMPLE_FIXTURES, use_cache=False)
        # All should have status PASS or EXTRACTOR_GAP (not REFERENCE_RENDER_FAILURE)
        failed = [
            (r.fixture_stem, r.status)
            for r in results
            if r.status == ComparisonStatus.REFERENCE_RENDER_FAILURE
        ]
        assert not failed, f"Render failures: {failed}"

    def test_parallel_edges_distinct(self):
        """Parallel edges produce distinct IDs (AC4)."""
        from tools.mermaid_fidelity.capture.runner import BatchRunner

        parallel_source = "flowchart LR\n  A --> B\n  A --> B\n"
        runner = BatchRunner()
        results = runner.render_all(
            [("parallel-edge-test", "flowchart", parallel_source)],
            use_cache=False,
        )
        diag = results[0]
        edge_ids = [e.id for e in diag.edges]
        assert len(edge_ids) == len(set(edge_ids)), f"Duplicate edge IDs: {edge_ids}"

    def test_coordinate_determinism(self):
        """Same source produces identical bounds across two runs (AC3)."""
        from tools.mermaid_fidelity.capture.runner import BatchRunner

        fixture = [("flowchart-basic", "flowchart", "flowchart LR\n  A --> B\n")]
        runner = BatchRunner()
        r1 = runner.render_all(fixture, use_cache=False)[0]
        r2 = runner.render_all(fixture, use_cache=False)[0]

        # Canvas bounds and node positions must be identical
        assert r1.canvas_bounds == r2.canvas_bounds
        if r1.nodes and r2.nodes:
            assert r1.nodes[0].bbox == r2.nodes[0].bbox
