#!/usr/bin/env python3
"""Pre-flight preview for the device owner / distributor change (read-only).

Resolves the new owner (ysb.customer) and optional distributor (basic.company),
reads each IMEI's current values across every table involved, and prints the
exact SQL that would run. Performs no writes and calls no DSS endpoint.

    python preview.py --imeis A,B --owner "淮南农场" --distributor "寿县大唐"
    python preview.py --imeis A,B --owner 7219
"""

import sys
import argparse

import common

SYNC_URL = "https://dss.datian360.com/prod_api/dtwl/sales/install/pushData"


def fmt(value) -> str:
    return "-" if value in (None, "") else str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Device owner/distributor change preview (read-only).")
    parser.add_argument("--imeis", required=True, help="One or more IMEIs, comma separated.")
    parser.add_argument("--owner", required=True,
                        help="New owner: ysb.customer id, or full/partial name.")
    parser.add_argument("--distributor", help="New distributor: basic.company id or name.")
    args = parser.parse_args()

    imeis = common.parse_imeis(args.imeis)

    print("=" * 64)
    print("大田修改机主 / 经销商 — 预查询确认（只读）")
    print("=" * 64)

    try:
        plan = common.build_plan(imeis, args.owner, args.distributor)
    except common.AbortError as e:
        print(f"\n[ABORT] {e.message}")
        for line in e.details:
            print(f"        {line}")
        if not e.details:
            print(f"        共 {len(imeis)} 台：{', '.join(imeis) if imeis else '(空)'}")
        sys.exit(2)

    owner = plan["owner"]
    match_label = {"id": "按 id", "exact": "精确匹配", "fuzzy": "模糊匹配"}[plan["owner_match"]]
    print(f"\n[1] 新机主 (输入「{args.owner}」, {match_label}, machine.ysb.customer)")
    print(f"    id={owner['id']}  {owner['name']}  status={owner['status']}")
    if plan["owner_note"]:
        print(f"    注: {plan['owner_note']}")

    distributor = plan["distributor"]
    if distributor:
        dist_label = {"id": "按 id", "exact": "精确匹配", "fuzzy": "模糊匹配"}[plan["distributor_match"]]
        print(f"\n[2] 新经销商 (输入「{args.distributor}」, {dist_label}, machine.basic.company)")
        print(f"    id={distributor['id']}  {distributor['name']}  status={distributor['status']}")
        if plan["distributor_note"]:
            print(f"    注: {plan['distributor_note']}")

    print(f"\n[3] 机主表核对 (machine.ysb.install_iot_owner, is_deleted=0, {len(imeis)} 台)")
    for imei in imeis:
        row = plan["state"].get(imei)
        if row is None or row.get("owner_customer_id") is None:
            print(f"    - {imei}  [未找到机主记录] -> 跳过")
            continue
        is_target = row in plan["targets"]
        print(f"    - {imei}  机主={fmt(row.get('customer_name'))}({fmt(row.get('owner_customer_id'))})"
              f" -> {'改' if is_target else '跳过（已一致）'}")
        if is_target and distributor:
            missing = common.distributor_mismatches(row, distributor["id"])
            if missing:
                print(f"        待改经销商字段: {', '.join(missing)}")

    print(f"\n[4] 将执行的 SQL (machine 库, 共 {len(plan['targets'])} 台)")
    for line in plan["sql"].splitlines():
        print(f"    {line}")
    if plan["dss_sql"]:
        print("\n[5] 将执行的 SQL (dss 库 contract.iot)")
        for line in plan["dss_sql"].splitlines():
            print(f"    {line}")

    print("\n[6] 变更后调用 DSS 同步接口 (每台一次)")
    print(f"    POST {SYNC_URL}")
    print('    body  {"imei": "<每台 IMEI>"}   (Authorization: <token>)')

    print("\n[7] 结论")
    if plan["missing"]:
        print(f"    [WARN] {len(plan['missing'])} 台在机主表中不存在，将被跳过：{', '.join(plan['missing'])}")
    if plan["unchanged"]:
        print(f"    [INFO] {len(plan['unchanged'])} 台已一致，不重复写入")
    target = f"机主 -> {owner['name']}({owner['id']})"
    if distributor:
        target += f"，经销商 -> {distributor['name']}({distributor['id']})"
    print(f"    [OK] 将修改 {len(plan['targets'])} 台：{target}，随后推送 DSS 同步。")
    print("    确认后执行 update_owner.py（同一组参数 + --yes）。")


if __name__ == "__main__":
    main()
