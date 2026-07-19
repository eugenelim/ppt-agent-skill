"""CLI entry point: python3 scripts/mermaid_render/layout/ --source ... """
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Bootstrap: when invoked as `python3 scripts/mermaid_render/layout/` the package
# grandparent (scripts/) may not be on sys.path. Ensure it is so that
# `mermaid_render` is importable as a top-level package.
_scripts_dir = Path(__file__).parent.parent.parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from ._strategies import _dispatch  # noqa: E402 (relative — works when pkg is on path)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Render Mermaid source to pipeline-safe HTML/CSS fragment."
    )
    ap.add_argument(
        "--source", required=True,
        help="Mermaid source string, or @path to read from file (e.g. @diagram.mmd).",
    )
    ap.add_argument(
        "--direction", choices=["TB", "LR", "RL", "BT"], default=None,
        help="Override graph direction (default: from source directive).",
    )
    ap.add_argument(
        "--width-hint", type=int, default=0, metavar="N",
        help="Target canvas width hint in px; script scales to fit.",
    )
    ap.add_argument(
        "--output", default=None, metavar="FILE",
        help="Write HTML fragment to FILE (default: stdout).",
    )
    args = ap.parse_args()

    src_arg: str = args.source
    if src_arg.startswith("@"):
        fpath = Path(src_arg[1:])
        try:
            src = fpath.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"mermaid_layout: cannot read source file: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        src = src_arg.replace("\\n", "\n")

    try:
        fragment = _dispatch(src, args.direction, args.width_hint)
    except RecursionError:
        print("mermaid_layout: diagram too deeply nested (recursion limit)", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"mermaid_layout: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        Path(args.output).write_text(fragment, encoding="utf-8")
    else:
        print(fragment)


if __name__ == "__main__":
    main()
