"""Backward-compat shim: mermaid_layout._constants → mermaid_render.layout._constants."""
import sys as _sys, pathlib as _p
_sys.path.insert(0, str(_p.Path(__file__).parent.parent))
from mermaid_render.layout import _constants as _real  # noqa: E402
_sys.modules[__name__] = _real
