"""pytest configuration for mermaid renderer test suite.

Registers the --snapshot-capture option and cost-tier markers.
Must live here (conftest.py) rather than in the test module itself,
since pytest only picks up pytest_addoption/pytest_configure from conftest files.

Cost-tier markers
-----------------
  browser            Requires Playwright + Chromium. Opt-in only.
  snapshot           Snapshot regression test; implies browser. One browser session
                     per pytest session; do NOT use with -n (xdist).
  external_reference Requires the mmdc npm CLI binary. Skips cleanly when absent.
  isolation          Subprocess process-boundary test; verifies import/process wiring.

Canonical tier commands
-----------------------
  # Fast / default — no browser, no mmdc, no subprocess renders
  pytest -m "not browser and not snapshot and not external_reference and not isolation" tests/

  # Browser tests (Playwright, no snapshots)
  pytest -m "browser and not snapshot" tests/

  # Snapshot regression (one browser session, all baselines)
  pytest -m snapshot tests/test_snapshots.py

  # Oracle — committed data only (no mmdc)
  pytest tests/test_oracle.py -m "not external_reference"

  # Oracle — live differential (requires mmdc npm CLI)
  pytest tests/test_oracle.py -m external_reference

  # All tests (intentional)
  pytest tests/
"""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "browser: requires Playwright + Chromium; opt-in only",
    )
    config.addinivalue_line(
        "markers",
        "snapshot: snapshot regression test (implies browser); do NOT combine with -n/xdist",
    )
    config.addinivalue_line(
        "markers",
        "external_reference: requires the mmdc npm CLI binary",
    )
    config.addinivalue_line(
        "markers",
        "isolation: subprocess process-boundary / import-isolation test",
    )


def pytest_addoption(parser):
    parser.addoption(
        "--snapshot-capture",
        action="store_true",
        default=False,
        help="Re-capture PNG baselines instead of comparing against them.",
    )
