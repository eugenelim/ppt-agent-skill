#!/usr/bin/env python3
"""Icon library search / validate / snippet — used by python3 -m mermaid_render icons."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ICONS_DIR = Path(__file__).parent / "icons"
CATALOG = ICONS_DIR / "catalog.json"

# Pipeline-unsafe techniques an icon SVG must never contain. Wording tracks
# references/pipeline-compat.md and tools/lint_diagram_recipes.py's FORBIDDEN set.
FORBIDDEN = [
    ("SVG <text> (use HTML overlay, never SVG text)", re.compile(r"<text[\s/>]", re.I)),
    ("mask-image", re.compile(r"-?\bwebkit-?\s*-?mask-image|mask-image", re.I)),
    ("conic-gradient", re.compile(r"conic-gradient", re.I)),
    ("mix-blend-mode", re.compile(r"mix-blend-mode", re.I)),
    ("background-image:url()", re.compile(r"background-image\s*:\s*url", re.I)),
    ("background-clip:text", re.compile(r"background-clip\s*:\s*text", re.I)),
    ("filter:blur()", re.compile(r"filter\s*:\s*blur", re.I)),
]

_ALLOWED_PAINT = re.compile(r"^(currentColor|none|inherit|transparent)$", re.I)
_PAINT_ATTR = re.compile(r"\b(?:fill|stroke|stop-color)\s*[=:]\s*[\"']?\s*([^\"';>]+?)\s*[\"';>]", re.I)


def load_catalog() -> dict:
    if not CATALOG.exists():
        return {"version": 1, "icons": []}
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def _tokens(s: str) -> list[str]:
    return [t for t in re.split(r"[\s,]+", s.strip().lower()) if t]


def score(icon: dict, query_tokens: list[str]) -> int:
    """Rank id/name matches above tag matches above keyword-only matches."""
    idv = icon.get("id", "").lower()
    name = icon.get("name", "").lower()
    tags = [t.lower() for t in icon.get("tags", [])]
    kws = [k.lower() for k in icon.get("keywords", [])]
    total = 0
    for tok in query_tokens:
        s = 0
        if tok == idv or tok == name:
            s = 10
        elif tok in idv or tok in name:
            s = 6
        elif any(tok == t for t in tags):
            s = 4
        elif any(tok in t for t in tags):
            s = 3
        elif any(tok in k for k in kws):
            s = 2
        total += s
    return total


def search(query: str, catalog: dict, category: str | None = None) -> list[dict]:
    toks = _tokens(query)
    hits = []
    for icon in catalog.get("icons", []):
        if category and icon.get("category") != category:
            continue
        sc = score(icon, toks)
        if sc > 0:
            hits.append((sc, icon))
    hits.sort(key=lambda x: (-x[0], x[1].get("id", "")))
    return [icon for _, icon in hits]


def validate(catalog: dict) -> list[str]:
    """Return a list of problems; empty == clean."""
    problems: list[str] = []
    seen_files: set[str] = set()
    for icon in catalog.get("icons", []):
        iid = icon.get("id", "<no-id>")
        for req in ("id", "name", "category", "tags", "keywords", "viewBox", "file"):
            if req not in icon:
                problems.append(f"{iid}: missing catalog field '{req}'")
        fname = icon.get("file")
        if not fname:
            continue
        seen_files.add(fname)
        svg_path = ICONS_DIR / fname
        if not svg_path.exists():
            problems.append(f"{iid}: file '{fname}' not found in mermaid_render/icons/")
            continue
        svg = svg_path.read_text(encoding="utf-8")
        if "viewBox" not in svg:
            problems.append(f"{iid}: SVG has no viewBox (not inline-safe / not scalable)")
        for label, rx in FORBIDDEN:
            if rx.search(svg):
                problems.append(f"{iid}: forbidden technique — {label}")
        for m in _PAINT_ATTR.finditer(svg):
            val = m.group(1).strip()
            if val.lower().startswith("url("):
                continue
            if val.startswith("var(") or _ALLOWED_PAINT.match(val):
                continue
            problems.append(
                f"{iid}: hardcoded paint '{val}' — bind to currentColor or var(--…) so it themes")
    for svg in sorted(ICONS_DIR.glob("*.svg")):
        if svg.name not in seen_files:
            problems.append(f"orphan: {svg.name} has no catalog.json entry")
    return problems


def run_icons(args: argparse.Namespace) -> int:
    """Dispatcher called by mermaid_render.__main__ icons subcommand."""
    if args.validate:
        catalog = load_catalog()
        problems = validate(catalog)
        n = len(catalog.get("icons", []))
        if problems:
            print(f"✗ icon library: {len(problems)} problem(s) across {n} icon(s)")
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print(f"✓ icon library clean: {n} icon(s), catalog↔files consistent, all inline-safe")
        return 0

    if args.snippet:
        hits = search(args.query, load_catalog(), getattr(args, "category", None))
        if not hits:
            print("no match", file=sys.stderr)
            return 1
        print((ICONS_DIR / hits[0]["file"]).read_text(encoding="utf-8").rstrip())
        return 0

    if args.list or not args.query:
        icons = load_catalog().get("icons", [])
        cat = getattr(args, "category", None)
        if cat:
            icons = [i for i in icons if i.get("category") == cat]
        if getattr(args, "json_out", False):
            print(json.dumps(icons, ensure_ascii=False, indent=2))
        else:
            for i in sorted(icons, key=lambda x: x.get("id", "")):
                print(f"{i['id']:<18} {i.get('category',''):<16} {' · '.join(i.get('tags', []))}")
        return 0

    hits = search(args.query, load_catalog(), getattr(args, "category", None))
    if getattr(args, "json_out", False):
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return 0
    if not hits:
        print(f"no icon matches '{args.query}' — consider redrawing it (see references/icons.md)")
        return 0
    for i in hits:
        print(f"{i['id']:<18} {i.get('category',''):<16} {' · '.join(i.get('tags', []))}  → {i['file']}")
    return 0


def main(argv=None) -> int:
    """Standalone entry point (used by icon_search.py shim)."""
    ap = argparse.ArgumentParser(description="Search / validate the SVG icon library.")
    ap.add_argument("query", nargs="?", default="", help="search terms")
    ap.add_argument("--list", action="store_true", help="list every icon id")
    ap.add_argument("--category", help="filter search/list to one category")
    ap.add_argument("--json", action="store_true", dest="json_out", help="machine-readable output")
    ap.add_argument("--snippet", action="store_true", help="print inline <svg> of the top hit")
    ap.add_argument("--validate", action="store_true", help="check catalog↔file + pipeline-safety")
    return run_icons(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
