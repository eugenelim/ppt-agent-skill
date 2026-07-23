# ADR-002: Mermaid Render Lift Seam

- **Status:** Informational
- **Date:** 2026-07-22
- **Spec:** [`docs/specs/mermaid-render-rearchitecture/spec.md`](../specs/mermaid-render-rearchitecture/spec.md)

## Context

After the `mermaid-render-rearchitecture` spec, `scripts/mermaid_render/` is a
self-contained rendering package with a documented public API. It has no imports
from any other `scripts/` module; all coupling is inward (layout sub-package,
vendor bundle, icons). Several follow-on projects (server-side rendering, testing
infrastructure, CI tooling) have asked how to consume it independently or whether
it could become a standalone installable.

This ADR records the lift seam — the exact dependency surface, the steps to
extract the package, and the compatibility contract that any shim or re-export
must preserve.

## Dependency surface

| Layer | What it is | Required by |
|---|---|---|
| **Python stdlib** | `argparse`, `base64`, `contextlib`, `dataclasses`, `enum`, `hashlib`, `heapq`, `html`, `json`, `math`, `os`, `re`, `shutil`, `subprocess`, `sys`, `tempfile`, `threading` | All paths |
| **`playwright`** | `playwright.sync_api` — headless Chromium for `to_png()` and the `legacy-dom` SVG fallback | `browser.py` (conditional import; `ImportError` degrades gracefully) |
| **`lxml`** | `lxml.etree` — SVG serialization and namespace-aware DOM manipulation | `svg_serializer.py` (lazy-loaded via `__getattr__`; absent → `to_svg()` / `render_svg_result()` raise `NativeRendererUnavailable`) |
| **`Pillow`** | `PIL.ImageFont` — TrueType font metrics for multi-line text measurement | `layout/_text.py` (used by sequence diagram layout for note row heights) |
| **vendor bundle** | `vendor/dom-to-svg.bundle.js` — bundled JS for the Playwright DOM render path | `browser.py` (path resolved relative to package root at runtime) |
| **icon SVGs** | `icons/*.svg` — inline SVG assets for architecture-canvas nodes | `_icons_cli.py` (resolved relative to package root) |

`to_html()`, `validate()`, `get_capability()`, and `canonicalize_directive()` run
on stdlib only — no optional deps needed.

`to_svg()` and `render_svg_result()` require `lxml`. `to_png()` additionally
requires `playwright`.

## How to lift to a standalone repo

1. **Copy the package directory.**
   ```
   cp -r scripts/mermaid_render/ mermaid-render/src/mermaid_render/
   ```

2. **Add `pyproject.toml`** (PEP 517/518):
   ```toml
   [project]
   name = "mermaid-render"
   dependencies = []  # stdlib-only core

   [project.optional-dependencies]
   svg  = ["lxml>=4.9"]
   png  = ["lxml>=4.9", "playwright>=1.40", "Pillow>=9.0"]
   full = ["lxml>=4.9", "playwright>=1.40", "Pillow>=9.0"]
   ```

3. **Vendor bundle travels with the package.** `vendor/dom-to-svg.bundle.js` is
   resolved via `Path(__file__).parent / "vendor" / "dom-to-svg.bundle.js"` at
   runtime — no path adjustment needed.

4. **Icons travel with the package.** `icons/*.svg` are resolved the same way.
   Include them in `MANIFEST.in` or `[tool.hatch.build]` `include` globs.

5. **No monkey-patching of `mermaid_render` imports** is needed in the host repo
   once the package is installed — the lazy `__getattr__` in `__init__.py` handles
   optional dep absence cleanly.

## Shim compatibility contract

Any caller that imports from `mermaid_render` directly (the current in-repo
usage) or via a shim re-export must satisfy these invariants:

| Contract | Detail |
|---|---|
| **Public API** | `to_html`, `to_svg`, `to_png`, `validate`, `render_svg_result`, `dispatch_native_result`, `get_capability`, `canonicalize_directive`, `RENDERER_REGISTRY`, `DIRECTIVE_ALIASES`, `RendererCapability`, `RenderResult`, `ValidationResult`, `Theme` are all re-exported from `__init__` — no direct sub-module imports needed. |
| **Error types** | `NativeRenderError`, `NativeRendererUnavailable`, `UnsupportedDiagramType`, `UnsupportedDiagramFeature`, `ExperimentalOptInRequired` — all re-exported. Callers must import these from `mermaid_render`, not from sub-modules. |
| **Degraded mode** | If `lxml` or `playwright` is absent, the functions that need them raise `NativeRendererUnavailable` (not `ImportError`). Callers that catch `ImportError` must be updated to catch `NativeRendererUnavailable`. |
| **Env overrides** | `MERMAID_RENDER_SVG_BACKEND=legacy-dom` switches `to_svg()` to the Playwright path. `MERMAID_LAYOUT_ENGINE=python` bypasses ELK (ADR-001). Both must remain honoured. |
| **Thread safety** | `BrowserLock` serialises concurrent `to_png()` calls. If the host repo re-exports the package across worker threads, the lock context must not be replaced. |
| **No `__main__` side effects** | `__main__.py` contains the CLI entry point. Importing `mermaid_render` never invokes `__main__`. |

## Alternatives considered

1. **Keep in-repo forever** — acceptable while the PPT agent skill is the only
   consumer. Deferred lift makes sense while the API is still evolving.
2. **Publish to PyPI immediately** — premature; the public API surface should be
   stable for ≥1 release cycle first. Revisit after `mermaid-p3` stabilises.
3. **Copy-paste per project** — rejected; the vendor bundle and icons would
   diverge immediately.
