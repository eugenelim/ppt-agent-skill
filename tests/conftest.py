"""pytest configuration for mermaid renderer test suite.

Registers cost-tier markers and makes them genuinely opt-in: plain ``pytest``
skips all browser, snapshot, external_reference, and isolation tests.  Pass
the matching flag (or ``--run-all-expensive``) to enable a tier.

Cost-tier markers
-----------------
  browser            Requires Playwright + Chromium. Opt-in only.
  snapshot           Snapshot regression test; implies browser. One browser session
                     per pytest session; do NOT use with -n/xdist (> 1 worker).
  external_reference Requires the mmdc npm CLI binary. Skips cleanly when absent.
  isolation          Subprocess process-boundary test; verifies import/process wiring.

Canonical tier commands
-----------------------
  # Fast / default — no browser, no mmdc, no subprocess renders
  pytest tests/

  # Browser tests (Playwright, no snapshots) — needs: playwright install chromium
  pytest --run-browser tests/

  # Snapshot regression (one browser session, all baselines)
  pytest --run-snapshots tests/test_snapshots.py

  # Snapshot regression — representative subset only (21 families, 42 items)
  pytest --run-snapshots-quick tests/test_snapshots.py

  # Oracle — committed data only (no mmdc)
  pytest tests/test_oracle.py

  # Oracle — live differential (requires mmdc npm CLI)
  pytest --run-external-reference tests/test_oracle.py

  # Isolation / subprocess tests
  pytest --run-isolation tests/

  # All tests (intentional; requires playwright + mmdc)
  pytest --run-all-expensive tests/
"""
from __future__ import annotations

import multiprocessing
import os
import sys

import pytest


# ---------------------------------------------------------------------------
# Marker registration
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "browser: requires Playwright + Chromium; opt-in with --run-browser",
    )
    config.addinivalue_line(
        "markers",
        "snapshot: snapshot regression test (implies browser); opt-in with --run-snapshots; "
        "do NOT combine with -n/xdist > 1 worker",
    )
    config.addinivalue_line(
        "markers",
        "external_reference: requires the mmdc npm CLI binary; opt-in with --run-external-reference",
    )
    config.addinivalue_line(
        "markers",
        "isolation: subprocess process-boundary / import-isolation test; opt-in with --run-isolation",
    )
    config.addinivalue_line(
        "markers",
        "requires_elk: mark test as requiring elkjs + node",
    )
    config.addinivalue_line(
        "markers",
        "parity_fast: browser-free parity check; run via make parity-fast or pytest -m parity_fast",
    )


# ---------------------------------------------------------------------------
# CLI options
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--snapshot-capture",
        action="store_true",
        default=False,
        help="Re-capture PNG baselines instead of comparing against them.",
    )
    parser.addoption(
        "--run-browser",
        action="store_true",
        default=False,
        help="Run browser-tier tests (requires playwright install chromium).",
    )
    parser.addoption(
        "--run-snapshots",
        action="store_true",
        default=False,
        help="Run snapshot regression tests (implies --run-browser; do not combine with -n > 1).",
    )
    parser.addoption(
        "--run-snapshots-quick",
        action="store_true",
        default=False,
        help="Run snapshot tests for a representative subset only (21 diagram families, 42 items).",
    )
    parser.addoption(
        "--run-external-reference",
        action="store_true",
        default=False,
        help="Run external_reference tests that invoke mmdc.",
    )
    parser.addoption(
        "--run-isolation",
        action="store_true",
        default=False,
        help="Run isolation / subprocess process-boundary tests.",
    )
    parser.addoption(
        "--run-all-expensive",
        action="store_true",
        default=False,
        help="Run all expensive tiers (browser + snapshot + external_reference + isolation).",
    )


# ---------------------------------------------------------------------------
# xdist worker count helper
# ---------------------------------------------------------------------------

def _xdist_worker_count(config) -> int:
    """Return the number of xdist workers configured, or 0 if xdist is not active."""
    try:
        n = config.getoption("numprocesses", default=None)
    except (ValueError, AttributeError):
        return 0
    if n is None:
        return 0
    if str(n).lower() in ("auto", "logical"):
        return multiprocessing.cpu_count()
    try:
        return int(n)
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Collection modifier — enforce opt-in; xdist guard for snapshots
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(config, items):
    run_all = config.getoption("--run-all-expensive", default=False)
    run_browser = config.getoption("--run-browser", default=False) or run_all
    run_snapshots_full = config.getoption("--run-snapshots", default=False) or run_all
    run_snapshots_quick = config.getoption("--run-snapshots-quick", default=False)
    run_snapshots = run_snapshots_full or run_snapshots_quick
    run_external = config.getoption("--run-external-reference", default=False) or run_all
    run_isolation = config.getoption("--run-isolation", default=False) or run_all

    skip_snapshot = pytest.mark.skip(
        reason="snapshot tests require --run-snapshots or --run-all-expensive"
    )
    skip_snapshot_quick = pytest.mark.skip(
        reason="not in representative fixture subset (use --run-snapshots for full corpus)"
    )
    skip_browser = pytest.mark.skip(
        reason="browser tests require --run-browser or --run-all-expensive"
    )
    skip_external = pytest.mark.skip(
        reason="external_reference tests require --run-external-reference or --run-all-expensive"
    )
    skip_isolation = pytest.mark.skip(
        reason="isolation tests require --run-isolation or --run-all-expensive"
    )

    # Representative stems for --run-snapshots-quick (must match test_snapshots._REPRESENTATIVE_STEMS)
    _REPRESENTATIVE_STEMS: frozenset[str] = frozenset({
        "architecture-basic", "block-basic", "c4-basic",
        "class-basic", "er-basic", "flowchart-arrows-defs",
        "gantt-basic", "gitgraph-basic", "journey-basic",
        "kanban-basic", "mindmap-basic", "packet-basic",
        "pie-basic", "quadrant-basic", "requirement-basic",
        "sankey-basic", "sequence-basic", "statediagram-basic",
        "timeline-basic", "xychart-basic", "zenuml-basic",
    })

    snapshot_selected: list = []

    # ELK availability — computed once for requires_elk skip logic
    try:
        _elk_scripts = os.path.join(os.path.dirname(__file__), "..", "scripts")
        if _elk_scripts not in sys.path:
            sys.path.insert(0, _elk_scripts)
        from mermaid_render.layout.elk_adapter import _find_elkjs, _find_node
        _elk_ok = _find_elkjs() is not None and _find_node() is not None
    except Exception:
        _elk_ok = False
    skip_elk = pytest.mark.skip(reason="requires elkjs + node")

    for item in items:
        marker_names = {m.name for m in item.iter_markers()}

        if "snapshot" in marker_names:
            if run_snapshots:
                if run_snapshots_quick and not run_snapshots_full:
                    # Filter to representative stems only.
                    # Test IDs look like: test_snapshot_fused[architecture-basic-light]
                    # Strip trailing -light / -dark to get the stem.
                    node_id = item.nodeid
                    stem = ""
                    if "[" in node_id:
                        param = node_id.split("[", 1)[1].rstrip("]")
                        for suffix in ("-light", "-dark"):
                            if param.endswith(suffix):
                                stem = param[: -len(suffix)]
                                break
                    if stem in _REPRESENTATIVE_STEMS:
                        snapshot_selected.append(item)
                    else:
                        item.add_marker(skip_snapshot_quick)
                else:
                    snapshot_selected.append(item)
            else:
                item.add_marker(skip_snapshot)
        elif "browser" in marker_names:
            if not run_browser:
                item.add_marker(skip_browser)

        if "external_reference" in marker_names and not run_external:
            item.add_marker(skip_external)

        if "isolation" in marker_names and not run_isolation:
            item.add_marker(skip_isolation)

        if "requires_elk" in marker_names and not _elk_ok:
            item.add_marker(skip_elk)

    # xdist guard: snapshot tests require a single worker
    if snapshot_selected:
        workers = _xdist_worker_count(config)
        if workers > 1:
            raise pytest.UsageError(
                f"snapshot tests are not xdist-safe (session cache + single browser). "
                f"Requested {workers} workers. Run without -n or with -n 1:\n"
                f"  pytest --run-snapshots tests/test_snapshots.py"
            )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def browser_lock():
    """Acquire the shared browser resource budget for a non-snapshot browser test.

    Serializes concurrent browser launches against the same OS-level flock that
    the snapshot session uses.  Use as a parameter on any @pytest.mark.browser
    test that launches Chromium outside the snapshot suite.
    """
    from mermaid_render.browser_lock import browser_budget
    with browser_budget():
        yield
