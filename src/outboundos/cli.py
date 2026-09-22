"""Command-line interface for the OutboundOS template."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import CampaignBrief
from .workflow import OutboundWorkflow, parse_time


def _brief(path: Path) -> CampaignBrief:
    data = json.loads(path.read_text())
    source = Path(data["research_input"])
    if not source.is_absolute():
        data["research_input"] = str((path.parent / source).resolve())
    return CampaignBrief.from_dict(data)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="outboundos")
    root.add_argument("--workspace", default=".outboundos", help="Directory for workflow state")
    commands = root.add_subparsers(dest="command", required=True)

    schedule = commands.add_parser("schedule", help="Schedule a campaign research task")
    schedule.add_argument("--brief", type=Path, required=True)
    schedule.add_argument("--at", help="ISO-8601 execution time; defaults to now")

    run = commands.add_parser("run-due", help="Run every due scheduled task")
    run.add_argument("--now", help="ISO-8601 cutoff; defaults to now")
    run.add_argument("--live-research", action="store_true", help="Use database, Firecrawl, AI scoring and Prospeo")
    run.add_argument("--execute", action="store_true", help="Authorize paid research for due tasks")

    upload = commands.add_parser("upload", help="Preview or execute an approved Instantly export")
    upload.add_argument("--proposal", required=True)
    upload.add_argument("--campaign", required=True)
    upload.add_argument("--expected-org", required=True)
    upload.add_argument("--execute", action="store_true")

    review = commands.add_parser("review", help="Approve or reject a proposal")
    review.add_argument("--proposal", required=True)
    review.add_argument("--decision", choices=("approve", "reject"), required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--note", default="")

    materialize = commands.add_parser("materialize", help="Produce the approved output")
    materialize.add_argument("--proposal", required=True)

    commands.add_parser("status", help="Print current tasks and proposals")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    workflow = OutboundWorkflow(args.workspace)

    if args.command == "schedule":
        task = workflow.schedule(_brief(args.brief), scheduled_for=parse_time(args.at) if args.at else None)
        print(json.dumps(task.to_dict(), indent=2))
    elif args.command == "run-due":
        if args.live_research:
            from .integrations import live_research
            if not args.execute:
                print(json.dumps({"dry_run": True, "tasks": [t.to_dict() for t in workflow.store.list_tasks() if t.status == "scheduled"]}, indent=2))
                return 0
            workflow.researcher = lambda brief: live_research(brief, execute=True, cache=workflow.store.root / "research-cache")
        proposals = workflow.run_due(now=parse_time(args.now) if args.now else None)
        print(json.dumps([proposal.to_dict() for proposal in proposals], indent=2))
    elif args.command == "review":
        review = workflow.review(
            args.proposal,
            decision=args.decision,
            reviewer=args.reviewer,
            note=args.note,
        )
        print(json.dumps(review.to_dict(), indent=2))
    elif args.command == "materialize":
        print(workflow.materialize(args.proposal))
    elif args.command == "upload":
        from .integrations import upload_approved
        print(json.dumps(upload_approved(workflow, args.proposal, campaign_id=args.campaign,
            expected_org=args.expected_org, execute=args.execute), indent=2))
    elif args.command == "status":
        print(
            json.dumps(
                {
                    "tasks": [task.to_dict() for task in workflow.store.list_tasks()],
                    "proposals": [proposal.to_dict() for proposal in workflow.store.list_proposals()],
                    "events": workflow.store.read_events(),
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
