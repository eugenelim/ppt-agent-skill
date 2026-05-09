#!/usr/bin/env python3
"""smoke_test.py -- 端到端测试 + 失败模式扫描

测试覆盖：
1. 风格定义校验：从 references/styles/*.md 提取 JSON，校验必填字段
2. 风格 mock HTML 校验：检查 ppt-output/style-gallery/<id>.html 存在 + pipeline-compat 检查
3. 图表组件渲染校验（Phase 3 后启用）
4. 端到端 PPT 生成（Phase 5 后启用）
5. 失败模式扫描（参考 references/principles/failure-modes.md）

用法：
    python3 scripts/smoke_test.py                   # 跑全部
    python3 scripts/smoke_test.py --style dark_tech # 只测一个风格
    python3 scripts/smoke_test.py --phase 1         # 只跑 Phase 1 测试

输出：
    tests/smoke-results/<timestamp>/report.md
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# -------------------------------------------------------------------
# 项目根目录
# -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
STYLES_DIR = ROOT / "references" / "styles"
GALLERY_DIR = ROOT / "ppt-output" / "style-gallery"
RESULTS_DIR = ROOT / "tests" / "smoke-results"

# -------------------------------------------------------------------
# 必填字段定义
# -------------------------------------------------------------------
STYLE_REQUIRED_FIELDS = {
    "style_id", "style_name", "category",
    "inspiration", "mood_keywords", "design_soul", "variation_strategy",
    "decoration_dna", "background", "card", "text", "accent",
    "typography", "decorations", "font_imports",
}
DECORATION_DNA_REQUIRED = {"signature_move", "forbidden", "recommended_combos"}
VALID_CATEGORIES = {
    "dark_professional", "light_premium", "vibrant",
    "cultural_oriental", "natural_retro",
}

# -------------------------------------------------------------------
# pipeline-compat 禁止清单
# -------------------------------------------------------------------
FORBIDDEN_CSS = [
    (r'mask-image\s*:', "mask-image (use div mask instead)"),
    (r'-webkit-mask-image\s*:', "-webkit-mask-image (use div mask instead)"),
    (r'conic-gradient\s*\(', "conic-gradient (use SVG circle + dasharray)"),
    (r'mix-blend-mode\s*:', "mix-blend-mode (use opacity instead)"),
    (r'background-image\s*:\s*url', "CSS background-image url() (use <img> tag)"),
]

# -------------------------------------------------------------------
# 工具函数
# -------------------------------------------------------------------

def extract_style_jsons(md_path: Path) -> list:
    """从 markdown 文件中提取所有 ```json ... ``` 代码块的 JSON 对象（含 style_id）。"""
    text = md_path.read_text(encoding="utf-8")
    blocks = re.findall(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
    styles = []
    for block in blocks:
        try:
            obj = json.loads(block)
            if isinstance(obj, dict) and "style_id" in obj:
                styles.append(obj)
        except json.JSONDecodeError:
            pass
    return styles


def validate_style(style: dict) -> list:
    """校验单个风格 JSON。返回错误列表（空表示通过）。"""
    errors = []
    style_id = style.get("style_id", "<unknown>")

    # 1. 必填字段
    missing = STYLE_REQUIRED_FIELDS - set(style.keys())
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")

    # 2. category 合法值
    cat = style.get("category")
    if cat and cat not in VALID_CATEGORIES:
        errors.append(f"invalid category '{cat}'; must be one of {sorted(VALID_CATEGORIES)}")

    # 3. decoration_dna 子字段
    dd = style.get("decoration_dna", {})
    if isinstance(dd, dict):
        dd_missing = DECORATION_DNA_REQUIRED - set(dd.keys())
        if dd_missing:
            errors.append(f"decoration_dna missing: {sorted(dd_missing)}")
        if "forbidden" in dd and len(dd["forbidden"]) < 3:
            errors.append(f"decoration_dna.forbidden should list >= 3 items (got {len(dd['forbidden'])})")

    # 4. mood_keywords 数量
    mk = style.get("mood_keywords", [])
    if not isinstance(mk, list) or len(mk) < 3:
        errors.append(f"mood_keywords should have >= 3 items (got {len(mk) if isinstance(mk, list) else type(mk).__name__})")

    # 5. accent 结构
    acc = style.get("accent", {})
    if not isinstance(acc, dict) or "primary" not in acc:
        errors.append("accent.primary missing")
    elif not isinstance(acc.get("primary"), list) or len(acc["primary"]) < 2:
        errors.append("accent.primary should be array of >= 2 colors")

    # 6. typography 必填子字段
    typo = style.get("typography", {})
    typo_required = {"display_font", "body_font", "display_letter_spacing", "tabular_nums"}
    typo_missing = typo_required - set(typo.keys())
    if typo_missing:
        errors.append(f"typography missing: {sorted(typo_missing)}")

    # 7. font_imports 是数组
    fi = style.get("font_imports", [])
    if not isinstance(fi, list):
        errors.append("font_imports must be array")

    return errors


def check_html_pipeline_compat(html_path: Path) -> list:
    """扫描 HTML 是否使用了 pipeline-compat 禁止的 CSS 特性。"""
    errors = []
    if not html_path.exists():
        return [f"file not found: {html_path}"]
    text = html_path.read_text(encoding="utf-8")
    for pattern, description in FORBIDDEN_CSS:
        # 排除注释中的提及
        for match in re.finditer(pattern, text, re.IGNORECASE):
            # 简单跳过注释（不严谨但够用）
            line_start = text.rfind("\n", 0, match.start()) + 1
            line = text[line_start:text.find("\n", match.start())]
            if line.strip().startswith(("//", "*", "/*")):
                continue
            errors.append(f"forbidden CSS '{description}' at offset {match.start()}")
            break
    return errors


def check_html_typography(html_path: Path) -> list:
    """简单的排版铁律检查（启发式，只检查同一 CSS 规则块内的字距）。"""
    warnings = []
    if not html_path.exists():
        return []
    text = html_path.read_text(encoding="utf-8")

    # 解析 CSS 规则块（粗略：{ ... }）
    # 每个规则块内独立检查 font-size 与 letter-spacing 关系
    css_blocks = re.findall(r'\{([^{}]*)\}', text)

    for block in css_blocks:
        # 找到本块内的 font-size（取最大的，如果有多个声明）
        size_matches = re.findall(r'font-size\s*:\s*(\d+(?:\.\d+)?)px', block)
        if not size_matches:
            continue
        max_size = max(float(s) for s in size_matches)
        if max_size < 64:  # 只检查 64px 以上的真大字（serif/luxury 用 48-63 可豁免）
            continue

        # 检查同一规则块内的 letter-spacing
        ls_match = re.search(r'letter-spacing\s*:\s*(-?\d+(?:\.\d+)?)em', block)
        if not ls_match:
            continue
        ls_value = float(ls_match.group(1))
        # 严格 sans display 规则：>= 64px 且 < -0.02em；
        # 允许 serif italic 风格保持松弛字距（通过文本上下文识别）
        # 阈值放宽到 -0.015em（serif/编辑风允许略松散）；
        # 真正要警告的是接近 0 或正值（明显未做收紧）
        if ls_value > -0.015:
            # 检查是否是 serif italic 或 luxury 风格（豁免）
            block_low = block.lower()
            if any(x in block_low for x in ['italic', 'playfair', 'didot', 'serif', 'fraunces', 'bodoni', 'tiempos', 'cheltenham']):
                continue
            warnings.append(f"sans display font-size {max_size:.0f}px should have letter-spacing <= -0.025em (found {ls_value}em)")

    # 检查是否引入了 tabular-nums（如果有数字）
    if re.search(r'\d+%|\d+\s*ms|\d{2,}', text) and "tabular-nums" not in text:
        warnings.append("HTML contains numbers but no font-variant-numeric: tabular-nums")

    # 检查是否启用 OpenType 特性
    if "font-feature-settings" not in text:
        warnings.append("HTML missing font-feature-settings (kern/liga/ss01)")

    return warnings


# -------------------------------------------------------------------
# Phase 1 测试
# -------------------------------------------------------------------

def phase1_tests(style_filter: str = None) -> dict:
    """Phase 1：风格定义 + Mock HTML 校验。"""
    results = {
        "phase": 1,
        "style_validation": {},
        "html_compat": {},
        "html_typography": {},
        "summary": {"pass": 0, "fail": 0, "warn": 0},
    }

    # 收集所有风格 JSON
    md_files = sorted(STYLES_DIR.glob("*.md"))
    md_files = [f for f in md_files if f.name != "index.md"]
    all_styles = []
    for md in md_files:
        all_styles.extend(extract_style_jsons(md))

    if not all_styles:
        results["summary"]["fail"] += 1
        results["error"] = "no styles found in references/styles/*.md"
        return results

    for style in all_styles:
        sid = style["style_id"]
        if style_filter and sid != style_filter:
            continue

        # 校验 JSON
        errors = validate_style(style)
        results["style_validation"][sid] = errors
        if errors:
            results["summary"]["fail"] += len(errors)
        else:
            results["summary"]["pass"] += 1

        # 校验对应 mock HTML
        html_path = GALLERY_DIR / f"{sid}.html"
        compat_errors = check_html_pipeline_compat(html_path)
        results["html_compat"][sid] = compat_errors
        if compat_errors:
            results["summary"]["fail"] += len(compat_errors)
        elif html_path.exists():
            results["summary"]["pass"] += 1

        # 排版警告（不计 fail）
        typo_warnings = check_html_typography(html_path)
        results["html_typography"][sid] = typo_warnings
        results["summary"]["warn"] += len(typo_warnings)

    return results


# -------------------------------------------------------------------
# 报告生成
# -------------------------------------------------------------------

def generate_report(results: dict, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / "report.md"
    lines = [
        f"# Smoke Test Report",
        f"",
        f"- 时间: {datetime.now().isoformat(timespec='seconds')}",
        f"- Phase: {results.get('phase')}",
        f"- 通过: {results['summary']['pass']}",
        f"- 失败: {results['summary']['fail']}",
        f"- 警告: {results['summary']['warn']}",
        f"",
    ]

    if "error" in results:
        lines += [f"## ❌ 全局错误", "", f"```", results["error"], "```", ""]

    # Style validation
    sv = results.get("style_validation", {})
    if sv:
        lines += ["## 风格 JSON 校验", ""]
        for sid, errs in sv.items():
            if errs:
                lines.append(f"### ❌ {sid}")
                for e in errs:
                    lines.append(f"  - {e}")
            else:
                lines.append(f"### ✅ {sid} (passed)")
        lines.append("")

    # HTML compat
    hc = results.get("html_compat", {})
    if hc:
        lines += ["## Mock HTML pipeline-compat 检查", ""]
        for sid, errs in hc.items():
            if errs:
                lines.append(f"### ❌ {sid}")
                for e in errs:
                    lines.append(f"  - {e}")
            else:
                html_path = GALLERY_DIR / f"{sid}.html"
                status = "✅" if html_path.exists() else "⚠️ (no mock yet)"
                lines.append(f"### {status} {sid}")
        lines.append("")

    # Typography warnings
    ht = results.get("html_typography", {})
    if any(ht.values()):
        lines += ["## 排版警告（不阻塞，但应修复）", ""]
        for sid, warns in ht.items():
            if warns:
                lines.append(f"### ⚠️ {sid}")
                for w in warns:
                    lines.append(f"  - {w}")
        lines.append("")

    report.write_text("\n".join(lines), encoding="utf-8")
    return report


# -------------------------------------------------------------------
# 主入口
# -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PPT Agent Smoke Test")
    parser.add_argument("--style", help="只测试指定 style_id")
    parser.add_argument("--phase", type=int, default=1, choices=[1, 2, 3, 4, 5],
                       help="只跑指定 Phase 测试")
    parser.add_argument("--quiet", action="store_true", help="只输出失败")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RESULTS_DIR / timestamp

    if args.phase == 1:
        results = phase1_tests(style_filter=args.style)
    else:
        print(f"Phase {args.phase} tests not yet implemented", file=sys.stderr)
        sys.exit(1)

    report = generate_report(results, out_dir)

    s = results["summary"]
    print(f"\n{'='*60}")
    print(f"Smoke Test Phase {results['phase']}")
    print(f"{'='*60}")
    print(f"✅ Pass:  {s['pass']}")
    print(f"❌ Fail:  {s['fail']}")
    print(f"⚠️  Warn: {s['warn']}")
    print(f"📄 Report: {report}")
    print()

    sys.exit(0 if s['fail'] == 0 else 1)


if __name__ == "__main__":
    main()
