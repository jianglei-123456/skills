# dbx — database access for AI agents

Wraps the [DBX CLI](https://github.com/t8y2/dbx) (`@dbx-app/cli`) for AI coding agents: named database connections, schema inspection, safe queries, prompt-ready schema context — pure bash, no MCP. The agent-facing instructions live in [SKILL.md](SKILL.md); this file is for humans.

## Install (human step)

```bash
npm install -g @dbx-app/cli
```

Node.js 18.18.0+ is needed only for the npm launcher; the native CLI ships per-platform and needs no Node.js.

Alternatives:

- Homebrew: `brew tap t8y2/tap && brew install dbx-cli`
- Standalone native binaries from the `packages-v*` GitHub Release (`dbx-cli-darwin-{arm64,x64}.tar.gz`, `dbx-cli-linux-{arm64,x64}-gnu.tar.gz`, `dbx-cli-win32-{arm64,x64}.zip`) — verify with `CLI-SHA256SUMS`, extract, run `./dbx`. Set `DBX_DATA_DIR` when using a custom or portable data directory.

## Add a connection (human step — agents never do this)

Connections are created in DBX Desktop. Agents only use connection names that already exist (`dbx connections list`). To omit the connection name on query/context commands, set `DBX_CONNECTION`.

## What agents run (read-only by default)

See [SKILL.md](SKILL.md) for the quick reference; full command syntax lives in [references/commands.md](references/commands.md): `doctor`, `capabilities`, `connections list`, `schema list`, `schema describe`, `query`, `context`, `open`. Writes require explicit opt-in flags (`--allow-writes`, `--allow-dangerous-sql`).
