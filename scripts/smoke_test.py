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
import subprocess
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

_STYLE_ID_PATTERN = re.compile(r'^[a-z][a-z0-9_]*$')

def extract_style_jsons(md_path: Path) -> list:
    """从 markdown 文件中提取所有 ```json ... ``` 代码块的 JSON 对象（含合法 style_id）。

    跳过示例 schema（如 "自定义 ID 或预置 ID" / "your_style_id" / 占位符等），
    只收 snake_case 合法 ID。
    """
    text = md_path.read_text(encoding="utf-8")
    blocks = re.findall(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
    styles = []
    for block in blocks:
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        sid = obj.get("style_id", "")
        if not isinstance(sid, str) or not _STYLE_ID_PATTERN.match(sid):
            continue
        styles.append(obj)
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


def check_html_pseudo_decorations(html_path: Path) -> list:
    """伪元素视觉装饰检查（警告级，不计 fail）。

    pipeline-compat.md 把 `::before`/`::after` 视觉装饰列为"内容消失"风险，应改用真实
    `<span>`/`<div>`；但 html2svg.py 对伪元素有（效果较差的）兜底，故为**警告**而非硬失败。
    判据：选择器含 `::before`/`::after` 且规则块声明 `content` —— 装饰型伪元素必带 content。
    通用 reset（如 `*,*::before,*::after{box-sizing:border-box}` 无 content）不触发。
    """
    warnings = []
    if not html_path.exists():
        return []
    text = html_path.read_text(encoding="utf-8")
    for sel, body in re.findall(r'([^{}]*)\{([^{}]*)\}', text):
        if "::before" not in sel and "::after" not in sel:
            continue
        if re.search(r'(^|[;\s])content\s*:', body):
            warnings.append(
                f"pseudo-element decoration '{sel.strip()[:48]}' declares content: "
                "-- prefer a real <span>/<div> (pipeline-compat; html2svg fallback is lossy)"
            )
    return warnings


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
        # CJK 中文（宋体/楷体）需要 0.15-0.32em 的正字距，是设计要求；
        # 真正要警告的是 0 ~ 0.1em 之间的拉丁字体（明显未做收紧或未拉开）
        if -0.015 < ls_value < 0.10:
            block_low = block.lower()
            # 豁免：serif italic / luxury / 圆润字体（kindergarten / retro 70s）
            exempt_keywords = [
                'italic', 'playfair', 'didot', 'serif', 'fraunces',
                'bodoni', 'tiempos', 'cheltenham', 'instrument',
                'quicksand', 'nunito', 'bagel', 'bowlby',
                # CJK 字体（宋体/楷体/黑体）
                'noto serif sc', 'source han', 'stsong', 'stkaiti',
                'simsun', 'noto sans sc', 'pingfang', 'microsoft yahei',
                'noto serif jp', 'hiragino',
            ]
            if any(x in block_low for x in exempt_keywords):
                continue
            warnings.append(f"sans display font-size {max_size:.0f}px should have letter-spacing in [-0.045, -0.015]em or > 0.15em (found {ls_value}em)")

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
        "html_pseudo": {},
        "summary": {"pass": 0, "fail": 0, "warn": 0},
    }

    # 收集所有风格 JSON
    md_files = sorted(STYLES_DIR.glob("*.md"))
    # 排除 schema 示例文件，与 gallery.py 的口径一致（index.md + readme.md）
    md_files = [f for f in md_files if f.name.lower() not in ("index.md", "readme.md")]
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

        # 校验 mock HTML —— 两个层级都是**必备**夹具：详情 <id>.html + 封面
        # <id>.cover.html。任一缺失 → check_html_pipeline_compat 返回
        # "file not found" → 计 fail，从而机械保证"每个风格两版齐全"（forward
        # standard，见 spec AC）。新增/吸收风格若只出一版，smoke 直接判 fail。
        tiers = [
            (sid, GALLERY_DIR / f"{sid}.html"),
            (f"{sid} (cover)", GALLERY_DIR / f"{sid}.cover.html"),
        ]

        for key, html_path in tiers:
            compat_errors = check_html_pipeline_compat(html_path)
            results["html_compat"][key] = compat_errors
            if compat_errors:
                results["summary"]["fail"] += len(compat_errors)
            elif html_path.exists():
                results["summary"]["pass"] += 1

            # 排版警告（不计 fail）
            typo_warnings = check_html_typography(html_path)
            results["html_typography"][key] = typo_warnings
            results["summary"]["warn"] += len(typo_warnings)

            # 伪元素装饰警告（不计 fail）
            pseudo_warnings = check_html_pseudo_decorations(html_path)
            results["html_pseudo"][key] = pseudo_warnings
            results["summary"]["warn"] += len(pseudo_warnings)

    # 子进程自检：图解配方 lint + QA 自检 + 画廊 Cover|Detail 切换构造检查
    results["diagram_qa"] = {}
    for label, cmd in [
        ("recipe_lint", [sys.executable, str(ROOT / "scripts" / "lint_diagram_recipes.py"), "--refs-dir", str(ROOT / "references")]),
        ("qa_selftest", [sys.executable, str(ROOT / "scripts" / "test_diagram_qa.py")]),
        ("gallery_toggle", [sys.executable, str(ROOT / "scripts" / "test_gallery_toggle.py")]),
        ("proof_worksheet", [sys.executable, str(ROOT / "scripts" / "test_proof_worksheet.py")]),
        ("proof_gate", [sys.executable, str(ROOT / "scripts" / "test_proof_gate.py")]),
        ("html_packager", [sys.executable, str(ROOT / "scripts" / "test_html_packager.py")]),
        ("build_pdf", [sys.executable, str(ROOT / "scripts" / "test_build_pdf.py")]),
        ("diag_route", [sys.executable, str(ROOT / "scripts" / "test_planning_diag_route.py")]),
        ("slide_montage", [sys.executable, str(ROOT / "scripts" / "test_slide_montage.py")]),
        ("html2png_cwd", [sys.executable, str(ROOT / "scripts" / "test_html2png_cwd.py")]),
        ("render_gate", [sys.executable, str(ROOT / "scripts" / "test_render_gate.py")]),
    ]:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        ok = proc.returncode == 0
        results["diagram_qa"][label] = {"ok": ok, "tail": (proc.stdout or proc.stderr).strip().splitlines()[-1:] or ["(no output)"]}
        if ok:
            results["summary"]["pass"] += 1
        else:
            results["summary"]["fail"] += 1

    return results


# -------------------------------------------------------------------
# Phase 0 文档/代码合同漂移检查（调用 sunbigfly 的 check_skill.py）
# -------------------------------------------------------------------

def phase0_check_skill() -> dict:
    """Phase 0: 跑 check_skill.py 检查 SKILL.md/cheatsheet/scripts 三方一致性。"""
    results = {"phase": 0, "check_skill": {}, "summary": {"pass": 0, "fail": 0, "warn": 0}}
    cs = subprocess.run(
        ["python3", str(ROOT / "scripts" / "check_skill.py")],
        capture_output=True, text=True, timeout=60
    )
    out = cs.stdout
    err_count = 0
    warn_count = 0
    m = re.search(r'errors:\s*(\d+)', out)
    if m: err_count = int(m.group(1))
    m = re.search(r'warnings:\s*(\d+)', out)
    if m: warn_count = int(m.group(1))
    results["check_skill"] = {
        "rc": cs.returncode,
        "errors": err_count,
        "warnings": warn_count,
        "output": out[-1000:],
    }
    if err_count == 0:
        results["summary"]["pass"] += 1
    else:
        results["summary"]["fail"] += err_count
    results["summary"]["warn"] += warn_count
    return results


# -------------------------------------------------------------------
# Phase 5 端到端测试：跑完整 HTML→SVG→PPTX 管线
# -------------------------------------------------------------------

E2E_REPRESENTATIVE_STYLES = ["dark_tech", "mocha_editorial", "royal_red"]


def phase5_e2e_tests(style_filter: str = None) -> dict:
    """Phase 5: 端到端管线测试。"""
    import shutil
    results = {
        "phase": 5,
        "e2e": {},
        "summary": {"pass": 0, "fail": 0, "warn": 0},
    }

    e2e_dir = ROOT / "ppt-output" / "e2e-test"
    slides_dir = e2e_dir / "slides"
    svg_dir = e2e_dir / "svg"

    # 清理并准备 slides + svg 目录（避免上次残留干扰计数）
    if slides_dir.exists():
        shutil.rmtree(slides_dir)
    if svg_dir.exists():
        shutil.rmtree(svg_dir)
    slides_dir.mkdir(parents=True, exist_ok=True)

    test_styles = [style_filter] if style_filter else E2E_REPRESENTATIVE_STYLES
    for sid in test_styles:
        src = GALLERY_DIR / f"{sid}.html"
        if not src.exists():
            results["e2e"][sid] = {"error": f"source mock not found: {src}"}
            results["summary"]["fail"] += 1
            continue
        dst = slides_dir / f"{sid}.html"
        shutil.copy(src, dst)

    # 1. html_packager
    pkg_result = subprocess.run(
        ["python3", str(ROOT / "scripts" / "html_packager.py"),
         str(slides_dir), "-o", str(e2e_dir / "preview.html")],
        capture_output=True, text=True, timeout=60
    )
    results["e2e"]["html_packager"] = {
        "rc": pkg_result.returncode,
        "stdout": pkg_result.stdout[-200:],
        "stderr": pkg_result.stderr[-200:],
    }
    if pkg_result.returncode == 0 and (e2e_dir / "preview.html").exists():
        results["summary"]["pass"] += 1
    else:
        results["summary"]["fail"] += 1

    # 2. html2svg
    svg_result = subprocess.run(
        ["python3", str(ROOT / "scripts" / "html2svg.py"),
         str(slides_dir), "-o", str(svg_dir)],
        capture_output=True, text=True, timeout=300
    )
    results["e2e"]["html2svg"] = {
        "rc": svg_result.returncode,
        "stdout": svg_result.stdout[-300:],
        "stderr": svg_result.stderr[-300:],
    }
    svgs_count = len(list(svg_dir.glob("*.svg"))) if svg_dir.exists() else 0
    if svg_result.returncode == 0 and svgs_count == len(test_styles):
        results["summary"]["pass"] += 1
    else:
        results["summary"]["fail"] += 1

    # 3. svg2pptx
    pptx_result = subprocess.run(
        ["python3", str(ROOT / "scripts" / "svg2pptx.py"),
         str(svg_dir), "-o", str(e2e_dir / "presentation.pptx")],
        capture_output=True, text=True, timeout=120
    )
    results["e2e"]["svg2pptx"] = {
        "rc": pptx_result.returncode,
        "stdout": pptx_result.stdout[-300:],
        "stderr": pptx_result.stderr[-300:],
    }
    if pptx_result.returncode == 0 and (e2e_dir / "presentation.pptx").exists():
        results["summary"]["pass"] += 1
    else:
        results["summary"]["fail"] += 1

    # 4. 验证每个 SVG 含 <text> 元素（文字可编辑）
    for sid in test_styles:
        svg_path = svg_dir / f"{sid}.svg"
        if svg_path.exists():
            content = svg_path.read_text(errors="ignore")
            text_count = content.count("<text ")
            results["e2e"][f"{sid}_text_count"] = text_count
            if text_count >= 5:
                results["summary"]["pass"] += 1
            else:
                results["summary"]["warn"] += 1

    # 5. 清理 e2e-test 测试产物（puppeteer node_modules 现在装在 ROOT，不在这里）
    if e2e_dir.exists() and pptx_result.returncode == 0:
        shutil.rmtree(e2e_dir)
        results["e2e"]["cleanup"] = "ok (e2e-test removed)"

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
        for key, errs in hc.items():
            if errs:
                lines.append(f"### ❌ {key}")
                for e in errs:
                    lines.append(f"  - {e}")
            else:
                # key is the composite tier key: "<id>" (detail) or "<id> (cover)".
                # Resolve to the real file rather than rebuilding "<id>.html" blindly.
                if key.endswith(" (cover)"):
                    html_path = GALLERY_DIR / f"{key[:-len(' (cover)')]}.cover.html"
                else:
                    html_path = GALLERY_DIR / f"{key}.html"
                status = "✅" if html_path.exists() else "⚠️ (no mock yet)"
                lines.append(f"### {status} {key}")
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

    # Pseudo-element decoration warnings
    hp = results.get("html_pseudo", {})
    if any(hp.values()):
        lines += ["## 伪元素装饰警告（不阻塞，建议改真实元素）", ""]
        for sid, warns in hp.items():
            if warns:
                lines.append(f"### ⚠️ {sid}")
                for w in warns:
                    lines.append(f"  - {w}")
        lines.append("")

    # check_skill (Phase 0)
    cs = results.get("check_skill", {})
    if cs:
        ok = cs.get("errors", 0) == 0
        lines += [f"## ✅/❌ check_skill (文档/代码合同漂移)", ""]
        lines.append(f"- 退出码: {cs.get('rc')}")
        lines.append(f"- errors: {cs.get('errors', 0)}")
        lines.append(f"- warnings: {cs.get('warnings', 0)}")
        if cs.get("output"):
            lines.append("")
            lines.append("```")
            lines.append(cs["output"])
            lines.append("```")
        lines.append("")

    # E2E pipeline
    e2e = results.get("e2e", {})
    if e2e:
        lines += ["## 端到端管线测试", ""]
        for stage in ["html_packager", "html2svg", "svg2pptx"]:
            r = e2e.get(stage, {})
            ok = r.get("rc") == 0
            lines.append(f"### {'✅' if ok else '❌'} {stage}")
            if not ok and r.get("stderr"):
                lines.append("```")
                lines.append(r["stderr"])
                lines.append("```")
        lines.append("")
        # Text 元素统计
        text_counts = {k: v for k, v in e2e.items() if k.endswith("_text_count")}
        if text_counts:
            lines += ["### SVG `<text>` 可编辑文字统计", ""]
            for k, v in text_counts.items():
                sid = k.replace("_text_count", "")
                marker = "✅" if v >= 5 else "⚠️"
                lines.append(f"- {marker} {sid}: {v} 个 <text> 元素")
            lines.append("")

    report.write_text("\n".join(lines), encoding="utf-8")
    return report


# -------------------------------------------------------------------
# 主入口
# -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PPT Agent Smoke Test")
    parser.add_argument("--style", help="只测试指定 style_id")
    parser.add_argument("--phase", type=int, default=1, choices=[0, 1, 2, 3, 4, 5],
                       help="只跑指定 Phase 测试 (0=check_skill, 1=style+pipeline-compat, 5=e2e)")
    parser.add_argument("--quiet", action="store_true", help="只输出失败")
    parser.add_argument("--max-warn", type=int, default=None,
                       help="警告预算：当 summary.warn 超过 N 时以非零退出（默认不启用）。"
                            "把文档里的 warn 预算变成真实闸门，例如 CI 用 --phase 1 --max-warn 10。")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RESULTS_DIR / timestamp

    if args.phase == 1:
        results = phase1_tests(style_filter=args.style)
    elif args.phase == 5:
        results = phase5_e2e_tests(style_filter=args.style)
    elif args.phase == 0:
        results = phase0_check_skill()
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
    if args.max_warn is not None and s['warn'] > args.max_warn:
        print(f"❌ Warn budget exceeded: {s['warn']} > --max-warn {args.max_warn}")
    print()

    warn_over = args.max_warn is not None and s['warn'] > args.max_warn
    sys.exit(0 if (s['fail'] == 0 and not warn_over) else 1)


if __name__ == "__main__":
    main()
