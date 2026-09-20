"""Deterministic fixture research used by the template workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import CampaignBrief


def build_candidate_payload(brief: CampaignBrief) -> dict[str, Any]:
    """Return evidence-backed candidates from a JSON fixture.

    This deliberately does not call an LLM or external service. A real system can
    replace this function while preserving the workflow and review contracts.
    """
    source = Path(brief.research_input)
    records = json.loads(source.read_text())
    if not isinstance(records, list):
        raise ValueError("Research input must contain a JSON list")

    signals = [signal.casefold() for signal in brief.signals]
    exclusions = [signal.casefold() for signal in brief.exclusion_signals]
    candidates: list[dict[str, Any]] = []

    for record in records:
        text = str(record.get("text", ""))
        folded = text.casefold()
        blocked_by = [signal for signal in exclusions if signal in folded]
        if blocked_by:
            continue
        matched = [original for original, signal in zip(brief.signals, signals) if signal in folded]
        if not matched:
            continue
        candidates.append(
            {
                "name": str(record.get("name", record.get("domain", "Unknown"))),
                "domain": str(record.get("domain", "")),
                "score": len(matched),
                "matched_signals": matched,
                "evidence": text[:280],
            }
        )

    candidates.sort(key=lambda row: (-row["score"], row["domain"]))
    return {
        "brief_id": brief.id,
        "objective": brief.objective,
        "audience": brief.audience,
        "signals": brief.signals,
        "candidates": candidates,
    }

