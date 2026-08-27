#!/usr/bin/env python3
"""Run the public release gate locally without GitHub Actions or publishing."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import site
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(argv: list[object], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    command = [str(item) for item in argv]
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root: Path, output: Path | None) -> dict[str, object]:
    root = root.resolve()
    if not (root / ".git").is_dir():
        raise ValueError("the full release verifier requires a Git repository")
    gitleaks = shutil.which("gitleaks")
    if not gitleaks:
        raise ValueError("gitleaks is required on PATH")
    if output is not None and output.exists():
        raise ValueError(f"output already exists: {output}")

    checks = (
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        [sys.executable, "-m", "compileall", "-q", "src", "tests", "scripts", "skills", "benchmarks"],
        [sys.executable, "scripts/validate_docs_indexes.py"],
        [sys.executable, "skills/graphori/scripts/validate_skill.py", "skills/graphori"],
        [sys.executable, "scripts/dashboard_smoke.py"],
        [sys.executable, "scripts/public_release_audit.py"],
    )
    for command in checks:
        run(command, cwd=root)
    run([gitleaks, "git", "--redact", "--no-banner"], cwd=root)
    run([gitleaks, "dir", "--redact", "--no-banner", root], cwd=root)

    with tempfile.TemporaryDirectory() as temporary_text:
        temporary = Path(temporary_text)
        build_env = temporary / "build-env"
        run([sys.executable, "-m", "venv", build_env], cwd=root)
        build_python = build_env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run([
            build_python, "-m", "pip", "install", "--quiet", "--upgrade",
            "pip", "build", "twine", "pip-audit",
        ], cwd=root)

        artifacts = temporary / "dist"
        run([build_python, "-m", "build", "--outdir", artifacts], cwd=root)
        distributions = sorted((*artifacts.glob("*.whl"), *artifacts.glob("*.tar.gz")))
        if len(distributions) != 2:
            raise ValueError("expected exactly one wheel and one source distribution")
        run([build_python, "-m", "twine", "check", *distributions], cwd=root)

        install_env = temporary / "install-env"
        run([sys.executable, "-m", "venv", install_env], cwd=root)
        install_python = install_env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        scripts_dir = install_env / ("Scripts" if os.name == "nt" else "bin")
        run([
            install_python, "-m", "pip", "install", "--quiet", "--upgrade",
            "pip", "setuptools",
        ], cwd=root)
        wheel = next(artifacts.glob("*.whl"))
        run([install_python, "-m", "pip", "install", "--quiet", "--no-deps", wheel], cwd=root)
        graphori_command = scripts_dir / ("graphori.exe" if os.name == "nt" else "graphori")
        run([graphori_command, "--help"], cwd=root)

        if os.name != "nt":
            fake_home = temporary / "home"
            fake_home.mkdir()
            run([
                root / "scripts/install_graphori.sh", "--mode", "solo",
                "--target", "both",
            ], cwd=root, env=dict(os.environ, HOME=str(fake_home)))

        site_packages = subprocess.check_output(
            [str(install_python), "-c", "import site; print(site.getsitepackages()[0])"],
            text=True,
        ).strip()
        sbom = artifacts / "sbom.cdx.json"
        pip_audit = build_env / ("Scripts/pip-audit.exe" if os.name == "nt" else "bin/pip-audit")
        run([
            pip_audit, "--path", site_packages, "--format", "cyclonedx-json",
            "--output", sbom,
        ], cwd=root)

        sums = artifacts / "SHA256SUMS"
        sums.write_text(
            "".join(
                f"{digest(path)}  {path.name}\n"
                for path in sorted(artifacts.iterdir()) if path != sums
            ),
            encoding="utf-8",
        )
        artifact_names = sorted(path.name for path in artifacts.iterdir())
        artifact_digests = {path.name: digest(path) for path in artifacts.iterdir()}
        if output is not None:
            shutil.copytree(artifacts, output)

    return {
        "status": "pass",
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True,
        ).strip(),
        "artifacts": artifact_names,
        "sha256": dict(sorted(artifact_digests.items())),
        "github_actions_used": False,
        "published": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(
            verify(args.root, args.output.resolve() if args.output else None),
            indent=2,
            sort_keys=True,
        ))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"LOCAL RELEASE VERIFICATION: FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
