# CodeGraph — troubleshooting

Read this file only when a command fails or its output looks wrong.

- `codegraph: command not found` → not installed; tell the user (`npm i -g @colbymchenry/codegraph`).
- "not indexed" error → `.codegraph/` is missing; tell the user, do not run `init`.
- Missing output sections (e.g. no Flow/Relationships) → output is budget-gated; on large repos `Relationships` appears only above ~500 indexed files. Narrow your query.
- Node ≥ 25 hard-block → user-side issue (`CODEGRAPH_ALLOW_UNSAFE_NODE=1` override exists); not something the agent fixes.
- Telemetry: anonymous, subcommand names only; users can disable with `CODEGRAPH_TELEMETRY=0` — agents do not run `telemetry off`.
