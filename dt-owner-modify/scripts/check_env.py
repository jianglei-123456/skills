#!/usr/bin/env python3
"""Environment check for the device-owner change flow.

Checks (read-only; prints status only, never credential values):
  1. dbx CLI installed
  2. DT_USERNAME / DT_PASSWORD present (DSS sync login)
  3. the machine dbx connection exists
  4. ysb.customer and ysb.install_iot_owner are readable

    python check_env.py
"""

import json
import os
import subprocess
import sys

DBX_CONNECTION = "prod_192.168.5.17_machine"
DBX_INSTALL_CMD = "npm install -g @dbx-app/cli"
REQUIRED_ENV_VARS = ["DT_USERNAME", "DT_PASSWORD"]
REQUIRED_TABLES = ["customer", "install_iot_owner"]


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


def check_connection() -> bool:
    print("[3] dbx connection")
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
    if DBX_CONNECTION in names:
        print(f"    PASS  {DBX_CONNECTION}")
        return True
    print(f"    FAIL  {DBX_CONNECTION} NOT found")
    print("          create it in DBX Desktop (human step); see README.md")
    return False


def check_tables() -> bool:
    print("[4] ysb tables")
    sql = ("select table_name from information_schema.tables "
           "where table_schema = 'ysb' and table_name in "
           "('customer', 'install_iot_owner')")
    out = subprocess.run(f'dbx query {DBX_CONNECTION} "{sql}" --json',
                         capture_output=True, encoding="utf-8", shell=True)
    if out.returncode != 0:
        print(f"    FAIL  query failed: {out.stderr.strip()}")
        return False
    try:
        found = {r.get("table_name") for r in json.loads(out.stdout).get("rows", [])}
    except json.JSONDecodeError:
        print("    FAIL  non-JSON output")
        return False
    ok = True
    for table in REQUIRED_TABLES:
        if table in found:
            print(f"    PASS  ysb.{table}")
        else:
            print(f"    FAIL  ysb.{table} NOT found")
            ok = False
    return ok


def main() -> None:
    results = [fn() for fn in (check_dbx_cli, check_env_vars, check_connection, check_tables)]
    all_ok = all(results)
    print("\n" + ("[ENV OK] all checks passed — flow can run."
                  if all_ok else "[ENV FAIL] fix the FAIL items above first."))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
