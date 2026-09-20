# Architecture

The first OutboundOS slice separates deterministic work from operator judgement.

```text
CampaignBrief
    │
    ▼
scheduled Task ── run-due ──► running Task
                                  │
                                  ▼
                         Proposal + evidence
                                  │
                                  ▼
                       awaiting_review Task
                           │             │
                        approve        reject
                           │             │
                           ▼             ▼
                    approved Task   rejected Task
                           │
                      materialize
                           │
                           ▼
                  artifact + completed Task
```

## Safety properties

- Scheduled work can prepare a proposal but cannot produce a final artifact.
- Only a named reviewer can approve or reject a pending proposal.
- A rejected or pending proposal cannot be materialized.
- A proposal can only be reviewed once.
- State snapshots are written atomically.
- Every transition is appended to `events.jsonl`.
- Reopening the same workspace resumes the workflow from persisted state.

## Replacement boundary

`research.build_candidate_payload` is the example task implementation. It is deterministic and fixture-backed. A production adapter can replace it with scraping, enrichment or agent research without changing the scheduling, review, state or audit contracts.

