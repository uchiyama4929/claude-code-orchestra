# claude-code-orchestra

![Claude Code Orchestra](./summary.png)

Dual-runtime multi-agent development environment for Claude Code and Codex.

```
Shared `.agents/` ─┬─ Claude Code: Sonnet / Opus / Fable adapters
                   └─ Codex: Luna / Terra / Sol adapters
```

## Quick Start

Confirm that both AI CLIs are installed and authenticated first:

```bash
claude --version && codex --version
```

### New Project

Create a repository with GitHub's **Use this template** button, clone it, then
launch either runtime in the same working tree:

```bash
./scripts/orchestra claude
# or
./scripts/orchestra codex
```

Invoke `orchestra-init` (`/orchestra-init` in Claude Code or
`$orchestra-init` in Codex) to detect the stack and populate shared project
identity and design documents.

On the first Codex launch, open `/hooks`, review the repository hook commands,
and trust them. Codex skips untrusted project hooks until this review is done.

### Existing Project

Run this from the root of an existing Git repository:

```bash
template_dir="$(mktemp -d)"
git clone --depth 1 https://github.com/uchiyama4929/claude-code-orchestra.git "$template_dir"
bash "$template_dir/scripts/install.sh" . && rm -rf "$template_dir"
```

The installer preserves project-owned files, including `README.md`, `VERSION`, and
existing `AGENTS.md` / `CLAUDE.md` content, native Claude agents and skills,
native Codex agents, and `.codex/skills/`. It installs the merged content in
`.agents/STATE.md`, installs the concise shared `AGENTS.md` contract, and creates
`CLAUDE.md -> AGENTS.md`. Template-owned path conflicts stop the install before
changes are made. After reviewing the reported paths, `--force` can be used to back
them up under `.orchestra-backup-*/` and replace them.

Existing `.claude/settings.json` and `.codex/hooks.json` files are never
overwritten. When a manual merge is needed, the installer writes the matching
`*.orchestra.json` candidate; merge it and delete the candidate.

Then start either runtime:

```bash
./scripts/orchestra claude
./scripts/orchestra codex
```

## Prerequisites

### Claude Code

```bash
npm install -g @anthropic-ai/claude-code
claude login
```

### Codex CLI

```bash
npm install -g @openai/codex
codex login
```

### System Tools

The installer and updater require Python 3.11+, `git`, and standard Unix shell
tools. Template updates additionally require `rsync`.

### Codex Plugin for Claude Code (Optional)

A plugin that lets you use Codex directly from Claude Code. Simplifies code review and task delegation.

```bash
# Run inside Claude Code
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup
```

**Available commands:**
- `/codex:review` — Code review
- `/codex:adversarial-review` — Design challenge review
- `/codex:rescue` — Task delegation
- `/codex:status` / `/codex:result` / `/codex:cancel` — Job management

### Keeping AI CLIs Up to Date

Claude Code and Codex CLI both release frequently — model names, flags, and sandbox semantics drift between minor versions. **Update both before each working session.**

```bash
# Claude Code (built-in self-update)
claude update

# Codex CLI
npm install -g @openai/codex@latest
```

Confirm versions afterward:

```bash
claude --version && codex --version
```

The Codex model is centralized in `.claude/settings.json` (`env.CODEX_MODEL`), which every `${CODEX_MODEL:-...}` reference resolves to. `.codex/config.toml` (`model` + `model_reasoning_effort = "xhigh"`) must be kept in sync — `.agents/check.sh` verifies coherence between the two. To always use the latest model, bump that single value (currently `gpt-5.6-sol`) — no need to edit individual skill files. The `${CODEX_MODEL:-...}` fallback is just a default for when the env var is unset. Note: `update.sh` never auto-merges `.claude/settings.json` — downstream users must bump `env.CODEX_MODEL` manually after reviewing the Phase 5 diff.

Claude runs the main context on `opus[1m]`; its routine and deep routes use
Sonnet and Opus. Codex runs the main context on `gpt-5.6-sol`; its routine,
debug, and deep routes use Luna, Terra, and Sol. Stable route names point to the
native model adapter rather than promising one vendor in both products.

## Architecture

The normative, tool-neutral orchestration policy and the complete agent/skill
overview live in root `AGENTS.md`; `.agents/rules/tiers.md` defines the stable
tier details.
The launched runtime is the initial main agent. To pin a repository default,
follow `.agents/change_main.md`. The diagram below is a non-normative overview.

```
┌─────────────────────────────────────────────────────────────┐
│      Current runtime (Claude Code or Codex orchestrator)    │
│       → Context conservation is top priority                │
│       → Handles user interaction, coordination, concise edits│
│                          │                                  │
│  ┌───────────────────────┼──────────────────────────────┐   │
│  │  Tier 1 — Default     │                              │   │
│  │  ┌────────────────────┴─────────────────────────┐    │   │
│  │  │ general-purpose-sonnet: Sonnet / Luna        │    │   │
│  │  │ general-purpose-opus: Opus / Sol             │    │   │
│  │  │ codex-debugger: Claude→Codex / Terra         │    │   │
│  │  └──────────────────────────────────────────────┘    │   │
│  │                       │                              │   │
│  │  ┌────────────────────┴─────────────────────────┐    │   │
│  │  │ Tier 2 — Sol                                 │    │   │
│  │  │ Codex native or Claude→Codex CLI handoff     │    │   │
│  │  │ → Design, planning, complex code, debugging  │    │   │
│  │  └──────────────────────────────────────────────┘    │   │
│  │                       │                              │   │
│  │  ┌────────────────────┴─────────────────────────┐    │   │
│  │  │ Tier 3 — Fable  (rare advisor, read-only)    │    │   │
│  │  │ → Arbitration, stuck problems, final review  │    │   │
│  │  │ → Notes to .agents/docs/reviews/             │    │   │
│  │  └──────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Context Management (Important)

Use the routing policy and execution patterns in root `AGENTS.md`.
Product-specific delegation mechanics remain in
`.agents/rules/runtime-compatibility.md` and native adapters.

The posture is **delegation-first**: `.agents/rules/delegation.md` makes direct
execution by the main agent the exception, limited to a closed Self-Handle List,
and names the triggers, route table, and subagent prompt contract that every
skill follows. Delegating moves the work, not the accountability — the caller
still runs the acceptance checks and inspects the diff.

## Directory Structure

`.agents/` owns shared policy, runtime content, project context, and state.
`.claude/` and `.codex/` retain product-native configuration and project-owned
extensions. Orchestra entries are canonical under `.agents/`; native agent
directories receive entry-level links so unrelated project entries can coexist.

```
.
├── AGENTS.md                    # Shared mission, routing, agent/skill catalog, and gates
├── CLAUDE.md -> AGENTS.md       # Claude Code discovery symlink
├── README.md
├── PROGRESS.md                  # Generated by the first /checkpointing run; latest 5 summaries
├── LICENSE
├── pyproject.toml               # Python project configuration
├── uv.lock                      # Dependency lock file
├── VERSION                      # Version of this template repository; downstream projects may replace it
│
├── .agents/                     # Shared tool-neutral orchestration SSOT
│   ├── INDEX.md                 # Agent registry — lists all CLI subagents and their tiers
│   ├── STATE.md                 # Main agent, repository identity, and working state
│   ├── orchestra-version       # Installed Orchestra version in downstream projects
│   ├── change_main.md           # On-demand main-agent change runbook
│   ├── check.sh                 # Contract, bootstrap, model, and tier coherence checker
│   ├── agents/                  # Shared role definitions (Claude-readable)
│   ├── adapters/                # Thin product-specific surfaces
│   │   ├── claude/skills/       # Claude-only manual invocation policy
│   │   └── codex/agents/        # Codex TOML model/tool adapters
│   ├── skills/                  # Shared workflow skills and deterministic helpers
│   │   └── _shared/             # Bundled runtime: helpers every skill may depend on
│   ├── hooks/                   # Shared hook implementations
│   ├── rules/                   # Shared policy: delegation, tiers, CLI, coding, testing, security
│   ├── docs/                    # Design, handoff, research, review, and library documents
│   ├── logs/                    # Runtime logs (git-ignored)
│   ├── checkpoints/             # Session checkpoints (git-ignored)
│   └── workflows/
│       └── antigravity/         # Experimental Antigravity adapter skeletons
│           ├── feature.md
│           └── troubleshoot.md
│
├── .claude/
│   ├── settings.json             # Claude Code settings; hooks point to .agents/
│   ├── agents/                   # Per-entry links plus project-owned native agents
│   └── skills/                   # Per-entry links plus project-owned native skills
│
├── .codex/
│   ├── config.toml              # Codex native configuration
│   ├── hooks.json               # Codex lifecycle mapping to .agents/hooks/
│   ├── agents/                  # Per-entry links plus project-owned agents
│   └── skills/                  # Optional project-owned legacy skills; preserved
│
├── tests/                      # Contract tests for the template's own scripts and docs
│
└── scripts/
    ├── install.sh              # Conflict-aware installer for existing projects
    ├── update.sh               # Template update script
    └── orchestra              # Runtime selector; never switches Git branches
```

### Stabilizing Codex Integration

- Use templates from `@.agents/docs/CODEX_HANDOFF_PLAYBOOK.md` to standardize requests to Codex
- `.agents/rules/codex-delegation.md` defines the "Codex-first delegation" policy and exception conditions
- `.codex/config.toml` uses `approval_policy = "never"` to prevent blocking in non-interactive flows, and `sandbox_mode = "danger-full-access"` for unrestricted execution

## Workflow

The main workflow executes two skills in sequence. Use `/name` in Claude Code
and `$name` in Codex; both load the same `.agents/skills/name/SKILL.md`.

```
/feature <feature>   Planning: mode determination → understanding → research & design → plan
    ↓ After user approval (COMPLEX route)
/team-execute        Phase 1: Parallel implementation → Phase 2: Parallel review (Agent Teams)
```

1. Determine existing or greenfield mode.
2. The native deep worker analyzes the codebase while the main agent gathers requirements.
3. Native subagents perform design and research in parallel where useful.
4. The main agent integrates the plan and requests user approval.
5. `team-execute` performs parallel implementation and review (`--review-only` skips implementation).

## Skills

Each skill is a `SKILL.md` procedure that an agent follows. Steps with exactly
one correct output for a given input — deriving artifact paths, validating
document structure, invoking the Codex CLI, running quality gates — are
delegated to bundled scripts instead of being described in prose, so they cannot
drift between phases or fail silently. Judgment steps stay in markdown. The
boundary and the shared script contract (one JSON object on stdout, a common
exit-code vocabulary, errors never swallowed) are documented in
`.agents/skills/_shared/README.md`.

### Core Workflow

#### `/feature` — Feature Planning & Implementation (unified)

One entry point for feature work, with two modes (merger of the old `/add-feature` and `/start-feature`).

```
/feature user profile editing feature
```

**Modes:**
- **existing** — native deep-worker analysis, architecture, planning, and validation for an established codebase
- **greenfield** — parallel native research and architecture subagents for a large or new feature

**Shared complexity-based routing:**
- SIMPLE (1-3 files, <50 LOC) → focused native implementation
- MODERATE (3-5 files) → deep worker + `team-execute --review-only`
- COMPLEX (5+ files) → `team-execute`

#### `/team-execute` — Parallel Implementation + Review (unified)

Two-phase native-subagent execution based on the plan approved in `feature`.

```
/team-execute                 # Phase 1 IMPLEMENT → Phase 2 REVIEW
/team-execute --review-only   # Skip Phase 1; review existing changes
```

**Phase 1 IMPLEMENT:**
- Launches native subagents per module/layer with separated file ownership
- Manages dependencies via shared task list for autonomous coordination
- Each Teammate records a work log to `.agents/logs/agent-teams/` upon completion

**Phase 2 REVIEW (reviewer composition):**
- **Security Reviewer** — Detects security vulnerabilities
- **Quality Reviewer** — Checks code quality & pattern compliance (leveraging Codex)
- **Test Reviewer** — Validates test coverage & quality

#### `/spike` — Technical Investigation & Feasibility Study

A time-boxed technical investigation using the current runtime's deep route.
It produces a **decision document**, not an implementation plan.

```
/spike Should we adopt WebSocket or SSE?
```

**Workflow:**
1. Main agent → Frame questions and constraints
2. Native subagents → Research and feasibility analysis in parallel
3. Deep route → Synthesize a go/no-go recommendation and report

> After a GO decision, proceed to implementation with `/feature`

### Development

#### `/plan` — Implementation Plan

Breaks down requirements into concrete steps.

```
/plan Add API endpoint
```

**Output:**
- Implementation steps (files, changes, verification methods)
- Dependencies & risks
- Validation criteria

#### `/tdd` — Test-Driven Development

Implements using the Red-Green-Refactor cycle.

```
/tdd user registration feature
```

**Workflow:**
1. Design test cases
2. Write failing tests (Red)
3. Minimal implementation (Green)
4. Refactoring (Refactor)

#### `/simplify` — Code Refactoring

Simplifies code and improves readability.

#### `/troubleshoot` — Error Diagnosis & Fix Planning

Diagnoses errors and creates fix plans through multi-agent coordination centered on Codex.

```
/troubleshoot TypeError: cannot unpack non-iterable NoneType object
```

**Workflow:**
1. Deep worker → Error reproduction and context collection
2. Native subagents → Root-cause and impact diagnosis in parallel
3. Main agent → Fix-plan integration and user approval

### Agent Delegation

#### `codex-system` — Deep Reasoning Route

Used for design decisions, debugging, and trade-off analysis. Claude Code may
delegate these to Codex CLI; Codex performs them natively and never recurses.

**Trigger examples:**
- "How should this be designed?" "How should I implement this?"
- "Why isn't this working?" "I'm getting an error"
- "Which is better?" "Compare these options"

### Documentation

#### `/design-tracker` — Design Decision Tracking

Detects design decisions during conversation and structurally updates the relevant section of `.agents/docs/DESIGN.md` (機能要件 / 非機能要件 / アーキテクチャ / 技術選定 / 制約 / Key Decisions). Activates proactively and also on explicit requests ("record this", "update DESIGN").

#### `/research-lib` — Library Research

Investigates a library and generates comprehensive documentation in `.agents/docs/libraries/`.

```
/research-lib httpx
```

#### `/update-lib-docs` — Update Library Documentation

Updates existing documentation in `.agents/docs/libraries/` with the latest information.

### Session Management

#### `/checkpointing` — Session Persistence

Records session activity into `.agents/checkpoints/`, regenerates the rolling
`PROGRESS.md`, and compacts stale working blocks in `.agents/STATE.md` while
preserving the main-agent selection, repository identity, and progress link.

```bash
/checkpointing                    # Full recording + pattern discovery
/checkpointing --since "2026-02-08"  # Only since a specific date
/checkpointing --compact-only    # Run only the Compact Phase (old /context-refresh)
```

#### `/orchestra-init` — Project Initialization

Analyzes the project structure, auto-detects tech stack, commands, and
configuration. Populates `.agents/docs/DESIGN.md` and updates only the thin
`## Repository Identity` section in `.agents/STATE.md`.

#### `/catchup` — Onboarding Guide

Scans the repository (git history, AGENTS.md, project rules, skill catalog, DESIGN.md, research & library notes, checkpoints, agent-team logs) and writes a `GUIDE.md` at the repository root so new or returning contributors can understand past work and resume quickly.

```bash
/catchup
```

## Development

### Template Update

Safely applies template updates to your local project.

```bash
# Update to the latest version
./scripts/update.sh

# Update to a specific version
./scripts/update.sh v0.2.0

# Skip confirmation prompt
./scripts/update.sh --yes
```

When upgrading an installation that still uses an updater from v0.3.0 or earlier,
replace the updater itself before the first run. This prevents the old process from
writing its template version to a project-owned root `VERSION`:

```bash
template_dir="$(mktemp -d)"
git clone --depth 1 https://github.com/uchiyama4929/claude-code-orchestra.git "$template_dir"
cp "$template_dir/scripts/install.sh" "$template_dir/scripts/update.sh" \
  "$template_dir/scripts/orchestra" scripts/
chmod +x scripts/install.sh scripts/update.sh scripts/orchestra
rm -rf "$template_dir"
./scripts/update.sh
```

**How it works:**
- `AGENTS.md` is replaced with the shared agent contract;
  `CLAUDE.md` is repaired as a symlink to it.
- `.agents/STATE.md`, project design/research, logs, and checkpoints are
  preserved. Legacy 2/3-zone `AGENTS.md` or `CLAUDE.md` state is migrated into
  `.agents/STATE.md` before the bootstrap is replaced.
- Only template-owned `.agents/` subdirectories and `.codex/config.toml` are
  atomically synced. Existing native Claude/Codex agents and skills are
  preserved; missing Orchestra entries are linked individually.
- Real legacy `.claude/{docs,logs,checkpoints}` data is migrated to `.agents/`;
  collisions are backed up before missing files are merged.
- Known legacy `.claude/hooks/` references in Claude settings are migrated to
  `.agents/hooks/`; other settings differences still require manual review.
- Missing native settings are installed. Differing `.claude/settings.json` or
  `.codex/hooks.json` produces a `*.orchestra.json` merge candidate.
- The installed template version is stored in `.agents/orchestra-version`; a
  downstream project's root `VERSION` is never modified.
- If the update modifies `scripts/update.sh` itself (e.g. a new version adds
  template directories such as `.agents/`), **run `./scripts/update.sh` a second
  time** — the first run still uses the old script's sync list. Newer scripts
  print a reminder when this applies (updating from v0.2.0 does not, so run
  twice when upgrading to v0.3.0)

### Tech Stack

| Tool | Purpose |
|--------|------|
| **uv** | Package management (pip is prohibited) |
| **ruff** | Linting & formatting |
| **ty** | Type checking |
| **pytest** | Testing |
| **poethepoet** | Task runner |

### Commands

```bash
# Dependencies
uv add <package>           # Add package
uv add --dev <package>     # Add dev dependency
uv sync                    # Sync dependencies

# Quality checks
poe lint                   # ruff check + format
poe typecheck              # ty
poe test                   # pytest
poe all                    # Run all checks

# Direct execution
uv run pytest -v
uv run ruff check .
```

## Hooks

Automation hooks execute agent coordination and quality checks at the appropriate timing.

| Hook | Trigger | Action |
|--------|----------|------|
| `agent-router.py` | User input | Suggests the active runtime's native route |
| `runtime-context.py` | Codex session start/resume | Loads shared durable context |
| `runtime-handoff.py` | Codex stop/subagent stop/compact | Saves the latest completed output for cross-runtime access |
| `lint-on-save.py` | Claude Edit/Write or Codex apply_patch of Python | Reports format, lint, and type errors without rewriting files |
| `check-codex-before-write.py` | Before file write | Suggests consulting Codex |
| `check-codex-after-plan.py` | After Task execution | Suggests Codex review after planning/design tasks |
| `post-bash-check.py` | Any Bash tool call | Dispatcher: runs error detection, test-failure analysis, and Codex I/O logging in one process (deduped) |
| `error-to-codex.py` | Bash error detected | Suggests codex-debugger subagent (invoked in-process by `post-bash-check.py`) |
| `post-test-analysis.py` | Test/build failure | Suggests debug analysis via Codex (invoked in-process by `post-bash-check.py`) |
| `post-implementation-review.py` | After large implementation | Suggests code review via Codex |
| `log-cli-tools.py` | Codex execution | Records I/O logs (invoked in-process by `post-bash-check.py`; also runs standalone on `TaskCompleted`) |

`lint-on-save.py` is an agent post-tool hook, not an editor-wide save hook.
It runs `ruff format --check`, `ruff check`, and `ty check` only for the Python
files the agent just edited. It does not pass `--fix` and cannot change files.
Run `poe format` explicitly when a formatting rewrite is intended; that command
can update every Python file under the current directory.

## Language Rules

- **Code, thinking, and reasoning**: English
- **Responses to users**: Japanese
- **Technical documentation**: English
- **README, etc.**: Japanese permitted
