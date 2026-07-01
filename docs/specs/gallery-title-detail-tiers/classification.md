# T0 — Tier classification of the 29 existing `<id>.html` mocks

Each existing `<id>.html` is classified **cover-primary** (title/identity slide —
needs a net-new *detail* authored + its cover relocated to `<id>.cover.html`) or
**detail-primary** (multi-section content slide — keep as `<id>.html`, author a
net-new *cover*). The 3 styles that already ship both tiers are **complete**.

Method: visual pass over each rendered `<id>.png` / hero composite (block-element
count is *not* used — it counts decoration, not content; e.g. `royal_red` is a
15-block title cover, `cyberpunk_neon` is a 101-block hero cover).

## dark_professional (8)

| style | current `<id>.html` | class | net-new |
|-------|---------------------|-------|---------|
| dark_tech | "Intelligence, at the edge." + 3 stats + gauge | cover-primary | detail |
| xiaomi_orange | "让性能不再设限" + 3 stats | cover-primary | detail |
| luxury_purple | "Æternum" pure title | cover-primary | detail |
| nocturne_violet | "Designed for the dreamers" + stats | cover-primary | detail |
| cyberpunk_neon | "JACK IN" + HUD panels | cover-primary | detail |
| chrome_y2k | "DIGITAL FUTURE" | cover-primary | detail |
| noir_film | "The City Awakens" photo-essay cover | cover-primary | detail |
| graphite_gold | advisory-card grid | detail-primary | **complete** (cover exists) |

## light_premium (10)

| style | current `<id>.html` | class | net-new |
|-------|---------------------|-------|---------|
| blue_white | "Enterprise-grade…" + 3 stats + CTA | cover-primary | detail |
| fresh_green | "Quiet rituals…" + 3 product cards | cover-primary | detail *(borderline)* |
| minimal_gray | "The Quiet Revolution" essay + evidence + swatches | **detail-primary** | cover |
| mocha_editorial | "Models that think…" editorial | cover-primary | detail *(borderline)* |
| medical_pulse | "精准数字心血管预警系统" ECG dashboard + 4 stats | **detail-primary** | cover |
| earth_concrete | "构造城市之肌理 042/12" + project meta | cover-primary | detail |
| champagne_gold | "Marie & Étienne" wedding invitation | cover-primary | detail |
| liquid_glass | "Liquid Glass" + 3 stat cards | cover-primary | detail |
| editorial_paper | research essay | detail-primary | **complete** (cover exists) |
| schematic_blueprint | RACI worksheet table | detail-primary | **complete** (cover exists) |

## vibrant (4)

| style | current `<id>.html` | class | net-new |
|-------|---------------------|-------|---------|
| vibrant_rainbow | "Payments, reimagined." + 3 stat cards | cover-primary | detail |
| kindergarten_pop | hero + 3 cards | cover-primary | detail |
| bauhaus_block | "Less is more" + 3 principle cards + plate + curator meta | **detail-primary** | cover *(borderline)* |
| candy_pastel | "Douceur de printemps" + 3 product cards | cover-primary | detail |

## cultural_oriental (3)

| style | current `<id>.html` | class | net-new |
|-------|---------------------|-------|---------|
| royal_red | "千年文脉·当代新生" prologue title (verified) | cover-primary | detail |
| sakura_wabi | 侘寂 minimal title | cover-primary | detail |
| ink_jade | 道之茶 title | cover-primary | detail |

## natural_retro (4)

| style | current `<id>.html` | class | net-new |
|-------|---------------------|-------|---------|
| botanic_forest | "Wild Places…" + 3 stats | cover-primary | detail |
| safari_savanna | "Serengeti Sunrise." + coordinates + map | cover-primary | detail *(borderline)* |
| retro_70s | "STAY GROOVY." + 3 stat cards + vinyl | cover-primary | detail |
| gov_authority | "全面推进高质量发展" keynote title + stats | cover-primary | detail |

## Derived authoring split

- **Complete (both tiers already):** 3 — graphite_gold, editorial_paper, schematic_blueprint.
- **detail-primary → author a COVER (no relocation):** 3 — minimal_gray, medical_pulse, bauhaus_block.
- **cover-primary → relocate cover to `<id>.cover.html` (git mv) + author a DETAIL:** 23 — all others.

**Net-new slides to author: 26** = **23 details + 3 covers** (predominantly
details). **Relocations (git mv): 23.** Total tier-fixtures at the end: 58
(29 covers + 29 details).

*Borderline calls* (fresh_green, mocha_editorial, safari_savanna as cover-primary;
bauhaus_block as detail-primary) may flip on closer authoring inspection; a flip
changes only whether that style's net-new slide is a cover or a detail (and
whether it relocates), not the total of 26. Re-record here if flipped during T4.
