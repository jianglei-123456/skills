# DBX commands — full reference

Detail layer for the dbx skill. Read this file only when you need a command's exact syntax, options, or output details. The one-line form of every command lives in `SKILL.md`.

## Common output options

- `--json` — stable machine-readable output (JSON).
- `--format csv` — for query, connection, and schema data piped into other command-line tools.
- Errors go to stderr and return a non-zero exit code.

## doctor / capabilities — health and support

```bash
dbx doctor          # local config + desktop bridge diagnostics
dbx capabilities    # which database types are direct-query vs bridge-required
```

## connections list — no secrets printed

```bash
dbx connections list --json
dbx connections list --format csv
```

## schema — inspect before querying

```bash
dbx schema list <connection> --json                 # tables and views
dbx schema describe <connection> <table> --json     # table columns
```

## query — one SQL statement

```bash
dbx query <connection> "<sql>" --json
dbx query <connection> "<sql>" --format csv
dbx query <connection> "select * from users" --limit 50 --timeout 10s --json
dbx query <connection> --file ./query.sql --json
```

Read-only by default. `--limit <n>` controls returned rows; `--timeout <duration>` accepts `ms`/`s`/`m` (`500ms`, `10s`, `1m`).

**Writes:** non-dangerous statements need `--allow-writes`; dangerous SQL (`DROP`, `TRUNCATE`, `ALTER`) needs `--allow-writes` **and** `--allow-dangerous-sql`.

SQL starting with a dash: pass `--` before the SQL:

```bash
dbx query local --json -- "-- comment
select 1"
```

## context — prompt-ready schema

```bash
dbx context <connection>                        # all tables
dbx context <connection> --tables users,orders  # selected tables
```

Prints a compact schema context ready to feed into prompts.

## open — DBX Desktop

```bash
dbx open <connection> <table>
```

## Default connection

Set `DBX_CONNECTION` to omit the connection name:

```bash
DBX_CONNECTION=local dbx query "select 1" --json
DBX_CONNECTION=local dbx context --tables users,orders
```

## Without DBX Desktop

Direct execution (no desktop bridge) covers: `connections list`, `schema list`, `schema describe`, `query`, `context`. Direct database support: PostgreSQL/Redshift, MySQL-compatible (MySQL, Doris, StarRocks), SQLite. Other database types need the DBX Desktop bridge / Agent / JDBC — check `dbx capabilities`.
