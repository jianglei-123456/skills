# codegraph — code intelligence for AI agents

Wraps the **read-only** CLI of [CodeGraph](https://github.com/colbymchenry/codegraph) (`@colbymchenry/codegraph`) for AI coding agents: symbol search, source with call paths, change-impact analysis, affected tests — pure bash, no MCP. The agent-facing instructions live in [SKILL.md](SKILL.md); this file is for humans.

## Install (human step)

```bash
npm i -g @colbymchenry/codegraph
codegraph --version
```

The npm package ships a per-platform bundle with a vendored Node runtime — no separate Node.js install required. Alternatives: standalone installer (`curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh` on macOS/Linux; the `install.ps1` equivalent on Windows), or `npx @colbymchenry/codegraph`.

Caveats: Node ≥ 25 is hard-blocked by the CLI (override `CODEGRAPH_ALLOW_UNSAFE_NODE=1`); Windows↔WSL shared working trees need `CODEGRAPH_DIR` to give each OS its own index.

## Index a project (human step — agents never do this)

```bash
cd <project> && codegraph init
```

Creates `.codegraph/` in the project root (self-gitignored; contains `codegraph.db`, the index). A project counts as indexed once `codegraph.db` exists. Optional project-root `codegraph.json` tunes `include` / `exclude` / `extensions` — re-index after changing it.

## What agents run (read-only)

See [SKILL.md](SKILL.md) for the full reference: `status`, `explore`, `query`, `node`, `callers`, `callees`, `impact`, `affected`, `files`, `--version`. Everything else (`init`, `index`, `sync`, `install`, …) is human-only.

## Telemetry

Anonymous; records subcommand names only, never code or queries. Disable with `CODEGRAPH_TELEMETRY=0` or `DO_NOT_TRACK=1`.
