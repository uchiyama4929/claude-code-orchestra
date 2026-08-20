#!/usr/bin/env python3
"""Load the shared durable context when a Codex session starts or resumes."""

from __future__ import annotations

import json

CONTEXT = """Orchestra uses one shared source of truth for Claude Code and Codex.
Read AGENTS.md, .agents/STATE.md, .agents/docs/DESIGN.md, and the relevant files
under .agents/rules/ before acting. Use .codex/agents/*.toml for native Codex
subagents. Do not invoke Codex CLI recursively from a Codex session. Completed
runtime outputs are available under .agents/logs/handoffs/."""


def main() -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": CONTEXT,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
