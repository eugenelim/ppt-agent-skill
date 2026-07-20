#!/usr/bin/env python3
"""Backward-compat shim: html2png → mermaid_render.png.

Replaces the original implementation; the real code lives in
scripts/mermaid_render/png.py. Using sys.modules aliasing so
direct attribute access reaches the real module.
"""
import sys as _sys
import pathlib as _p

_sys.path.insert(0, str(_p.Path(__file__).parent))
from mermaid_render import png as _real  # noqa: E402
_sys.modules[__name__] = _real

# __name__ remains "__main__" here even after the sys.modules alias above, so
# subprocess invocations (python3 html2png.py ...) reach _real.main() correctly.
if __name__ == "__main__":
    _real.main()
