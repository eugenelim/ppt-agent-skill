#!/usr/bin/env bash
# build-print.sh — combine a multi-file HTML slide deck into one print/PDF view.
#
# Harvested authoring pattern (see references/playbooks/print-combiner-playbook.md).
# A deck laid out as: index.html (nav shell) + slide-NN.html (one page each) +
# css/styles.css (single style source). This regenerates <deck>/index-print.html —
# all pages concatenated into one scrollable document with landscape print CSS, so
# the browser's Print -> Save as PDF exports the whole deck.
#
# Run after adding/removing/reordering slides.
# Usage: ./scripts/build-print.sh <deck-dir>

set -euo pipefail

DECK_DIR="${1:-.}"
cd "$DECK_DIR"

if [[ ! -f index.html ]]; then
  echo "Error: no index.html in '$DECK_DIR' (expected index.html + slide-*.html + css/styles.css)" >&2
  exit 1
fi

# Page order: index.html first, then slide-NN.html sorted.
PAGES=("index.html")
for f in $(ls slide-*.html 2>/dev/null | sort); do
  PAGES+=("$f")
done
TOTAL=${#PAGES[@]}

TITLE=$(sed -n 's/.*<title>\(.*\)<\/title>.*/\1/p' index.html | head -1)

# Extract each file's #slide-container inner markup, in order.
ALL_SLIDES=$(python3 -c "
import re, sys
for page in sys.argv[1:]:
    with open(page, encoding='utf-8') as f:
        html = f.read()
    m = re.search(r'<div id=\"slide-container\">(.*?)</div>\s*\n\s*<a class=\"nav-btn\"', html, re.DOTALL)
    if not m:
        m = re.search(r'<div id=\"slide-container\">(.*?)</div>', html, re.DOTALL)
    if m:
        print(m.group(1).strip())
" "${PAGES[@]}")

cat > index-print.html << ENDOFPRINT
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${TITLE} — Print View</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="css/styles.css">
  <style>
    body { overflow: auto !important; display: block !important; min-height: auto !important; background: #000; }
    #slide-container { position: static !important; width: auto !important; height: auto !important; display: block !important; }
    .slide {
      position: relative !important; opacity: 1 !important; pointer-events: all !important;
      width: var(--slide-width); height: var(--slide-height);
      margin: 20px auto; border: 1px solid #333;
    }
    .nav-btn, .slide-counter, .draft { display: none !important; }
    .print-toolbar {
      position: fixed; top: 0; left: 0; right: 0; z-index: 200;
      display: flex; align-items: center; gap: 12px; padding: 8px 16px;
      background: var(--card2); border-bottom: 1px solid var(--line);
      font-family: var(--font-heading); font-size: 12px;
    }
    .print-toolbar a, .print-toolbar button {
      color: var(--muted); text-decoration: none; cursor: pointer;
      background: var(--card); border: 1px solid var(--line);
      padding: 5px 12px; border-radius: 5px; font-size: 12px; font-family: var(--font-heading);
    }
    .print-toolbar a:hover, .print-toolbar button:hover { color: var(--gold); border-color: var(--gold); }
    .print-toolbar span { color: var(--muted); }
    @media print {
      html { font-size: 11px !important; }
      body { background: transparent !important; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
      @page { size: landscape; margin: 0; }
      .print-toolbar { display: none !important; }
      #slide-container { padding-top: 0 !important; }
      .slide {
        display: flex !important; width: 100vw !important; height: 100vh !important;
        margin: 0 !important; border: none !important; overflow: hidden !important;
        page-break-after: always; break-after: page; page-break-inside: avoid; break-inside: avoid;
      }
      .slide:last-child { page-break-after: auto; break-after: auto; }
      .slide * { animation: none !important; }
    }
  </style>
</head>
<body>
  <div class="print-toolbar">
    <a href="index.html">&larr; Back</a>
    <button onclick="window.print()">&#9113; Print / Save as PDF</button>
    <span>${TOTAL} slides</span>
  </div>
  <div id="slide-container" style="padding-top:44px;">
${ALL_SLIDES}
  </div>
</body>
</html>
ENDOFPRINT

echo "Built ${DECK_DIR%/}/index-print.html from $TOTAL page(s)"
