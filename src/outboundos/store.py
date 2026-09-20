"""Filesystem state store with atomic snapshots and an append-only event log."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, TypeVar

from .models import CampaignBrief, Proposal, Review, Task


T = TypeVar("T")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class FileStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        for name in ("briefs", "tasks", "proposals", "reviews", "artifacts"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "events.jsonl"

    def _path(self, collection: str, identifier: str) -> Path:
        if not SAFE_ID.fullmatch(identifier):
            raise ValueError(f"Unsafe identifier: {identifier!r}")
        return self.root / collection / f"{identifier}.json"

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        payload = asdict(value) if is_dataclass(value) else value
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        temp.replace(path)

    @staticmethod
    def _read(path: Path, factory: type[T]) -> T:
        if not path.exists():
            raise FileNotFoundError(path)
        return factory.from_dict(json.loads(path.read_text()))  # type: ignore[attr-defined]

    def save_brief(self, brief: CampaignBrief) -> None:
        self._write_json(self._path("briefs", brief.id), brief)

    def load_brief(self, brief_id: str) -> CampaignBrief:
        return self._read(self._path("briefs", brief_id), CampaignBrief)

    def save_task(self, task: Task) -> None:
        self._write_json(self._path("tasks", task.id), task)

    def load_task(self, task_id: str) -> Task:
        return self._read(self._path("tasks", task_id), Task)

    def list_tasks(self) -> list[Task]:
        return [Task.from_dict(json.loads(path.read_text())) for path in sorted((self.root / "tasks").glob("*.json"))]

    def save_proposal(self, proposal: Proposal) -> None:
        self._write_json(self._path("proposals", proposal.id), proposal)

    def load_proposal(self, proposal_id: str) -> Proposal:
        return self._read(self._path("proposals", proposal_id), Proposal)

    def list_proposals(self) -> list[Proposal]:
        return [Proposal.from_dict(json.loads(path.read_text())) for path in sorted((self.root / "proposals").glob("*.json"))]

    def save_review(self, review: Review) -> None:
        self._write_json(self._path("reviews", review.id), review)

    def save_artifact(self, proposal_id: str, payload: dict[str, Any]) -> Path:
        path = self._path("artifacts", proposal_id)
        self._write_json(path, payload)
        return path

    def append_event(self, event: dict[str, Any]) -> None:
        with self.events_path.open("a") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    def read_events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        return [json.loads(line) for line in self.events_path.read_text().splitlines() if line.strip()]

