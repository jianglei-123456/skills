#!/usr/bin/env python3
"""Environment check for the DT cabin modify flow.

Checks (read-only, prints only PASS/FAIL status — never credential values):
  1. dbx CLI installed          -> if missing, prints the install command
  2. required env vars present  -> reports only WHICH variable is missing
  3. dbx connection exists      -> prod_192.168.5.17_machine

IMPORTANT: this script never prints credential values. Output is limited to
status markers and missing-variable NAMES, so nothing sensitive leaks into
the conversation context.

    python check_env.py
"""

import os
import sys
import json
import subprocess

DBX_CONN = "prod_192.168.5.17_machine"
DBX_INSTALL_CMD = "npm install -g @dbx-app/cli"

# Env vars the flow needs. NEVER print their values — names only.
# Token is NOT user-provided: get_token.py fetches it by logging in with
# DT_USERNAME/DT_PASSWORD, then scripts take it via --token.
REQUIRED_ENV_VARS = [
    "DT_USERNAME",
    "DT_PASSWORD",
]


def check_dbx_cli() -> bool:
    print(f"[1] dbx CLI")
    out = subprocess.run("dbx --version", capture_output=True, text=True, shell=True)
    if out.returncode == 0:
        version = out.stdout.strip().splitlines()[0] if out.stdout.strip() else "?"
        print(f"    PASS  dbx installed ({version})")
        return True
    print(f"    FAIL  dbx CLI not found")
    print(f"    FIX   install it (human step, agents never install):")
    print(f"          {DBX_INSTALL_CMD}")
    print(f"          (or Homebrew: brew tap t8y2/tap && brew install dbx-cli)")
    return False


def check_env_vars() -> bool:
    print("[2] Environment variables")
    ok = True
    for name in REQUIRED_ENV_VARS:
        if os.environ.get(name):
            print(f"    PASS  {name} is set")
        else:
            print(f"    FAIL  {name} is NOT set")
            ok = False
    return ok


def check_dbx_connection() -> bool:
    print(f"[3] dbx connection ({DBX_CONN})")
    out = subprocess.run(
        "dbx connections list --json",
        capture_output=True, encoding="utf-8", shell=True,
    )
    if out.returncode != 0:
        print(f"    FAIL  cannot list connections: {out.stderr.strip()}")
        return False
    try:
        conns = json.loads(out.stdout).get("connections", [])
    except json.JSONDecodeError:
        print(f"    FAIL  dbx connections list returned non-JSON output")
        return False
    names = {c.get("name") for c in conns}
    if DBX_CONN in names:
        print(f"    PASS  connection exists")
        return True
    print(f"    FAIL  connection '{DBX_CONN}' NOT found in dbx connections list")
    print(f"    FIX   create it in DBX Desktop (human step, agents never do this),")
    print(f"          or see README.md in this skill for the exact connection settings")
    print(f"    INFO  current connections: {sorted(names)}")
    return False


def main() -> None:
    checks = [check_dbx_cli, check_env_vars, check_dbx_connection]
    results = [fn() for fn in checks]
    all_ok = all(results)
    print("\n" + ("[ENV OK] all checks passed — flow can run." if all_ok
                  else "[ENV FAIL] fix the FAIL items above before running the flow."))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
