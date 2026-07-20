#!/usr/bin/env python3
"""mermaid_render.svg — HTML -> true-vector SVG via Playwright + dom-to-svg.

Text is preserved as editable <text> elements (not paths).
"""

import base64
import sys
import tempfile
from pathlib import Path

from .browser import _setup_page, _within_deck_root, get_browser

BUNDLE_PATH = Path(__file__).resolve().parent / "vendor" / "dom-to-svg.bundle.js"

# Verbatim in-page JS: materialise CSS features dom-to-svg can't read (steps 1–6).
_PREPROCESS_JS = r"""() => {
    // 1. Materialise ::before / ::after pseudo-elements as real <span> elements
    const all = document.querySelectorAll('*');
    for (const el of all) {
        for (const pseudo of ['::before', '::after']) {
            const style = getComputedStyle(el, pseudo);
            const content = style.content;
            if (!content || content === 'none' || content === '""' || content === "''") continue;

            const w = parseFloat(style.width) || 0;
            const h = parseFloat(style.height) || 0;
            const bg = style.backgroundColor;
            const border = style.borderTopWidth;
            const borderColor = style.borderTopColor;

            if ((w > 0 || h > 0 || parseFloat(border) > 0) && content !== 'normal') {
                const span = document.createElement('span');
                span.style.display = style.display === 'none' ? 'none' : 'inline-block';
                span.style.position = style.position;
                span.style.width = style.width;
                span.style.height = style.height;
                span.style.backgroundColor = bg;
                span.style.borderTop = style.borderTop;
                span.style.borderRight = style.borderRight;
                span.style.borderBottom = style.borderBottom;
                span.style.borderLeft = style.borderLeft;
                span.style.transform = style.transform;
                span.style.top = style.top;
                span.style.left = style.left;
                span.style.right = style.right;
                span.style.bottom = style.bottom;
                span.style.borderRadius = style.borderRadius;
                span.setAttribute('data-pseudo', pseudo);

                const textContent = content.replace(/^["']|["']$/g, '');
                if (textContent && textContent !== 'normal' && textContent !== 'none') {
                    span.textContent = textContent;
                    span.style.color = style.color;
                    span.style.fontSize = style.fontSize;
                    span.style.fontWeight = style.fontWeight;
                }

                if (pseudo === '::before') {
                    el.insertBefore(span, el.firstChild);
                } else {
                    el.appendChild(span);
                }
            }
        }
    }

    // 2. Replace conic-gradient ring charts with inline SVG
    for (const el of document.querySelectorAll('*')) {
        const bg = el.style.background || el.style.backgroundImage || '';
        const computed = getComputedStyle(el);
        const bgImage = computed.backgroundImage || '';

        if (!bgImage.includes('conic-gradient')) continue;

        const rect = el.getBoundingClientRect();
        const size = Math.min(rect.width, rect.height);
        if (size <= 0) continue;

        const match = bgImage.match(/conic-gradient\(([^)]+)\)/);
        if (!match) continue;

        const gradStr = match[1];
        const percMatch = gradStr.match(/([\d.]+)%/g);
        let percentage = 75;
        if (percMatch && percMatch.length >= 2) {
            percentage = parseFloat(percMatch[1]);
        }

        const colorMatch = gradStr.match(/(#[0-9a-fA-F]{3,8}|rgb[a]?\([^)]+\))/g);
        const mainColor = colorMatch ? colorMatch[0] : '#4CAF50';
        const bgColor = colorMatch && colorMatch.length > 1 ? colorMatch[1] : '#e0e0e0';

        const svgNS = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(svgNS, 'svg');
        svg.setAttribute('width', String(size));
        svg.setAttribute('height', String(size));
        svg.setAttribute('viewBox', `0 0 ${size} ${size}`);
        svg.style.display = el.style.display || 'block';
        svg.style.position = computed.position;
        svg.style.top = computed.top;
        svg.style.left = computed.left;

        const cx = size / 2, cy = size / 2;
        const r = size * 0.4;
        const circumference = 2 * Math.PI * r;
        const strokeWidth = size * 0.15;

        const bgCircle = document.createElementNS(svgNS, 'circle');
        bgCircle.setAttribute('cx', String(cx));
        bgCircle.setAttribute('cy', String(cy));
        bgCircle.setAttribute('r', String(r));
        bgCircle.setAttribute('fill', 'none');
        bgCircle.setAttribute('stroke', bgColor);
        bgCircle.setAttribute('stroke-width', String(strokeWidth));

        const fgCircle = document.createElementNS(svgNS, 'circle');
        fgCircle.setAttribute('cx', String(cx));
        fgCircle.setAttribute('cy', String(cy));
        fgCircle.setAttribute('r', String(r));
        fgCircle.setAttribute('fill', 'none');
        fgCircle.setAttribute('stroke', mainColor);
        fgCircle.setAttribute('stroke-width', String(strokeWidth));
        fgCircle.setAttribute('stroke-dasharray', `${circumference * percentage / 100} ${circumference}`);
        fgCircle.setAttribute('stroke-linecap', 'round');
        fgCircle.setAttribute('transform', `rotate(-90 ${cx} ${cy})`);

        svg.appendChild(bgCircle);
        svg.appendChild(fgCircle);

        if (el.textContent && el.textContent.trim()) {
            const svgText = document.createElementNS(svgNS, 'text');
            svgText.setAttribute('x', String(cx));
            svgText.setAttribute('y', String(cy));
            svgText.setAttribute('text-anchor', 'middle');
            svgText.setAttribute('dominant-baseline', 'central');
            svgText.setAttribute('fill', computed.color);
            svgText.setAttribute('font-size', computed.fontSize);
            svgText.setAttribute('font-weight', computed.fontWeight);
            svgText.textContent = el.textContent.trim();
            svg.appendChild(svgText);
        }

        el.style.background = 'none';
        el.style.backgroundImage = 'none';
        el.insertBefore(svg, el.firstChild);
    }

    // 3. Fix CSS border-triangle arrows
    for (const el of document.querySelectorAll('*')) {
        const cs = getComputedStyle(el);
        const w = parseFloat(cs.width);
        const h = parseFloat(cs.height);
        if (w !== 0 || h !== 0) continue;

        const bt = parseFloat(cs.borderTopWidth) || 0;
        const br = parseFloat(cs.borderRightWidth) || 0;
        const bb = parseFloat(cs.borderBottomWidth) || 0;
        const bl = parseFloat(cs.borderLeftWidth) || 0;

        const borders = [bt, br, bb, bl].filter(v => v > 0);
        if (borders.length < 2) continue;

        const btc = cs.borderTopColor;
        const brc = cs.borderRightColor;
        const bbc = cs.borderBottomColor;
        const blc = cs.borderLeftColor;

        const nonTransparent = [];
        if (bt > 0 && !btc.includes('0)') && btc !== 'transparent') nonTransparent.push({dir: 'top', size: bt, color: btc});
        if (br > 0 && !brc.includes('0)') && brc !== 'transparent') nonTransparent.push({dir: 'right', size: br, color: brc});
        if (bb > 0 && !bbc.includes('0)') && bbc !== 'transparent') nonTransparent.push({dir: 'bottom', size: bb, color: bbc});
        if (bl > 0 && !blc.includes('0)') && blc !== 'transparent') nonTransparent.push({dir: 'left', size: bl, color: blc});

        if (nonTransparent.length !== 1) continue;

        const arrow = nonTransparent[0];
        const totalW = bl + br;
        const totalH = bt + bb;
        el.style.width = totalW + 'px';
        el.style.height = totalH + 'px';
        el.style.border = 'none';

        const svgNS = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(svgNS, 'svg');
        svg.setAttribute('width', String(totalW));
        svg.setAttribute('height', String(totalH));
        svg.style.display = 'block';
        svg.style.overflow = 'visible';

        const polygon = document.createElementNS(svgNS, 'polygon');
        let points = '';
        if (arrow.dir === 'bottom') points = `0,0 ${totalW},0 ${totalW/2},${totalH}`;
        else if (arrow.dir === 'top') points = `${totalW/2},0 0,${totalH} ${totalW},${totalH}`;
        else if (arrow.dir === 'right') points = `0,0 ${totalW},${totalH/2} 0,${totalH}`;
        else if (arrow.dir === 'left') points = `${totalW},0 0,${totalH/2} ${totalW},${totalH}`;
        polygon.setAttribute('points', points);
        polygon.setAttribute('fill', arrow.color);
        svg.appendChild(polygon);
        el.appendChild(svg);
    }

    // 4. Fix background-clip: text gradient text
    for (const el of document.querySelectorAll('*')) {
        const cs = getComputedStyle(el);
        const bgClip = cs.webkitBackgroundClip || cs.backgroundClip || '';
        if (bgClip !== 'text') continue;

        const bgImage = cs.backgroundImage || '';
        let mainColor = '#FF6900';
        const colorMatch = bgImage.match(/(#[0-9a-fA-F]{3,8}|rgb[a]?\([^)]+\))/);
        if (colorMatch) mainColor = colorMatch[1];

        el.style.backgroundImage = 'none';
        el.style.background = 'none';
        el.style.webkitBackgroundClip = 'border-box';
        el.style.backgroundClip = 'border-box';
        el.style.webkitTextFillColor = 'unset';
        el.style.color = mainColor;
        console.warn('html2svg fallback: background-clip:text -> color:' + mainColor, el.tagName);
    }

    // 5. Fix -webkit-text-fill-color
    for (const el of document.querySelectorAll('*')) {
        const cs = getComputedStyle(el);
        const fillColor = cs.webkitTextFillColor;
        if (!fillColor || fillColor === cs.color) continue;
        if (fillColor !== 'rgba(0, 0, 0, 0)' && fillColor !== 'transparent') {
            el.style.color = fillColor;
            el.style.webkitTextFillColor = 'unset';
        }
    }

    // 6. Fix mask-image / -webkit-mask-image
    for (const el of document.querySelectorAll('*')) {
        const cs = getComputedStyle(el);
        const maskImg = cs.maskImage || cs.webkitMaskImage || '';
        if (!maskImg || maskImg === 'none') continue;

        el.style.maskImage = 'none';
        el.style.webkitMaskImage = 'none';

        const zIndex = parseInt(cs.zIndex) || 0;
        const pointerEvents = cs.pointerEvents;
        const isImg = el.tagName === 'IMG';
        const currentOpacity = parseFloat(cs.opacity) || 1;

        if (isImg || pointerEvents === 'none' || zIndex <= 0) {
            const newOpacity = Math.min(currentOpacity, 0.15);
            el.style.opacity = String(newOpacity);
            if (isImg) {
                const parent = el.parentElement;
                if (parent) {
                    const parentRect = parent.getBoundingClientRect();
                    const elRect = el.getBoundingClientRect();
                    if (elRect.width > parentRect.width * 0.8) {
                        el.style.maxWidth = '60%';
                        el.style.maxHeight = '60%';
                    }
                }
            }
            console.warn('html2svg fallback: mask-image -> opacity:' + newOpacity + ' (background layer)', el.tagName);
        } else {
            console.warn('html2svg fallback: mask-image removed (foreground)', el.tagName);
        }
    }
}"""

# Verbatim in-page JS: DOM→SVG conversion (dom-to-svg must be injected first).
_DOM_TO_SVG_JS = r"""async () => {
    const { documentToSVG, inlineResources } = window.__domToSvg;
    const svgDoc = documentToSVG(document);
    await inlineResources(svgDoc.documentElement);

    // Post-process: translate <text> color attribute to fill (SVG standard)
    const texts = svgDoc.querySelectorAll('text');
    for (const t of texts) {
        const c = t.getAttribute('color');
        if (c && !t.getAttribute('fill')) {
            t.setAttribute('fill', c);
            t.removeAttribute('color');
        }
    }

    return new XMLSerializer().serializeToString(svgDoc);
}"""


def _inline_images(page, html_file: Path, deck_root: Path) -> None:
    """Read img srcs from the page, base64-encode in Python, patch back into the DOM.

    Confinement: images outside deck_root are skipped with a warning (LLM05/CWE-22).
    """
    img_srcs = page.evaluate(
        "() => Array.from(document.querySelectorAll('img')).map(img => img.getAttribute('src') || '')"
    )
    img_data_map = {}
    html_dir = html_file.parent

    for src in img_srcs:
        if not src or src.startswith("data:"):
            continue
        file_path = src
        if file_path.startswith("file://"):
            file_path = file_path[7:]
        if not Path(file_path).is_absolute():
            file_path = str(html_dir / file_path)
        resolved = Path(file_path).resolve()
        if not _within_deck_root(resolved, deck_root):
            print(f"Skipping image outside deck directory: {resolved}", file=sys.stderr)
            continue
        if resolved.exists():
            ext = resolved.suffix.lstrip(".") or "png"
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
            data = base64.b64encode(resolved.read_bytes()).decode()
            img_data_map[src] = f"data:{mime};base64,{data}"
        else:
            print(f"Image not found: {resolved} (src: {src})", file=sys.stderr)

    if img_data_map:
        page.evaluate(
            """(dataMap) => {
                const imgs = document.querySelectorAll('img');
                for (const img of imgs) {
                    const origSrc = img.getAttribute('src');
                    if (origSrc && dataMap[origSrc]) {
                        img.src = dataMap[origSrc];
                    }
                }
            }""",
            img_data_map,
        )
        page.wait_for_timeout(300)


def _render_page_to_svg(page, html_file: Path) -> str:
    deck_root = html_file.parent.parent
    page.goto("file://" + str(html_file), wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(500)
    _inline_images(page, html_file, deck_root)
    page.add_script_tag(path=str(BUNDLE_PATH))
    page.evaluate(_PREPROCESS_JS)
    page.wait_for_timeout(300)
    return page.evaluate(_DOM_TO_SVG_JS)


def convert(html_dir: Path, output_dir: Path) -> bool:
    """Main conversion entry point."""
    if html_dir.is_file():
        html_files = [html_dir]
    else:
        html_files = sorted(html_dir.glob("*.html"))

    if not html_files:
        print(f"No HTML files in {html_dir}", file=sys.stderr)
        return False

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with get_browser() as browser:
            print(f"Converting {len(html_files)} HTML files (dom-to-svg, text editable)...")
            ok = 0
            for html_file in html_files:
                page = browser.new_page()
                _setup_page(page)
                try:
                    svg_string = _render_page_to_svg(page, html_file)
                    out_path = output_dir / (html_file.stem + ".svg")
                    out_path.write_text(svg_string, encoding="utf-8")
                    print(f"SVG: {html_file.name}")
                    text_count = svg_string.count("<text ")
                    print(f"  Text elements: {text_count} (editable in PPT)")
                    ok += 1
                except Exception as e:
                    print(f"[ERROR] html2svg: {html_file.name}: {e}", file=sys.stderr)
                finally:
                    try:
                        page.close()
                    except Exception:
                        pass

            print(f"\nDone! {ok}/{len(html_files)} SVGs -> {output_dir}")
            return ok > 0
    except RuntimeError as e:
        print(f"[SKIP] html2svg: {e}", file=sys.stderr)
        return False


def _to_svg_from_html_file(html_file: Path) -> str:
    """Convert a single HTML file on disk to an SVG string."""
    with get_browser() as browser:
        page = browser.new_page()
        _setup_page(page)
        try:
            return _render_page_to_svg(page, html_file)
        finally:
            try:
                page.close()
            except Exception:
                pass


def _to_svg_from_html_string(html: str) -> str:
    """Convert an HTML string to an SVG string via a temporary file."""
    with tempfile.TemporaryDirectory() as tmp:
        html_file = Path(tmp) / "diagram.html"
        html_file.write_text(html, encoding="utf-8")
        return _to_svg_from_html_file(html_file)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 html2svg.py <html_dir_or_file> [-o output_dir]")
        sys.exit(1)

    html_path = Path(sys.argv[1]).resolve()
    if "-o" in sys.argv:
        idx = sys.argv.index("-o")
        output_dir = Path(sys.argv[idx + 1]).resolve()
    else:
        output_dir = (html_path.parent if html_path.is_file() else html_path.parent) / "svg"

    success = convert(html_path, output_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
