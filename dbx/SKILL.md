---
name: dbx
description: Database access via the dbx CLI. Use when the user needs database work — run SQL queries, inspect tables or schemas, list connections — against databases preconfigured in DBX (PostgreSQL/Redshift, MySQL-compatible, SQLite, …). Read-only by default; writes require explicit opt-in flags. Gate: dbx CLI not installed → tell the user, do not install.
---

# DBX — query databases through preconfigured connections

## When to use

DBX stores named connections to databases (PostgreSQL/Redshift, MySQL-compatible, SQLite). Use it whenever the user needs database work — run SQL, inspect tables or columns, list connections — that a DBX connection can serve.

**Gate — check first:** `dbx --version` must run. If `dbx: command not found`, tell the user to install (see README.md) — do not install it yourself. If the connection name the user wants is not in `dbx connections list`, tell them — connections are created in DBX Desktop, not by the agent.

## Start (every session)

1. **Verify:** `dbx doctor` — confirms the CLI, connection store, and native SQLite loader are available.
2. **Find the connection:** `dbx connections list --json` — the exact connection name (a default can be set via `DBX_CONNECTION`, see references/commands.md).
3. **Inspect the schema first:** `dbx schema list <conn>` then `dbx schema describe <conn> <table>` — know the tables and columns before writing a query.
4. **Query:** `dbx query <conn> "<sql>" --json`.

## Command quick reference

One-line form per command. Need exact syntax, options (`--format`, `--limit`, `--timeout`, `--file`, `--allow-writes`, …), or output details? Read [references/commands.md](references/commands.md).

| Goal | Command |
|---|---|
| Check CLI / desktop bridge health | `dbx doctor` |
| List connections (no secrets) | `dbx connections list` |
| List tables/views | `dbx schema list <conn>` |
| Show table columns | `dbx schema describe <conn> <table>` |
| Run one SQL statement | `dbx query <conn> "<sql>"` |
| Run SQL from a file | `dbx query <conn> --file ./query.sql` |
| Compact schema context for prompts | `dbx context <conn>` |
| Open a table in DBX Desktop | `dbx open <conn> <table>` |

## Safety

1. **`dbx query` is read-only by default.** Non-dangerous writes need `--allow-writes`; dangerous SQL (`DROP`, `TRUNCATE`, `ALTER`) needs `--allow-writes` **and** `--allow-dangerous-sql`. Add these only when the user explicitly asks for a write — never for reads.
2. Use `--json` for stable machine-readable output; `--format csv` when piping into other tools.
3. Bound big queries with `--limit <n>` and `--timeout <duration>` (`500ms`, `10s`, `1m`).

## When something fails

Read [references/troubleshooting.md](references/troubleshooting.md) — error codes, desktop-bridge issues, fixes.
