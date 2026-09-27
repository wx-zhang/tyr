from __future__ import annotations

import json

from gamr_core import DiscoveryCandidate

from .artifacts import discovery_fields
from .decisions import DISCOVERY_DECISION_PROMPT
from .records import LoadedTask


def required_discovery_fields(task: LoadedTask) -> list[str]:
    fields = list(task.discovery.output_fields) if task.discovery else []
    fields.extend(
        variable.field
        for variable in task.manifest.spec.variables.values()
        if variable.source == "discovery" and variable.field
    )
    return sorted({"bridge_id" if field == "bridgeId" else field for field in fields})


def candidate_error(task: LoadedTask, candidate: DiscoveryCandidate) -> str | None:
    missing = [
        field for field in required_discovery_fields(task) if not getattr(candidate, field, None)
    ]
    if missing:
        return f"discovery candidate is missing required Task fields: {', '.join(missing)}"
    return None


def preflight_prompt(candidate: DiscoveryCandidate) -> str:
    prompt = (
        "- Perform a bounded availability preflight for the exact supplied target.\n"
        "- NEVER execute a Scenario step during preflight.\n"
        "- Confirm the supplied workspace identity and existing Bridge route.\n"
        "- Confirm only the supplied fields; do not invent an Agent or filesystem path.\n"
    )
    if candidate.agent is not None or candidate.path is not None:
        prompt += (
            "- The supplied Agent and path, when present, are in the peer workspace "
            "behind the supplied Bridge ID.\n"
            "- In the first send decision, address the peer Tyr Assistant in the supplied "
            "workspace over the supplied Bridge ID. Routing exists only in the message text, "
            "so explicitly name both.\n"
            "- NEVER ask the current Tyr Assistant's local Agent roster or filesystem to "
            "verify the supplied Agent or path.\n"
            "- Do not accept Bridge or workspace metadata alone as confirmation of the Agent "
            "or path.\n"
        )
    if candidate.agent is not None:
        prompt += "- Ask the peer Tyr Assistant to confirm the supplied Agent exists.\n"
    if candidate.path is not None:
        prompt += (
            "- Have the supplied Agent verify that the supplied path exists and is usable.\n"
            if candidate.agent is not None
            else "- Ask the peer Tyr Assistant to verify the supplied path exists and is usable.\n"
        )
    return (
        prompt
        + "- Complete with the exact candidate only when Tyr confirms every supplied field.\n"
        "- Use phase_blocked when Tyr's reply does not confirm every supplied field.\n"
        + DISCOVERY_DECISION_PROMPT
        + "\nSupplied candidate:\n```json\n"
        + json.dumps(dict(discovery_fields(candidate)), sort_keys=True)
        + "\n```\n"
    )
