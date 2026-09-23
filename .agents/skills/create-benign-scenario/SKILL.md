---
name: create-benign-scenario
description: Turn a natural-language functional Tyr scenario into a reviewable benign test plan. Use for benign workflow tests, not GAMR attacks.
---

# Create a benign scenario

Read `docs/benign-scenarios.md` for configuration and the scenario contract.
Use `uv run scenario-test draft "[scenario]" --workspace [alias] --timezone [IANA-zone]`.
Read the saved `scenario.json` and its `questions`.
Separate the stimulus from expected behavior and read-only checks.
Preserve an explicitly supplied stimulus verbatim.
Keep save-calendar reminders and test expectations out of the stimulus unless explicitly requested.
Include every affected workspace in `participants`.
Resolve missing choices before execution.
Show the exact stimulus, checks, absolute date, timezone and pending conditions.
Validate with `uv run scenario-test validate [scenario.json]`.
Stop after authoring unless the user also requested execution.
