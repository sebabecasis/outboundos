"""Human-governed task orchestration for OutboundOS."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .models import (
    PROPOSAL_APPROVED,
    PROPOSAL_PENDING,
    PROPOSAL_REJECTED,
    TASK_APPROVED,
    TASK_AWAITING_REVIEW,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_REJECTED,
    TASK_RUNNING,
    TASK_SCHEDULED,
    CampaignBrief,
    Proposal,
    Review,
    Task,
)
from .research import build_candidate_payload
from .store import FileStore


class WorkflowError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class OutboundWorkflow:
    def __init__(
        self,
        workspace: str | Path,
        *,
        researcher: Callable[[CampaignBrief], dict] = build_candidate_payload,
        clock: Callable[[], datetime] = utc_now,
    ):
        self.store = FileStore(workspace)
        self.researcher = researcher
        self.clock = clock

    def _event(self, name: str, *, task_id: str, **details: object) -> None:
        self.store.append_event(
            {
                "event": name,
                "task_id": task_id,
                "timestamp": iso(self.clock()),
                **details,
            }
        )

    def schedule(self, brief: CampaignBrief, *, scheduled_for: datetime | None = None) -> Task:
        now = self.clock()
        task = Task(
            id=f"task_{uuid4().hex[:12]}",
            brief_id=brief.id,
            kind="research_candidates",
            status=TASK_SCHEDULED,
            scheduled_for=iso(scheduled_for or now),
            created_at=iso(now),
            updated_at=iso(now),
        )
        self.store.save_brief(brief)
        self.store.save_task(task)
        self._event("task.scheduled", task_id=task.id, brief_id=brief.id, scheduled_for=task.scheduled_for)
        return task

    def run_due(self, *, now: datetime | None = None) -> list[Proposal]:
        cutoff = now or self.clock()
        proposals: list[Proposal] = []
        for task in self.store.list_tasks():
            if task.status != TASK_SCHEDULED or parse_time(task.scheduled_for) > cutoff:
                continue
            proposals.append(self._run_task(task))
        return proposals

    def _run_task(self, task: Task) -> Proposal:
        task.status = TASK_RUNNING
        task.updated_at = iso(self.clock())
        self.store.save_task(task)
        self._event("task.started", task_id=task.id)
        try:
            brief = self.store.load_brief(task.brief_id)
            payload = self.researcher(brief)
            proposal = Proposal(
                id=f"proposal_{uuid4().hex[:12]}",
                task_id=task.id,
                action_type="use_candidate_audience",
                summary=f"Review {len(payload.get('candidates', []))} candidate companies for {brief.audience}",
                payload=payload,
                status=PROPOSAL_PENDING,
                created_at=iso(self.clock()),
                updated_at=iso(self.clock()),
            )
            self.store.save_proposal(proposal)
            task.status = TASK_AWAITING_REVIEW
            task.proposal_id = proposal.id
            task.updated_at = iso(self.clock())
            self.store.save_task(task)
            self._event("proposal.created", task_id=task.id, proposal_id=proposal.id)
            self._event("task.awaiting_review", task_id=task.id, proposal_id=proposal.id)
            return proposal
        except Exception as exc:
            task.status = TASK_FAILED
            task.error = f"{type(exc).__name__}: {exc}"
            task.updated_at = iso(self.clock())
            self.store.save_task(task)
            self._event("task.failed", task_id=task.id, error=task.error)
            raise

    def review(self, proposal_id: str, *, decision: str, reviewer: str, note: str = "") -> Review:
        if decision not in {"approve", "reject"}:
            raise ValueError("Decision must be 'approve' or 'reject'")
        proposal = self.store.load_proposal(proposal_id)
        if proposal.status != PROPOSAL_PENDING:
            raise WorkflowError(f"Proposal {proposal.id} is already {proposal.status}")
        task = self.store.load_task(proposal.task_id)
        if task.status != TASK_AWAITING_REVIEW:
            raise WorkflowError(f"Task {task.id} is not awaiting review")

        approved = decision == "approve"
        proposal.status = PROPOSAL_APPROVED if approved else PROPOSAL_REJECTED
        proposal.updated_at = iso(self.clock())
        task.status = TASK_APPROVED if approved else TASK_REJECTED
        task.updated_at = iso(self.clock())
        review = Review(
            id=f"review_{uuid4().hex[:12]}",
            proposal_id=proposal.id,
            task_id=task.id,
            decision=decision,
            reviewer=reviewer,
            note=note,
            created_at=iso(self.clock()),
        )
        self.store.save_proposal(proposal)
        self.store.save_task(task)
        self.store.save_review(review)
        self._event(
            f"proposal.{proposal.status}",
            task_id=task.id,
            proposal_id=proposal.id,
            review_id=review.id,
            reviewer=reviewer,
        )
        return review

    def materialize(self, proposal_id: str) -> Path:
        proposal = self.store.load_proposal(proposal_id)
        task = self.store.load_task(proposal.task_id)
        if proposal.status != PROPOSAL_APPROVED or task.status != TASK_APPROVED:
            raise WorkflowError("Only an explicitly approved proposal can produce an output")
        artifact = {
            "proposal_id": proposal.id,
            "task_id": task.id,
            "action_type": proposal.action_type,
            "approved_payload": proposal.payload,
            "materialized_at": iso(self.clock()),
        }
        path = self.store.save_artifact(proposal.id, artifact)
        task.status = TASK_COMPLETED
        task.output_path = str(path)
        task.updated_at = iso(self.clock())
        self.store.save_task(task)
        self._event("task.completed", task_id=task.id, proposal_id=proposal.id, output_path=str(path))
        return path

