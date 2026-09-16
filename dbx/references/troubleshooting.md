# DBX — troubleshooting

Read this only when a command fails or its output looks wrong.

## Read the failure correctly

DBX reports failures in two envelopes, and success is never just "stdout had text":

| Situation | Where it lands | Shape |
|---|---|---|
| Option/argument/notes-file problem, and most runtime failures | stderr | `Error [CODE]: message` |
| Failure while `--json` was requested | stdout | `{"error":{"code":"…","message":"…"}}` |

Both exit non-zero. So check the exit code first, then parse `error.code` (JSON) or the bracketed code (stderr). A `--json` run that hits a database error still prints well-formed JSON — it is the `error` object that marks it as a failure, not the shape of the output.

## Error codes

| Code | Meaning |
|---|---|
| `UNKNOWN_OPTION` | an unsupported flag was provided |
| `INVALID_OPTION` | a flag is missing a value or has an invalid value — also raised when `--allow-dangerous-sql` is used without `--allow-writes` |
| `INVALID_ARGUMENT` | positional arguments are missing or conflicting |
| `CONNECTION_STORE_ERROR` | connection storage exists but could not be read |
| `CONNECTION_NOT_FOUND` | no DBX connection matched the requested name |
| `SQL_BLOCKED` | SQL safety rules blocked execution |
| `DBX_NOT_RUNNING` | DBX Desktop bridge is unavailable |
| `NOTES_INVALID` | a `--notes` file is missing, unparseable, or the wrong shape |
| `WRITE_FAILED` | an output file could not be written |
| `EXPORT_FAILED` | a `dbml` / `docs` export failed |
| `QUERY_ERROR` | reserved for query failure inside the database; current builds report those as `ERROR` |
| `ERROR` | unexpected runtime failure — for queries, carries the database's own message |

## Fixes

- `dbx: command not found` → not installed; tell the user: `npm i -g @dbx-app/cli` (or Homebrew `brew install dbx-cli`; standalone native binaries in GitHub releases — see README.md).
- `DBX_NOT_RUNNING` → the database type needs the DBX Desktop bridge and Desktop isn't running; tell the user to start DBX Desktop. Direct execution without Desktop covers `connections list`, `schema list`, `schema describe`, `query`, and `context`, for PostgreSQL/Redshift, MySQL-compatible, and SQLite only — check `dbx capabilities`.
- `CONNECTION_NOT_FOUND` → re-read `dbx connections list --json` and use the exact `name`; connections are created in DBX Desktop, so offer that rather than inventing a connection.
- `SQL_BLOCKED` → the statement is a write and no opt-in flag was passed. If the user explicitly asked for the write, show them the statement and re-run with `--allow-writes` (plus `--allow-dangerous-sql` for `DROP`/`TRUNCATE`/`ALTER`). Otherwise rewrite the statement as a read.
- `ERROR` with `permission denied for table …` → the connection's database user lacks the grant. This is a database-side fact, not a CLI flag; report it and stop retrying.
- `NOTES_INVALID` → `--notes` wants **JSON**, not Markdown, with `formatVersion` set (`1` on current builds). Each error names the offending field — the expected shapes are in [commands.md](commands.md#notes-files). A "references a table or column that no longer exists" line is a warning, not a failure, and the notes file is left untouched.
- `WRITE_FAILED` / `EXPORT_FAILED` → the `--out` path is unwritable (missing directory, no permission, path is a directory). Create the directory first or pick another path.
- `INVALID_ARGUMENT` / `UNKNOWN_OPTION` → the usage line printed with the message is authoritative; compare against [commands.md](commands.md) before retrying.
- Optional platform package missing → reinstall without `--no-optional`:
  ```bash
  npm uninstall -g @dbx-app/cli
  npm install -g @dbx-app/cli
  ```

## Output that looks wrong

- Query rows look short → `row_count` equals your `--limit`; the result was capped. Add `ORDER BY` plus a `WHERE` bound.
- A schema dump is missing tables → for `context`, check `"truncated"` in the JSON form; the text form does not report it. Raise `--max-tables`.
- `dbml` output has no `Ref` blocks or no `Note:` lines → the run warned that the database reports no foreign-key metadata or no comments (SQLite always warns about both). Supply descriptions through `--notes`.
- `--tables` seemed ignored → an unmatched name is not an error; open the produced file and confirm the tables you asked for are in it.
- `dbx docs` flooded the terminal → `--out` was omitted and the HTML document went to stdout. Re-run with `--out`.
