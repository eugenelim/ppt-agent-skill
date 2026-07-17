#!/usr/bin/env python3
"""visual_qa.py — 自动化视觉质量断言脚本

在 subagent review 完成后，由主 agent 运行此脚本对 slide PNG 做客观检测。
检测项全部基于像素分析，不依赖 LLM 判断。

注意：本脚本是机械客观项，只是图审的**下限**，不是图审本身。人工/子代理的
"找茬心态 + 新鲜眼睛"冷读（见 references/playbooks/step4/page-review-playbook.md
的 Part A-bug）才是主力：假设一定有问题、零发现=没看够狠、修一处必重扫一轮。
脚本退出码 0 不代表设计过关，只代表没触发这几条像素级红线。

用法：
    # 检查单页
    python3 scripts/visual_qa.py OUTPUT_DIR/png/slide-1.png --planning OUTPUT_DIR/planning/planning1.json --html OUTPUT_DIR/slides/slide-1.html

    # 批量检查所有页（同时接受 slide-N.png 与 slide_NN.png 命名）
    python3 scripts/visual_qa.py OUTPUT_DIR/png --planning-dir OUTPUT_DIR/planning --html-dir OUTPUT_DIR/slides

    # 浅底 deck 务必带 --style，让 BLANK-01 / CUT-01 知道声明背景色（避免近白底假阳）
    python3 scripts/visual_qa.py OUTPUT_DIR/png --planning-dir OUTPUT_DIR/planning --html-dir OUTPUT_DIR/slides --style OUTPUT_DIR/style.json

    # 同时把文本报告写入 runtime
    python3 scripts/visual_qa.py OUTPUT_DIR/png/slide-1.png --planning OUTPUT_DIR/planning/planning1.json --html OUTPUT_DIR/slides/slide-1.html --output OUTPUT_DIR/runtime/page-review-qa-1.txt

退出码：
    0 = 全部通过
    1 = 存在 FAIL（致命缺陷，建议重跑该页）
    2 = 只有 WARN（品质警告，可交付但建议人工复查）
"""

import json
import re
import sys
from pathlib import Path

# PIL 是唯一外部依赖；如缺失则给出友好提示
try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow", file=sys.stderr)
    sys.exit(1)


DECORATION_BUDGET_LIMITS = {
    "generous": 6,
    "medium": 4,
    "low": 2,
    "minimal": 1,
}

# BLANK-01 / CUT-01：背景感知常量
# 主色与「声明背景色」的 RGB 曼哈顿距离小于此值 → 视为同一背景（不算空白/裁切）
BLANK_BG_MATCH_DIST = 60
# 像素相对主背景色的曼哈顿距离大于此值 → 视为「内容」（前景像素）
BLANK_CONTENT_DIST = 90
# 边缘像素相对背景色偏离大于此值 → 视为「触边内容」（疑似裁切）
CUT_EDGE_DIST = 60


def _slide_number(stem: str) -> int | None:
    """从 slide-N / slide_NN 文件名提取页码（去零填充）。无法匹配返回 None。"""
    m = re.search(r"slide[-_](\d+)", stem)
    return int(m.group(1)) if m else None


def _rgb_dist(a: tuple, b: tuple) -> int:
    """RGB 曼哈顿距离（sum of abs channel diff），对深/浅背景对称。"""
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def _parse_color(value) -> tuple | None:
    """把 #hex / #rgb / rgb()/rgba() 字符串解析为 (r,g,b)；无法解析返回 None。"""
    if not isinstance(value, str):
        return None
    v = value.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", v, re.IGNORECASE)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _parse_rgba(value) -> tuple | None:
    """解析 #hex / rgb() / rgba() 为 (r,g,b,a)，a∈[0,1]；无法解析返回 None。

    text_secondary 常写成 rgba(...,0.7) 之类的半透明色 —— 计算对比度前必须先
    把它按 alpha 混合到所在表面上（见 _composite_over），否则会低估其真实亮度。
    """
    rgb = _parse_color(value)
    if rgb is None:
        return None
    a = 1.0
    if isinstance(value, str):
        m = re.match(r"rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*([0-9.]+)\s*\)",
                     value.strip(), re.IGNORECASE)
        if m:
            try:
                a = max(0.0, min(1.0, float(m.group(1))))
            except ValueError:
                a = 1.0
    return (rgb[0], rgb[1], rgb[2], a)


def _composite_over(rgba: tuple, bg: tuple) -> tuple:
    """把带 alpha 的前景色混合到不透明背景色上，返回不透明 (r,g,b)。"""
    a = rgba[3]
    return tuple(round(rgba[i] * a + bg[i] * (1 - a)) for i in range(3))


def _rel_luminance(rgb: tuple) -> float:
    """WCAG 2.x 相对亮度（sRGB → 线性 → 加权）。"""
    def _lin(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (_lin(rgb[0]), _lin(rgb[1]), _lin(rgb[2]))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(a: tuple, b: tuple) -> float:
    """WCAG 对比度比值 (L1+0.05)/(L2+0.05)，1.0–21.0。"""
    la, lb = _rel_luminance(a), _rel_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def load_style_bg(style_path: Path | None) -> tuple | None:
    """从 style.json 读取声明的主背景色（css_variables.bg_primary）。

    供 BLANK-01 / CUT-01 排除「设计意图内的背景」——浅底 deck（如 blue_white）
    的近白底不再被误判为大面积空白或触边裁切。
    """
    if not style_path or not Path(style_path).exists():
        return None
    try:
        data = json.loads(Path(style_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    cssv = data.get("css_variables")
    if not isinstance(cssv, dict):
        return None
    for key in ("bg_primary", "bg_secondary"):
        rgb = _parse_color(cssv.get(key))
        if rgb:
            return rgb
    return None


def load_style_palette(style_path: Path | None) -> dict | None:
    """从 style.json 读取文本色 + 表面色，供 CONTRAST-01/02 算真实 WCAG 对比度。

    只依赖 style-phase1-playbook 的 12 基础 css_variables 红线合同
    （text_primary / text_secondary + bg_primary / bg_secondary /
    card_bg_from / card_bg_to），因此对任何风格都成立、无外部依赖。
    返回 {"texts": {role: (r,g,b,a)}, "surfaces": {name: (r,g,b)}}；缺料返回 None。
    """
    if not style_path or not Path(style_path).exists():
        return None
    try:
        data = json.loads(Path(style_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    cssv = data.get("css_variables") if isinstance(data, dict) else None
    if not isinstance(cssv, dict):
        return None
    texts = {}
    for key in ("text_primary", "text_secondary"):
        rgba = _parse_rgba(cssv.get(key))
        if rgba:
            texts[key] = rgba
    surfaces = {}
    for key in ("bg_primary", "bg_secondary", "card_bg_from", "card_bg_to"):
        rgb = _parse_color(cssv.get(key))
        if rgb:
            surfaces[key] = rgb
    if not texts or not surfaces:
        return None
    return {"texts": texts, "surfaces": surfaces}


# ─────────────────────── 检测函数 ───────────────────────

def check_dimensions(img: Image.Image) -> dict:
    """检测截图分辨率是否为 16:9 比例，支持下层缩小图片"""
    w, h = img.size
    if abs(w / h - 16 / 9) < 0.05:
        if w >= 960:
            return {"id": "DIM-01", "status": "PASS", "msg": f"分辨率 {w}x{h} (比例正常)"}
        else:
            return {"id": "DIM-01", "status": "WARN", "msg": f"分辨率 {w}x{h} (较小但可接受)"}
    return {"id": "DIM-01", "status": "FAIL", "msg": f"分辨率 {w}x{h} 不符合 16:9 规格"}


def check_blank_ratio(img: Image.Image, threshold: float = 0.40,
                      bg_rgb: tuple | None = None) -> dict:
    """检测大面积空白/纯色区域是否超过阈值。

    策略：将图片缩放到小尺寸后统计主色占比。占比高本身不是问题——
    深色主题的深底、浅色主题（如 blue_white）的近白底天然占比高。
    判定改为「相对主背景色的内容像素是否太少」，对深/浅背景对称：
      - 深底：偏离主色的更亮像素 = 内容
      - 浅底：偏离主色的更暗/着色像素 = 内容
    若传入 style.json 的声明背景色 bg_rgb，则主色贴近它时直接按背景处理，
    不再对浅底误报为「大面积空白」（修复 BLANK-01 在浅底 deck 的假阳）。
    """
    # 缩放以加速
    small = img.resize((128, 72), Image.LANCZOS)
    pixels = list(small.getdata())
    total = len(pixels)

    # 统计颜色频率（降低精度到 8-bit 级别）
    color_count: dict[tuple, int] = {}
    for p in pixels:
        # 量化到 32 级
        quantized = (p[0] // 8 * 8, p[1] // 8 * 8, p[2] // 8 * 8)
        color_count[quantized] = color_count.get(quantized, 0) + 1

    # 找最高频色
    dominant_color = max(color_count, key=color_count.get)
    dominant_ratio = color_count[dominant_color] / total

    if dominant_ratio <= threshold:
        return {"id": "BLANK-01", "status": "PASS",
                "msg": f"画面色彩分布正常，主色占比 {dominant_ratio:.0%}"}

    brightness = sum(dominant_color) / 3
    # 主色是否为「背景」：声明背景色贴近，或本身是深/浅极值
    is_declared_bg = bg_rgb is not None and _rgb_dist(dominant_color, bg_rgb) <= BLANK_BG_MATCH_DIST
    is_extreme_bg = brightness < 60 or brightness > 200

    if is_declared_bg or is_extreme_bg:
        # 背景占比高属正常，改判「内容是否太少」——偏离主色的像素即内容
        content_pixels = sum(1 for p in pixels if _rgb_dist(p[:3], dominant_color) > BLANK_CONTENT_DIST)
        content_ratio = content_pixels / total
        tone = "浅色背景" if brightness > 128 else "深色背景"
        src = "（style 声明背景）" if is_declared_bg else ""
        if content_ratio < 0.15:
            return {"id": "BLANK-01", "status": "FAIL",
                    "msg": f"内容区域仅占 {content_ratio:.0%}，{tone}{src}占 {dominant_ratio:.0%}（P0-3 大面积空白）"}
        return {"id": "BLANK-01", "status": "PASS",
                "msg": f"{tone}{src} {dominant_ratio:.0%}，内容区 {content_ratio:.0%}"}

    # 中间调主色大面积铺满、又不是声明背景 → 才是真可疑
    return {"id": "BLANK-01", "status": "FAIL",
            "msg": f"主色 RGB{dominant_color} 占比 {dominant_ratio:.0%}，疑似大面积空白（P0-3）"}


def check_vertical_text(img: Image.Image) -> dict:
    """辅助检测：是否存在疑似竖排单字列。

    注意：此检测为辅助提示（WARN），不做最终判定。
    排版质量的真正判断应由 LLM 通过宿主可用的图像查看能力看 PNG 截图完成。
    """
    w, h = img.size
    right_half = img.crop((w // 2, 0, w, h))
    small = right_half.resize((256, 144), Image.LANCZOS).convert("L")
    pixels = small.load()
    sw, sh = small.size

    threshold = 60
    suspect_regions = []

    x = 0
    while x < sw:
        col_content = sum(1 for y in range(sh) if pixels[x, y] > threshold)

        if col_content > sh * 0.25:  # 宽松阈值，宁可误报
            band_start = x
            band_end = x
            while band_end < sw - 1:
                next_content = sum(1 for y in range(sh) if pixels[band_end + 1, y] > threshold)
                if next_content > sh * 0.15:
                    band_end += 1
                else:
                    break

            band_width = band_end - band_start + 1
            content_rows = set()
            for bx in range(band_start, band_end + 1):
                for y in range(sh):
                    if pixels[bx, y] > threshold:
                        content_rows.add(y)

            content_height = (max(content_rows) - min(content_rows) + 1) if content_rows else 0
            width_ratio = band_width / sw
            height_ratio = content_height / sh

            if width_ratio < 0.06 and height_ratio > 0.35:
                suspect_regions.append(f"w={width_ratio:.1%} h={height_ratio:.1%}")

            x = band_end + 1
        else:
            x += 1

    if suspect_regions:
        return {"id": "VTXT-01", "status": "WARN",
                "msg": f"检测到 {len(suspect_regions)} 处疑似窄列内容带（{'; '.join(suspect_regions[:3])}），建议人工确认排版"}

    return {"id": "VTXT-01", "status": "PASS", "msg": "未检测到竖排异常"}


def check_overflow_cutoff(img: Image.Image, bg_rgb: tuple | None = None) -> dict:
    """检测底部/右侧是否有内容被裁切痕迹。

    策略：检查底部/右侧边缘是否仍有**偏离背景色**的内容（提示被裁切）。
    过去用「绝对亮度 > 80」判定，会在浅底 deck 把白色留白误判为内容而永远
    触发（修复 CUT-01 浅底假阳）。改为相对背景色的色彩变化：白底白边、
    深底深边都归零，只有真正触边的内容（任意颜色）才计入。
    背景色来源：优先 style.json 声明的 bg_rgb，否则取四角像素众数作为背景。
    """
    w, h = img.size
    pixels = img.load()

    bg = bg_rgb if bg_rgb is not None else _infer_bg_from_corners(img)

    # 检查底部最后 4 行
    bottom_content_pixels = 0
    bottom_total = w * 4
    for y in range(h - 4, h):
        for x in range(w):
            if _rgb_dist(pixels[x, y][:3], bg) > CUT_EDGE_DIST:
                bottom_content_pixels += 1

    bottom_ratio = bottom_content_pixels / bottom_total if bottom_total > 0 else 0

    # 检查右侧最后 4 列
    right_content_pixels = 0
    right_total = h * 4
    for x in range(w - 4, w):
        for y in range(h):
            if _rgb_dist(pixels[x, y][:3], bg) > CUT_EDGE_DIST:
                right_content_pixels += 1

    right_ratio = right_content_pixels / right_total if right_total > 0 else 0

    issues = []
    if bottom_ratio > 0.2:
        issues.append(f"底部边缘 {bottom_ratio:.0%} 像素偏离背景色，疑似内容被裁切")
    if right_ratio > 0.15:
        issues.append(f"右侧边缘 {right_ratio:.0%} 像素偏离背景色，疑似内容被裁切")

    if issues:
        return {"id": "CUT-01", "status": "WARN", "msg": " | ".join(issues)}

    return {"id": "CUT-01", "status": "PASS", "msg": "边缘无异常裁切痕迹"}


def _infer_bg_from_corners(img: Image.Image) -> tuple:
    """取四角 8x8 区域的像素众数作为背景参考色（无 style 声明时的兜底）。"""
    w, h = img.size
    s = 8
    regions = [(0, 0), (w - s, 0), (0, h - s), (w - s, h - s)]
    counts: dict[tuple, int] = {}
    px = img.load()
    for ox, oy in regions:
        for x in range(ox, min(ox + s, w)):
            for y in range(oy, min(oy + s, h)):
                q = tuple(c // 8 * 8 for c in px[x, y][:3])
                counts[q] = counts.get(q, 0) + 1
    return max(counts, key=counts.get) if counts else (0, 0, 0)


def check_contrast_zones(img: Image.Image) -> dict:
    """检测是否存在大面积低对比度区域（文字不可读）。

    策略：将图片分成 8x8 网格，对每个块计算亮度标准差。
    如果大量块的标准差极低（= 纯色块），且这些块不是背景色，则可能有对比度问题。
    """
    w, h = img.size
    grid_w, grid_h = 8, 8
    block_w = w // grid_w
    block_h = h // grid_h

    low_contrast_blocks = 0
    total_blocks = grid_w * grid_h

    for gx in range(grid_w):
        for gy in range(grid_h):
            block = img.crop((gx * block_w, gy * block_h, (gx + 1) * block_w, (gy + 1) * block_h))
            small_block = block.resize((16, 16), Image.LANCZOS)
            pixels = list(small_block.getdata())
            brightnesses = [sum(p[:3]) / 3 for p in pixels]

            avg = sum(brightnesses) / len(brightnesses)
            variance = sum((b - avg) ** 2 for b in brightnesses) / len(brightnesses)

            # 低方差 + 中等亮度 = 可能有文字被遮盖或对比度不足
            if variance < 25 and 40 < avg < 200:
                low_contrast_blocks += 1

    ratio = low_contrast_blocks / total_blocks
    if ratio > 0.6:
        return {"id": "CONT-01", "status": "WARN",
                "msg": f"{ratio:.0%} 的区块对比度极低，可能存在文字不可读区域"}

    return {"id": "CONT-01", "status": "PASS",
            "msg": f"对比度分布正常（低对比区块 {ratio:.0%}）"}


# WCAG 1.4.3 文本对比度下限（可读性铁律，非交互 a11y）：
# 正文(<24px) ≥ 4.5:1；大字(≥24px 或 ≥18.66px 粗体) ≥ 3:1。
CONTRAST_BODY_MIN = 4.5
CONTRAST_LARGE_MIN = 3.0


def check_text_contrast(palette: dict) -> list[dict]:
    """CONTRAST-01/02：用声明调色板算真实 WCAG 对比度（deck 级，纯色彩数学）。

    CONT-01 只是像素方差代理（大面积中亮度平面 = 疑似不可读）；本检查用
    style.json 声明的 text × surface 直接算 WCAG 比值，是可读性的硬下限。
    每个文本色取「最可读的声明表面」判级：若在所有表面都 < 3:1，主文本视为
    彻底不可读 → FAIL；仅达大字标准或部分表面不达标 → WARN。深/浅底对称。
    """
    results = []
    surfaces = palette["surfaces"]
    role_meta = {
        "text_primary": ("CONTRAST-01", "主文本", True),
        "text_secondary": ("CONTRAST-02", "次文本", False),
    }
    for role, rgba in palette["texts"].items():
        cid, label, is_primary = role_meta.get(role, ("CONTRAST-00", role, False))
        pairs = [(_contrast_ratio(_composite_over(rgba, s), s), name)
                 for name, s in surfaces.items()]
        if not pairs:
            continue
        best_ratio, best_surface = max(pairs, key=lambda t: t[0])
        worst_ratio, worst_surface = min(pairs, key=lambda t: t[0])
        if best_ratio < CONTRAST_LARGE_MIN:
            results.append({"id": cid, "status": "FAIL" if is_primary else "WARN",
                "msg": f"{label}色在所有声明表面对比度均 < 3:1（最佳 {best_ratio:.1f}:1 @ {best_surface}），正文与大字均不可读"})
        elif best_ratio < CONTRAST_BODY_MIN:
            results.append({"id": cid, "status": "WARN",
                "msg": f"{label}色最佳仅 {best_ratio:.1f}:1（@ {best_surface}），仅达大字(≥24px)标准；正文需 ≥4.5:1"})
        elif worst_ratio < CONTRAST_BODY_MIN:
            results.append({"id": cid, "status": "WARN",
                "msg": f"{label}色在 {worst_surface} 上仅 {worst_ratio:.1f}:1（<4.5:1）；该表面放正文需换色或加深"})
        else:
            results.append({"id": cid, "status": "PASS",
                "msg": f"{label}色对比度 {worst_ratio:.1f}–{best_ratio:.1f}:1，全表面达正文标准(≥4.5:1)"})
    return results


def check_file_size(png_path: Path) -> dict:
    """检测 PNG 文件大小是否合理。"""
    size = png_path.stat().st_size
    if size < 10_000:
        return {"id": "SIZE-01", "status": "FAIL",
                "msg": f"PNG 仅 {size:,} bytes，疑似空白页或截图失败"}
    if size < 50_000:
        return {"id": "SIZE-01", "status": "WARN",
                "msg": f"PNG {size:,} bytes，内容可能过少"}
    return {"id": "SIZE-01", "status": "PASS", "msg": f"PNG {size:,} bytes"}


def check_planning_cards_coverage(img: Image.Image, planning_path: Path) -> dict:
    """辅助检测：planning 卡片 vs 图片结构复杂度的粗略对比。

    注意：此检测为辅助提示。深色主题下边缘密度天然偏低，
    真正的卡片缺失判断应由 LLM 看图 + 对照 planning JSON 完成。
    """
    if not planning_path.exists():
        return {"id": "CARD-01", "status": "WARN", "msg": f"planning 文件不存在: {planning_path}"}

    try:
        with open(planning_path) as f:
            planning = json.load(f)
        page = planning.get("page", planning)
        cards = page.get("cards", [])
        card_count = len(cards)
    except (json.JSONDecodeError, KeyError):
        return {"id": "CARD-01", "status": "WARN", "msg": "planning JSON 解析失败"}

    if card_count == 0:
        return {"id": "CARD-01", "status": "PASS", "msg": "planning 无卡片定义"}

    w, h = img.size
    small = img.resize((64, 36), Image.LANCZOS).convert("L")
    pixels = small.load()
    sw, sh = small.size

    edge_count = 0
    for y in range(sh):
        for x in range(1, sw):
            diff = abs(pixels[x, y] - pixels[x - 1, y])
            if diff > 30:
                edge_count += 1

    edge_density = edge_count / (sw * sh)

    # 极低边缘密度 + 多卡片 = 疑似卡片缺失（辅助提示）
    if card_count >= 3 and edge_density < 0.015:
        return {"id": "CARD-01", "status": "WARN",
                "msg": f"planning 有 {card_count} 张卡片，但图片结构极简（边缘密度 {edge_density:.3f}），建议人工确认卡片完整性"}

    return {"id": "CARD-01", "status": "PASS",
            "msg": f"planning {card_count} 张卡片，图片边缘密度 {edge_density:.3f}"}


def load_planning_page(planning_path: Path) -> dict | None:
    if not planning_path.exists():
        return None
    try:
        payload = json.loads(planning_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict) and isinstance(payload.get("page"), dict):
        return payload["page"]
    return payload if isinstance(payload, dict) else None


def check_density_contract_budget(planning_path: Path) -> list[dict]:
    page = load_planning_page(planning_path)
    if not isinstance(page, dict):
        return [{"id": "DENS-01", "status": "WARN", "msg": "planning JSON 解析失败，跳过密度合同检查"}]

    density_contract = page.get("density_contract")
    if not isinstance(density_contract, dict):
        return [{"id": "DENS-01", "status": "FAIL", "msg": "planning 缺少 density_contract"}]

    cards = [card for card in page.get("cards", []) if isinstance(card, dict)]
    chart_count = sum(
        1 for card in cards
        if isinstance(card.get("chart"), dict) and isinstance(card.get("chart", {}).get("chart_type"), str)
    )
    results: list[dict] = []

    max_cards = density_contract.get("max_cards")
    if isinstance(max_cards, int) and len(cards) > max_cards:
        results.append({"id": "DENS-01", "status": "FAIL", "msg": f"卡片数 {len(cards)} 超过 density_contract.max_cards={max_cards}"})
    else:
        results.append({"id": "DENS-01", "status": "PASS", "msg": f"卡片数 {len(cards)} / 上限 {max_cards}"})

    max_charts = density_contract.get("max_charts")
    if isinstance(max_charts, int) and chart_count > max_charts:
        results.append({"id": "DENS-02", "status": "FAIL", "msg": f"图表数 {chart_count} 超过 density_contract.max_charts={max_charts}"})
    else:
        results.append({"id": "DENS-02", "status": "PASS", "msg": f"图表数 {chart_count} / 上限 {max_charts}"})

    density_label = str(page.get("density_label") or "").strip().lower()
    image_policy = density_contract.get("image_policy")
    if density_label == "dashboard":
        has_needed_image = any(isinstance(card.get("image"), dict) and card["image"].get("needed") for card in cards)
        has_image_hero = any(card.get("card_type") == "image_hero" for card in cards)
        if image_policy != "decorate_only" or has_needed_image or has_image_hero:
            results.append(
                {
                    "id": "DENS-03",
                    "status": "FAIL",
                    "msg": "dashboard 页必须使用 decorate_only，且不得包含 image_hero 或外部图片合同",
                }
            )
        else:
            results.append({"id": "DENS-03", "status": "PASS", "msg": "dashboard 图片策略符合合同"})

    return results


def check_html_contracts(html_path: Path, planning_path: Path | None) -> list[dict]:
    if not html_path.exists():
        return [{"id": "HTML-01", "status": "FAIL", "msg": f"html 文件不存在: {html_path}"}]

    text = html_path.read_text(encoding="utf-8")
    page = load_planning_page(planning_path) if planning_path else None
    page_type = str((page or {}).get("page_type") or "").strip().lower()
    density_label = str((page or {}).get("density_label") or "").strip().lower()
    density_contract = (page or {}).get("density_contract") if isinstance((page or {}).get("density_contract"), dict) else {}
    results: list[dict] = []

    if page_type in {"content", "toc", "section", "section-marker", "reference"}:
        header_ok = bool(re.search(r'<header[^>]*class=([\'"])[^\'"]*\bslide-header\b[^\'"]*\1', text, re.IGNORECASE))
        footer_ok = bool(re.search(r'<footer[^>]*class=([\'"])[^\'"]*\bslide-footer\b[^\'"]*\1', text, re.IGNORECASE))
        results.append({"id": "HTML-01", "status": "PASS" if header_ok else "FAIL", "msg": "header.slide-header 存在" if header_ok else "缺少统一标题区 header.slide-header"})
        results.append({"id": "HTML-02", "status": "PASS" if footer_ok else "FAIL", "msg": "footer.slide-footer 存在" if footer_ok else "缺少统一页脚 footer.slide-footer"})

    if isinstance(page, dict):
        expected_ids = [str(card.get("card_id")).strip() for card in page.get("cards", []) if isinstance(card, dict) and str(card.get("card_id") or "").strip()]
        missing_ids = [card_id for card_id in expected_ids if f'data-card-id="{card_id}"' not in text and f"data-card-id='{card_id}'" not in text]
        if missing_ids:
            results.append({"id": "HTML-03", "status": "FAIL", "msg": f"缺少 data-card-id 节点: {missing_ids[:5]}"})
        else:
            results.append({"id": "HTML-03", "status": "PASS", "msg": f"全部 {len(expected_ids)} 个 data-card-id 已落地"})

    if density_label == "dashboard":
        has_img = "<img" in text.lower()
        has_bg_url = "background-image" in text.lower() and "url(" in text.lower()
        if has_img or has_bg_url:
            results.append({"id": "HTML-04", "status": "FAIL", "msg": "dashboard 页不应出现外部图片或 background-image url()"})
        else:
            results.append({"id": "HTML-04", "status": "PASS", "msg": "dashboard 页未检测到外部图片依赖"})

    if re.search(r"<img\b", text, flags=re.IGNORECASE):
        object_fit_ok = "object-fit: cover" in text.lower() or "object-fit:contain" in text.lower() or "object-fit: contain" in text.lower()
        results.append({"id": "HTML-05", "status": "PASS" if object_fit_ok else "WARN", "msg": "检测到 img 且 object-fit 已声明" if object_fit_ok else "检测到 img，但未发现 object-fit 声明，建议人工确认是否会拉伸"})

    min_body_font = density_contract.get("min_body_font_px")
    if isinstance(min_body_font, int):
        font_sizes = [int(item) for item in re.findall(r"font-size\s*:\s*(\d+)px", text, flags=re.IGNORECASE)]
        if font_sizes:
            too_small = [size for size in font_sizes if size < min_body_font]
            if too_small and min(too_small) <= max(10, min_body_font - 4):
                results.append({"id": "HTML-06", "status": "FAIL", "msg": f"检测到字体低于合同下限 {min_body_font}px：最小 {min(too_small)}px"})
            elif too_small:
                results.append({"id": "HTML-06", "status": "WARN", "msg": f"检测到低于合同下限 {min_body_font}px 的字体 {sorted(set(too_small))}，请人工确认是否为正文"})
            else:
                results.append({"id": "HTML-06", "status": "PASS", "msg": f"未检测到明显低于 {min_body_font}px 的字体"})

    decoration_budget = density_contract.get("decoration_budget")
    decoration_tags = re.findall(
        r"<[^>]*data-decoration-layer\s*=\s*(['\"])(background|floating|page-accent)\1[^>]*>",
        text,
        flags=re.IGNORECASE,
    )
    marker_count = len(decoration_tags)
    if decoration_budget in DECORATION_BUDGET_LIMITS:
        max_allowed = DECORATION_BUDGET_LIMITS[decoration_budget]
        if marker_count > max_allowed:
            results.append(
                {
                    "id": "HTML-07",
                    "status": "FAIL",
                    "msg": f"装饰节点 {marker_count} 个，超过 decoration_budget={decoration_budget} 的上限 {max_allowed}",
                }
            )
        else:
            results.append(
                {
                    "id": "HTML-07",
                    "status": "PASS",
                    "msg": f"装饰节点 {marker_count} / 上限 {max_allowed}（budget={decoration_budget}）",
                }
            )

    invalid_decoration_tags = []
    for match in re.finditer(r"<[^>]*data-decoration-layer\s*=\s*(['\"])(background|floating|page-accent)\1[^>]*>", text, flags=re.IGNORECASE):
        tag = match.group(0)
        if not re.search(r"aria-hidden\s*=\s*(['\"])true\1", tag, flags=re.IGNORECASE):
            invalid_decoration_tags.append(tag)
    if invalid_decoration_tags:
        results.append(
            {
                "id": "HTML-08",
                "status": "FAIL",
                "msg": f"检测到 {len(invalid_decoration_tags)} 个装饰节点缺少 aria-hidden=\"true\"",
            }
        )
    elif marker_count:
        results.append({"id": "HTML-08", "status": "PASS", "msg": f"全部 {marker_count} 个装饰节点已标记 aria-hidden=\"true\""})

    return results


# ─────────────────── 视觉一致性检查（diagram-consistency-system） ───────────────────
# 这些检查都是 WARN 级（绝不 FAIL），不会阻塞良好页面的 FINALIZE。
# 阈值是命名常量、fixture 校准，留待后续微调。

TREND_COLORS = {"#22c55e", "#ef4444"}
# 结构性常量：#fff / #ffffff 在任何调色板下都是同一个「白」——白色文字、白卡底、
# 白图标填充都用它，与主题无关，不需要绑定 CSS 变量。默认从硬编码色检测中豁免。
STRUCTURAL_HEX = {"#fff", "#ffffff"}
# 硬编码色检测统一豁免集合（趋势色 + 结构性白）
IGNORED_HEX = TREND_COLORS | STRUCTURAL_HEX
# 8-digit before 6 before 3 so #rrggbbaa isn't truncated to a 6-digit match
_HEX_RE = re.compile(r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")
_RGB_RE = re.compile(r"\brgba?\(", re.IGNORECASE)
_ROOT_RE = re.compile(r":root\s*\{(.*?)\}", re.DOTALL)
_FONT_SIZE_RE = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", re.IGNORECASE)
_RADIUS_RE = re.compile(r"border-radius\s*:\s*(\d+(?:\.\d+)?)px", re.IGNORECASE)
_SPACING_RE = re.compile(r"(?:gap|margin|padding)\s*:\s*(\d+(?:\.\d+)?)px", re.IGNORECASE)

# 阈值常量
PAL_OFFPALETTE_WARN = 0.15      # 离色像素占比 > 15% → WARN
PAL_COLOR_DIST = 60             # RGB 距离 > 此值视为离色
RAD_MAX_DISTINCT = 3            # 不同圆角值 > 3 种 → WARN
ALIGN_OFFGRID_WARN = 0.40       # 不在 4px 栅格上的间距占比 > 40% → WARN


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def parse_root_palette(html_text: str) -> list[tuple[int, int, int]]:
    """从 HTML 的 :root 提取调色板（hex 颜色变量值）。"""
    palette: list[tuple[int, int, int]] = []
    for block in _ROOT_RE.findall(html_text):
        for hx in _HEX_RE.findall(block):
            try:
                palette.append(_hex_to_rgb(hx))
            except ValueError:
                pass
    return palette


def _strip_root(html_text: str) -> str:
    return _ROOT_RE.sub("", html_text)


def check_hardcoded_colors(html_text: str) -> dict:
    """HEX-01：HTML 正文（:root 之外）的硬编码颜色 = 脱离主题。"""
    body = _strip_root(html_text)
    hits = [h for h in _HEX_RE.findall(body) if h.lower() not in IGNORED_HEX]
    rgb_hits = len(re.findall(r"\brgba?\(", body, re.IGNORECASE))
    total = len(hits) + rgb_hits
    if total > 0:
        sample = ", ".join(sorted(set(hits))[:4]) or "rgb()"
        return {"id": "HEX-01", "status": "WARN",
                "msg": f"检测到 {total} 处硬编码颜色（{sample}…），建议改用 CSS 变量绑定主题"}
    return {"id": "HEX-01", "status": "PASS", "msg": "正文未见硬编码颜色（趋势色/结构性白除外）"}


def check_type_scale(html_text: str) -> dict:
    """TYPE-01：是否存在可辨识的字号层级。"""
    sizes = sorted({float(s) for s in _FONT_SIZE_RE.findall(html_text)})
    if len(sizes) < 2:
        return {"id": "TYPE-01", "status": "WARN",
                "msg": f"仅 {len(sizes)} 种字号，缺乏字号层级（标题/正文/标注应拉开）"}
    ratio = sizes[-1] / sizes[0] if sizes[0] else 0
    return {"id": "TYPE-01", "status": "PASS",
            "msg": f"字号层级 {len(sizes)} 级，最大/最小 = {ratio:.1f}×"}


def check_corner_radius(html_text: str) -> dict:
    """RAD-01：圆角值是否过于杂乱（呼应既有 P2-1）。"""
    radii = {float(r) for r in _RADIUS_RE.findall(html_text)}
    if len(radii) > RAD_MAX_DISTINCT:
        return {"id": "RAD-01", "status": "WARN",
                "msg": f"{len(radii)} 种不同圆角 {sorted(radii)}，建议统一为 var(--card-radius)（参见 P2-1）"}
    return {"id": "RAD-01", "status": "PASS", "msg": f"圆角值 {sorted(radii) or '—'} 一致"}


def check_alignment_rhythm(html_text: str) -> dict:
    """ALIGN-01：间距是否落在 4px 栅格上（间距韵律）。"""
    vals = [float(v) for v in _SPACING_RE.findall(html_text)]
    if not vals:
        return {"id": "ALIGN-01", "status": "PASS", "msg": "未检测到显式间距"}
    off = [v for v in vals if v % 4 != 0]
    ratio = len(off) / len(vals)
    if ratio > ALIGN_OFFGRID_WARN:
        return {"id": "ALIGN-01", "status": "WARN",
                "msg": f"{ratio:.0%} 的间距不在 4px 栅格上（如 {sorted(set(off))[:5]}），节奏零碎"}
    return {"id": "ALIGN-01", "status": "PASS", "msg": f"间距基本落在 4px 栅格（off={ratio:.0%}）"}


def _card_region(html_text: str, card_id: str) -> str:
    """取某张卡片 data-card-id 起、到下一张 data-card-id（或文末）的 HTML 片段。"""
    anchors = [f'data-card-id="{card_id}"', f"data-card-id='{card_id}'"]
    start = -1
    for a in anchors:
        start = html_text.find(a)
        if start != -1:
            break
    if start == -1:
        return ""
    nxt = re.search(r"data-card-id\s*=", html_text[start + 20:])
    end = (start + 20 + nxt.start()) if nxt else len(html_text)
    return html_text[start:end]


def check_diagram_theme_binding(html_text: str, planning_path: Path | None) -> dict | None:
    """DTHEME-01：diagram 卡自身区域内是否有硬编码颜色（未绑定主题）。"""
    page = load_planning_page(planning_path) if planning_path else None
    if not isinstance(page, dict):
        return None
    diagram_ids = [
        str(c.get("card_id")).strip()
        for c in page.get("cards", [])
        if isinstance(c, dict) and str(c.get("card_type", "")).strip() == "diagram" and c.get("card_id")
    ]
    if not diagram_ids:
        return None
    offenders: list[str] = []
    scanned = 0
    for cid in diagram_ids:
        region = _card_region(html_text, cid)
        if not region:
            continue
        scanned += 1
        hard = [h for h in _HEX_RE.findall(region) if h.lower() not in IGNORED_HEX]
        if hard or _RGB_RE.search(region):
            offenders.append(cid)
    if not scanned:
        return {"id": "DTHEME-01", "status": "WARN",
                "msg": f"planning 有 diagram 卡 {diagram_ids} 但 HTML 中找不到对应 data-card-id 区域"}
    if offenders:
        return {"id": "DTHEME-01", "status": "WARN",
                "msg": f"diagram 卡 {offenders} 区域内含硬编码颜色，未绑定主题契约变量"}
    return {"id": "DTHEME-01", "status": "PASS", "msg": f"{scanned} 张 diagram 卡均绑定主题变量"}


def check_palette_adherence(img: Image.Image, palette: list[tuple[int, int, int]]) -> dict:
    """PAL-01：离色像素占比（相对 :root 调色板）。无调色板来源则 WARN 提示。"""
    if not palette:
        return {"id": "PAL-01", "status": "WARN", "msg": "无法从 :root 读取调色板，跳过离色检测"}
    small = img.resize((96, 54), Image.LANCZOS)
    pixels = list(small.getdata())
    off = 0
    counted = 0
    for p in pixels:
        r, g, b = p[:3]
        bright = (r + g + b) / 3
        if bright < 24 or bright > 232:  # 跳过近黑/近白中性
            continue
        counted += 1
        nearest = min((abs(r - cr) + abs(g - cg) + abs(b - cb)) for cr, cg, cb in palette)
        if nearest > PAL_COLOR_DIST:
            off += 1
    if counted == 0:
        return {"id": "PAL-01", "status": "PASS", "msg": "页面以中性色为主，无离色"}
    ratio = off / counted
    if ratio > PAL_OFFPALETTE_WARN:
        return {"id": "PAL-01", "status": "WARN",
                "msg": f"{ratio:.0%} 的着色像素偏离 :root 调色板，疑似脱离主题"}
    return {"id": "PAL-01", "status": "PASS", "msg": f"着色像素 {1 - ratio:.0%} 贴合调色板"}


# ─────────────────── 全 deck 跨页一致性聚合（DECK-*） ───────────────────
# 仅在批量模式（多页）运行，输出 deck 级别裁定。阈值为 fixture 校准的暂定常量。

DECK_PAL_JACCARD = 0.5     # 调色板 Jaccard 相似度 < 0.5 → 与 deck 主调不一致
DECK_BG_DIST = 48          # 主背景色与 deck 众数 RGB 距离 > 48 → 背景漂移
DECK_TYPE_DELTA = 2        # 顶部字号集合与 deck 众数相差 > 2 → 字号阶梯漂移


def deck_signal(png: Path, html_path: Path | None) -> dict:
    """采集单页的 deck 级信号：主背景色 + 调色板 + 顶部字号集合。"""
    sig: dict = {"name": png.name, "bg": None, "palette": frozenset(), "sizes": frozenset()}
    try:
        img = Image.open(png).convert("RGB")
        small = img.resize((64, 36), Image.LANCZOS)
        counts: dict[tuple, int] = {}
        for p in small.getdata():
            q = (p[0] // 16 * 16, p[1] // 16 * 16, p[2] // 16 * 16)
            counts[q] = counts.get(q, 0) + 1
        sig["bg"] = max(counts, key=counts.get)
    except Exception:
        pass
    if html_path and Path(html_path).exists():
        text = Path(html_path).read_text(encoding="utf-8")
        sig["palette"] = frozenset(h.lower() for h in _HEX_RE.findall("".join(_ROOT_RE.findall(text))))
        sizes = sorted({float(s) for s in _FONT_SIZE_RE.findall(text)}, reverse=True)
        sig["sizes"] = frozenset(sizes[:4])
    return sig


def _mode(items: list):
    """返回出现最频繁的元素（众数）。"""
    freq: dict = {}
    for it in items:
        freq[it] = freq.get(it, 0) + 1
    return max(freq, key=freq.get) if freq else None


def check_deck_consistency(signals: list[dict]) -> list[dict]:
    """跨页一致性聚合。返回 DECK-* 结果列表（含每个漂移页 + 总裁定）。"""
    results: list[dict] = []
    if len(signals) < 2:
        return results

    # DECK-PAL-01：调色板一致性（同一 style.json 应产生相同 :root）
    palettes = [s["palette"] for s in signals if s["palette"]]
    if palettes:
        modal = _mode(palettes)
        drift = []
        for s in signals:
            if not s["palette"]:
                continue
            inter = len(s["palette"] & modal)
            union = len(s["palette"] | modal) or 1
            if inter / union < DECK_PAL_JACCARD:
                drift.append(s["name"])
        results.append({"id": "DECK-PAL-01",
                        "status": "WARN" if drift else "PASS",
                        "msg": f"调色板漂移页: {drift}" if drift else f"全 {len(palettes)} 页调色板一致"})

    # DECK-BG-01：主背景色一致性
    bgs = [s["bg"] for s in signals if s["bg"]]
    if bgs:
        modal_bg = _mode(bgs)
        drift = [s["name"] for s in signals if s["bg"] and
                 sum(abs(a - b) for a, b in zip(s["bg"], modal_bg)) > DECK_BG_DIST]
        results.append({"id": "DECK-BG-01",
                        "status": "WARN" if drift else "PASS",
                        "msg": f"背景色漂移页: {drift}（deck 众数 RGB{modal_bg}）" if drift
                               else f"全 deck 主背景色一致 RGB{modal_bg}"})

    # DECK-TYPE-01：字号阶梯一致性
    sizesets = [s["sizes"] for s in signals if s["sizes"]]
    if sizesets:
        modal_sizes = _mode(sizesets)
        drift = [s["name"] for s in signals if s["sizes"] and
                 len(s["sizes"] ^ modal_sizes) > DECK_TYPE_DELTA]
        results.append({"id": "DECK-TYPE-01",
                        "status": "WARN" if drift else "PASS",
                        "msg": f"字号阶梯漂移页: {drift}" if drift else "全 deck 字号阶梯一致"})
    return results


# ─────────────────────── 主逻辑 ───────────────────────

def run_checks(
    png_path: Path,
    planning_path: Path | None = None,
    html_path: Path | None = None,
    style_bg: tuple | None = None,
) -> list[dict]:
    """对单张 PNG 运行全部检测。

    style_bg：style.json 声明的背景色 (r,g,b)，供 BLANK-01 / CUT-01 排除
    设计意图内的浅底/深底背景，避免在浅色 deck 上误报。
    """
    results = []

    # 文件级检查
    results.append(check_file_size(png_path))

    # 打开图片
    try:
        img = Image.open(png_path).convert("RGB")
    except Exception as e:
        results.append({"id": "OPEN-01", "status": "FAIL", "msg": f"无法打开 PNG: {e}"})
        return results

    # 像素级检查
    results.append(check_dimensions(img))
    results.append(check_blank_ratio(img, bg_rgb=style_bg))
    results.append(check_vertical_text(img))
    results.append(check_overflow_cutoff(img, bg_rgb=style_bg))
    results.append(check_contrast_zones(img))

    # planning 对照检查
    if planning_path:
        results.append(check_planning_cards_coverage(img, planning_path))
        results.extend(check_density_contract_budget(planning_path))

    if html_path:
        results.extend(check_html_contracts(html_path, planning_path))

    # 视觉一致性检查（WARN 级；HTML 可用时基于 HTML，调色板取自 :root）
    if html_path and Path(html_path).exists():
        html_text = Path(html_path).read_text(encoding="utf-8")
        results.append(check_palette_adherence(img, parse_root_palette(html_text)))
        results.append(check_hardcoded_colors(html_text))
        results.append(check_type_scale(html_text))
        results.append(check_corner_radius(html_text))
        results.append(check_alignment_rhythm(html_text))
        dtheme = check_diagram_theme_binding(html_text, planning_path)
        if dtheme is not None:
            results.append(dtheme)

    return results


def print_report(png_name: str, results: list[dict]) -> tuple[int, int]:
    """打印检测报告，返回 (fail_count, warn_count)。"""
    fails = sum(1 for r in results if r["status"] == "FAIL")
    warns = sum(1 for r in results if r["status"] == "WARN")

    print(f"\n{'─' * 60}")
    print(f"  {png_name}")
    print(f"{'─' * 60}")

    for r in results:
        icon = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}[r["status"]]
        print(f"  [{icon}] {r['id']}: {r['msg']}")

    verdict = "PASS" if fails == 0 and warns == 0 else ("FAIL" if fails > 0 else "WARN")
    print(f"\n  verdict: {verdict}  (FAIL={fails}, WARN={warns})")
    return fails, warns


def build_report_lines(png_name: str, results: list[dict]) -> tuple[list[str], int, int]:
    """构造文本报告，同时返回 (fail_count, warn_count)。"""
    fails = sum(1 for r in results if r["status"] == "FAIL")
    warns = sum(1 for r in results if r["status"] == "WARN")
    verdict = "PASS" if fails == 0 and warns == 0 else ("FAIL" if fails > 0 else "WARN")

    lines = [
        "",
        f"{'─' * 60}",
        f"  {png_name}",
        f"{'─' * 60}",
    ]
    for r in results:
        icon = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}[r["status"]]
        lines.append(f"  [{icon}] {r['id']}: {r['msg']}")
    lines.append(f"\n  verdict: {verdict}  (FAIL={fails}, WARN={warns})")
    return lines, fails, warns


def write_text_report(path: Path | None, text: str) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()

    # 解析可选参数
    planning_path = None
    planning_dir = None
    html_path = None
    html_dir = None
    output_path = None
    style_path = None
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--planning" and i + 1 < len(args):
            planning_path = Path(args[i + 1]).resolve()
            i += 2
        elif args[i] == "--planning-dir" and i + 1 < len(args):
            planning_dir = Path(args[i + 1]).resolve()
            i += 2
        elif args[i] == "--html" and i + 1 < len(args):
            html_path = Path(args[i + 1]).resolve()
            i += 2
        elif args[i] == "--html-dir" and i + 1 < len(args):
            html_dir = Path(args[i + 1]).resolve()
            i += 2
        elif args[i] == "--style" and i + 1 < len(args):
            style_path = Path(args[i + 1]).resolve()
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_path = Path(args[i + 1]).resolve()
            i += 2
        else:
            i += 1

    # style.json 声明背景色（供 BLANK-01 / CUT-01 排除浅底/深底假阳）
    style_bg = load_style_bg(style_path)
    # style.json 声明调色板（供 deck 级 CONTRAST-01/02 真实 WCAG 对比度）
    style_palette = load_style_palette(style_path)

    # 收集要检查的 PNG（同时接受 slide-N.png 与 slide_NN.png 两种命名，
    # 兼容 html2png.py 沿用输入 HTML 文件名产出的 slide_NN.png）
    if target.is_file():
        pngs = [target]
    elif target.is_dir():
        found = {p.resolve() for p in target.glob("slide-*.png")}
        found |= {p.resolve() for p in target.glob("slide_*.png")}
        pngs = sorted(found, key=lambda p: (_slide_number(p.stem) or 0, p.name))
    else:
        print(f"ERROR: {target} 不存在", file=sys.stderr)
        sys.exit(1)

    if not pngs:
        print(f"ERROR: 未找到 slide-*.png / slide_*.png 文件于 {target}", file=sys.stderr)
        sys.exit(1)

    total_fails = 0
    total_warns = 0
    report_lines: list[str] = []
    deck_signals: list[dict] = []

    for png in pngs:
        # 自动推断 planning / html 路径（页码接受 slide-N 与 slide_NN 两种分隔符）
        pp = planning_path
        hh = html_path
        n = _slide_number(png.stem)
        if pp is None and planning_dir and n is not None:
            # slide-3.png / slide_03.png -> planning3.json（去零填充）
            pp = planning_dir / f"planning{n}.json"
        if hh is None and html_dir and n is not None:
            # 依次尝试 slide-N.html、slide_N.html、原始零填充 slide_NN.html
            for cand in (f"slide-{n}.html", f"slide_{n}.html", f"{png.stem}.html"):
                if (html_dir / cand).exists():
                    hh = html_dir / cand
                    break
            if hh is None:
                hh = html_dir / f"slide-{n}.html"

        results = run_checks(png, pp, hh, style_bg=style_bg)
        lines, f, w = build_report_lines(png.name, results)
        report_lines.extend(lines)
        print("\n".join(lines))
        total_fails += f
        total_warns += w
        deck_signals.append(deck_signal(png, hh))

    # deck 级：声明调色板的真实 WCAG 文本对比度（可读性下限，纯色彩数学、无外部依赖）
    if style_palette:
        contrast_results = check_text_contrast(style_palette)
        if contrast_results:
            clines, cf, cw = build_report_lines("DECK · 文本对比度（WCAG 1.4.3）", contrast_results)
            report_lines.extend(clines)
            print("\n".join(clines))
            total_fails += cf
            total_warns += cw

    # 全 deck 跨页一致性聚合（仅多页时）
    if len(pngs) > 1:
        deck_results = check_deck_consistency(deck_signals)
        if deck_results:
            dlines, df, dw = build_report_lines("DECK · 跨页一致性聚合", deck_results)
            report_lines.extend(dlines)
            print("\n".join(dlines))
            total_fails += df
            total_warns += dw

    summary_lines = [
        f"\n{'=' * 60}",
        f"  TOTAL: {len(pngs)} pages, FAIL={total_fails}, WARN={total_warns}",
    ]
    if total_fails > 0:
        summary_lines.append("  EXIT 1 — 存在致命缺陷，建议重跑对应页面")
    elif total_warns > 0:
        summary_lines.append("  EXIT 2 — 存在品质警告，建议人工复查")
    else:
        summary_lines.append("  EXIT 0 — 全部通过")
    summary_lines.append(f"{'=' * 60}")
    print("\n".join(summary_lines))

    write_text_report(output_path, "\n".join(report_lines + summary_lines) + "\n")

    sys.exit(1 if total_fails > 0 else (2 if total_warns > 0 else 0))


if __name__ == "__main__":
    main()
