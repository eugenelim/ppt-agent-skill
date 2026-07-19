#!/usr/bin/env python3
"""build_pdf.py — deterministic, **pixel-1:1** HTML → PDF export.

Why screenshots and not `page.pdf()`: Chrome's PDF/print path is NOT guaranteed
identical to the on-screen render (print media, page box, font hinting), so
`page.pdf()` can drift from the HTML. To guarantee the PDF is **1:1 with the
HTML render**, we screenshot the exact rendered viewport (the proven approach)
and wrap the PNG into a PDF. Tradeoff: text is raster (not selectable) — the
right price for guaranteed visual fidelity on a fixed-size slide.

Toolchain (no ad-hoc installs — both already present): **Playwright** renders +
screenshots (shared _browser.py launcher); **Pillow** wraps PNG→PDF
(`Image.save(..., "PDF")`). Never WeasyPrint, `pdf2svg`, `img2pdf`, or a
`page.pdf()` print export.

Modes:
  * mocks   — each 1280×720 slide HTML → a single-page PDF (or one multi-page
              PDF with --out).
  * --deck  — a deck dir's slide HTMLs (all *.html except the combined
              index-print.html / *preview.html views) → one multi-page PDF, in
              filename order. Without --out the PDF is named after the deck dir
              (the <deck-slug>), so it carries the topic: <deck-slug>.pdf.

Usage:
    python3 scripts/build_pdf.py <a.html> [<b.html> ...] [--out deck.pdf]
    python3 scripts/build_pdf.py ppt-output/style-gallery/            # each *.html → .pdf
    python3 scripts/build_pdf.py --deck ppt-output/<deck-slug>        # → <deck-slug>.pdf
    python3 scripts/build_pdf.py <a.html> --width 1280 --height 720 --scale 2
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

from _browser import get_browser, new_page

ROOT = Path(__file__).resolve().parent.parent


def _natural_key(p: Path):
    """Natural sort key so slide-2 precedes slide-10."""
    return [int(x) if x.isdigit() else x.lower()
            for x in re.split(r'(\d+)', p.stem)]


def resolve_documents(paths: list[str], out: str | None, deck: str | None) -> list[dict]:
    """Pure input→document resolution (testable without a browser). Each document
    is one PDF and its ordered list of absolute source HTML pages."""
    if deck:
        d = Path(deck)
        slides = sorted(
            (h for h in d.glob("*.html")
             if h.name != "index-print.html" and not h.name.endswith("preview.html")),
            key=_natural_key,
        )
        if not slides:
            ip = d / "index-print.html"
            slides = [ip] if ip.exists() else []
        pdf = Path(out).resolve() if out else (d / f"{d.name}.pdf").resolve()
        return [{"pdf": str(pdf), "pages": [str(s.resolve()) for s in slides]}]

    htmls: list[Path] = []
    for p in paths:
        pp = Path(p)
        htmls.extend(sorted(pp.glob("*.html"), key=_natural_key) if pp.is_dir() else [pp])
    htmls = [h.resolve() for h in htmls]
    if out:
        return [{"pdf": str(Path(out).resolve()), "pages": [str(h) for h in htmls]}]
    return [{"pdf": str(h.with_suffix(".pdf")), "pages": [str(h)]} for h in htmls]


def _pngs_to_pdf(pngs: list[Path], pdf: Path, scale: int) -> None:
    from PIL import Image
    frames = [Image.open(p).convert("RGB") for p in pngs]
    if not frames:
        return
    pdf.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(str(pdf), "PDF", resolution=96.0 * scale, save_all=True,
                   append_images=frames[1:])


def render(documents: list[dict], width: int, height: int, scale: int) -> int:
    tmp = Path(tempfile.mkdtemp(prefix="build_pdf_"))
    try:
        pages, i = [], 0
        for doc in documents:
            doc["_pngs"] = []
            for html in doc["pages"]:
                if not Path(html).exists():
                    print(f"skip (no HTML): {html}", file=sys.stderr)
                    continue
                png = tmp / f"p{i}.png"
                i += 1
                pages.append({"html": html, "png": png})
                doc["_pngs"].append(png)

        if not pages:
            print("no HTML pages to render", file=sys.stderr)
            return 1

        try:
            with get_browser() as browser:
                for item in pages:
                    page = new_page(browser, width=width, height=height, scale=float(scale))
                    try:
                        # networkidle fires fast because non-file:// requests are aborted;
                        # wait_for_timeout below is the actual render-settle guard.
                        page.goto("file://" + item["html"], wait_until="networkidle", timeout=30000)
                        page.wait_for_timeout(600)
                        page.screenshot(
                            path=str(item["png"]),
                            clip={"x": 0, "y": 0, "width": width, "height": height},
                        )
                        print(f"shot: {item['png'].name}")
                    except Exception as e:
                        print(f"[ERROR] build_pdf: {Path(item['html']).name}: {e}", file=sys.stderr)
                    finally:
                        try:
                            page.close()
                        except Exception:
                            pass
        except RuntimeError as e:
            print(f"[SKIP] build_pdf: {e}", file=sys.stderr)
            return 1

        for doc in documents:
            shot = [p for p in doc["_pngs"] if p.exists()]
            if shot:
                _pngs_to_pdf(shot, Path(doc["pdf"]), scale)
                print(f"PDF: {doc['pdf']} ({len(shot)} page(s))")
        return 0
    finally:
        for f in tmp.glob("*"):
            f.unlink(missing_ok=True)
        tmp.rmdir()


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic pixel-1:1 HTML→PDF (Playwright screenshot + Pillow).")
    ap.add_argument("paths", nargs="*", help="HTML file(s) or a directory of *.html")
    ap.add_argument("--deck", help="a deck dir; renders its slide HTMLs into one multi-page PDF")
    ap.add_argument("--out", help="output PDF path (combines all inputs into one multi-page PDF)")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--scale", type=int, default=2, help="deviceScaleFactor for crispness (default 2)")
    args = ap.parse_args()

    if not args.paths and not args.deck:
        ap.print_help()
        return 2
    docs = resolve_documents(args.paths, args.out, args.deck)
    if not any(d["pages"] for d in docs):
        print("no HTML inputs found", file=sys.stderr)
        return 1
    return render(docs, args.width, args.height, args.scale)


if __name__ == "__main__":
    sys.exit(main())
