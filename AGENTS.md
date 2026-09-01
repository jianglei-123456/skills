# AGENTS.md — guidance for AI coding agents

## About this repository

A collection of reusable, **agent-agnostic skills** for AI coding agents. Each skill is a top-level directory containing a `SKILL.md` (instructions with YAML frontmatter: `name`, `description`) and optional `scripts/` / `references/`. Skills are consumed through this file, through skill loaders (e.g. Claude Code skills), or by pointing an agent at the relevant folder.

## When you (an agent) work in this repository

- Follow the convention: one skill per top-level directory; `SKILL.md` with `name` and `description` frontmatter.
- Keep instructions **agent-agnostic**: pure bash commands only, no editor/tool-specific idioms.
- Write in English.

## The codegraph skill — when to use it

- **Trigger:** the project you are working in contains a `.codegraph/` directory (a prebuilt code-intelligence index created by the `codegraph` CLI).
- **Action:** read `codegraph/SKILL.md` and use the read-only `codegraph` CLI commands via bash (`status`, `explore`, `query`, `node`, `callers`, `callees`, `impact`, `affected`, `files`); full syntax in `codegraph/references/commands.md`.
- **Gate:** if `.codegraph/` is absent, the skill does NOT apply — tell the user the project is not indexed instead; indexing (`init`/`index`/`sync`) is the user's decision, never the agent's. Read-only retrieval only: maintenance commands (`install`, `uninstall`, `uninit`, `unlock`, `upgrade`, `telemetry`, `daemon`, `serve`, `prompt-hook`) are human-only.

## The dbx skill — when to use it

- **Trigger:** the user needs database work — run SQL queries, inspect tables/schemas, list connections — that a DBX connection can serve.
- **Action:** read `dbx/SKILL.md` and use the `dbx` CLI via bash (`doctor`, `connections list`, `schema list/describe`, `query`, `context`, `open`); full syntax in `dbx/references/commands.md`.
- **Gate:** `dbx: command not found`, or the requested connection is missing from `dbx connections list` → tell the user (install the CLI / create the connection in DBX Desktop); agents never install the CLI or create connections. Queries are read-only by default; write flags (`--allow-writes`, `--allow-dangerous-sql`) only when the user explicitly asks.

## The codebuddy会话总结 skill — when to use it

- **Trigger:** the user asks to 总结/回顾/查询 their past CodeBuddy coding sessions — what they built on a given day or range of days, across projects (e.g. "总结下18,19,20这三天都开发了什么东西").
- **Action:** read `codebuddy-session-summary/SKILL.md` and run `python codebuddy-session-summary/scripts/summarize_sessions.py --since YYYY-MM-DD [--until YYYY-MM-DD]` (options: `--days N`, `--project <name>`, `--root <dir>`); group output by day into a digest in the user's language.
- **Gate:** no `*.jsonl` transcripts under `~/.codebuddy/projects/` → tell the user no session history was found; never invent content.

## The topic-note skill — when to use it

- **Trigger:** the user asks for a topic researched and written up as a **single** document — a report, a study note, an overview (e.g. "整理一份关于 X 的文档").
- **Action:** read `topic-note/SKILL.md` and follow its workflow: scope → background-agent research → write one Markdown file in the user's language → land it in the current directory (or a user-specified path).
- **Gate:** the output is exactly one document — never multiple files, never folder structures; write only from researched sources, never from parametric knowledge.

## The dt-cabin-modify skill — explicit invocation only

- **Trigger:** NONE — this skill must NOT fire on natural language. The user must explicitly invoke it (e.g. `/dt-cabin-modify`) before any of its scripts run.
- **Action:** read `dt-cabin-modify/SKILL.md` and follow its flow: confirm inputs (IMEI, target owner company) → `get_token.py` → `preview.py` (show all dbx lookups to the user, await confirmation) → `run_flow.py --yes` (update sale info, conditional install delete, three install inserts, 5s delay + updateUserInfo).
- **Gate:** only run when the user explicitly asks for this skill; never auto-trigger on mentions of 座舱/归属企业/IMEI changes.

## General rule for consuming skills

Always honor a skill's gate conditions: a skill that requires a precondition (like an existing `.codegraph/` directory) must not be force-used, and must not trigger the precondition itself.
