from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO_ROOT / ".agents/hooks/lint-on-save.py"


def load_hook() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lint_on_save", HOOK_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_python_save_hook_checks_without_rewriting(monkeypatch, tmp_path: Path) -> None:
    hook = load_hook()
    python_file = tmp_path / "example.py"
    python_file.write_text("value=1\n", encoding="utf-8")
    commands: list[list[str]] = []

    monkeypatch.setattr(hook, "get_file_path", lambda: str(python_file))
    monkeypatch.setattr(
        hook,
        "run_command",
        lambda command, cwd: (commands.append(command) or (0, "", "")),
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    hook.main()

    assert commands == [
        ["uv", "run", "--no-sync", "ruff", "format", "--check", str(python_file)],
        ["uv", "run", "--no-sync", "ruff", "check", str(python_file)],
        ["uv", "run", "--no-sync", "ty", "check", str(python_file)],
    ]
    assert python_file.read_text(encoding="utf-8") == "value=1\n"
