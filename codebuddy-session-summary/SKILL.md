---
name: codebuddy会话总结
description: "Summarize past CodeBuddy coding sessions — what was developed on a given date range, recent work history across projects. Use when the user asks to 总结/回顾/查询 what they built over the last days (e.g. \"总结下18,19,20这三天都开发了什么东西\"), or wants a digest of their session history. Reads CodeBuddy session transcripts at ~/.codebuddy/projects/*/*.jsonl, extracts AI titles and first user messages, groups by day. Gate: no .jsonl transcripts under the root → skill does not apply."
---

# CodeBuddy 会话总结 — reconstruct what was built from session transcripts

## When to use

Use it when the user wants a digest of their own past coding sessions: what was developed on a given day or range of days, across projects. The transcripts live at `~/.codebuddy/projects/<project>/*.jsonl` — one file per session, one JSON per line, with `ai-title` records carrying the AI-generated session title.

**Gate — check first:** the transcripts root must contain `*.jsonl` files. If not, stop and tell the user no session history was found; never invent content.

## Start (every run)

1. **Fix the date range.** User gave dates → use them. No range → default to the last 3 days (`--days 3`) and say so. `--until` defaults to now.
2. **Run the extractor:**

   ```bash
   python "E:/Dev/jianglei/skills/codebuddy-session-summary/scripts/summarize_sessions.py" \
     --since YYYY-MM-DD --until YYYY-MM-DD
   ```

   Optional: `--root <dir>` for a non-default transcripts root, `--project <name>` to filter one project (matches the directory name).
3. **Summarize.** Group the per-session lines by day, one line each — `HH:MM [project] title — what it was about` (use the first user message when the title alone is vague). If the user asked for a review, connect related sessions across projects into short storylines; a bare "what did I build" gets a plain grouped list.

## Completion criteria

- Every session file in the range is listed — none silently skipped (count the files: `find <root> -maxdepth 2 -name '*.jsonl'` within the range must match the output).
- The summary is grouped by day and uses the user's language; titles stay verbatim.
