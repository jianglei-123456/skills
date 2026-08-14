---
name: codegraph
description: Code intelligence via the codegraph CLI. Use when the project contains a .codegraph/ directory (a prebuilt code-intelligence index) and you need to explore code — find symbols, read relevant source with call paths, trace callers/callees, assess change impact, or find affected tests — faster than grep/read loops. Runs only read-only bash commands (explore, query, node, callers, callees, impact, affected, files, status). Does NOT apply to projects without .codegraph/ and never initializes or reindexes.
---

# CodeGraph — explore code through its prebuilt index

## When to use this skill

Use it whenever the current project contains a `.codegraph/` directory — a prebuilt code-intelligence index (SQLite at `.codegraph/codegraph.db`) created by the `codegraph` CLI. It is ideal for:

- Understanding what a symbol does and how it is used (callers/callees, call paths).
- Answering questions like "how does X work?" or "what happens if I change X?" (`explore`, `impact`).
- Finding tests affected by a change (`affected`).
- Locating symbols and files without blind grepping (`query`, `files`, `explore`).

**Hard gate — check first:** if the project has no `.codegraph/` directory, this skill does NOT apply. Stop and tell the user the project is not indexed; they can run `codegraph init` themselves. **Never run `codegraph init`, `index`, or `sync` on your own** — indexing is the user's decision.

## Verify prerequisites (once, before the first command)

```bash
codegraph --version     # CLI installed? (install: npm i -g @colbymchenry/codegraph)
codegraph status        # index present? (fails with a clear message if not)
```

If `codegraph` is not installed, tell the user — do not install it yourself.

## Start with status (always)

```bash
codegraph status          # text summary
codegraph status --json   # machine-readable
```

`status` reports index freshness: `lastIndexed`, `pendingChanges` (added/modified/removed), `reindexRecommended`. If the index looks stale, note it in your reply and suggest the user re-sync — **do not reindex yourself**.

## Command reference (read-only retrieval only)

All commands below are read-only. Use `--path <dir>` when the `.codegraph/` root is not your current directory.

### explore — one-shot answer to a whole question (preferred)

```bash
codegraph explore "how does authentication flow from login to session?" [--path <p>] [--max-files <n>]
```

Returns verbatim, line-numbered source of the relevant symbols grouped by file, a `**Flow**` call-path section (including dynamic-dispatch hops), and a `**Blast radius**` summary. Treat the returned source as already read — do not re-read or grep the same files.

### query — symbol search

```bash
codegraph query <search> [--limit <n>] [--kind <kind>] [--json]
```

Ranked list of matching symbols (default limit 10; no source bodies). Use it to find the exact name/location of a symbol.

### node — deep dive into one symbol, or read a file

```bash
codegraph node <name>                                  # body + caller/callee trail
codegraph node --file <path> [--offset <n>] [--limit <n>]  # read a file, line-numbered, with dependents
codegraph node <name> --symbols-only
```

### callers / callees — dependency navigation

```bash
codegraph callers <symbol> [--limit <n>] [--json]   # who calls it
codegraph callees <symbol> [--limit <n>] [--json]   # what it calls
```

### impact — change analysis

```bash
codegraph impact <symbol> [--depth <n>] [--json]    # default depth 2, clamped 1–10
```

### affected — tests hit by a change

```bash
codegraph affected <changed-file>... [--depth <n>] [--filter <glob>] [--quiet]
git diff --name-only | codegraph affected --stdin   # pipe changed files
```

### files — structure overview

```bash
codegraph files [--format tree|flat|grouped] [--filter <dir>] [--pattern <glob>] [--max-depth <n>] [--json]
```

### version

```bash
codegraph --version
```

## Choosing the right command

| Goal | Command |
|---|---|
| "How does X work?" / "what happens if I change X?" | `explore` |
| Find a symbol's exact name/location | `query` |
| Full body + call trail of one symbol, or read a file | `node` |
| Who calls X / what X calls | `callers` / `callees` |
| Blast radius of changing a symbol | `impact` |
| Which tests are affected by changed files | `affected` |
| Codebase structure overview | `files` |

## Hard rules

1. **Never run write/maintenance commands:** `install`, `uninstall`, `init`, `uninit`, `index`, `sync`, `unlock`, `upgrade`, `telemetry on|off`, `daemon`, `serve --mcp`, `prompt-hook`. The agent's job is retrieval only.
2. Never modify `.codegraph/` or a project-root `codegraph.json` (user-managed config; changing `include`/`exclude`/`extensions` requires the user to re-index).
3. Output is already formatted context. Don't re-verify it with grep/read unless the task genuinely needs to; don't dump huge outputs — narrow with `--limit`, `--path`, `--max-files`, or a more specific query.
4. Use `--json` when you need machine-readable data for further processing.

## Troubleshooting

- `codegraph: command not found` → not installed; tell the user (`npm i -g @colbymchenry/codegraph`).
- "not indexed" error → `.codegraph/` is missing; tell the user, do not run `init`.
- Missing output sections (e.g. no Flow/Relationships) → output is budget-gated; on large repos `Relationships` appears only above ~500 indexed files. Narrow your query.
- Node ≥ 25 hard-block → user-side issue (`CODEGRAPH_ALLOW_UNSAFE_NODE=1` override exists); not something the agent fixes.
- Telemetry: anonymous, subcommand names only; users can disable with `CODEGRAPH_TELEMETRY=0` — agents do not run `telemetry off`.
