"""
Shared load/save for the browser-editable test-case JSON file
(test_cases/qatestsearch.json). Used by the prompt module
(prompts.py) at import time, and by editor_server.py for the
browser editor's read/write API.

Each case on disk is a dict with at least "id", "title", "category", and
either "instruction" (single-line) or "steps" (ordered list) -- the same
shape render_case() in the prompt module already expects. An
"enabled": false case is kept on disk (so it's still visible/editable in
the browser) but excluded from load_enabled().

An optional "success" field states what PASS means for that one case, in
plain words. It is the case's own pass bar: the steps say what to do, and
"success" says which observed outcome counts as having done it. Cases
without one fall back to prompts.DEFAULT_SUCCESS.

"instruction"/"steps" text may contain {placeholder} tokens (e.g.
{store_url}) that load_enabled() fills in via str.format() -- the editor
always reads/writes the raw, unfilled text via load_raw()/save_raw().
"""

from __future__ import annotations

import json
from pathlib import Path

TEST_CASES_DIR = Path(__file__).resolve().parent / "test_cases"
TEST_CASES_FILE = TEST_CASES_DIR / "qatestsearch.json"


def load_raw() -> list[dict]:
    """All cases as stored on disk, including disabled ones and the raw
    (unfilled) "enabled" flag and placeholder tokens."""
    return json.loads(TEST_CASES_FILE.read_text(encoding="utf-8"))


def save_raw(cases: list[dict]) -> None:
    TEST_CASES_FILE.write_text(
        json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


class _KeepUnknown(dict):
    """Leaves an unrecognised {token} in place instead of raising KeyError.

    Case text is edited freely in the browser, so a typo'd or simply unknown
    placeholder must not crash the whole run at import time -- it should show
    up verbatim in the prompt, where it is obvious."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def safe_format(text: str, **values: str) -> str:
    """str.format that leaves unrecognised {tokens} untouched.

    Case text is filled in two passes: the static ones ({store_url},
    {fake_data_marker}) at import, and the ones only known after the discovery
    phase ({path}, {workspace}, {agent}) at execute time. Each pass must leave
    the other pass's tokens alone, which is exactly what this does."""
    return text.format_map(_KeepUnknown(values))


def load_enabled(**placeholders: str) -> list[dict]:
    """Enabled cases only, with the "enabled" flag stripped and any
    {placeholder} tokens filled in -- what the prompt module actually runs
    against Tyr. "title" is filled too: it is rendered into the execute prompt
    and into the QA report, so a raw token there leaks into both."""
    cases = []
    for case in load_raw():
        if not case.get("enabled", True):
            continue
        case = dict(case)
        case.pop("enabled", None)
        if placeholders:
            for field in ("title", "instruction", "success"):
                if isinstance(case.get(field), str):
                    case[field] = safe_format(case[field], **placeholders)
            if "steps" in case:
                case["steps"] = [safe_format(step, **placeholders) for step in case["steps"]]
        cases.append(case)
    return cases
