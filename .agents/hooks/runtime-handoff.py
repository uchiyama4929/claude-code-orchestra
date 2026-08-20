#!/usr/bin/env python3
"""Persist the latest completed runtime output for cross-runtime handoff."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

MAX_MESSAGE_CHARS = 100_000
SAFE_PART = re.compile(r"[^A-Za-z0-9_-]+")


def _runtime(data: dict[str, object]) -> str:
    configured = os.environ.get("ORCHESTRA_RUNTIME", "").lower()
    if configured in {"claude", "codex"}:
        return configured.capitalize()
    model = str(data.get("model", "")).lower()
    if model.startswith("gpt-") or "codex" in model:
        return "Codex"
    return "Claude Code"


def _safe_part(value: object, fallback: str) -> str:
    cleaned = SAFE_PART.sub("-", str(value)).strip("-")[:80]
    return cleaned or fallback


def _project_root(data: dict[str, object]) -> Path | None:
    cwd = Path(str(data.get("cwd") or os.getcwd())).resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".agents").is_dir():
            return candidate
    return None


def _write_handoff(data: dict[str, object]) -> None:
    root = _project_root(data)
    if root is None:
        return

    event = _safe_part(data.get("hook_event_name"), "event")
    session = _safe_part(data.get("session_id"), "session")
    identity = _safe_part(
        data.get("agent_id") or data.get("turn_id"),
        "turn",
    )
    handoff_dir = root / ".agents" / "logs" / "handoffs"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    destination = handoff_dir / f"{session}-{event}-{identity}.md"

    message = str(data.get("last_assistant_message") or "")[:MAX_MESSAGE_CHARS]
    content = (
        "# Runtime Handoff\n\n"
        f"- Runtime: {_runtime(data)}\n"
        f"- Event: {data.get('hook_event_name', '')}\n"
        f"- Session: {data.get('session_id', '')}\n"
        f"- Turn: {data.get('turn_id', '')}\n"
        f"- Agent: {data.get('agent_id', '')}\n"
        f"- Agent type: {data.get('agent_type', '')}\n"
        f"- Model: {data.get('model', '')}\n\n"
        "## Latest completed output\n\n"
        f"{message or '(No assistant output was provided by this hook event.)'}\n"
    )

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=handoff_dir,
        prefix=".handoff-",
        delete=False,
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, destination)


def main() -> int:
    try:
        data = json.load(sys.stdin)
        if isinstance(data, dict):
            _write_handoff(data)
    except (OSError, ValueError, TypeError) as exc:
        print(f"runtime handoff skipped: {exc}", file=sys.stderr)
    print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
