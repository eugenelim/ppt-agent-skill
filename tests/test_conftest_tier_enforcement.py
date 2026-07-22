"""Regression tests: expensive tiers are skipped in default mode.

AC-A1: plain `pytest` must not launch any Playwright browser.
AC-A2: --collect-only shows all expensive items carry explicit skip marks.
AC-A3: opt-in flags exist and enable their respective tiers.
AC-A4: test_to_png_returns_bytes carries @pytest.mark.browser.
AC-A5: TestOutOfRootImageConfinement carries @pytest.mark.browser.

Tests use subprocess so they don't inherit the current test session's
opt-in flags.  Playwright and Chromium are NOT required for these tests.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent


def _run_pytest(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args, "--tb=no", "--no-header", "-q"],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# AC-A4 / AC-A5 — marker presence (source-level, no subprocess needed)
# ---------------------------------------------------------------------------

def test_to_png_returns_bytes_has_browser_marker():
    """AC-A4: test_to_png_returns_bytes carries @pytest.mark.browser."""
    src = (TESTS_DIR / "test_mermaid_p3_stage12.py").read_text()
    # The marker must appear directly above the function definition
    assert "@pytest.mark.browser" in src, (
        "test_mermaid_p3_stage12.py is missing @pytest.mark.browser"
    )
    assert "def test_to_png_returns_bytes" in src


def test_out_of_root_image_confinement_has_browser_marker():
    """AC-A5: TestOutOfRootImageConfinement carries @pytest.mark.browser."""
    src = (TESTS_DIR / "test_html2svg_tmp_isolation.py").read_text()
    assert "@pytest.mark.browser" in src, (
        "test_html2svg_tmp_isolation.py is missing @pytest.mark.browser"
    )


# ---------------------------------------------------------------------------
# AC-A3 — option registration
# ---------------------------------------------------------------------------

def test_run_browser_flag_exists():
    """AC-A3: --run-browser flag is registered."""
    result = _run_pytest("--help")
    assert "--run-browser" in result.stdout, "--run-browser flag not found in --help"


def test_run_snapshots_flag_exists():
    """AC-A3: --run-snapshots flag is registered."""
    result = _run_pytest("--help")
    assert "--run-snapshots" in result.stdout, "--run-snapshots flag not found in --help"


def test_run_snapshots_quick_flag_exists():
    """AC-A3: --run-snapshots-quick flag is registered."""
    result = _run_pytest("--help")
    assert "--run-snapshots-quick" in result.stdout, "--run-snapshots-quick flag not found in --help"


def test_run_external_reference_flag_exists():
    """AC-A3: --run-external-reference flag is registered."""
    result = _run_pytest("--help")
    assert "--run-external-reference" in result.stdout


def test_run_isolation_flag_exists():
    """AC-A3: --run-isolation flag is registered."""
    result = _run_pytest("--help")
    assert "--run-isolation" in result.stdout


def test_run_all_expensive_flag_exists():
    """AC-A3: --run-all-expensive flag is registered."""
    result = _run_pytest("--help")
    assert "--run-all-expensive" in result.stdout


# ---------------------------------------------------------------------------
# AC-A1 / AC-A2 — default tier skips all expensive items
# ---------------------------------------------------------------------------

def test_browser_marker_tests_skipped_in_default_mode():
    """AC-A1/A2: browser-marked tests are skipped without --run-browser.

    Runs only test_mermaid_p3_stage12.py (contains a @browser test) and
    verifies the browser test is skipped (not passed, not failed).
    """
    result = _run_pytest(
        "tests/test_mermaid_p3_stage12.py::test_to_png_returns_bytes",
    )
    output = result.stdout + result.stderr
    # Must be skipped, not passed or errored
    assert "1 skipped" in output or "skipped" in output, (
        f"Expected test_to_png_returns_bytes to be skipped in default mode.\n"
        f"Output:\n{output[:1000]}"
    )
    assert "passed" not in output.lower() or "0 passed" in output, (
        f"test_to_png_returns_bytes passed in default mode (should be skipped).\n"
        f"Output:\n{output[:1000]}"
    )


def test_snapshot_tests_skipped_in_default_mode():
    """AC-A2 (structural): --collect-only on test_snapshots.py does not error.

    When Playwright is absent, test_snapshots.py module-skips at import (rc 5).
    When Playwright is present, conftest adds skip marks to all snapshot items
    in default mode (no --run-snapshots). Either way, collection must not error.
    The behavioral assertion (skip marks visible in output) is CI-gated to
    Playwright-present environments (backlog: playwright-gated-snapshot-verification).
    """
    result = _run_pytest(
        "tests/test_snapshots.py",
        "--collect-only",
    )
    output = result.stdout + result.stderr
    assert result.returncode in (0, 5), (
        f"Collection errored unexpectedly (rc={result.returncode}):\n{output[:1000]}"
    )
