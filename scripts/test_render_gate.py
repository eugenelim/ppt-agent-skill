#!/usr/bin/env python3
"""test_render_gate.py — the render-completeness gate (milestone_check --with-visual-qa)
enforces that Stage-3 review ran on the *current* HTML.

Covers the load-bearing new logic: PNG-freshness (missing / stale) and the
node-unavailable announced-skip decision. The visual_qa batch itself is covered
by the existing visual_qa self-tests; a live end-to-end run is manual QA (T6).

No pytest harness; run directly or via smoke_test.py. Exit 0 = pass, 1 = fail.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import milestone_check as M  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(f"  [{'OK' if cond else 'XX'}] {name}")
    if not cond:
        FAILS.append(name)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        slides = Path(td) / "slides"
        png = Path(td) / "png"
        slides.mkdir()
        png.mkdir()
        for n in (1, 2, 3):
            (slides / f"slide-{n}.html").write_text(f"<html>{n}</html>")
        time.sleep(0.01)
        for n in (1, 2, 3):
            (png / f"slide-{n}.png").write_bytes(b"\x89PNG\r\n")

        # 1. all fresh PNGs -> no issues (clean deck passes).
        check("fresh PNGs -> no freshness issues", M.png_freshness_issues(slides, png) == [])

        # 2. missing PNG -> flagged.
        (png / "slide-2.png").unlink()
        iss = M.png_freshness_issues(slides, png)
        check(f"missing PNG flagged (got {iss})", any("slide-2" in m and "no matching" in m for m in iss))
        (png / "slide-2.png").write_bytes(b"\x89PNG\r\n")

        # 3. stale PNG (older than its HTML) -> flagged.
        now = time.time()
        os.utime(png / "slide-1.png", (now - 100, now - 100))
        os.utime(slides / "slide-1.html", (now, now))
        iss2 = M.png_freshness_issues(slides, png)
        check(f"stale PNG flagged (got {iss2})", any("slide-1.png is stale" in m for m in iss2))

    # 4. node-unavailable -> announced-skip BEHAVIOR (not just the helper). Drive
    #    the real enforcement seam against a PNG-less deck with node stubbed out:
    #    it must NOT hard-fail and must emit the [SKIP] marker. An inverted
    #    condition would hard-fail here.
    import io
    from contextlib import redirect_stdout
    with tempfile.TemporaryDirectory() as td:
        deck = Path(td)
        s = deck / "slides"; p = deck / "png"; s.mkdir(); p.mkdir()
        (s / "slide-1.html").write_text("<html></html>")  # note: png/ deliberately empty
        chk = M.Checker(skill_dir=ROOT, output_dir=deck, target="4", with_visual_qa=True)
        chk.pages = 1
        orig = M.shutil.which
        try:
            M.shutil.which = lambda name: None  # simulate no node on PATH
            buf = io.StringIO()
            raised = False
            try:
                with redirect_stdout(buf):
                    chk._check_pngs_and_visual(s, p)
            except Exception:
                raised = True
            out = buf.getvalue()
            check("node absent + PNG-less deck -> gate does NOT hard-fail", not raised)
            check("node absent -> announced [SKIP] marker emitted", "[SKIP] visual gate" in out)
        finally:
            M.shutil.which = orig
    check("node_available() True in this env (node present)", M.node_available() is True)

    # 5. regression: the flag is off by default (existing callers byte-identical).
    c = M.Checker(skill_dir=ROOT, output_dir=ROOT, target="4")
    check("with_visual_qa defaults to False", c.with_visual_qa is False)

    # 6. _render_visual_gate: freshness + visual_qa exit-code mapping. The visual_qa
    #    subprocess is stubbed so we assert the 0/2 -> pass, 1 -> fail mapping and
    #    that freshness is enforced *before* the subprocess runs.
    class FakeProc:
        def __init__(self, rc: int) -> None:
            self.returncode, self.stdout, self.stderr = rc, "", ""

    def gate_raises(checker, slides, png) -> bool:
        try:
            checker._render_visual_gate(slides, png)
            return False
        except RuntimeError:
            return True

    with tempfile.TemporaryDirectory() as td:
        deck = Path(td)
        s = deck / "slides"; p = deck / "png"; s.mkdir(); p.mkdir()
        for n in (1, 2):
            (s / f"slide-{n}.html").write_text("<html></html>")
        time.sleep(0.01)
        for n in (1, 2):
            (p / f"slide-{n}.png").write_bytes(b"\x89PNG\r\n")
        chk = M.Checker(skill_dir=ROOT, output_dir=deck, target="4")
        orig_run = M.subprocess.run
        try:
            M.subprocess.run = lambda *a, **k: FakeProc(0)
            check("visual gate: fresh + visual_qa exit 0 -> pass", not gate_raises(chk, s, p))
            M.subprocess.run = lambda *a, **k: FakeProc(2)
            check("visual gate: exit 2 (WARN) -> pass", not gate_raises(chk, s, p))
            M.subprocess.run = lambda *a, **k: FakeProc(1)
            check("visual gate: exit 1 (FAIL) -> raises", gate_raises(chk, s, p))
            # stale PNG must fail the gate even when visual_qa would pass (exit 0).
            now = time.time()
            os.utime(p / "slide-1.png", (now - 100, now - 100))
            os.utime(s / "slide-1.html", (now, now))
            M.subprocess.run = lambda *a, **k: FakeProc(0)
            check("visual gate: stale PNG -> raises before visual_qa", gate_raises(chk, s, p))
        finally:
            M.subprocess.run = orig_run

    if FAILS:
        print(f"\nFAILED: {len(FAILS)} check(s): {FAILS}")
        return 1
    print("\nAll render-gate checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
