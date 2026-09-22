# Live outbound workflow

The generic Prospeo search/enrich and Instantly upload contracts were adapted from the existing Sentvia primitives (search_prospeo_people, enrich_prospeo_person, upload_to_instantly). Private customer configuration and organisation IDs were deliberately excluded. This is implementation reuse, not a recreation of production data.

## Inputs

Supply a private SQLite file with a companies table containing name, domain and website. The connector opens it read-only and selects a bounded batch ordered by domain. Exporting an approved subset from a hosted company database into this contract is currently the operator's responsibility.

Set the brief's research_input to a JSON integration plan, resolved relative to the brief:

```json
{
  "database": "companies.db",
  "company_limit": 25,
  "scoring_model": "your-openrouter-model-id",
  "min_score": 0.6,
  "contacts_per_company": 3,
  "seniorities": ["Founder/Owner", "C-Suite"]
}
```

The database path is relative to this plan. Company limit is 1–1000; contacts per company 1–100. Prospeo searches at most one page per company in this workflow; the standalone primitive supports up to ten pages. Check current provider-supported seniority values before spending.

Configure environment variables privately: FIRECRAWL_API_KEY, OPENROUTER_API_KEY, PROSPEO_API_KEY, INSTANTLY_API_KEY. The example scoring model is deliberately not a silently chosen paid provider.

## Execute and review

Schedule a brief using the normal CLI, then:

```bash
PYTHONPATH=src python -m outboundos.cli --workspace .outboundos run-due --live-research
PYTHONPATH=src python -m outboundos.cli --workspace .outboundos run-due --live-research --execute
```

The first command only lists scheduled tasks. Inspect each task's stored brief and plan before authorizing the second. Execution calls the database, Firecrawl, AI scoring and Prospeo. A score must include exact source quotations; invalid evidence or provider errors fail the task instead of yielding a misleading partial export. Successful stages cache within the workspace. New runs can deliberately reuse those cached results; agree the freshness requirement.

Use review and materialize from AGENTS.md. The payload includes sources, assessments, candidates, leads and the plan hash. Review contact destinations as well as company fit. Source/lead data are private run artifacts.

```bash
PYTHONPATH=src python -m outboundos.cli --workspace .outboundos upload --proposal <id> --campaign <id> --expected-org <id>
```

Preview is default. Append --execute only for an authorized upload. There is no campaign creation, activation or email-send method; uploading to an already active campaign can nevertheless trigger its existing sending workflow.

## Export safety

The upload requires a completed, approved proposal and an unchanged materialized artifact. It deduplicates email addresses, checks the API account organisation and campaign organisation, and asks Instantly to skip existing campaign leads. One batch is limited to 1000 leads. Split larger audiences into separately reviewed proposals.

An exclusive local lock and persisted in-flight marker guard the send. Successful calls retain the provider response including skipped/invalid counts. A timeout or unrecognised response blocks automatic retry; inspect the destination and preserve reconciliation evidence. No promise of exactly-once delivery is made across manual edits or separate workspaces.

Provider references: [Prospeo search](https://prospeo.io/api-docs/search-person), [Prospeo enrichment](https://prospeo.io/api-docs/enrich-person), [Instantly campaign](https://developer.instantly.ai/api-reference/campaign/get-campaign), [Firecrawl scrape](https://docs.firecrawl.dev/api-reference/endpoint/scrape). Tests inject synthetic provider responses and never use paid accounts.
