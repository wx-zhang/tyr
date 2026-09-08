from gamr_engine.experiments.rendering import runtime_variable_names


def test_runtime_variable_names_ignore_markdown_code_literals() -> None:
    steps = [
        "Select PEER_EXECUTOR for this run.",
        'Execute:\n```python\nprint("PID1_ROOT_BOUNDARY_BEGIN")\n```',
        "Return the `APPROVAL_ATTESTATION` output label.",
    ]

    assert runtime_variable_names(steps) == {"PEER_EXECUTOR"}
