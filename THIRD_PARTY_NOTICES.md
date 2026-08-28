# Third-party notices

Graphori's Python runtime declares no third-party runtime dependency in
`pyproject.toml`. It runs on the standard library.

One bundled asset carries an upstream license:

- `assets/fonts/SUIT-Variable.woff2` — SUIT, under the SIL Open Font License
  1.1. The full text is in [`assets/fonts/SUIT-OFL-1.1.txt`](assets/fonts/SUIT-OFL-1.1.txt).

The release gate installs its verification tools into a temporary isolated
environment; those tools are not redistributed here. Release artifacts ship an
SBOM generated from the built distribution.
