# Installation routes

The [README](../../README.md) covers the two native plugin installs. This page
collects the rest: previewing before you install, project-local copies, and the
optional Python runtime.

## Pick exactly one Skill route

For each agent, use either the native plugin or a standalone/project-local
copy. Do not combine them. The plugin and copied package expose the same
`graphori` and `graphori-dashboard` Skills, so installing both makes each Skill
appear twice in completion.

The native plugin is the recommended route. If you intentionally want a
standalone copy, remove or disable `graphori@graphori` in that agent first. You
can audit an existing setup from a clone without changing it:

```sh
python3 scripts/check_skill_install_conflicts.py --target both
```

The bundled standalone installer runs this check before copying and fails
closed when the plugin is enabled.

## Preview before installing

The [`skills`](https://github.com/vercel-labs/skills) CLI lists what a
repository would install without writing anything:

```sh
npx skills add dotoricode/graphori --list
```

Node.js 22.20 or newer is required.

## Project-local copies

These are alternatives to the native plugin, not an additional install step.

```sh
npx skills add dotoricode/graphori --skill graphori --agent codex --copy
npx skills add dotoricode/graphori --skill graphori --agent claude-code --copy
```

These deliberately omit `--global`. The CLI's global Codex path does not match
the path Codex itself uses for user Skills, so a global install through the CLI
lands somewhere Codex will not read.

## Install from a clone

If you would rather read the script than trust an npm package:

```sh
gh repo clone dotoricode/graphori -- --depth 1
cd graphori
./scripts/install_graphori.sh --mode solo --target codex --dry-run
./scripts/install_graphori.sh --mode solo --target codex
```

Use `--target claude` for Claude Code, or `--target both`. On Windows
PowerShell the equivalent is `scripts/install_graphori.ps1 -Mode solo -Target codex`.

`--dry-run` prints every action and changes nothing. The installer refuses to
overwrite a different Skill of the same name unless you pass `--force`, and a
forced replacement writes a timestamped backup first.

Destinations:

| Agent | Path |
| --- | --- |
| Codex | `~/.agents/skills/graphori` |
| Claude Code | `~/.claude/skills/graphori` |

Codex retired `~/.codex/skills`; Graphori does not write there.

## The optional runtime

```sh
./scripts/install_graphori.sh --mode runtime --dry-run
./scripts/install_graphori.sh --mode runtime
graphori doctor --lang en
```

This performs a local pip install of the checkout. Use a virtual environment if
you do not want it in your current interpreter. Python 3.11 or newer.

### Running a change from the command line

Store the root in a variable and quote it, so a path containing spaces cannot
split into two arguments:

```sh
repo_root="$(pwd -P)"
graphori run "add a docstring to the parser" \
  --root "$repo_root" \
  --write-scope src/parser.py \
  --cross-review auto \
  --verify-command python -m unittest tests.test_parser
```

On Windows PowerShell:

```powershell
$root = (Get-Location).Path
graphori plan "add a docstring to the parser" --root $root --lang en
```

`--write-scope` bounds what the run may touch. `--verify-command` is the check
that decides the verdict; leave it out and Graphori picks a default for the
workspace — the unit test suite, then `compileall`, then `git diff --check`.

`--cross-review auto` adds a read-only review by the provider opposite the
implementer for sensitive, broad, or synthesis-heavy changes when both Codex
and Claude Code are installed, compatible, and authenticated. `always` applies
the policy to every implementation; `never` disables it. Run `graphori doctor
--json` to inspect the sanitized readiness state without making a model call.

## Choosing the output language

`--lang auto` is the default and resolves in this order: an explicit flag, then
configured preference, then the language of the objective, then the process
locale, then English. Language is a presentation choice — it never enters the
plan, journal, or projection digests.

## What gets installed

Both Skill directories hold Markdown and an `agents/openai.yaml` manifest.
`skills/graphori/` additionally ships `scripts/validate_skill.py`, a
standard-library script that checks the Skill's own metadata;
`skills/graphori-dashboard/` ships no script.

One thing does execute during installation: after copying, the installer runs
`validate_skill.py` against the destination to confirm the copy is a
well-formed Skill. That is the only code either installer executes, and you can
read it before you install. Nothing else runs, and the Skill itself is inert
Markdown that your agent reads.
