#!/usr/bin/env python3
"""Milestone checker for the PPT workflow.

Usage examples:
  python3 scripts/milestone_check.py 0
  python3 scripts/milestone_check.py 3.5
  python3 scripts/milestone_check.py 4
  python3 scripts/milestone_check.py preview
  python3 scripts/milestone_check.py 5 --output-dir /path/to/ppt-output
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from planning_validator import load_planning_pages
from proof_gate import gate_status


STAGE_ORDER = ("0", "1", "2", "3", "3.5", "4", "preview", "5")
STAGE_ALIAS = {
    "0": "0",
    "step0": "0",
    "step_0": "0",
    "step-0": "0",
    "1": "1",
    "step1": "1",
    "step_1": "1",
    "step-1": "1",
    "2": "2",
    "step2": "2",
    "step_2": "2",
    "step-2": "2",
    "3": "3",
    "step3": "3",
    "step_3": "3",
    "step-3": "3",
    "3.5": "3.5",
    "step3.5": "3.5",
    "step_3.5": "3.5",
    "step-3.5": "3.5",
    "4": "4",
    "step4": "4",
    "step_4": "4",
    "step-4": "4",
    "preview": "preview",
    "steppreview": "preview",
    "step_preview": "preview",
    "step-preview": "preview",
    "5": "5",
    "step5": "5",
    "step_5": "5",
    "step-5": "5",
}


def natural_sort_key(path: Path) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", path.name)
    key: list[object] = []
    for part in parts:
        key.append(int(part) if part.isdigit() else part.lower())
    return tuple(key)


def _slide_number(path: Path) -> int | None:
    m = re.search(r"(\d+)", path.stem)
    return int(m.group(1)) if m else None


def node_available() -> bool:
    """Whether headless-Chrome screenshotting (Stage-3 render) is possible. When
    False the render degrades to HTML/preview only and the visual gate is skipped
    with an announcement rather than hard-failing.

    Post-playwright-migration: probes playwright + Chromium, not system Node.
    """
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        return False
    try:
        import subprocess, sys as _sys
        # Use the same launch args as _browser.py to avoid a false-positive probe.
        r = subprocess.run(
            [_sys.executable, "-c",
             "from playwright.sync_api import sync_playwright;"
             "p=sync_playwright().start();"
             "b=p.chromium.launch(args=['--no-sandbox','--disable-gpu','--font-render-hinting=none']);"
             "b.close(); p.stop()"],
            capture_output=True, timeout=15,
        )
        return r.returncode == 0
    except Exception:
        return False


def png_freshness_issues(slides_dir: Path, png_dir: Path) -> list[str]:
    """Each slides/slide-N.html must have a png/slide-N.png whose mtime is >= the
    HTML's. A missing or *stale* PNG means Stage-3 review did not (re)run on the
    current HTML — the exact way a re-render can falsely satisfy a bare count check.
    Pure/no-subprocess so it is directly unit-testable."""
    issues: list[str] = []
    pngs_by_num = {n: p for p in png_dir.glob("slide-*.png")
                   if (n := _slide_number(p)) is not None}
    for html in sorted(slides_dir.glob("slide-*.html"), key=natural_sort_key):
        num = _slide_number(html)
        if num is None:
            continue
        png = pngs_by_num.get(num)
        if png is None:
            issues.append(f"{html.name}: no matching png/slide-{num}.png (Stage-3 review not run)")
            continue
        if png.stat().st_mtime + 1e-6 < html.stat().st_mtime:
            issues.append(
                f"slide-{num}.png is stale (older than {html.name}) — Stage-3 review "
                f"did not re-run on the current HTML; re-render this page"
            )
    return issues


class Checker:
    def __init__(self, skill_dir: Path, output_dir: Path, target: str, quiet: bool = False,
                 with_visual_qa: bool = False):
        self.skill_dir = skill_dir
        self.output_dir = output_dir
        self.target = target
        self.target_idx = STAGE_ORDER.index(target)
        self.python = sys.executable or "python3"
        self.quiet = quiet
        # Render-completeness gate: also enforce PNG-freshness + visual_qa batch.
        # Off by default so existing callers are byte-identical; the render-done
        # step turns it on. Degrades (announced skip) when node is unavailable.
        self.with_visual_qa = with_visual_qa
        self.pages: int | None = None

    def reached(self, stage: str) -> bool:
        return self.target_idx >= STAGE_ORDER.index(stage)

    def echo(self, message: str) -> None:
        if not self.quiet:
            print(message)

    def fail(self, message: str) -> None:
        raise RuntimeError(message)

    def must_file(self, path: Path) -> None:
        if not path.is_file():
            self.fail(f"missing file: {path}")

    def must_dir(self, path: Path) -> None:
        if not path.is_dir():
            self.fail(f"missing dir: {path}")

    def must_glob(self, pattern: str, label: str) -> None:
        # Deliverable filenames may carry a <deck-slug> prefix (e.g.
        # my-topic-preview.html); match by suffix pattern so both the bare
        # and slug-prefixed names satisfy the gate.
        if not any(p.is_file() for p in self.output_dir.glob(pattern)):
            self.fail(f"missing {label}: no file matching {pattern} in {self.output_dir}")

    def run_cmd(self, cmd: list[str], title: str) -> None:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return
        details: list[str] = [f"{title} failed: {' '.join(cmd)}"]
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        if out:
            details.append(f"stdout:\n{out}")
        if err:
            details.append(f"stderr:\n{err}")
        self.fail("\n".join(details))

    def latest(self, pattern: str) -> Path:
        matches = sorted(self.output_dir.glob(pattern), key=natural_sort_key)
        if not matches:
            self.fail(f"missing {pattern} in {self.output_dir}")
        return matches[-1]

    def check_step0(self) -> None:
        self.echo("== Step 0 ==")
        self.echo("[OK] step 0")

    def check_step1(self) -> None:
        self.echo("== Step 1 ==")
        interview = self.output_dir / "interview-qa.txt"
        requirements = self.output_dir / "requirements-interview.txt"
        self.must_file(interview)
        self.must_file(requirements)
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "interview",
                str(interview),
            ],
            "contract_validator interview",
        )
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "requirements-interview",
                str(requirements),
            ],
            "contract_validator requirements-interview",
        )
        self.echo("[OK] step 1")

    def check_step2(self) -> None:
        self.echo("== Step 2 ==")
        search = self.output_dir / "search.txt"
        search_brief = self.output_dir / "search-brief.txt"
        source_brief = self.output_dir / "source-brief.txt"

        if search.is_file() and search_brief.is_file():
            # harness 执行证据
            self.must_file(self.output_dir / "runtime" / "prompt-research-synth.md")
            self.run_cmd(
                [
                    self.python,
                    str(self.skill_dir / "scripts/contract_validator.py"),
                    "search",
                    str(search),
                ],
                "contract_validator search",
            )
            self.run_cmd(
                [
                    self.python,
                    str(self.skill_dir / "scripts/contract_validator.py"),
                    "search-brief",
                    str(search_brief),
                ],
                "contract_validator search-brief",
            )
        elif source_brief.is_file():
            self.run_cmd(
                [
                    self.python,
                    str(self.skill_dir / "scripts/contract_validator.py"),
                    "source-brief",
                    str(source_brief),
                ],
                "contract_validator source-brief",
            )
        else:
            self.fail(
                "missing step 2 artifacts: expected search.txt + search-brief.txt "
                "or source-brief.txt"
            )
        self.echo("[OK] step 2")

    def check_step3(self) -> None:
        self.echo("== Step 3 ==")
        # harness 执行证据
        self.must_file(self.output_dir / "runtime" / "prompt-outline.md")
        outline = self.output_dir / "outline.txt"
        self.must_file(outline)
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "outline",
                str(outline),
            ],
            "contract_validator outline",
        )
        self.echo("[OK] step 3")

    def check_step4(self) -> None:
        self.echo("== Step 4 ==")
        images_dir = self.output_dir / "images"
        planning_dir = self.output_dir / "planning"
        slides_dir = self.output_dir / "slides"
        png_dir = self.output_dir / "png"
        runtime_dir = self.output_dir / "runtime"
        self.must_dir(planning_dir)
        # harness 执行证据：每页必须有对应的 runtime prompt
        pages = load_planning_pages(planning_dir)
        if pages:
            for i in range(1, len(pages) + 1):
                self.must_file(runtime_dir / f"prompt-page-{i}.md")
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/planning_validator.py"),
                str(planning_dir),
                "--refs",
                str(self.skill_dir / "references"),
            ],
            "planning_validator",
        )
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "images",
                str(planning_dir),
            ],
            "contract_validator images (step4)",
        )
        pages = load_planning_pages(planning_dir)
        if not pages:
            self.fail("planning pages must be > 0")
        self.pages = len(pages)
        needs_external_images = any(
            isinstance(card, dict)
            and isinstance(card.get("image"), dict)
            and bool(card.get("image", {}).get("needed"))
            for page in pages
            for card in (page.get("cards") if isinstance(page.get("cards"), list) else [])  # type: ignore[union-attr]
        )
        if needs_external_images:
            self.must_dir(images_dir)
            self.run_cmd(
                [
                    self.python,
                    str(self.skill_dir / "scripts/contract_validator.py"),
                    "images",
                    str(planning_dir),
                    "--require-paths",
                ],
                "contract_validator images --require-paths",
            )

        self.must_dir(slides_dir)
        slides = sorted(slides_dir.glob("slide-*.html"), key=natural_sort_key)
        if len(slides) != self.pages:
            self.fail(f"slide count={len(slides)} != planning pages={self.pages}")

        # PNGs are produced only by Stage-3 review. When node/puppeteer is
        # unavailable the render degrades to HTML/preview only (no screenshots),
        # so under the render-done gate we announce-skip the PNG/visual
        # requirement rather than hard-failing (never silent, never a hard stop
        # just because the visual gate could not run).
        self._check_pngs_and_visual(slides_dir, png_dir)
        self.echo(f"[OK] step 4 (pages={self.pages})")

    def _check_pngs_and_visual(self, slides_dir: Path, png_dir: Path) -> None:
        """PNG-count (+ optional freshness/visual_qa) enforcement, extracted so the
        playwright-absent announced-skip branch is behaviorally testable without the full
        check_step4 planning preamble. PNGs are produced only by Stage-3 review; when
        playwright/chromium is unavailable the render degrades to HTML/preview only, so under
        the render-done gate we announce-skip rather than hard-fail."""
        if self.with_visual_qa and not node_available():
            self.echo("[SKIP] visual gate: playwright/chromium unavailable — render degraded "
                      "to HTML/preview only; PNG + visual_qa not enforced")
            return
        self.must_dir(png_dir)
        pngs = sorted(png_dir.glob("slide-*.png"), key=natural_sort_key)
        if len(pngs) != self.pages:
            self.fail(f"png count={len(pngs)} != planning pages={self.pages}")
        if self.with_visual_qa:
            self._render_visual_gate(slides_dir, png_dir)

    def _render_visual_gate(self, slides_dir: Path, png_dir: Path) -> None:
        """Render-done gate: PNG freshness + visual_qa batch (exit != 1). This is
        the mechanical enforcement that Stage-3 review actually ran on the current
        HTML — a bare PNG count can be satisfied by stale leftovers."""
        stale = png_freshness_issues(slides_dir, png_dir)
        if stale:
            self.fail("PNG-freshness gate failed:\n  - " + "\n  - ".join(stale))
        cmd = [
            self.python, str(self.skill_dir / "scripts/visual_qa.py"), str(png_dir),
            "--planning-dir", str(self.output_dir / "planning"),
            "--html-dir", str(slides_dir),
        ]
        style = self.output_dir / "style.json"
        if style.is_file():
            cmd += ["--style", str(style)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            self.fail("visual_qa batch timed out (>300s) — treat as gate failure")
            return
        if proc.returncode == 0:
            self.echo("[OK] visual_qa batch clean")
        elif proc.returncode == 2:
            self.echo("[WARN] visual_qa batch reported warnings (exit 2) — review before ship")
        else:
            # exit 1 = FAIL; any other non-zero = crashed/unexpected -> never a silent pass.
            self.fail(f"visual_qa batch failed (exit {proc.returncode}):\n"
                      + (proc.stdout.strip() or proc.stderr.strip() or "(no output)"))

    def ensure_pages(self) -> int:
        if self.pages is not None:
            return self.pages
        planning_dir = self.output_dir / "planning"
        self.must_dir(planning_dir)
        pages = load_planning_pages(planning_dir)
        if not pages:
            self.fail("planning pages must be > 0")
        self.pages = len(pages)
        return self.pages

    def check_step35(self) -> None:
        self.echo("== Step 3.5 ==")
        # harness 执行证据
        self.must_file(self.output_dir / "runtime" / "prompt-style.md")
        style = self.output_dir / "style.json"
        self.must_file(style)
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "style",
                str(style),
            ],
            "contract_validator style",
        )
        self.echo("[OK] step 3.5")

    def check_preview(self) -> None:
        self.echo("== Preview ==")
        self.must_glob("*preview.html", "preview.html")
        ok, msg = gate_status(self.output_dir)
        if not ok:
            self.fail(f"proof gate not recorded: {msg}")
        self.echo("[OK] preview")

    def check_step5(self) -> None:
        self.echo("== Step 5 ==")
        pages = self.ensure_pages()
        png_dir = self.output_dir / "png"
        svg_dir = self.output_dir / "svg"
        manifest = self.output_dir / "delivery-manifest.json"

        self.must_glob("*preview.html", "preview.html")
        self.must_dir(png_dir)
        self.must_dir(svg_dir)
        self.must_glob("*png.pptx", "png pptx")
        self.must_glob("*svg.pptx", "svg pptx")
        self.must_file(manifest)

        pngs = sorted(png_dir.glob("slide-*.png"), key=natural_sort_key)
        svgs = sorted(svg_dir.glob("slide-*.svg"), key=natural_sort_key)
        if len(pngs) != pages:
            self.fail(f"png count={len(pngs)} != planning pages={pages}")
        if len(svgs) != pages:
            self.fail(f"svg count={len(svgs)} != planning pages={pages}")

        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "delivery-manifest",
                str(manifest),
                "--base-dir",
                str(self.output_dir),
            ],
            "contract_validator delivery-manifest",
        )
        ok, msg = gate_status(self.output_dir)
        if not ok:
            self.fail(f"proof gate not recorded: {msg}")
        self.echo("[OK] step 5")

    def run(self) -> None:
        required_scripts = [
            self.skill_dir / "scripts/contract_validator.py",
            self.skill_dir / "scripts/planning_validator.py",
        ]
        for path in required_scripts:
            self.must_file(path)

        if self.reached("0"):
            self.check_step0()
        if self.reached("1"):
            self.check_step1()
        if self.reached("2"):
            self.check_step2()
        if self.reached("3"):
            self.check_step3()
        if self.reached("3.5"):
            self.check_step35()
        if self.reached("4"):
            self.check_step4()
        if self.reached("preview"):
            self.check_preview()
        if self.reached("5"):
            self.check_step5()

        self.echo("[PASS] milestone checks passed")


def normalize_stage(raw: str) -> str:
    key = raw.strip().lower().replace(" ", "")
    stage = STAGE_ALIAS.get(key)
    if not stage:
        raise ValueError(f"unsupported stage: {raw!r}; expected one of {STAGE_ORDER}")
    return stage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run milestone acceptance checks for the PPT workflow")
    parser.add_argument("stage", help="Milestone target: 0/1/2/3/3.5/4/preview/5")
    parser.add_argument(
        "--skill-dir",
        default=str(Path(__file__).resolve().parent.parent),
        help="Skill root directory (default: auto-detected from this script)",
    )
    parser.add_argument(
        "--output-dir",
        default="ppt-output",
        help="Workflow output directory (default: ./ppt-output)",
    )
    parser.add_argument("--quiet", action="store_true", help="Only print failures")
    parser.add_argument(
        "--with-visual-qa",
        action="store_true",
        help="Render-done gate: also enforce PNG-freshness + visual_qa batch (exit != 1). "
             "Degrades to an announced skip when playwright/chromium is unavailable.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        target = normalize_stage(args.stage)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    skill_dir = Path(args.skill_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    checker = Checker(skill_dir=skill_dir, output_dir=output_dir, target=target,
                      quiet=bool(args.quiet), with_visual_qa=bool(args.with_visual_qa))
    try:
        checker.run()
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
