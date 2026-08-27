# Graphori

![Dori, Graphori's acorn operations engineer](assets/brand/hero.png)

## Fewer agents. Every result verified.

Graphori plans coding work as a graph, runs only the agents it needs, and verifies the result with recorded evidence. Its local-first journal can replay what was planned, dispatched, and verified without trusting an agent's memory. It is not a hosted service or a promise that autonomous agents are correct.

[한국어 안내](README.ko.md) · [Trust model](docs/public/TRUST.md) · [History and evidence](docs/public/HISTORY.md) · [Limitations](docs/public/LIMITATIONS.md) · [Security](SECURITY.md)

## Public beta boundary

The beta supports Python 3.11+, local Codex or Claude Code command-line adapters, a deterministic generic verifier, an append-only run journal, and read-only replay. Providers, credentials, network access, and a final human decision remain outside Graphori's authority. See the [public product guide](docs/public/README.md) before using it on a repository you care about.

## Install

From a checkout, inspect the exact action first:

```sh
./scripts/install_graphori.sh --mode runtime --dry-run
./scripts/install_graphori.sh --mode solo --dry-run
```

Install the runtime into the selected Python environment, or install the Graphori Skill for a Solo session:

```sh
./scripts/install_graphori.sh --mode runtime
./scripts/install_graphori.sh --mode solo --target codex
```

The installer never uploads code, starts a provider, or replaces a differing Skill without `--force`. The runtime command performs a local `pip install` of this checkout; use a virtual environment when you do not want to change the current interpreter.

## First plan

```sh
repo_root="$(pwd -P)"
graphori plan "implement a small change" --root "$repo_root" --lang en
```

`--lang auto` (the default) prefers the objective language, then the configured or process locale. Language remains a presentation choice: it never enters a plan, journal, or digest. Start work only with an explicit verification command:

Set a project preference in `.graphori/config.json`, or a user preference in `$XDG_CONFIG_HOME/graphori/config.json` (normally `~/.config/graphori/config.json`): `{"language":"en"}`. An explicit `--lang` still wins.

```sh
graphori run "implement a small change" --root "$repo_root" \
  --write-scope src/example.py \
  --verify-command python -m unittest tests.test_example
```

Windows PowerShell:

```powershell
$root = (Get-Location).Path
graphori plan "implement a small change" --root $root --lang en
```

Use `graphori doctor`, `status`, and `replay` to inspect local state. A non-terminal run is resumed only from its recorded plan and commands; ambiguous dispatched work fails closed.

## Evidence, not marketing numbers

The repository contains v1/v2 design and verification records. They are historical local artifacts, not independent performance claims and not a benchmark. The benchmark harness under [`benchmarks/`](benchmarks/) intentionally ships without results until a reproducible run records them.

## Contributing and release safety

Read [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This repository does not use GitHub Actions. Maintainers run the complete fail-closed release gate locally with:

```sh
python3.11 scripts/verify_public_release.py --output build/release-artifacts
```

It tests, audits, builds, installs, and hashes the release candidate. It does not publish, deploy, change visibility, or rewrite history. See the [release gate](docs/public/RELEASE_GATE.md) and [limitations](docs/public/LIMITATIONS.md).

## Repository maps

- [CHANGELOG.md](CHANGELOG.md): release notes and explicit beta status.
- [CONTEXT.md](CONTEXT.md), [PRODUCT.md](PRODUCT.md), and [DESIGN.md](DESIGN.md): maintained product and design context.
- [TEAM_TOPOLOGY.md](TEAM_TOPOLOGY.md) and [design-qa.md](design-qa.md): historical team and design-review records.
