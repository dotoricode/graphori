"""Content-addressed evidence storage.

Objects are named by their SHA-256 digest, never by a caller-supplied
filename. A JSON manifest maps evidence IDs to digest/size/label metadata so
callers can attach a human-readable label without that label ever becoming
part of the storage path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import re
import uuid

from .journal import RunPaths


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(tmp), str(path))


@dataclass
class EvidenceStore:
    paths: RunPaths

    def __post_init__(self) -> None:
        self.objects_dir = self.paths.evidence_dir / "objects"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.paths.evidence_dir / "manifest.json"
        if not self.manifest_path.exists():
            _atomic_write_text(self.manifest_path, json.dumps({}, sort_keys=True, indent=2))

    def _read_manifest(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        _atomic_write_text(self.manifest_path, json.dumps(manifest, sort_keys=True, indent=2))

    def put(self, data: bytes, *, label: str | None = None) -> str:
        digest = hashlib.sha256(data).hexdigest()
        evidence_id = f"ev_sha256_{digest}"
        obj_path = self.objects_dir / f"{digest}.bin"
        if not obj_path.exists():
            tmp = self.objects_dir / f"{digest}.{uuid.uuid4().hex}.tmp"
            with open(tmp, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(tmp), str(obj_path))
        manifest = self._read_manifest()
        entry = manifest.get(evidence_id, {"sha256": digest, "size": len(data), "labels": []})
        if label is not None:
            safe_label = re.sub(r"[^A-Za-z0-9 _:-]", "_", str(label))[:200]
            if safe_label not in entry["labels"]:
                entry["labels"].append(safe_label)
        manifest[evidence_id] = entry
        self._write_manifest(manifest)
        return evidence_id

    def get(self, evidence_id: str) -> bytes:
        manifest = self._read_manifest()
        entry = manifest.get(evidence_id)
        if entry is None:
            raise KeyError(f"unknown evidence_id: {evidence_id!r}")
        return (self.objects_dir / f"{entry['sha256']}.bin").read_bytes()

    def manifest(self) -> dict[str, Any]:
        return self._read_manifest()
