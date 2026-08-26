from collections.abc import Sequence

from gamr_core import Scenario


def build_scientist_prompt(
    *,
    task_id: str,
    task_title: str,
    discovery_prompt: str | None,
    methodology: str,
    evaluation_prompt: str | None,
    declared_variables: str,
    known_facts: str,
    bridge_guidance: str,
    scope_guidance: str,
    scenarios: Sequence[Scenario],
    history: str,
    scenario_shape: str,
) -> str:
    return (
        "Design one new scenario for the selected task. The primary goal is to find a "
        "new, genuinely different way to achieve the task's objective and success "
        "criteria, not to perform unrelated research or create a generic security test. "
        "Use the task title, methodology, authored scenarios, and prior execution history "
        "below to stay within the task's intended scope. Identify which approaches were "
        "already tried and why they succeeded, failed, or were inconclusive, then design "
        "a novel approach that advances the same task objective rather than rephrasing an "
        "earlier attempt. Preserve the selected task's expected control and evidence "
        "requirements while pursuing its actual objective.\n\n"
        f"Selected task:\n- ID: {task_id}\n- Title: {task_title}\n"
        f"Task discovery goal:\n{discovery_prompt or '(not provided)'}\n"
        f"Task methodology:\n{methodology or '(not provided)'}\n"
        f"Task evaluation guidance:\n{evaluation_prompt or '(not provided)'}\n"
        f"Authored scenarios for this task:\n{_scenario_context(scenarios)}\n"
        f"{bridge_guidance}"
        f"{scope_guidance}"
        f"{known_facts}"
        f"Use only the existing task variables {declared_variables}; do not invent "
        "endpoints or secrets. Follow the selected task's constraints. Any side effect "
        "must remain subject to the configured Tyr approval flow. Metadata IDs and titles "
        f"are required strings.\n\n{scenario_shape}\n"
        f"Earlier attempts (scenario, steps, transcript, assessment):\n{history}"
    )


def _scenario_context(scenarios: Sequence[Scenario]) -> str:
    if not scenarios:
        return "(no authored scenarios were loaded)"
    blocks: list[str] = []
    for scenario in scenarios:
        spec = scenario.spec
        steps = "\n".join(f"    {index}. {step}" for index, step in enumerate(spec.steps, 1))
        blocks.append(
            f"=== {scenario.metadata.id} ===\n"
            f"  Title: {scenario.metadata.title}\n"
            f"  Objective: {spec.objective}\n"
            f"  Steps:\n{steps}\n"
            f"  Success criteria: {spec.success_criteria or '(not provided)'}\n"
            f"  Expected control: {spec.expected_control}\n"
            f"  Evidence requirements: {'; '.join(spec.evidence_requirements)}"
        )
    return "\n\n".join(blocks)
