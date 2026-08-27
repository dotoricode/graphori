# Graphori

[![Install Graphori from skills.sh](https://skills.sh/b/dotoricode/graphori)](https://skills.sh/dotoricode/graphori)

![Dori, Graphori's acorn operations engineer](assets/brand/hero.png)

## Give Graphori a coding task. It plans the steps, uses only the agents that help, and checks the result.

Graphori does not start an agent swarm by default. Small work stays in one session.
Larger work is split only at useful boundaries, and completion is judged from recorded
checks instead of an agent saying “done.”

[한국어](README.ko.md) · [Trust](docs/public/TRUST.md) · [Limitations](docs/public/LIMITATIONS.md) · [Security](SECURITY.md)

## Measured v1-style vs v2 result

I originally expected a second AI reviewer to make small coding tasks safer. In this
controlled comparison it found no new issue. The v2 candidate kept the same hidden-
check result with half as many AI calls.

| Metric | v1-style reconstruction | Graphori v2 candidate | Change |
| --- | ---: | ---: | ---: |
| Hidden checks passed | 4/4 | 4/4 | Same |
| Completion claim matched result | 4/4 | 4/4 | Same |
| Scope violations | 0 | 0 | Same |
| AI calls | 8 | 4 | **-50.0%** |
| Median completion time | 48.542 s | 32.110 s | **-33.9%** |
| Total input tokens | 567,584 | 333,681 | **-41.2%** |
| Cached input tokens | 396,800 | 267,776 | **-32.5%** |
| Fresh input tokens | 170,784 | 65,905 | **-61.4%** |
| Output tokens | 4,960 | 3,309 | **-33.3%** |
| New issues found by the second AI | 0 | Not applicable | — |
| Provider cost | Not recorded | Not recorded | Unknown |

Small controlled comparison: `n=4` per arm, two Python tasks run twice per arm,
Codex only. v1-style reconstructed its design from commit `93c5fcf`; it did not replay
historical runs. Fresh input is derived as total minus cached input. These numbers do
not predict every coding task.

[Method](benchmarks/v1_v2/PROTOCOL.en.md) · [Full report](benchmarks/v1_v2/REPORT.en.md) · [Raw data](benchmarks/v1_v2/raw-results.json) · [Corrected result](benchmarks/v1_v2/results.json) · [Verifier](benchmarks/v1_v2/verify_results.py)

Recalculate the retained result locally:

```sh
python benchmarks/v1_v2/verify_results.py
```

The broader Direct vs v1-style vs v2 protocol is published under
[`benchmarks/`](benchmarks/), but its planned 72-run study has **not** been run. No
result is claimed for it.

## Other decisions backed by measurements

These are routing experiments, not additions to the performance table above.

| Experiment | Samples | Result | Product decision |
| --- | ---: | --- | --- |
| Direct Codex + Claude baseline | 24 | 24/24 deterministic checks passed; 0 scope violations, rework, or self-report disagreements | Keep both direct routes |
| Ponytail auto-selection | 22 | 4/4 provider/workload cells: `NO_BENEFIT` | Do not auto-select |
| TDD auto-selection | 24 | Codex: `HARMFUL`; Claude: `MANUAL_ONLY` | Keep automatic selection off |

[Direct baseline](docs/research/RRC-04_DIRECT_ROUTE_BASELINE.md) · [Ponytail result](docs/research/RRC-05A_PONYTAIL_EFFECTIVENESS.md) · [TDD result](docs/research/RRC-05B_TDD_EFFECTIVENESS.md)

## Install the Agent Skill

### Codex

```sh
codex plugin marketplace add dotoricode/graphori
codex plugin add graphori@graphori
codex plugin list
```

Start a new Codex session. The list should show `graphori@graphori` as enabled. Then:

```text
$graphori:graphori plan, implement, and verify this task end to end. Respond in English.
```

Codex stores user Skills under `~/.agents/skills`; Graphori does not install them under
the retired `~/.codex/skills` path.

### Claude Code

Run these inside Claude Code:

```text
/plugin marketplace add dotoricode/graphori
/plugin install graphori@graphori
/plugin list
```

Restart Claude Code after an install or update. The plugin details should show the
`graphori` and `graphori-dashboard` Skills. Then:

```text
/graphori:graphori plan, implement, and verify this task end to end. Respond in English.
```

Claude Code stores user Skills under `~/.claude/skills`.

## Preview or install without a plugin marketplace

Preview the repository with the open [`skills`](https://github.com/vercel-labs/skills)
CLI:

```sh
npx skills add dotoricode/graphori --list
```

Project-local Codex install:

```sh
npx skills add dotoricode/graphori --skill graphori --agent codex --copy
```

Project-local Claude Code install:

```sh
npx skills add dotoricode/graphori --skill graphori --agent claude-code --copy
```

These commands intentionally omit `--global` because the CLI's current Codex global
path differs from Codex's official user Skill path. Node.js 22.20 or newer is required.

Prefer `gh` and a readable local script instead of npm? Preview before copying:

```sh
gh repo clone dotoricode/graphori -- --depth 1
cd graphori
./scripts/install_graphori.sh --mode solo --target codex --dry-run
./scripts/install_graphori.sh --mode solo --target codex
```

Change `--target codex` to `--target claude` for Claude Code. The installer refuses to
replace a different Skill without `--force`; forced replacement creates a timestamped
backup. Windows PowerShell uses `scripts/install_graphori.ps1` with `-Mode solo` and
`-Target codex` or `claude`.

The exact personal destinations are `~/.agents/skills/graphori` for Codex and
`~/.claude/skills/graphori` for Claude Code.

## Optional Runtime

The Agent Skill works without Graphori's Python Runtime. Clone the repository and add
the Runtime only when you need the `graphori` CLI, deterministic verification, journal
replay, or resume:

```sh
gh repo clone dotoricode/graphori -- --depth 1
cd graphori
./scripts/install_graphori.sh --mode runtime --dry-run
./scripts/install_graphori.sh --mode runtime
graphori doctor --lang en
```

The installer performs a local pip install of the checkout. Use a virtual environment
if you do not want to change the current interpreter.

Example:

```sh
repo_root="$(pwd -P)"
graphori run "implement a small change" --root "$repo_root" \
  --write-scope src/example.py \
  --verify-command python -m unittest tests.test_example
```

Windows PowerShell:

```powershell
$root = (Get-Location).Path
graphori plan "implement a small change" --root $root --lang en
```

`--lang auto` is the default. An explicit language wins; otherwise Graphori uses the
objective language, configured preference, process locale, then English. Locale is a
presentation choice and does not enter plan, journal, or projection digests.

## Trust at a glance

| Agent Skill | Optional Runtime |
| --- | --- |
| Plain Markdown and metadata | Open-source Python package |
| No executable bundled in the Skill directories | No hidden daemon or Graphori telemetry |
| Preview before installation | Append-only local journal and read-only replay |
| Separate Codex and Claude install paths | Local release gate builds, audits, installs, and hashes artifacts |

Graphori is not a sandbox. A provider or verifier that you authorize can modify files
or run commands. Use narrow write scopes, version control, explicit checks, and human
review for risky work. Read the [trust model](docs/public/TRUST.md).

## Public source gate — 2026-08-27

These checks were run locally without GitHub Actions immediately before and after the
public push. They are release evidence, not an independent security certification.

| Check | Measured result |
| --- | ---: |
| Python 3.11 test suite | 401 passed, 6 skipped |
| Retained v1/v2 artifact verifier | 8/8 hidden checks passed, 0 scope violations |
| Gitleaks, clean public history and tree | 0 secrets found |
| Installed Runtime dependency audit | 0 known vulnerabilities found |
| Package build | wheel + sdist built; Twine check passed; SBOM + SHA-256 generated |
| Public GitHub native plugin install | Codex 1/1, Claude Code 1/1; version `0.1.0` |
| Installed Skill manifests vs public source | Codex match, Claude Code match |
| Authenticated English behavior E2E | Codex 2/2 tests; Claude Code 3/3 tests |

The live E2E tasks each used a fresh disposable Git repository, changed only the two
requested files, produced an English final report, and spawned no subagent.

## Current verification and limits

- Python 3.11+ is supported; the local suite is tested before every public push.
- Native marketplace installation is tested separately for Codex and Claude Code.
- Direct Codex and Claude Code adapters are supported; Orca execution is disabled.
- Provider progress can be unavailable during a long run.
- Optional Skill auto-selection is intentionally off.
- A check proves only what its command and assertions cover.
- Graphori v2 is the architecture generation; `0.1.0` is the first public source
  version. No stable API is promised.

This repository does not use GitHub Actions. Maintainers run the fail-closed release
gate locally:

```sh
python3.11 scripts/verify_public_release.py --output build/release-artifacts
```

It runs tests, secret and dependency audits, package builds, isolated installs, SBOM
generation, and hashes. It does not publish, deploy, change visibility, or rewrite Git
history. See the [release gate](docs/public/RELEASE_GATE.md).

## Documentation

- [Public product guide](docs/public/README.md)
- [v1 to v2 history](docs/public/HISTORY.md)
- [Architecture](docs/architecture/GRAPHORI_ARCHITECTURE.md)
- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Changelog](CHANGELOG.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
- Maintainer context: [CONTEXT.md](CONTEXT.md), [PRODUCT.md](PRODUCT.md),
  [DESIGN.md](DESIGN.md), [TEAM_TOPOLOGY.md](TEAM_TOPOLOGY.md), and
  [design-qa.md](design-qa.md)
