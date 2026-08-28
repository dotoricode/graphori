#!/usr/bin/env bash
# Local-only public-beta installer.  It prints before mutating with --dry-run.
set -euo pipefail

mode="runtime"; target="codex"; dry_run=0; force=0; python_bin="${GRAPHORI_PYTHON:-python3}"
while (($#)); do
  case "$1" in
    --mode) mode="${2:?--mode needs runtime or solo}"; shift 2 ;;
    --target) target="${2:?--target needs codex, claude, or both}"; shift 2 ;;
    --python) python_bin="${2:?--python needs an interpreter}"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    --force) force=1; shift ;;
    -h|--help) echo "usage: install_graphori.sh --mode runtime|solo [--target codex|claude|both] [--python PYTHON] [--dry-run] [--force]"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
case "$mode" in runtime|solo) ;; *) echo "invalid mode: $mode" >&2; exit 2;; esac
case "$target" in codex|claude|both) ;; *) echo "invalid target: $target" >&2; exit 2;; esac
if (( dry_run )); then
  if [[ "$mode" == runtime ]]; then
    printf 'DRY RUN: %q -m pip install --no-deps %q\n' "$python_bin" "$repo_root"
  else
    printf 'DRY RUN: %q --target %q%s\n' "$repo_root/scripts/install_skill.sh" "$target" "$([[ $force == 1 ]] && printf ' --force')"
  fi
  exit 0
fi
if [[ "$mode" == runtime ]]; then
  command -v "$python_bin" >/dev/null 2>&1 || { echo "Python interpreter not found: $python_bin" >&2; exit 1; }
  "$python_bin" -m pip install --no-deps "$repo_root"
else
  args=(--target "$target")
  (( force )) && args+=(--force)
  "$repo_root/scripts/install_skill.sh" "${args[@]}"
fi
