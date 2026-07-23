"""Batched browser runner for Mermaid geometry capture.

This module is browser-dependent and must be gated with:
    @pytest.mark.browser
    @pytest.mark.skipif(not _HAVE_PLAYWRIGHT, reason="playwright not installed")

The BatchRunner opens ONE Playwright Chromium context and iterates
all fixtures in that single context — it never spawns one process
per fixture.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext  # type: ignore[import-untyped]
    _HAVE_PLAYWRIGHT = True
except ImportError:
    _HAVE_PLAYWRIGHT = False

from tools.mermaid_fidelity.capture.extractor import extract_diagram
from tools.mermaid_fidelity.capture.provenance import record_provenance
from tools.mermaid_fidelity.capture.cache import DiagramCache
from tools.mermaid_fidelity.capture.versions import MERMAID_CLI_VERSION
from tools.mermaid_fidelity.models import ReferenceDiagram, ComparisonStatus, ExtractorGap


# Minimal HTML page to host a Mermaid render
_MERMAID_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>body {{ margin: 0; padding: 0; background: white; }}</style>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@{mermaid_version}/dist/mermaid.min.js"></script>
</head>
<body>
  <div class="mermaid">
{source}
  </div>
  <script>
    mermaid.initialize({{ startOnLoad: true }});
  </script>
</body>
</html>"""


class BatchRunner:
    """Renders a list of Mermaid fixtures in a single long-lived browser session.

    Usage::

        runner = BatchRunner()
        results = runner.render_all(fixture_sources)

    Args:
        cache_dir: Path to the cache directory; defaults to .cache/mermaid_reference/.
        viewport_width: Browser viewport width in CSS pixels.
        viewport_height: Browser viewport height in CSS pixels.
        mermaid_version: Mermaid CDN version to load (defaults to locked version).
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        viewport_width: int = 1200,
        viewport_height: int = 900,
        mermaid_version: str = MERMAID_CLI_VERSION,
    ) -> None:
        if not _HAVE_PLAYWRIGHT:
            raise RuntimeError(
                "Playwright is not installed. "
                "Install it with: pip install playwright && playwright install chromium"
            )
        self._cache = DiagramCache(cache_dir)
        self._viewport_width = viewport_width
        self._viewport_height = viewport_height
        self._mermaid_version = mermaid_version

    def render_all(
        self,
        fixture_sources: list[tuple[str, str, str]],
        *,
        use_cache: bool = True,
    ) -> list[ReferenceDiagram]:
        """Render all fixtures in a single browser session.

        Args:
            fixture_sources: List of (fixture_stem, diagram_type, mmd_source) tuples.
            use_cache: Whether to use/populate the file cache.

        Returns:
            List of ReferenceDiagram records, one per fixture.
        """
        results: list[ReferenceDiagram] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            chromium_version = browser.version

            context = browser.new_context(
                viewport={"width": self._viewport_width, "height": self._viewport_height},
            )

            for fixture_stem, diagram_type, source in fixture_sources:
                source_hash = hashlib.sha256(source.encode()).hexdigest()

                # Check cache first
                if use_cache:
                    cached = self._cache.get(
                        source_hash=source_hash,
                        mermaid_version=self._mermaid_version,
                        browser_version=chromium_version,
                        font_fingerprint="",  # computed after first render
                    )
                    if cached is not None:
                        results.append(cached)
                        continue

                # Render via browser
                diagram = self._render_one(
                    context, fixture_stem, diagram_type, source,
                    source_hash, chromium_version,
                )

                if use_cache:
                    prov = diagram.provenance
                    self._cache.put(
                        diagram,
                        source_hash=source_hash,
                        mermaid_version=self._mermaid_version,
                        browser_version=chromium_version,
                        font_fingerprint=prov.font_fingerprint,
                    )

                results.append(diagram)

            context.close()
            browser.close()

        return results

    def _render_one(
        self,
        context: "BrowserContext",
        fixture_stem: str,
        diagram_type: str,
        source: str,
        source_hash: str,
        chromium_version: str,
    ) -> ReferenceDiagram:
        """Render one fixture in the shared browser context."""
        page = context.new_page()
        try:
            # Build the HTML page content
            html = _MERMAID_HTML_TEMPLATE.format(
                mermaid_version=self._mermaid_version,
                source=source,
            )

            # Write to a temp file and navigate to it
            with tempfile.NamedTemporaryFile(
                suffix=".html", mode="w", delete=False, encoding="utf-8"
            ) as f:
                f.write(html)
                tmp_path = Path(f.name)

            try:
                page.goto(f"file://{tmp_path}", wait_until="networkidle")
                # Wait for Mermaid to render
                page.wait_for_selector(".mermaid svg", timeout=15000)

                # Extract SVG from DOM
                svg_text = page.eval_on_selector(
                    ".mermaid svg",
                    "el => el.outerHTML",
                )
            finally:
                tmp_path.unlink(missing_ok=True)

            # Record provenance
            prov = record_provenance(
                source_hash=source_hash,
                fixture=fixture_stem,
            )
            # Patch in the actual chromium version
            import dataclasses
            prov = dataclasses.replace(prov, chromium_version=chromium_version)

            return extract_diagram(
                svg_text=svg_text,
                fixture_stem=fixture_stem,
                diagram_type=diagram_type,
                provenance=prov,
            )

        except Exception as exc:  # noqa: BLE001
            prov = record_provenance(source_hash=source_hash, fixture=fixture_stem)
            return ReferenceDiagram(
                fixture_stem=fixture_stem,
                diagram_type=diagram_type,
                canvas_bounds=__import__("tools.mermaid_fidelity.models", fromlist=["BoundingBox"]).BoundingBox(
                    x=0, y=0, width=0, height=0,
                ),
                view_box=None,
                provenance=prov,
                gaps=[ExtractorGap(field="render", reason=str(exc))],
                status=ComparisonStatus.REFERENCE_RENDER_FAILURE,
            )
        finally:
            page.close()
