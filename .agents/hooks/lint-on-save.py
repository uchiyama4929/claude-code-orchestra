#!/usr/bin/env python3
"""
Post-tool hook: Check formatting, lint, and types after Python Edit/Write.

Triggered after Claude Edit/Write or Codex apply_patch modifies files.
Reports issues without rewriting the edited file.
"""

import json
import os
import re
import subprocess
import sys

# Input validation constants
MAX_PATH_LENGTH = 4096


def validate_path(file_path: str) -> bool:
    """Validate file path for security."""
    if not file_path or len(file_path) > MAX_PATH_LENGTH:
        return False
    # Check for path traversal
    if ".." in file_path:
        return False
    return True


def get_hook_input() -> dict:
    """Read one native hook payload."""
    try:
        data = json.load(sys.stdin)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def get_file_paths(data: dict) -> list[str]:
    """Return changed Python paths from Claude or Codex tool input."""
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path")
    if isinstance(file_path, str):
        return [file_path] if is_python_file(file_path) else []

    if data.get("tool_name") != "apply_patch":
        return []
    patch = tool_input.get("patch", "")
    if not isinstance(patch, str):
        return []
    paths = re.findall(r"^\*\*\* (?:Add|Update) File: (.+)$", patch, re.MULTILINE)
    return list(dict.fromkeys(path for path in paths if is_python_file(path)))


def is_python_file(path: str) -> bool:
    """Check if the file is a Python file."""
    return path.endswith(".py")


def run_command(cmd: list[str], cwd: str) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except FileNotFoundError:
        return 1, "", f"Command not found: {cmd[0]}"


def main() -> None:
    data = get_hook_input()
    file_paths = get_file_paths(data)
    if not file_paths:
        return

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    for file_path in file_paths:
        if not validate_path(file_path):
            continue
        rel_path = (
            os.path.relpath(file_path, project_dir)
            if file_path.startswith(project_dir)
            else file_path
        )
        issues: list[str] = []

        # Preserve the user's diff; formatting is an explicit command.
        ret, stdout, stderr = run_command(
            ["uv", "run", "--no-sync", "ruff", "format", "--check", file_path],
            cwd=project_dir,
        )
        if ret != 0:
            issues.append(f"ruff format check failed:\n{stderr or stdout}")

        ret, stdout, stderr = run_command(
            ["uv", "run", "--no-sync", "ruff", "check", file_path],
            cwd=project_dir,
        )
        if ret != 0:
            output = stdout or stderr
            if output.strip():
                issues.append(f"ruff check issues:\n{output}")

        ret, stdout, stderr = run_command(
            ["uv", "run", "--no-sync", "ty", "check", file_path],
            cwd=project_dir,
        )
        if ret != 0:
            output = stdout or stderr
            if output.strip():
                issues.append(f"ty check issues:\n{output}")

        if issues:
            print(f"[lint-on-save] Issues found in {rel_path}:", file=sys.stderr)
            for issue in issues:
                print(issue, file=sys.stderr)
            print("\nPlease review and fix these issues.", file=sys.stderr)
        else:
            print(f"[lint-on-save] OK: {rel_path} passed all checks")


if __name__ == "__main__":
    main()
