#!/usr/bin/env python3
"""Extract CodeBuddy session digests: title + first user message per session.

Finds *.jsonl session transcripts under <root>/*/, filters by file mtime,
extracts the AI-generated title (type="ai-title") and the first real user
message, prints one block per session sorted by time.

Usage:
  python summarize_sessions.py [--root ~/.codebuddy/projects]
                               [--since YYYY-MM-DD] [--until YYYY-MM-DD]
                               [--days N] [--project NAME]
"""

import argparse
import datetime
import glob
import json
import os
import sys

DEFAULT_ROOT = os.path.join(os.path.expanduser("~"), ".codebuddy", "projects")

# Windows pipes default stdout to the locale codepage (cp936), which mangles
# UTF-8 Chinese titles — force UTF-8 so output is stable across terminals.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=DEFAULT_ROOT,
                   help="transcripts root (default: %(default)s)")
    p.add_argument("--since", help="include files modified on/after YYYY-MM-DD")
    p.add_argument("--until", help="include files modified before YYYY-MM-DD (default: now)")
    p.add_argument("--days", type=int, help="shortcut: include the last N days")
    p.add_argument("--project", help="only sessions under a project directory matching NAME")
    return p.parse_args()


def parse_date(s):
    if not s:
        return None
    return datetime.datetime.strptime(s, "%Y-%m-%d")


def first_user_message(path):
    """Return the first non-trivial user message text from a session file."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if obj.get("type") == "message" and obj.get("role") == "user":
                parts = []
                for c in obj.get("content", []):
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "input_text":
                        parts.append(c.get("text", ""))
                    elif isinstance(c.get("text"), str):
                        parts.append(c["text"])
                txt = " ".join(p for p in parts if p).strip()
                # skip system-reminder-only messages
                if txt and "system-reminder" not in txt[:200]:
                    return " ".join(txt.split())[:300]
    return ""


def main():
    args = parse_args()
    since = parse_date(args.since)
    if args.days:
        since = datetime.datetime.now() - datetime.timedelta(days=args.days)
    until = parse_date(args.until) or datetime.datetime.now()

    files = []
    for path in sorted(glob.glob(os.path.join(args.root, "*", "*.jsonl"))):
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path))
        if since and mtime < since:
            continue
        if mtime >= until:
            continue
        project = os.path.basename(os.path.dirname(path))
        if args.project and args.project not in project:
            continue
        files.append((path, mtime, project))

    if not files:
        print(f"no session files found under {args.root}"
              + (f" matching project '{args.project}'" if args.project else "")
              + (f" between {since:%Y-%m-%d} and {until:%Y-%m-%d}" if since else ""),
              file=sys.stderr)
        sys.exit(1)

    files.sort(key=lambda x: x[1])
    for path, mtime, project in files:
        title = None
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    if obj.get("type") == "ai-title":
                        title = obj.get("aiTitle")
                        break
        except OSError as e:
            print(f"# [error reading {path}: {e}]", file=sys.stderr)
            continue
        msg = first_user_message(path)
        print(f"== {mtime:%Y-%m-%d %H:%M} [{project}] {os.path.basename(path)[:8]}")
        print(f"   title: {title}")
        if msg:
            print(f"   user : {msg}")
        print()


if __name__ == "__main__":
    main()
