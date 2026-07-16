#!/usr/bin/env python3
"""proof_worksheet.py -- deterministic, no-LLM slide-intent worksheet.

Renders a deck's ``planning/*.json`` (+ ``outline.json``) into a low-fidelity
review worksheet at ``OUTPUT_DIR/runtime/proof/<deck-slug>-intent.html``, styled
by the owned ``assets/proof/proof.css`` (a color-muted schematic_blueprint
derivative). It renders the *plan* as an engineering worksheet -- NOT a mock of
the bespoke slide -- so it is fully deterministic: the same inputs (including CLI
args) produce byte-identical output, with no LLM, no network, and no system-clock
read (the as-of date is the explicit ``--as-of`` argument).

Read-only review artifact: ``planning/*.json`` stays the source of truth; fixes
land there and the worksheet is regenerated. Output is scratch under ``runtime/``
(gitignored). This tool writes ONLY under ``OUTPUT_DIR/runtime/proof/``.

Usage:
    python3 scripts/proof_worksheet.py <deck_dir> [--as-of DATE]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import planning_validator as PV  # noqa: E402  (sibling script; planning-data contract)

REPO_ROOT = Path(__file__).resolve().parent.parent
PROOF_CSS = REPO_ROOT / "assets" / "proof" / "proof.css"

# Deterministic spillover budget: max content rows per worksheet card before a
# continuation card ("N * 2/2") starts. Content fields are NEVER truncated -- a
# single card larger than the budget still renders whole, alone, in its own part.
# 40 is an arbitrary readability budget with no downstream contract; retune freely.
MAX_CARD_ROWS = 40

# Art-direction / metadata fields, rendered collapsed (spillover-first), in an
# explicit order so output never depends on dict iteration.
AUX_FIELDS = (
    "director_command", "decoration_hints", "variation_guardrails", "must_avoid",
    "focus_zone", "negative_space_target", "page_text_strategy", "rhythm_action",
    "layout_variation_note", "content_budget", "density_reason",
)


def esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def as_list(v: Any) -> list:
    if isinstance(v, list):
        return v
    return [] if v is None else [v]


# ---- derived, testable predicates ------------------------------------------

def source_marker(card: dict) -> str | None:
    """Source status derived solely from data_points.

    Returns "ok" (●) when any entry is a dict with a truthy ``source``, "none"
    (○) when data_points is non-empty but none carry a source (covers plain
    strings and source-less dicts), and None (no marker) when empty/absent.
    """
    dps = card.get("data_points")
    if not isinstance(dps, list) or not dps:
        return None
    for entry in dps:
        if isinstance(entry, dict) and entry.get("source"):
            return "ok"
    return "none"


def is_chart(card: dict) -> bool:
    """Chart predicate matching planning_validator: a dict ``chart`` whose
    ``chart_type`` is a non-empty string."""
    ch = card.get("chart")
    return isinstance(ch, dict) and isinstance(ch.get("chart_type"), str) and bool(ch.get("chart_type"))


def card_rows(card: dict) -> int:
    body = [b for b in as_list(card.get("body")) if isinstance(b, str) and b.strip()]
    items = [i for i in as_list(card.get("items")) if i]  # match render_card_row's filters
    return 1 + len(body) + len(items) + len(as_list(card.get("data_points")))


def chunk_cards(cards: list[dict]) -> list[list[dict]]:
    """Greedy, deterministic priority chunking. Content is never truncated: a
    card bigger than the budget occupies its own part alone."""
    parts: list[list[dict]] = []
    cur: list[dict] = []
    cur_rows = 0
    for card in cards:
        rows = card_rows(card)
        if cur and cur_rows + rows > MAX_CARD_ROWS:
            parts.append(cur)
            cur, cur_rows = [], 0
        cur.append(card)
        cur_rows += rows
    if cur:
        parts.append(cur)
    return parts or [[]]


# ---- titles -----------------------------------------------------------------

def deck_title(deck_dir: Path) -> str:
    """Deck heading from outline.json cover.title (fallback: deck-slug). No clock,
    no network -- reads the already-clean upstream title field only."""
    for name in ("outline.json", "outline.txt"):
        path = deck_dir / name
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"proof_worksheet: {name} unreadable ({exc}); using deck-slug", file=sys.stderr)
            continue
        match = re.search(r"\[PPT_OUTLINE\](.*?)\[/PPT_OUTLINE\]", raw, re.S)
        if match:
            raw = match.group(1)
        try:
            data = json.loads(raw.strip())
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"proof_worksheet: {name} not valid JSON ({exc}); using deck-slug", file=sys.stderr)
            continue
        node = data.get("ppt_outline", data) if isinstance(data, dict) else {}
        cover = node.get("cover") if isinstance(node, dict) else None
        cand = cover.get("title") if isinstance(cover, dict) else None
        if isinstance(cand, str) and cand.strip():
            return cand.strip()
    return deck_dir.name


# ---- rendering (deterministic; explicit field order throughout) -------------

def fmt_data_points(dps: Any) -> str:
    pieces = []
    for entry in as_list(dps):
        if isinstance(entry, dict):
            head = " ".join(str(x) for x in (entry.get("label"), entry.get("value")) if x not in (None, ""))
            unit = entry.get("unit")
            if unit:
                head = f"{head}{unit}" if head else str(unit)
            pieces.append(head or json.dumps(entry, ensure_ascii=False, sort_keys=True))
        else:
            pieces.append(str(entry))
    return " · ".join(esc(p) for p in pieces)


def render_card_row(card: dict) -> str:
    role = card.get("role") or ""
    role_cls = "role anchor" if role == "anchor" else "role"
    kind = "/".join(str(x) for x in (card.get("card_type"), card.get("card_style")) if x)
    arg = card.get("argument_role")

    content_bits = []
    headline = card.get("headline")
    if isinstance(headline, str) and headline.strip():
        content_bits.append(f'<div class="headline">{esc(headline)}</div>')
    body = [b for b in as_list(card.get("body")) if isinstance(b, str) and b.strip()]
    items = [i for i in as_list(card.get("items")) if i]
    for line in body:
        content_bits.append(f"<div>{esc(line)}</div>")
    if items:
        lis = "".join(f"<li>{esc(i)}</li>" for i in items)
        content_bits.append(f"<ul>{lis}</ul>")
    dps = fmt_data_points(card.get("data_points"))
    if dps:
        content_bits.append(f'<div class="data">{dps}</div>')
    if is_chart(card):
        content_bits.append(f'<div class="data">chart: {esc(card["chart"]["chart_type"])}</div>')
    image = card.get("image")
    if isinstance(image, dict) and image.get("needed"):
        img = " ".join(str(x) for x in (image.get("usage"), image.get("content_description")) if x)
        content_bits.append(f'<div class="src">img: {esc(img)}</div>')
    # diagram_source.mermaid_source — show topology for proof review
    ds = card.get("diagram_source")
    if isinstance(ds, dict):
        ms = ds.get("mermaid_source")
        if isinstance(ms, str) and ms.strip():
            src_ref = ds.get("source_ref") or ""
            fence_idx = ds.get("fence_index")
            meta = ""
            if src_ref:
                meta += f" · {esc(src_ref)}"
            if isinstance(fence_idx, int):
                meta += f" · fence {fence_idx}"
            content_bits.append(
                f'<div class="mermaid-src-label">mermaid source{meta}</div>'
                f'<pre class="mermaid-src"><code>```mermaid\n{esc(ms.strip())}\n```</code></pre>'
            )

    marker = source_marker(card)
    if marker == "ok":
        status = '<td class="status st-ok" title="sourced">●</td>'
    elif marker == "none":
        status = '<td class="status st-none" title="no source">○</td>'
    else:
        status = '<td class="status"></td>'

    return (
        "<tr>"
        f'<td class="{role_cls}">{esc(role)}</td>'
        f'<td class="kind">{esc(kind)}{("&nbsp;·&nbsp;" + esc(arg)) if arg else ""}</td>'
        f'<td class="content">{"".join(content_bits)}</td>'
        f"{status}"
        "</tr>"
    )


def render_meta(page: dict, n_cards: int, n_charts: int) -> str:
    dc = page.get("density_contract") if isinstance(page.get("density_contract"), dict) else {}
    max_cards = dc.get("max_cards")
    max_charts = dc.get("max_charts")
    cards_flag = isinstance(max_cards, int) and n_cards == max_cards
    charts_flag = isinstance(max_charts, int) and n_charts == max_charts
    density = esc(page.get("density_label"))
    if cards_flag or charts_flag:
        density = f'{density} <span class="warn">⚠ at budget</span>'
    bits = []
    if page.get("layout_hint"):
        bits.append(f'<span>layout: {esc(page["layout_hint"])}</span>')
    bits.append(f"<span>density: {density}</span>")
    bits.append(f"<span>cards: {n_cards}/{esc(max_cards) if max_cards is not None else '-'}</span>")
    bits.append(f"<span>charts: {n_charts}/{esc(max_charts) if max_charts is not None else '-'}</span>")
    return f'<div class="meta">{"".join(bits)}</div>'


def render_source_guidance(page: dict) -> str:
    sg = page.get("source_guidance")
    if not isinstance(sg, dict):
        return ""
    parts = []
    briefs = sg.get("brief_sections")
    if briefs:
        parts.append(f"<b>brief:</b> {esc(', '.join(str(b) for b in as_list(briefs)))}")
    if sg.get("citation_expectation"):
        parts.append(f"<b>citations:</b> {esc(sg['citation_expectation'])}")
    if sg.get("strictness"):
        parts.append(f"<b>strictness:</b> {esc(sg['strictness'])}")
    return f'<div class="sg">{" &nbsp;·&nbsp; ".join(parts)}</div>' if parts else ""


def render_aux(page: dict) -> str:
    dump = {}
    for field in AUX_FIELDS:
        if field in page and page.get(field) not in (None, "", [], {}):
            dump[field] = page.get(field)
    if not dump:
        return ""
    text = json.dumps(dump, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        '<details class="aux"><summary>art-direction &amp; pacing (collapsed)</summary>'
        f"<pre>{esc(text)}</pre></details>"
    )


def render_page(page: dict) -> str:
    slide_no = page.get("slide_number")
    cards = [c for c in as_list(page.get("cards")) if isinstance(c, dict)]
    n_cards = len(cards)
    n_charts = sum(1 for c in cards if is_chart(c))
    parts = chunk_cards(cards)
    total = len(parts)
    title = esc(page.get("title"))
    ptype = esc(page.get("page_type"))
    nrole = esc(page.get("narrative_role"))
    takeaway = page.get("audience_takeaway") or page.get("page_goal")

    blocks = []
    for idx, part in enumerate(parts):
        part_label = f" · {idx + 1}/{total}" if total > 1 else ""
        anchor = f' id="slide-{esc(slide_no)}"' if idx == 0 else ""
        head = f'<div class="card-head"><span>Slide {esc(slide_no)}{part_label}</span><span>{ptype}{(" · " + nrole) if nrole else ""}</span></div>'
        rows = "".join(render_card_row(c) for c in part)
        table = (
            '<table class="cards"><thead><tr>'
            "<th>role</th><th>type/style</th><th>content</th><th>src</th>"
            f"</tr></thead><tbody>{rows}</tbody></table>"
        )
        body = [f'<section class="slide-card"{anchor}>', head]
        if idx == 0:
            body.append(f'<h2 class="slide-title">{title}</h2>')
            if takeaway:
                body.append(f'<p class="takeaway">↳ {esc(takeaway)}</p>')
            body.append(render_meta(page, n_cards, n_charts))
            body.append(render_source_guidance(page))
        body.append(table)
        if idx == total - 1:
            body.append(render_aux(page))
        body.append("</section>")
        blocks.append("".join(b for b in body if b))
    return "".join(blocks)


def render_index(pages: list[dict]) -> str:
    rows = ['<div class="index">']
    for page in pages:
        slide_no = page.get("slide_number")
        cards = [c for c in as_list(page.get("cards")) if isinstance(c, dict)]
        n_cards = len(cards)
        n_charts = sum(1 for c in cards if is_chart(c))
        unsourced = sum(1 for c in cards if source_marker(c) == "none")
        dc = page.get("density_contract") if isinstance(page.get("density_contract"), dict) else {}
        at_budget = (isinstance(dc.get("max_cards"), int) and n_cards == dc["max_cards"]) or (
            isinstance(dc.get("max_charts"), int) and n_charts == dc["max_charts"]
        )
        flags = []
        if unsourced:
            flags.append(f"○×{unsourced}")
        if at_budget:
            flags.append("⚠")
        rows.append(
            '<div class="index-row">'
            f'<span class="no"><a href="#slide-{esc(slide_no)}">{esc(slide_no)}</a></span>'
            f"<span>{esc(page.get('title'))}</span>"
            f"<span>{esc(page.get('density_label'))}</span>"
            f'<span class="flags">{esc(" ".join(flags))}</span>'
            "</div>"
        )
    rows.append("</div>")
    return "".join(rows)


def render_worksheet(deck_dir: Path, pages: list[dict], as_of: str | None) -> str:
    title = deck_title(deck_dir)
    archetype = pages[0].get("narrative_archetype") if pages else None
    meta_bits = [f"{len(pages)} slides"]
    if archetype:
        meta_bits.append(esc(archetype))
    if as_of:
        meta_bits.append(f"as of {esc(as_of)}")
    css = PROOF_CSS.read_text(encoding="utf-8")
    header = (
        '<header class="deck-header">'
        f'<h1 class="deck-title">{esc(title)}</h1>'
        f'<div class="deck-meta">slide-intent worksheet · {" · ".join(meta_bits)}</div>'
        "</header>"
    )
    body = header + render_index(pages) + "".join(render_page(p) for p in pages)
    return (
        "<!doctype html>\n"
        '<html lang="zh">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)} — slide-intent</title>\n"
        f"<style>\n{css}\n</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


def load_pages(deck_dir: Path) -> list[dict]:
    """Load planning/*.json with per-file error context so a malformed file is
    named (not a bare traceback). Non-dict pages are skipped by load_planning_pages."""
    pdir = deck_dir / "planning"
    files = sorted(pdir.glob("planning*.json"), key=PV.natural_sort_key)
    if not files:
        raise ValueError(f"no planning*.json files in {pdir}")
    pages: list[dict] = []
    for path in files:
        try:
            pages.extend(PV.load_planning_pages(path))
        except (ValueError, OSError) as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
    return sorted(pages, key=lambda p: int(p.get("slide_number") or 0))


def build(deck_dir: Path, as_of: str | None = None) -> Path:
    pages = load_pages(deck_dir)
    out_dir = deck_dir / "runtime" / "proof"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{deck_dir.name}-intent.html"
    out_path.write_text(render_worksheet(deck_dir, pages, as_of), encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic slide-intent review worksheet")
    parser.add_argument("deck_dir", help="Deck OUTPUT_DIR (contains planning/, outline.json)")
    parser.add_argument("--as-of", default=None, help="Explicit deck as-of date (verbatim; no clock read)")
    args = parser.parse_args(argv)

    deck_dir = Path(args.deck_dir).resolve()
    if not (deck_dir / "planning").is_dir():
        print(f"proof_worksheet: no planning/ under {deck_dir}", file=sys.stderr)
        return 1
    try:
        out_path = build(deck_dir, args.as_of)
    except (ValueError, OSError) as exc:
        print(f"proof_worksheet: {exc}", file=sys.stderr)
        return 1
    print(f"proof_worksheet: wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
