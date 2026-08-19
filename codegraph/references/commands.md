# CodeGraph commands — full reference

Detail layer for the codegraph skill. Read this file only when you need a command's exact syntax, options, or output-format details (e.g. `--json`, `--limit`, `--depth`, `--filter`, `--stdin`, pipe usage). The one-line form of every command lives in `SKILL.md`.

All commands are **read-only**. Use `--path <dir>` when the `.codegraph/` root is not your current directory.

## status — index state (run first, always)

```bash
codegraph status          # text summary
codegraph status --json   # machine-readable
```

Reports index freshness: `lastIndexed`, `pendingChanges` (added/modified/removed), `reindexRecommended`. If the index looks stale, note it in your reply and suggest the user re-sync — do not reindex yourself.

## explore — one-shot answer to a whole question (preferred)

```bash
codegraph explore "how does authentication flow from login to session?" [--path <p>] [--max-files <n>]
```

Returns verbatim, line-numbered source of the relevant symbols grouped by file, a `**Flow**` call-path section (including dynamic-dispatch hops), and a `**Blast radius**` summary. Treat the returned source as already read — do not re-read or grep the same files.

## query — symbol search

```bash
codegraph query <search> [--limit <n>] [--kind <kind>] [--json]
```

Ranked list of matching symbols (default limit 10; no source bodies). Use it to find the exact name/location of a symbol.

## node — deep dive into one symbol, or read a file

```bash
codegraph node <name>                                  # body + caller/callee trail
codegraph node --file <path> [--offset <n>] [--limit <n>]  # read a file, line-numbered, with dependents
codegraph node <name> --symbols-only
```

## callers / callees — dependency navigation

```bash
codegraph callers <symbol> [--limit <n>] [--json]   # who calls it
codegraph callees <symbol> [--limit <n>] [--json]   # what it calls
```

## impact — change analysis

```bash
codegraph impact <symbol> [--depth <n>] [--json]    # default depth 2, clamped 1–10
```

## affected — tests hit by a change

```bash
codegraph affected <changed-file>... [--depth <n>] [--filter <glob>] [--quiet]
git diff --name-only | codegraph affected --stdin   # pipe changed files
```

## files — structure overview

```bash
codegraph files [--format tree|flat|grouped] [--filter <dir>] [--pattern <glob>] [--max-depth <n>] [--json]
```

## version

```bash
codegraph --version
```
