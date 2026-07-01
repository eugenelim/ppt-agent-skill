#!/usr/bin/env python3
"""lint_diagram_recipes.py — structural + pipeline-safety lint for diagram recipes.

Checks the diagram recipe family files against the contract pinned in
docs/specs/diagram-consistency-system/spec.md:

  1. Each recipe (a `### <name> (<id>)` heading) carries the five bold-label
     markers in any order: 何时用 / 数据格式 / 模板(or HTML 模板) / 自检 / 管线安全.
  2. No fenced code block uses a pipeline-forbidden technique:
     SVG <text>, CSS-border triangle, ::before/::after visual content,
     mask-image, conic-gradient, background-clip:text, mix-blend-mode,
     stroke-dashoffset.
  3. No hardcoded hex/rgb() colors in code blocks except the trend
     whitelist (#22c55e / #ef4444).
  4. The selector file blocks/diagram.md carries the theming contract.

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

COLOR_WHITELIST = {"#22c55e", "#ef4444"}
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs-dir", default="references")
    args = ap.parse_args()
    blocks_dir = Path(args.refs_dir) / "blocks"
    if not blocks_dir.is_dir():
        print(f"ERROR: {blocks_dir} not found", file=sys.stderr)
        return 1

    targets = sorted(blocks_dir.glob("diagram*.md")) + [blocks_dir / "timeline.md"]
    targets = [t for t in targets if t.exists()]

    all_findings: list[str] = []
    recipe_count = 0
    for t in targets:
        all_findings.extend(lint_file(t))
        recipe_count += sum(1 for ln in t.read_text(encoding="utf-8").splitlines() if RECIPE_HEADING.match(ln))

    if all_findings:
        print(f"lint_diagram_recipes: {len(all_findings)} violation(s) across {len(targets)} file(s):")
        for f in all_findings:
            print(f"  XX {f}")
        return 1
    print(f"lint_diagram_recipes: OK — {recipe_count} recipe(s) across {len(targets)} file(s), no violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
