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

The same expansion/fill pass a case goes through here (prepare_case(), used
internally by load_enabled()) is reused directly by agent_loop.py's scientist
phase for the scenarios it invents at runtime, which never touch this file --
one pipeline for both a hand-written case and a self-generated one.

An optional "success" field states what PASS means for that one case, in
plain words. It is the case's own pass bar: the steps say what to do, and
"success" says which observed outcome counts as having done it. Cases
without one fall back to prompts.DEFAULT_SUCCESS.

Two mechanisms keep the cases from repeating each other:

  Shared fragments -- a step of the exact form "@name" expands in place to
  the list of steps stored under that name in test_cases/shared.json. The
  channel preamble and the whole upload sequence live there, so they are
  written once instead of copy-pasted into every case and left to drift.
  Shared pass-bar wording lives in the same file under "text" and is
  referenced as an ordinary {placeholder} (e.g. {grading_note}).

  Placeholders -- "instruction"/"steps"/"title"/"success" text may contain
  {token}s filled by safe_format(). They come from three places, in
  increasing order of lateness: the case's own extra string fields (e.g.
  {artifact}), the caller's arguments at import time (e.g. {store_url}),
  and the discovery result at execute time (e.g. {path}). The editor
  always reads/writes the raw, unfilled text via load_raw()/save_raw().
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_CASES_DIR = PROJECT_ROOT / "test_cases"
TEST_CASES_FILE = TEST_CASES_DIR / "qatestsearch.json"
SHARED_FILE = TEST_CASES_DIR / "shared.json"

# A step consisting of exactly "@name" is a reference to a shared fragment.
FRAGMENT_PREFIX = "@"

# Case keys that are structure rather than substitutable values. Every OTHER
# string field on a case becomes a {placeholder} usable in its own text --
# that is how {artifact} and {artifact_var} reach the shared fragments.
STRUCTURAL_FIELDS = frozenset({
    "id", "title", "category", "enabled", "steps", "instruction", "success",
})

# Fields filled by fill_case(). "title" is included because it is rendered
# into the QA report, so a raw token there leaks into the finished document.
FILLABLE_FIELDS = ("title", "instruction", "success")


def load_raw() -> list[dict]:
    """All cases as stored on disk, including disabled ones, unexpanded
    "@fragment" steps, and raw placeholder tokens."""
    return json.loads(TEST_CASES_FILE.read_text(encoding="utf-8"))


def save_raw(cases: list[dict]) -> None:
    TEST_CASES_FILE.write_text(
        json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def load_shared() -> dict:
    """The shared fragment file, as {"steps": {name: [step, ...]}, "text": {name: str}}.

    Missing or malformed sections degrade to empty rather than raising: an
    unresolved "@name" survives into the prompt verbatim, where it is obvious,
    which is the same failure mode _KeepUnknown gives an unknown placeholder."""
    if not SHARED_FILE.exists():
        return {"steps": {}, "text": {}}
    doc = json.loads(SHARED_FILE.read_text(encoding="utf-8"))
    steps = doc.get("steps") if isinstance(doc.get("steps"), dict) else {}
    text = doc.get("text") if isinstance(doc.get("text"), dict) else {}
    return {"steps": steps, "text": text}


def fragment_names() -> set[str]:
    """Names a case may reference as "@name". Used by the editor to reject a
    typo'd reference at save time rather than at the next run."""
    return set(load_shared()["steps"])


class _KeepUnknown(dict):
    """Leaves an unrecognised {token} in place instead of raising KeyError.

    Case text is edited freely in the browser, so a typo'd or simply unknown
    placeholder must not crash the whole run at import time -- it should show
    up verbatim in the prompt, where it is obvious. It is also what lets the
    import-time pass leave the execute-time tokens alone."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def safe_format(text: str, **values: str) -> str:
    """str.format that leaves unrecognised {tokens} untouched.

    Case text is filled in two passes: the static ones ({store_url},
    {fake_data_marker}, {artifact}) at import, and the ones only known after
    the discovery phase ({path}, {workspace}, {agent}) at execute time. Each
    pass must leave the other pass's tokens alone, which is exactly what this
    does."""
    return text.format_map(_KeepUnknown(values))


def fill_case(case: dict, **values: str) -> dict:
    """A copy of `case` with {placeholders} filled in every text-bearing field.

    One helper for both fill passes -- the import-time one in load_enabled()
    and the discovery-time one in prompts.fill_target() -- so a newly
    text-bearing field only has to be added to FILLABLE_FIELDS once."""
    case = dict(case)
    for field in FILLABLE_FIELDS:
        if isinstance(case.get(field), str):
            case[field] = safe_format(case[field], **values)
    if "steps" in case:
        case["steps"] = [safe_format(step, **values) for step in case["steps"]]
    return case


def expand_fragments(steps: list[str], fragments: dict) -> list[str]:
    """Replace every "@name" step with the fragment it names.

    An unknown name is left in place rather than dropped: a silently missing
    upload sequence would turn into a case that quietly tests less than it
    claims, whereas a literal "@upload_request" in the prompt is visible."""
    expanded = []
    for step in steps:
        name = step[len(FRAGMENT_PREFIX):].strip() if step.startswith(FRAGMENT_PREFIX) else None
        if name and name in fragments:
            expanded.extend(fragments[name])
        else:
            expanded.append(step)
    return expanded


def prepare_case(case: dict, shared: dict, **placeholders: str) -> dict:
    """One case, with @fragments expanded and {placeholder}s filled -- the
    per-case body of load_enabled(), pulled out so a case built at runtime
    (the scientist phase's self-generated scenarios) can go through the exact
    same expansion/fill pass as one loaded from disk, instead of a second,
    drifting copy of this logic.

    Values are layered: the case's own extra string fields first, then the
    caller's `placeholders`, then the shared "text" entries (themselves filled
    from those first two, so {grading_note} can talk about {artifact})."""
    case = dict(case)
    case.pop("enabled", None)

    if "steps" in case:
        case["steps"] = expand_fragments(case["steps"], shared["steps"])

    values = {
        k: v for k, v in case.items()
        if k not in STRUCTURAL_FIELDS and isinstance(v, str)
    }
    values.update(placeholders)
    values.update({
        name: safe_format(text, **values) for name, text in shared["text"].items()
    })

    return fill_case(case, **values)


def load_enabled(**placeholders: str) -> list[dict]:
    """Enabled cases only -- fragments expanded, placeholders filled, "enabled"
    stripped. This is what the prompt module actually runs against Tyr."""
    shared = load_shared()
    return [
        prepare_case(case, shared, **placeholders)
        for case in load_raw()
        if case.get("enabled", True)
    ]
