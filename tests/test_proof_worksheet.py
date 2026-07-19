#!/usr/bin/env python3
"""test_proof_worksheet.py -- the deterministic slide-intent worksheet renderer.

Covers the spec's Acceptance Criteria: SHOWN field set, source-status predicate
(●/○/none), density at-budget flag with the validator's chart predicate,
determinism (byte-identical + reserialization-stable), priority spillover
(content never truncated), title derivation, and write-set isolation.

No pytest in this repo; run directly or via smoke_test.py. Exit 0 = pass.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

import proof_worksheet as PW  # noqa: E402
import smoke_skill as S  # noqa: E402


if __name__ == "__main__":
    FAILS: list[str] = []


    def check(name: str, cond: bool) -> None:
        print(f"  [{'OK' if cond else 'XX'}] {name}")
        if not cond:
            FAILS.append(name)


    def write_deck(deck_dir: Path, pages: list[dict], outline: dict | None = None) -> None:
        pdir = deck_dir / "planning"
        pdir.mkdir(parents=True, exist_ok=True)
        for i, page in enumerate(pages, start=1):
            (pdir / f"planning{i:02d}.json").write_text(
                json.dumps(page, ensure_ascii=False), encoding="utf-8"
            )
        if outline is not None:
            (deck_dir / "outline.json").write_text(
                json.dumps(outline, ensure_ascii=False), encoding="utf-8"
            )


    def base_page(slide_number: int) -> dict:
        return S.build_content_page_fixture(slide_number=slide_number, density_label="medium")["page"]


    def status_page() -> dict:
        page = base_page(1)
        page["title"] = "Status page"
        page["cards"] = [
            {"card_id": "s01-anchor-1", "role": "anchor", "card_type": "data", "card_style": "accent",
             "argument_role": "claim", "headline": "sourced", "body": [],
             "data_points": [{"label": "x", "value": "1", "unit": "%", "source": "rep-2022"}]},
            {"card_id": "s01-support-1", "role": "support", "card_type": "data", "card_style": "outline",
             "argument_role": "evidence", "headline": "unsourced-dict", "body": [],
             "data_points": [{"label": "y", "value": "2"}]},
            {"card_id": "s01-support-2", "role": "support", "card_type": "data", "card_style": "filled",
             "argument_role": "evidence", "headline": "string-dp", "body": [], "data_points": ["raw datum"]},
            {"card_id": "s01-context-1", "role": "context", "card_type": "text", "card_style": "transparent",
             "argument_role": "context", "headline": "no-data", "body": ["prose only"], "data_points": []},
        ]
        return page


    def main() -> int:
        # ---- predicate unit checks ------------------------------------------------
        check("source_marker: dict with source -> ok",
              PW.source_marker({"data_points": [{"value": "1", "source": "s"}]}) == "ok")
        check("source_marker: source-less dict -> none",
              PW.source_marker({"data_points": [{"value": "1"}]}) == "none")
        check("source_marker: plain-string data_points -> none",
              PW.source_marker({"data_points": ["datum"]}) == "none")
        check("source_marker: empty data_points -> None",
              PW.source_marker({"data_points": []}) is None)
        check("source_marker: absent data_points -> None",
              PW.source_marker({}) is None)
        check("is_chart: dict chart_type -> True",
              PW.is_chart({"chart": {"chart_type": "kpi"}}) is True)
        check("is_chart: empty chart_type -> False",
              PW.is_chart({"chart": {"chart_type": ""}}) is False)
        check("is_chart: no chart -> False", PW.is_chart({}) is False)

        with tempfile.TemporaryDirectory() as td:
            # ---- basic render + SHOWN set + index + titles ------------------------
            deck = Path(td) / "threat-report"
            write_deck(deck, [base_page(1), base_page(2)],
                       outline={"ppt_outline": {"cover": {"title": "The Threat Surface"}}})
            out = PW.build(deck)
            html = out.read_text(encoding="utf-8")
            check("output under runtime/proof/ with deck-slug name",
                  out == deck / "runtime" / "proof" / "threat-report-intent.html")
            check("deck title from outline cover.title", "The Threat Surface" in html)
            check("browser tab title derived from deck title (distinct from <h1>)",
                  "<title>The Threat Surface — slide-intent</title>" in html)
            check("pinned index present", 'class="index"' in html and 'href="#slide-1"' in html)
            check("per-slide anchor present", 'id="slide-1"' in html)
            check("SHOWN meta strip present", 'class="meta"' in html and "density:" in html)
            check("source_guidance rendered in meta", 'class="sg"' in html)
            check("art-direction collapsed in <details>", 'details class="aux"' in html)
            check("routing field visual_weight omitted", "visual_weight" not in html)

            # ---- deck title fallback to slug -------------------------------------
            deck2 = Path(td) / "no-outline-deck"
            write_deck(deck2, [base_page(1)])
            html2 = PW.build(deck2).read_text(encoding="utf-8")
            check("deck title falls back to deck-slug", "no-outline-deck" in html2)

            # ---- source status predicate in rendered HTML ------------------------
            deck3 = Path(td) / "status-deck"
            write_deck(deck3, [status_page()])
            html3 = PW.build(deck3).read_text(encoding="utf-8")
            check("one ● (st-ok) card", html3.count('class="status st-ok"') == 1)
            check("two ○ (st-none) cards", html3.count('class="status st-none"') == 2)
            check("one no-marker (empty status) card", html3.count('<td class="status"></td>') == 1)

            # ---- density at-budget flag (medium fixture: 4 cards == max_cards 4) --
            check("density ⚠ fires at budget (cards branch)", "⚠ at budget" in html)

            # chart branch isolated: charts == max_charts while cards below max_cards
            chart_budget_page = {
                "slide_number": 1, "page_type": "content", "title": "Chart budget",
                "narrative_role": "evidence", "page_goal": "g", "density_label": "medium",
                "density_contract": {"max_cards": 4, "max_charts": 1},
                "cards": [
                    {"card_id": "c1", "role": "anchor", "card_type": "data_highlight", "card_style": "accent",
                     "headline": "kpi", "data_points": [{"value": "1", "source": "s"}], "chart": {"chart_type": "kpi"}},
                    {"card_id": "c2", "role": "support", "card_type": "text", "card_style": "outline",
                     "headline": "note", "body": ["prose"], "data_points": []},
                ],
            }
            deckc = Path(td) / "chart-budget-deck"
            write_deck(deckc, [chart_budget_page])
            htmlc = PW.build(deckc).read_text(encoding="utf-8")
            check("chart ⚠ fires (charts==max_charts, cards below max_cards)", "⚠ at budget" in htmlc)

            # ---- determinism: byte-identical + reserialization-stable ------------
            deck4 = Path(td) / "det-deck"
            write_deck(deck4, [base_page(1), base_page(2)],
                       outline={"cover": {"title": "Det"}})
            first = PW.build(deck4).read_text(encoding="utf-8")
            second = PW.build(deck4).read_text(encoding="utf-8")
            check("two renders byte-identical", first == second)
            check("no --as-of -> no clock read, no date shown", "as of" not in first)
            withdate = PW.render_worksheet(deck4, PW.PV.load_planning_pages(deck4 / "planning"), "2026-07-03")
            check("--as-of renders the date", "as of 2026-07-03" in withdate)

            # reserialization stability: reorder page dict keys, output unchanged
            pages = PW.PV.load_planning_pages(deck4 / "planning")
            shuffled = [dict(reversed(list(p.items()))) for p in pages]
            check("reserialized (reordered-keys) input renders identically",
                  PW.render_worksheet(deck4, shuffled, None) == PW.render_worksheet(deck4, pages, None))

            # ---- spillover: content never truncated; continuation parts ----------
            big = base_page(1)
            big["cards"] = [
                {"card_id": f"s01-c-{i}", "role": "support", "card_type": "text", "card_style": "outline",
                 "argument_role": "evidence", "headline": f"CARD-{i}",
                 "body": [f"line-{i}-a", f"line-{i}-b", f"line-{i}-c"], "data_points": []}
                for i in range(30)
            ]
            deck5 = Path(td) / "big-deck"
            write_deck(deck5, [big])
            html5 = PW.build(deck5).read_text(encoding="utf-8")
            check("spillover produced a continuation part (· 2/)", "· 2/" in html5)
            check("all 30 card headlines survive spillover (none truncated)",
                  all(f"CARD-{i}" in html5 for i in range(30)))
            # art-direction stays collapsed under overflow (base fixture carries
            # director_command/decoration_hints, so aux must render on the last part)
            check("art-direction stays collapsed (<details aux>) under spillover",
                  'details class="aux"' in html5)

            # ---- isolation: build writes only under runtime/proof/ ---------------
            import gallery  # noqa: E402
            deck6 = Path(td) / "iso-deck"
            write_deck(deck6, [base_page(1)], outline={"cover": {"title": "Iso"}})
            before = {p for p in deck6.rglob("*") if p.is_file()}
            ids_before = {s.get("style_id") for s in gallery.collect_all_styles()}
            PW.build(deck6)
            ids_after = {s.get("style_id") for s in gallery.collect_all_styles()}
            after = {p for p in deck6.rglob("*") if p.is_file()}
            new_files = after - before

            proof_root = deck6 / "runtime" / "proof"
            check("build created at least one file", len(new_files) >= 1)
            check("every new file is under runtime/proof/",
                  all(str(p).startswith(str(proof_root)) for p in new_files))
            forbidden = ("references/styles", "style-gallery", "/slides/")
            check("no new file touches a forbidden repo surface",
                  not any(tok in str(p) for p in new_files for tok in forbidden))

            # build must not mutate the gallery style inventory (pinned by equality,
            # not an unpinned before/after count) and must add no 'proof' style id.
            check("gallery style id-set unchanged by build", ids_before == ids_after)
            check("schematic_blueprint present; no proof style id leaked",
                  "schematic_blueprint" in ids_after
                  and not any("proof" in str(sid) for sid in ids_after))

            # ---- reliability: malformed / empty / non-dict inputs ----------------
            script = str(ROOT / "scripts" / "proof_worksheet.py")
            deck7 = Path(td) / "skip-deck"
            (deck7 / "planning").mkdir(parents=True)
            (deck7 / "planning" / "planning01.json").write_text(
                json.dumps({"ppt_planning": {"pages": [base_page(1), "not-a-dict"]}}, ensure_ascii=False),
                encoding="utf-8")
            check("non-dict page skipped; render still succeeds", PW.build(deck7).is_file())

            deck8 = Path(td) / "bad-deck"
            (deck8 / "planning").mkdir(parents=True)
            (deck8 / "planning" / "planning01.json").write_text("{ not valid json", encoding="utf-8")
            r8 = subprocess.run([sys.executable, script, str(deck8)], capture_output=True, text=True)
            check("malformed planning -> exit 1, no traceback",
                  r8.returncode == 1 and "Traceback" not in r8.stderr)
            check("malformed planning -> stderr names the offending file",
                  "planning01.json" in r8.stderr)

            deck9 = Path(td) / "empty-deck"
            (deck9 / "planning").mkdir(parents=True)
            r9 = subprocess.run([sys.executable, script, str(deck9)], capture_output=True, text=True)
            check("empty planning dir -> exit 1 with actionable stderr",
                  r9.returncode == 1 and "Traceback" not in r9.stderr)

        if FAILS:
            print(f"\n{len(FAILS)} failure(s): {FAILS}")
            return 1
        print("\nall proof_worksheet checks passed")
        return 0


    if __name__ == "__main__":
        sys.exit(main())
