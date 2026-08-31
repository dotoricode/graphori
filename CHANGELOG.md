# Changelog

## Unreleased

### Fixed

- Codex and Claude Code no longer silently accept a standalone Graphori Skill
  beside an enabled `graphori@graphori` plugin. The standalone installers now
  fail before copying, and a read-only checker reports existing duplicate
  discovery paths.
- The journal writer now works on Windows. It took a POSIX `flock` and failed
  closed everywhere else, so `graphori run` aborted with exit code 2 on Windows
  even though the installers and documentation described PowerShell use. Windows
  now uses `msvcrt.locking`; a platform with neither backend still fails closed.
- `graphori doctor` honours `--lang`. It previously reported in Korean whatever
  the flag said.
- The verifier node title is no longer Korean. It is part of the canonical plan
  digest, and the portability contract requires language to stay out of plan,
  journal, and projection digests.
- Ready-file consumption is reproducible again. Ordering keyed on modification
  time, so filesystem timestamp granularity decided which submissions collided
  and that varied per run. Each run now assigns a persistent logical ordinal under
  a short interprocess lock after the tmp file is flushed, persists the counter,
  and holds the lock through the ready rename. The writer takes the same lock
  while capturing its ready snapshot, so clock rollback, equal timestamps, and
  concurrent producers cannot publish a later ordinal first. Files left by an
  older version have no ordinal and fall back to `st_mtime_ns`; the new counter
  starts above every legacy file already waiting. A `v2.` filename marker keeps
  numeric legacy producer IDs distinct from new ordinals.
- On Windows, a lock failure that was not contention was reported as "another
  Graphori is running". Only `EACCES` and `EDEADLOCK` now mean contention;
  every other errno reports its own cause. A missing lock backend raises the
  unsupported-platform error instead of escaping as `ImportError`, and the lock
  descriptor is closed on every failure path.
- `scripts/validate_docs_indexes.py` reads the tracked tree instead of walking
  the working directory, so it no longer fails on ignored build output. It also
  checks untracked documents Git would not ignore, which is how a new document
  used to escape the index check until after it was committed.
- `scripts/verify_public_release.py` now accepts a linked Git worktree as well
  as an ordinary clone. It previously required `.git` to be a directory even
  though Git stores a control file at a linked worktree root.
- The macOS generic-adapter verdict no longer rests on the full suite alone.
  A dedicated local fixture now verifies process-tree termination, path and
  POSIX symlink escape, case collisions, journal publication, replay, and
  idempotency plus a real generic-adapter lifecycle. It emits one whole-record
  hash per boundary and preserves the JSON beside local release artifacts.
- `THIRD_PARTY_NOTICES.md` listed IBM Plex Sans KR fonts that this repository
  does not ship.
- Several documents overstated what is verified. The README claimed macOS `run`
  support the portability contract holds at `deferred/unknown`, presented an
  environment-dependent skip count as fixed, said a run without
  `--verify-command` has nothing to judge by when the runtime picks a default,
  and called `0.1.0` the first public source version even though this public
  beta line already declared `v0.9.0-beta.1`. The install
  guide said nothing executes at install time, but the installer runs
  `validate_skill.py` against the copied Skill.

### Changed

- `--live-verify` can overlap an explicitly repeatable deterministic check with
  the worker's reporting tail. It verifies an immutable copy and reuses only a
  matching PASS; uncertainty falls back to the serial v2 verifier. The paired
  control-plane gate passed, but no provider end-to-end speed claim is made.
- `ProofActionKey v0` now compares the bounded, observable verifier envelope at
  speculation and adoption without claiming complete transitive toolchain
  closure. Persistable metadata contains only environment names and one
  aggregate digest, never raw environment values.
- Deterministic verifier commands now map their exit status directly to a
  verdict instead of launching a second Python process to write and reread a
  verdict file.

- Graphori Sprout introduces proof-carrying artifacts and a replayable Proof
  Frontier. Declared proof obligations, rather than node completion alone, now
  gate sparse dispatch; qualified pilots can create immutable plan revisions,
  proof-qualified branches gate fan-in, reversible commit requires synthesis proof,
  and irreversible Sprout commit is rejected until its human gate is implemented.
- A reproducible 1,000-cell routing-model benchmark compares v1 target review,
  Graphori v2, unconditional pilot, adaptive Sprout, and a static oracle. The
  performance gate keeps v2 until declared estimates predict a pilot gain; modeled
  latency is not presented as provider wall time.

- Runtime can now add a read-only cross-provider review with
  `--cross-review auto|always|never`. It checks Codex and Claude Code CLI
  compatibility plus local authentication without a model call, assigns the
  provider opposite the implementer, and keeps the deterministic command as
  the only source of final PASS. A missing provider is an explicit
  deterministic-only downgrade; a dispatched unknown outcome is never silently
  rerouted.
- `--verify-criterion ID` now explicitly maps a deterministic verification
  command to the acceptance criteria it proves. Mapped criteria become PROVEN
  or FAILED from that command; unmapped criteria remain NOT_PROVEN. The mapping
  is stored in the plan's evidence requirements and survives replay.
- Cross-provider review now supports both Codex-to-Claude and Claude-to-Codex
  paths through `--implementation-provider`. Auto review also covers two-file,
  directory, glob, and explicitly high-uncertainty changes. A blocking review
  terminates the run as failed instead of leaving pending descendants stranded.

- The public benchmark now includes the completed 72-run Direct/v1-style/
  Graphori v2 matrix for Codex and Claude. Raw JSONL, deterministic analysis,
  task fixtures, provider-separated reports, and complete README metrics are
  published. All 72 runs passed; Graphori v2 matched measured quality with half
  the AI sessions of v1-style, while Direct remained fastest on the small tasks.
- Public `main` now starts from one parentless noreply source snapshot after the
  approved history rewrite. That exact snapshot passed the complete local
  release verifier before publication; the earlier prerelease tag and ordinary
  work branches were removed.

- Runtime output follows the language you work in. Journal, resume, provider,
  doctor, and dashboard messages carry a condition key with an English default
  and are rendered in the resolved locale at the point of display, so no locale
  reaches the writer or the journal. `graphori status` used to print a readable
  report in Korean and raw JSON in English; both languages now get the report.
  Keyword lists that match Korean input are unchanged — they read the objective
  rather than write output. Argparse now resolves explicit, configured,
  objective, or process language before constructing help, so top-level and
  subcommand help are available in both English and Korean.
- The declared version is `0.9.0-beta.1`; `pyproject.toml` spells it `0.9.0b1`
  because PEP 440 normalizes it that way. Calling this beta `0.1.0` understated
  how much of the line already existed. The early public prerelease tag was
  retired during the approved clean-history rewrite; no package was published.
- Internal build reports, reviews, research checkpoints, and preserved Doctori
  evidence moved under `docs/archive/`. Maintainer-context documents moved from
  the repository root into `docs/`. Every relative link was repointed.
- Three tests were environment-dependent rather than deliberately platform-
  specific: the writer-ownership fixture now runs wherever a lock backend
  exists, and the macOS-only image probe and the symlink fixture skip instead
  of failing.

## 0.9.0-beta.1 — first public source release

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
