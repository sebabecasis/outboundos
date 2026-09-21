# OutboundOS

Clean-room template extracted from a working outbound operating system.

## Repository status

The first working slice is implemented. No Disciple data, credentials or production integrations belong in this repository.

The first working slice will demonstrate:

```text
campaign brief
→ scheduled research task
→ proposed action
→ operator review
→ approved output
→ run log
```

## Run the example

The package has no runtime dependencies outside Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

outboundos --workspace .demo schedule \
  --brief examples/sample-campaign/brief.json

outboundos --workspace .demo run-due
outboundos --workspace .demo status
```

Copy the proposal ID from `run-due`, then make an explicit decision:

```bash
outboundos --workspace .demo review \
  --proposal <proposal-id> \
  --decision approve \
  --reviewer operator \
  --note "Evidence checked"

outboundos --workspace .demo materialize \
  --proposal <proposal-id>
```

Nothing is materialized before approval. Rejection is terminal for the proposal.

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

See [`docs/architecture.md`](docs/architecture.md) for the state machine and replacement boundary.
