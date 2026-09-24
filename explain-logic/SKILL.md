---
name: explain-logic
description: Explain one named piece of business logic by tracing only its own upstream and downstream chain, then presenting it as prose plus code and diagrams. Use when the user points at a specific rule, function, or flow and wants to understand it end to end. Invoke explicitly as /explain-logic <target>.
argument-hint: <business logic to explain>
disable-model-invocation: true
---

# explain-logic — explain one business chain, not the whole system

## When to use

Use when the user names **one** piece of business logic — a rule, a function, an operation such as "deduct inventory" — and wants to understand it end to end.

A system holds many businesses. This skill explains exactly one chain, and nothing else.

## Core rules

1. **Scope is the chain, not the repository.** Explain only the logic that was named.
2. **Confirm scope before explaining.** Show a scope sketch first and wait. Never explain before the boundary is agreed.
3. **Reading may overshoot; output may not.** Reading wider to find the chain's edges is fine. Anything judged to belong to another business stays out.
4. **Prefer code and diagrams to prose.** If a code block or a mermaid diagram can carry the point, use it. Never leave a section as pure prose.
5. **Every step has a location.** Every step resolves to a real `file:line`.

## Step 1 — Scope sketch

Find the chain's edges:

- **Upstream:** the natural entry — HTTP handler, queue consumer, scheduled job, `main`.
- **Downstream:** the natural terminus — database write, external call, response.
- If the user gave a boundary, use theirs verbatim.

Then present both and stop:

- A table: `Step | Location | Responsibility | Direction`
- A mermaid flowchart of the chain.

**Done when:** the user confirms the sketch or corrects it.

## Step 2 — Explanation

Five layers, in order. Skip one only when it genuinely does not apply.

1. **What it does** — 2–3 sentences a newcomer can follow.
2. **Key design decisions** — patterns, why these data structures, non-obvious algorithmic choices.
3. **Execution walkthrough** — the confirmed chain, step by step, with code.
4. **Edge cases and gotchas** — inputs that break it, side effects, what failure looks like.
5. **Changing it safely** — invariants that must hold, what breaks if a step changes.

## Reading rules

- Start at the named logic; expand outward one edge at a time, and only when the current node does not answer the question.
- Record every location opened; keep the excluded ones for the section below.
- If the project has `.codegraph/`, prefer it to locate and read the chain (`node`, `callers`, `callees`, `explore`). Otherwise read files directly.
  **Gate — check first:** never run `codegraph init`, `index`, or `sync` — indexing is the user's decision.

## Excluded reads

Only when non-empty. One terse line each:

`path or symbol — why read — why excluded`

## Common rationalizations

| Excuse | Rebuttal |
|---|---|
| "The whole flow is easier to explain at once" | That is the one thing the user asked you not to do. One chain. |
| "The boundary is obvious" | Business boundaries are semantic, not physical. Confirm the sketch. |
| "This other service is clearly related" | Related is not in scope. Record it, exclude it. |
| "Skip the gotchas, it is simple" | Skipping layer 4 is how changes break production. |

## Red flags

- Explaining logic the user did not name.
- Explaining before the sketch is confirmed.
- A section with no code and no diagram.
- A step with no `file:line`.

## Completion criteria

- A scope sketch was shown and confirmed before any explanation.
- Every step resolves to a real `file:line`.
- Layer 4 names at least one concrete gotcha.
- Code or a diagram appears wherever it can carry the point.
- Excluded reads are disclosed, or the section is absent.

## References

- [references/example.md](references/example.md) — one worked example: input → scope sketch → explanation.
