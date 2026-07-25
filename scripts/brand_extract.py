#!/usr/bin/env python3
"""brand_extract.py — extract a brand color shell from an external PPTX and
write a contract-valid style.json using the closest built-in base style.

Usage:
    python3 scripts/brand_extract.py <input.pptx> --output <path/style.json>
    python3 scripts/brand_extract.py <input.pptx> --output <path/style.json> \\
        --refs-dir SKILL_DIR/references --footer-text --base-style dark_tech

Output: a complete style.json that passes contract_validator.py style <path>.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB

BOARD_FILES = ["dark.md", "light.md", "vibrant.md", "cultural.md", "natural.md"]
DARK_CANDIDATE_CATEGORIES = {"dark_professional"}
LIGHT_CANDIDATE_CATEGORIES = {"light_premium"}
DARK_DEFAULT = "dark_tech"
LIGHT_DEFAULT = "blue_white"


def _load_styles_from_boards(refs_dir: Path) -> list[dict]:
    """Load all style JSON blocks from the 5 named board files. De-dup by style_id."""
    styles: list[dict] = []
    seen: set[str] = set()
    for name in BOARD_FILES:
        board = refs_dir / "styles" / name
        if not board.exists():
            continue
        text = board.read_text(encoding="utf-8")
        for raw in re.findall(r"```json\n(\{[^`]+?\})\n```", text, re.DOTALL):
            try:
                style = json.loads(raw)
            except json.JSONDecodeError:
                continue
            sid = style.get("style_id")
            if sid and sid not in seen:
                seen.add(sid)
                styles.append(style)
    return styles


def _nested_to_css_variables(style: dict) -> tuple[dict, str]:
    """Map nested style JSON → flat css_variables dict + font_family string."""
    bg = style["background"]
    card = style["card"]
    text = style["text"]
    acc = style["accent"]
    typo = style["typography"]
    css = {
        "bg_primary":    bg["primary"],
        "bg_secondary":  bg["gradient_to"],
        "card_bg_from":  card["gradient_from"],
        "card_bg_to":    card["gradient_to"],
        "card_border":   card["border"],
        "card_radius":   f"{card['border_radius']}px",
        "text_primary":  text["primary"],
        "text_secondary": text["secondary"],
        "accent_1":      acc["primary"][0],
        "accent_2":      acc["primary"][1],
        "accent_3":      acc["secondary"][0],
        "accent_4":      acc["secondary"][1],
    }
    font_family = typo["display_font"]
    return css, font_family


def select_base_style(
    shell: object,
    styles: list[dict],
    override_id: str | None,
) -> dict | None:
    """Return the best base style dict, or None if not found / no candidates.

    Never calls sys.exit — the caller (main) owns that decision.
    """
    if override_id is not None:
        for s in styles:
            if s.get("style_id") == override_id:
                return s
        return None  # caller prints error + valid IDs

    detected_mode = getattr(shell, "detected_mode", "neutral")
    if detected_mode == "dark":
        candidates = [s for s in styles if s.get("category") in DARK_CANDIDATE_CATEGORIES]
        default_id = DARK_DEFAULT
    else:
        candidates = [s for s in styles if s.get("category") in LIGHT_CANDIDATE_CATEGORIES]
        default_id = LIGHT_DEFAULT

    if not candidates:
        return None

    for s in candidates:
        if s.get("style_id") == default_id:
            return s
    return candidates[0]


def merge_shell(base: dict, shell: object, pptx_stem: str) -> dict:
    """Overlay brand colors from shell onto the base style; always writes brand_mode."""
    base_css, base_font = _nested_to_css_variables(base)

    dna = copy.deepcopy(base["decoration_dna"])
    if isinstance(dna.get("forbidden"), list) and len(dna["forbidden"]) > 5:
        dna["forbidden"] = dna["forbidden"][:5]

    detected_mode = getattr(shell, "sparse", False) and "neutral" or getattr(shell, "detected_mode", "neutral")
    # Recalculate: sparse branch still uses the detected_mode
    detected_mode = getattr(shell, "detected_mode", "neutral")

    if getattr(shell, "sparse", False):
        # Sparse: return base identity with only forbidden-trim applied
        return {
            "style_id":           base["style_id"],
            "style_name":         base["style_name"],
            "mood_keywords":      base["mood_keywords"],
            "design_soul":        base["design_soul"],
            "variation_strategy": base["variation_strategy"],
            "decoration_dna":     dna,
            "font_family":        base_font,
            "css_variables":      base_css,
            "brand_mode":         detected_mode,
        }

    # Compute style_id: MD5 of stem + sorted fill colors
    fingerprint = pptx_stem + "".join(sorted(getattr(shell, "fill_colors", [])))
    md5_hex = hashlib.md5(fingerprint.encode()).hexdigest()

    # Conditionally override 8 brand-controlled css_variables (skip empty strings)
    brand_overrides = {
        "bg_primary":    getattr(shell, "bg_primary", ""),
        "bg_secondary":  getattr(shell, "bg_secondary", ""),
        "text_primary":  getattr(shell, "text_primary", ""),
        "text_secondary": getattr(shell, "text_secondary", ""),
        "accent_1":      getattr(shell, "accent_1", ""),
        "accent_2":      getattr(shell, "accent_2", ""),
        "accent_3":      getattr(shell, "accent_3", ""),
        "accent_4":      getattr(shell, "accent_4", ""),
    }

    return {
        "style_id":           "brand_shell_" + md5_hex[:8],
        "style_name":         f"Brand Shell ({pptx_stem})",
        "mood_keywords":      base["mood_keywords"],
        "design_soul":        base["design_soul"],
        "variation_strategy": base["variation_strategy"],
        "decoration_dna":     dna,
        "font_family":        base_font,
        "css_variables": {
            **base_css,
            **{k: v for k, v in brand_overrides.items() if v},
        },
        "brand_mode": detected_mode,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract brand shell from a PPTX")
    parser.add_argument("input_pptx", help="Path to the brand PPTX file")
    parser.add_argument("--output", required=True, help="Output path for style.json")
    parser.add_argument("--refs-dir", default=None,
                        help="Path to the skill references/ dir (default: auto-detect)")
    parser.add_argument("--footer-text", action="store_true",
                        help="Include brand_footer_text in output")
    parser.add_argument("--base-style", default=None,
                        help="Override auto base-style selection with a specific style_id")
    args = parser.parse_args()

    input_path = Path(args.input_pptx).expanduser()
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 1

    if input_path.stat().st_size > _MAX_FILE_BYTES:
        print(f"Error: file exceeds 50 MB limit ({input_path.stat().st_size} bytes)", file=sys.stderr)
        return 1

    if args.refs_dir:
        refs_dir = Path(args.refs_dir).expanduser()
    else:
        refs_dir = Path(__file__).parent.parent / "references"

    # Load base styles
    styles = _load_styles_from_boards(refs_dir)

    # Probe the PPTX
    sys.path.insert(0, str(Path(__file__).parent))
    from deck_probe import probe_pptx_brand
    shell = probe_pptx_brand(input_path, footer_text=args.footer_text)

    # Select base style
    base = select_base_style(shell, styles, args.base_style)
    if base is None:
        if args.base_style:
            valid_ids = sorted(s["style_id"] for s in styles)
            print(f"Error: unknown style_id '{args.base_style}'. Valid IDs: {', '.join(valid_ids)}",
                  file=sys.stderr)
        else:
            print(f"Error: no candidate styles found for mode '{shell.detected_mode}'. "
                  f"Check board files in {refs_dir / 'styles'}.", file=sys.stderr)
        return 1

    # Merge brand shell
    output = merge_shell(base, shell, input_path.stem)

    if args.footer_text and shell.footer_text:
        output["brand_footer_text"] = shell.footer_text

    # Write output
    out_path = Path(args.output).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    # Post-write contract validation
    from contract_validator import validate_style
    result, _ = validate_style(out_path)
    if result.errors:
        print("Error: output failed contract_validator style check:", file=sys.stderr)
        for e in result.errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    print(f"brand_extract: wrote {out_path} (brand_mode={output['brand_mode']}, "
          f"base={base['style_id']}, sparse={shell.sparse})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
