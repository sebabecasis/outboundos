"""Data contracts for the first OutboundOS workflow slice."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


TASK_SCHEDULED = "scheduled"
TASK_RUNNING = "running"
TASK_AWAITING_REVIEW = "awaiting_review"
TASK_APPROVED = "approved"
TASK_REJECTED = "rejected"
TASK_COMPLETED = "completed"
TASK_FAILED = "failed"

PROPOSAL_PENDING = "pending_review"
PROPOSAL_APPROVED = "approved"
PROPOSAL_REJECTED = "rejected"


@dataclass(slots=True)
class CampaignBrief:
    id: str
    objective: str
    audience: str
    signals: list[str]
    research_input: str
    exclusion_signals: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignBrief":
        required = ("id", "objective", "audience", "signals", "research_input")
        missing = [key for key in required if not data.get(key)]
        if missing:
            raise ValueError(f"Campaign brief missing required fields: {', '.join(missing)}")
        if not isinstance(data["signals"], list) or not all(
            isinstance(item, str) and item.strip() for item in data["signals"]
        ):
            raise ValueError("Campaign brief signals must be a non-empty list of strings")
        return cls(
            id=str(data["id"]),
            objective=str(data["objective"]),
            audience=str(data["audience"]),
            signals=[str(item) for item in data["signals"]],
            research_input=str(data["research_input"]),
            exclusion_signals=[str(item) for item in data.get("exclusion_signals", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Task:
    id: str
    brief_id: str
    kind: str
    status: str
    scheduled_for: str
    created_at: str
    updated_at: str
    proposal_id: str | None = None
    output_path: str | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Proposal:
    id: str
    task_id: str
    action_type: str
    summary: str
    payload: dict[str, Any]
    status: str
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Proposal":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Review:
    id: str
    proposal_id: str
    task_id: str
    decision: str
    reviewer: str
    note: str
    created_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Review":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

