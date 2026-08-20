from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install.sh"
UPDATE_SCRIPT = REPO_ROOT / "scripts" / "update.sh"
PERSONAL_FORK_URL = "https://github.com/uchiyama4929/claude-code-orchestra.git"


def init_git_repo(path: Path) -> None:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def run_install(
    target: Path,
    *options: str,
    script: Path = INSTALL_SCRIPT,
    extra_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if extra_path is not None:
        env["PATH"] = f"{extra_path}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        ["bash", str(script), "--yes", *options, str(target)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def build_template_repo(tmp_path: Path, name: str = "template") -> Path:
    """Copy this repository into a fresh git repo so scripts under test can
    be run against a template source distinct from the live checkout."""
    template = tmp_path / name
    shutil.copytree(
        REPO_ROOT,
        template,
        symlinks=True,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
        ),
    )
    subprocess.run(["git", "init", "-q", str(template)], check=True)
    subprocess.run(
        ["git", "-C", str(template), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(template), "config", "user.name", "Test User"],
        check=True,
    )
    subprocess.run(["git", "-C", str(template), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(template), "commit", "-qm", "template"], check=True
    )
    return template


def run_update(
    target: Path,
    template: Path,
    *options: str,
    extra_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "ORCHESTRA_TEMPLATE_REPO": str(template)}
    if extra_path is not None:
        env["PATH"] = f"{extra_path}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        ["bash", str(target / "scripts/update.sh"), "--yes", *options],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def find_debris(root: Path) -> list[Path]:
    """Locate any leftover stage-and-swap artifacts under root (excluding .git)."""
    debris: list[Path] = []
    for pattern in ("*.orchestra-staging.*", "*.orchestra-old.*"):
        for match in root.rglob(pattern):
            if ".git" in match.relative_to(root).parts:
                continue
            debris.append(match)
    return debris


def make_rejected_realpath_shim(tmp_path: Path) -> Path:
    shim_dir = tmp_path / "fake-bin"
    shim_dir.mkdir(parents=True)
    shim = shim_dir / "realpath"
    shim.write_text(
        '#!/usr/bin/env bash\necho "realpath must not be required" >&2\nexit 64\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return shim_dir


def test_default_update_source_is_personal_fork() -> None:
    assert PERSONAL_FORK_URL in UPDATE_SCRIPT.read_text(encoding="utf-8")


def test_install_does_not_require_gnu_realpath(tmp_path: Path) -> None:
    target = tmp_path / "project"
    init_git_repo(target)

    result = run_install(target, extra_path=make_rejected_realpath_shim(tmp_path))

    assert result.returncode == 0, result.stderr


def test_update_does_not_require_gnu_realpath(tmp_path: Path) -> None:
    template = build_template_repo(tmp_path)
    target = tmp_path / "project"
    init_git_repo(target)
    install_result = run_install(target, script=template / "scripts/install.sh")
    assert install_result.returncode == 0, install_result.stderr

    result = run_update(
        target,
        template,
        extra_path=make_rejected_realpath_shim(tmp_path / "update"),
    )

    assert result.returncode == 0, result.stderr


def test_install_adds_complete_template_without_overwriting_project_version(
    tmp_path: Path,
) -> None:
    target = tmp_path / "project"
    init_git_repo(target)
    (target / "README.md").write_text("# Existing project\n", encoding="utf-8")
    (target / "VERSION").write_text("9.4.1\n", encoding="utf-8")

    result = run_install(target)

    assert result.returncode == 0, result.stderr
    assert (target / "README.md").read_text(encoding="utf-8") == "# Existing project\n"
    assert (target / "VERSION").read_text(encoding="utf-8") == "9.4.1\n"
    assert (target / ".claude/orchestra-version").read_text(encoding="utf-8") == (
        REPO_ROOT / "VERSION"
    ).read_text(encoding="utf-8")
    assert (target / ".agents/INDEX.md").is_file()
    assert (target / ".agents/change_main.md").is_file()
    assert "## Skill Catalog" in (target / "AGENTS.md").read_text(encoding="utf-8")
    assert not (target / ".agents/rules/orchestration.md").exists()
    assert (target / ".agents/rules").is_dir()
    assert (target / ".agents/skills").is_dir()
    assert (target / ".agents/agents").is_dir()
    assert (target / ".agents/hooks").is_dir()
    assert (target / "AGENTS.md").is_file()
    assert (target / "CLAUDE.md").is_symlink()
    assert (target / "CLAUDE.md").resolve() == (target / "AGENTS.md").resolve()
    assert {path.name for path in (target / ".claude").iterdir()} == {
        "orchestra-version",
        "settings.json",
        "agents",
        "skills",
    }
    assert {path.name for path in (target / ".codex").iterdir()} == {"config.toml"}
    assert (target / "scripts/install.sh").is_file()
    assert (target / "scripts/update.sh").is_file()
    assert (target / ".claude/settings.json").is_file()
    assert (target / ".agents/docs/plans/.gitkeep").is_file()
    assert (target / ".agents/docs/research/.gitkeep").is_file()
    assert (target / ".agents/STATE.md").is_file()
    assert "@orchestra:" not in (target / "AGENTS.md").read_text(encoding="utf-8")
    gitignore = (target / ".gitignore").read_text(encoding="utf-8")
    assert ".agents/logs/" in gitignore
    assert ".agents/checkpoints/" in gitignore
    assert ".orchestra-backup-*/" in gitignore


def test_install_preserves_existing_claude_md_in_agents_state(tmp_path: Path) -> None:
    target = tmp_path / "project"
    init_git_repo(target)
    existing_content = "# Existing instructions\n\nKeep this project rule.\n"
    (target / "CLAUDE.md").write_text(existing_content, encoding="utf-8")

    result = run_install(target)

    assert result.returncode == 0, result.stderr
    assert (target / "CLAUDE.md").is_symlink()
    installed = (target / ".agents/STATE.md").read_text(encoding="utf-8")
    assert installed.count(existing_content.strip()) == 1
    assert existing_content.strip() not in (target / "AGENTS.md").read_text(
        encoding="utf-8"
    )


def test_install_refuses_template_owned_path_conflicts_by_default(
    tmp_path: Path,
) -> None:
    target = tmp_path / "project"
    init_git_repo(target)
    custom_file = target / ".agents/rules/custom.md"
    custom_file.parent.mkdir(parents=True)
    custom_file.write_text("custom contract\n", encoding="utf-8")

    result = run_install(target)

    assert result.returncode == 2
    assert "--force" in result.stderr
    assert custom_file.read_text(encoding="utf-8") == "custom contract\n"
    assert not (target / "AGENTS.md").exists()


def test_force_install_backs_up_conflicts_before_replacing_them(
    tmp_path: Path,
) -> None:
    target = tmp_path / "project"
    init_git_repo(target)
    custom_file = target / ".agents/rules/custom.md"
    custom_file.parent.mkdir(parents=True)
    custom_file.write_text("custom contract\n", encoding="utf-8")

    result = run_install(target, "--force")

    assert result.returncode == 0, result.stderr
    backups = list(target.glob(".orchestra-backup-*"))
    assert len(backups) == 1
    assert (backups[0] / ".agents/rules/custom.md").read_text(
        encoding="utf-8"
    ) == "custom contract\n"
    assert (target / ".agents/INDEX.md").is_file()
    assert not (target / ".agents/rules/custom.md").exists()


def test_install_preserves_existing_native_subagents_and_skills(
    tmp_path: Path,
) -> None:
    target = tmp_path / "project"
    init_git_repo(target)
    existing_agent = target / ".claude/agents/my-agent.md"
    existing_agent.parent.mkdir(parents=True)
    existing_agent.write_text("user's own subagent\n", encoding="utf-8")
    existing_skill = target / ".claude/skills/my-skill/SKILL.md"
    existing_skill.parent.mkdir(parents=True)
    existing_skill.write_text("user's own skill\n", encoding="utf-8")

    result = run_install(target)

    assert result.returncode == 0, result.stderr
    assert existing_agent.read_text(encoding="utf-8") == "user's own subagent\n"
    assert existing_skill.read_text(encoding="utf-8") == "user's own skill\n"
    assert (target / ".claude/agents/general-purpose-opus.md").is_symlink()
    assert (target / ".claude/skills/context-loader").is_symlink()


def test_force_install_keeps_existing_native_subagents_and_skills_active(
    tmp_path: Path,
) -> None:
    target = tmp_path / "project"
    init_git_repo(target)
    existing_agent = target / ".claude/agents/my-agent.md"
    existing_agent.parent.mkdir(parents=True)
    existing_agent.write_text("user's own subagent\n", encoding="utf-8")

    result = run_install(target, "--force")

    assert result.returncode == 0, result.stderr
    assert existing_agent.read_text(encoding="utf-8") == "user's own subagent\n"
    assert (target / ".claude/agents").is_dir()
    assert not (target / ".claude/agents").is_symlink()
    assert (target / ".claude/agents/general-purpose-opus.md").is_symlink()


def test_install_preserves_existing_native_project_rules(tmp_path: Path) -> None:
    target = tmp_path / "project"
    init_git_repo(target)
    existing_rule = target / ".claude/rules/billing.md"
    existing_rule.parent.mkdir(parents=True)
    existing_rule.write_text("project billing rule\n", encoding="utf-8")

    result = run_install(target)

    assert result.returncode == 0, result.stderr
    assert existing_rule.read_text(encoding="utf-8") == "project billing rule\n"
    check_result = subprocess.run(
        ["bash", str(target / ".agents/check.sh")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert check_result.returncode == 0, check_result.stdout


def test_update_preserves_existing_native_project_rules(tmp_path: Path) -> None:
    template = build_template_repo(tmp_path)
    target = tmp_path / "project"
    init_git_repo(target)
    install_result = run_install(target, script=template / "scripts/install.sh")
    assert install_result.returncode == 0, install_result.stderr
    existing_rule = target / ".claude/rules/billing.md"
    existing_rule.parent.mkdir(parents=True)
    existing_rule.write_text("project billing rule\n", encoding="utf-8")

    update_result = run_update(target, template)

    assert update_result.returncode == 0, update_result.stderr
    assert existing_rule.read_text(encoding="utf-8") == "project billing rule\n"


def test_update_removes_renamed_init_discovery_link(tmp_path: Path) -> None:
    template = build_template_repo(tmp_path)
    target = tmp_path / "project"
    init_git_repo(target)
    install_result = run_install(target, script=template / "scripts/install.sh")
    assert install_result.returncode == 0, install_result.stderr
    stale_link = target / ".claude/skills/init"
    stale_link.symlink_to("../../.agents/skills/init")

    update_result = run_update(target, template)

    assert update_result.returncode == 0, update_result.stderr
    assert not stale_link.exists()
    assert not stale_link.is_symlink()
    assert (target / ".claude/skills/orchestra-init").is_symlink()


def test_update_preserves_project_owned_native_init_skill(tmp_path: Path) -> None:
    template = build_template_repo(tmp_path)
    target = tmp_path / "project"
    init_git_repo(target)
    install_result = run_install(target, script=template / "scripts/install.sh")
    assert install_result.returncode == 0, install_result.stderr
    native_skill = target / ".claude/skills/init/SKILL.md"
    native_skill.parent.mkdir()
    native_skill.write_text("project-owned init skill\n", encoding="utf-8")

    update_result = run_update(target, template)

    assert update_result.returncode == 0, update_result.stderr
    assert native_skill.read_text(encoding="utf-8") == "project-owned init skill\n"


def test_existing_whole_directory_discovery_link_is_migrated_to_entry_links(
    tmp_path: Path,
) -> None:
    target = tmp_path / "project"
    init_git_repo(target)
    (target / ".claude").mkdir()
    (target / ".claude/agents").symlink_to("../.agents/agents")

    result = run_install(target)

    assert result.returncode == 0, result.stderr
    assert (target / ".claude/agents").is_dir()
    assert not (target / ".claude/agents").is_symlink()
    assert (target / ".claude/agents/general-purpose-opus.md").is_symlink()
    assert (target / ".claude/agents/general-purpose-opus.md").is_file()


def test_update_preserves_native_discovery_content_and_adds_entry_links(
    tmp_path: Path,
) -> None:
    template = build_template_repo(tmp_path)
    target = tmp_path / "project"
    init_git_repo(target)
    assert run_install(target, script=template / "scripts/install.sh").returncode == 0

    native_agents = target / ".claude/agents"
    (native_agents / "downstream-agent.md").write_text(
        "downstream agent\n", encoding="utf-8"
    )

    update_result = run_update(target, template)

    assert update_result.returncode == 0, update_result.stderr
    assert native_agents.is_dir()
    assert (native_agents / "downstream-agent.md").read_text(
        encoding="utf-8"
    ) == "downstream agent\n"
    assert (native_agents / "general-purpose-opus.md").is_symlink()


def test_install_preserves_existing_codex_skills(tmp_path: Path) -> None:
    target = tmp_path / "project"
    init_git_repo(target)
    existing_skill = target / ".codex/skills/my-skill/SKILL.md"
    existing_skill.parent.mkdir(parents=True)
    existing_skill.write_text("user's Codex skill\n", encoding="utf-8")

    result = run_install(target)

    assert result.returncode == 0, result.stderr
    assert existing_skill.read_text(encoding="utf-8") == "user's Codex skill\n"
    assert (target / ".codex/config.toml").is_file()


def test_install_preserves_existing_settings_and_writes_merge_candidate(
    tmp_path: Path,
) -> None:
    target = tmp_path / "project"
    init_git_repo(target)
    settings = target / ".claude/settings.json"
    settings.parent.mkdir(parents=True)
    custom_settings = '{"language": "english"}\n'
    settings.write_text(custom_settings, encoding="utf-8")

    result = run_install(target)

    assert result.returncode == 0, result.stderr
    assert settings.read_text(encoding="utf-8") == custom_settings
    candidate = target / ".claude/settings.orchestra.json"
    assert candidate.read_text(encoding="utf-8") == (
        REPO_ROOT / ".claude/settings.json"
    ).read_text(encoding="utf-8")
    assert "settings.orchestra.json" in result.stdout


def test_install_refuses_parent_symlink_that_escapes_target(tmp_path: Path) -> None:
    target = tmp_path / "project"
    outside = tmp_path / "outside"
    init_git_repo(target)
    outside.mkdir()
    (target / ".claude").symlink_to(outside, target_is_directory=True)

    result = run_install(target)

    assert result.returncode == 2
    assert "symlinked parent" in result.stderr
    assert list(outside.iterdir()) == []


def test_install_refuses_parent_symlink_that_aliases_inside_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "project"
    aliased_directory = target / "aliased"
    init_git_repo(target)
    aliased_directory.mkdir()
    (target / ".claude").symlink_to(aliased_directory, target_is_directory=True)

    result = run_install(target)

    assert result.returncode == 2
    assert "symlinked parent" in result.stderr
    assert list(aliased_directory.iterdir()) == []


def test_install_refuses_non_regular_project_file_before_writing(
    tmp_path: Path,
) -> None:
    target = tmp_path / "project"
    init_git_repo(target)
    (target / "CLAUDE.md").mkdir()

    result = run_install(target)

    assert result.returncode == 2
    assert "regular file" in result.stderr
    assert not (target / "AGENTS.md").exists()


def test_update_uses_namespaced_version_file_and_preserves_project_version(
    tmp_path: Path,
) -> None:
    template = build_template_repo(tmp_path)

    target = tmp_path / "project"
    init_git_repo(target)
    (target / "VERSION").write_text("9.4.1\n", encoding="utf-8")
    install_result = run_install(target, script=template / "scripts/install.sh")
    assert install_result.returncode == 0, install_result.stderr

    (template / "VERSION").write_text("0.3.1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(template), "add", "VERSION"], check=True)
    subprocess.run(
        ["git", "-C", str(template), "commit", "-qm", "release 0.3.1"],
        check=True,
    )

    update_result = run_update(target, template)

    assert update_result.returncode == 0, update_result.stderr
    assert (target / "VERSION").read_text(encoding="utf-8") == "9.4.1\n"
    assert (target / ".claude/orchestra-version").read_text(
        encoding="utf-8"
    ) == "0.3.1\n"


def test_install_creates_native_discovery_symlinks(tmp_path: Path) -> None:
    target = tmp_path / "project"
    init_git_repo(target)

    result = run_install(target)

    assert result.returncode == 0, result.stderr
    assert (target / ".claude/agents").is_dir()
    assert (target / ".claude/skills").is_dir()
    assert not (target / ".claude/agents").is_symlink()
    assert not (target / ".claude/skills").is_symlink()
    assert (target / ".claude/agents/general-purpose-opus.md").is_symlink()
    assert (target / ".claude/skills/context-loader").is_symlink()
    assert (target / ".claude/skills/orchestra-init").is_symlink()
    assert not (target / ".claude/skills/init").exists()
    assert (target / ".claude/agents/general-purpose-opus.md").is_file()
    assert (target / ".claude/skills/context-loader/SKILL.md").is_file()
    assert not any(path.is_symlink() for path in (target / ".codex").iterdir())
    assert ".agents/hooks/" in (target / ".claude/settings.json").read_text(
        encoding="utf-8"
    )


def test_update_preserves_codex_skills_and_repairs_native_discovery(
    tmp_path: Path,
) -> None:
    template = build_template_repo(tmp_path)

    target = tmp_path / "project"
    init_git_repo(target)
    install_result = run_install(target, script=template / "scripts/install.sh")
    assert install_result.returncode == 0, install_result.stderr
    subprocess.run(["git", "-C", str(target), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(target), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(target), "config", "user.name", "Test User"], check=True
    )
    subprocess.run(
        ["git", "-C", str(target), "commit", "-qm", "initial install"], check=True
    )

    link = target / ".claude/skills"
    if link.is_symlink():
        link.unlink()
    elif link.is_dir():
        shutil.rmtree(link)
    link.write_text("not a symlink anymore\n", encoding="utf-8")
    codex_skills = target / ".codex/skills"
    if codex_skills.is_symlink():
        codex_skills.unlink()
    codex_skills.mkdir()
    (codex_skills / "legacy.md").write_text("legacy\n", encoding="utf-8")
    legacy_project_files = {
        "docs/DESIGN.md": "# Legacy design\n",
        "logs/session.log": "legacy log\n",
        "checkpoints/session.md": "legacy checkpoint\n",
    }
    for relative_path, content in legacy_project_files.items():
        legacy_path = target / ".claude" / relative_path
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text(content, encoding="utf-8")
    claude_settings = target / ".claude/settings.json"
    claude_settings.write_text(
        claude_settings.read_text(encoding="utf-8").replace(
            ".agents/hooks/", ".claude/hooks/"
        ),
        encoding="utf-8",
    )

    update_result = run_update(target, template)

    assert update_result.returncode == 0, update_result.stderr
    assert link.is_dir()
    assert not link.is_symlink()
    assert (link / "context-loader").is_symlink()
    assert (target / ".claude/agents").is_dir()
    assert (target / ".claude/agents/general-purpose-opus.md").is_symlink()
    assert (codex_skills / "legacy.md").read_text(encoding="utf-8") == "legacy\n"
    assert {path.name for path in (target / ".codex").iterdir()} == {
        "config.toml",
        "skills",
    }
    migrated_settings = claude_settings.read_text(encoding="utf-8")
    assert ".agents/hooks/" in migrated_settings
    assert ".claude/hooks/" not in migrated_settings
    for relative_path in ("logs/session.log", "checkpoints/session.md"):
        assert (target / ".agents" / relative_path).read_text(encoding="utf-8") == (
            legacy_project_files[relative_path]
        )
    migration_backups = list(target.glob(".orchestra-backup-native-migration-*"))
    assert len(migration_backups) == 1
    assert (migration_backups[0] / ".claude/docs/DESIGN.md").read_text(
        encoding="utf-8"
    ) == legacy_project_files["docs/DESIGN.md"]


def test_update_migrates_legacy_claude_zones_into_agents_state(tmp_path: Path) -> None:
    template = build_template_repo(tmp_path)
    target = tmp_path / "project"
    init_git_repo(target)
    install_result = run_install(target, script=template / "scripts/install.sh")
    assert install_result.returncode == 0, install_result.stderr

    (target / "CLAUDE.md").unlink()
    legacy_state = "## Current Project\n\nKeep this migrated state.\n"
    (target / "CLAUDE.md").write_text(
        "# Old Claude adapter\n\n"
        "# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "# @orchestra:template-boundary\n"
        "# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "## Repository Identity\n\nLegacy project.\n\n"
        "# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "# @orchestra:repo-boundary\n"
        "# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n" + legacy_state,
        encoding="utf-8",
    )
    (target / "AGENTS.md").write_text("# Old CLI bootstrap\n", encoding="utf-8")

    update_result = run_update(target, template)

    assert update_result.returncode == 0, update_result.stderr
    assert (target / "CLAUDE.md").is_symlink()
    assert (target / "CLAUDE.md").resolve() == (target / "AGENTS.md").resolve()
    migrated = (target / ".agents/STATE.md").read_text(encoding="utf-8")
    assert "Legacy project." in migrated
    assert legacy_state.strip() in migrated
    assert "Legacy project." not in (target / "AGENTS.md").read_text(encoding="utf-8")


def test_update_leaves_no_stage_and_swap_debris_and_syncs_safe_dirs(
    tmp_path: Path,
) -> None:
    template = build_template_repo(tmp_path)

    target = tmp_path / "project"
    init_git_repo(target)
    install_result = run_install(target, script=template / "scripts/install.sh")
    assert install_result.returncode == 0, install_result.stderr

    marker = "# updated marker for debris test\n"
    (template / ".agents/INDEX.md").write_text(
        (template / ".agents/INDEX.md").read_text(encoding="utf-8") + marker,
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(template), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(template), "commit", "-qm", "bump .agents content"],
        check=True,
    )

    update_result = run_update(target, template)

    assert update_result.returncode == 0, update_result.stderr
    assert find_debris(target) == []
    assert (target / ".agents/INDEX.md").read_text(encoding="utf-8") == (
        template / ".agents/INDEX.md"
    ).read_text(encoding="utf-8")


def test_update_rolls_back_safe_dir_on_mid_swap_failure(tmp_path: Path) -> None:
    template = build_template_repo(tmp_path)

    target = tmp_path / "project"
    init_git_repo(target)
    install_result = run_install(target, script=template / "scripts/install.sh")
    assert install_result.returncode == 0, install_result.stderr

    original_index = (target / ".agents/INDEX.md").read_text(encoding="utf-8")
    original_listing = sorted(
        p.relative_to(target / ".agents") for p in (target / ".agents").rglob("*")
    )

    marker = "# should never reach the target on a rolled-back update\n"
    (template / ".agents/INDEX.md").write_text(
        (template / ".agents/INDEX.md").read_text(encoding="utf-8") + marker,
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(template), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(template), "commit", "-qm", "bump .agents content"],
        check=True,
    )

    # Shim `mv` on PATH to fail specifically on the second (staging -> live)
    # rename of the .agents/rules swap, simulating a crash between the two mv
    # calls in sync_safe_dirs(). Every other invocation delegates to the
    # real mv so the rest of the update proceeds normally.
    shim_dir = tmp_path / "fake-bin"
    shim_dir.mkdir()
    mv_shim = shim_dir / "mv"
    mv_shim.write_text(
        "#!/usr/bin/env bash\n"
        'for arg in "$@"; do\n'
        '    if [[ "${arg}" == *".agents/rules.orchestra-staging."* ]]; then\n'
        '        echo "shim: simulated mid-swap mv failure" >&2\n'
        "        exit 1\n"
        "    fi\n"
        "done\n"
        'exec /bin/mv "$@"\n',
        encoding="utf-8",
    )
    mv_shim.chmod(0o755)

    update_result = run_update(target, template, extra_path=shim_dir)

    assert update_result.returncode != 0
    assert find_debris(target) == []
    restored_listing = sorted(
        p.relative_to(target / ".agents") for p in (target / ".agents").rglob("*")
    )
    assert restored_listing == original_listing
    assert (target / ".agents/INDEX.md").read_text(encoding="utf-8") == original_index
