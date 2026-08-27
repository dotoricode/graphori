# Limitations

- Direct providers require their own installed, authenticated CLIs; Graphori does not supply models or accounts.
- The generic verifier only reports the command it was given. Passing tests are evidence about that command, not a general correctness claim.
- Locale changes presentation only. Canonical identifiers remain English and a digest does not encode translated labels.
- Journal replay is local and assumes the stored files are available and readable. It intentionally refuses unsafe resume cases.
- The dashboard and learning game are explanatory interfaces, not evidence that an external provider is active.
- There are no published performance numbers in this beta. The benchmark protocol is scaffolding, not a result.
- Public-release evidence is produced by the local verifier; this repository does not use GitHub Actions.
- The current public-beta gate was executed on macOS with Python 3.11 and 3.12. Windows-specific installation and Job Object behavior remain experimental rather than verified release claims.
- CodeQL, OpenSSF Scorecard, and OIDC build attestations are not part of this no-Actions release. Gitleaks, `pip-audit`, an SBOM, artifact hashes, and reproducible local commands are the published evidence boundary.
