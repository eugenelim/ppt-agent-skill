#!/usr/bin/env python3
"""test_slide_montage.py — slide_montage.py builds a deterministic contact sheet.

No pytest harness in this repo; run directly or via smoke_test.py.
Exit 0 = all pass, 1 = a failure.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


if __name__ == "__main__":
    try:
        from PIL import Image
    except ImportError:
        print("Pillow not installed. Run: pip install Pillow", file=sys.stderr)
        sys.exit(1)

    import slide_montage as M  # noqa: E402

    FAILS: list[str] = []


    def check(name: str, cond: bool) -> None:
        print(f"  [{'OK' if cond else 'XX'}] {name}")
        if not cond:
            FAILS.append(name)


    def make_png(path: Path, color=(120, 130, 140)) -> None:
        Image.new("RGB", (1280, 720), color).save(path)


    def main() -> int:
        with tempfile.TemporaryDirectory() as td:
            png_dir = Path(td) / "png"
            png_dir.mkdir()
            # 5 slides, out of order + a 2-vs-10 natural-sort trap.
            for n in (1, 2, 3, 10, 11):
                make_png(png_dir / f"slide-{n}.png")

            # 1. natural sort: slide-2 before slide-10.
            ordered = [p.name for p in M.collect_slides(png_dir)]
            check(f"natural sort (got {ordered})",
                  ordered == ["slide-1.png", "slide-2.png", "slide-3.png", "slide-10.png", "slide-11.png"])

            # 2. montage dimensions match the grid formula.
            cols, tw, th, gap, pad = 3, 200, 112, 12, 24
            img = M.build_montage(M.collect_slides(png_dir), cols=cols,
                                  thumb_w=tw, thumb_h=th, gap=gap, pad=pad)
            n = 5
            rows = (n + cols - 1) // cols
            exp_w = pad * 2 + cols * tw + (cols - 1) * gap
            exp_h = pad * 2 + rows * th + (rows - 1) * gap
            check(f"montage size {img.size} == expected ({exp_w}, {exp_h})",
                  img.size == (exp_w, exp_h))

            # 3. CLI writes one PNG for a deck dir and exits 0.
            deck = Path(td) / "my-deck"
            (deck / "png").mkdir(parents=True)
            for n in (1, 2):
                make_png(deck / "png" / f"slide-{n}.png")
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "slide_montage.py"), str(deck)],
                               capture_output=True, text=True)
            out = deck / "my-deck-contact-sheet.png"
            check(f"CLI on deck dir exits 0 (rc={r.returncode}); stderr={r.stderr[:120]}", r.returncode == 0)
            check("CLI wrote <deck-slug>-contact-sheet.png", out.exists() and out.stat().st_size > 0)

            # 4. empty/missing png dir -> non-zero exit, no output.
            empty = Path(td) / "empty"
            empty.mkdir()
            r2 = subprocess.run([sys.executable, str(ROOT / "scripts" / "slide_montage.py"), str(empty)],
                                capture_output=True, text=True)
            check(f"empty dir -> non-zero exit (rc={r2.returncode})", r2.returncode != 0)

        if FAILS:
            print(f"\nFAILED: {len(FAILS)} check(s): {FAILS}")
            return 1
        print("\nAll slide_montage checks passed.")
        return 0


    if __name__ == "__main__":
        sys.exit(main())
