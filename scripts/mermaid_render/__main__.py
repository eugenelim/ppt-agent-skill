#!/usr/bin/env python3
"""python3 -m mermaid_render <subcommand>"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_scripts_dir = Path(__file__).parent.parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))


def _read_source(source: str) -> str:
    if source.startswith("@"):
        try:
            return Path(source[1:]).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"mermaid_render: {exc}", file=sys.stderr)
            sys.exit(1)
    return source.replace("\\n", "\n")


def _write_text(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def _cmd_render(args: argparse.Namespace) -> int:
    from . import to_html
    src = _read_source(args.source)
    try:
        html = to_html(src, theme=args.theme)
    except Exception as exc:
        print(f"mermaid_render render: {exc}", file=sys.stderr)
        return 1
    _write_text(html, args.output)
    return 0


def _cmd_svg(args: argparse.Namespace) -> int:
    from . import to_svg
    src = _read_source(args.source)
    try:
        svg = to_svg(src, theme=args.theme, experimental=True)
    except Exception as exc:
        print(f"mermaid_render svg: {exc}", file=sys.stderr)
        return 1
    if args.output:
        Path(args.output).write_text(svg, encoding="utf-8")
    else:
        print(svg, end="")
    return 0


def _cmd_png(args: argparse.Namespace) -> int:
    from . import to_png
    src = _read_source(args.source)
    try:
        data = to_png(src, theme=args.theme, scale=args.scale, experimental=True)
    except Exception as exc:
        print(f"mermaid_render png: {exc}", file=sys.stderr)
        return 1
    if args.output:
        Path(args.output).write_bytes(data)
    else:
        sys.stdout.buffer.write(data)
    return 0


def _cmd_icons(args: argparse.Namespace) -> int:
    from ._icons_cli import run_icons
    return run_icons(args)


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="python3 -m mermaid_render",
        description="Mermaid diagram renderer.",
    )
    sub = ap.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    def _src(p):
        p.add_argument("--source", required=True, metavar="TEXT",
                       help="Mermaid source, or @file.mmd.")

    def _out(p):
        p.add_argument("--output", default=None, metavar="FILE")

    def _theme(p):
        p.add_argument("--theme", default=None, choices=["auto", "light", "dark"])

    p = sub.add_parser("render", help="Mermaid → themed HTML page (no browser)")
    _src(p); _theme(p); _out(p)
    p.set_defaults(func=_cmd_render)

    p = sub.add_parser("svg", help="Mermaid → SVG (requires Playwright)")
    _src(p); _theme(p); _out(p)
    p.set_defaults(func=_cmd_svg)

    p = sub.add_parser("png", help="Mermaid → PNG (requires Playwright)")
    _src(p); _theme(p); _out(p)
    p.add_argument("--scale", type=float, default=1.0, metavar="FLOAT")
    p.set_defaults(func=_cmd_png)

    p = sub.add_parser("icons", help="Icon library: search, validate, snippet")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--list", action="store_true")
    p.add_argument("--category", metavar="TEXT")
    p.add_argument("--snippet", action="store_true")
    p.add_argument("--json", action="store_true", dest="json_out")
    p.add_argument("--validate", action="store_true")
    p.set_defaults(func=_cmd_icons)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
