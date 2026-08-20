from __future__ import annotations

import json
import os
import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED_AGENTS = REPO_ROOT / ".agents" / "agents"
CODEX_ADAPTERS = REPO_ROOT / ".agents" / "adapters" / "codex" / "agents"
CODEX_NATIVE_AGENTS = REPO_ROOT / ".codex" / "agents"
MANUAL_SKILLS = {
    "orchestra-init",
    "plan",
    "research-lib",
    "simplify",
    "tdd",
    "update-lib-docs",
}


def test_codex_agent_adapters_resolve_to_shared_role_definitions() -> None:
    expected = {
        "codex-debugger": "gpt-5.6-terra",
        "fable-advisor": "gpt-5.6-sol",
        "general-purpose-opus": "gpt-5.6-sol",
        "general-purpose-sonnet": "gpt-5.6-luna",
    }

    assert {path.stem for path in CODEX_ADAPTERS.glob("*.toml")} == set(expected)
    for name, model in expected.items():
        adapter = CODEX_ADAPTERS / f"{name}.toml"
        config = tomllib.loads(adapter.read_text(encoding="utf-8"))
        assert config["name"] == name
        assert config["model"] == model
        assert f".agents/agents/{name}.md" in config["developer_instructions"]

        native = CODEX_NATIVE_AGENTS / adapter.name
        assert native.is_symlink()
        assert native.resolve() == adapter.resolve()
        assert (SHARED_AGENTS / f"{name}.md").is_file()

    project_config = tomllib.loads(
        (REPO_ROOT / ".codex/config.toml").read_text(encoding="utf-8")
    )
    assert project_config["features"]["hooks"] is True
    assert project_config["agents"]["max_concurrent_threads_per_session"] >= 4


def test_codex_hooks_use_shared_scripts_and_native_lifecycle_events() -> None:
    config = json.loads(
        (REPO_ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8")
    )
    hooks = config["hooks"]

    assert {
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "PreCompact",
        "SubagentStop",
        "Stop",
    } <= hooks.keys()
    assert "TeammateIdle" not in hooks
    assert "TaskCompleted" not in hooks

    commands = [
        handler["command"]
        for groups in hooks.values()
        for group in groups
        for handler in group["hooks"]
    ]
    assert commands
    assert all(".agents/hooks/" in command for command in commands)
    assert all(".codex/hooks/" not in command for command in commands)


def test_every_shared_skill_has_codex_interface_metadata() -> None:
    skill_files = sorted((REPO_ROOT / ".agents" / "skills").glob("*/SKILL.md"))
    assert skill_files

    for skill_file in skill_files:
        skill_name = skill_file.parent.name
        metadata = skill_file.parent / "agents" / "openai.yaml"
        content = metadata.read_text(encoding="utf-8")
        assert "display_name:" in content
        assert "short_description:" in content
        assert f"${skill_name}" in content
        assert "disable-model-invocation" not in skill_file.read_text(encoding="utf-8")
        if skill_name in MANUAL_SKILLS:
            assert "allow_implicit_invocation: false" in content


def test_manual_skill_policy_is_adapted_without_copying_the_skill_body() -> None:
    for skill_name in MANUAL_SKILLS:
        shared = REPO_ROOT / ".agents" / "skills" / skill_name / "SKILL.md"
        adapter = (
            REPO_ROOT
            / ".agents"
            / "adapters"
            / "claude"
            / "skills"
            / skill_name
            / "SKILL.md"
        )
        native = REPO_ROOT / ".claude" / "skills" / skill_name

        adapter_content = adapter.read_text(encoding="utf-8")
        assert "disable-model-invocation: true" in adapter_content
        assert f".agents/skills/{skill_name}/SKILL.md" in adapter_content
        assert native.is_symlink()
        assert native.resolve() == adapter.parent.resolve()
        assert shared.is_file()


def test_launcher_selects_runtime_without_switching_git_branches(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture = tmp_path / "capture.txt"
    for runtime in ("claude", "codex"):
        executable = fake_bin / runtime
        executable.write_text(
            "#!/usr/bin/env bash\n"
            f'printf "%s\\n" "$ORCHESTRA_RUNTIME|$*" > "{capture}"\n',
            encoding="utf-8",
        )
        executable.chmod(0o755)

        result = subprocess.run(
            [str(REPO_ROOT / "scripts" / "orchestra"), runtime, "--example"],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"},
        )

        assert result.returncode == 0, result.stderr
        assert capture.read_text(encoding="utf-8") == f"{runtime}|--example\n"


def test_runtime_handoff_persists_completed_output_for_the_other_runtime(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / ".agents" / "logs").mkdir(parents=True)
    hook = REPO_ROOT / ".agents" / "hooks" / "runtime-handoff.py"
    payload = {
        "hook_event_name": "SubagentStop",
        "cwd": str(project),
        "session_id": "session-123",
        "turn_id": "turn-456",
        "agent_id": "agent-789",
        "agent_type": "general-purpose-sonnet",
        "model": "gpt-5.6-luna",
        "last_assistant_message": "Implemented the scoped change and ran tests.",
    }

    result = subprocess.run(
        ["python3", str(hook)],
        input=json.dumps(payload),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"continue": True}
    handoffs = list((project / ".agents" / "logs" / "handoffs").glob("*.md"))
    assert len(handoffs) == 1
    content = handoffs[0].read_text(encoding="utf-8")
    assert "Codex" in content
    assert "general-purpose-sonnet" in content
    assert "Implemented the scoped change" in content


def test_runtime_contract_defines_native_delegation_without_recursive_cli_calls() -> (
    None
):
    content = (REPO_ROOT / ".agents" / "rules" / "runtime-compatibility.md").read_text(
        encoding="utf-8"
    )

    assert ".claude/agents/*.md" in content
    assert ".codex/agents/*.toml" in content
    assert "current runtime" in content.lower()
    assert "must not invoke itself" in content.lower()


def test_router_uses_native_codex_delegation_inside_codex() -> None:
    hook = REPO_ROOT / ".agents" / "hooks" / "agent-router.py"
    result = subprocess.run(
        ["python3", str(hook)],
        input=json.dumps(
            {
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-5.6-sol",
                "prompt": "この機能の設計を考えてください",
            }
        ),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "native Codex subagent" in context
    assert "codex_consult.py" not in context


def test_pre_write_hook_does_not_recurse_into_codex_cli() -> None:
    hook = REPO_ROOT / ".agents" / "hooks" / "check-codex-before-write.py"
    result = subprocess.run(
        ["python3", str(hook)],
        input=json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "model": "gpt-5.6-sol",
                "tool_input": {
                    "file_path": "src/architecture.py",
                    "content": "class Architecture:\n    pass\n",
                },
            }
        ),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "native Codex subagent" in context
    assert "codex_consult.py" not in context
