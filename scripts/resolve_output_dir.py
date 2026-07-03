#!/usr/bin/env python3
"""resolve_output_dir.py — atomically claim a per-deck OUTPUT_DIR.

Owns the *mechanical* half of the SKILL.md path-convention protocol: kebab-
normalize an already-English slug, then atomically claim `<root>/<slug>` (or the
first free `<slug>-N`, N up to 99) using a bare `os.mkdir` — which fails if the
directory already exists, so two concurrent runs under the same root can never
select the same directory. Prints the resolved absolute path on success.

Deliberately NOT owned here (stays an agent/prose judgment):
  - CJK -> English transliteration of the topic (needs the model).
  - Resume: reusing the existing deck dir whose artifacts match this run. Resume
    is a single-writer, agent-selected path; this script never guesses it.

Usage:
    resolve_output_dir.py --root ppt-output --slug "Dify Enterprise Intro"
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

MAX_SLUG_LEN = 40
MAX_SUFFIX = 99


def normalize_slug(raw: str) -> str:
    """kebab-case: lowercase, non-[a-z0-9] runs -> single '-', trim, <=40 chars."""
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    if len(slug) > MAX_SLUG_LEN:
        slug = slug[:MAX_SLUG_LEN].rstrip("-")
    return slug


def claim_output_dir(root: Path, slug: str) -> Path:
    """Atomically claim <root>/<slug> or first free <slug>-N. Raises on exhaustion."""
    root.mkdir(parents=True, exist_ok=True)
    candidates = [slug] + [f"{slug}-{n}" for n in range(2, MAX_SUFFIX + 1)]
    for name in candidates:
        target = root / name
        try:
            target.mkdir()  # bare mkdir: atomic claim, fails if it already exists
        except FileExistsError:
            continue
        return target.resolve()
    raise RuntimeError(
        f"could not claim an output dir for slug '{slug}' under {root} "
        f"(tried {slug} and {slug}-2..{slug}-{MAX_SUFFIX}); stop and ask for help"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Atomically claim a per-deck OUTPUT_DIR")
    parser.add_argument("--root", required=True, help="OUTPUT_ROOT (e.g. ppt-output)")
    parser.add_argument("--slug", required=True, help="already-English topic phrase")
    args = parser.parse_args()

    slug = normalize_slug(args.slug)
    if not slug:
        print(f"error: slug '{args.slug}' normalizes to empty; provide an English phrase",
              file=sys.stderr)
        return 1
    try:
        resolved = claim_output_dir(Path(args.root), slug)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(resolved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
