#!/usr/bin/env python3
"""Run the full DT cabin install write chain for one IMEI.

Sequence (each step must succeed before the next runs):
  1. installIotInsert        (install_iot_insert.py)
  2. installIotMachine/insert (install_iot_machine_insert.py)
  3. installIotOwner/insert  (install_iot_owner_insert.py)
  4. wait 5s
  5. updateUserInfo          (update_user_info.py)

    python run_install_chain.py --token "$TOKEN" --imei YS0285093740549
"""

import os
import sys
import subprocess
import argparse

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def run_script(script: str, token: str, imei: str, extra: list | None = None) -> bool:
    cmd = [
        sys.executable,
        os.path.join(SCRIPTS_DIR, script),
        "--token", token,
        "--imei", imei,
    ] + (extra or [])
    print(f"\n=== {script} ===")
    r = subprocess.run(cmd, encoding="utf-8")
    if r.returncode != 0:
        print(f"[FAILED] {script} exited {r.returncode}. Chain aborted.")
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full DT install write chain.")
    parser.add_argument("--token", help="Login token. (required, from get_token.py).")
    parser.add_argument("--imei", required=True, help="Device IMEI.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Dry-run every step (no POSTs).")
    args = parser.parse_args()

    token = args.token
    if not token:
        sys.stderr.write("Missing token. Pass --token.\n")
        sys.exit(1)

    extra = ["--dry-run"] if args.dry_run else []
    chain = [
        ("install_iot_insert.py", []),
        ("install_iot_machine_insert.py", []),
        ("install_iot_owner_insert.py", []),
        ("update_user_info.py", ["--delay", "5"]),
    ]

    ok = True
    for script, more in chain:
        if not run_script(script, token, args.imei, extra + more):
            ok = False
            break

    if ok:
        print("\n[CHAIN DONE] All steps completed.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
