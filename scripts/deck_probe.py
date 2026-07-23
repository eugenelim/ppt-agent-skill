#!/usr/bin/env python3
"""deck_probe.py — deterministic *reusable-form* probe for the assimilate-slides
skill's INGEST step.

Why this exists: without a fixed tool, an agent assimilating a deck improvises a
parser and `pip install`s whatever it guesses (pymupdf, pdf2image, cairosvg,
unoconv, …) — non-deterministic and against the repo's no-new-dependency rule.
This script does the extraction with **only already-present deps**
(`python-pptx`, `lxml`, stdlib) and, for formats no bundled lib handles
(PDF / images / SVG), prints guidance to use the harness's own file viewer
rather than installing anything.

It reports *style/structure*, not content: palette, fonts, per-slide shape
composition, dense-diagram slides, and image-heavy discard candidates. Short
text labels are printed only behind `--labels` (for icon-concept spotting).

Usage:
    python3 scripts/deck_probe.py <file|dir> [--labels]

Output goes to stdout — redirect into the gitignored `.context/` scratch; never
commit it. No network, no install, no writes.
"""
from __future__ import annotations

import collections
import re
import shutil
import subprocess
import sys
from pathlib import Path

SUPPORTED_PPTX = {".pptx"}
SUPPORTED_WEB = {".html", ".htm", ".css"}
VISUAL = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"}


def probe_pptx(path: Path, show_labels: bool) -> None:
    try:
        from pptx import Presentation
        from pptx.util import Emu
    except ImportError:
        print("python-pptx not installed. It is a declared repo dep: "
              "`pip install python-pptx lxml`. Do NOT substitute another library.",
              file=sys.stderr)
        raise SystemExit(2)

    prs = Presentation(str(path))
    W, H = prs.slide_width, prs.slide_height
    print(f"SOURCE type=pptx slides={len(prs.slides)} "
          f"size={Emu(W).inches:.2f}x{Emu(H).inches:.2f}in")  # type: ignore[arg-type]

    fonts: collections.Counter = collections.Counter()
    fill_colors: collections.Counter = collections.Counter()
    font_colors: collections.Counter = collections.Counter()
    dense, discard = [], []

    for i, slide in enumerate(prs.slides, 1):
        n_pic = n_txt = n_tbl = n_grp = 0
        pic_area = chars = 0
        auto = free = line = 0
        for shp in slide.shapes:
            st = str(shp.shape_type or "")
            if "PICTURE" in st:
                n_pic += 1
                try:
                    pic_area += (shp.width or 0) * (shp.height or 0)
                except Exception:
                    pass
            if "AUTO_SHAPE" in st:
                auto += 1
            if "FREEFORM" in st:
                free += 1
            if st.startswith("LINE") or "CONNECTOR" in st:
                line += 1
            if "GROUP" in st:
                n_grp += 1
            if getattr(shp, "has_table", False) and shp.has_table:
                n_tbl += 1
            if shp.has_text_frame:
                n_txt += 1
                chars += len(shp.text_frame.text)
                for p in shp.text_frame.paragraphs:
                    for r in p.runs:
                        if r.font.name:
                            fonts[r.font.name] += 1
                        try:
                            c = r.font.color
                            if c and c.type is not None and c.rgb is not None:
                                font_colors[str(c.rgb)] += 1
                        except Exception:
                            pass
            try:
                f = shp.fill
                if f.type is not None and "SOLID" in str(f.type) and f.fore_color and f.fore_color.rgb:
                    fill_colors[str(f.fore_color.rgb)] += 1
            except Exception:
                pass
        frac = (pic_area / (W * H)) if (W and H) else 0
        diagram_shapes = auto + free + line
        flags = []
        if frac > 0.55 and chars < 120:
            flags.append("IMG_HEAVY→discard")
            discard.append(i)
        if diagram_shapes >= 20:
            flags.append("DENSE_DIAGRAM")
            dense.append(i)
        print(f"S{i:02d} layout={slide.slide_layout.name!r} pic={n_pic}({frac:.0%}) "
              f"txt={n_txt} chars={chars} tbl={n_tbl} grp={n_grp} "
              f"auto/free/line={auto}/{free}/{line} {' '.join(flags)}")

    print("\nTOP_FONTS", fonts.most_common(10))
    print("FOCUS/FONT_COLORS", font_colors.most_common(12))
    print("FILL_COLORS", fill_colors.most_common(12))
    print("DENSE_DIAGRAM_SLIDES (architecture-canvas candidates):", dense)
    print("DISCARD_CANDIDATES (image-only headers/dividers):", discard)

    if show_labels:
        seen = []
        for slide in prs.slides:
            for shp in slide.shapes:
                if shp.has_text_frame:
                    t = shp.text_frame.text.strip().replace("\n", " ")
                    if 0 < len(t) <= 40 and t not in seen:
                        seen.append(t)
        print("\nSHORT_LABELS (for icon-concept spotting — scrub before any commit):")
        print(" | ".join(seen[:60]))


def probe_pdf(path: Path, show_labels: bool) -> None:
    """Ingest a source PDF *install-free*: use poppler's pdftotext/pdfinfo when
    already present; otherwise route to the harness viewer. Never installs a
    renderer/parser (no pymupdf/pdf2image/poppler-via-pip)."""
    print(f"SOURCE type=pdf file={path.name}")
    info = shutil.which("pdfinfo")
    totext = shutil.which("pdftotext")
    if info:
        try:
            out = subprocess.run([info, str(path)], capture_output=True, text=True, timeout=30).stdout
            pages = next((l.split(":", 1)[1].strip() for l in out.splitlines() if l.startswith("Pages")), "?")
            print(f"pages={pages} (via poppler pdfinfo)")
        except Exception:
            pass
    if totext:
        try:
            txt = subprocess.run([totext, "-layout", str(path), "-"], capture_output=True,
                                 text=True, timeout=60).stdout
            print(f"text_chars={len(txt)} (via poppler pdftotext)")
            if show_labels:
                labels = [t.strip() for t in txt.splitlines() if 0 < len(t.strip()) <= 40]
                uniq = list(dict.fromkeys(labels))
                print("\nSHORT_LABELS (icon-concept spotting — scrub before any commit):")
                print(" | ".join(uniq[:60]))
        except Exception:
            pass
    else:
        print("poppler not installed — read this PDF with the harness's own file viewer "
              "(it renders PDF pages); do NOT `pip install` pymupdf/pdf2image/weasyprint or "
              "`apt install poppler`. Extract palette/layout/icon-ideas by eye.")


def probe_web(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    print(f"SOURCE type=web/{path.suffix.lstrip('.')} bytes={len(text)}")
    root_vars = re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", text)
    fonts = re.findall(r"font-family\s*:\s*([^;{}]+)[;}]", text, re.I)
    hexes = collections.Counter(re.findall(r"#[0-9a-fA-F]{3,8}\b", text))
    print("\nCSS_ROOT_VARS:")
    for k, v in root_vars[:40]:
        print(f"  {k}: {v.strip()[:60]}")
    print("\nFONT_STACKS:")
    for f in dict.fromkeys(s.strip()[:70] for s in fonts):
        print(f"  {f}")
    print("\nTOP_HEX_COLORS", hexes.most_common(15))


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_labels = "--labels" in sys.argv
    if not args:
        print(__doc__)
        return 2
    target = Path(args[0]).expanduser()
    if not target.exists():
        print(f"not found: {target}", file=sys.stderr)
        return 1

    paths = sorted(target.rglob("*")) if target.is_dir() else [target]
    handled = False
    for p in paths:
        if p.is_dir():
            continue
        ext = p.suffix.lower()
        if ext in SUPPORTED_PPTX:
            print("=" * 72)
            probe_pptx(p, show_labels)
            handled = True
        elif ext in SUPPORTED_WEB:
            print("=" * 72)
            probe_web(p)
            handled = True
        elif ext in VISUAL:
            print("=" * 72)
            print(f"SOURCE type={ext.lstrip('.')} — visual/binary. Read it with the "
                  f"harness's own file viewer (it renders PDFs/images); do NOT install "
                  f"a renderer or SVG/PDF parser. Extract palette/layout/icon-ideas by eye.")
            handled = True
    if not handled:
        print("no supported files found (looked for: .pptx, .html/.css; "
              ".pdf/.png/.jpg/.svg are read by the harness viewer, not this script).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
