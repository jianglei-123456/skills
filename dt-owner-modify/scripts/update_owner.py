#!/usr/bin/env python3
"""Re-point the owner (and optionally the distributor) of IMEIs, then sync DSS.

Step 1 writes, in one statement on the machine db: ysb.install_iot_owner
(customer_id, distributor_id), ysb.install_iot (company_id,
install_distributor_company_id), ysb.install_iot_machine (distributor_id) and
public.iot (owner_company_id, owner_company). Step 2 mirrors ownerCompanyId /
ownerCompany into dss contract.iot. Step 3 re-reads everything to verify, step 4
posts the DSS sync endpoint once per IMEI (same call as push_ysb.py).

Requires --yes: the user must confirm the preview first.

    python update_owner.py --imeis A,B --owner "淮南农场" --distributor "寿县大唐" --yes
    python update_owner.py --imeis A,B --owner 7219 --token "$TOKEN" --yes
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


def verify(imeis: list[str], owner_id: int, distributor_id) -> tuple[list[str], dict]:
    """Re-read every table; return (mismatching IMEIs, details)."""
    bad, details = [], {}
    state = common.fetch_state(imeis)
    for imei in imeis:
        row = state.get(imei) or {}
        if row.get("owner_customer_id") != owner_id:
            bad.append(imei)
            details[imei] = f"customer_id={row.get('owner_customer_id')}"
            continue
        if distributor_id:
            missing = common.distributor_mismatches(row, distributor_id)
            if missing:
                bad.append(imei)
                details[imei] = "经销商未更新: " + ", ".join(missing)
    return bad, details


def main() -> None:
    parser = argparse.ArgumentParser(description="Change device owner/distributor and sync DSS.")
    parser.add_argument("--imeis", required=True, help="One or more IMEIs, comma separated.")
    parser.add_argument("--owner", required=True,
                        help="New owner: ysb.customer id, or full/partial name.")
    parser.add_argument("--distributor",
                        help="New distributor: basic.company id or name (updates all 6 distributor fields).")
    parser.add_argument("--token", help="Reuse an existing token (default: login with env vars).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the SQL and the sync calls, but do nothing.")
    parser.add_argument("--yes", action="store_true",
                        help="Confirm the user reviewed the preview; required to write.")
    args = parser.parse_args()

    imeis = common.parse_imeis(args.imeis)
    try:
        plan = common.build_plan(imeis, args.owner, args.distributor)
    except common.AbortError as e:
        print(f"[ABORT] {e.message}")
        for line in e.details:
            print(f"        {line}")
        sys.exit(2)

    owner = plan["owner"]
    distributor = plan["distributor"]
    target_imeis = [row["imei"] for row in plan["targets"]]

    if args.dry_run:
        print(f"[DRY-RUN] 新机主 {owner['name']} ({owner['id']})"
              + (f"，新经销商 {distributor['name']} ({distributor['id']})" if distributor else ""))
        print(plan["sql"])
        if plan["dss_sql"]:
            print(plan["dss_sql"])
        for imei in target_imeis:
            print(f'[DRY-RUN] POST {SYNC_URL} {{"imei": "{imei}"}}')
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

    print(f"[INFO] 新机主 {owner['name']} (id={owner['id']})"
          + (f"  新经销商 {distributor['name']} (id={distributor['id']})" if distributor else "")
          + f"  待修改={len(target_imeis)}  已一致={len(plan['unchanged'])}  "
            f"未找到={len(plan['missing'])}")

    # Step 1: machine db.
    try:
        rows = common.dbx_rows(common.DBX_MACHINE, plan["sql"], write=True)
    except common.AbortError as e:
        print(f"[ABORT] {e.message}")
        for line in e.details:
            print(f"        {line}")
        sys.exit(1)

    if distributor:
        per_table = {}
        for r in rows:
            per_table.setdefault(r.get("tbl"), set()).add(r.get("imei"))
        updated_imeis = sorted(per_table.get("owner", set()))
        print(f"\n[MACHINE] 已更新 {len(updated_imeis)}/{len(target_imeis)} 台")
        for table, label in (("owner", "ysb.install_iot_owner"), ("install", "ysb.install_iot"),
                             ("machine", "ysb.install_iot_machine"), ("iot", "public.iot")):
            hit = per_table.get(table, set())
            miss = [i for i in target_imeis if i not in hit]
            print(f"    {label:<28} {len(hit)} 行" + (f"  未命中: {', '.join(miss)}" if miss else ""))
    else:
        updated_imeis = [r.get("imei") for r in rows]
        print(f"\n[MACHINE] 已更新 {len(updated_imeis)}/{len(target_imeis)} 行")
    for imei in target_imeis:
        print(f"    {imei} -> {'OK' if imei in updated_imeis else 'MISS'}")

    # Step 2: dss db (ownerCompanyId / ownerCompany mirror).
    dss_failed = False
    if distributor:
        try:
            dss_rows = common.dbx_rows(common.DBX_DSS, plan["dss_sql"], write=True)
            print(f"\n[DSS] contract.iot 已更新 {len(dss_rows)} 行"
                  + ("" if dss_rows else "（该库无对应 iot 记录，跳过）"))
        except common.AbortError as e:
            dss_failed = True
            print(f"\n[WARN] dss contract.iot 更新失败: {e.message}")
            for line in e.details:
                print(f"        {line}")

    # Step 3: read back.
    bad, details = verify(updated_imeis, owner["id"],
                          distributor["id"] if distributor else None) if updated_imeis else ([], {})
    print(f"\n[VERIFY] 回读 {len(updated_imeis)} 台，"
          f"{'全部一致' if not bad else '不一致: ' + ', '.join(bad)}")
    for imei, why in details.items():
        print(f"    {imei}  {why}")

    # Step 4: DSS sync.
    print(f"\n[SYNC] POST {SYNC_URL}")
    synced, sync_failed = [], []
    for idx, imei in enumerate(updated_imeis, 1):
        ok, summary = sync_imei(token, imei)
        print(f"    [{idx}/{len(updated_imeis)}] {imei} -> {'OK' if ok else 'FAIL'}  {summary}")
        (synced if ok else sync_failed).append(imei)

    print("\n[SUMMARY]")
    print(f"    updated:  {len(updated_imeis)}/{len(target_imeis)}")
    if plan["unchanged"]:
        print(f"    unchanged:{len(plan['unchanged'])}  (已一致)")
    if plan["missing"]:
        print(f"    missing:  {len(plan['missing'])}  ({', '.join(plan['missing'])})")
    print(f"    synced:   {len(synced)}/{len(updated_imeis)}")
    if sync_failed or bad or dss_failed:
        if dss_failed:
            print("    dss contract.iot: 更新失败")
        if sync_failed:
            print(f"    sync failed: {', '.join(sync_failed)}")
        if bad:
            print(f"    verify mismatch: {', '.join(bad)}")
        sys.exit(1)
    print("    全部完成。")


if __name__ == "__main__":
    main()
