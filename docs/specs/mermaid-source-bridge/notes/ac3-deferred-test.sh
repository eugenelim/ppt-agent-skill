#!/usr/bin/env bash
# AC3 deferred test: CSS variable inheritance under three style variants.
#
# Blocked on diagram-consistency-system shipping its recipe family CSS overrides.
# Run this once that spec reaches Implementing + the recipe family HTML is available.
#
# Usage: bash docs/specs/mermaid-source-bridge/notes/ac3-deferred-test.sh
#
# Expected outcome: visual_qa.py returns non-FAIL for all three style variants,
# confirming that node fill, border, and edge stroke inherit from deck CSS variables.

set -euo pipefail
SKILL_DIR="$(git rev-parse --show-toplevel)"
cd "$SKILL_DIR"

printf 'flowchart TB\n  A[Ingest] --> B[Process]\n  B --> C[Store]' > /tmp/ac3-test.mmd
python3 scripts/mermaid_layout.py --source @/tmp/ac3-test.mmd --output /tmp/ac3-fragment.html

for STYLE in dark light editorial; do
    # Wrap fragment in minimal HTML with deck :root CSS variables from style.json
    STYLE_JSON=$(find . -name "${STYLE}.json" -path "*/styles/*" | head -1)
    if [ -z "$STYLE_JSON" ]; then
        echo "SKIP: style ${STYLE}.json not found"
        continue
    fi
    echo "Testing style: $STYLE ($STYLE_JSON)"
    cat > /tmp/ac3-wrapper-${STYLE}.html << HTMLEOF
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
/* Inject deck CSS variables here — replace with actual :root from style pipeline */
:root {
  --card-bg-from: #1e1e2e;
  --card-bg-to: #181825;
  --card-border: rgba(255,255,255,0.12);
  --text-primary: #cdd6f4;
  --text-secondary: #a6adc8;
  --accent-1: #89b4fa;
  --accent-2: #cba6f7;
  --font-primary: 'Inter', sans-serif;
}
body { background: #11111b; padding: 40px; }
</style>
</head>
<body>
$(cat /tmp/ac3-fragment.html)
</body>
</html>
HTMLEOF
    python3 scripts/html2png.py /tmp/ac3-wrapper-${STYLE}.html /tmp/ac3-${STYLE}.png
    RESULT=$(python3 scripts/visual_qa.py /tmp/ac3-${STYLE}.png 2>&1)
    if echo "$RESULT" | grep -qi "FAIL"; then
        echo "FAIL: visual_qa returned failure for style $STYLE"
        echo "$RESULT"
    else
        echo "PASS: visual_qa non-FAIL for style $STYLE"
    fi
done

echo "AC3 test complete."
