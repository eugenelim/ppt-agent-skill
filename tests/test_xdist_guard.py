"""Guard: snapshot tests must fail when invoked with xdist -n > 1."""
import subprocess
import sys


def test_snapshot_xdist_guard():
    """Collection must be rejected when -n > 1 is paired with --run-snapshots.

    The guard lives in pytest_collection_modifyitems (conftest.py).  It fires
    on the controller process during collection, before any test runs — which
    is why --collect-only is used here: it keeps the subprocess fast (no
    Playwright/Chromium needed) and hits the exact code path the guard lives on.
    """
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest", "tests/test_snapshots.py",
            "-n", "2", "--run-snapshots", "--collect-only",
            "-q", "--no-header", "--tb=no",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, (
        "Expected non-zero exit when snapshots run with xdist"
    )
    combined = result.stdout + result.stderr
    assert "not xdist-safe" in combined, (
        f"Expected 'not xdist-safe' in output; got:\n{combined[:500]}"
    )
