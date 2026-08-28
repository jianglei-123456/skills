# ai-agent-skills

Reusable, **agent-agnostic skills** for AI coding agents (Codex, Cursor, Gemini CLI, opencode, Cline, Claude Code, and any agent that reads `AGENTS.md` or loads skill folders).

Each skill is a self-contained directory with a `SKILL.md` that tells the agent **when** to use it and **how** to run it. Skills are written as plain bash instructions so any agent can execute them directly.

## Skills

| Skill | What it does | Requires |
|---|---|---|
| [codegraph](codegraph/) | Explore a codebase through its prebuilt code-intelligence graph: symbol search, source with call paths, change-impact analysis, affected tests — no grep/read loops. | `codegraph` CLI + a `.codegraph/` index in the target project |
| [codebuddy会话总结](codebuddy-session-summary/) | Summarize past CodeBuddy coding sessions: extract AI titles and first user messages from `~/.codebuddy/projects/*/*.jsonl`, group by day. | Python 3 |
| [dt-cabin-modify](dt-cabin-modify/) | Modify a device's owner company on the DT platform and rebuild install/machine/owner records. Explicit invocation only — never auto-triggers. Includes env checks (dbx CLI, credentials via env vars, dbx connection). | Python 3, `dbx` CLI, `DT_USERNAME`/`DT_PASSWORD` env vars |

## Quick start

1. Install the CLI each skill needs (see the skill's own README, e.g. [codegraph/README.md](codegraph/README.md)).
2. Make the skills available to your agent:
   - **Copy a skill folder** into your agent's skills directory, or
   - **Point your agent at this repo** (clone it / add it as a workspace) so it picks up `AGENTS.md` and the skill folders.

### Agent integration

| Agent | How it consumes this repo |
|---|---|
| Codex CLI, opencode, Gemini CLI, Cline | Reads `AGENTS.md` from the workspace root — the codegraph trigger/gate rules live there |
| Cursor | Add the repo to your project, or copy the `AGENTS.md` guidance into `.cursor/rules`; or use the skill folder directly |
| Claude Code | Copy a skill folder into `~/.claude/skills/` (or project `.claude/skills/`); the `SKILL.md` frontmatter triggers it |

## The codegraph skill in one paragraph

The [codegraph](codegraph/) skill wraps the **read-only** commands of the [`codegraph` CLI](https://github.com/colbymchenry/codegraph) (`@colbymchenry/codegraph`). When a project contains a `.codegraph/` directory, agents use `codegraph explore / query / node / callers / callees / impact / affected / files / status` to explore code instead of blind grep/read loops. Initialization and reindexing stay with the human: **the skill never runs `init` / `index` / `sync`**, and it only applies when `.codegraph/` already exists.

## Adding a skill

1. Create a top-level directory `<skill-name>/`.
2. Write `<skill-name>/SKILL.md` with YAML frontmatter (`name`, `description`) followed by the instructions.
3. Add optional `scripts/` / `references/` as needed.
4. Update the skills table above and the gate rules in `AGENTS.md`.

## License

[MIT](LICENSE)
