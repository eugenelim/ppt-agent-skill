#!/usr/bin/env python3
"""build_pdf.py — deterministic, **pixel-1:1** HTML → PDF export.

Why screenshots and not `page.pdf()`: Chrome's PDF/print path is NOT guaranteed
identical to the on-screen render (print media, page box, font hinting), so
`page.pdf()` can drift from the HTML. To guarantee the PDF is **1:1 with the
HTML render**, we screenshot the exact rendered viewport (the proven approach)
and wrap the PNG into a PDF. Tradeoff: text is raster (not selectable) — the
right price for guaranteed visual fidelity on a fixed-size slide.

Toolchain (no ad-hoc installs — both already present): **Puppeteer** renders +
screenshots (same provisioning as gallery.py); **Pillow** wraps PNG→PDF
(`Image.save(..., "PDF")`). Never WeasyPrint, `pdf2svg`, `img2pdf`, or a
`page.pdf()` print export.

Modes:
  * mocks   — each 1280×720 slide HTML → a single-page PDF (or one multi-page
              PDF with --out).
  * --deck  — a deck dir's slide HTMLs (all *.html except index-print.html) →
              one multi-page PDF, in filename order.

Usage:
    python3 scripts/build_pdf.py <a.html> [<b.html> ...] [--out deck.pdf]
    python3 scripts/build_pdf.py ppt-output/style-gallery/            # each *.html → .pdf
    python3 scripts/build_pdf.py --deck ppt-output/<deck-dir> [--out deck.pdf]
    python3 scripts/build_pdf.py <a.html> --width 1280 --height 720 --scale 2
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Screenshot the exact rendered viewport → guaranteed 1:1 with the HTML.
NODE_TEMPLATE = """
const puppeteer = require('puppeteer');
const fs = require('fs');
(async () => {
  const cfg = JSON.parse(process.argv[2]);
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu',
           '--font-render-hinting=none', '--force-color-profile=srgb']
  });
  for (const pg of cfg.pages) {
    if (!fs.existsSync(pg.html)) { console.warn('skip (no HTML): ' + pg.html); continue; }
    const page = await browser.newPage();
    await page.setViewport({ width: cfg.width, height: cfg.height, deviceScaleFactor: cfg.scale });
    await page.goto('file://' + pg.html, { waitUntil: 'networkidle0', timeout: 30000 });
    await new Promise(r => setTimeout(r, 600));
    // clip to the exact page box so output == the rendered viewport, no scrollbars
    await page.screenshot({ path: pg.png, clip: { x: 0, y: 0, width: cfg.width, height: cfg.height } });
    console.log('shot: ' + pg.png);
    await page.close();
  }
  await browser.close();
  console.log('Done: ' + cfg.pages.length + ' screenshot(s)');
})();
"""


def resolve_documents(paths: list[str], out: str | None, deck: str | None) -> list[dict]:
    """Pure input→document resolution (testable without a browser). Each document
    is one PDF and its ordered list of absolute source HTML pages."""
    if deck:
        d = Path(deck)
        slides = sorted(h for h in d.glob("*.html") if h.name != "index-print.html")
        if not slides:
            ip = d / "index-print.html"
            slides = [ip] if ip.exists() else []
        pdf = Path(out).resolve() if out else (d / f"{d.name}.pdf").resolve()
        return [{"pdf": str(pdf), "pages": [str(s.resolve()) for s in slides]}]

    htmls: list[Path] = []
    for p in paths:
        pp = Path(p)
        htmls.extend(sorted(pp.glob("*.html")) if pp.is_dir() else [pp])
    htmls = [h.resolve() for h in htmls]  # file:// needs an absolute path
    if out:  # one multi-page PDF
        return [{"pdf": str(Path(out).resolve()), "pages": [str(h) for h in htmls]}]
    return [{"pdf": str(h.with_suffix(".pdf")), "pages": [str(h)]} for h in htmls]


def build_node_script(work_dir: Path) -> Path:
    sp = work_dir / ".build_pdf.cjs"
    sp.write_text(NODE_TEMPLATE)
    return sp


def _puppeteer_work_dir() -> Path:
    for cand in (ROOT, ROOT / "ppt-output" / "e2e-test"):
        if (cand / "node_modules" / "puppeteer").exists():
            return cand
    print("Installing puppeteer in project root (one-time, the sanctioned renderer)...")
    subprocess.run(["npm", "install", "puppeteer"], capture_output=True, text=True,
                   timeout=300, cwd=str(ROOT))
    return ROOT


def _pngs_to_pdf(pngs: list[Path], pdf: Path, scale: int) -> None:
    from PIL import Image
    frames = [Image.open(p).convert("RGB") for p in pngs]
    if not frames:
        return
    # resolution = 96*scale dpi → physical page = css_px/96 inches (a 1280x720
    # mock → 13.33x7.5in landscape), independent of deviceScaleFactor crispness.
    pdf.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(str(pdf), "PDF", resolution=96.0 * scale, save_all=True,
                   append_images=frames[1:])


def render(documents: list[dict], width: int, height: int, scale: int) -> int:
    work_dir = _puppeteer_work_dir()
    script_path = build_node_script(work_dir)
    tmp = Path(tempfile.mkdtemp(prefix="build_pdf_"))
    try:
        pages, i = [], 0
        for doc in documents:
            doc["_pngs"] = []
            for html in doc["pages"]:
                png = tmp / f"p{i}.png"; i += 1
                pages.append({"html": html, "png": str(png)})
                doc["_pngs"].append(png)
        if not pages:
            print("no HTML pages to render", file=sys.stderr)
            return 1
        cfg = {"pages": pages, "width": width, "height": height, "scale": scale}
        r = subprocess.run(["node", str(script_path), json.dumps(cfg)],
                           cwd=str(work_dir), timeout=600)
        if r.returncode != 0:
            return r.returncode
        for doc in documents:
            shot = [p for p in doc["_pngs"] if p.exists()]
            if shot:
                _pngs_to_pdf(shot, Path(doc["pdf"]), scale)
                print(f"PDF: {doc['pdf']} ({len(shot)} page(s))")
        return 0
    finally:
        script_path.unlink(missing_ok=True)
        for f in tmp.glob("*"):
            f.unlink(missing_ok=True)
        tmp.rmdir()


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic pixel-1:1 HTML→PDF (puppeteer screenshot + Pillow).")
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
