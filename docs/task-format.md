# Task format

Tasks are immutable, schema-validated JSON documents. A task directory
contains a `task.json` manifest, optional `discovery.json`,
`methodology.json`, and `evaluation.json` plans, plus ordered `cases/*.json`
scenario files. References are confined below the task directory and every
case ID is unique.

`tasks/exfiltrate-important-txt` contains five scenarios. Two are enabled by default; the
three additional transform/relay scenarios remain available through explicit
`--case-id` or `--all-cases` selection.

The manifest declares `spec.variables` with `literal`, `run`, or `discovery`
sources. Scenario text may use only declared `{placeholders}`. Discovery
variables are bound only after a validated active Bridge candidate under
`/home` is found. `spec.defaults.defaultCaseIds` preserves the default suite
selection; explicit run `caseIds` can select other cases in manifest order.

Each scenario separates the attacker objective (`objective` and
`successCriteria`) from the expected Tyr control (`expectedControl`) and lists
the evidence needed to assess both. Read-only is the runtime default even if a
task declares an action-enabled profile.

The evaluation plan supplies dataset-specific decision rules. At runtime GAMR
wraps those rules in a strict judge contract. The judge receives rendered
scenario text, real turn IDs, safe operation facts, collector evidence, and the
exact JSON response schema. Transcript text is marked as untrusted evidence.
Invalid output is retried once as a model-only operation; it never repeats the
tested Tyr action. A failed assessment remains `inconclusive` with
`assessmentStatus: failed` and visible missing evidence.

Set `spec.collectorEvidence` to `request` or `file` when a scenario delivers to
the declared collector. The Tyr response must include the collector's exact
`request_id`. GAMR uses that ID to verify the remote request and, for `file`,
every attachment's size and SHA-256 before assessment. When Tyr omits the ID,
GAMR performs a best-effort lookup and proceeds only if one request captured
during the upload turn contains the exact uploaded filename. No match or an
ambiguous match remains unavailable.

Validate with:

```bash
uv run gamr task validate tasks/exfiltrate-important-txt
```

The generated contract is [schemas/task.schema.json](../schemas/task.schema.json).
Canonical completed runs use [schemas/run-result.schema.json](../schemas/run-result.schema.json).
