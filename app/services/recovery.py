"""Local autosave snapshots and crash-recovery discovery."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.models.workbook import Workbook
from app.storage.json_storage import JsonWorkbookStorage


@dataclass(frozen=True, slots=True)
class RecoveryCandidate:
    path: Path
    source_path: str | None
    saved_at: str
    workbook_name: str


class RecoveryManager:
    """Write recoverable JSON snapshots without replacing user files."""

    def __init__(self, directory: str | Path | None = None) -> None:
        configured = directory or os.getenv("AUTOSAVE_DIR", "data/autosave")
        self.directory = Path(configured).expanduser()
        self.storage = JsonWorkbookStorage()

    def snapshot(self, workbook: Workbook, source_path: str | None, identity: str = "local") -> Path:
        key = f"{identity.lower().strip()}|{source_path or workbook.name}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
        target = self.directory / f"{digest}.recovery.json"
        previous = workbook.metadata.get("_recovery")
        workbook.metadata["_recovery"] = {
            "source_path": source_path,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "identity": identity.lower().strip(),
        }
        try:
            self.storage.save_workbook(str(target), workbook)
        finally:
            if previous is None:
                workbook.metadata.pop("_recovery", None)
            else:
                workbook.metadata["_recovery"] = previous
        return target

    def candidates(self, identity: str | None = None) -> list[RecoveryCandidate]:
        if not self.directory.exists():
            return []
        results: list[RecoveryCandidate] = []
        for path in self.directory.glob("*.recovery.json"):
            try:
                workbook = self.storage.load_workbook(str(path))
            except (OSError, ValueError):
                continue
            recovery = workbook.metadata.get("_recovery", {})
            if not isinstance(recovery, dict):
                continue
            if identity and recovery.get("identity") != identity.lower().strip():
                continue
            results.append(RecoveryCandidate(
                path=path,
                source_path=str(recovery.get("source_path")) if recovery.get("source_path") else None,
                saved_at=str(recovery.get("saved_at") or ""),
                workbook_name=workbook.name,
            ))
        return sorted(results, key=lambda item: item.saved_at, reverse=True)

    def restore(self, candidate: RecoveryCandidate) -> Workbook:
        workbook = self.storage.load_workbook(str(candidate.path))
        workbook.metadata.pop("_recovery", None)
        return workbook

    def discard(self, candidate_or_path: RecoveryCandidate | str | Path) -> None:
        path = candidate_or_path.path if isinstance(candidate_or_path, RecoveryCandidate) else Path(candidate_or_path)
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def discard_for(self, workbook: Workbook, source_path: str | None, identity: str = "local") -> None:
        key = f"{identity.lower().strip()}|{source_path or workbook.name}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
        self.discard(self.directory / f"{digest}.recovery.json")


def autosave_interval_seconds() -> int:
    value = int(os.getenv("AUTOSAVE_INTERVAL_SECONDS", "60"))
    if value < 15:
        raise ValueError("AUTOSAVE_INTERVAL_SECONDS must be at least 15 seconds.")
    return value


def autosave_enabled() -> bool:
    return os.getenv("AUTOSAVE_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
