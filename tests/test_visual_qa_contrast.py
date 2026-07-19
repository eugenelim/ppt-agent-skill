#!/usr/bin/env python3
"""test_visual_qa_contrast.py — self-tests for the WCAG text-contrast gate.

Covers the deck-level CONTRAST-01/02 checks in visual_qa.py: the WCAG relative-
luminance / contrast-ratio math, alpha compositing of semi-transparent text,
check_text_contrast verdicts, and load_style_palette parsing the 12-var
css_variables contract. Pure colour math — no browser, no external dependency.
No pytest harness in this repo; run directly or via smoke_test.py.
Exit 0 = all pass, 1 = a failure.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import visual_qa as V  # noqa: E402


if __name__ == "__main__":
    FAILS: list[str] = []


    def check(name: str, cond: bool):
        if cond:
            print(f"  [OK] {name}")
        else:
            print(f"  [XX] {name}")
            FAILS.append(name)


    def approx(a: float, b: float, tol: float = 0.05) -> bool:
        return abs(a - b) <= tol


    # ─────────────── WCAG math ───────────────
    check("black on white = 21:1", approx(V._contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0))
    check("white on white = 1:1", approx(V._contrast_ratio((255, 255, 255), (255, 255, 255)), 1.0))
    # #767676 on white is the canonical 4.5:1 boundary colour
    check("#767676 on white ≈ 4.5:1", approx(V._contrast_ratio((118, 118, 118), (255, 255, 255)), 4.54))
    check("ratio is symmetric", approx(
        V._contrast_ratio((30, 30, 40), (240, 240, 240)),
        V._contrast_ratio((240, 240, 240), (30, 30, 40)),
    ))

    # ─────────────── alpha compositing ───────────────
    opaque = V._composite_over((255, 255, 255, 1.0), (17, 17, 24))
    check("alpha=1 is identity", opaque == (255, 255, 255))
    mixed = V._composite_over((255, 255, 255, 0.7), (17, 17, 24))
    check("rgba(...,0.7) over dark lightens toward fg", mixed == (184, 184, 186))
    # secondary text judged on its composited colour, not its nominal colour
    check("compositing changes the ratio", not approx(
        V._contrast_ratio((255, 255, 255), (17, 17, 24)),
        V._contrast_ratio(mixed, (17, 17, 24)),
    ))

    # ─────────────── check_text_contrast verdicts ───────────────
    GOOD = {
        "texts": {"text_primary": (236, 236, 242, 1.0), "text_secondary": (154, 155, 168, 1.0)},
        "surfaces": {"bg_primary": (17, 17, 24), "bg_secondary": (22, 22, 31),
                     "card_bg_from": (28, 29, 40), "card_bg_to": (33, 34, 47)},
    }
    good = {r["id"]: r for r in V.check_text_contrast(GOOD)}
    check("good deck: primary PASS", good["CONTRAST-01"]["status"] == "PASS")
    check("good deck: secondary PASS", good["CONTRAST-02"]["status"] == "PASS")

    # light-grey text on near-white everywhere → unreadable on every surface
    BAD = {
        "texts": {"text_primary": (200, 200, 200, 1.0), "text_secondary": (220, 220, 220, 1.0)},
        "surfaces": {"bg_primary": (255, 255, 255), "bg_secondary": (248, 250, 252),
                     "card_bg_from": (255, 255, 255), "card_bg_to": (248, 248, 248)},
    }
    bad = {r["id"]: r for r in V.check_text_contrast(BAD)}
    check("broken deck: primary FAIL (no readable surface)", bad["CONTRAST-01"]["status"] == "FAIL")
    check("broken deck: secondary WARN (never FAIL)", bad["CONTRAST-02"]["status"] == "WARN")

    # large-text-only band: primary readable ≥3:1 but <4.5:1 on best surface → WARN, not FAIL
    LARGE_ONLY = {
        "texts": {"text_primary": (130, 130, 130, 1.0)},
        "surfaces": {"bg_primary": (255, 255, 255), "bg_secondary": (255, 255, 255),
                     "card_bg_from": (255, 255, 255), "card_bg_to": (255, 255, 255)},
    }
    lo = {r["id"]: r for r in V.check_text_contrast(LARGE_ONLY)}
    check("large-only band: primary WARN (3–4.5:1)", lo["CONTRAST-01"]["status"] == "WARN")

    # ─────────────── load_style_palette ───────────────
    with tempfile.TemporaryDirectory() as d:
        sp = Path(d) / "style.json"
        sp.write_text(json.dumps({"css_variables": {
            "bg_primary": "#111118", "bg_secondary": "#16161f",
            "card_bg_from": "#1c1d28", "card_bg_to": "#21222f",
            "card_border": "#2C2D3A", "card_radius": "14px",
            "text_primary": "#ECECF2", "text_secondary": "rgba(255,255,255,0.7)",
            "accent_1": "#D4A96E", "accent_2": "#B98E4E",
            "accent_3": "#6DBEA3", "accent_4": "#7BB4CC",
        }}), encoding="utf-8")
        pal = V.load_style_palette(sp)
        check("palette loads from 12-var contract", pal is not None)
        check("parses both text roles", set(pal["texts"]) == {"text_primary", "text_secondary"})
        check("parses all four surfaces", set(pal["surfaces"]) ==
              {"bg_primary", "bg_secondary", "card_bg_from", "card_bg_to"})
        check("secondary text keeps its alpha", approx(pal["texts"]["text_secondary"][3], 0.7))
        check("missing style path → None", V.load_style_palette(None) is None)

    if FAILS:
        print(f"\ntest_visual_qa_contrast: {len(FAILS)} FAILED")
        sys.exit(1)
    print("\ntest_visual_qa_contrast: all passed")
