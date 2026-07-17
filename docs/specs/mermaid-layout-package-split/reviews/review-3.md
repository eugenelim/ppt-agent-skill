# Adversarial review 3 — pre-EXECUTE spec/plan review (third pass)

## Blockers fixed

**1. T5 missing NODE_H.** Added to routing import.

**2. T6 missing RANK_GAP, GROUP_CAP.** Added to renderer import.

**3. T7 missing _arrowhead.** Added to strategies routing import.

**4. _ICON_DIR path breaks after split.** parent.parent → parent.parent.parent noted in
T2 and spec § _constants.py. This is the one non-pure-copy change.

## Concerns fixed

**4. T7 dead alias _node_render_h as _nh.** Removed.

## Nits

**5. Dead imports in various tasks.** To be trimmed during implementation.

**6. _DIRECTIVE_LABELS missing from spec renderer list.** Added.

## Next: fourth adversarial pass pending.
