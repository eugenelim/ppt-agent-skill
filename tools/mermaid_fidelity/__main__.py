"""python -m mermaid_fidelity — entry point for the reusable core CLI.

Repository-specific commands (run, capture-reference) require adapters
to be injected from the calling context. This entry point exposes
validate and a self-test.
"""
import sys
from .cli import build_parser


def main() -> int:
    parser = build_parser()
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
