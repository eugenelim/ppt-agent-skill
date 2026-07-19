#!/usr/bin/env python3
"""test_gallery_toggle.py — construction check for the gallery cover/detail toggle.

Pins the **emitted-markup contract** of `gallery.build_index_html` (a build-time
check, not a JS-behavior test): given synthetic styles under a temp GALLERY_DIR,
a style with both tiers emits a toggle control (`class="tier-toggle"` +
`card has-both`) with correct `data-cover`/`data-detail` URLs; a style with only
one tier emits none; the global switch is always present; the both-tier default
face is the cover. The runtime swap/guard behavior of the inline `setTier` JS
(clicking Detail actually changes `iframe.src`, the `if(!url) return` degradation
guard) is verified by the T1 manual-QA transcript, not here. See
docs/specs/gallery-title-detail-tiers/. No pytest harness required — run directly
or via `smoke_test.py --phase 1` (wired into its subprocess self-checks). Exit
0 = all pass, 1 = a failure.
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import gallery as G  # noqa: E402


if __name__ == "__main__":
    FAILS: list[str] = []


    def check(name: str, cond: bool) -> None:
        print(("PASS " if cond else "FAIL ") + name)
        if not cond:
            FAILS.append(name)


    def _style(sid: str) -> dict:
        return {
            "style_id": sid, "style_name": sid, "inspiration": "insp",
            "design_soul": "soul", "mood_keywords": ["a", "b", "c"],
            "background": {"primary": "#111111"},
            "accent": {"primary": ["#222222"], "secondary": ["#333333"]},
        }


    def main() -> int:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "both.html").write_text("<html></html>", encoding="utf-8")
        (tmp / "both.cover.html").write_text("<html></html>", encoding="utf-8")
        (tmp / "onlydetail.html").write_text("<html></html>", encoding="utf-8")
        (tmp / "onlycover.cover.html").write_text("<html></html>", encoding="utf-8")

        G.GALLERY_DIR = tmp  # redirect filesystem-presence checks to the fixture
        grouped = {c: [] for c in G.CATEGORY_ORDER}
        grouped["dark_professional"] = [_style("both"), _style("onlydetail"), _style("onlycover")]
        html = G.build_index_html(grouped)

        # both-tier style → exactly one toggle, marked has-both, correct tier URLs
        check("both-tier card carries has-both",
              'class="card has-both" data-cover="both.cover.html" data-detail="both.html"' in html)
        check("exactly one per-card toggle rendered",
              html.count('class="tier-toggle"') == 1)

        # one-tier styles → no toggle, empty missing-tier attr, still a card
        check("detail-only card has empty data-cover + no toggle",
              'data-cover="" data-detail="onlydetail.html"' in html)
        check("cover-only card has empty data-detail + no toggle",
              'data-cover="onlycover.cover.html" data-detail=""' in html)

        # default face is cover-first (both-tier iframe/open point at the cover)
        both_card = re.search(r'data-cover="both\.cover\.html".*?</div>\s*</div>\s*</div>', html, re.DOTALL)
        check("both-tier default iframe src is the cover",
              both_card is not None and 'src="both.cover.html"' in both_card.group(0))

        # global switch always present, default Cover active
        check("global tierswitch present with Cover default active",
              'class="tierswitch"' in html and 'data-tier="cover" class="active"' in html)

        if FAILS:
            print(f"\n{len(FAILS)} FAILED: " + ", ".join(FAILS))
            return 1
        print("\nAll gallery-toggle construction checks passed.")
        return 0


    if __name__ == "__main__":
        sys.exit(main())
