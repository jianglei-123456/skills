# DBX — troubleshooting

Read this file only when a command fails or its output looks wrong.

## Error codes (JSON errors use stable codes)

| Code | Meaning |
|---|---|
| `UNKNOWN_OPTION` | an unsupported flag was provided |
| `INVALID_OPTION` | a flag is missing a value or has an invalid value |
| `INVALID_ARGUMENT` | positional arguments are missing or conflicting |
| `CONNECTION_STORE_ERROR` | connection storage exists but could not be read |
| `CONNECTION_NOT_FOUND` | no DBX connection matched the requested name |
| `SQL_BLOCKED` | SQL safety rules blocked execution |
| `DBX_NOT_RUNNING` | DBX Desktop bridge is unavailable |
| `ERROR` | unexpected runtime failure |

## Fixes

- `dbx: command not found` → not installed; tell the user: `npm i -g @dbx-app/cli` (or Homebrew `brew install dbx-cli`; standalone native binaries in GitHub releases — see README.md).
- `DBX_NOT_RUNNING` → the database type needs the DBX Desktop bridge but Desktop isn't running; tell the user to start DBX Desktop. Direct execution (no Desktop) covers PostgreSQL/Redshift, MySQL-compatible, SQLite.
- Optional platform package missing → reinstall without `--no-optional`:
  ```bash
  npm uninstall -g @dbx-app/cli
  npm install -g @dbx-app/cli
  ```
- `SQL_BLOCKED` → safety rules blocked the statement; rewrite it, or — only if the user explicitly asked for the write — use the write flags in `references/commands.md`.
