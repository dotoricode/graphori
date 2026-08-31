# Live verification speed research

Status: first control-plane hypothesis implemented; resident-provider work remains  
Date: 2026-08-31

## Decision

Graphori should test a **resident proof loop**, not replace its durable file
journal with another mailbox.

The common path should keep one provider process and one verifier service alive
for the run, stream small control messages over stdio, store large evidence in
the existing content-addressed store, and accept a proof only when its complete
action key matches the final workspace snapshot. A failed live check should be
steered into the same agent turn when the provider supports it, or sent as the
next turn in the same thread. Files remain the crash-recovery authority.

```text
resident provider thread                         resident verifier
        |                                               |
        |-- file/diff notification -------------------->|
        |                                               |-- incremental check
        |<-- compact NACK over live stream --------------|
        |-- repair                                       |
        |                                               |-- exact-key PASS
        +---------------- final snapshot fence ----------+
                                |
                         durable journal + CAS
```

This is more promising than adding agents or shared memory. The measured common
path has only one LLM session, so the available speedups are removing cold
startup/context reconstruction, overlapping verification with implementation,
and avoiding duplicate deterministic work.

## What Graphori does today

- Every Codex dispatch launches `codex exec --ephemeral` in
  [`codex/adapter.py`](../../src/graphori_adapters/codex/adapter.py).
- Every Claude dispatch launches `claude -p --no-session-persistence` in
  [`claude/adapter.py`](../../src/graphori_adapters/claude/adapter.py).
- The execution engine releases the session after each node attempt in
  [`execution_engine.py`](../../src/graphori_core/execution_engine.py).
- The journal submission path durably writes a temporary event, fsyncs a
  persistent ordering counter, renames the ready event, appends and fsyncs the
  journal, then removes the ready file in
  [`journal.py`](../../src/graphori_core/journal.py).
- Graphori already has a SHA-256 content-addressed evidence store in
  [`evidence.py`](../../src/graphori_core/evidence.py). A second large-payload
  mailbox would duplicate an existing capability.

The `SessionHandle` abstraction therefore does not currently mean a warm model
or provider process. It is an attempt-scoped handle around a new CLI process.

## Mechanisms ranked by expected value

| Rank | Mechanism | Expected common-path effect | Principal risk |
|---:|---|---|---|
| 1 | Resident provider thread | Removes repeated CLI/bootstrap work and preserves repair context | State leakage and provider-version drift |
| 2 | Live, incremental verifier | Overlaps checks with agent work; final PASS may already exist | Stale or incomplete dependency closure |
| 3 | Bounded action-key proof reuse | Avoids rerunning a matching observable execution envelope | False cache hit if the stated boundary is mistaken for full toolchain closure |
| 4 | Same-turn NACK steering | Repairs before the agent exits instead of creating a rework session | Steering races with turn completion |
| 5 | Stream notification plus durable journal | Makes progress and handoff immediate while retaining replay | Two channels must not become two truths |
| 6 | Projection checkpoint plus tail replay | Speeds long-run resume/status | Adds little value to today's short runs |
| 7 | Shared memory | May reduce copying for very large, very frequent messages | Synchronization, lifecycle, and portability cost |

### 1. Keep the provider alive

OpenAI's official Codex app-server is a bidirectional JSON-RPC interface with
newline-delimited stdio and a local Unix-socket option. A connection initializes
once, then starts or resumes threads and drives multiple turns. It also emits an
updated whole-turn diff after each file change and supports `turn/steer` for an
active regular turn. This gives Graphori a supported route to observe changes
and inject a verifier NACK without terminating the provider process. The
websocket transport is explicitly experimental; stdio is the portable default.
[Codex app-server protocol](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)

Anthropic's official Claude Agent SDK cookbook distinguishes an open
`ClaudeSDKClient`, which can receive repeated `.query()` calls without resending
history, from disk-backed `resume=session_id`, which survives a process restart
but is local to one machine. The public Claude Code CLI also exposes
`--continue`, `--resume`, and streaming JSON input/output. Graphori must probe
the installed provider and authentication mode instead of assuming the SDK is
available under a user's subscription.
[Claude Agent SDK session guidance](https://platform.claude.com/cookbook/claude-agent-sdk-04-migrating-from-openai-agents-sdk),
[Claude Code CLI reference](https://docs.anthropic.com/en/docs/claude-code/cli-usage)

Bazel persistent workers provide the general systems precedent: repeated
requests to a long-running tool remove startup/JIT work and allow internal
caches to survive. Bazel also warns that state may leak between requests and
that worker sandboxing is weaker unless explicitly configured. Graphori should
therefore allocate a provider thread by `(run, role, provider, workspace,
permission profile)` and never share worker and independent-review context.
[Bazel persistent workers](https://bazel.build/remote/persistent)

### 2. Verify while the agent is still working

The verifier should subscribe to authoritative provider file-change events when
available and use an OS watcher only as a wake-up hint otherwise. It should
debounce bursts, derive the affected proof obligations, and run the cheapest
declared check in a persistent tool process or in the build tool's own
incremental mode. The agent continues working while the check runs.

Watcher events cannot prove the snapshot. Linux inotify can coalesce events and
lose its queue; macOS FSEvents can coalesce or drop events and then requires a
rescan; Windows discards an overflowed change buffer and requires directory
enumeration. The final decision must therefore re-enumerate or hash the declared
input closure, while watcher output only narrows speculative work.
[Linux inotify](https://man7.org/linux/man-pages/man7/inotify.7.html),
[Apple FSEvents](https://developer.apple.com/library/archive/documentation/Darwin/Conceptual/FSEvents_ProgGuide/UsingtheFSEventsFramework/UsingtheFSEventsFramework.html),
[Windows ReadDirectoryChangesW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-readdirectorychangesw)

Git already offers a portable optimization for large repositories:
`core.fsmonitor` and the untracked cache let Git ask for recently changed paths
instead of scanning the whole worktree. Graphori should use Git's result where
available before owning a cross-platform watcher implementation.
[Git index and FSMonitor](https://git-scm.com/docs/git-update-index),
[Git status performance](https://git-scm.com/docs/git-status)

### 3. Reuse proofs only by a matching bounded action key

Bazel's cache model maps an action hash to result metadata and keeps outputs in
a content-addressed store. Its action includes declared inputs, command line,
environment, and output names. Bazel documents concrete false-hit hazards:
inputs modified during execution, environment leakage, and tools outside the
tracked workspace. Graphori must be at least as conservative.
[Bazel remote caching](https://bazel.build/remote/caching)

The first implementable Graphori proof key is deliberately bounded:

```text
SHA-256(
  verifier argv and working directory
  + logical workspace/input digest
  + one aggregate digest of the filtered child environment
  + directly executed entry-file identity
  + proof/verifier identity
  + sandbox and network policy
)
```

`ProofActionKey v0` does not claim complete transitive toolchain or input
closure. Graphori does not automatically reject Python, Java, Gradle, or shell
verifiers merely because an interpreter or wrapper may read dependencies that
v0 does not trace. Instead, v0 proves equality of the execution envelope that
Graphori directly observes or the caller explicitly declares. If a required
observable field cannot be identified, the key is incomplete and the normal v2
verifier runs. Stronger dependency discovery is future work and must not be
retroactively claimed by v0.

If the workspace, copied snapshot, entry executable, or bounded action key
changes across its corresponding fence, the result remains evidence for the
old action and cannot satisfy the final fence. Release gates still run their
full documented verification.

The payload should be stored once in Graphori's existing evidence CAS. Live
messages and journal events carry only an evidence ID, action key, status, and
small summary. Git's `hash-object` documents the underlying content-to-object-ID
model used for this kind of identity.
[Git hash-object](https://git-scm.com/docs/git-hash-object)

### 4. Send a NACK before closing the agent

Codex app-server's `turn/steer` appends input to an in-flight regular turn and
requires the expected turn ID, preventing accidental delivery to another turn.
Graphori can send a compact counterexample containing the failing obligation,
command, exit code, and smallest useful error slice. If the turn has already
finished, it starts the next turn on the same thread. Claude uses the same open
SDK client where available, or the documented session resume fallback.

The verifier remains independent: session reuse is allowed between one worker's
implementation and its own repair, never between the worker and the reviewer.

### 5. Use streams for notification, files for authority

The Model Context Protocol standardizes local subprocess communication as
newline-delimited JSON-RPC over stdin/stdout. Codex app-server uses the same
shape. This is sufficient for Graphori's small control messages and is portable.
A Unix-domain socket is useful only when several clients must attach to one
resident daemon. Shared memory still needs a synchronization primitive and has
no inherent durability; it should be tested only if profiling shows payload
copying dominates.
[MCP transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports),
[POSIX local socket semantics](https://man7.org/linux/man-pages/man7/unix.7.html),
[POSIX shared-memory overview](https://man7.org/linux/man-pages/man7/shm_overview.7.html)

There must be one truth rule:

> A stream event may update live UI and schedule speculative work, but only a
> journaled event whose referenced evidence passes the final digest fence may
> change canonical completion state.

### 6. Checkpoint only after the hot path wins

A canonical projection snapshot can be stored in the CAS with its journal
sequence and head digest. Resume verifies that boundary and replays only the
tail; any mismatch falls back to full replay. This follows the append-log plus
checkpoint pattern documented by SQLite WAL, without requiring a database
migration. Current runs are short, so this is lower priority than provider and
verifier residency.
[SQLite write-ahead logging](https://sqlite.org/wal.html)

## Local transport measurement

An illustrative microbenchmark was run on macOS 26.5.2 x86_64 with Python
3.11.15. One persistent child echoed a 1 KiB payload over two pipes or a Unix
socket pair. The Graphori case submitted and consumed one canonical heartbeat
through the real durable `tmp -> ready -> journal` path. After 30 warmups, 300
samples produced:

| Path | Median round trip | p95 round trip |
|---|---:|---:|
| Anonymous pipes | 36.6 us | 335.3 us |
| Unix socket pair | 46.2 us | 141.6 us |
| Graphori durable submit + consume | 28.1 ms | 165.2 ms |

This does **not** predict end-to-end agent speed. It only falsifies the idea
that a durable file round trip is a competitive live notification channel on
this machine. Provider inference and test execution are orders of magnitude
larger, so IPC replacement passes only if an end-to-end experiment also passes.

## Prototype order

Each stage must be measured against unchanged v2 before the next stage is added.

1. Add a provider capability probe and resident Codex app-server adapter. Keep
   v2 as the fallback and preserve role/session isolation.
2. Add resident Claude transport only through a documented, locally available
   authentication path. Do not require a paid API key for a CLI-subscriber path.
3. Add a verifier broker that captures exact commands already executed by the
   agent and binds their result to an action key and workspace digest.
4. Add live speculative verification and same-thread NACK delivery. A watcher
   supplies dirty hints only.
5. Add projection checkpoints only if replay/status profiling shows a material
   share of latency.

## Strict falsification gate

Use paired, interleaved v2 and candidate runs from identical repository
snapshots. The task set must reflect measured use rather than 8- or 16-branch
synthetic graphs:

- 60%: one implementation session, first deterministic verification passes;
- 25%: one implementation session, first verification fails, then repair;
- 15%: two to four implementation/proof nodes;
- at least five repositories, ten tasks per class, and three paired repetitions;
- same provider, model, effort, permissions, verifier command, hidden checks,
  cache temperature, and machine power state within each pair;
- order randomized as AB/BA, with raw timestamps and token counters retained.

The candidate passes only when **all** conditions hold independently for Codex
and Claude:

1. Hidden correctness is no worse than v2; false or stale proof acceptance is
   exactly zero; scope violations are exactly zero.
2. AI calls and fresh input tokens do not increase on any task class.
3. Overall end-to-end median improves by at least 25% and p95 by at least 15%,
   with a bootstrap 95% confidence interval for each improvement wholly above
   zero.
4. First-pass common tasks regress by no more than 2% at p50 and no individual
   workload regresses by more than 5% at p50.
5. For repair tasks, verification-NACK-to-PASS median improves by at least 35%
   and fresh input tokens improve by at least 30%.
6. Live notification p95 is below 5 ms for 1 KiB messages, while a crash at any
   injection point still recovers to the same canonical journal projection.
7. Disabling the resident process, watcher, cache, or steering separately shows
   which mechanism caused the gain. If only the combined candidate passes, the
   interaction must be explained by recorded timing evidence.

Stop and keep v2 if these gates fail after the resident-provider and
live-verifier prototypes have each had one measured correction cycle. Do not
weaken the thresholds or present a transport microbenchmark as product speed.

## Main risks and required defenses

| Risk | Required defense |
|---|---|
| Cross-run or worker/reviewer context leak | Session key includes run, role, provider, workspace, and permission profile; explicit TTL and close |
| Stale verifier PASS | Full action key plus final snapshot fence; unknown dependency means rerun |
| Watcher loss/coalescing | Watcher is a hint; overflow/fresh-instance/symlink uncertainty triggers full scan |
| Concurrent mutation during verification | Bind result to start/end input digests; mismatch cannot close proof |
| Provider protocol changes | Generate/probe installed schema and retain the v2 CLI fallback |
| Resident-process crash | Restart, resume only through provider-documented identity, and replay the durable journal |
| Two sources of truth | Streams schedule/display only; journal plus evidence digest authorizes completion |
| Cache poisoning | Local per-repository cache first, immutable CAS objects, toolchain/env in key, full release verification |

## Conclusion

The strongest speed hypothesis is not more parallel agent sessions and not
shared memory. It is to turn the existing two-node path into one overlapped,
resident feedback loop:

```text
keep context + verify early + reuse exact proof + repair before exit
```

The local IPC result supports moving notifications off the durable mailbox, but
only the strict paired end-to-end gate can justify a Graphori performance claim.

## Implemented first slice

The first measured slice keeps the durable journal unchanged, removes the
verdict-file wrapper, and adds opt-in immutable-snapshot verification. In ten
paired control-plane runs it reduced median wall time by 33.2% and p95 by 35.0%;
the paired bootstrap 95% lower bound was 31.8%. All ten normal runs produced a
complete bounded key and reused their PASS candidate. Ten injected late writes
fell back with `source_changed` and reused zero stale proofs. The initial
mutable-directory prototype and a shorter 250 ms
fixture were rejected: the former had an unsound concurrent-read boundary, and
the latter could not amortize snapshot construction. These results justify the
bounded feature and its fallback, not a provider performance claim.

Resident Codex/Claude sessions, same-turn NACK steering, and separate live
provider gates remain research work. They must not inherit the control-plane
numbers above.
