# Graphori

[![Install from skills.sh](https://skills.sh/b/dotoricode/graphori)](https://skills.sh/dotoricode/graphori)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

An Agent Skill that turns a coding task into a dependency graph, decides for
itself which parts can run at the same time, and picks a model per step.

![Dori, Graphori's acorn operations engineer](assets/brand/hero.png)

[한국어](README.ko.md) · [Install](docs/public/INSTALL.md) · [Trust model](docs/public/TRUST.md) · [Limitations](docs/public/LIMITATIONS.md)

## The problem

Work that could run at the same time usually runs one step after another,
because the agent has no plan that says which steps are independent.

You can fix that by hand. Write "research these three things in parallel, then
implement" and a capable agent will do it. But now you are the planner: you
decide what splits, you decide what waits, you decide who does what, and you
redo that thinking for every task.

Graphori moves that decision into the agent. You describe the outcome. It
builds the graph, and the graph is what decides what runs together.

## What happens when you use it

You give your agent a task in plain language:

```text
/graphori:graphori add rate limiting to the public API and cover it with tests
```

Graphori then does four things.

**It plans a graph, not a list.** Every step is a node with explicit
dependencies. Nodes with no dependency between them are free to run together;
nodes that need an earlier result wait for it. Nothing is parallel because you
asked for parallelism — it is parallel because the graph says the two nodes
never touch each other.

**It drops the steps you don't need.** A one-line fix does not get a research
phase. Teams that have nothing to do are marked omitted, with the reason, in
the plan you see before anything runs.

**It picks a model per node.** A mechanical edit and a design decision do not
need the same model, so they do not get the same one.

**It verifies before calling anything done.** Every implementation node gets a
verification node that runs an actual command. "Complete" means that command
passed.

## The five teams

Graphori plans against five roles. Each node belongs to exactly one, and each
run uses only the ones the task needs.

| Team | What it does | When it appears |
| --- | --- | --- |
| **Planning** | Builds the graph, assigns roles, collects results. Your agent session is this role. | Always |
| **Research** | Gathers what the change depends on — external sources, or the current shape of the code. | When your wording asks for it (`research`, `조사`, `리서치`, "check the docs") |
| **Design** | Decides an approach before code is written. | When your wording asks for it (`design`, `architecture`, `설계`) alongside a change |
| **Implementation** | Writes the change, inside a declared write scope. | Almost always |
| **Verification** | Runs the check and records an independent verdict. | Whenever something was implemented |

Which teams appear is decided by matching words in what you wrote, not by the
planner judging your task. Asking to "research the rate limit options and then
implement them" gets you a research phase; "fix the typo" does not. That is
worth knowing, because it means you can ask for a phase and get it.

Implementation and verification are always separate nodes with separate roles,
so nothing signs off on its own work. That separation comes from the planner
building the graph that way — the event layer checks that a verdict comes from
a verifier, not that the verifier is a different agent than the worker.

A typical small fix uses Planning, Implementation, and Verification, and says
so:

```text
Research · Omitted
No external research is needed for this request.
```

## How it decides to run things in parallel

Splitting work is not free. Two agents mean two startups, context handed to
both, and results merged at the end. Graphori only splits when the split wins:

```
gain = (time if run one after another)
     − (longest single node + startup for each + handoff + merge)

split only when gain ≥ max(30 seconds, 15% of the sequential time)
```

Below that line it stays in one session, because the coordination would cost
more than the wait. Two nodes run concurrently by default; a run can raise that
when the graph genuinely has more independent work.

This is the part you would otherwise be doing in your head every time.

## How it picks a model

Each node is classified by what it demands, and each class has a minimum
capability score. Graphori keeps every model that clears the bar and has the
right capability, then takes the **fastest** one left.

| Node kind | Minimum coding index |
| --- | ---: |
| Routine | 42 |
| Bounded implementation | 48 |
| General or complex implementation | 56 |
| Design | 56 |
| Verification | 56 |
| Critical synthesis | 64 |

The scores come from a pinned snapshot of the
[Artificial Analysis Coding Agent Index](https://artificialanalysis.ai/agents/coding-agents)
(v1.3), stored in the repository so a routing decision can be replayed later.

| Model | Provider | Coding index by effort | Approval |
| --- | --- | --- | --- |
| `gpt-5.6-luna` | Codex | 42 medium · 51 high | normal |
| `gpt-5.6-terra` | Codex | 48 medium · 56 high · 57 xhigh | normal |
| `gpt-5.6-sol` | Codex | 61 medium · 64 high · 65 xhigh | **premium** |
| `claude-sonnet-5` | Claude Code | not in the snapshot — see below | normal |
| `claude-opus-5` | Claude Code | 62 medium · 63 high · 67 xhigh | **premium** |

Three rules sit on top of the scores:

**Faster wins, but the current route gets the benefit of the doubt.** Among
everything that qualifies, Graphori takes the lowest expected wall time. A
model far above the bar is not better for a node that only needs the bar. One
exception keeps routes from flapping: if the run already prefers a model, a
rival has to be more than 10% faster to displace it.

**Normal before premium.** `gpt-5.6-sol` and `claude-opus-5` are gated.
Graphori considers them only when the qualifying set contains no normal-class
model at all, and when it does reach for one it stops and asks. The approval is
bounded to that node, model family, effort ceiling, and write scope — it is not
reusable for the rest of the run.

**An unscored model is marked as such.** `claude-sonnet-5` has no entry in the
pinned snapshot. Rather than borrowing a number, Graphori lets an unscored
model qualify — always for research, design, and verification, and for coding
only when nothing scored is available — and records the node as
`BENCHMARK_PARTIAL_PROVIDER_ONLY` with partial confidence. So a route can be
chosen without clearing a floor; when that happens the plan says so instead of
inventing a score.

If a provider CLI is missing or not signed in, the route falls back to an
available one and records why, instead of failing the node.

## What you get

Compared with prompting an agent yourself:

- You describe the outcome. The decomposition is not your job any more.
- Parallelism happens when it pays, not when you remember to ask for it.
- Steps you don't need are omitted out loud, so the plan is short and you can
  see the reasoning before it runs.

Compared with orchestrators that fan out by default:

- Small work stays in one session. In a controlled comparison, dropping a
  second AI reviewer that never found anything halved the AI calls.
- Completion is a check that passed, not a model reporting success.
- Every routing decision, verdict, and check is written to an append-only local
  journal you can replay.

## Install

Run this inside your agent. Full details and other routes are in
[INSTALL.md](docs/public/INSTALL.md).

### Claude Code

```text
/plugin marketplace add dotoricode/graphori
/plugin install graphori@graphori
```

Restart, then `/graphori:graphori <your task>`.

### Codex

```sh
codex plugin marketplace add dotoricode/graphori
codex plugin add graphori@graphori
```

New session, then `$graphori:graphori <your task>`.

The Skill is all you need. A separate Python runtime is available if you want a
`graphori` command line, journal replay, and resume; it is optional and
documented in [INSTALL.md](docs/public/INSTALL.md).

## What was measured

Three experiments settled current defaults. All three said "don't", and the
defaults follow.

**Does a second AI reviewer catch what the first missed?** Two Python tasks,
four runs per arm, Codex only. It found nothing, and cost twice as much. So v2
does not run one.

| Metric | With second reviewer | Without | Change |
| --- | ---: | ---: | ---: |
| Hidden checks passed | 4/4 | 4/4 | same |
| Issues the reviewer found | 0 | n/a | — |
| AI calls | 8 | 4 | −50% |
| Median completion | 48.5 s | 32.1 s | −34% |
| Fresh input tokens | 170,784 | 65,905 | −61% |

Small sample, reconstructed from commit `93c5fcf` rather than replayed. It does
not predict your codebase. Recompute it from the retained artifacts:

```sh
python benchmarks/v1_v2/verify_results.py
```

[Method](benchmarks/v1_v2/PROTOCOL.en.md) · [Report](benchmarks/v1_v2/REPORT.en.md) · [Raw data](benchmarks/v1_v2/raw-results.json)

**Should Graphori attach other Agent Skills to a node automatically?** It can
bind an external Skill to a step. Two skills were used as probes — `ponytail`
and `tdd`, both third-party Skills, not part of Graphori. Auto-binding did not
help in any provider/workload cell, and on Codex the TDD skill made results
worse. Automatic Skill selection is therefore **off**; you can still bind one
deliberately.

| Experiment | Samples | Result |
| --- | ---: | --- |
| [Both direct routes reliable?](docs/archive/research/RRC-04_DIRECT_ROUTE_BASELINE.md) | 24 | 24/24 checks passed, no scope violations — both kept |
| [Auto-bind `ponytail`?](docs/archive/research/RRC-05A_PONYTAIL_EFFECTIVENESS.md) | 22 | no benefit in any cell — not enabled |
| [Auto-bind `tdd`?](docs/archive/research/RRC-05B_TDD_EFFECTIVENESS.md) | 24 | harmful on Codex — not enabled |

## Limits worth knowing

- Graphori is not a sandbox. A provider you authorize can edit files and run
  commands. Use narrow write scopes and version control.
- A check proves what its command asserts, and nothing else.
- A heartbeat means the provider is alive, not that it is making progress.
- `0.9.0-beta.1` is a beta and the name says so. No stable API, and nothing is
  published to a package registry yet.
- Orca integration exists as an optional adapter and is currently off.
- Windows and Linux are exercised, and the maintainer develops on macOS. What
  macOS does not have is a recorded fixture run, so the
  [portability contract](docs/architecture/PORTABILITY_CONTRACT.md) still lists
  it as unverified — daily use is not the same evidence as a platform suite.

## Documentation

- [Product guide](docs/public/README.md) — start here
- [Architecture](docs/architecture/GRAPHORI_ARCHITECTURE.md) and [event protocol](docs/architecture/EVENT_PROTOCOL.md)
- [Decision records](docs/decisions/README.md) — why the defaults are what they are
- [CONTEXT.md](CONTEXT.md) — the vocabulary the code and docs share
- [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)
- [docs/archive/](docs/archive/README.md) — build and review records kept for provenance

## License

MIT. See [LICENSE](LICENSE).
