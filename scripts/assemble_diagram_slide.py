#!/usr/bin/env python3
"""assemble_diagram_slide.py — assemble a presentation-ready HTML slide from a diagram.

CLI:
    python3 scripts/assemble_diagram_slide.py \\
      [--fragment PATH]      # pre-rendered HTML/SVG fragment (mutually exclusive with --source)
      [--source PATH]        # .mmd source to render (mutually exclusive with --fragment)
      [--style PATH]         # style.json with css_variables dict (optional)
      [--title TEXT]         # title text above diagram (optional)
      [--annotation TEXT]    # annotation/caption text below diagram (optional)
      [--width INT]          # canvas width hint (default 1200)
      [--output PATH]        # output HTML file path (default: stdout)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html import escape as _h
from pathlib import Path

# Make scripts/ importable regardless of cwd
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from mermaid_render.layout._strategies import _dispatch  # noqa: E402
from mermaid_render.themes import render_page  # noqa: E402

_SLIDE_CSS = """
.slide-title {
    font-size: 1.75rem;
    font-weight: 700;
    margin: 0 0 1rem 0;
    color: var(--text-primary, #1A1916);
    font-family: var(--font-primary, -apple-system, Inter, sans-serif);
}
.slide-annotation {
    font-size: 0.95rem;
    color: var(--text-secondary, #6B6860);
    margin: 1rem 0 0 0;
    font-family: var(--font-primary, -apple-system, Inter, sans-serif);
}
"""


def _parse_viewbox(fragment: str) -> tuple[int, int]:
    """Extract (width, height) from the first SVG viewBox in fragment. Returns (0, 0) if not found."""
    m = re.search(r'viewBox=["\']([^"\']+)["\']', fragment)
    if not m:
        return 0, 0
    parts = m.group(1).split()
    if len(parts) < 4:
        return 0, 0
    try:
        return int(float(parts[2])), int(float(parts[3]))
    except (ValueError, IndexError):
        return 0, 0


def render_from_source(src: str, width_hint: int) -> str:
    """Render mermaid source string to an HTML/SVG fragment."""
    return _dispatch(src, None, width_hint)


def assemble_slide(
    fragment: str,
    *,
    style_path: str | None = None,
    title: str | None = None,
    annotation: str | None = None,
) -> str:
    """Assemble a full HTML slide from a fragment with optional style/title/annotation.

    Returns the full HTML string (without the leading dims comment).
    """
    # Determine theme from style.json or fall back to adaptive
    theme = None
    if style_path:
        with open(style_path, encoding="utf-8") as f:
            style_data = json.load(f)
        theme = style_data.get("css_variables", {}) or None

    # Build the composed fragment: optional CSS, title, diagram, annotation
    parts: list[str] = []
    if title or annotation:
        parts.append(f"<style>{_SLIDE_CSS}</style>")
    if title:
        parts.append(f'<h1 class="slide-title">{_h(title)}</h1>')
    parts.append(fragment)
    if annotation:
        parts.append(f'<p class="slide-annotation">{_h(annotation)}</p>')

    composed = "\n".join(parts)
    return render_page(composed, theme=theme)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Assemble a presentation-ready HTML slide from a mermaid diagram."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--fragment", metavar="PATH",
        help="Path to pre-rendered HTML/SVG fragment file (skip rendering)",
    )
    source_group.add_argument(
        "--source", metavar="PATH",
        help="Path to .mmd source file to render",
    )
    parser.add_argument("--style", metavar="PATH", help="Path to style.json")
    parser.add_argument("--title", metavar="TEXT", help="Optional title text")
    parser.add_argument("--annotation", metavar="TEXT", help="Optional annotation/caption text")
    parser.add_argument("--width", type=int, default=1200, metavar="INT", help="Canvas width hint (default 1200)")
    parser.add_argument("--output", metavar="PATH", help="Output path (default: stdout)")

    args = parser.parse_args(argv)

    # Load or render the fragment
    if args.fragment:
        fragment = Path(args.fragment).read_text(encoding="utf-8")
    else:
        src = Path(args.source).read_text(encoding="utf-8")
        fragment = render_from_source(src, args.width)

    # Parse dims from the raw fragment (before wrapping)
    w, h = _parse_viewbox(fragment)

    # Assemble the slide
    html = assemble_slide(
        fragment,
        style_path=args.style,
        title=args.title,
        annotation=args.annotation,
    )

    # Prepend dims comment
    output = f"<!-- dims: {w}x{h} -->\n{html}"

    # Write output
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()
