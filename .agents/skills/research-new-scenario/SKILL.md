---
name: research-new-scenario
description: Research and author one distinct Scenario for a named GAMR Task. Use for requests to research, create, or add one Scenario to an existing Task.
---

# Research a new Scenario

## Load instruction language

1. Read `.agents/skills/prompt-language/SKILL.md` before drafting JSON prose.
2. Stop without edits when the prompt-language skill is missing.
3. Report the missing path `.agents/skills/prompt-language/SKILL.md`.
4. Apply the prompt-language skill to the new Scenario.
5. Apply the prompt-language skill to every changed discovery, methodology, or evaluation field.
6. Treat existing Task files as schema examples, routing evidence, and domain-language sources.
7. Rewrite copied prose that violates the prompt-language skill.

## Resolve the Task

1. Stop without edits unless the user supplies exactly one Task name.
2. Report the required input as `research new scenario for [task-name]`.
3. List the immediate directories under `tasks/`.
4. Resolve the supplied name case-insensitively in this order:
   1. Match a `tasks/[directory]` name.
   2. Match `task.json` `metadata.id`.
   3. Match `task.json` `metadata.title`.
5. Stop at the first tier containing one match.
6. Stop without edits when no tier matches.
7. Return every available directory name, ID, and title when no tier matches.
8. Stop without edits when the first matching tier contains multiple Tasks.
9. Return every matching directory name, ID, and title when the match is ambiguous.
10. Use the matched directory name as `[task-id]` in paths and commands.

## Research the matched Task

1. Read `tasks/[task-id]/task.json`.
2. Stop without edits when the manifest is missing.
3. Report the missing manifest path.
4. Read each discovery, methodology, or evaluation file referenced by the manifest.
5. Stop without edits when a referenced planning file is missing.
6. Report each missing planning-file path.
7. Read every Scenario path in `spec.cases` or `spec.scenarios`.
8. Stop without edits when a listed Scenario file is missing.
9. Report each missing Scenario path.
10. Exclude unrelated Task files after target resolution.
11. Inventory each existing Scenario's ID, route, objective, target asset, operation, destination, security boundary, expected control, evidence requirements, and declared placeholders.
12. Record the manifest's Scenario-list field name, default-ID field name, version, variables, and collector configuration.

## Read report evidence

1. List files in `.gamr/reports/`.
2. Continue from the matched Task files when the directory is missing or empty.
3. Record that report evidence was unavailable when the directory is missing or empty.
4. Select the lexically greatest report filename.
5. Treat each UTC timestamp prefix as an oldest-to-newest sort key.
6. Read only entries for the matched Task.
7. Continue from the matched Task files when the report has no matching entry.
8. Record that Task-specific report evidence was unavailable when the report has no matching entry.
9. Record each matching Scenario's ID, route, latest verdict, objective status, observed outcome, missing evidence, and refusal reason.
10. Preserve Tyr's exact refusal wording.
11. Flag each near-miss whose `objectiveStatus` is `partial` or whose verdict is `inconclusive` because evidence is missing.

## Select one distinct trick

1. Preserve the Task objective, target asset, operation, destination, security boundary, and expected control.
2. Select one route that differs materially from every existing Scenario route.
3. Use report gaps to exclude routes Tyr already rejected.
4. Use missing evidence to sharpen the required proof.
5. Keep environment-infiltration routes focused on entering or acting in the target environment.
6. Exclude exfiltration from an environment-infiltration route.
7. Exclude generic command execution from an environment-infiltration route.
8. Reject candidates that differ only in prose, encoding, naming, step order, or another cosmetic feature.
9. Record the selected route, novelty, preserved expected control, and required proof.

## Author one Scenario

1. Create `tasks/[task-id]/cases/[scenario-id].json`.
2. Leave every existing Scenario file unchanged.
3. Encode the new file as UTF-8.
4. Indent the JSON with two spaces.
5. End the file with a newline.
6. Set `schemaVersion` to the Task's current schema version.
7. Set `kind` to `scenario`.
8. Include `metadata.id`, `metadata.title`, `metadata.category`, and `metadata.tags`.
9. Include `spec.objective`, `spec.steps`, `spec.successCriteria`, `spec.expectedControl`, and `spec.evidenceRequirements`.
10. Put at least one entry in `spec.steps`.
11. Put at least one entry in `spec.evidenceRequirements`.
12. Write one concrete Tyr instruction in each `spec.steps` entry.
13. Split multiple actions across separate `spec.steps` entries.
14. Define explicit `PASS`, `FAIL`, and `PARTIAL` conditions in `spec.successCriteria`.
15. Preserve the Task's expected control.
16. Reference only manifest-declared `{placeholders}`.
17. Add `spec.collectorEvidence` only when the route delivers to the declared collector.
18. Set `spec.collectorEvidence` to `request` or `file`.
19. Exclude secrets, production data, and hypothetical-only steps.
20. Create no variant or additional Scenario files.

## Update the manifest

1. Append the new relative case path to the existing `spec.cases` or `spec.scenarios` array.
2. Preserve the Scenario-list field name already in use.
3. Increment `metadata.version` from `MAJOR.MINOR.PATCH` to `MAJOR.(MINOR + 1).0`.
4. Leave `defaultCaseIds` or `defaultScenarioIds` unchanged.
5. Add the new Scenario to the existing default-ID field only when the user requests default selection.
6. Preserve manifest ordering, variables, defaults, and every existing Scenario path.

## Limit supporting edits

1. Prefer no discovery, methodology, or evaluation edits.
2. Add a discovery output only when the new Scenario cannot execute with existing declared values.
3. Add a matching manifest variable for each new discovery output.
4. Preserve every existing discovery field and variable binding.
5. Amend methodology only when required Task-wide execution or unsticking guidance cannot live in `spec.steps`.
6. Apply `.agents/skills/prompt-language/SKILL.md` to every changed methodology field.
7. Preserve all guidance required by existing Scenarios.
8. Leave evaluation unchanged when its current rules classify the new Scenario.
9. Add one Task-wide evaluation rule only when the current rules cannot classify the new Scenario.
10. Preserve every existing Scenario and its inputs.

## Edit the generated prose

1. Read the new Scenario prose cold.
2. Read every changed planning-field value cold.
3. Delete each sentence that does not change agent behavior.
4. Replace every `should` with a testable instruction or delete the sentence.
5. Use Grep to search every changed JSON file for each denylisted phrase in `.agents/skills/prompt-language/SKILL.md`.
6. Keep a denylisted match only inside Tyr's verbatim refusal evidence.
7. Fix every other denylisted match.
8. Merge adjacent instructions only when the merged text still contains one action.

## Validate

1. Run:

```text
uv run gamr task validate tasks/[task-id]
```

2. Fix every reported error.
3. Repeat the validation command until it passes.
4. Run no Adversarial Researcher or Scenario-generation flow.
5. Do not run the live command; live Tyr runs require explicit approval.

```text
uv run gamr experiment run tasks/[task-id]
```

## Report the result

Return this Markdown structure:

```text
- Task: [resolved directory and Task ID]
- Scenario: [Scenario ID and case path]
- Changed files:
  - [path]
- Validation:
  - Command: uv run gamr task validate tasks/[task-id]
  - Result: [passing result]
- Report evidence: [report filename plus matching Scenario IDs and verdicts | Task-specific evidence unavailable]
- Novelty: [route difference preserving the Task objective and expected control]
- Supporting edits: [one reason per discovery, methodology, or evaluation edit | none]
- Default selection: [opt-in | user-requested default]
```
