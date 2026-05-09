# PPT Agent Skill

**[中文文档](README.md)**

> A **world-class** AI-powered presentation generator. Simulates the complete workflow of a top-tier PPT design company (quoted at $1,000+/page), outputting high-quality HTML presentations + editable vector PPTX files.
>
> Quality benchmarked against the actual typography practices of **Linear / Anthropic / Stripe / Apple / NYT / Tom Ford / Pitch / Mercury / Vercel** and other top brands.

## Workflow

```
Requirements Interview → Research → Outline → Planning Draft → Style + Images + HTML Design → Post-processing (SVG + PPTX)
```

## Key Features

| Feature | Description |
|---------|-------------|
| **6-Step Pipeline** | Requirements → Research → Outline → Planning → Design → Post-processing |
| **26 World-Class Styles** | 5 categories ｜ Mirrors actual typography of Linear / Anthropic / Stripe / Apple / NYT / Tom Ford |
| **18 Data Visualizations** | 8 basic + 6 advanced + 4 ECharts-grade (world map / network / Sankey / heatmap calendar) |
| **Bento Grid Layout** | 7 flexible card-based layouts driven by content, not templates |
| **World-Class Typography** | 7-level scale + letter-spacing rules + tabular-nums + OpenType features + serif italic mixing + 3-tier font fallback |
| **Smart Illustrations** | AI-generated images with 5 visual fusion techniques |
| **Failure Modes Catalog** | 8 documented failure modes (underfill / support_collapse / decorative_substitution etc.) + repair order |
| **Cross-page Narrative** | Density alternation, chapter color progression, cover-ending visual echo |
| **Style Preview Gallery** | `gallery.py` one-shot generates a 26-style card-wall index page |
| **Smoke Testing** | `smoke_test.py` validates JSON / pipeline-compat / typography rules |
| **PPTX Compatible** | HTML → SVG → PPTX pipeline, right-click "Convert to Shape" in PPT 365 for full editing |

## Output

| File | Description |
|------|-------------|
| `preview.html` | Browser-based paginated preview (auto-generated) |
| `presentation.pptx` | PPTX file, right-click "Convert to Shape" in PPT 365 for editing |
| `svg/*.svg` | Per-page vector SVG, drag into PPT directly |
| `slides/*.html` | Per-page HTML source files |

## Requirements

**Required:**
- **Node.js** >= 18 (Puppeteer + dom-to-svg)
- **Python** >= 3.8
- **python-pptx** (PPTX generation)

**Quick Install:**
```bash
pip install python-pptx lxml Pillow
npm install puppeteer dom-to-svg
```

## Directory Structure

```
ppt-agent-skill/
  SKILL.md                    # Main workflow instructions (Agent entry point)
  README.md                   # Chinese documentation (default)
  README_EN.md                # This file
  references/
    prompts.md                # 5 Prompt templates
    style-system.md           # 8 preset styles + CSS variables
    bento-grid.md             # 7 layout specs + card types
    method.md                 # Core methodology
  scripts/
    html_packager.py          # Merge multi-page HTML into paginated preview
    html2svg.py               # HTML → SVG (dom-to-svg, preserves editable text)
    svg2pptx.py               # SVG → PPTX (OOXML native SVG embedding)
```

## Usage

Just describe your needs in the conversation to trigger the skill. The Agent will automatically execute the full 6-step workflow:

```
You: "Make a PPT about X"
  → Agent interviews you for requirements (waits for your reply)
  → Auto research → outline → planning draft → per-page HTML design
  → Auto post-processing: HTML → SVG → PPTX
  → All outputs saved to ppt-output/
```

**Trigger Examples**:

| Scenario | What to Say |
|----------|-------------|
| Topic only | "Make a PPT about X" / "Create a presentation on Y" |
| With source material | "Turn this document into slides" / "Make a PPT from this report" |
| With requirements | "15-page dark tech style AI safety presentation" |
| Implicit trigger | "I need to present to my boss about Y" / "Make training materials" |

> No manual script execution needed. All post-processing (preview merge, SVG conversion, PPTX generation) is handled automatically by the Agent in Step 6.

## Technical Architecture

```
HTML slides
  → [Puppeteer] → [dom-to-svg] → SVG (editable <text>)
  → [python-pptx + lxml] → PPTX (OOXML svgBlip + PNG fallback)
```

## License

[MIT](LICENSE)
