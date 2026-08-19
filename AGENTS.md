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

## General rule for consuming skills

Always honor a skill's gate conditions: a skill that requires a precondition (like an existing `.codegraph/` directory) must not be force-used, and must not trigger the precondition itself.
