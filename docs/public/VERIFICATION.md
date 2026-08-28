# Local verification record

This page records commands that actually ran. It is evidence, not a platform-wide
support claim.

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

These commands do not satisfy the dedicated process-tree termination, path-escape,
and symlink acceptance fixture in the portability contract. The macOS platform
verdict remains deferred. No Linux release gate is claimed, and Windows installation
and Job Object behavior remain experimental.
