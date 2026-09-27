# Experiment collaborator scope

## Purpose

Own behavior-specific collaborators used by the shared ExperimentRunner.

## Standards

Collaborators depend on engine ports and core models. They must not import `runner.py` or the `gamr_engine` package root. Keep provider calls, artifact evidence, and trace boundaries in the behavior owner that performs them.

## Source map

`records.py` owns shared runner records. `activity.py` owns progress and activity publication. `artifacts.py` owns evidence serialization helpers. `rendering.py` owns Scenario rendering and prompts. `model_response.py` owns model response framing. `results.py` owns CaseResult and RunResult construction. Conversation, discovery, case, and Adversarial Researcher lifecycles live in their same-named collaborators.

`discovery_contract.py` owns Task-required candidate fields and preflight prompts.
Path and Agent requirements come from each Task's discovery outputs and variable
bindings. Shared discovery models do not impose a filesystem root.

## Testing

Use fake ports by default. Focused regressions remain in the neighboring engine test suite.
`test_discovery_fields.py` covers Task-required fields, routing-only discovery,
provided targets, and preflight without filesystem assumptions.
