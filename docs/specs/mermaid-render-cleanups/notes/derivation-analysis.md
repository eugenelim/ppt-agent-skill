# Derivation faithfulness analysis (arrow-semantics-cleanup)

Definitions:
- `arrow ≡ tk != NONE` where `tk = _marker_kind(target_marker)`
- `bidir ≡ sk == ARROW and tk == ARROW` where `sk = _marker_kind(source_marker)`

## Writer census → marker intent after migration

| Site | Old | New markers | arrow | bidir |
|------|-----|-------------|-------|-------|
| `_parser.py:568/576` flowchart | `arrow=has_arrow, bidir=is_bidir` + markers | markers kept (drop kwargs) | =has_arrow | =is_bidir |
| `_parser.py:325/339/445` notes | `arrow=False` | none (drop kwarg) | False | False |
| `statediagram.py:442` | `arrow=True` | target=ARROW | True | False |
| `_strategies.py:1375` ER-rel | `arrow=False`+card | none (drop) | False | False |
| `_strategies.py:1773` class | `arrow=True`+markers | markers kept (drop arrow) | per marker | per marker |
| `_strategies.py:4043/4046` arch `<-->` (2 edges) | `arrow=True` | target=ARROW | True | False |
| `_strategies.py:4051` arch `<--` | `arrow=True` | target=ARROW | True | False |
| `_strategies.py:4056` arch `-->`/`--` | `arrow=(op=='-->')` | target=ARROW iff `-->` | =that | False |
| `_strategies.py:4376` requirement | `arrow=True` | target=ARROW | True | False |
| `er.py:368` | `arrow=False` | none (drop) | False | False |
| `architecture.py:428` arch `<-->` | `arrow=True,bidir=True` | source=ARROW,target=ARROW | True | True |
| `architecture.py:432` arch `<--` | `arrow=True` | target=ARROW | True | False |
| `architecture.py:436` arch `-->`/`--` | `arrow=(op=='-->')` | target=ARROW iff `-->` | =that | False |
| `native_svg.py:189` class | `arrow=True`+markers | markers kept (drop arrow) | per marker | per marker |
| `_layered.py:189`/`_layout.py:140` dummy | `arrow=False` | none (drop) | False | False |
| `_layered.py:193`/`_layout.py:143` final | `arrow=e.arrow` (bidir never copied) | copy **target_marker only** | =orig | False |

Every site's post-migration `arrow`/`bidir` equals its old value. ✅ Note the
dummy-chain final segment copies **only** `target_marker`: the old code copied
just the `arrow` bool and left `bidir` at its `False` default, so copying
`source_marker` too would have flipped `bidir` True for a multi-rank `<-->`
edge (source arrowhead the old code never emitted). Copying target-only
reproduces the old `arrow` exactly and keeps `bidir` False.

## Reader census → resolution

- `_routing.py` all `if e.arrow` geometry/marker_id (806, 827, 852…1261) — property, faithful for flowchart/state/req/arch; class `ah` invisible (marker_id wins in `_renderer.py:792`).
- `_routing.py:814,818` class gate `... and e.arrow` — **remove the `and e.arrow`** (class arrow always True ⇒ redundant; keeping it would drop the aggregation source-marker whose `target_marker==NONE`).
- `_strategies.py:5121` `dst_mk = _tm_kind if _tm_kind!=NONE else (ARROW if e.arrow else NONE)` — **simplify to `dst_mk = _tm_kind`** (writers now authoritative).
- `_strategies.py:5326` `if _e_obj.arrow` (sets `arrow-normal`) — property; ELK route dict is flowchart, target-only arrow correct.
- `_strategies.py:5353` `"bidir": _e_obj.bidir` — property.
- `_renderer.py:653` `getattr(e,"bidir",False)` — property.
- `architecture.py:226` `getattr(e,"bidir",False)`, `:234` `getattr(e,"arrow",True)` — property; builds LayoutEdge markers, faithful.
- `paint.py` / `svg_serializer.py` — key on route-dict `ah`/`marker_id`/`bidir` and `LayoutEdge` markers; no `_Edge` field access. No change.

## Residual risk (reasoned; snapshot suite run to confirm no fixture drift)

These are **reasoned, not fixture-covered** — no existing fixture is known to
exercise them. The `--run-snapshots` pixel oracle is run as the backstop: any
unexpected drift here fails the gate and is investigated.

- Class self-loop with a source-only marker: old drew the generic `ah` triangle
  (`e.arrow` was always True), new draws none (`arrow ≡ target!=NONE` is False).
  In the `_renderer.py` path the *visible* marker is `marker_end`/`marker_start`
  driven by `marker_id`/`mid` (`_renderer.py:784-788`), and the class marker_id
  is still emitted (the ungated cls branch), so the loss of `ah` is invisible
  there; `ah` only feeds the `data-arrow` *attribute* (`_renderer.py:792`). In
  the `paint.py` path `ah` is a visible polygon — but a self-loop that
  *aggregates a class with itself* is a nonsensical construct absent from the
  fixture corpus. **Accepted residual.**
- Class plain association `--` (both markers NONE) reaching the ELK route-dict
  path: old `e.arrow=True`→`arrow-normal`, new none. Class diagrams do not route
  through the ELK route-dict path. **Accepted residual.**
