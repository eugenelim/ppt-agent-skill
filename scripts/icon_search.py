#!/usr/bin/env python3
"""Backward-compat shim: icon_search → mermaid_render._icons_cli."""
import sys as _sys
import pathlib as _p

_sys.path.insert(0, str(_p.Path(__file__).parent))
from mermaid_render import _icons_cli as _real  # noqa: E402

_sys.modules[__name__] = _real

if __name__ == "__main__":
    _sys.exit(_real.main())
