#!/usr/bin/env python3
"""
UserPromptSubmit hook: Route to appropriate agent based on user intent.

Routing rules (checked in order, most specific first):
- Design arbitration / stuck problems / final review → Fable advisor (rare)
- Explicit review/rescue/delegation phrases → Codex Plugin commands
- Planning, design, complex code → Codex CLI
- Codebase understanding / large analysis / external research → Opus subagent

Messages are adapted to the active runtime so Codex never delegates back to
Codex CLI recursively.
"""

import json
import sys

# Triggers for Fable advisor (rare escalation: arbitration, stuck, final review)
FABLE_TRIGGERS = {
    "ja": [
        "設計判断に迷",
        "設計の裁定",
        "裁定して",
        "行き詰ま",
        "詰まった",
        "打開",
        "最終レビュー",
        "最終判断",
        "方針を決めて",
        "方針決定",
        "fableに聞",
        "fableに相談",
        "アドバイザー",
    ],
    "en": [
        "design arbitration",
        "arbitrate",
        "settle this",
        "stuck",
        "deadlocked",
        "blocked on design",
        "final review",
        "final judgment",
        "second opinion",
        "ask fable",
        "fable advisor",
        "advisor",
    ],
}

# Triggers for Codex (planning, design, debugging, complex implementation)
CODEX_TRIGGERS = {
    "ja": [
        "設計",
        "どう設計",
        "アーキテクチャ",
        "計画",
        "計画を立てて",
        "なぜ動かない",
        "エラー",
        "バグ",
        "デバッグ",
        "どちらがいい",
        "比較して",
        "トレードオフ",
        "実装方法",
        "どう実装",
        "リファクタリング",
        "リファクタ",
        "レビュー",
        "考えて",
        "分析して",
        "深く",
        "最適化",
    ],
    "en": [
        "design",
        "architecture",
        "architect",
        "plan",
        "planning",
        "debug",
        "error",
        "bug",
        "not working",
        "fails",
        "compare",
        "trade-off",
        "tradeoff",
        "which is better",
        "how to implement",
        "implementation",
        "complex",
        "refactor",
        "simplify",
        "review",
        "check this",
        "think",
        "analyze",
        "deeply",
        "optimize",
        "performance",
    ],
}

# Triggers for Opus research (codebase analysis + external research)
OPUS_RESEARCH_TRIGGERS = {
    "ja": [
        "調べて",
        "リサーチ",
        "調査",
        "サーベイ",
        "最新",
        "ドキュメント",
        "ライブラリ",
        "パッケージ",
        "コードベース",
        "リポジトリ",
        "全体構造",
        "理解して",
        "把握して",
    ],
    "en": [
        "research",
        "investigate",
        "look up",
        "find out",
        "survey",
        "latest",
        "documentation",
        "docs",
        "library",
        "package",
        "framework",
        "codebase",
        "repository",
        "project structure",
        "understand",
        "analyze the code",
    ],
}

# Triggers for Codex Plugin commands (review, rescue, delegation)
CODEX_PLUGIN_TRIGGERS = {
    "ja": [
        "レビューして",
        "コードレビュー",
        "レビューお願い",
        "チェックして",
        "出荷前",
        "codexに任せ",
        "codexに渡",
        "codexに委",
        "バグ調査",
        "調査して",
    ],
    "en": [
        "review this",
        "code review",
        "review my",
        "before shipping",
        "pre-ship",
        "delegate to codex",
        "hand to codex",
        "ask codex to",
        "codex rescue",
        "codex review",
    ],
}


def detect_agent(prompt: str) -> tuple[str | None, str]:
    """Detect which agent should handle this prompt.

    Returns (agent, trigger).
    """
    prompt_lower = prompt.lower()

    # Fable triggers (rare escalation: arbitration, stuck, final review)
    # Checked FIRST — narrow, high-specificity triggers that must not be
    # swallowed by the broader Codex keywords.
    for triggers in FABLE_TRIGGERS.values():
        for trigger in triggers:
            if trigger in prompt_lower:
                return "fable", trigger

    # Codex Plugin triggers (review, rescue, delegation)
    # Checked BEFORE the broad Codex triggers: these are more specific
    # phrases (e.g. "コードレビュー", "review this") that the bare
    # CODEX_TRIGGERS substrings (e.g. "レビュー", "review") would
    # otherwise shadow.
    for triggers in CODEX_PLUGIN_TRIGGERS.values():
        for trigger in triggers:
            if trigger in prompt_lower:
                return "codex-plugin", trigger

    # Codex triggers (planning, design, debug, complex code)
    for triggers in CODEX_TRIGGERS.values():
        for trigger in triggers:
            if trigger in prompt_lower:
                return "codex", trigger

    # Opus research triggers (codebase analysis + external research)
    for triggers in OPUS_RESEARCH_TRIGGERS.values():
        for trigger in triggers:
            if trigger in prompt_lower:
                return "opus-research", trigger

    return None, ""


def is_codex_runtime(data: dict) -> bool:
    """Detect Codex from the hook payload without relying on a shell wrapper."""
    model = str(data.get("model", "")).lower()
    return model.startswith("gpt-") or "codex" in model


def main():
    try:
        data = json.load(sys.stdin)
        prompt = data.get("prompt", "")

        # Skip short prompts
        if len(prompt) < 10:
            sys.exit(0)

        agent, trigger = detect_agent(prompt)
        codex_runtime = is_codex_runtime(data)

        if agent == "fable":
            route = (
                "spawn the native `fable-advisor` Codex subagent; its adapter "
                "coordinates the read-only Fable CLI escalation"
                if codex_runtime
                else "use the fable-advisor subagent"
            )
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": (
                        f"[Fable Advisor] Detected '{trigger}' — this may warrant the "
                        f"{route} (rare escalation: design arbitration / "
                        "stuck problems / final review of large changes; read-only, never "
                        "implements; notes saved to .agents/docs/reviews/). For routine "
                        "review or implementation, use the normal Codex/team-execute "
                        "routes instead."
                    ),
                }
            }
            print(json.dumps(output))

        elif agent == "codex":
            if codex_runtime:
                recommendation = (
                    "use a native Codex subagent such as `general-purpose-opus` "
                    "or `codex-debugger`. Solve the work directly in this runtime; "
                    "do not call Codex CLI recursively."
                )
            else:
                recommendation = (
                    "write the prompt to a file, then `python3 .agents/skills/_shared/"
                    "codex_consult.py --prompt-file <path> --sandbox read-only` for "
                    "design decisions, planning, debugging, or complex analysis."
                )
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": (
                        f"[Agent Routing] Detected '{trigger}' — this task may benefit from "
                        "the deep-work route for planning, design, or complex "
                        f"implementation. Consider: {recommendation}"
                    ),
                }
            }
            print(json.dumps(output))

        elif agent == "codex-plugin":
            recommendation = (
                "Use the native Codex reviewer/deep-worker subagent; Claude-only "
                "`/codex:*` commands do not apply inside Codex."
                if codex_runtime
                else (
                    "Available: `/codex:review` (code review), "
                    "`/codex:adversarial-review` (design challenge), "
                    "`/codex:rescue` (task delegation). Add `--background` for "
                    "async execution, check with `/codex:status`."
                )
            )
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": (
                        f"[Review Route] Detected '{trigger}'. {recommendation}"
                    ),
                }
            }
            print(json.dumps(output))

        elif agent == "opus-research":
            route = (
                "Spawn the native Codex `general-purpose-opus` adapter for "
                "long-context research, codebase analysis, and investigation."
                if codex_runtime
                else (
                    "Opus subagents provide 1M context plus WebSearch/WebFetch. "
                    "Use the Agent tool with subagent_type='general-purpose-opus'."
                )
            )
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": (
                        f"[Opus Research] Detected '{trigger}' — use general-purpose-opus "
                        "for this task. "
                        f"{route} "
                        "Save results to .agents/docs/research/."
                    ),
                }
            }
            print(json.dumps(output))

        sys.exit(0)

    except Exception as e:
        print(f"Hook error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
