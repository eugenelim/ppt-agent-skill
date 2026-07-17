"""pytest configuration for mermaid renderer test suite.

Registers the --snapshot-capture option used by test_snapshots.py.
Must live here (conftest.py) rather than in the test module itself,
since pytest only picks up pytest_addoption from conftest files.
"""


def pytest_addoption(parser):
    parser.addoption(
        "--snapshot-capture",
        action="store_true",
        default=False,
        help="Re-capture PNG baselines instead of comparing against them.",
    )
