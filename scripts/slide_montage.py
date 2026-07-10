#!/usr/bin/env python3
"""slide_montage.py — stitch a deck's rendered slide PNGs into one contact-sheet
image for the human review turn.

Why this exists: agents reach for a local preview *server* to show a deck, which
adds ports/shells and breaks under sandboxed / cloud-synced (OneDrive) mounts. A
single deterministic PNG the agent can open or attach replaces that instinct — no
server, no port, Pillow-only.

Usage:
    python3 scripts/slide_montage.py <deck_dir | png_dir> [-o out.png] [--cols N]

Given a deck dir (contains `png/`), the default output is
`<deck-slug>-contact-sheet.png` inside the deck dir. Given a png dir directly, the
default is `<parent>-contact-sheet.png`. Empty/missing dir -> message + exit 1.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow not installed. It is a declared repo dep: `pip install Pillow`.",
          file=sys.stderr)
    sys.exit(1)

THUMB_W, THUMB_H = 400, 225  # 16:9
GAP = 16
PAD = 32
BG = (16, 16, 20)
BORDER = (48, 56, 72)
LABEL_BG = (0, 0, 0, 170)
LABEL_FG = (220, 230, 240)


def natural_key(path: Path) -> tuple[object, ...]:
    return tuple(int(p) if p.isdigit() else p.lower()
                 for p in re.split(r"(\d+)", path.name))


def collect_slides(png_dir: Path) -> list[Path]:
    """Natural-sorted slide-*.png / slide_*.png in png_dir."""
    found = list(png_dir.glob("slide-*.png")) + list(png_dir.glob("slide_*.png"))
    return sorted(set(found), key=natural_key)


def _thumb(path: Path, w: int, h: int) -> Image.Image:
    """Thumbnail one slide PNG. A truncated / 0-byte / non-image file yields a
    labelled placeholder tile (and a stderr note) rather than crashing the whole
    contact sheet."""
    try:
        img = Image.open(path).convert("RGB")
        img.thumbnail((w * 2, h * 2))
        return img.resize((w, h), Image.LANCZOS)
    except Exception as exc:  # noqa: BLE001 — any decode failure -> placeholder
        print(f"slide_montage: skipping unreadable {path.name}: {exc}", file=sys.stderr)
        placeholder = Image.new("RGB", (w, h), (40, 40, 48))
        ImageDraw.Draw(placeholder).text((8, 8), f"[unreadable]\n{path.name}", fill=(200, 120, 120))
        return placeholder


def build_montage(slides: list[Path], cols: int = 4, thumb_w: int = THUMB_W,
                  thumb_h: int = THUMB_H, gap: int = GAP, pad: int = PAD) -> Image.Image:
    """Tile slides into a cols-wide grid. Deterministic size:
    W = 2*pad + cols*tw + (cols-1)*gap ; H = 2*pad + rows*th + (rows-1)*gap."""
    n = len(slides)
    cols = max(1, min(cols, n))
    rows = (n + cols - 1) // cols
    width = pad * 2 + cols * thumb_w + (cols - 1) * gap
    height = pad * 2 + rows * thumb_h + (rows - 1) * gap
    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)

    for i, path in enumerate(slides):
        row, col = divmod(i, cols)
        x = pad + col * (thumb_w + gap)
        y = pad + row * (thumb_h + gap)
        canvas.paste(_thumb(path, thumb_w, thumb_h), (x, y))
        draw.rectangle([(x, y), (x + thumb_w - 1, y + thumb_h - 1)], outline=BORDER, width=1)
        overlay = Image.new("RGBA", (thumb_w, 22), LABEL_BG)
        canvas.paste(overlay, (x, y), overlay)
        draw.text((x + 8, y + 5), path.stem, fill=LABEL_FG)
    return canvas


def resolve_png_dir(target: Path) -> tuple[Path, str]:
    """Return (png_dir, deck_slug). Accept a deck dir (has png/) or a png dir."""
    if (target / "png").is_dir():
        return target / "png", target.name
    if target.name == "png":
        return target, target.parent.name
    return target, target.name


def main() -> int:
    ap = argparse.ArgumentParser(description="Stitch slide PNGs into a contact sheet.")
    ap.add_argument("target", help="deck dir (containing png/) or a png dir")
    ap.add_argument("-o", "--output", help="output PNG path")
    ap.add_argument("--cols", type=int, default=4, help="columns in the grid (default 4)")
    args = ap.parse_args()

    target = Path(args.target).expanduser().resolve()
    if not target.is_dir():
        print(f"not a directory: {target}", file=sys.stderr)
        return 1

    png_dir, slug = resolve_png_dir(target)
    if not png_dir.is_dir():
        print(f"no png/ directory under {target}", file=sys.stderr)
        return 1

    slides = collect_slides(png_dir)
    if not slides:
        print(f"no slide-*.png in {png_dir} — render slides first (Step 5c).", file=sys.stderr)
        return 1

    out = Path(args.output).expanduser().resolve() if args.output else \
        (target if target.name != "png" else target.parent) / f"{slug}-contact-sheet.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    build_montage(slides, cols=args.cols).save(out)
    print(f"contact sheet: {len(slides)} slides -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
