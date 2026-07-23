"""Pure-Python text layout service using Pillow FreeType APIs.

Font resolution order:
  1. Explicit font_path argument
  2. MERMAID_RENDER_FONT_PATH environment variable
  3. Known Inter font locations
  4. Known Arial / Liberation Sans locations
  5. Known DejaVu Sans locations
  6. Pillow default font (last resort)

The emitted HTML font-family matches the resolved font so measurement
and browser painting use the same typeface.
"""
from __future__ import annotations

import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional, Protocol

from PIL import ImageFont

from ._geometry import (
    TextStyle, TextRun, TextLine, TextLayout,
)

# ── Font resolution ────────────────────────────────────────────────────────────

_FONT_SEARCH_PATHS: list[tuple[str, list[str]]] = [
    # Inter (preferred — matches the renderer's default CSS)
    ("Inter", [
        "/System/Library/Fonts/Supplemental/Inter.ttf",
        "/Library/Fonts/Inter.ttf",
        os.path.expanduser("~/Library/Fonts/Inter.ttf"),
        "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
        "/usr/share/fonts/inter/Inter-Regular.ttf",
    ]),
    # Arial / Liberation Sans (common fallback)
    ("Arial", [
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
        "C:\\Windows\\Fonts\\Arial.ttf",
    ]),
    # DejaVu Sans (Linux fallback)
    ("DejaVu Sans", [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]),
]

_BOLD_SEARCH_PATHS: dict[str, list[str]] = {
    "Inter": [
        "/System/Library/Fonts/Supplemental/Inter-Bold.ttf",
        "/Library/Fonts/Inter-Bold.ttf",
        os.path.expanduser("~/Library/Fonts/Inter-Bold.ttf"),
        "/usr/share/fonts/truetype/inter/Inter-Bold.ttf",
    ],
    "Arial": [
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:\\Windows\\Fonts\\ArialBD.ttf",
    ],
    "DejaVu Sans": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
}


def resolve_font(
    explicit_path: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """Return (font_path_or_None, font_family_name).

    font_path is None only when the Pillow default font is selected.
    """
    # 1. Explicit argument
    if explicit_path and Path(explicit_path).exists():
        return explicit_path, _family_from_path(explicit_path)

    # 2. Environment variable
    env_path = os.environ.get("MERMAID_RENDER_FONT_PATH", "")
    if env_path and Path(env_path).exists():
        return env_path, _family_from_path(env_path)

    # 3-5. Search known locations
    for family, paths in _FONT_SEARCH_PATHS:
        for p in paths:
            if p and Path(p).exists():
                return p, family

    # 6. Pillow default
    return None, "sans-serif"


def _family_from_path(path: str) -> str:
    name = Path(path).stem.lower()
    if "inter" in name:
        return "Inter"
    if "arial" in name or "helvetica" in name or "liberation" in name:
        return "Arial, Helvetica, sans-serif"
    if "dejavu" in name:
        return "DejaVu Sans"
    return "sans-serif"


def _find_bold_path(family: str, regular_path: Optional[str]) -> Optional[str]:
    if family in _BOLD_SEARCH_PATHS:
        for p in _BOLD_SEARCH_PATHS[family]:
            if p and Path(p).exists():
                return p
    return regular_path  # fall back to regular when bold variant not found


# ── Font object cache ──────────────────────────────────────────────────────────

@lru_cache(maxsize=256)
def _get_font(path: Optional[str], size: int, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return a cached Pillow font object."""
    if path is None:
        return ImageFont.load_default()
    try:
        if bold:
            # Try to load bold variant from same directory
            p = Path(path)
            bold_candidates = [
                p.parent / (p.stem + "-Bold" + p.suffix),
                p.parent / (p.stem + "Bold" + p.suffix),
                p.parent / (p.stem + "_bold" + p.suffix),
            ]
            family = _family_from_path(path)
            bold_path = _find_bold_path(family, None)
            if bold_path and bold_path != path and Path(bold_path).exists():
                return ImageFont.truetype(bold_path, size)
            for bc in bold_candidates:
                if bc.exists():
                    return ImageFont.truetype(str(bc), size)
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# ── Markdown-like format parser ────────────────────────────────────────────────

_MD_RE = re.compile(
    r'(\*\*(.+?)\*\*)'          # bold: **text**
    r'|(\*(.+?)\*)'             # italic: *text*
    r'|(~~(.+?)~~)'             # strikethrough: ~~text~~
    r'|(<br\s*/?>)',            # explicit line break
    re.DOTALL,
)


def parse_markdown_runs(text: str, base_style: TextStyle) -> list[tuple[str, TextStyle]]:
    """Parse **bold**, *italic*, ~~strikethrough~~ and <br> into (text, style) pairs.

    Returns a flat list; <br> is represented as ('\n', base_style).
    """
    result: list[tuple[str, TextStyle]] = []
    pos = 0
    for m in _MD_RE.finditer(text):
        start, end = m.span()
        if start > pos:
            result.append((text[pos:start], base_style))
        if m.group(1):  # bold
            result.append((m.group(2), _bold_style(base_style)))
        elif m.group(3):  # italic
            result.append((m.group(4), _italic_style(base_style)))
        elif m.group(5):  # strikethrough
            result.append((m.group(6), _strike_style(base_style)))
        elif m.group(7):  # <br>
            result.append(("\n", base_style))
        pos = end
    if pos < len(text):
        result.append((text[pos:], base_style))
    return result


def _bold_style(s: TextStyle) -> TextStyle:
    return TextStyle(
        font_size=s.font_size, font_weight=700, italic=s.italic,
        strikethrough=s.strikethrough, letter_spacing=s.letter_spacing,
        line_height_factor=s.line_height_factor,
    )


def _italic_style(s: TextStyle) -> TextStyle:
    return TextStyle(
        font_size=s.font_size, font_weight=s.font_weight, italic=True,
        strikethrough=s.strikethrough, letter_spacing=s.letter_spacing,
        line_height_factor=s.line_height_factor,
    )


def _strike_style(s: TextStyle) -> TextStyle:
    return TextStyle(
        font_size=s.font_size, font_weight=s.font_weight, italic=s.italic,
        strikethrough=True, letter_spacing=s.letter_spacing,
        line_height_factor=s.line_height_factor,
    )


# ── TextMeasurer protocol ──────────────────────────────────────────────────────

class TextMeasurer(Protocol):
    def measure_run(self, text: str, style: TextStyle) -> TextRun: ...

    def layout(
        self,
        text: str,
        style: TextStyle,
        max_width: Optional[float],
        *,
        allow_emergency_break: bool = False,
    ) -> TextLayout: ...


# ── PillowTextMeasurer ────────────────────────────────────────────────────────

class PillowTextMeasurer:
    """Measures text using Pillow FreeType APIs.

    Thread-safe via lru_cache (pure lookups) and immutable TextStyle keys.
    """

    def __init__(self, font_path: Optional[str] = None) -> None:
        resolved_path, family = resolve_font(font_path)
        self._font_path = resolved_path
        self._font_family = family

    @property
    def font_family(self) -> str:
        return self._font_family

    @property
    def font_path(self) -> Optional[str]:
        return self._font_path

    def _font(self, style: TextStyle) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        size = max(1, round(style.font_size))
        bold = style.font_weight >= 600
        return _get_font(self._font_path, size, bold)

    def _measure_single_line(self, text: str, style: TextStyle) -> tuple[float, float]:
        """Return (width, height) of a single unsplit line of text."""
        if not text:
            return 0.0, style.font_size * style.line_height_factor
        font = self._font(style)
        try:
            # getlength is the preferred API (Pillow 8+)
            w = font.getlength(text)
        except AttributeError:
            try:
                bbox = font.getbbox(text)
                w = float(bbox[2] - bbox[0])
            except Exception:
                w = len(text) * style.font_size * 0.6
        try:
            bbox = font.getbbox("Xy")
            h = float(bbox[3] - bbox[1])
        except Exception:
            h = style.font_size
        line_h = h * style.line_height_factor
        if style.letter_spacing:
            w += style.letter_spacing * max(0, len(text) - 1)
        return w, line_h

    def measure_run(self, text: str, style: TextStyle) -> TextRun:
        w, h = self._measure_single_line(text, style)
        return TextRun(text=text, style=style, width=w, height=h)

    def _break_into_tokens(self, text: str) -> list[str]:
        """Split text into break-opportunity tokens (words, hyphens, CJK chars).

        Never splits a normal Latin word into individual characters.
        """
        tokens: list[str] = []
        word = ""
        for ch in text:
            cp = ord(ch)
            if ch in (" ", "\t"):
                if word:
                    tokens.append(word)
                    word = ""
                tokens.append(ch)
            elif ch == "-":
                word += ch
                tokens.append(word)
                word = ""
            elif ch == "/":
                word += ch
                tokens.append(word)
                word = ""
            elif 0x4E00 <= cp <= 0x9FFF or 0x3040 <= cp <= 0x30FF:
                # CJK: break at character boundaries
                if word:
                    tokens.append(word)
                    word = ""
                tokens.append(ch)
            else:
                word += ch
        if word:
            tokens.append(word)
        return tokens

    def layout(
        self,
        text: str,
        style: TextStyle,
        max_width: Optional[float],
        *,
        allow_emergency_break: bool = False,
    ) -> TextLayout:
        """Wrap text into TextLayout lines respecting max_width.

        Line break opportunities:
          - explicit \\n or <br>
          - spaces
          - after hyphens
          - after slashes
          - CJK character boundaries
          - zero-width spaces (U+200B)

        Normal Latin words are NEVER split character-by-character unless
        allow_emergency_break=True and the word alone exceeds max_width.
        """
        # Normalize explicit newlines and <br>
        normalized = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        normalized = normalized.replace("\\n", "\n")
        normalized = normalized.replace("​", " ")  # ZWSP → space

        # Parse markdown runs
        runs_with_style = parse_markdown_runs(normalized, style)

        # Flatten into paragraph chunks split at \n
        paragraphs: list[list[tuple[str, TextStyle]]] = [[]]
        for raw_text, st in runs_with_style:
            parts = raw_text.split("\n")
            paragraphs[-1].append((parts[0], st))
            for part in parts[1:]:
                paragraphs.append([(part, st)])

        text_lines: list[TextLine] = []
        for para in paragraphs:
            # Wrap each paragraph
            para_lines = self._wrap_paragraph(para, style, max_width, allow_emergency_break)
            text_lines.extend(para_lines)

        if not text_lines:
            # Empty layout
            _, lh = self._measure_single_line("", style)
            empty_line = TextLine(runs=(), width=0.0, height=lh, baseline=lh * 0.8)
            text_lines = [empty_line]

        total_h = sum(ln.height for ln in text_lines)
        total_w = max(ln.width for ln in text_lines)
        nom_lh = text_lines[0].height if text_lines else style.font_size * style.line_height_factor

        # Calculate min/max content widths
        all_tokens = self._break_into_tokens(normalized.replace("\n", " "))
        min_w = max(
            (self._measure_single_line(t.strip(), style)[0] for t in all_tokens if t.strip()),
            default=0.0,
        )
        max_w, _ = self._measure_single_line(
            normalized.replace("\n", " ").replace("  ", " ").strip(), style
        )

        return TextLayout(
            lines=tuple(text_lines),
            width=total_w,
            height=total_h,
            line_height=nom_lh,
            min_content_width=min_w,
            max_content_width=max_w,
            resolved_font_path=self._font_path,
            resolved_font_family=self._font_family,
        )

    def _wrap_paragraph(
        self,
        runs: list[tuple[str, TextStyle]],
        base_style: TextStyle,
        max_width: Optional[float],
        allow_emergency_break: bool,
    ) -> list[TextLine]:
        """Wrap a single paragraph (no embedded newlines) into TextLines."""
        if max_width is None:
            # No wrap — single line
            return [self._runs_to_line(runs)]

        lines: list[TextLine] = []
        current_run_parts: list[tuple[str, TextStyle]] = []
        current_w = 0.0

        for raw_text, st in runs:
            tokens = self._break_into_tokens(raw_text)
            for tok in tokens:
                tok_w, _ = self._measure_single_line(tok, st)
                if not current_run_parts:
                    # Start of line — strip leading space
                    if tok.strip() == "":
                        continue
                    current_run_parts.append((tok, st))
                    current_w = tok_w
                elif current_w + tok_w <= max_width:
                    current_run_parts.append((tok, st))
                    current_w += tok_w
                else:
                    # Would overflow — flush current line
                    if tok.strip():  # skip pure-whitespace that triggered the break
                        if current_run_parts:
                            lines.append(self._runs_to_line(current_run_parts))
                            current_run_parts = []
                            current_w = 0.0

                        # If single token exceeds max_width
                        if tok_w > max_width:
                            if allow_emergency_break:
                                parts = self._emergency_break(tok, st, max_width)
                                for p in parts[:-1]:
                                    pw, _ = self._measure_single_line(p, st)
                                    lines.append(self._runs_to_line([(p, st)]))
                                current_run_parts = [(parts[-1], st)]
                                current_w, _ = self._measure_single_line(parts[-1], st)
                            else:
                                # Keep oversized token on its own line
                                current_run_parts = [(tok, st)]
                                current_w = tok_w
                        else:
                            current_run_parts = [(tok, st)]
                            current_w = tok_w
                    else:
                        # Whitespace token caused wrap — flush line, skip whitespace
                        if current_run_parts:
                            lines.append(self._runs_to_line(current_run_parts))
                            current_run_parts = []
                            current_w = 0.0

        if current_run_parts:
            lines.append(self._runs_to_line(current_run_parts))

        return lines or [self._runs_to_line([])]

    def _runs_to_line(self, run_parts: list[tuple[str, TextStyle]]) -> TextLine:
        """Convert (text, style) pairs into a TextLine."""
        tr_list: list[TextRun] = []
        total_w = 0.0
        max_h = 0.0
        for txt, st in run_parts:
            w, h = self._measure_single_line(txt, st)
            tr_list.append(TextRun(text=txt, style=st, width=w, height=h))
            total_w += w
            max_h = max(max_h, h)
        if not tr_list:
            _, h = self._measure_single_line("", TextStyle())
            max_h = h
        baseline = max_h * 0.8
        return TextLine(
            runs=tuple(tr_list),
            width=total_w,
            height=max_h,
            baseline=baseline,
        )

    def _emergency_break(self, tok: str, style: TextStyle, max_width: float) -> list[str]:
        """Break a single unsplittable token at character boundaries."""
        parts: list[str] = []
        current = ""
        for ch in tok:
            test = current + ch
            w, _ = self._measure_single_line(test, style)
            if w > max_width and current:
                parts.append(current)
                current = ch
            else:
                current = test
        if current:
            parts.append(current)
        return parts or [tok]


# ── HeuristicTextMeasurer (backward-compat fallback) ─────────────────────────

class HeuristicTextMeasurer:
    """Character-class bucketing measurer — same algorithm as _constants._measure_text_width.

    Used as a fallback when Pillow font loading fails or in tests without font files.
    """

    _NARROW = frozenset("iltfjI1!|.,:;'")
    _SEMI   = frozenset("()[]{}/\\-\"`")
    _WIDE   = frozenset("WMwm@%")

    def __init__(self) -> None:
        self._font_family = "sans-serif"
        self._font_path: Optional[str] = None

    @property
    def font_family(self) -> str:
        return self._font_family

    @property
    def font_path(self) -> Optional[str]:
        return self._font_path

    def _width(self, text: str, style: TextStyle) -> float:
        if not text:
            return 0.0
        fs = style.font_size
        fw = style.font_weight
        base = 0.60 if fw >= 600 else (0.57 if fw >= 500 else 0.54)
        total = 0.0
        for c in text:
            cp = ord(c)
            if 0x0300 <= cp <= 0x036F:
                ratio = 0.0
            elif c == " ":
                ratio = 0.3
            elif c in self._NARROW:
                ratio = 0.4
            elif c in self._SEMI:
                ratio = 0.5
            elif c == "r":
                ratio = 0.8
            elif c in self._WIDE:
                ratio = 1.5
            elif "A" <= c <= "Z":
                ratio = 1.2
            elif cp >= 0x4E00:
                ratio = 2.0
            else:
                ratio = 1.0
            total += ratio
        return total * fs * base + fs * 0.15

    def measure_run(self, text: str, style: TextStyle) -> TextRun:
        w = self._width(text, style)
        h = style.font_size * style.line_height_factor
        return TextRun(text=text, style=style, width=w, height=h)

    def layout(
        self,
        text: str,
        style: TextStyle,
        max_width: Optional[float],
        *,
        allow_emergency_break: bool = False,
    ) -> TextLayout:
        normalized = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        normalized = normalized.replace("\\n", "\n")

        raw_lines = normalized.split("\n")
        text_lines: list[TextLine] = []
        lh = style.font_size * style.line_height_factor

        for raw in raw_lines:
            if max_width is None:
                w = self._width(raw, style)
                tr = TextRun(text=raw, style=style, width=w, height=lh)
                text_lines.append(TextLine(
                    runs=(tr,), width=w, height=lh, baseline=lh * 0.8
                ))
            else:
                words = raw.split(" ") if raw else [""]
                cur = ""
                for word in words:
                    test = (cur + " " + word).strip() if cur else word
                    if self._width(test, style) <= max_width:
                        cur = test
                    else:
                        if cur:
                            cw = self._width(cur, style)
                            tr = TextRun(text=cur, style=style, width=cw, height=lh)
                            text_lines.append(TextLine(
                                runs=(tr,), width=cw, height=lh, baseline=lh * 0.8
                            ))
                        cur = word
                if cur:
                    cw = self._width(cur, style)
                    tr = TextRun(text=cur, style=style, width=cw, height=lh)
                    text_lines.append(TextLine(
                        runs=(tr,), width=cw, height=lh, baseline=lh * 0.8
                    ))

        if not text_lines:
            tr = TextRun(text="", style=style, width=0.0, height=lh)
            text_lines = [TextLine(runs=(tr,), width=0.0, height=lh, baseline=lh * 0.8)]

        total_h = sum(ln.height for ln in text_lines)
        total_w = max(ln.width for ln in text_lines)
        words_flat = normalized.replace("\n", " ").split()
        min_w = max((self._width(w, style) for w in words_flat), default=0.0)
        max_w = self._width(normalized.replace("\n", " "), style)

        return TextLayout(
            lines=tuple(text_lines),
            width=total_w,
            height=total_h,
            line_height=lh,
            min_content_width=min_w,
            max_content_width=max_w,
            resolved_font_path=None,
            resolved_font_family="sans-serif",
        )


# ── Module-level singleton (lazy) ─────────────────────────────────────────────

_DEFAULT_MEASURER: Optional[PillowTextMeasurer | HeuristicTextMeasurer] = None


def get_default_measurer() -> PillowTextMeasurer | HeuristicTextMeasurer:
    """Return the process-wide default measurer (PillowTextMeasurer when fonts available)."""
    global _DEFAULT_MEASURER
    if _DEFAULT_MEASURER is None:
        path, _ = resolve_font()
        if path is not None:
            _DEFAULT_MEASURER = PillowTextMeasurer(path)
        else:
            _DEFAULT_MEASURER = HeuristicTextMeasurer()
    return _DEFAULT_MEASURER
