# Limitations

- Direct providers require their own installed, authenticated CLIs; Graphori does not supply models or accounts.
- The generic verifier only reports the command it was given. Passing tests are evidence about that command, not a general correctness claim.
- Locale changes presentation only. Canonical identifiers remain English and a digest does not encode translated labels.
- Journal replay is local and assumes the stored files are available and readable. It intentionally refuses unsafe resume cases.
- The dashboard and learning game are explanatory interfaces, not evidence that an external provider is active.
- The repository publishes a 72-run three-arm benchmark and one smaller historical comparison. The 72 runs use four small deterministic Python fixtures, not production repositories; they do not prove that Graphori will improve a particular codebase.
- Public-release evidence is produced by the local verifier; this repository does not use GitHub Actions.
- The dedicated generic-adapter fixture passed on one macOS 26.5.2 x86_64 host with Python 3.11 and 3.14. That is scoped evidence, not a claim about every macOS version or architecture. No Linux release gate is claimed; Windows installation and Job Object behavior remain experimental.
- CodeQL, OpenSSF Scorecard, and OIDC build attestations are not part of this no-Actions release. Gitleaks, `pip-audit`, an SBOM, artifact hashes, and reproducible local commands are the published evidence boundary.
