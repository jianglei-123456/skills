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

## The dt-sale-update skill — explicit invocation only

- **Trigger:** NONE — this skill must NOT fire on natural language. The user must explicitly invoke it (e.g. `/dt-sale-update`) before any of its scripts run.
- **Action:** read `dt-sale-update/SKILL.md` and follow its flow: confirm inputs (IMEI list, SKU, owner company — a partial name is fine, `--date` optional defaulting to today) → `get_token.py` → `preview.py` (product by SKU, company full name/id, current device values, final JSON; await confirmation) → `update_sale.py --yes` (sequential `updateSaleInformation`, stops at the first failure, prints updated/failed/skipped).
- **Gate:** explicit invocation only; never auto-trigger on mentions of 销售信息/销售时间/服务期. DB access is read-only (`dbx query` against `prod_192.168.5.129_dss_owner` for `contract.product` and `prod_192.168.5.17_machine` for `basic.company`); the only external write is the DT update API.
## The ysb-data-export skill — explicit invocation only

- **Trigger:** NONE — this skill must NOT fire on natural language. The user must explicitly invoke it (e.g. `/ysb-data-export`) before any of its scripts run.
- **Action:** read `ysb-data-export/SKILL.md` and follow its flow: resolve the export scope (owner company name/id via `--company` and/or explicit IMEI list via `--imeis` and/or owner region `--owner-province`/`--owner-city`/`--owner-county` and/or terminal types `--terminal-types`; at least one required) → interactive field selection (`--list-fields`, then `--fields` / `--exclude` / `--no-photos` / `--no-idcard`) → `--preview` (show summary + IMEI hit/miss list + 5-row sample, await user confirmation) → rerun the same parameters with `--yes` to write the xlsx. Install mode is the default; `--with-work` exports install+work rows (one row per device × work day) and requires a date range.
- **Gate:** explicit invocation only; never auto-trigger on mentions of 安装数据/作业数据/导出. All DB access is read-only (`dbx query` against `prod_192.168.5.17_machine`); the only write is the resulting local xlsx.

## The explain-logic skill — explicit invocation only

- **Trigger:** NONE — this skill must NOT fire on natural language. The user explicitly invokes `/explain-logic <target>` before it runs.
- **Action:** read `explain-logic/SKILL.md` and follow it: scope sketch → wait for the user's confirmation → five-layer explanation. It explains exactly one named business chain, never the whole repository.
- **Gate:** never run `codegraph init` / `index` / `sync`; indexing is the user's decision. If the project has no `.codegraph/` index, read files directly instead.

## General rule for consuming skills

Always honor a skill's gate conditions: a skill that requires a precondition (like an existing `.codegraph/` directory) must not be force-used, and must not trigger the precondition itself.
