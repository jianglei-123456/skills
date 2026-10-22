#!/usr/bin/env python3
"""Environment check for the DT sale-info update flow.

Checks (read-only; prints status only, never credential values):
  1. dbx CLI installed
  2. DT_USERNAME / DT_PASSWORD present
  3. both dbx connections exist

    python check_env.py
"""

import json
import os
import subprocess
import sys

DBX_CONNECTIONS = [
    "prod_192.168.5.129_dss_owner",  # dss database: contract.product
    "prod_192.168.5.17_machine",     # machine database: basic.company
]
DBX_INSTALL_CMD = "npm install -g @dbx-app/cli"
REQUIRED_ENV_VARS = ["DT_USERNAME", "DT_PASSWORD"]


def check_dbx_cli() -> bool:
    print("[1] dbx CLI")
    out = subprocess.run("dbx --version", capture_output=True, text=True, shell=True)
    if out.returncode == 0:
        version = out.stdout.strip().splitlines()[0] if out.stdout.strip() else "?"
        print(f"    PASS  dbx installed ({version})")
        return True
    print("    FAIL  dbx CLI not found")
    print("    FIX   install it (human step, agents never install):")
    print(f"          {DBX_INSTALL_CMD}")
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


def check_dbx_connections() -> bool:
    print("[3] dbx connections")
    out = subprocess.run("dbx connections list --json", capture_output=True,
                         encoding="utf-8", shell=True)
    if out.returncode != 0:
        print(f"    FAIL  cannot list connections: {out.stderr.strip()}")
        return False
    try:
        names = {c.get("name") for c in json.loads(out.stdout).get("connections", [])}
    except json.JSONDecodeError:
        print("    FAIL  dbx connections list returned non-JSON output")
        return False
    ok = True
    for conn in DBX_CONNECTIONS:
        if conn in names:
            print(f"    PASS  {conn}")
        else:
            print(f"    FAIL  {conn} NOT found")
            print("          create it in DBX Desktop (human step); see README.md")
            ok = False
    return ok


def main() -> None:
    results = [fn() for fn in (check_dbx_cli, check_env_vars, check_dbx_connections)]
    all_ok = all(results)
    print("\n" + ("[ENV OK] all checks passed — flow can run."
                  if all_ok else "[ENV FAIL] fix the FAIL items above first."))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
