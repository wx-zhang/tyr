# Task scope

## Purpose

Own versioned JSON task manifests, discovery prompts, and scenario cases.

## Standards

- Keep one `task.json` manifest per task and one JSON file per case.
- Use stable IDs, semantic versions, UTF-8, two-space indentation, and a final newline.
- Keep prompts and scenario text in JSON, not Python modules.
- Validate with `uv run gamr task validate <directory>` before committing.

## Safety

Tasks are authoring sources. Do not add secrets, production data, or instructions that enable unapproved real actions. Never mutate a versioned task from an evaluator or API read path.
