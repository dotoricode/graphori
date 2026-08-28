#!/usr/bin/env python3
"""Publish an atomic dashboard snapshot derived from the journal."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from graphori_core.dashboard import DashboardStore


def publish(root: Path, run_id: str, output: Path) -> dict:
    snapshot, _events = DashboardStore(root).snapshot(run_id)
    snapshot["publisher"] = "graphori-journal-snapshot"
    snapshot["publishedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(snapshot, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish a truthful Graphori dashboard snapshot")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    snapshot = publish(args.root, args.run_id, args.output)
    print(json.dumps({"run_id": snapshot["run_id"], "state": snapshot["state"],
                      "percent": snapshot["progress"]["percent"],
                      "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
