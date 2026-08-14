# AGENTS.md — guidance for AI coding agents

## About this repository

A collection of reusable, **agent-agnostic skills** for AI coding agents. Each skill is a top-level directory containing a `SKILL.md` (instructions with YAML frontmatter: `name`, `description`) and optional `scripts/` / `references/`. Skills are consumed through this file, through skill loaders (e.g. Claude Code skills), or by pointing an agent at the relevant folder.

## When you (an agent) work in this repository

- Follow the convention: one skill per top-level directory; `SKILL.md` with `name` and `description` frontmatter.
- Keep instructions **agent-agnostic**: pure bash commands only, no editor/tool-specific idioms.
- Write in English.

## The codegraph skill — when to use it

- **Trigger:** the project you are working in contains a `.codegraph/` directory (a prebuilt code-intelligence index created by the `codegraph` CLI).
- **Action:** read `codegraph/SKILL.md` and use the read-only `codegraph` CLI commands via bash: `status`, `explore`, `query`, `node`, `callers`, `callees`, `impact`, `affected`, `files`.
- **Gate:** if `.codegraph/` is absent, the skill does NOT apply. Do not use it, and **do not** run `codegraph init` / `index` / `sync` — indexing is the user's decision. Tell the user the project is not indexed instead.
- **Never run** (maintenance/service commands are human-only): `install`, `uninstall`, `init`, `uninit`, `index`, `sync`, `unlock`, `upgrade`, `telemetry`, `daemon`, `serve`, `prompt-hook`.

## General rule for consuming skills

Always honor a skill's gate conditions: a skill that requires a precondition (like an existing `.codegraph/` directory) must not be force-used, and must not trigger the precondition itself.
