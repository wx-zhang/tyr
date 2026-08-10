# Dataset format

Datasets are immutable, schema-validated JSON documents. A dataset directory
contains a `dataset.json` manifest, optional `discovery.json`,
`methodology.json`, and `evaluation.json` plans, plus ordered `cases/*.json`
scenario files. References are confined below the dataset directory and every
case ID is unique.

`datasets/first-plan` contains five scenarios. Two are enabled by default; the
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
dataset declares an action-enabled profile.

Validate with:

```bash
uv run gamr dataset validate datasets/first-plan
```

The generated contract is [schemas/dataset.schema.json](../schemas/dataset.schema.json).
Canonical completed runs use [schemas/run-result.schema.json](../schemas/run-result.schema.json).
