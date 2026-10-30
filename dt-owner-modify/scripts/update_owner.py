#!/usr/bin/env python3
"""Re-point the owner of one or more IMEIs, then trigger the DSS sync.

Step 1 writes ysb.install_iot_owner.customer_id through dbx (--allow-writes),
step 2 re-reads the rows to verify, step 3 posts the DSS sync endpoint once per
IMEI (same call as push_ysb.py). Requires --yes: the user must confirm the
preview first.

    python update_owner.py --imeis A,B --owner "抉择" --yes
    python update_owner.py --imeis A,B --owner 6236 --token "$TOKEN" --yes
"""

import sys
import json
import argparse
import urllib.request
import urllib.error

import common
import get_token as token_mod

SYNC_URL = "https://dss.datian360.com/prod_api/dtwl/sales/install/pushData"
TIMEOUT = 30
OK_CODES = {"0", "200", "20000"}


def sync_imei(token: str, imei: str) -> tuple[bool, str]:
    """POST the sync endpoint for one IMEI. Returns (ok, summary)."""
    data = json.dumps({"imei": imei}).encode("utf-8")
    req = urllib.request.Request(SYNC_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", token)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status, text = resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace').strip()[:200]}"
    except urllib.error.URLError as e:
        return False, f"request failed: {e.reason}"

    if status != 200:
        return False, f"HTTP {status}: {text.strip()[:200]}"
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        return True, f"HTTP 200 {text.strip()[:120]}"
    if isinstance(body, dict):
        code = body.get("code", body.get("status"))
        if body.get("success") is False:
            return False, f"code={code} message={body.get('message') or body.get('msg') or ''}"
        if code is not None and str(code) not in OK_CODES and body.get("success") is not True:
            return False, f"code={code} message={body.get('message') or body.get('msg') or ''}"
    return True, f"HTTP 200 {text.strip()[:120]}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Change device owner and trigger the DSS sync.")
    parser.add_argument("--imeis", required=True, help="One or more IMEIs, comma separated.")
    parser.add_argument("--owner", required=True,
                        help="New owner: ysb.customer id, or full/partial name.")
    parser.add_argument("--token", help="Reuse an existing token (default: login with env vars).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the UPDATE and the sync calls, but do nothing.")
    parser.add_argument("--yes", action="store_true",
                        help="Confirm the user reviewed the preview; required to write.")
    args = parser.parse_args()

    imeis = common.parse_imeis(args.imeis)
    try:
        plan = common.build_plan(imeis, args.owner)
    except common.AbortError as e:
        print(f"[ABORT] {e.message}")
        for line in e.details:
            print(f"        {line}")
        sys.exit(2)

    owner = plan["owner"]
    target_imeis = [r["imei"] for r in plan["targets"]]

    if args.dry_run:
        print(f"[DRY-RUN] 新机主 {owner['name']} ({owner['id']})")
        print(plan["sql"])
        for imei in target_imeis:
            print(f"[DRY-RUN] POST {SYNC_URL} {{\"imei\": \"{imei}\"}}")
        sys.exit(0)

    if not args.yes:
        sys.stderr.write(
            "[ABORT] refusing to write without --yes. Run preview.py, show the data "
            "to the user, then re-run with --yes.\n"
        )
        sys.exit(2)

    # Log in before mutating anything: a late auth failure would leave the DB
    # changed with no sync call.
    token = args.token or token_mod.get_token_from_env()

    print(f"[INFO] 新机主 {owner['name']} (id={owner['id']})  "
          f"待修改={len(target_imeis)}  已一致={len(plan['unchanged'])}  "
          f"未找到={len(plan['missing'])}")

    # Step 1: write.
    try:
        updated = common.dbx_rows(common.DBX_MACHINE, plan["sql"], write=True)
    except common.AbortError as e:
        print(f"[ABORT] {e.message}")
        for line in e.details:
            print(f"        {line}")
        sys.exit(1)
    updated_imeis = [r["imei"] for r in updated]
    print(f"\n[UPDATE] 已更新 {len(updated_imeis)}/{len(target_imeis)} 行")
    for imei in target_imeis:
        mark = "OK" if imei in updated_imeis else "MISS"
        print(f"    {imei} -> {mark}")

    # Step 2: read back.
    verify = common.fetch_owner_rows(updated_imeis) if updated_imeis else {}
    bad = [i for i in updated_imeis if (verify.get(i) or {}).get("customer_id") != owner["id"]]
    print(f"\n[VERIFY] 回读 {len(updated_imeis)} 行，"
          f"{'全部一致' if not bad else '不一致: ' + ', '.join(bad)}")

    # Step 3: DSS sync.
    print(f"\n[SYNC] POST {SYNC_URL}")
    synced, sync_failed = [], []
    for idx, imei in enumerate(updated_imeis, 1):
        ok, summary = sync_imei(token, imei)
        print(f"    [{idx}/{len(updated_imeis)}] {imei} -> {'OK' if ok else 'FAIL'}  {summary}")
        (synced if ok else sync_failed).append(imei)

    print("\n[SUMMARY]")
    print(f"    updated:  {len(updated_imeis)}/{len(target_imeis)}")
    if plan["unchanged"]:
        print(f"    unchanged:{len(plan['unchanged'])}  (已是目标机主)")
    if plan["missing"]:
        print(f"    missing:  {len(plan['missing'])}  ({', '.join(plan['missing'])})")
    print(f"    synced:   {len(synced)}/{len(updated_imeis)}")
    if sync_failed or bad:
        if sync_failed:
            print(f"    sync failed: {', '.join(sync_failed)}")
        if bad:
            print(f"    verify mismatch: {', '.join(bad)}")
        sys.exit(1)
    print("    全部完成。")


if __name__ == "__main__":
    main()
