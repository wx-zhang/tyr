#!/usr/bin/env python3
"""
Local browser editor for the QATestSearch test-case JSON file
(test_cases/qatestsearch.json).

Stdlib only, no extra dependencies. Binds to localhost only -- this is a
dev tool for editing test cases on your own machine, not a service to
expose beyond it.

Usage:
  uv run python -m tyr_agent_tester.editor_server  # serves http://127.0.0.1:8765
  uv run python -m tyr_agent_tester.editor_server 9000  # custom port

Then open the printed URL, edit case/step text inline, and click Save.
Saves write straight back to test_cases/qatestsearch.json --
The prompts module picks up the change the next time it's imported
(i.e. the next ``uv run agent`` run).
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .test_case_store import PROJECT_ROOT, load_raw, save_raw

INDEX_FILE = PROJECT_ROOT / "editor.html"


def _validate_cases(cases: object) -> str | None:
    """Return an error string, or None if `cases` is a well-formed case list."""
    if not isinstance(cases, list):
        return "Top-level value must be a JSON array."
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            return f"Case {i} is not an object."
        if not case.get("id") or not isinstance(case["id"], str):
            return f"Case {i} is missing a non-empty string \"id\"."
        if not case.get("title") or not isinstance(case["title"], str):
            return f"Case {i} ({case.get('id')}) is missing a non-empty string \"title\"."
        if "steps" in case and not (
            isinstance(case["steps"], list) and all(isinstance(s, str) for s in case["steps"])
        ):
            return f"Case {i} ({case.get('id')}) \"steps\" must be an array of strings."
        if "instruction" in case and not isinstance(case["instruction"], str):
            return f"Case {i} ({case.get('id')}) \"instruction\" must be a string."
    ids = [c["id"] for c in cases]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        return f"Duplicate case id(s): {', '.join(sorted(dupes))}"
    return None


class EditorHandler(BaseHTTPRequestHandler):
    server_version = "TyrTestCaseEditor/1.0"

    def log_message(self, fmt: str, *args) -> None:  # quieter default logging
        sys.stderr.write(f"[editor_server] {self.address_string()} - {fmt % args}\n")

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            body = INDEX_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/cases":
            self._send_json(200, {"cases": load_raw()})
            return

        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/cases":
            self.send_error(404, "Not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b""
        try:
            cases = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            self._send_json(400, {"error": f"Invalid JSON body: {e}"})
            return

        error = _validate_cases(cases)
        if error:
            self._send_json(400, {"error": error})
            return

        save_raw(cases)
        self._send_json(200, {"saved": len(cases)})


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), EditorHandler)
    print(f"Test-case editor running at http://127.0.0.1:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
