# Limitations

- Direct providers require their own installed, authenticated CLIs; Graphori does not supply models or accounts.
- Provider readiness checks CLI compatibility and local authentication without a paid model call. A provider can still fail after dispatch because of quota, service, network, or policy changes; Graphori records that outcome and does not silently reroute an unknown attempt.
- Cross-provider review is an AI review report, not a verification verdict. A blocking report stops the graph, while only the later deterministic command can record PASS. If both providers are not ready, the plan records a deterministic-only downgrade.
- The generic verifier only reports the command it was given. Passing tests are evidence about that command, not a general correctness claim.
- Live Verify is opt-in and benefits only slow, repeatable, local checks with enough overlap. It rejects symlink snapshots and falls back for unsupported or changed workspaces. Its published numbers are synthetic control-plane wall time, not Codex or Claude end-to-end performance.
- Locale changes presentation only. Canonical identifiers remain English and a digest does not encode translated labels.
- Journal replay is local and assumes the stored files are available and readable. It intentionally refuses unsafe resume cases.
- The dashboard and learning game are explanatory interfaces, not evidence that an external provider is active.
- The repository publishes a 72-run three-arm benchmark and one smaller historical comparison. The 72 runs use four small deterministic Python fixtures, not production repositories; they do not prove that Graphori will improve a particular codebase.
- Public-release evidence is produced by the local verifier; this repository does not use GitHub Actions.
- The dedicated generic-adapter fixture passed on one macOS 26.5.2 x86_64 host with Python 3.11 and 3.14. That is scoped evidence, not a claim about every macOS version or architecture. No Linux release gate is claimed; Windows installation and Job Object behavior remain experimental.
- CodeQL, OpenSSF Scorecard, and OIDC build attestations are not part of this no-Actions release. Gitleaks, `pip-audit`, an SBOM, artifact hashes, and reproducible local commands are the published evidence boundary.
