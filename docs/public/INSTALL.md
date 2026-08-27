# Installation routes

The [README](../../README.md) covers the two native plugin installs. This page
collects the rest: previewing before you install, project-local copies, and the
optional Python runtime.

## Preview before installing

The [`skills`](https://github.com/vercel-labs/skills) CLI lists what a
repository would install without writing anything:

```sh
npx skills add dotoricode/graphori --list
```

Node.js 22.20 or newer is required.

## Project-local copies

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

## Choosing the output language

`--lang auto` is the default and resolves in this order: an explicit flag, then
configured preference, then the language of the objective, then the process
locale, then English. Language is a presentation choice — it never enters the
plan, journal, or projection digests.

## What gets installed

The Skill directories hold Markdown, an `agents/openai.yaml` manifest, and one
standard-library Python script (`scripts/validate_skill.py`) that checks the
Skill's own metadata. Nothing executes at install time; the installer copies
files and prints what it copied.
