#!/usr/bin/env python3
"""mermaid_render.png — HTML -> high-DPI PNG via Playwright.

All CSS features are preserved; text becomes pixels (not editable in PPT).
"""

import re
import sys
import tempfile
from pathlib import Path

from .browser import get_browser, new_page


def convert(html_dir: Path, output_dir: Path, scale: float = 1.0, full_page: bool = False) -> bool:
    """Main conversion entry point."""
    if html_dir.is_file():
        html_files = [html_dir]
    else:
        html_files = sorted(
            html_dir.glob("*.html"),
            key=lambda p: [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", p.stem)],
        )

    if not html_files:
        print(f"No HTML files in {html_dir}", file=sys.stderr)
        return False

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with get_browser() as browser:
            print(f"Converting {len(html_files)} HTML files -> PNG ({scale}x scale)...")
            ok = 0
            for f in html_files:
                page = new_page(browser, width=1280, height=720, scale=scale)
                try:
                    page.goto("file://" + str(f), wait_until="networkidle", timeout=30000)
                    page.evaluate(
                        """async () => {
                            await document.fonts.ready;
                            const imgs = Array.from(document.querySelectorAll('img'));
                            await Promise.all(imgs.map(img => {
                                if (img.complete) return Promise.resolve();
                                return new Promise(r => { img.onload = r; img.onerror = r; });
                            }));
                        }"""
                    )
                    out_path = output_dir / (f.stem + ".png")
                    if full_page:
                        page.screenshot(path=str(out_path), type="png", full_page=True)
                    else:
                        page.screenshot(
                            path=str(out_path),
                            type="png",
                            full_page=False,
                            clip={"x": 0, "y": 0, "width": 1280, "height": 720},
                        )
                    print(f"PNG: {f.name} -> {out_path.name}")
                    ok += 1
                except Exception as e:
                    print(f"[ERROR] html2png: {f.name}: {e}", file=sys.stderr)
                finally:
                    try:
                        page.close()
                    except Exception:
                        pass
            print(f"\nDone! {ok}/{len(html_files)} PNGs -> {output_dir}")
            return ok > 0
    except RuntimeError as e:
        print(f"[SKIP] html2png: {e}", file=sys.stderr)
        return False


def _to_png_from_html_file(html_path: Path, scale: float = 1.0) -> bytes:
    """Convert a single HTML file on disk to PNG bytes."""
    with get_browser() as browser:
        page = new_page(browser, width=1280, height=720, scale=scale)
        try:
            page.goto("file://" + str(html_path), wait_until="networkidle", timeout=30000)
            page.evaluate(
                """async () => {
                    await document.fonts.ready;
                    const imgs = Array.from(document.querySelectorAll('img'));
                    await Promise.all(imgs.map(img => {
                        if (img.complete) return Promise.resolve();
                        return new Promise(r => { img.onload = r; img.onerror = r; });
                    }));
                }"""
            )
            return page.screenshot(type="png", full_page=True)
        finally:
            try:
                page.close()
            except Exception:
                pass


def _to_png_from_html_string(html: str, scale: float = 1.0) -> bytes:
    """Convert an HTML string to PNG bytes via a temporary file."""
    with tempfile.TemporaryDirectory() as tmp:
        html_file = Path(tmp) / "diagram.html"
        html_file.write_text(html, encoding="utf-8")
        return _to_png_from_html_file(html_file, scale=scale)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print("Usage: python3 scripts/html2png.py <html_dir_or_file> [-o output_dir] [--scale 1] [--fullpage]")
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    html_path = Path(sys.argv[1]).resolve()

    output_dir = None
    scale = 1.0
    full_page = False

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "-o" and i + 1 < len(args):
            output_dir = Path(args[i + 1]).resolve()
            i += 2
        elif args[i] == "--scale" and i + 1 < len(args):
            scale = float(args[i + 1])
            i += 2
        elif args[i] == "--fullpage":
            full_page = True
            i += 1
        else:
            i += 1

    if output_dir is None:
        output_dir = (html_path.parent if html_path.is_file() else html_path.parent) / "png"

    success = convert(html_path, output_dir, scale, full_page)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
