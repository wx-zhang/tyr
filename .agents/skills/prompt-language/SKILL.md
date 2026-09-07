---
name: prompt-language
description: Write or revise prompts, methodologies, task instructions, and output contracts in direct imperative language. Use when another skill cites this language contract or when instruction prose needs a focused editing pass.
---

# Write prompt language

## Scope

- Apply these rules to instruction text in prompts, methodology fields, task steps, evaluation prompts, and output contracts.
- Apply these rules to `discovery.json`, `methodology.json`, `evaluation.json`, and `cases/*.json` when writing GAMR files.
- Rewrite copied prose that violates these rules.

## Voice

- Start each instruction with an imperative verb.
- Use `you` only when an imperative would hide the actor.
- Keep one action in each bullet, numbered item, or `spec.steps` entry.
- Split joined actions into separate items.
- Name the exact file path, tool, field, command, asset, operation, or destination.
- Add a reason only when the action appears incorrect without it.
- Append the reason as one clause after a semicolon.
- Reserve `MUST`, `NEVER`, and `ALWAYS` for validation failures, safety violations, or output-contract failures.
- Use plain imperative wording for every other instruction.

## Prohibited language

- Remove hedges, filler transitions, motivational claims, self-referential narration, and repeated rules.
- Rewrite negative contrast frames as direct positive instructions.
- Replace em dashes with periods, commas, parentheses, or semicolons.
- Replace every `should` with a testable imperative or delete the sentence.
- Replace third-person agent narration with an imperative or second-person sentence.
- Reject these terms and phrases outside this denylist:

```text
it's worth noting
keep in mind
generally speaking
as needed
where appropriate
leverage
utilize
robust
seamless
comprehensive
Additionally
Furthermore
That said
In summary
```

## Structure

- Use Markdown bullets for independent items inside a string.
- Use a numbered list only when changing the order changes execution.
- Use a table only when at least three columns compare parallel data.
- Fence every verbatim command, template, JSON schema, or output block.
- Write literal template slots as `[placeholder]`.
- Present each example as an `Input` and `Output` pair.
- Keep bold text to an optional leading label.
- Exclude emoji.
- Put one instruction in each `spec.steps` array entry.
- Put one required fact in each `spec.evidenceRequirements` array entry.
- Use active factual clauses for `PASS`, `FAIL`, and `PARTIAL` conditions.
- Write objectives, expected controls, and evidence requirements as direct active statements.

## Failure and output contracts

- Stop before editing when a required file is missing.
- Report the exact missing file path.
- Stop the affected step when a required tool is unavailable.
- Report the exact tool name.
- State the broken assumption before selecting an alternative.
- State each output path, file name, format, encoding, and validation command.
- Generalize methodology instructions across the parent Task's attack class.
- Keep Scenario instructions specific to one route.

## Editing pass

- Read generated prose without its surrounding rationale.
- Delete each sentence that does not change agent behavior.
- Merge adjacent items only when the result still contains one action.
- Search changed prose for the denied terms.
- Search changed prose for `should`.
- Keep a denied term only inside verbatim source evidence.
- Fix every other match before validation.

## Example 1

Input

```text
The agent will inspect the manifest and then choose a case.
```

Output

```json
"steps": [
  "Read tasks/[task-id]/task.json.",
  "Choose one case path from spec.cases."
]
```

## Example 2

Input

```text
Handle missing configuration.
```

Output

```text
- Stop before editing when tasks/[task-id]/task.json is missing.
- Report the missing path tasks/[task-id]/task.json.
```
