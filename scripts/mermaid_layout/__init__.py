"""Backward-compat shim: mermaid_layout → mermaid_render.layout.

Replaces the original implementation; the real code lives in
scripts/mermaid_render/layout/. Using sys.modules aliasing so
`from mermaid_layout import X` and `from mermaid_layout._strategies import Y`
both reach the real module and its attributes.
"""
import sys as _sys
import pathlib as _p

_sys.path.insert(0, str(_p.Path(__file__).parent.parent))
from mermaid_render import layout as _real  # noqa: E402

_pkg = __name__  # "mermaid_layout"
_sys.modules[_pkg] = _real

# Pre-register submodule aliases so `from mermaid_layout._strategies import X`
# resolves to the already-loaded mermaid_render.layout submodules without
# re-loading the original _*.py files on disk.
for _sub in ("_constants", "_parser", "_layout", "_routing", "_renderer", "_strategies"):
    _key_real = f"mermaid_render.layout.{_sub}"
    if _key_real in _sys.modules:
        _sys.modules[f"{_pkg}.{_sub}"] = _sys.modules[_key_real]
