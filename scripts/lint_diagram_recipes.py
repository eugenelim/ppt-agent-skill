#!/usr/bin/env python3
"""lint_diagram_recipes.py — structural + pipeline-safety lint for block recipes.

Covers the diagram recipe family files, timeline.md, worksheet.md, and
advisory-brief.md. Checks
the recipe contract pinned in docs/specs/diagram-consistency-system/spec.md:

  1. Each recipe (a `### <name> (<id>)` heading) carries the five bold-label
     markers in any order: 何时用 / 数据格式 / 模板(or HTML 模板) / 自检 / 管线安全.
  2. No fenced code block uses a pipeline-forbidden technique:
     SVG <text>, CSS-border triangle, ::before/::after visual content,
     mask-image, conic-gradient, background-clip:text, mix-blend-mode,
     stroke-dashoffset.
  3. No hardcoded hex/rgb() colors in code blocks except the trend
     whitelist (#22c55e / #ef4444).
  4. The selector file blocks/diagram.md carries the theming contract.
  5. persistent_chrome sample-literal sync: the design-specs §A "持久化页框例外"
     forbidden-literal list stays in sync (both directions) with the worksheet
     group-C masthead/footer recipe sample copy, so the prohibition can't go
     stale on a recipe edit (docs/specs/persistent-chrome-flag).

Usage:
    python3 scripts/lint_diagram_recipes.py [--refs-dir references]

Exit: 0 = clean, 1 = violations found.
Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SELECTOR = "diagram.md"
RECIPE_HEADING = re.compile(r"^###\s+.*\(.+\)\s*$")
FENCE = re.compile(r"```[a-zA-Z0-9]*\n(.*?)```", re.DOTALL)
MARKERS = ["何时用", "数据格式", ("模板", "HTML 模板"), "自检", "管线安全"]

# trend colors (#22c55e/#ef4444) + worksheet status-block semantic signal colors
# (ok / warn, with their -soft tints) — both are semantic-constant carve-outs
# documented in blocks/worksheet.md + styles/light.md §10, not theme colors.
COLOR_WHITELIST = {
    "#22c55e", "#ef4444",
    "#1f7a3a", "#e9f5ed", "#b35900", "#fef3e6",
}
# 8-digit before 6-digit before 3-digit so #rrggbbaa is caught (not truncated to 6)
HEX = re.compile(r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")
RGB = re.compile(r"\brgba?\(", re.IGNORECASE)
# 命名颜色出现在 CSS 值 / SVG 属性位置（fill/stroke/color/background）也算脱离主题
NAMED_COLOR = re.compile(
    r"(?:fill|stroke|color|background(?:-color)?)\s*[:=]\s*[\"']?"
    r"(red|blue|green|white|black|yellow|orange|purple|pink|gray|grey|cyan|magenta)\b",
    re.IGNORECASE,
)

# (label, regex) forbidden in code blocks
FORBIDDEN = [
    ("SVG <text>", re.compile(r"<text[\s>]", re.IGNORECASE)),
    ("conic-gradient", re.compile(r"conic-gradient", re.IGNORECASE)),
    ("mask-image", re.compile(r"-?\bwebkit-?\s*-?mask-image|mask-image", re.IGNORECASE)),
    ("background-clip:text", re.compile(r"background-clip\s*:\s*text", re.IGNORECASE)),
    ("mix-blend-mode", re.compile(r"mix-blend-mode", re.IGNORECASE)),
    # only pseudo-elements CARRYING visual content (content: with a non-empty string) — AC4 scope
    ("::before/::after visual content",
     re.compile(r"::(before|after)[\s\S]{0,160}?content\s*:\s*[\"'][^\"']+[\"']", re.IGNORECASE)),
    ("stroke-dashoffset", re.compile(r"stroke-dashoffset", re.IGNORECASE)),
    ("CSS border triangle", re.compile(r"solid\s+transparent|border-color\s*:\s*transparent", re.IGNORECASE)),
]


_COMMENT_RE = re.compile(r"<!--.*?-->|/\*.*?\*/", re.DOTALL)


def code_blocks(text: str) -> list[str]:
    # Strip HTML/CSS comments so explanatory notes ("无 <text>") don't false-trip
    # the forbidden-technique scan — only rendered markup is checked.
    return [_COMMENT_RE.sub("", b) for b in FENCE.findall(text)]


def lint_file(path: Path) -> list[str]:
    findings: list[str] = []
    text = path.read_text(encoding="utf-8")
    name = path.name

    # ── selector file: theming contract present, not treated as recipes ──
    if name == SELECTOR:
        if "主题契约" not in text or "--node-bg-from" not in text:
            findings.append(f"{name}: selector missing 主题契约 / --node-bg-from theming contract")

    # ── per-recipe marker completeness (recipe = ### heading with (id)) ──
    lines = text.splitlines()
    recipe_idxs = [i for i, ln in enumerate(lines) if RECIPE_HEADING.match(ln)]
    for n, start in enumerate(recipe_idxs):
        end = recipe_idxs[n + 1] if n + 1 < len(recipe_idxs) else len(lines)
        body = "\n".join(lines[start:end])
        title = lines[start].strip()
        for marker in MARKERS:
            opts = marker if isinstance(marker, tuple) else (marker,)
            if not any(f"**{o}**" in body for o in opts):
                findings.append(f"{name}: recipe {title!r} missing marker **{opts[0]}**")

    # ── code-block scans: forbidden techniques + hardcoded colors ──
    for block in code_blocks(text):
        for label, rx in FORBIDDEN:
            if rx.search(block):
                snippet = rx.search(block).group(0)
                findings.append(f"{name}: pipeline-forbidden technique {label} ({snippet!r}) in code block")
        for m in HEX.findall(block):
            if m.lower() not in COLOR_WHITELIST:
                findings.append(f"{name}: hardcoded color {m} in code block (use a theme variable)")
        if RGB.search(block):
            findings.append(f"{name}: hardcoded rgb()/rgba() in code block (use a theme variable)")
        nm = NAMED_COLOR.search(block)
        if nm:
            findings.append(f"{name}: hardcoded named color {nm.group(1)!r} in code block (use a theme variable)")
    return findings


# ── persistent_chrome sample-literal sync (design-specs §A ↔ worksheet group C) ──
# The §A "持久化页框例外" forbids leaking worksheet group-C masthead/footer sample
# copy (docs/specs/persistent-chrome-flag). That prohibition list is hand-copied
# from the recipe, so it can silently go stale when a recipe literal is renamed
# (→ §A entry no longer real) or added (→ §A misses it). This check keeps the two
# in sync in both directions. Structural column headings the recipe carries but §A
# does not forbid (they are relabelled per-page, not leaked brand copy) are allowlisted.
CHROME_LABEL_ALLOWLIST = {"Sections", "Rev", "Section", "Page"}
_TAG_RE = re.compile(r"<[^>]+>")
_ENTITIES = {"&gt;": ">", "&lt;": "<", "&amp;": "&", "&mdash;": "—", "&nbsp;": " "}


def _visible_text_literals(element_html: str) -> list[str]:
    """Tag-strip an HTML element to its human-visible text nodes (decoded, trimmed),
    dropping empties and symbol-only fragments (chevrons, glyphs)."""
    text = _TAG_RE.sub("\n", element_html)
    for ent, ch in _ENTITIES.items():
        text = text.replace(ent, ch)
    out: list[str] = []
    for raw in text.split("\n"):
        node = raw.strip()
        if len(node) >= 2 and any(c.isalnum() for c in node):
            out.append(node)
    return out


def check_persistent_chrome_literals(refs_dir: Path) -> list[str]:
    findings: list[str] = []
    specs = refs_dir / "design-runtime" / "design-specs.md"
    worksheet = refs_dir / "blocks" / "worksheet.md"
    if not specs.exists() or not worksheet.exists():
        return findings  # feature not present in this refs tree — nothing to sync
    spec_text = specs.read_text(encoding="utf-8")
    ws_text = worksheet.read_text(encoding="utf-8")

    m = re.search(r"绝不沿用配方里的示例文案[^（(]*[（(](.+?)[）)]", spec_text, re.S)
    if not m:
        findings.append("design-specs.md §A: persistent_chrome forbidden-literal list not found "
                        "(expected '绝不沿用配方里的示例文案（…）')")
        return findings
    forbidden = re.findall(r"`([^`]+)`", m.group(1))
    if not forbidden:
        findings.append("design-specs.md §A: persistent_chrome forbidden-literal list is empty")

    # recipe side: masthead <div class="masthead">…</div> + footer <footer>…</footer>
    recipe_literals: list[str] = []
    mh = re.search(r'<div class="masthead".*?</div>', ws_text, re.S)
    ft = re.search(r"<footer.*?</footer>", ws_text, re.S)
    if not mh or not ft:
        findings.append("blocks/worksheet.md: group-C masthead/footer recipe not found "
                        "(persistent_chrome literal sync cannot run)")
        return findings
    for element in (mh.group(0), ft.group(0)):
        recipe_literals.extend(_visible_text_literals(element))

    # direction B — every recipe sample literal must be forbidden by §A (catches added/renamed)
    for lit in recipe_literals:
        if lit in CHROME_LABEL_ALLOWLIST:
            continue
        if lit not in forbidden:
            findings.append(f"blocks/worksheet.md group C shows sample literal {lit!r} that "
                            f"design-specs.md §A does not forbid — add it to the §A 禁用清单")
    # direction A — every §A entry must still exist in the recipe (catches renamed/removed)
    joined = mh.group(0) + "\n" + ft.group(0)
    for lit in forbidden:
        if lit not in joined:
            findings.append(f"design-specs.md §A forbids {lit!r} but it no longer appears in the "
                            f"blocks/worksheet.md group-C masthead/footer recipe — the list is stale")
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs-dir", default="references")
    args = ap.parse_args()
    refs_dir = Path(args.refs_dir)
    blocks_dir = refs_dir / "blocks"
    if not blocks_dir.is_dir():
        print(f"ERROR: {blocks_dir} not found", file=sys.stderr)
        return 1

    targets = sorted(blocks_dir.glob("diagram*.md")) + [
        blocks_dir / "timeline.md",
        blocks_dir / "worksheet.md",
        blocks_dir / "advisory-brief.md",
        blocks_dir / "discovery-readout.md",
    ]
    targets = [t for t in targets if t.exists()]

    all_findings: list[str] = []
    recipe_count = 0
    for t in targets:
        all_findings.extend(lint_file(t))
        recipe_count += sum(1 for ln in t.read_text(encoding="utf-8").splitlines() if RECIPE_HEADING.match(ln))

    all_findings.extend(check_persistent_chrome_literals(refs_dir))

    if all_findings:
        print(f"lint_diagram_recipes: {len(all_findings)} violation(s) across {len(targets)} file(s):")
        for f in all_findings:
            print(f"  XX {f}")
        return 1
    print(f"lint_diagram_recipes: OK — {recipe_count} recipe(s) across {len(targets)} file(s), no violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
