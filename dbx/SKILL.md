---
name: dbx
description: "Database access via the dbx CLI. Use when the user needs database work — run SQL queries, inspect tables or schemas, list connections, generate DBML or HTML schema docs — against databases preconfigured in DBX (PostgreSQL/Redshift, MySQL-compatible, SQLite, …). Read-only by default; writes require explicit opt-in flags. Gate: dbx CLI not installed → tell the user, do not install."
---

# DBX — query databases through preconfigured connections

## When to use

DBX stores named connections to databases (PostgreSQL/Redshift, MySQL-compatible, SQLite, and — through DBX Desktop — many more). Use it whenever the user needs database work that a DBX connection can serve: run SQL, inspect tables or columns, list connections, or export schema documentation.

**Gate — check first:** `dbx --version` must run. If `dbx: command not found`, tell the user to install (see README.md) — do not install it yourself. If the connection the user names is not in `dbx connections list`, tell them — connections are created in DBX Desktop, not by the agent.

## Start (every session)

1. **Verify:** `dbx doctor` — confirms the CLI, connection store, and native SQLite loader are available.
2. **Find the connection:** `dbx connections list --json` — take the exact `name` (a default can be set via `DBX_CONNECTION`, see [references/commands.md](references/commands.md#default-connection)).
3. **Inspect the schema first:** `dbx schema list <conn>` then `dbx schema describe <conn> <table>` — know the tables and columns before writing a query.
4. **Query:** `dbx query <conn> "<sql>" --json`.

## Command quick reference

| Goal | Command |
|---|---|
| Check CLI / desktop bridge health | `dbx doctor` |
| See which database types need DBX Desktop | `dbx capabilities` |
| List connections (no secrets) | `dbx connections list` |
| List tables and views | `dbx schema list <conn>` |
| Show table columns | `dbx schema describe <conn> <table>` |
| Run one SQL statement | `dbx query <conn> "<sql>"` |
| Run SQL from a file | `dbx query <conn> --file ./query.sql` |
| Compact schema context for prompts | `dbx context <conn>` |
| Restrict any of the above to one schema | add `--schema <name>` |
| Generate a DBML model file | `dbx dbml <conn> --out ./model.dbml` |
| Generate an HTML data dictionary | `dbx docs <conn> --out ./docs.html` |
| Open a table in DBX Desktop | `dbx open <conn> <table>` |

Full syntax and every flag: [references/commands.md](references/commands.md). JSON field names and error envelopes: [references/outputs.md](references/outputs.md).

## Safety and parsing

1. **`dbx query` is read-only by default.** Non-dangerous writes need `--allow-writes`; dangerous SQL (`DROP`, `TRUNCATE`, `ALTER`) needs `--allow-writes` **and** `--allow-dangerous-sql`. Add these only when the user explicitly asks for a write — show them the statement first, then run it. Never for reads.
2. **`--json` is the parsing contract**, not guesswork: result rows are objects keyed by column name, `columns` gives the order, `row_count` is rows returned. When `row_count` equals your `--limit`, the result was likely cut short — bound the query in SQL instead of paging blindly.
3. **Bound big queries** with `--limit <n>` and `--timeout <duration>` (`500ms`, `10s`, `1m`).
4. **Watch for silent truncation:** `dbx context` caps tables and only the JSON form reports `"truncated": true`. Check the flag or raise `--max-tables` before treating a schema dump as complete.
5. **Always pass `--out` to `dbx docs`:** without it the whole HTML document goes to stdout — hundreds of KB into the conversation. `dbx dbml` without `--out` prints DBML text to stdout, which is usually what you want.

## When something fails

A failure is reported on stderr as `Error [CODE]: message`, or under `--json` as `{"error":{"code":…,"message":…}}` — in both cases the exit code is non-zero, so never treat stdout without checking the exit. Read [references/troubleshooting.md](references/troubleshooting.md) for the code table, the desktop-bridge cases, and fixes.
