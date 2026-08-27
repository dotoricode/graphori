#!/usr/bin/env bash
set -euo pipefail

target="both"
skill="graphori"
force=0
while (($#)); do
  case "$1" in
    --target) target="${2:?--target needs codex, claude, or both}"; shift 2;;
    --skill) skill="${2:?--skill needs graphori or graphori-dashboard}"; shift 2;;
    --force) force=1; shift;;
    -h|--help) echo "usage: install_skill.sh [--target codex|claude|both] [--skill graphori|graphori-dashboard] [--force]"; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done
case "$target" in codex|claude) targets=("$target");; both) targets=(codex claude);; *) echo "invalid target: $target" >&2; exit 2;; esac
case "$skill" in graphori|graphori-dashboard);; *) echo "invalid skill: $skill" >&2; exit 2;; esac

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source="$repo_root/$skill"
validator="$repo_root/graphori/scripts/validate_skill.py"
home_path="${HOME:?HOME is required}"
python_bin="${GRAPHORI_PYTHON:-python3}"
command -v "$python_bin" >/dev/null 2>&1 || python_bin=python

same_tree() {
  local destination="$1"
  [[ -d "$destination" ]] || return 1
  diff -qr "$source" "$destination" >/dev/null
}

for kind in "${targets[@]}"; do
  if [[ "$kind" == codex ]]; then
    codex_skills_dir="${GRAPHORI_CODEX_SKILLS_DIR:-$home_path/.agents/skills}"
    destination="$codex_skills_dir/$skill"
  else
    destination="$home_path/.claude/skills/$skill"
  fi
  if [[ -e "$destination" ]]; then
    if same_tree "$destination"; then
      printf '%s: already matches canonical skill; validating.\n' "$kind"
    elif (( ! force )); then
      printf '%s destination exists and differs: %s. Use --force to create a backup and replace it.\n' "$kind" "$destination" >&2
      exit 1
    else
      stamp="$(date -u +%Y%m%d-%H%M%S)"
      backup="$destination.backup-$stamp"
      mv -- "$destination" "$backup"
      printf '%s: backed up existing skill to %s\n' "$kind" "$backup"
    fi
  fi
  if [[ ! -e "$destination" ]]; then
    mkdir -p "$(dirname "$destination")"
    cp -R -- "$source" "$destination"
    printf '%s: installed canonical skill at %s\n' "$kind" "$destination"
  fi
  "$python_bin" -B "$validator" "$destination"
done
printf '%s\n' 'Graphori skill installation complete.'
