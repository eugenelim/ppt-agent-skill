"""mermaid_render.themes — theme palettes and page-wrapping for the render module.

Provides:
- THEME_ADAPTIVE_DARK / THEME_ADAPTIVE_LIGHT: brand-neutral WCAG-AA palettes
- Theme type alias
- render_page(): unified page factory routing theme → full standalone HTML
  (named render_page, not make_page, to avoid collision with layout._renderer.make_page)
"""
from __future__ import annotations

from typing import Union

Theme = Union[str, dict, None]

THEME_ADAPTIVE_DARK: dict[str, str] = {
    "--card-bg-from":    "#1C2033",
    "--card-bg-to":      "#161929",
    "--card-border":     "#2D3454",
    "--text-primary":    "#E8EDF7",
    "--text-secondary":  "#94A3B8",
    "--accent-1":        "#60A5FA",
    "--accent-2":        "#34D399",
    "--accent-3":        "#FBBF24",
    "--accent-4":        "#A78BFA",
    "--bg-primary":      "#0F1117",
    "--edge-label-bg":   "#1C2033",
    "--font-primary":    "-apple-system,Inter,sans-serif",
    "--node-shadow":     "0 1px 3px rgba(0,0,0,0.4),0 1px 0 rgba(0,0,0,0.2)",
    "--node-radius":     "8px",
    "--group-radius":    "8px",
}

THEME_ADAPTIVE_LIGHT: dict[str, str] = {
    "--card-bg-from":    "#FFFFFF",
    "--card-bg-to":      "#F5F4F0",
    "--card-border":     "#E2E0D8",
    "--text-primary":    "#1A1916",
    "--text-secondary":  "#6B6860",
    "--accent-1":        "#2563EB",
    "--accent-2":        "#059669",
    "--accent-3":        "#D97706",
    "--accent-4":        "#7C3AED",
    "--bg-primary":      "#FAFAF9",
    "--edge-label-bg":   "#F5F4F0",
    "--font-primary":    "-apple-system,Inter,sans-serif",
    "--node-shadow":     "0 1px 3px rgba(0,0,0,0.08),0 1px 0 rgba(0,0,0,0.03)",
    "--node-radius":     "8px",
    "--group-radius":    "8px",
}


def _css_vars(d: dict[str, str]) -> str:
    return "\n".join(f"    {k}: {v};" for k, v in d.items())


def make_adaptive_page(fragment: str) -> str:
    """Wrap fragment in CSS-var-driven HTML with auto prefers-color-scheme.

    Dark by default; switches to light via media query. Host pages can override
    the CSS vars to adapt the diagram to their own design system.
    """
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<style>\n"
        f"  :root {{\n{_css_vars(THEME_ADAPTIVE_DARK)}\n  }}\n"
        "  @media (prefers-color-scheme: light) {\n"
        f"    :root {{\n{_css_vars(THEME_ADAPTIVE_LIGHT)}\n    }}\n"
        "  }\n"
        "  body { margin: 0; padding: 24px;\n"
        "    background: var(--bg-primary, #FAFAF9);\n"
        "    font-family: var(--font-primary, -apple-system, Inter, sans-serif); }\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"{fragment}\n"
        "</body>\n"
        "</html>"
    )


def make_baked_page(fragment: str, palette: dict[str, str]) -> str:
    """Wrap fragment in full HTML with concretely baked CSS vars (no media query).

    Used by to_svg / to_png to produce a stable, medium-agnostic output.
    Also used when the caller passes an explicit dict theme.
    """
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<style>\n"
        f"  :root {{\n{_css_vars(palette)}\n  }}\n"
        "  body { margin: 0; padding: 24px;\n"
        "    background: var(--bg-primary, #FAFAF9);\n"
        "    font-family: var(--font-primary, -apple-system, Inter, sans-serif); }\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"{fragment}\n"
        "</body>\n"
        "</html>"
    )


def render_page(fragment: str, theme: Theme = None) -> str:
    """Unified page factory for mermaid_render's public API.

    theme=None | "adaptive" | "auto"  → CSS-var-driven adaptive (prefers-color-scheme)
    theme="light" | "adaptive-light"  → baked adaptive light palette
    theme="dark"  | "adaptive-dark"   → baked adaptive dark palette
    theme=dict                        → baked with the caller's vars
    """
    if theme is None or theme in ("adaptive", "auto"):
        return make_adaptive_page(fragment)
    if isinstance(theme, dict):
        return make_baked_page(fragment, theme)
    if theme in ("light", "adaptive-light"):
        return make_baked_page(fragment, THEME_ADAPTIVE_LIGHT)
    if theme in ("dark", "adaptive-dark"):
        return make_baked_page(fragment, THEME_ADAPTIVE_DARK)
    raise ValueError(
        f"unknown theme {theme!r}; expected None, 'adaptive', 'auto', 'light', "
        "'adaptive-light', 'dark', 'adaptive-dark', or a dict of CSS vars"
    )
