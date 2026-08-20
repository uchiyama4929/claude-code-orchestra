# Runtime Compatibility

Orchestra keeps durable instructions, skills, state, design, checkpoints, and
handoffs under `.agents/`. Claude Code and Codex read those same files; native
directories contain adapters only.

## Native adapters

| Capability | Claude Code | Codex |
|---|---|---|
| Root instructions | `CLAUDE.md` -> `AGENTS.md` | `AGENTS.md` |
| Skills | `.claude/skills/*` links to shared skills or thin invocation adapters | `.agents/skills/*` |
| Subagents | `.claude/agents/*.md` | `.codex/agents/*.toml` |
| Lifecycle config | `.claude/settings.json` | `.codex/hooks.json` |

Names such as `general-purpose-sonnet` and `general-purpose-opus` are stable
routing identifiers. They select the native adapter for the current runtime;
they do not promise that the same model vendor runs in both products.

## Delegation semantics

- Use the current runtime's native subagent API for every route defined in
  `.agents/rules/delegation.md`.
- Claude Code uses its Task/Agent Teams operations and the linked Markdown
  definitions. Codex spawns the matching project agent from
  `.codex/agents/*.toml`.
- A runtime must not invoke itself through a CLI wrapper. In particular, Codex
  performs Codex work directly instead of calling `codex_consult.py`.
- Cross-vendor escalation uses `.agents/skills/_shared/cli_consult.py`. It is a
  separate authenticated CLI session, so the caller must persist the result in
  `.agents/` before continuing.
- Legacy skill wording such as `Task(subagent_type=...)` denotes the matching
  native subagent operation when the current runtime is Codex.

## Shared and local state

`STATE.md`, `DESIGN.md`, `PROGRESS.md`, checkpoints, and project documentation
are the durable source of truth. Native chat histories and in-memory context are
not interchangeable. Stop hooks save the latest completed output under
`.agents/logs/handoffs/` so the other runtime can inspect it; use checkpointing
for a full resumable handoff.

Concurrent sessions may read shared files. Writes to project state must use the
existing atomic helpers or a runtime-owned file; do not have two agents edit the
same state block concurrently.
