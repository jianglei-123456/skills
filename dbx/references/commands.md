# DBX commands — full reference

Detail layer for the dbx skill: every command, every flag, every output mode. The one-line form of each command lives in `SKILL.md`; exact output shapes live in [outputs.md](outputs.md).

`<conn>` is a connection name from `dbx connections list`. Every command also accepts the `DBX_CONNECTION` environment variable in place of `<conn>` (see [Default connection](#default-connection)).

## Common options

| Option | Applies to | Meaning |
|---|---|---|
| `--json` | all commands | Stable machine-readable JSON. Equivalent to `--format json` on `query`. |
| `--format csv` | `connections list`, `schema list`, `schema describe`, `query` | CSV for piping. Not supported by `context`, `dbml`, `docs`. |
| `--schema <name>` | `schema list`, `schema describe`, `context`, `dbml`, `docs`, `open` | Restrict to one database schema (PostgreSQL/Redshift). |
| `--database <name>` | `dbml`, `docs`, `open` | Label the target database. |
| `--tables a,b` | `context`, `dbml`, `docs` | Restrict to a comma-separated table list. No spaces after commas. |

Errors go to stderr, or into a JSON `error` object under `--json`, always with a non-zero exit. See [outputs.md](outputs.md#errors) for both envelopes.

## doctor — health check

```bash
dbx doctor
dbx doctor --json
```

Reports the connection store path, how many connections loaded, whether the native SQLite loader works, the desktop bridge port file and URL, plus the `directQueryTypes` / `bridgeRequiredTypes` lists. Run this first in a session.

## capabilities — what runs without DBX Desktop

```bash
dbx capabilities
dbx capabilities --json
```

The `directQueryTypes` / `bridgeRequiredTypes` split without the rest of the diagnostics. On a current build, direct query covers `postgres`, `redshift`, `mysql`, `doris`, `starrocks`, `manticoresearch`, `sqlite`, `rqlite`, `kwdb`, `questdb`; everything else needs the Desktop bridge — read the live list instead of hard-coding it, since it grows.

## connections list — no secrets printed

```bash
dbx connections list --json
dbx connections list --format csv
```

Prints name, type, host, port, database — never passwords. Use the exact `name` values as `<conn>`.

## schema list — tables and views

```bash
dbx schema list <conn> --json
dbx schema list <conn> --schema public --json
```

## schema describe — columns of one table

```bash
dbx schema describe <conn> <table> --json
dbx schema describe <conn> <table> --schema public --json
```

Each column carries `data_type`, `is_nullable`, `column_default`, `is_primary_key`, `is_unique`, `extra`, `comment`, `numeric_precision`, `numeric_scale`, `character_maximum_length` (field-by-field example in [outputs.md](outputs.md#schema-describe)).

Qualify with `--schema` when the table name exists in more than one schema.

## query — one SQL statement

```bash
dbx query <conn> "<sql>" --json
dbx query <conn> "<sql>" --format csv
dbx query <conn> "<sql>" --limit 50 --timeout 10s --json
dbx query <conn> --file ./query.sql --json
```

With `DBX_CONNECTION` set, drop the connection name: `dbx query --file ./query.sql --json`.

| Option | Meaning |
|---|---|
| `--limit <n>` | Cap returned rows. `row_count` reports what came back, so a full page means the result may be truncated — narrow the query with `WHERE` or `ORDER BY … LIMIT` instead of trusting a big page. |
| `--timeout <duration>` | `ms`, `s`, or `m` — `500ms`, `10s`, `1m`. |
| `--file <path>` | Read the SQL from a file. Use this for multi-line SQL; it avoids quoting problems in shell strings. |
| `--allow-writes` | Permit non-dangerous writes (`INSERT`, `UPDATE`, `DELETE`). |
| `--allow-dangerous-sql` | Permit `DROP`, `TRUNCATE`, `ALTER`. **Requires `--allow-writes` too**, otherwise the call fails with `INVALID_OPTION`. |

**Read-only by default.** A write without `--allow-writes` fails with `SQL_BLOCKED`. Safe to retry with fewer rows: binding `--limit` is not a security control, it only trims the response.

SQL starting with a dash: pass `--` before the SQL.

```bash
dbx query local --json -- "-- comment
select 1"
```

One statement per call.

## context — prompt-ready schema

```bash
dbx context <conn>
dbx context <conn> --tables users,orders
dbx context <conn> --tables users,orders --max-tables 5 --json
dbx context <conn> --schema public --tables users
```

Prints a compact schema — table name, type, then `- column type NULL/NOT NULL PK` lines — ready to feed into a prompt. Without `--json` this is the most token-efficient way to hand a schema to a downstream agent.

`--max-tables <n>` caps how many tables are included. **The cap is silent in the text form**: the JSON output carries `"truncated": true`, the plain text does not. Before trusting a schema dump, check that flag (or raise `--max-tables`) — otherwise you reason about a partial schema.

## dbml — DBML model file

```bash
dbx dbml <conn> --out ./model.dbml
dbx dbml <conn> --tables c_machine,orders --out ./model.dbml
dbx dbml <conn> --schema public --database machine --tables c_machine --out ./model.dbml
dbx dbml <conn> --notes ./notes.json --out ./model.dbml
```

Writes a [DBML](https://dbml.dbdiagram.io/) file: `Project`, `Table` blocks with columns, flags (`pk`, `not null`, `unique`), `Indexes`, and `Ref` blocks for derived foreign keys.

| Option | Meaning |
|---|---|
| `--out <path>` | Output file. **Omit it and the DBML is printed to stdout** and nothing is written. |
| `--notes <path>` | JSON annotation file merged into the model — see [notes files](#notes-files). |
| `--tables a,b` | Restrict to these tables. Keys may be schema-qualified (`public.c_machine`). |
| `--schema`, `--database` | Restrict the schema / label the database. |

Prints `Wrote <n> bytes to <path>` on success, plus `warning:` lines on stderr when the database cannot supply comments or foreign keys (SQLite always warns about both). Treat those warnings as a signal that descriptions must come from `--notes`. Notes land as `Note: '…'` lines for the project, groups, and tables, and inline on the column (`title varchar(1024) [not null, note: '…']`).

An unknown table name in `--tables` is **not** an error: you get a model with the matched tables only, so verify the tables actually landed in the output.

## docs — standalone HTML data dictionary

```bash
dbx docs <conn> --out ./docs.html
dbx docs <conn> --tables c_machine,orders --lang zh-CN --out ./docs.html
dbx docs <conn> --notes ./notes.json --database machine --out ./docs.html
```

Writes one self-contained HTML file (hundreds of KB: embedded CSS, JS, and fonts) with a searchable, groupable data dictionary — tables, columns, indexes, references, enums, and warnings. `--lang` sets the UI language (`en`, `zh-CN`, `zh-TW`, …).

**`--out` behaves differently here than elsewhere:** omit it and the whole HTML document is written to stdout. Always pass `--out` when the output is going anywhere near an agent's context — a missing `--out` dumps hundreds of kilobytes of markup into the conversation. `--json` is ignored by this command.

## open — DBX Desktop

```bash
dbx open <conn> <table>
dbx open <conn> <table> --schema public --json
```

Opens the table in DBX Desktop. Requires Desktop running; there is nothing useful to do with the result beyond confirming `{"opened": true, …}`. Only run it when the user asked for the table to be opened.

## Notes files

`--notes` takes a JSON file, not Markdown — a Markdown file fails with `NOTES_INVALID`. Supply `formatVersion` (`1` on current builds) and describe what the database itself cannot: table and column descriptions, and table groups. All keys are optional except `formatVersion`.

```json
{
  "formatVersion": 1,
  "project": { "note": "What this database is for." },
  "groups": [
    { "id": "core", "name": "Core", "hue": 210, "note": "Transactional core tables." }
  ],
  "tables": {
    "book": {
      "group": "core",
      "note": "One row per book.",
      "columns": { "title": { "note": "Display title." } }
    },
    "public.c_machine": { "note": "Schema-qualify the key when schemas repeat table names." }
  }
}
```

Shape rules, all enforced with a `NOTES_INVALID` error naming the offending field:

- Top level: `formatVersion`, `project`, `groups`, `tables` only.
- `groups` is an **array**; each entry takes `id`, `name`, `hue`, `note`. There is no `color` field — the DBML `[color: …]` line is derived from `hue`.
- `tables` is an **object keyed by table name** (or `schema.table`), not an array.
- Each table entry takes `group`, `note`, `columns`; each column entry is an object (`{"note": …}`), not a bare string.
- Notes that name a table or column that no longer exists produce a `warning:` and are kept, not deleted — safe to re-run.

`formatVersion` mismatches fail loudly with the supported version in the message.

## Default connection

Set `DBX_CONNECTION` to omit the connection name on `query` and `context`:

```bash
DBX_CONNECTION=local dbx query "select 1" --json
DBX_CONNECTION=local dbx context --tables users,orders
```

PowerShell: `$env:DBX_CONNECTION='local'`. `DBX_DATA_DIR` points the CLI at a custom or portable connection store.

## Without DBX Desktop

Direct execution (no desktop bridge) covers `connections list`, `schema list`, `schema describe`, `query`, and `context`, for PostgreSQL/Redshift, MySQL-compatible (MySQL, Doris, StarRocks), and SQLite. Every other database type — `dbml`, `docs`, and `open` included where they need metadata the bridge supplies — needs the DBX Desktop bridge. Check `dbx capabilities` and `dbx doctor` rather than assuming.
