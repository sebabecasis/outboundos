"""OutboundOS: a small, human-governed workflow template."""

from .models import CampaignBrief, Proposal, Review, Task
from .workflow import OutboundWorkflow, WorkflowError

__all__ = [
    "CampaignBrief",
    "OutboundWorkflow",
    "Proposal",
    "Review",
    "Task",
    "WorkflowError",
]

