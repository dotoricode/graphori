# Changelog

## Unreleased

### Fixed

- The journal writer now works on Windows. It took a POSIX `flock` and failed
  closed everywhere else, so `graphori run` aborted with exit code 2 on Windows
  even though the installers and documentation described PowerShell use. Windows
  now uses `msvcrt.locking`; a platform with neither backend still fails closed.
- `graphori doctor` honours `--lang`. It previously reported in Korean whatever
  the flag said.
- The verifier node title is no longer Korean. It is part of the canonical plan
  digest, and the portability contract requires language to stay out of plan,
  journal, and projection digests.
- On Windows, a lock failure that was not contention was reported as "another
  Graphori is running". Only `EACCES` and `EDEADLOCK` now mean contention;
  every other errno reports its own cause. A missing lock backend raises the
  unsupported-platform error instead of escaping as `ImportError`, and the lock
  descriptor is closed on every failure path.
- `scripts/validate_docs_indexes.py` reads the tracked tree instead of walking
  the working directory, so it no longer fails on ignored build output. It also
  checks untracked documents Git would not ignore, which is how a new document
  used to escape the index check until after it was committed.
- `THIRD_PARTY_NOTICES.md` listed IBM Plex Sans KR fonts that this repository
  does not ship.
- Several documents overstated what is verified. The README claimed macOS `run`
  support the portability contract holds at `deferred/unknown`, presented an
  environment-dependent skip count as fixed, said a run without
  `--verify-command` has nothing to judge by when the runtime picks a default,
  and called `0.1.0` the first public source version even though the
  `v0.9.0-beta.1` tag sits on this repository's own first commit. The install
  guide said nothing executes at install time, but the installer runs
  `validate_skill.py` against the copied Skill.

### Known inconsistency

`pyproject.toml` declares `0.1.0` while the repository's first commit carries a
`v0.9.0-beta.1` tag. The documents no longer try to reconcile the two; picking
one scheme is still open.

### Changed

- Internal build reports, reviews, research checkpoints, and preserved Doctori
  evidence moved under `docs/archive/`. Maintainer-context documents moved from
  the repository root into `docs/`. Every relative link was repointed.
- Three tests were environment-dependent rather than deliberately platform-
  specific: the writer-ownership fixture now runs wherever a lock backend
  exists, and the macOS-only image probe and the symlink fixture skip instead
  of failing.

## 0.1.0 — first public source release

- Codex and Claude Code native plugin manifests, with separate install paths.
- Dry-run installers for both the Skill and the optional Python runtime.
- Explicit `auto`, English, and Korean output selection, with locale kept out
  of canonical digests.
- The v1-style/v2 benchmark artifacts, their verifier, and their stated limits.
- Documentation, security policy, licensing, SBOM, and provenance scaffolding.

This is the first public source line. It does not publish a package registry
release and does not promise a stable API.

The v2 execution engine and dashboard predate this changelog; their
commit-linked evidence and its limits are in
[`docs/public/HISTORY.md`](docs/public/HISTORY.md).
