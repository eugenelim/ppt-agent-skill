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

    # --- build_notes_stub ---
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        (d / "slide-1.html").write_text(
            "<html><head><title>Roadmap Overview</title></head><body></body></html>"
        )
        (d / "slide-2.html").write_text(
            "<html><body><h1>Key Findings</h1></body></html>"
        )
        stubs_slides = [str(s) for s in H.collect_slides(d)]
        stub = H.build_notes_stub(stubs_slides)
        check(stub["schema_version"] == "1", "build_notes_stub: schema_version=1")
        check("_comment" in stub, "build_notes_stub: _comment present")
        check(len(stub["slides"]) == 2, "build_notes_stub: 2 slide entries")
        check(stub["slides"][0]["slide_number"] == 1, "build_notes_stub: slide_number=1")
        check(stub["slides"][0]["title"] == "Roadmap Overview", "build_notes_stub: title from <title>")
        check(stub["slides"][0]["notes"] == "", "build_notes_stub: empty notes string")
        check(stub["slides"][1]["title"] == "Key Findings", "build_notes_stub: title from <h1>")
        check(
            stub["_comment"] == "Fill in facilitation notes here; pass --notes to html_packager.py to embed them.",
            "build_notes_stub: _comment literal matches",
        )

    # --- build_preview with notes ---
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        (d / "slide-1.html").write_text(
            "<html><head><title>Intro</title></head><body></body></html>"
        )
        (d / "slide-2.html").write_text("<html><body></body></html>")
        notes_slides = [str(s) for s in H.collect_slides(d)]

        notes_data = [
            {"slide_number": 1, "notes": "Welcome everyone."},
            {"slide_number": 2, "notes": ""},
        ]
        html_with = H.build_preview(notes_slides, title="T", notes=notes_data)
        html_without = H.build_preview(notes_slides, title="T")

        check(
            'data-notes="Welcome everyone."' in html_with,
            "build_preview notes: data-notes injected for slide with notes",
        )
        check(
            "data-notes=" not in html_without,
            "build_preview no notes: data-notes absent when notes=None",
        )
        check("id=\"notesPanel\"" in html_with, "build_preview notes: notesPanel element present")
        check(
            html_with.index('id="stage"') < html_with.index('id="notesPanel"'),
            "build_preview notes: notesPanel after stage open tag",
        )
        check(
            html_with.index('id="notesPanel"') < html_with.index('</div>\n<div class="controls"'),
            "build_preview notes: notesPanel inside stage (before stage close + controls)",
        )
        check("id=\"notesBtn\"" in html_with, "build_preview notes: Notes button present")
        check(
            "=== 'n'" in html_with or '=== "n"' in html_with,
            "build_preview notes: N key binding present",
        )

        # HTML-escaping test (XSS defense on data-notes attribute)
        special_notes = [{"slide_number": 1, "notes": 'line1\n<b>"&x"</b>'}]
        html_special = H.build_preview(notes_slides[:1], title="T", notes=special_notes)
        check("&lt;b&gt;" in html_special, "build_preview notes: < is HTML-escaped in data-notes")
        check("&quot;" in html_special, "build_preview notes: \" is HTML-escaped in data-notes")
        check("&amp;" in html_special, "build_preview notes: & is HTML-escaped in data-notes")
        check("<b>" not in html_special, "build_preview notes: raw <b> absent from output")

        # Defensive: non-dict entry and null slide_number must not crash
        bad_notes = [None, {"slide_number": None, "notes": "x"}, {"slide_number": 1, "notes": "Safe."}]
        html_bad = H.build_preview(notes_slides[:1], title="T", notes=bad_notes)
        check("data-notes=\"Safe.\"" in html_bad, "build_preview notes: defensively skips bad entries")

        # AC8: sandbox still preserved when notes are used
        check('sandbox=""' in html_with, "build_preview notes: sandbox preserved")
        check("allow-same-origin" not in html_with, "build_preview notes: allow-same-origin absent")

    if FAILS:
        print(f"✗ test_html_packager: {len(FAILS)} failure(s)")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)
    print("✓ test_html_packager: all checks pass")
    sys.exit(0)
