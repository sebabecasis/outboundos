from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from outboundos import CampaignBrief, OutboundWorkflow, WorkflowError


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


class WorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.companies = self.root / "companies.json"
        self.companies.write_text(
            json.dumps(
                [
                    {"name": "A", "domain": "a.example", "text": "workflow automation with human review"},
                    {"name": "B", "domain": "b.example", "text": "workflow automation consumer mobile app"},
                    {"name": "C", "domain": "c.example", "text": "unrelated services"},
                ]
            )
        )
        self.brief = CampaignBrief(
            id="brief-one",
            objective="Find governed automation teams",
            audience="Operations teams",
            signals=["workflow automation", "human review"],
            exclusion_signals=["consumer mobile app"],
            research_input=str(self.companies),
        )
        self.workflow = OutboundWorkflow(self.root / "state", clock=lambda: NOW)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_future_task_does_not_run(self) -> None:
        task = self.workflow.schedule(self.brief, scheduled_for=NOW + timedelta(hours=1))
        self.assertEqual([], self.workflow.run_due(now=NOW))
        self.assertEqual("scheduled", self.workflow.store.load_task(task.id).status)

    def test_due_task_creates_evidence_backed_proposal(self) -> None:
        task = self.workflow.schedule(self.brief)
        proposal = self.workflow.run_due(now=NOW)[0]
        candidates = proposal.payload["candidates"]
        self.assertEqual(["a.example"], [candidate["domain"] for candidate in candidates])
        self.assertEqual(2, candidates[0]["score"])
        self.assertIn("human review", candidates[0]["evidence"])
        self.assertEqual("awaiting_review", self.workflow.store.load_task(task.id).status)

    def test_output_is_blocked_until_explicit_approval(self) -> None:
        self.workflow.schedule(self.brief)
        proposal = self.workflow.run_due(now=NOW)[0]
        with self.assertRaisesRegex(WorkflowError, "explicitly approved"):
            self.workflow.materialize(proposal.id)

    def test_approved_proposal_can_be_materialized_after_resume(self) -> None:
        task = self.workflow.schedule(self.brief)
        proposal = self.workflow.run_due(now=NOW)[0]
        self.workflow.review(proposal.id, decision="approve", reviewer="operator", note="Evidence checked")

        resumed = OutboundWorkflow(self.root / "state", clock=lambda: NOW)
        artifact = resumed.materialize(proposal.id)

        self.assertTrue(artifact.exists())
        self.assertEqual("completed", resumed.store.load_task(task.id).status)
        events = [row["event"] for row in resumed.store.read_events()]
        self.assertEqual(
            [
                "task.scheduled",
                "task.started",
                "proposal.created",
                "task.awaiting_review",
                "proposal.approved",
                "task.completed",
            ],
            events,
        )

    def test_rejected_proposal_cannot_be_materialized(self) -> None:
        task = self.workflow.schedule(self.brief)
        proposal = self.workflow.run_due(now=NOW)[0]
        self.workflow.review(proposal.id, decision="reject", reviewer="operator")
        self.assertEqual("rejected", self.workflow.store.load_task(task.id).status)
        with self.assertRaises(WorkflowError):
            self.workflow.materialize(proposal.id)

    def test_proposal_can_only_be_reviewed_once(self) -> None:
        self.workflow.schedule(self.brief)
        proposal = self.workflow.run_due(now=NOW)[0]
        self.workflow.review(proposal.id, decision="approve", reviewer="operator")
        with self.assertRaisesRegex(WorkflowError, "already approved"):
            self.workflow.review(proposal.id, decision="reject", reviewer="operator")


if __name__ == "__main__":
    unittest.main()

