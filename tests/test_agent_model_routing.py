from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / ".agents/agents"
ROUTING_FILES = (
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "README.md",
    *sorted((REPO_ROOT / ".agents").rglob("*.md")),
    *sorted((REPO_ROOT / ".agents/hooks").glob("*.py")),
)
BARE_GENERAL_PURPOSE = re.compile(
    r"(?<![A-Za-z0-9-])general-purpose(?!-(?:opus|sonnet)|[A-Za-z0-9-])"
)


def read_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"

    frontmatter: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return frontmatter
        key, separator, value = line.partition(":")
        if separator:
            frontmatter[key.strip()] = value.strip().strip('"')

    raise AssertionError(f"Unclosed frontmatter: {path}")


def test_model_specific_general_purpose_agents_are_defined() -> None:
    expected_models = {
        "general-purpose-opus.md": ("general-purpose-opus", "opus[1m]"),
        "general-purpose-sonnet.md": ("general-purpose-sonnet", "sonnet"),
        "fable-advisor.md": ("fable-advisor", "claude-fable-5[1m]"),
    }

    for filename, (expected_name, expected_model) in expected_models.items():
        frontmatter = read_frontmatter(AGENTS_DIR / filename)
        assert frontmatter["name"] == expected_name
        assert frontmatter["model"] == expected_model

    assert not (AGENTS_DIR / "general-purpose.md").exists()


def test_main_and_delegated_models_are_configured_independently() -> None:
    settings = json.loads(
        (REPO_ROOT / ".claude/settings.json").read_text(encoding="utf-8")
    )

    assert settings["model"] == "opus[1m]"
    assert settings["effortLevel"] == "xhigh"
    assert settings["teammateDefaultModel"] == "sonnet"
    assert "CLAUDE_CODE_SUBAGENT_MODEL" not in settings["env"]


def test_routing_docs_do_not_reference_removed_general_purpose_agent() -> None:
    stale_references = []
    for path in ROUTING_FILES:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if BARE_GENERAL_PURPOSE.search(line):
                stale_references.append(f"{path.relative_to(REPO_ROOT)}:{line_number}")

    assert stale_references == []


def test_team_execution_defaults_to_sonnet_with_opus_escalation() -> None:
    team_execute = (REPO_ROOT / ".agents/skills/team-execute/SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "general-purpose-sonnet" in team_execute
    assert "general-purpose-opus" in team_execute
