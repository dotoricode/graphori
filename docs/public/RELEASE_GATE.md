# Public release gate

Graphori uses a **local verification + `gh` publication** process. GitHub Actions is disabled and is not a release requirement.

## Required local command

Run this from a clean-history candidate repository:

```bash
python3.11 scripts/verify_public_release.py --output <new-artifact-directory>
```

The command must exit successfully. It runs the complete unit suite, compilation, document indexes, Skill validation, dashboard smoke check, current-tree and Git-history privacy audit, Gitleaks tree and history scans, wheel/sdist build, Twine metadata check, isolated Runtime and Solo installations, `pip-audit`, CycloneDX SBOM generation, and SHA-256 generation.

The verifier does not publish a package, create a GitHub repository, change visibility, or upload artifacts.

## Evidence boundary

- The release is verified locally on macOS with Python 3.11. Python 3.12 is checked separately.
- Windows installation and Windows Job Object behavior are experimental and are not release claims.
- CodeQL, OpenSSF Scorecard, and OIDC provenance are not claimed because this no-Actions release does not run them.
- Gitleaks, `pip-audit`, SBOM, artifact hashes, clean-history inspection, and local test output are the release evidence.

See [LIMITATIONS.md](LIMITATIONS.md) for the user-facing boundary.

## Clean-history publication procedure

The existing development repository cannot be made public in place. Its old history contains non-noreply author emails and personal-path or organization-shaped identifiers.

1. Export the reviewed tree with `scripts/export_public_tree.py`.
2. Create a new `main` history with a noreply author identity.
3. Run `scripts/verify_public_release.py` in that repository.
4. Use `gh` to preserve the development repository as private, move the clean repository to `dotoricode/graphori`, disable Actions, and change only the clean repository to public.
5. Use `gh api` to enable vulnerability alerts, automated security fixes, secret scanning, push protection, and private vulnerability reporting where GitHub supports them.

No development branch, tag, pull request, Actions artifact, or old release is copied into the public repository.
