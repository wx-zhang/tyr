# Dataset scope

## Purpose

Own versioned JSON dataset manifests, discovery prompts, and scenario cases.

## Standards

- Keep one `dataset.json` manifest per dataset and one JSON file per case.
- Use stable IDs, semantic versions, UTF-8, two-space indentation, and a final newline.
- Keep prompts and scenario text in JSON, not Python modules.
- Validate with `uv run gamr dataset validate <directory>` before committing.

## Safety

Datasets are authoring sources. Do not add secrets, production data, or instructions that enable unapproved real actions. Never mutate a versioned dataset from an evaluator or API read path.
