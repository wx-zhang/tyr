# Run-evidence fixture bundles

These bundles are deterministic, small, and redacted. They model the source evidence that the
normalizer and projection rebuild consume; they are not live Tyr or model captures.

| Bundle | Scenario |
| --- | --- |
| `live` | Running multi-case read-only run with an active case |
| `completed` | Terminal run with a valid `result.json` |
| `interrupted` | Non-terminal run with checkpoint and no result |
| `malformed` | Retained diagnostic whose detail is explicitly malformed |
| `approval` | `approval_required` run waiting for a human decision |
| `delegation` | Outer operation terminal while delegated work is still unsettled |
| `bridge` | Outer operation terminal while bridge work is still unsettled |

The common files use the canonical bundle names: `run.json`, `task.snapshot.json`,
`checkpoint.json`, `events.jsonl`, `transcript.jsonl`, and optional `result.json` and `raw/` files.
All times are UTC, IDs are stable fixture values, and all summaries are safe redacted text.
