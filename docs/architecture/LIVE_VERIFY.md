# Live Verify

Live Verify is an opt-in latency optimization for deterministic verification.
It does not change the graph, verdict semantics, or durable journal.

## Contract

1. A worker dispatch starts the normal v2 execution path.
2. File scanning is only a wake-up hint.
3. After a quiet interval, Graphori copies the workspace into a temporary
   directory. `.git`, `.graphori`, `__pycache__`, and symlinks are not accepted
   as speculative inputs. Ignored project files remain part of the snapshot.
4. The copied content digest must equal a fresh source digest before the command
   starts.
5. Graphori builds a `ProofActionKey v0` from the observable execution envelope,
   then runs the command against the copy. Only exit zero is eligible for reuse,
   the command must leave the copy unchanged, and the directly executed entry
   file must have the same identity before and after execution.
6. When the real verifier Node becomes ready, its current workspace digest must
   still equal the sealed source digest and an independently built ActionKey
   must match. Otherwise Graphori runs the original v2 verifier.
7. Only the ordinary verifier event written by the engine changes canonical
   state. The speculative worker owns no journal authority.

This makes a speculative PASS evidence about an immutable content snapshot,
not about a directory that an agent may still be editing. Failure, timeout,
copy uncertainty, symlinks, unsupported Git-dependent checks, and digest drift
all fail closed to the serial path.

## ProofActionKey v0 boundary

The key covers inputs Graphori directly observes or a caller explicitly
declares:

- proof IDs, argv, logical working directory, and logical input digest;
- the names and one aggregate digest of the actual filtered child environment;
- the identity of the entry executable directly launched by
  `ProcessSupervisor`;
- declared permission, sandbox, network, and verifier profiles.

Raw environment values and per-variable value hashes are not persisted. Entry
executable identity is not a claim about the complete toolchain: `./gradlew`
identifies that wrapper, not every JDK, plugin, cache, or downloaded artifact it
may use. Likewise, a Python entry executable does not claim to identify every
transitive import. v0 intentionally proves equality only within this bounded
execution envelope.

Eligibility has two states. `REUSABLE` means every required v0 envelope field
could be compared. `INCOMPLETE` means at least one required observable field
could not be identified, so Graphori runs the existing verifier. An unknown
transitive dependency alone does not make a Python, Java, Gradle, or shell
command incomplete in v0.

Three independent checks remain separate:

1. snapshot safety: source digest equals copied digest, and the copy stays
   unchanged while verification runs;
2. action identity: the bounded ProofActionKey is complete and stable;
3. adoption safety: the final source digest and independently rebuilt key match
   the speculative candidate.

The policy fields are identities, not enforcement claims. In particular,
`sandbox_profile=none` records that the generic process verifier has no OS-level
sandbox; it does not pretend one exists.

## Intended use

Use Live Verify for repeatable local suites whose runtime is meaningfully longer
than snapshot construction and whose implementation agent commonly finishes
editing before it finishes reporting. Do not use it for network checks,
destructive commands, release signing, clock/random dependent checks, or very
short commands.

The feature is explicit (`--live-verify`) because Graphori cannot infer
repeatability or external side effects from argv alone.

## Evidence boundary

The public benchmark exercises real process supervision, immutable copies,
digest fences, fallback, and late-write faults. It does not include live model
inference and therefore does not establish a provider end-to-end performance
claim. See [`benchmarks/live_verify/`](../../benchmarks/live_verify/).
