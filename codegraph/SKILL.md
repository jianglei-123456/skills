---
name: codegraph
description: "Code intelligence via the codegraph CLI. Use when the project has a .codegraph/ directory (a prebuilt code-intelligence index) and you need to explore code — find symbols, read source with call paths, trace callers/callees, assess change impact, or find affected tests — faster than grep/read loops. Read-only commands only; never initializes or reindexes. Gate: no .codegraph/ → skill does not apply."
---

# CodeGraph — explore code through its prebuilt index

## When to use

Use it whenever the project contains a `.codegraph/` directory — a prebuilt code-intelligence index (SQLite at `.codegraph/codegraph.db`): explore symbols, call paths, change impact, affected tests — instead of blind grep/read loops.

**Gate — check first:** no `.codegraph/` → stop; tell the user the project is not indexed. Never run `codegraph init` / `index` / `sync` — indexing is the user's decision.

## Start (every session)

1. **Verify once:** `codegraph --version` — if not installed, tell the user (`npm i -g @colbymchenry/codegraph`); do not install it yourself.
2. **`codegraph status`** — reports index freshness (`lastIndexed`, `pendingChanges`, `reindexRecommended`). Stale → note it and suggest the user re-sync; do not reindex yourself.
3. **Pick a command** from the quick reference below.

## Command quick reference

One-line form per command. `explore` is preferred for whole questions. Need exact syntax, options (`--limit`, `--json`, `--depth`, `--filter`, `--stdin`, …), or output-format details? Read [references/commands.md](references/commands.md).

| Goal | Command |
|---|---|
| "How does X work?" / "what happens if I change X?" | `codegraph explore "<question>"` |
| Find a symbol's exact name/location | `codegraph query <search>` |
| Full body + call trail of one symbol, or read a file | `codegraph node <name>` / `codegraph node --file <path>` |
| Who calls X / what X calls | `codegraph callers <sym>` / `codegraph callees <sym>` |
| Blast radius of changing a symbol | `codegraph impact <sym>` |
| Which tests are affected by changed files | `codegraph affected <file>...` |
| Codebase structure overview | `codegraph files` |

`explore` returns line-numbered source + a `**Flow**` call-path section + a `**Blast radius**` summary in one shot — treat its output as already read, do not re-read or grep the same files.

## Hard rules

1. **Read-only retrieval only:** never run write/maintenance commands (`install`, `uninstall`, `init`, `uninit`, `index`, `sync`, `unlock`, `upgrade`, `telemetry`, `daemon`, `serve --mcp`, `prompt-hook`).
2. Never modify `.codegraph/` or a project-root `codegraph.json` (user-managed config; edits require the user to re-index).
3. Output is already formatted context — don't re-verify it with grep/read; narrow big outputs with `--limit`, `--path`, `--max-files`, or a more specific query.

## When something fails

Read [references/troubleshooting.md](references/troubleshooting.md).
