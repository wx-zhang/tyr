---
name: execute-adv-task
description: Resolve, validate, and execute a GAMR adversarial Task through the `gamr` CLI, with optional selection of one, several, default, or all Scenarios. Use when the user asks to run, execute, or test a GAMR task by path, task ID, title, objective, or description, including phrases such as `execute adv task`, `run this task`, or `run scenario`.
---

# Resolve the Task

1. Work from the repository root that contains `pyproject.toml` and `tasks/`.
2. Use the user's path when it names a directory containing `task.json`.
3. Run the task listing when the user supplies an ID, title, objective, or description:

   ```bash
   uv run gamr task list
   ```

4. Match an exact task ID or title first.
5. Read candidate `task.json` files when the listing does not identify one exact match.
6. Read candidate `cases/*.json` files when the description refers to a Scenario objective, title, category, tag, or step.
7. Select the sole clear match.
8. Ask the user to choose when two or more candidates remain plausible.
9. Stop when no task matches.
10. Report the searched description and task root when no task matches.

# Validate the Task

1. Run validation before every execution:

   ```bash
   uv run gamr task validate [task-directory]
   ```

2. Stop when validation returns a non-zero exit code.
3. Report the validation output verbatim enough to identify each invalid file or field.
4. Do not edit the Task unless the user asks for a repair.

# Select Scenarios

1. Read `[task-directory]/task.json`.
2. Read every Scenario file named by `spec.scenarios` or its `spec.cases` alias.
3. Record each Scenario's `metadata.id`, `metadata.title`, and `spec.objective`.
4. Use `--scenario-id [scenario-id]` when the user names one Scenario.
5. Repeat `--scenario-id` for each user-selected Scenario:

   ```bash
   uv run gamr experiment run [task-directory] \
     --scenario-id [first-scenario-id] \
     --scenario-id [second-scenario-id] \
     --approval-gated \
     --confirm-actions
   ```

6. Use `--all-scenarios` only when the user requests every Scenario.
7. Omit both selection options when the user requests the Task defaults.
8. Tell the user which Scenario IDs the Task defaults select when no selection was supplied.
9. Ask the user to choose `Task defaults`, `All Scenarios`, or specific Scenario IDs when the requested scope is unclear and the Task contains more than one Scenario.
10. Reject Scenario IDs absent from the Task before starting the Experiment.
11. Never combine `--all-scenarios` with `--scenario-id`.

# Always Use Approval-Gated Mode

1. Always execute adversarial Tasks in Approval-gated mode. Never choose read-only mode.
2. Add `--approval-gated` to every `gamr experiment run` command. `--allow-actions` is an equivalent CLI alias.
3. Explain that Approval-gated mode permits action requests while Tyr still requires a recorded human decision for every action.
4. Use both required flags for a non-interactive Approval-gated run:

   ```bash
   uv run gamr experiment run [task-directory] [scenario-options] \
     --approval-gated \
     --confirm-actions
   ```

5. Use `--approval-gated` without `--confirm-actions` only when the command has an interactive terminal and the user will answer its confirmation prompt.
6. Never approve Tyr actions on the user's behalf.

# Execute the Experiment

1. Run the assembled `uv run gamr experiment run` command from the repository root.
2. Preserve live terminal output until the command exits.
3. Do not retry a failed or interrupted Experiment automatically; an external step may already have executed.
4. Treat Ctrl+C exit code 130 as a cancelled Experiment.
5. Report a missing `TYR_MCP_TOKEN`, `OPENROUTER_API_KEY`, or `GAMR_MODEL_NAME` exactly as emitted by the CLI.
6. Stop when provider configuration is missing.
7. Do not print credential values.

# Verify the Result

1. Capture the Experiment ID and result path printed by the CLI.
2. Run canonical result validation after the Experiment produces `result.json`:

   ```bash
   uv run gamr result validate [result-path]
   ```

3. Read `[result-path]` after validation succeeds.
4. Report the Experiment outcome.
5. Report each executed Scenario ID, objective status, security verdict, and summary.
6. Report every Experiment or Scenario error.
7. Preserve evidence in `.gamr/runs/[experiment-id]/`; do not rewrite the run bundle.

# Output Contract

Return:

- Task directory and task ID.
- Selected Scenario IDs and whether selection came from defaults, explicit IDs, or `--all-scenarios`.
- Action mode.
- Exact executed command with secret values omitted.
- Experiment ID and terminal state.
- Result path and validation result.
- Per-Scenario objective status, verdict, and summary.
- Failure or cancellation details when the run does not complete.
