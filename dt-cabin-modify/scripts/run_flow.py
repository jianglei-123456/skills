#!/usr/bin/env python3
"""Execute the full DT cabin modify flow after preview confirmation.

Order:
  1. preview (read-only, shown to user; --yes skips the prompt)
  2. update_sale_info     — update owner company + recomputed time fields
  3. install_iot_insert   — write ①
  4. install_iot_machine_insert — write ②
  5. install_iot_owner_insert  — write ③
  6. sleep 5s
  7. update_user_info     — final call

NOTE: no delete step — install records are never removed by this flow.

    python run_flow.py --imei YS0285093740549 \
        --owner-company "山东天海重工有限公司" \
        [--company "第一拖拉机股份有限公司"] [--model "LP2204-C"] [--yes]
"""

import os
import sys
import subprocess
import argparse

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def run(script: str, args: list, label: str) -> bool:
    print(f"\n=== {label} ===")
    r = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, script)] + args,
        encoding="utf-8",
    )
    if r.returncode != 0:
        print(f"[FAILED] {label} exited {r.returncode}. Flow aborted.")
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full DT cabin modify flow.")
    parser.add_argument("--token", help="Login token. (required, from get_token.py).")
    parser.add_argument("--imei", required=True, help="Device IMEI.")
    parser.add_argument("--owner-company", required=True,
                        help="New owner company name.")
    parser.add_argument("--company", default="第一拖拉机股份有限公司",
                        help="Company for machine insert (dbx lookup).")
    parser.add_argument("--model", default="LP2204-C",
                        help="Model for machine insert (dbx lookup).")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the confirmation prompt.")
    args = parser.parse_args()

    token = args.token
    if not token:
        sys.stderr.write("Missing token. Pass --token.\n")
        sys.exit(1)

    # Step 0: preview (read-only) — always shown before proceeding.
    print("\n########## 预查询 ##########")
    r = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "preview.py"),
         "--token", token, "--imei", args.imei,
         "--owner-company", args.owner_company,
         "--company", args.company, "--model", args.model],
        encoding="utf-8",
    )
    if r.returncode != 0:
        sys.exit(1)

    # Confirmation gate.
    if not args.yes:
        try:
            answer = input("\n确认无误，开始执行全流程? (yes/no): ").strip().lower()
        except EOFError:
            answer = ""
        if answer != "yes":
            print("[ABORT] 用户未确认，流程中止。")
            sys.exit(0)

    steps = [
        ("update_sale_info.py",
         ["--token", token, "--imei", args.imei, "--owner-company", args.owner_company],
         "步骤2: 更新销售信息(生产企业/时间)"),
        ("install_iot_insert.py",
         ["--token", token, "--imei", args.imei],
         "步骤3a: 写入① installIotInsert"),
        ("install_iot_machine_insert.py",
         ["--token", token, "--imei", args.imei,
          "--company", args.company, "--model", args.model],
         "步骤3b: 写入② installIotMachine"),
        ("install_iot_owner_insert.py",
         ["--token", token, "--imei", args.imei],
         "步骤3c: 写入③ installIotOwner"),
        ("update_user_info.py",
         ["--token", token, "--imei", args.imei, "--delay", "5"],
         "步骤4: updateUserInfo (前置等待5s)"),
    ]

    for script, script_args, label in steps:
        if not run(script, script_args, label):
            sys.exit(1)

    print("\n[FLOW DONE] 全流程执行完成。")


if __name__ == "__main__":
    main()
