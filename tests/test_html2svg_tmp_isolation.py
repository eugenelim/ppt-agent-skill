#!/usr/bin/env python3
"""test_html2svg_tmp_isolation.py — Playwright-contract assertions for html2svg.py.

Verifies that html2svg.py:
- has no Puppeteer/Node bootstrap code (make_run_tmp, ensure_deps, CONVERT_SCRIPT, etc.)
- uses an unguarded top-level bare import from _browser
- wraps get_browser() in a RuntimeError catch (not ImportError)
- has no subprocess node invocations
- has no pdf2svg fallback
- SVG output from a fixture HTML contains at least one <text> element (requires Chromium)
- images outside the deck root are skipped with a stderr warning (requires Chromium)

No pytest harness for the script portion; run directly or via smoke_test.py.
Exit 0 = all pass, 1 = a failure. Pytest classes at the bottom for CI coverage.
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import html2svg as H  # noqa: E402


if __name__ == "__main__":
    FAILS: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"  [{'OK' if cond else 'XX'}] {name}")
        if not cond:
            FAILS.append(name)

    def main() -> int:
        src = (ROOT / "scripts" / "mermaid_render" / "svg.py").read_text()

        # Old Puppeteer helpers must be gone
        check("make_run_tmp removed", "def make_run_tmp(" not in src)
        check("ensure_deps removed", "def ensure_deps(" not in src)
        check("convert_dom_to_svg removed", "def convert_dom_to_svg(" not in src)
        check("convert_pdf2svg removed", "def convert_pdf2svg(" not in src)
        check("CONVERT_SCRIPT removed", "CONVERT_SCRIPT" not in src)
        check("FALLBACK_SCRIPT removed", "FALLBACK_SCRIPT" not in src)
        check("BUNDLE_ENTRY removed", "BUNDLE_ENTRY" not in src)

        # Bare unguarded top-level import (relative, from mermaid_render.svg)
        check("bare import from .browser present", "from .browser import" in src)
        lines = src.splitlines()
        import_lines = [l for l in lines if "from .browser import" in l]
        for il in import_lines:
            check(f"import line not indented (unguarded): {il.strip()!r}",
                  not il.startswith(" ") and not il.startswith("\t"))

        # RuntimeError catch, not ImportError
        check("RuntimeError catch present", "RuntimeError" in src)
        check("no ImportError catch on import", "except ImportError" not in src)

        # No node subprocess calls
        check("no subprocess node call", '"node"' not in src and "'node'" not in src)

        # pdf2svg fallback removed
        check("no convert_pdf2svg reference", "convert_pdf2svg" not in src)
        check("no pdf2svg reference", "pdf2svg" not in src)

        # page.add_script_tag present (dom-to-svg bundle injection)
        check("page.add_script_tag present", "page.add_script_tag(" in src)

        # Deck-root confinement in Python
        check("_within_deck_root used in Python", "_within_deck_root" in src)

        # Docstring updated
        check("docstring references Playwright", "Playwright" in src)

        # --- SVG output fixture test (requires Chromium + playwright) ---
        bundle = ROOT / "scripts" / "vendor" / "dom-to-svg.bundle.js"
        if not bundle.exists():
            check("dom-to-svg bundle exists", False)
        else:
            fixture_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>body{margin:0;background:#fff}h1{font-size:24px;color:#333}</style>
</head><body>
<h1>Test Heading</h1>
<p>Some paragraph text for SVG assertion.</p>
</body></html>"""
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                html_file = tmp_path / "fixture.html"
                html_file.write_text(fixture_html, encoding="utf-8")
                out_dir = tmp_path / "svg"
                ok = H.convert(html_file, out_dir)
                if not ok:
                    check("convert() returned True on fixture", False)
                else:
                    svg_out = out_dir / "fixture.svg"
                    check("SVG output file exists", svg_out.exists())
                    if svg_out.exists():
                        content = svg_out.read_text(encoding="utf-8")
                        text_count = content.count("<text ")
                        check(f"SVG contains >=1 <text> element (got {text_count})", text_count >= 1)

        if FAILS:
            print(f"FAIL: {len(FAILS)} check(s) failed")
            return 1
        print("all pass")
        return 0

    sys.exit(main())


class TestOutOfRootImageConfinement:
    """Deck-root confinement: images outside root are skipped + warned (requires Chromium)."""

    _BUNDLE = ROOT / "scripts" / "vendor" / "dom-to-svg.bundle.js"

    @pytest.mark.skipif(
        not (ROOT / "scripts" / "vendor" / "dom-to-svg.bundle.js").exists(),
        reason="dom-to-svg bundle not built",
    )
    def test_out_of_root_image_skipped_and_warned(self, tmp_path, capsys):
        # Layout: deck_root/slides/slide-1.html references ../../../outside/img.png
        # which resolves outside deck_root — must be skipped with a warning.
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        img_file = outside_dir / "img.png"
        # Minimal 1×1 red PNG bytes
        img_file.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        deck_root = tmp_path / "deck"
        slides_dir = deck_root / "slides"
        slides_dir.mkdir(parents=True)
        html_file = slides_dir / "slide-1.html"
        # The src path escapes the deck root via ../../outside
        html_file.write_text(
            '<!DOCTYPE html><html><body>'
            '<img src="../../outside/img.png">'
            '<h1>Hello</h1>'
            '</body></html>',
            encoding="utf-8",
        )

        out_dir = tmp_path / "svg"
        import html2svg as H
        result = H.convert(html_file, out_dir)

        captured = capsys.readouterr()
        # The out-of-root image should trigger the confinement warning on stderr
        assert "Skipping image outside deck directory" in captured.err, (
            f"Expected confinement warning in stderr, got: {captured.err!r}"
        )
        # The SVG should not contain the base64 of that image
        svg_out = out_dir / "slide-1.svg"
        if svg_out.exists():
            content = svg_out.read_text(encoding="utf-8")
            assert "data:image/png;base64" not in content, (
                "Out-of-root image must not appear as base64 in SVG"
            )
