# Local verification record

This page records commands that actually ran. It is evidence, not a platform-wide
support claim.

## 2026-08-28 · macOS portability fixture

- Command: `python scripts/verify_macos_portability.py`
- Host: macOS 26.5.2, x86_64
- Python: 3.11.15 and 3.14.6
- PASS: process-tree termination, path escape, POSIX symlink escape, case
  collision, JSONL tmp→ready publication, replay, and idempotency.
- Output: one contract-shaped record per fixture with `platform`, `fixture`,
  `verdict`, `evidence_id`, `command`, `host`, self-contained test evidence,
  and its SHA-256 hash.

This changes the macOS generic-adapter verdict only for the recorded host and
fixture scope. It does not establish Linux or Windows release support.

## 2026-08-28 · public-release follow-up candidate

- Tree: `312bea4`
- Host: macOS 26.5.2, x86_64
- Python 3.14.6: `python -m unittest discover -s tests` — 413 tests passed,
  6 skipped.
- Python 3.11.15: product-entry tests — 15 passed; local-release tests —
  6 passed.
- English top-level help, English objective-selected plan help, Korean help,
  and an English disposable-root `graphori plan` smoke all exited successfully.
- Document indexes covered 137 Markdown files. The retained eight benchmark
  rows recalculated to 8 hidden passes and 0 scope violations.
- Gitleaks found no leaks in the current tree or 17 reachable commits.

The history privacy audit still blocks the full release verifier for the reason
recorded below. No package or release was published.

## 2026-08-28 · ready-ordering merge

- Tree: public `main` at `4a1d5e3`
- Host: macOS 26.5.2, x86_64
- Python 3.14.6: `python -m unittest discover -s tests` — 410 tests passed,
  6 skipped.
- Python 3.11.15: `python3.11 -m unittest discover -s tests -p
  'test_journal_*.py'` — 26 journal tests passed.
- The ordering/concurrency pair ran 10 consecutive times without a failure.

An earlier Python 3.11 full local verifier run reached 406 passing tests plus
compilation, document-index, Skill, and dashboard smoke checks. It then stopped
at the Git-history privacy audit because the public history contains one
non-noreply author identity. Gitleaks, packaging, install, audit, SBOM, and hash
steps after that gate are not claimed by this record.

## Evidence boundary

The dedicated macOS fixture now has a scoped pass on the host above. No Linux
release gate is claimed, and Windows installation and Job Object behavior remain
experimental.
