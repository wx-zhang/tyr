from __future__ import annotations

import re

from gamr_core import (
    DiscoveryCandidate,
    ExperimentPresetConfig,
    Scenario,
    TargetOrigin,
    render_template,
)

from .decisions import CASE_DECISION_PROMPT
from .records import LoadedTask, RenderedScenario

_RUNTIME_VAR = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_MARKDOWN_CODE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)


def select_scenarios(task: LoadedTask, config: ExperimentPresetConfig) -> list[Scenario]:
    if config.case_ids is None:
        selected_ids = task.manifest.spec.defaults.default_case_ids
        if not selected_ids:
            return list(task.scenarios)
    else:
        selected_ids = config.case_ids
    known = {scenario.metadata.id for scenario in task.scenarios}
    missing = set(selected_ids) - known
    if missing:
        raise ValueError(f"unknown case IDs: {sorted(missing)}")
    return [scenario for scenario in task.scenarios if scenario.metadata.id in selected_ids]


def methodology_prefix(task: LoadedTask) -> str:
    if task.methodology is None:
        return ""
    return (
        f"System brief:\n{task.methodology.system_brief}\n"
        f"Unsticking guidance:\n{task.methodology.unsticking_guidance}\n"
        f"Testing methodology:\n{task.methodology.testing_methodology}\n"
    )


def variables(task: LoadedTask, candidate: DiscoveryCandidate) -> dict[str, str]:
    values: dict[str, str] = {}
    for name, variable in task.manifest.spec.variables.items():
        if variable.source == "literal" and variable.value is not None:
            values[name] = variable.value
        elif variable.source == "run" and variable.default is not None:
            values[name] = variable.default
        elif variable.source == "discovery" and variable.field:
            value = getattr(candidate, variable.field, None)
            if isinstance(value, str):
                values[name] = value
    return values


def known_facts_block(
    task: LoadedTask,
    values: dict[str, str],
    target_origin: TargetOrigin = TargetOrigin.LIVE,
) -> str:
    discovered = {
        name: values[name]
        for name, variable in task.manifest.spec.variables.items()
        if variable.source == "discovery" and name in values
    }
    if not discovered:
        return ""
    facts = "\n".join(f"- {name}: {value}" for name, value in sorted(discovered.items()))
    if target_origin is TargetOrigin.PROVIDED:
        return (
            "Operator-provided target facts for this run:\n"
            "- Use the supplied target facts directly.\n"
            "- Attribute these facts to the operator.\n"
            f"{facts}\n"
        )
    return (
        "Known confirmed facts for this run:\n"
        "- Use the target facts already established by discovery directly.\n"
        "- Repeat discovery or confirmation only when the agent holding the file "
        f"becomes unreachable.\n{facts}\n"
    )


def render_scenario(scenario: Scenario, values: dict[str, str]) -> RenderedScenario:
    return RenderedScenario(
        title=render_template(scenario.metadata.title, values),
        objective=render_template(scenario.spec.objective, values),
        steps=[render_template(step, values) for step in scenario.spec.steps],
        success=render_template(scenario.spec.success_criteria or "", values),
        expected_control=render_template(scenario.spec.expected_control, values),
    )


def case_prompt(
    task: LoadedTask,
    rendered: RenderedScenario,
    values: dict[str, str],
    target_origin: TargetOrigin,
) -> str:
    prompt = methodology_prefix(task)
    prompt += known_facts_block(task, values, target_origin)
    return (
        prompt
        + f"\n- Execute this Scenario to a concrete outcome.\nTitle: {rendered.title}\n"
        f"Objective: {rendered.objective}\nSteps:\n"
        + "\n".join(f"{index}. {step}" for index, step in enumerate(rendered.steps, 1))
        + f"\nSuccess criteria: {rendered.success}\n"
        + CASE_DECISION_PROMPT
    )


def runtime_variable_names(steps: list[str]) -> set[str]:
    prose = _MARKDOWN_CODE.sub("", " ".join(steps))
    return {match.group(0) for match in _RUNTIME_VAR.finditer(prose)}
