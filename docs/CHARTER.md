# Charter

> The foundational document for this project. One page, read whole.
> Modeled on the [CNCF project charter pattern](https://contribute.cncf.io/maintainers/governance/charter/):
> mission, scope, and principles in a single place, kept stable and short.

Changes to this file go through an RFC. The rest of the docs in this repo
are scaffolding around it; this file is the why.

---

## Mission

Turn a one-line prompt into a presentation indistinguishable from the work of a
premium design agency — by giving an AI agent the complete workflow of one
(research, planning, design, render) rather than a template to fill.

## Scope

What this project does:

- Runs a **research-first, 6-step pipeline** (needs research → material
  collection → outline → planning → HTML design → post-process) that produces a
  multi-page deck from a prompt, or from user-supplied source material.
- Ships **HTML pages plus an editable vector PPTX** — text stays editable in
  PowerPoint, not flattened to images — via the HTML → SVG → PPTX toolchain.
- Carries a curated **design resource library** — 26 world-class styles, ~18
  data visualizations, Bento-grid layouts, and typographic rules — that the
  agent routes over per page rather than reinventing.
- Drives **content-driven layout and global style consistency**: the deck's
  structure follows its content, and one style definition recolors every page.

What this project does **not** do:

- **Fill a template.** The whole point is the opposite — research and content
  decide structure; we do not slot text into fixed slide masters.
- **Host, serve, or deploy anything.** It is a local Claude Code skill that
  writes files to `ppt-output/`; there is no running service, account, or API.
- **Provide a live/WYSIWYG editor or real-time collaboration.** The editable
  PPTX is the handoff; ongoing editing happens in PowerPoint, not here.
- **Manage brand assets or act as a general design tool.** Scope is
  presentations; it is not a DAM, a document generator, or a web-page builder.

The "does not" list is at least as important as the "does" list. It's how
we — and AI agents working in the repo — know when a request is out of
bounds. If you find the project being asked to do things that aren't on
either list, that's a signal to refine this section, not to drift.

## Principles

The values that resolve ties when reasonable people disagree.

1. **Research before pixels.** Content is decided before design is touched —
   rendering is deliberately the *last* of the six steps, so a weak argument is
   caught when it's cheap to fix, not after a page is styled.
2. **Ground design in real implementations, not screenshots.** Styles benchmark
   how world-class brands actually build their pages (real CSS — kerning rules,
   tabular-nums, OpenType features, layered font-stack fallback), not a
   resemblance to a thumbnail.
3. **Editability is non-negotiable.** Text survives as text the whole way down
   the HTML → SVG → PPTX pipeline; the deliverable is something a human can keep
   working on, never a wall of flattened images.
4. **Consistency comes from tokens, not discipline.** Every page references CSS
   variables with no hardcoded colors, so global coherence is structural — swap
   one `style.json` and all pages recolor.
5. **Degrade, don't fail.** The pipeline senses its environment and steps down
   gracefully — no Node.js → emit `preview.html` only; no image generation →
   fall back to CSS-only decoration — rather than aborting the run.
6. **Name the failure modes and fix them in order.** Known failure modes
   (underfill, decorative substitution, …) are catalogued with a fixed repair
   order, so quality is a checklist the agent can follow, not a matter of taste.

## What's NOT in this charter

To keep this file from becoming everything-and-the-kitchen-sink:

- **Decision history** lives in [`adr/`](adr/). The charter is what we
  believe; ADRs are the choices we made because of those beliefs.
- **Current product state** lives in [`product/`](product/). The charter
  is direction; product/ is where we are.
- **Current architecture state** lives in [`architecture/`](architecture/).
- **Conventions for how we work** live in [`CONVENTIONS.md`](CONVENTIONS.md).
- **Governance** (roles, decision-making processes, voting) lives in
  [`GOVERNANCE.md`](GOVERNANCE.md) if and when the project is large
  enough to need it. Most small/medium projects don't — a single
  maintainer or small group operating by consensus is fine, and forcing
  governance ceremony on a project that doesn't need it produces theater,
  not clarity.

## When to revise

Revise this charter when:

- The mission has actually changed (rare — usually means a fork).
- The scope has shifted enough that PRs are routinely landing for things
  the current scope doesn't cover.
- A principle has stopped resolving ties — it's being ignored, or it
  contradicts another principle in ways we haven't acknowledged.

Revise via RFC. Editing the charter directly without discussion is the
single fastest way to lose the trust this document is meant to build.
