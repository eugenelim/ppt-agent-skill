#!/usr/bin/env python3
"""test_html_packager.py — tests for the HTML preview assembler.

No pytest harness; run directly or via smoke_test.py. Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import html_packager as H  # noqa: E402


if __name__ == "__main__":
    FAILS: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            FAILS.append(msg)

    # --- collect_slides orders by page number (the real, un-padded naming) ---
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        # 19 pages is enough to expose the lexicographic mis-sort at the 10/2 boundary.
        for n in range(1, 20):
            (d / f"slide-{n}.html").write_text("<html></html>")

        ordered = [p.name for p in H.collect_slides(d)]
        expected = [f"slide-{n}.html" for n in range(1, 20)]
        check(ordered == expected,
              f"collect_slides orders by page number 1..19 (got {ordered[:4]}…)")
        check(ordered.index("slide-2.html") < ordered.index("slide-11.html"),
              "slide-2 precedes slide-11 (not the other way round)")

    # --- _slide_title derives a display title from slide HTML ---
    check(
        H._slide_title('<html><head><title>Roadmap Overview</title></head></html>', 1) == "Roadmap Overview",
        "_slide_title: derives from <title>",
    )
    check(
        H._slide_title('<html><body><h1>Big Heading</h1></body></html>', 2) == "Big Heading",
        "_slide_title: falls back to <h1>",
    )
    check(
        H._slide_title('<html><body></body></html>', 3) == "Slide 3",
        "_slide_title: falls back to 'Slide N' when neither present",
    )
    # "Cover" is in _PLACEHOLDER_TITLES → _clean_title returns "" → fallback to "Slide N"
    check(
        H._slide_title('<html><head><title>Slide 5 - Cover</title></head></html>', 5) == "Slide 5",
        "_slide_title: placeholder title ('Cover') falls back to 'Slide N'",
    )
    # Non-placeholder stripped title survives
    check(
        H._slide_title('<html><head><title>Slide 3 - Roadmap Overview</title></head></html>', 3) == "Roadmap Overview",
        "_slide_title: non-placeholder stripped title survives",
    )

    # --- build_preview structural assertions ---
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        (d / "slide-1.html").write_text(
            "<html><head><title>Roadmap Overview</title></head><body></body></html>"
        )
        (d / "slide-2.html").write_text(
            "<html><body><h1>Key Findings</h1></body></html>"
        )
        (d / "slide-3.html").write_text("<html><body></body></html>")
        slides = [str(s) for s in H.collect_slides(d)]
        html = H.build_preview(slides, title="Test Deck")

        # AC1: controls appear after stage in HTML (bottom nav)
        check('class="controls"' in html, "controls element present in HTML")
        check(
            html.index('id="stage"') < html.index('class="controls"'),
            "controls element appears after stage (bottom nav)",
        )

        # AC2: progress bar present
        check('progress' in html.lower(), "progress bar element present")

        # AC4: per-slide titles injected as data attributes
        check('data-slide-title' in html, "data-slide-title attribute present on iframes")
        check('Roadmap Overview' in html, "slide title from <title> present in output")
        check('Key Findings' in html, "slide title from <h1> present in output")

        # AC5: extended keyboard shortcuts present (smoke checks — behavior verified by QA)
        check("'Home'" in html or '"Home"' in html, "Home key binding in JS")
        check("'End'" in html or '"End"' in html, "End key binding in JS")
        check("=== 'g'" in html or '=== "g"' in html, "G key for jump modal in JS")
        check("=== 'b'" in html or '=== "b"' in html, "B key for blank in JS")

        # AC1: absence invariants — old fixed-top toolbar must not exist
        check('margin-top: 60px' not in html, "old margin-top: 60px absent (controls are bottom-aligned)")
        check('.toolbar' not in html, "old .toolbar class absent from output")

        # AC6: iframe sandbox security invariant
        check('sandbox=""' in html, "sandbox=\"\" attribute preserved on iframes")
        check('allow-same-origin' not in html, "allow-same-origin absent from output")

        # AC7: lang attribute
        check('lang="en"' in html, "html[lang=en] present")
        check('lang="zh-CN"' not in html, "lang=zh-CN removed")

    # AC10: empty-list graceful no-op
    empty_html = H.build_preview([], title="Empty")
    check(empty_html.startswith('<!DOCTYPE'), "build_preview([]) returns valid HTML")

    if FAILS:
        print(f"✗ test_html_packager: {len(FAILS)} failure(s)")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)
    print("✓ test_html_packager: all checks pass")
    sys.exit(0)
