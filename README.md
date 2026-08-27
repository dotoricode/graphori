# Graphori

[![Install from skills.sh](https://skills.sh/b/dotoricode/graphori)](https://skills.sh/dotoricode/graphori)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

An Agent Skill that plans a coding task, delegates only where a second agent
earns its keep, and decides completion from checks it ran rather than from an
agent reporting success.

![Dori, Graphori's acorn operations engineer](assets/brand/hero.png)

[한국어](README.ko.md) · [Trust model](docs/public/TRUST.md) · [Limitations](docs/public/LIMITATIONS.md) · [Security](SECURITY.md)

## Why

Fanning out to several agents before knowing whether the work needs them costs
tokens on small tasks, and it hides failures behind a confident summary.

Graphori starts in one session and splits work only at boundaries where the
split pays for itself. Every step records the command that judged it, so
"complete" means a check passed.

## Install

Pick your agent. Both commands run inside the tool.

### Claude Code

```text
/plugin marketplace add dotoricode/graphori
/plugin install graphori@graphori
```

Restart Claude Code, then:

```text
/graphori:graphori plan, implement, and verify this task end to end.
```

### Codex

```sh
codex plugin marketplace add dotoricode/graphori
codex plugin add graphori@graphori
```

Start a new session, then:

```text
$graphori:graphori plan, implement, and verify this task end to end.
```

Skills land in `~/.claude/skills` for Claude Code and `~/.agents/skills` for
Codex. [INSTALL.md](docs/public/INSTALL.md) covers the other routes: `npx
skills`, a readable shell script over `gh`, and project-local copies.

## The optional runtime

The Skill works on its own. Add the Python runtime only if you want the
`graphori` CLI, an append-only journal, replay, or resume:

```sh
gh repo clone dotoricode/graphori -- --depth 1
cd graphori
./scripts/install_graphori.sh --mode runtime --dry-run   # prints, changes nothing
./scripts/install_graphori.sh --mode runtime
graphori doctor --lang en
```

Then plan and run a change. Store the root in a variable and quote it, so a
path with spaces cannot split into two arguments:

```sh
repo_root="$(pwd -P)"
graphori run "add a docstring to the parser" \
  --root "$repo_root" \
  --write-scope src/parser.py \
  --verify-command python -m unittest tests.test_parser
```

On Windows PowerShell:

```powershell
$root = (Get-Location).Path
graphori plan "add a docstring to the parser" --root $root --lang en
```

`--write-scope` bounds what the run may touch. `--verify-command` is the check
that decides the verdict. Leave it out and Graphori picks a default for the
workspace — the unit test suite, then `compileall`, then `git diff --check` —
which is weaker than a check you chose yourself.

## What the numbers say

I expected a second AI reviewer to make small coding tasks safer. In a
controlled comparison it found nothing the first pass missed, at twice the
cost. Graphori v2 dropped it.

| Metric | v1-style | v2 | Change |
| --- | ---: | ---: | ---: |
| Hidden checks passed | 4/4 | 4/4 | same |
| Scope violations | 0 | 0 | same |
| Issues found by the second AI | 0 | n/a | — |
| AI calls | 8 | 4 | −50% |
| Median completion | 48.5 s | 32.1 s | −34% |
| Fresh input tokens | 170,784 | 65,905 | −61% |

Four runs per arm, two Python tasks, Codex only. The v1-style arm is a
reconstruction from commit `93c5fcf`, not a replay of historical runs. This is
a small sample and it does not predict your codebase.

Recompute it from the retained artifacts:

```sh
python benchmarks/v1_v2/verify_results.py
```

[Method](benchmarks/v1_v2/PROTOCOL.en.md) · [Report](benchmarks/v1_v2/REPORT.en.md) · [Raw data](benchmarks/v1_v2/raw-results.json)

Three routing experiments settled other defaults, all of them negative
results that turned a feature off:

| Experiment | Samples | Result |
| --- | ---: | --- |
| [Direct Codex + Claude baseline](docs/archive/research/RRC-04_DIRECT_ROUTE_BASELINE.md) | 24 | 24/24 checks passed — both routes kept |
| [Ponytail auto-selection](docs/archive/research/RRC-05A_PONYTAIL_EFFECTIVENESS.md) | 22 | no benefit in any cell — not enabled |
| [TDD auto-selection](docs/archive/research/RRC-05B_TDD_EFFECTIVENESS.md) | 24 | harmful on Codex — left manual |

A wider Direct vs v1 vs v2 protocol is published under [`benchmarks/`](benchmarks/),
but its 72-run study has not been run and nothing is claimed for it.

## What it is not

Graphori is not a sandbox. A provider you authorize can edit files and run
commands. Use narrow write scopes, version control, and human review for
anything risky.

Other limits worth knowing before you install:

- A check proves what its command asserts, and nothing else.
- Provider progress can go dark during a long run. A heartbeat means alive,
  not advancing.
- Optional Skill auto-selection is off on purpose; the measurements above are why.
- `0.1.0` is the version that opens this source line. Earlier tags such as
  `v0.9.0-beta.1` predate the public source and do not describe it. No stable
  API yet.
- Orca integration exists as an optional adapter and is currently disabled.

## Supported platforms

| | Skill | CLI: `plan`, `doctor` | CLI: `run`, `resume` |
| --- | --- | --- | --- |
| Windows | yes | yes | yes, exercised |
| Linux | yes | yes | yes, exercised |
| macOS | yes | yes | implemented, not yet exercised |

The journal takes an exclusive advisory lock so two writers can never
interleave: `flock` on POSIX, `msvcrt.locking` on Windows. A platform with
neither fails closed rather than running unprotected.

macOS runs the same POSIX code path as Linux, but the
[portability contract](docs/architecture/PORTABILITY_CONTRACT.md) holds macOS
at `deferred/unknown` until the platform fixtures are run on a macOS host. The
table says "implemented" rather than "supported" for that reason.

The suite is 397 tests. The last full run on Windows with Python 3.12 passed
with 5 skipped. The skip count is environment-dependent: fixtures opt out when
a macOS-only tool is missing, when symlink creation needs privileges the host
does not grant, and when live-provider tests are not enabled.

## Release checks

This repository has no GitHub Actions. Maintainers run a fail-closed gate
locally before publishing:

```sh
python3.11 scripts/verify_public_release.py --output build/release-artifacts
```

It runs the tests, secret and dependency audits, package builds, isolated
installs, SBOM generation, and hashing. It never publishes, deploys, or
rewrites history. [RELEASE_GATE.md](docs/public/RELEASE_GATE.md) documents the
procedure and the evidence each step must produce; the artifacts themselves are
written to `build/release-artifacts` and are not committed.

## Documentation

- [Product guide](docs/public/README.md) — start here
- [Architecture](docs/architecture/GRAPHORI_ARCHITECTURE.md) and [event protocol](docs/architecture/EVENT_PROTOCOL.md)
- [Decision records](docs/decisions/README.md) — why the defaults are what they are
- [v1 to v2 history](docs/public/HISTORY.md)
- [CONTEXT.md](CONTEXT.md) — the domain vocabulary the code and docs both use
- [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md) · [Changelog](CHANGELOG.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)
- [docs/archive/](docs/archive/README.md) — build and review records kept for provenance

## License

MIT. See [LICENSE](LICENSE).
