---
name: generate-adv-report
description: Collect authored and Adversarial Researcher Scenarios with their latest run results, steps, and evidence links in a Markdown report. Fire when the user asks for `generate-adv-report`, an adversarial scenario report, or a report of GAMR scenarios with results and run evidence.
disable-model-invocation: true
---

# Workflow

1. Resolve the repository root from the user's path.
2. Run the helper from the repository root:

   ```bash
   uv run python .agents/skills/generate-adv-report/scripts/generate_report.py --root [repository-root]
   ```

3. Read the report path printed by the helper.
4. Confirm the report contains the task count.
5. Confirm the report contains the scenario count.
6. Confirm every reported Scenario contains `Steps`.
7. Confirm every reported Scenario contains `Run evidence` links.
8. Return the report path.

# Failure handling
- Stop when `tasks/` is missing.
- Report the missing repository path.
- Stop when the helper reports invalid JSON.
- Report the exact file path from the error.
- Preserve an existing report when generation fails.
- Do not inspect or rewrite raw evidence files to repair malformed run data.

# Output contract

- Write one Markdown file under `.gamr/reports/`.
- Name the file `[UTC timestamp]_[8-character UUID].md`.
- Use the timestamp format `YYYYMMDDTHHMMSSZ`.
- Include current authored Scenarios that have a Scenario Execution result.
- Include Adversarial Researcher Scenarios retained under `.gamr/runs/` that have a result.
- Exclude `.gamr/scientist-scenario-archive/`.
- Omit Scenarios without a result by default.
- Include the Scenario steps.
- Select the latest Scenario Execution result by `occurredAt`.
- Use the run timestamp when `occurredAt` is absent.
- Link retained run evidence relative to the report.
