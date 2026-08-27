# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

static HTML/CSS/JavaScript; delegated to the existing repository because the learning artifact must open offline without a build step.

## Users

- Primary user: a Graphori task director or maintainer who needs to understand what a run did without reading every code diff.
- Learning user: the same person, or a new learner, who benefits from a 12-year-old-friendly explanation and active practice.

## Product Purpose

Graphori turns a large request into a graph of smaller work nodes, records the work and verification evidence, and makes the result explainable. During work, the planning team keeps the monitoring dashboard alive and coordinates the graph. After work, the learning surface explains the finished task, its structure, and its evidence in plain language.

## Positioning

Graphori's distinctive mechanism is graph-based orchestration: independent work nodes can be fanned out at the same time and later joined at a verification point, while a journal preserves the event history used to reconstruct status and replay evidence.

## Operating Context

Users run Graphori from a terminal or an agent harness such as Claude Code or Codex. The current repository includes a generic terminal runner, JSONL journal, status/replay commands, a journal-backed dashboard server, and an optional Orca adapter. The dashboard is a monitoring view for multiple concurrent sessions; it is not the main product outcome.

## Capabilities and Constraints

- Current CLI can run one generic worker command safely inside a configured root.
- Current journal records ordered events with digest links and supports replay verification.
- Current dashboard exposes snapshot and SSE event paths and separates liveness, progress, and verdict clocks.
- Current baseline CLI does not yet automatically launch planning, research, implementation, and verification sessions as separate real teams; that multi-team scene is a design target and learning simulation.
- The learning HTML must distinguish real executable behavior from design simulation.
- The learning HTML must stay self-contained and usable offline, with no external font or script dependency.
- The visual world must use a single font, five distinct human employees, and state-specific motion that communicates walking, planning, reading, drawing, typing, inspecting, resting, and sleeping without relying on labels alone.

## Brand Commitments

Graphori is the product name. The interface should be honest about the current implementation versus the intended architecture, concrete rather than marketing-led, and understandable to a 12-year-old.

## Evidence on Hand

- `docs/GRAPHORI_FUNCTION_GUIDE.md` documents the current CLI, journal, status, replay, dashboard, and adapter behavior.
- `docs/archive/research/GRAPHORI_LEARNING_RESEARCH.md` records the learning principles used by the game.
- `docs/GRAPHORI_LEARNING_GAME.html` is the existing offline learning artifact and the target for the replacement visual world.
- No production customer claims, benchmark numbers, or external brand assets were supplied; future work must not invent them.

## Product Principles

1. Show the graph mechanism before the monitoring chrome.
2. Keep real behavior and design simulation visibly separate.
3. Teach one concept, ask the learner to use it, then show evidence.
4. Make concurrent work understandable through spatial structure and purposeful motion.
5. Explain the finished result in task language before exposing raw technical evidence.
