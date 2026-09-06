from __future__ import annotations


def strip_code_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return text


def completion_diagnostics(completion: dict[str, object]) -> str:
    return ", ".join(
        f"{key}={value}"
        for key, value in (
            ("finishReason", completion.get("finishReason")),
            ("refusal", completion.get("refusal")),
        )
        if value
    )


def render_transcript(transcript: list[dict[str, str]]) -> str:
    return "\n".join(f"[{item['role']}] {item['content']}" for item in transcript)
