# Public release gate

Graphori uses a **local verification + `gh` publication** process. GitHub Actions is disabled and is not a release requirement.

## Required local command

Run this from a clean-history candidate clone or linked worktree:

```bash
python3.11 scripts/verify_public_release.py --output <new-artifact-directory>
```

The command must exit successfully. It runs the complete unit suite, compilation, document indexes, Skill validation, dashboard smoke check, current-tree and Git-history privacy audit, Gitleaks tree and history scans, wheel/sdist build, Twine metadata check, isolated Runtime and Solo installations, `pip-audit`, CycloneDX SBOM generation, and SHA-256 generation.

The verifier does not publish a package, create a GitHub repository, change visibility, or upload artifacts.

## Evidence boundary

- Recorded local commands and the dedicated generic-adapter fixture have run on macOS 26.5.2 x86_64 with Python 3.11 and 3.14. See [VERIFICATION.md](VERIFICATION.md). This is a scoped host verdict, not a claim about every Mac.
- Windows installation and Windows Job Object behavior are experimental and are not release claims.
- CodeQL, OpenSSF Scorecard, and OIDC provenance are not claimed because this no-Actions release does not run them.
- Gitleaks, `pip-audit`, SBOM, artifact hashes, clean-history inspection, and local test output are the release evidence.

See [LIMITATIONS.md](LIMITATIONS.md) for the user-facing boundary.

## Clean-history publication procedure

The reviewed public tree was replaced on 2026-08-28 with the parentless noreply
commit `83fe5a5`. Before the force update, that exact commit passed the complete local
release verifier in an isolated one-commit repository. The old prerelease tag and the
three ordinary remote work branches were removed. A fresh public clone contains one
noreply commit and passes the tree/history privacy audit.

This rewrites ordinary Git refs; it cannot retract copies already fetched by another
party or promise that hosting caches and merged pull-request metadata no longer retain
old object identifiers. No secret was found by the tree or history Gitleaks scans.
