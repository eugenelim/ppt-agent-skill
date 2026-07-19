#!/usr/bin/env python3
"""test_build_pdf.py — build_pdf.py resolves inputs deterministically, renders
via a Puppeteer *screenshot* (guaranteed 1:1 with the HTML), and assembles the
PDF with Pillow — never WeasyPrint / img2pdf / a `page.pdf()` print export.

No pytest harness; run directly or via smoke_test.py. Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_pdf as B  # noqa: E402


if __name__ == "__main__":
    FAILS: list[str] = []


    def check(cond: bool, msg: str) -> None:
        if not cond:
            FAILS.append(msg)


    # --- resolve_documents (pure) ---
    d = B.resolve_documents(["a.html"], None, None)
    check(len(d) == 1 and Path(d[0]["pdf"]).name == "a.pdf", "single html → a.pdf")
    check(Path(d[0]["pdf"]).is_absolute() and Path(d[0]["pages"][0]).is_absolute(),
          "paths resolved absolute (file:// needs it)")

    d = B.resolve_documents(["a.html", "b.html"], "deck.pdf", None)
    check(len(d) == 1 and len(d[0]["pages"]) == 2 and Path(d[0]["pdf"]).name == "deck.pdf",
          "--out → one multi-page PDF over all inputs")

    d = B.resolve_documents(["a.html", "b.html"], None, None)
    check(len(d) == 2, "no --out → one PDF per input")

    with tempfile.TemporaryDirectory() as t:
        dd = Path(t) / "my-topic"
        dd.mkdir()
        for n in ("01.html", "02.html", "index-print.html", "my-topic-preview.html"):
            (dd / n).write_text("<html></html>")
        d = B.resolve_documents([], None, str(dd))
        check(len(d) == 1, "--deck → single document")
        names = [Path(p).name for p in d[0]["pages"]]
        check(names == ["01.html", "02.html"],
              "--deck orders slides and EXCLUDES index-print.html + *preview.html")
        check(Path(d[0]["pdf"]).name == "my-topic.pdf",
              "--deck without --out → <deck-slug>.pdf (topic-named)")

    # --- --deck collates slides by page NUMBER, not lexicographically ---
    # Real slide files are un-padded (cli-cheatsheet: slides/slide-1.html); the
    # old zero-padded fixture masked the mis-sort where slide-10..19 preceded slide-2.
    with tempfile.TemporaryDirectory() as t:
        dd = Path(t) / "big-deck"
        dd.mkdir()
        for n in range(1, 13):
            (dd / f"slide-{n}.html").write_text("<html></html>")
        d = B.resolve_documents([], None, str(dd))
        names = [Path(p).name for p in d[0]["pages"]]
        check(names == [f"slide-{n}.html" for n in range(1, 13)],
              f"--deck orders slide-1..12 by page number (got {names[:4]}…)")

    # --- node script: screenshot path, not print/page.pdf, no banned tools ---
    with tempfile.TemporaryDirectory() as t:
        js = B.build_node_script(Path(t)).read_text()
        check("screenshot(" in js and "clip:" in js, "renders via clipped screenshot (1:1 viewport)")
        check("page.pdf(" not in js, "does NOT use page.pdf() print export")
        check("deviceScaleFactor" in js, "sets deviceScaleFactor for crispness")
        for banned in ("weasy", "img2pdf", "pdf2svg", "toDataURL"):
            check(banned.lower() not in js.lower(), f"node script must NOT use {banned}")

    # --- Pillow PNG→PDF assembly (real, browserless) ---
    try:
        from PIL import Image
        with tempfile.TemporaryDirectory() as t:
            pngs = []
            for i, color in enumerate([(255, 0, 0), (0, 128, 255)]):
                p = Path(t) / f"s{i}.png"
                Image.new("RGB", (1280, 720), color).save(p)
                pngs.append(p)
            out = Path(t) / "out.pdf"
            B._pngs_to_pdf(pngs, out, scale=2)
            data = out.read_bytes()
            check(data[:4] == b"%PDF", "assembled a valid PDF (%PDF header)")
            # Pillow writes "/Type /Page" (with space); \b after Page excludes "/Pages"
            n_pages = len(re.findall(rb"/Type\s*/Page\b", data))
            check(n_pages == 2, f"multi-page PDF has one page per screenshot (got {n_pages})")
            # each embedded frame is the exact viewport*scale raster → 1:1 with the HTML
            dims = list(zip(re.findall(rb"/Width\s+(\d+)", data), re.findall(rb"/Height\s+(\d+)", data)))
            check((b"1280", b"720") in dims, "embedded frame is the exact page-box raster (1:1)")
    except ImportError:
        FAILS.append("Pillow not importable — it is a present dep (build_hero uses it)")

    if FAILS:
        print(f"✗ test_build_pdf: {len(FAILS)} failure(s)")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)
    print("✓ test_build_pdf: all checks pass")
    sys.exit(0)
