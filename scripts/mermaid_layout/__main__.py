"""Backward-compat shim: python3 scripts/mermaid_layout → mermaid_render.layout.__main__.

Delegates to the real CLI entry point in mermaid_render.layout.__main__.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from mermaid_render.layout.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
