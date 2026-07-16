#!/usr/bin/env python3
"""test_diagram_qa.py — self-tests for the diagram-consistency-system checks.

Covers scripts/lint_diagram_recipes.py and the new visual_qa.py checks with
crafted fixtures (no pytest harness in this repo; run directly or via
smoke_test.py). Exit 0 = all pass, 1 = a failure.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import lint_diagram_recipes as L  # noqa: E402
import visual_qa as V  # noqa: E402
from PIL import Image  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool):
    if cond:
        print(f"  [OK] {name}")
    else:
        print(f"  [XX] {name}")
        FAILS.append(name)


# ─────────────── lint tests ───────────────
GOOD_RECIPE = """# fam

### 流程图 (flowchart)
**何时用**：步骤逻辑。
**数据格式**：
```json
{"diagram_type":"flowchart"}
```
**模板**：
```html
<div style="background:var(--node-bg-from); color:var(--node-fg);">A</div>
<svg style="overflow:visible;"><polygon points="0,0 10,5 0,10" fill="var(--edge)"/></svg>
```
**自检**：颜色用变量。
**管线安全**：无 SVG `<text>`；箭头 `<polygon>`。
"""


def lint_findings(text: str) -> list[str]:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "diagram-fam.md"
        p.write_text(text, encoding="utf-8")
        return L.lint_file(p)


def test_lint():
    print("lint:")
    check("clean recipe → no findings", lint_findings(GOOD_RECIPE) == [])
    check("missing 管线安全 marker → finding",
          any("管线安全" in f for f in lint_findings(GOOD_RECIPE.replace("**管线安全**：无 SVG `<text>`；箭头 `<polygon>`。", ""))))
    bad_text = GOOD_RECIPE.replace('<div style="background:var(--node-bg-from)', '<svg><text>x</text></svg>\n<div style="background:var(--node-bg-from)')
    check("SVG <text> in code → finding", any("<text>" in f for f in lint_findings(bad_text)))
    bad_color = GOOD_RECIPE.replace("var(--node-fg)", "#abcdef")
    check("hardcoded hex in code → finding", any("#abcdef" in f for f in lint_findings(bad_color)))
    # comment mentioning <text> must NOT trip
    commented = GOOD_RECIPE.replace('<div style="background', '<!-- 无 <text> -->\n<div style="background')
    check("comment '<text>' → no false positive", lint_findings(commented) == [])
    # trend colors allowed
    trend = GOOD_RECIPE.replace("var(--edge)", "#22c55e")
    check("trend color #22c55e allowed", lint_findings(trend) == [])


# ─────────────── visual_qa per-page tests ───────────────
def test_visual_qa_html():
    print("visual_qa (html checks):")
    check("HEX-01 flags hardcoded body color",
          V.check_hardcoded_colors("<style>:root{--a:#fff;}</style><div style='color:#abcdef'>")["status"] == "WARN")
    check("HEX-01 passes var-only body",
          V.check_hardcoded_colors("<style>:root{--a:#fff;}</style><div style='color:var(--a)'>")["status"] == "PASS")
    check("HEX-01 ignores trend colors",
          V.check_hardcoded_colors("<div style='color:#22c55e'>")["status"] == "PASS")
    check("TYPE-01 warns on single size",
          V.check_type_scale("<div style='font-size:14px'>a</div>")["status"] == "WARN")
    check("TYPE-01 passes with hierarchy",
          V.check_type_scale("<h1 style='font-size:32px'>a</h1><p style='font-size:14px'>b</p>")["status"] == "PASS")
    radii = "".join(f"<div style='border-radius:{r}px'></div>" for r in (4, 8, 12, 16, 24))
    check("RAD-01 warns on >3 distinct radii", V.check_corner_radius(radii)["status"] == "WARN")
    check("RAD-01 passes on uniform radius",
          V.check_corner_radius("<div style='border-radius:8px'></div>")["status"] == "PASS")
    offgrid = "".join(f"<div style='gap:{g}px'></div>" for g in (6, 10, 14, 8))
    check("ALIGN-01 warns on off-4px-grid spacing", V.check_alignment_rhythm(offgrid)["status"] == "WARN")
    check("parse_root_palette extracts hex",
          set(V.parse_root_palette("<style>:root{--bg:#101820;--ac:#ff6600;}</style>")) ==
          {(16, 24, 32), (255, 102, 0)})


def test_visual_qa_palette():
    print("visual_qa (palette/image):")
    pal = [(20, 30, 40), (240, 100, 20)]
    on = Image.new("RGB", (96, 54), (240, 100, 20))
    check("PAL-01 passes on-palette image", V.check_palette_adherence(on, pal)["status"] == "PASS")
    off = Image.new("RGB", (96, 54), (20, 200, 30))  # far from palette
    check("PAL-01 warns off-palette image", V.check_palette_adherence(off, pal)["status"] == "WARN")
    check("PAL-01 warns when no palette", V.check_palette_adherence(on, [])["status"] == "WARN")


def test_deck():
    print("visual_qa (deck aggregate):")
    base = {"bg": (0, 0, 32), "palette": frozenset({"#101820", "#ff6600"}), "sizes": frozenset({32.0, 14.0})}
    drift = {"name": "slide-3.png", "bg": (240, 240, 240),
             "palette": frozenset({"#ffffff", "#0066cc"}), "sizes": frozenset({40.0, 20.0, 12.0})}
    sigs = [dict(base, name="slide-1.png"), dict(base, name="slide-2.png"), drift]
    res = V.check_deck_consistency(sigs)
    ids = {r["id"]: r["status"] for r in res}
    check("DECK-PAL-01 flags drift", ids.get("DECK-PAL-01") == "WARN")
    check("DECK-BG-01 flags drift", ids.get("DECK-BG-01") == "WARN")
    check("DECK-TYPE-01 flags drift", ids.get("DECK-TYPE-01") == "WARN")
    coherent = [dict(base, name=f"slide-{i}.png") for i in (1, 2, 3)]
    res2 = {r["id"]: r["status"] for r in V.check_deck_consistency(coherent)}
    check("DECK-* pass on coherent deck", all(v == "PASS" for v in res2.values()))
    check("deck check no-op on single slide", V.check_deck_consistency([base]) == [])


def test_exit_contract():
    """AC12: new checks are additive — they contribute only PASS/WARN, never a
    FAIL, so the 0/1/2 exit mapping cannot regress from the new code. (Pre-existing
    checks like SIZE/BLANK may still FAIL a synthetic fixture — that's not a
    regression, so the invariant is scoped to the new check ids.)"""
    print("visual_qa (exit-contract regression):")
    always_new = {"PAL-01", "HEX-01", "TYPE-01", "RAD-01", "ALIGN-01"}
    all_new = always_new | {"DTHEME-01", "DECK-PAL-01", "DECK-BG-01", "DECK-TYPE-01"}
    with tempfile.TemporaryDirectory() as d:
        png = Path(d) / "slide-1.png"
        Image.new("RGB", (1280, 720), (22, 29, 46)).save(png)
        html = Path(d) / "slide-1.html"
        html.write_text(
            "<style>:root{--bg-primary:#0a0e1a;--card-bg-from:#161d2e;--accent-1:#22d3ee;"
            "--text-primary:#e8eef7;--text-secondary:#94a3b8;--card-border:#2a3447;}</style>"
            "<h1 style='font-size:32px;color:var(--text-primary)'>标题</h1>"
            "<p style='font-size:14px;color:var(--text-secondary)'>正文</p>",
            encoding="utf-8")
        results = V.run_checks(png, None, html)
        ids = {r["id"] for r in results}
        statuses = {r["id"]: r["status"] for r in results}
        check("run_checks returns results without crashing", len(results) > 5)
        check("always-on new per-page checks present", always_new.issubset(ids))
        bad = [i for i in ids & all_new if statuses.get(i) == "FAIL"]
        check("no new check ever emits FAIL (exit contract preserved)", not bad)


def test_dtheme():
    """DTHEME-01 is diagram-card-scoped: hardcoded color inside a diagram card's
    region WARNs; a themed region PASSes."""
    print("visual_qa (DTHEME-01 scoping):")
    with tempfile.TemporaryDirectory() as d:
        planning = Path(d) / "p.json"
        planning.write_text('{"page":{"cards":[{"card_type":"diagram","card_id":"d1"}]}}', encoding="utf-8")
        hard = '<div data-card-id="d1"><svg><rect fill="#abcdef"/></svg></div>'
        themed = '<div data-card-id="d1"><svg><rect fill="var(--accent-1)"/></svg></div>'
        check("DTHEME warns on hardcoded color in diagram region",
              V.check_diagram_theme_binding(hard, planning)["status"] == "WARN")
        check("DTHEME passes on themed diagram region",
              V.check_diagram_theme_binding(themed, planning)["status"] == "PASS")
        check("DTHEME no-op when no diagram card",
              V.check_diagram_theme_binding(themed, None) is None)


def test_light_bg_false_positives():
    """BLANK-01 / CUT-01 must not fire on light-background (blue_white) decks:
    a near-white slide with content is fine; only truly empty slides FAIL blank,
    and only content bleeding to the edge WARNs cutoff."""
    print("visual_qa (light-bg false positives):")
    white = Image.new("RGB", (1280, 720), (248, 248, 248))
    content = Image.new("RGB", (1280, 720), (248, 248, 248))
    for x in range(100, 600):
        for y in range(100, 400):
            content.putpixel((x, y), (30, 40, 90))
    check("BLANK-01 passes light bg with content", V.check_blank_ratio(content)["status"] == "PASS")
    check("BLANK-01 fails truly-empty light slide", V.check_blank_ratio(white)["status"] == "FAIL")
    check("BLANK-01 mid-tone flat fill (no style) still FAILs", V.check_blank_ratio(Image.new("RGB", (1280, 720), (120, 120, 120)))["status"] == "FAIL")
    check("CUT-01 no false positive on all-white slide", V.check_overflow_cutoff(white)["status"] == "PASS")
    bleed = Image.new("RGB", (1280, 720), (248, 248, 248))
    for x in range(1280):
        for y in range(716, 720):
            bleed.putpixel((x, y), (200, 20, 20))
    check("CUT-01 warns on content bleeding to bottom edge", V.check_overflow_cutoff(bleed)["status"] == "WARN")
    check("CUT-01 no false positive on dark slide", V.check_overflow_cutoff(Image.new("RGB", (1280, 720), (16, 20, 30)))["status"] == "PASS")


def test_structural_hex_whitelist():
    """HEX-01 ignores structural #fff/#ffffff (theme-invariant white) but still
    flags genuinely off-theme hex."""
    print("visual_qa (HEX-01 structural white):")
    check("#fff whitelisted", V.check_hardcoded_colors("<div style='background:#fff'>")["status"] == "PASS")
    check("#ffffff whitelisted", V.check_hardcoded_colors("<div style='color:#ffffff'>")["status"] == "PASS")
    check("non-white hex still flagged", V.check_hardcoded_colors("<div style='color:#abcdef'>")["status"] == "WARN")
    check("#fff excluded from count, real offender kept",
          "1 处" in V.check_hardcoded_colors("<div style='background:#fff;color:#abcdef'>")["msg"])


def test_style_and_naming():
    """load_style_bg parses the declared background; _slide_number accepts both
    slide-N and slide_NN naming."""
    print("visual_qa (style bg + slide naming):")
    with tempfile.TemporaryDirectory() as d:
        sp = Path(d) / "style.json"
        sp.write_text('{"css_variables":{"bg_primary":"#f8f8f8"}}', encoding="utf-8")
        check("load_style_bg parses hex", V.load_style_bg(sp) == (248, 248, 248))
        sp.write_text('{"css_variables":{"bg_primary":"rgb(10, 14, 26)"}}', encoding="utf-8")
        check("load_style_bg parses rgb()", V.load_style_bg(sp) == (10, 14, 26))
        check("load_style_bg None on missing", V.load_style_bg(Path(d) / "nope.json") is None)
    check("_slide_number slide-3", V._slide_number("slide-3") == 3)
    check("_slide_number slide_03 (zero-pad)", V._slide_number("slide_03") == 3)
    check("_slide_number no match", V._slide_number("foo") is None)


def test_mermaid_polish():
    """Tests for diagram polish features: parse fixes, external class, tech label, legend, metadata."""
    print("mermaid_polish:")
    import sys as _sys
    import re as _re
    _sys.path.insert(0, str(ROOT / "scripts"))
    from mermaid_layout import (  # noqa: E402
        _parse_spec, _parse_spec_and_class, _parse_graph_source, _dispatch,
        _extract_diagram_title, _render_metadata_chip, _render_legend, _wrap_label,
        COL_GAP, GROUP_PAD_X, GROUP_PAD_Y_TOP,
    )

    # AC-1: _parse_spec strips surrounding quotes from rect labels
    nid, label, shape = _parse_spec('A["My Service"]')
    check("_parse_spec strips quotes from [\"label\"]", label == "My Service")
    _, label2, _ = _parse_spec("A['single']")
    check("_parse_spec strips single quotes", label2 == "single")

    # AC-2b: \n in labels renders as <br> line breaks
    check("_wrap_label splits on literal \\n escape", _wrap_label("Line 1\\nLine 2") == ["Line 1", "Line 2"])
    check("_wrap_label splits on real newline", _wrap_label("Line 1\nLine 2") == ["Line 1", "Line 2"])
    html_nl = _dispatch("flowchart TD\nA[\"First\\nSecond\"] --> B", None, 400)
    check("\\n in label renders as <br>", "<br>" in html_nl and "First" in html_nl and "Second" in html_nl)

    # AC-2: subgraph ID["Label"] bracket extraction (regression guard)
    nodes, edges, groups = _parse_graph_source([
        'subgraph db["Database Layer"]', 'N[x]', 'end'
    ])
    grp = list(groups.values())[0]
    check("subgraph ID[\"Label\"] extracts label text", grp.label == "Database Layer")

    # AC-3: COL_GAP and GROUP_PAD constants are at target values
    check("COL_GAP is 32px", COL_GAP == 32)
    check("GROUP_PAD_X is 16px", GROUP_PAD_X == 16)
    check("GROUP_PAD_Y_TOP is 28px", GROUP_PAD_Y_TOP == 28)

    # AC-4: :::external class parsing
    _, _, _, css_class = _parse_spec_and_class("A[Service]:::external")
    check("_parse_spec_and_class extracts :::external", css_class == "external")
    nodes, _, _ = _parse_graph_source(['A["API"]:::external --> B["DB"]'])
    check("external class stored on node A", nodes["A"].css_class == "external")
    check("internal node B has no css_class", nodes["B"].css_class == "")

    # External node renders with dim color on the node-external div itself
    html = _dispatch("flowchart TD\nA[Ext]:::external --> B[Int]", None, 400)
    check("external node has node-external CSS class in div", "node-external" in html)
    # Find the node-external div and check it contains --node-fg-dim in its own style attr
    ext_match = _re.search(r'<div class="node[^"]*node-external[^"]*" style="([^"]*)"', html)
    check("external node div style uses --node-fg-dim for border",
          ext_match is not None and "--node-fg-dim" in ext_match.group(1))

    # AC-5: | tech stereotype sub-label
    html = _dispatch('flowchart TD\nA["Svc|Spring Boot"] --> B[DB]', None, 400)
    check("tech sub-label span present", "node-tech" in html)
    check("tech sub-label text rendered", "Spring Boot" in html)
    check("main label still rendered", "Svc" in html)
    # | with surrounding spaces should strip whitespace
    html_ws = _dispatch('flowchart TD\nA["Svc | Spring Boot"] --> B', None, 400)
    check("tech label whitespace stripped", "Spring Boot" in html_ws)

    # AC-6: legend auto-generated for mixed edge styles
    html_mixed = _dispatch("flowchart TD\nA --> B\nA -.- C", None, 400)
    check("legend present for solid+dashed diagram", "diagram-legend" in html_mixed)
    check("Async legend item present", "Async" in html_mixed)
    html_plain = _dispatch("flowchart TD\nA --> B --> C", None, 400)
    check("legend absent for plain solid-only diagram", "diagram-legend" not in html_plain)
    html_thick = _dispatch("flowchart TD\nA --> B\nA ==> C", None, 400)
    check("legend present for solid+thick diagram", "diagram-legend" in html_thick)
    check("Critical path legend item present", "Critical path" in html_thick)
    # Single non-solid semantic still triggers legend (no solid edges present)
    html_dashed_only = _dispatch("flowchart TD\nA -.- B -.- C", None, 400)
    check("legend present for dashed-only diagram", "diagram-legend" in html_dashed_only)

    # AC-7: metadata chip is title-gated (not added to untitled diagrams)
    check("_extract_diagram_title finds %% title:", _extract_diagram_title(
        "%% title: My Arch\nflowchart TD\nA-->B") == "My Arch")
    check("_extract_diagram_title ignores plain %% comment",
          _extract_diagram_title("%% define nodes\nflowchart TD\nA-->B") == "")
    check("_extract_diagram_title returns '' for no comment",
          _extract_diagram_title("flowchart TD\nA-->B") == "")
    chip = _render_metadata_chip("flowchart", "My Arch")
    check("metadata chip contains type label", "Flowchart" in chip)
    check("metadata chip contains title", "My Arch" in chip)
    check("metadata chip empty for no title", _render_metadata_chip("flowchart", "") == "")
    check("metadata chip empty for unknown directive and no title",
          _render_metadata_chip("unknown_xyz", "") == "")
    html_titled = _dispatch("%% title: Payments\nflowchart TD\nA-->B", None, 400)
    check("titled diagram has diagram-meta", "diagram-meta" in html_titled)
    check("title text in titled diagram output", "Payments" in html_titled)
    html_untitled = _dispatch("flowchart TD\nA --> B", None, 400)
    check("untitled diagram has no diagram-meta", "diagram-meta" not in html_untitled)


def main() -> int:
    test_lint()
    test_visual_qa_html()
    test_visual_qa_palette()
    test_deck()
    test_exit_contract()
    test_dtheme()
    test_light_bg_false_positives()
    test_structural_hex_whitelist()
    test_style_and_naming()
    test_mermaid_polish()
    print()
    if FAILS:
        print(f"test_diagram_qa: {len(FAILS)} FAILED")
        return 1
    print("test_diagram_qa: all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
