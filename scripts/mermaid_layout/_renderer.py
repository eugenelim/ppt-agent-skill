"""Backward-compat shim: mermaid_layout._renderer → mermaid_render.layout._renderer."""
import sys as _sys, pathlib as _p
_sys.path.insert(0, str(_p.Path(__file__).parent.parent))
from mermaid_render.layout import _renderer as _real  # noqa: E402
_sys.modules[__name__] = _real
