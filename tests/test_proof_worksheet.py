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
            notes_file = deck6 / "iso-deck-notes.json"
            check("build created at least one file", len(new_files) >= 1)
            # notes.json is the one sanctioned write outside runtime/proof/
            non_proof = {p for p in new_files if not str(p).startswith(str(proof_root))}
            check("new files outside runtime/proof/ are only the notes.json",
                  non_proof == {notes_file} or non_proof == set())
            check("every non-notes new file is under runtime/proof/",
                  all(str(p).startswith(str(proof_root)) for p in new_files - non_proof))
            forbidden = ("references/styles", "style-gallery", "/slides/")
            check("no new file touches a forbidden repo surface",
                  not any(tok in str(p) for p in new_files for tok in forbidden))

            # build must not mutate the gallery style inventory (pinned by equality,
            # not an unpinned before/after count) and must add no 'proof' style id.
            check("gallery style id-set unchanged by build", ids_before == ids_after)
            check("schematic_blueprint present; no proof style id leaked",
                  "schematic_blueprint" in ids_after
                  and not any("proof" in str(sid) for sid in ids_after))

            # ---- notes.json generation: writes, correct schema, no overwrite ------
            notes_deck = Path(td) / "notes-deck"
            write_deck(notes_deck, [base_page(1), base_page(2)],
                       outline={"ppt_outline": {"cover": {"title": "Notes Test"}}})
            PW.build(notes_deck)
            notes_path = notes_deck / "notes-deck-notes.json"
            check("build() writes notes.json at deck root", notes_path.is_file())
            if notes_path.is_file():
                nj = json.loads(notes_path.read_text(encoding="utf-8"))
                check("notes.json schema_version is '1'", nj.get("schema_version") == "1")
                check("notes.json slides count matches page count",
                      isinstance(nj.get("slides"), list) and len(nj["slides"]) == 2)

            # overwrite guard: pre-write a stub with sentinel content
            sentinel = json.dumps({"schema_version": "1", "_comment": "SENTINEL", "slides": []})
            notes_deck2 = Path(td) / "notes-deck2"
            write_deck(notes_deck2, [base_page(1)])
            notes_path2 = notes_deck2 / "notes-deck2-notes.json"
            notes_path2.write_text(sentinel, encoding="utf-8")
            PW.build(notes_deck2)
            check("build() does not overwrite existing notes.json",
                  notes_path2.read_text(encoding="utf-8") == sentinel)

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

            # ---- Facilitation section: render_page() with and without notes ------
            fac_page = base_page(1)
            fac_html_with = PW.render_page(fac_page, notes_by_slide={1: "Test facilitation note."})
            fac_html_without = PW.render_page(fac_page, notes_by_slide=None)
            check("Facilitation section present when notes provided",
                  'class="facilitation"' in fac_html_with and "Test facilitation note." in fac_html_with)
            check("Facilitation label present when notes provided",
                  'class="fac-label"' in fac_html_with)
            check("Facilitation section absent when notes_by_slide is None",
                  'class="facilitation"' not in fac_html_without)
            fac_html_no_entry = PW.render_page(fac_page, notes_by_slide={99: "other slide"})
            check("Facilitation section absent when slide has no matching entry",
                  'class="facilitation"' not in fac_html_no_entry)

            # HTML escaping
            fac_html_escaped = PW.render_page(
                fac_page, notes_by_slide={1: '<script>alert(1)</script>'}
            )
            check("notes text is HTML-escaped in Facilitation",
                  "<script>" not in fac_html_escaped and "&lt;script&gt;" in fac_html_escaped)

            # render_worksheet with notes_by_slide=None unchanged
            deck_rw = Path(td) / "rw-deck"
            write_deck(deck_rw, [base_page(1)])
            pages_rw = PW.load_pages(deck_rw)
            out_no_notes = PW.render_worksheet(deck_rw, pages_rw, None, None)
            out_no_notes2 = PW.render_worksheet(deck_rw, pages_rw, None)
            check("render_worksheet notes_by_slide=None backward compatible",
                  out_no_notes == out_no_notes2)
            check("render_worksheet None notes has no Facilitation section",
                  'class="facilitation"' not in out_no_notes)

            # ---- T4: build() loads notes.json and passes to render_worksheet() ---
            bld_notes_deck = Path(td) / "bld-notes-deck"
            write_deck(bld_notes_deck, [base_page(1)],
                       outline={"ppt_outline": {"cover": {"title": "BldNotes"}}})
            # pre-populate notes.json with content
            bld_notes_path = bld_notes_deck / "bld-notes-deck-notes.json"
            bld_notes_path.write_text(
                json.dumps({
                    "schema_version": "1", "_comment": "test",
                    "slides": [{"slide_number": 1, "title": "T", "notes": "Facilitation text here."}]
                }), encoding="utf-8"
            )
            bld_html = PW.build(bld_notes_deck).read_text(encoding="utf-8")
            check("build() passes notes to worksheet when notes.json present",
                  'class="facilitation"' in bld_html and "Facilitation text here." in bld_html)

            # build() generates notes.json when absent and renders Facilitation from it
            bld_derived_deck = Path(td) / "bld-derived-deck"
            write_deck(bld_derived_deck, [base_page(1)])
            bld_derived_html = PW.build(bld_derived_deck).read_text(encoding="utf-8")
            bld_derived_notes = bld_derived_deck / "bld-derived-deck-notes.json"
            check("build() generates notes.json from planning when absent",
                  bld_derived_notes.is_file())
            check("build() renders Facilitation from derived notes",
                  'class="facilitation"' in bld_derived_html)

            # build determinism with notes.json
            bld_det_deck = Path(td) / "bld-det-deck"
            write_deck(bld_det_deck, [base_page(1)])
            det_path = bld_det_deck / "bld-det-deck-notes.json"
            det_path.write_text(json.dumps({
                "schema_version": "1", "_comment": "det",
                "slides": [{"slide_number": 1, "title": "D", "notes": "Determinism note."}]
            }), encoding="utf-8")
            det_html1 = PW.build(bld_det_deck).read_text(encoding="utf-8")
            det_html2 = PW.build(bld_det_deck).read_text(encoding="utf-8")
            check("build() with notes.json is deterministic", det_html1 == det_html2)

            # malformed notes.json: bad JSON → build proceeds, no crash
            bld_bad_deck = Path(td) / "bld-bad-deck"
            write_deck(bld_bad_deck, [base_page(1)])
            bad_notes_path = bld_bad_deck / "bld-bad-deck-notes.json"
            bad_notes_path.write_text("{ not valid json", encoding="utf-8")
            import io, contextlib
            stderr_buf = io.StringIO()
            with contextlib.redirect_stderr(stderr_buf):
                bld_bad_html = PW.build(bld_bad_deck).read_text(encoding="utf-8")
            check("build() degrades on malformed notes.json — no crash", bld_bad_html is not None)
            check("build() logs warning to stderr on malformed notes.json",
                  "notes.json" in stderr_buf.getvalue() or "notes" in stderr_buf.getvalue())

            # malformed entries: null slide_number + non-dict + valid → only valid renders
            bld_mixed_deck = Path(td) / "bld-mixed-deck"
            write_deck(bld_mixed_deck, [base_page(1)])
            mixed_notes_path = bld_mixed_deck / "bld-mixed-deck-notes.json"
            mixed_notes_path.write_text(json.dumps({
                "schema_version": "1", "_comment": "mixed",
                "slides": [
                    {"slide_number": None, "title": "bad", "notes": "skip me"},
                    "not a dict",
                    {"slide_number": 1, "title": "good", "notes": "Valid note here."},
                ]
            }), encoding="utf-8")
            bld_mixed_html = PW.build(bld_mixed_deck).read_text(encoding="utf-8")
            check("build() renders valid notes entry despite malformed siblings",
                  "Valid note here." in bld_mixed_html)

        if FAILS:
            print(f"\n{len(FAILS)} failure(s): {FAILS}")
            return 1
        print("\nall proof_worksheet checks passed")
        return 0


    if __name__ == "__main__":
        sys.exit(main())
