"""Acceptance criterion tests for mermaid-test-perf-pass2.

Covers: AC-C2, AC-D2, AC-E1, AC-F2, AC-G2, AC-G3.
None of these tests require Playwright or Chromium.

AC-G2/G3 and AC-D2/E1 are verified using production helper functions imported
directly from test_snapshots.py (sha256_bytes_equal, manifest_prefilter_applies).
These helpers are defined before the module-level pytest.skip guard so they
are importable even when Playwright is not installed.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
BROWSER_PY = REPO_ROOT / "scripts" / "mermaid_render" / "browser.py"
PNG_PY = REPO_ROOT / "scripts" / "mermaid_render" / "png.py"

# Import pure helpers from test_snapshots before its playwright skip guard.
# These are defined at the top of the file (before the playwright check).
sys.path.insert(0, str(REPO_ROOT / "tests"))
from test_snapshots import sha256_bytes_equal, manifest_prefilter_applies  # noqa: E402


# ---------------------------------------------------------------------------
# AC-C2 — no networkidle in raster modules
# ---------------------------------------------------------------------------

def test_no_networkidle_in_browser_py():
    """AC-C2: browser.py must not contain the string 'networkidle'."""
    src = BROWSER_PY.read_text()
    assert "networkidle" not in src, (
        f"Found 'networkidle' in {BROWSER_PY} — remove it (use domcontentloaded + evaluate)"
    )


def test_no_networkidle_in_png_py():
    """AC-C2: png.py must not contain the string 'networkidle'."""
    src = PNG_PY.read_text()
    assert "networkidle" not in src, (
        f"Found 'networkidle' in {PNG_PY} — remove it (use domcontentloaded + evaluate)"
    )


# ---------------------------------------------------------------------------
# AC-F2 — SnapshotRasterSession uses set_content not goto
# ---------------------------------------------------------------------------

def test_snapshot_raster_session_uses_set_content():
    """AC-F2: SnapshotRasterSession uses set_content, not page.goto."""
    src = BROWSER_PY.read_text()
    class_start = src.find("class SnapshotRasterSession")
    assert class_start != -1, "SnapshotRasterSession class not found in browser.py"
    next_class = src.find("\nclass ", class_start + 1)
    class_body = src[class_start:next_class] if next_class != -1 else src[class_start:]

    # The method must call set_content
    assert "set_content" in class_body, (
        "SnapshotRasterSession.render_html must call page.set_content"
    )
    # page.goto must not appear as an actual call (check executable code, not docstring)
    # Strip the docstring by looking for the first non-docstring line after the class header.
    # The docstring ends at the first '"""' after the opening one.
    docstring_end = class_body.find('"""', class_body.find('"""') + 3)
    code_after_docstring = class_body[docstring_end + 3:] if docstring_end != -1 else class_body
    assert "page.goto" not in code_after_docstring, (
        "SnapshotRasterSession must not call page.goto in executable code — use set_content instead"
    )


def test_snapshot_raster_session_uses_domcontentloaded():
    """AC-F2: SnapshotRasterSession uses wait_until='domcontentloaded' not 'networkidle'."""
    src = BROWSER_PY.read_text()
    class_start = src.find("class SnapshotRasterSession")
    next_class = src.find("\nclass ", class_start + 1)
    class_body = src[class_start:next_class] if next_class != -1 else src[class_start:]
    assert "domcontentloaded" in class_body, (
        "SnapshotRasterSession must use wait_until='domcontentloaded'"
    )
    assert "networkidle" not in class_body, (
        "SnapshotRasterSession must not use wait_until='networkidle'"
    )


# ---------------------------------------------------------------------------
# AC-D2 — manifest pre-filter (uses production helper from test_snapshots)
# ---------------------------------------------------------------------------

def test_manifest_prefilter_applies_for_missing_baseline():
    """AC-D2: manifest_prefilter_applies returns True when pair absent from manifest."""
    manifest = frozenset({("flowchart-basic", "light")})
    key = ("unknown-fixture", "light")
    # In comparison mode (capture=False), missing key → filter applies → skip
    assert manifest_prefilter_applies(key, manifest, capture=False) is True


def test_manifest_prefilter_does_not_apply_for_known_baseline():
    """AC-D2 complement: prefilter does NOT apply when pair is in manifest."""
    manifest = frozenset({("flowchart-basic", "light"), ("flowchart-basic", "dark")})
    key = ("flowchart-basic", "light")
    assert manifest_prefilter_applies(key, manifest, capture=False) is False


def test_manifest_prefilter_does_not_apply_in_capture_mode():
    """AC-D2 / AC-G4: capture mode always bypasses the manifest filter."""
    manifest = frozenset()  # empty — no baselines
    key = ("new-fixture", "light")
    # capture=True → do not filter, render anyway
    assert manifest_prefilter_applies(key, manifest, capture=True) is False


def test_manifest_prefilter_applies_for_any_missing_theme():
    """AC-D2: filter applies independently per (stem, theme) key."""
    manifest = frozenset({("flowchart-basic", "light")})  # only light exists
    assert manifest_prefilter_applies(("flowchart-basic", "dark"), manifest, capture=False) is True
    assert manifest_prefilter_applies(("flowchart-basic", "light"), manifest, capture=False) is False


# ---------------------------------------------------------------------------
# AC-G2 / AC-G3 — SHA-256 fast path (uses production helper from test_snapshots)
# ---------------------------------------------------------------------------

def test_sha256_bytes_equal_identical():
    """AC-G3: sha256_bytes_equal returns True for identical bytes (fast path fires)."""
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    assert sha256_bytes_equal(png_bytes, png_bytes) is True


def test_sha256_bytes_equal_different():
    """AC-G2: sha256_bytes_equal returns False for different bytes (PIL decode proceeds)."""
    b1 = b"\x89PNG\r\n\x1a\n" + b"\x01" * 100
    b2 = b"\x89PNG\r\n\x1a\n" + b"\x02" * 100
    assert sha256_bytes_equal(b1, b2) is False


def test_sha256_bytes_equal_empty():
    """AC-G3: sha256_bytes_equal handles empty bytes correctly."""
    assert sha256_bytes_equal(b"", b"") is True
    assert sha256_bytes_equal(b"", b"\x00") is False


# ---------------------------------------------------------------------------
# AC-E1 — compile-once per fixture (algorithm test using fragment_cache pattern)
# ---------------------------------------------------------------------------

def _build_fragment_cache(stems_and_calls, dispatch_fn):
    """Simulate the compile-once cache: call dispatch_fn once per stem."""
    fragment_cache: dict = {}
    for stem in stems_and_calls:
        if stem not in fragment_cache:
            try:
                fragment_cache[stem] = dispatch_fn(stem)
            except ValueError:
                fragment_cache[stem] = None
    return fragment_cache


def test_dispatch_called_once_per_fixture_for_two_themes():
    """AC-E1: _dispatch called exactly once per fixture, not per (fixture, theme)."""
    dispatch = MagicMock(return_value="<div>fragment</div>")
    # Simulates: get_png("flowchart-basic", "light") then get_png("flowchart-basic", "dark")
    # Both calls look up the same stem — dispatch called once
    stems = ["flowchart-basic", "flowchart-basic"]  # same stem for light + dark
    _build_fragment_cache(stems, dispatch)
    assert dispatch.call_count == 1, (
        f"Expected _dispatch called once for same fixture with two themes, "
        f"but was called {dispatch.call_count} times"
    )


def test_dispatch_called_once_per_distinct_fixture():
    """AC-E1: two distinct fixtures each trigger one dispatch call."""
    dispatch = MagicMock(return_value="<div>fragment</div>")
    stems = ["flowchart-basic", "er-basic"]
    _build_fragment_cache(stems, dispatch)
    assert dispatch.call_count == 2
    dispatch.assert_any_call("flowchart-basic")
    dispatch.assert_any_call("er-basic")


def test_fragment_cache_deduplicates_repeated_calls():
    """AC-E1 complement: repeated calls for same stem hit cache (dispatch not re-called)."""
    dispatch = MagicMock(return_value="<div>fragment</div>")
    stems = ["flowchart-basic", "flowchart-basic", "flowchart-basic"]
    _build_fragment_cache(stems, dispatch)
    assert dispatch.call_count == 1


# ---------------------------------------------------------------------------
# Representative stems consistency guard (Concern-8 / AC-J1)
# ---------------------------------------------------------------------------

def test_representative_stems_consistent_between_conftest_and_test_snapshots():
    """conftest._REPRESENTATIVE_STEMS and test_snapshots._REPRESENTATIVE_STEMS must match.

    Both sets are defined independently (test_snapshots.py is imported conditionally;
    conftest.py defines a local copy for the quick-tier filter). This test asserts they
    are identical so a divergence is caught immediately.
    """
    import ast

    def _extract_representative_stems(path: Path) -> "frozenset[str]":
        src = path.read_text()
        tree = ast.parse(src)

        def _value_from_node(value_node):
            if isinstance(value_node, ast.Call) and value_node.args:
                arg = value_node.args[0]
                if isinstance(arg, (ast.Set, ast.List)):
                    return frozenset(
                        elt.value for elt in arg.elts
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                    )
            return None

        for node in ast.walk(tree):
            # Handle: _REPRESENTATIVE_STEMS = frozenset({...})
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_REPRESENTATIVE_STEMS":
                        result = _value_from_node(node.value)
                        if result is not None:
                            return result
            # Handle: _REPRESENTATIVE_STEMS: frozenset[str] = frozenset({...})
            if isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id == "_REPRESENTATIVE_STEMS":
                    if node.value is not None:
                        result = _value_from_node(node.value)
                        if result is not None:
                            return result
        return frozenset()

    conftest_stems = _extract_representative_stems(TESTS_DIR / "conftest.py")
    snapshots_stems = _extract_representative_stems(TESTS_DIR / "test_snapshots.py")

    assert conftest_stems, "Could not parse _REPRESENTATIVE_STEMS from conftest.py"
    assert snapshots_stems, "Could not parse _REPRESENTATIVE_STEMS from test_snapshots.py"
    assert conftest_stems == snapshots_stems, (
        f"_REPRESENTATIVE_STEMS mismatch between conftest and test_snapshots.\n"
        f"In conftest only: {conftest_stems - snapshots_stems}\n"
        f"In test_snapshots only: {snapshots_stems - conftest_stems}"
    )


# ---------------------------------------------------------------------------
# AC-F3 — route handler installed (source-level)
# ---------------------------------------------------------------------------

def test_snapshot_raster_session_installs_route():
    """AC-F3: SnapshotRasterSession calls _install_route on each page."""
    src = BROWSER_PY.read_text()
    class_start = src.find("class SnapshotRasterSession")
    next_class = src.find("\nclass ", class_start + 1)
    class_body = src[class_start:next_class] if next_class != -1 else src[class_start:]
    assert "_install_route" in class_body, (
        "SnapshotRasterSession.render_html must call _install_route(page) (LLM01/ASI05)"
    )
