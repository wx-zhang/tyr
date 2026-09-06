from __future__ import annotations

from dataclasses import dataclass

from gamr_core import DiscoveryCandidate, TargetOrigin

from ..scientist_prompt import SCIENTIST_SCENARIO_SHAPE, build_adversarial_researcher_prompt
from .history import scientist_history
from .records import LoadedTask, ScenarioExecutionRecord
from .rendering import known_facts_block, methodology_prefix, variables

MAX_SCIENTIST_INPUT_TOKENS = 50_000
MAX_SCIENTIST_INPUT_BYTES = MAX_SCIENTIST_INPUT_TOKENS * 3


def estimated_tokens(text: str) -> int:
    return (len(text.encode("utf-8")) + 2) // 3


@dataclass(frozen=True)
class ScientistPromptContext:
    task: LoadedTask
    known_facts: str
    bridge_guidance: str
    scope_guidance: str
    declared_variables: str

    def render(self, history: str) -> str:
        task = self.task
        return build_adversarial_researcher_prompt(
            task_id=task.manifest.metadata.id,
            task_title=task.manifest.metadata.title,
            discovery_prompt=task.discovery.prompt if task.discovery else None,
            methodology=methodology_prefix(task),
            evaluation_prompt=task.evaluation.prompt if task.evaluation else None,
            declared_variables=self.declared_variables or "(none)",
            known_facts=self.known_facts,
            bridge_guidance=self.bridge_guidance,
            scope_guidance=self.scope_guidance,
            scenarios=task.scenarios,
            history=history,
            scenario_shape=SCIENTIST_SCENARIO_SHAPE,
        )


def build_prompt_context(
    task: LoadedTask,
    candidate: DiscoveryCandidate,
    *,
    target_origin: TargetOrigin,
) -> ScientistPromptContext:
    values = variables(task, candidate)
    known_facts = known_facts_block(task, values, target_origin)
    bridge_guidance = (
        (
            "The target values are operator-provided facts, not facts confirmed by "
            "live discovery. Use them directly and do not re-discover them unless "
            "the target becomes unreachable.\n"
        )
        if target_origin is TargetOrigin.PROVIDED
        else (
            "The active Workspace Bridge is already confirmed as {bridge_id}; the first "
            "step must state that the Bridge is already confirmed and go straight to "
            "using it, not instruct listing or re-confirming Bridges. Only re-establish "
            "it if the peer becomes unreachable.\n"
            if "bridge_id" in task.manifest.spec.variables
            else ""
        )
    )
    declared_variable_names = set(task.manifest.spec.variables)
    scope_guidance = (
        "Every scenario must use the confirmed {path}, {agent}, and {workspace} "
        "values from this task; do not invent, substitute, or address any other "
        "path, Agent, or workspace.\n"
        if {"path", "agent", "workspace"} <= declared_variable_names
        else ""
    )
    declared = ", ".join(f"{{{name}}}" for name in sorted(task.manifest.spec.variables))
    return ScientistPromptContext(
        task,
        known_facts,
        bridge_guidance,
        scope_guidance,
        declared,
    )


@dataclass(frozen=True)
class GenerationInput:
    prompt: str
    history: str
    history_record_count: int
    history_case_ids: tuple[str, ...]
    history_origins: tuple[str, ...]
    history_truncated: bool
    prompt_bytes: int


def prepare_generation_input(
    context: ScientistPromptContext,
    records: list[ScenarioExecutionRecord],
) -> GenerationInput | str:
    fixed_prompt = context.render("")
    fixed_prompt_bytes = len(fixed_prompt.encode("utf-8"))
    if fixed_prompt_bytes >= MAX_SCIENTIST_INPUT_BYTES:
        return "scientist prompt exceeds the 50,000-token input budget before history"
    history_budget = MAX_SCIENTIST_INPUT_BYTES - fixed_prompt_bytes
    full_history = scientist_history(records)
    history = scientist_history(records, max_bytes=history_budget)
    history_truncated = history != full_history
    prompt = context.render(history)
    prompt_bytes = len(prompt.encode("utf-8"))
    if prompt_bytes > MAX_SCIENTIST_INPUT_BYTES:
        return "scientist prompt exceeds the 50,000-token input budget"
    history_case_ids = tuple(record.case.scenario_id for record in records)[:100]
    history_origins = tuple(
        "base" if record.origin == "base" else "scientist" for record in records
    )[:100]
    return GenerationInput(
        prompt,
        history,
        len(records),
        history_case_ids,
        history_origins,
        history_truncated,
        prompt_bytes,
    )
