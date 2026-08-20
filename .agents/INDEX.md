# .agents/ Registry (non-normative index)

## Ownership Boundary

| Directory   | Owns                                                        |
|-------------|-------------------------------------------------------------|
| `.agents/`  | Shared policy/capabilities plus project docs, logs, checkpoints, and state |
| `.claude/`  | Claude Code native configuration only                         |
| `.codex/`   | Codex native configuration and project-owned extensions       |

## Entries

| Item                          | Status                | Canonical File                                | Notes                              |
|-------------------------------|-----------------------|-----------------------------------------------|------------------------------------|
| Root agent contract           | normative             | `AGENTS.md`                                  | Mission, routing, catalogs, execution, quality, language, ownership |
| Tier definitions              | normative             | `.agents/rules/tiers.md`                            | 3-tier hierarchy (default/sol/fable) |
| Delegation-first policy       | normative             | `.agents/rules/delegation.md`                       | Self-handle list, mandatory triggers, route table, subagent prompt contract |
| CLI executor extension        | normative             | `.agents/rules/cli-execution.md`                           | Response, handoff, and verification rules |
| Shared rules                  | normative             | `.agents/rules/`                              | Coding, testing, security, routing, and state rules |
| Shared skills                 | normative             | `.agents/skills/`                             | Workflow and deterministic helper implementations |
| Agent definitions             | normative             | `.agents/agents/`                             | Shared executor role contracts |
| Runtime compatibility         | normative             | `.agents/rules/runtime-compatibility.md`      | Claude/Codex native mapping and state boundary |
| Codex agent adapters          | normative             | `.agents/adapters/codex/agents/`              | TOML model/tool adapters linked from `.codex/agents/` |
| Shared hooks                  | normative             | `.agents/hooks/`                              | Called by both native lifecycle configurations |
| Mutable agent state           | project-owned         | `.agents/STATE.md`                            | Repository identity and cross-session working state |
| Main-agent change runbook     | normative             | `.agents/change_main.md`                      | On-demand procedure for changing the main runtime |
| Project documentation        | project-owned         | `.agents/docs/`                               | Design, research, reviews, and library notes |
| Approved plans                | project-owned         | `.agents/docs/plans/`                         | `/plan` output, consumed by `/team-execute` |
| Antigravity workflows         | experimental/inactive | `.agents/workflows/antigravity/`              | Future multi-agent orchestration   |
| Consistency checker           | tooling               | `.agents/check.sh`                            | Validates cross-file coherence     |

## Related Canonical Files (outside .agents/)

- **Model configuration**: `.claude/settings.json` (`env.CODEX_MODEL`) and `.codex/config.toml` (`model`)
- **Native lifecycle configuration**: `.claude/settings.json` and `.codex/hooks.json`
- **Cross-runtime details**: `.agents/rules/runtime-compatibility.md` and `.agents/rules/codex-delegation.md`
- **Root bootstrap**: `AGENTS.md`; `CLAUDE.md` is a relative symlink to it
- **Runtime launcher**: `scripts/orchestra <claude|codex>`
