# Diff-mode adversarial review — pass 1

Verdict: not clean (3 Blockers, 2 Concerns, 1 Nit). Wiring confirmed correct/complete.

## Blockers

**1. Spec Status not flipped despite complete implementation.** `docs/specs/persistent-chrome-flag/spec.md:3`. Fix: set spec Status + README row to Implementing/Shipped; set plan Status to Executing/Done.

**2. Every Acceptance Criterion still unchecked on a shipping spec.** `docs/specs/persistent-chrome-flag/spec.md:117`. Fix: mark AC2–AC7 met; AC1 after finding 3.

**3. AC1's required read-through result is not recorded.** `docs/specs/persistent-chrome-flag/plan.md:44`. Fix: append a dated read-through record to the plan Changelog stating the five checks were run and passed.

## Concerns

**4. Footer reserves ~56px for columns that will mostly render empty under the omit rule.** `references/design-runtime/design-specs.md:114`. Fix: map footer col2 = section label, col3 = page number (per-page fields already cited), or shrink the band.

**5. Masthead slot to deck_chrome mapping is left implicit.** `references/prompts/step4/tpl-page-html.md:42`. Fix: pin brand-left = deck_chrome.title, subtitle-center = deck_chrome.subtitle, revision-right = page number/omitted, in the page-html flag-gated block.

## Nits

**6. Plan risk section says 720px vertical budget.** `docs/specs/persistent-chrome-flag/plan.md:263`. Fix: reword to "within the 720px canvas height (580px content area)".
