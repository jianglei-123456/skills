#!/usr/bin/env python3
"""Pre-flight preview for the device-owner change (read-only).

Resolves the new owner in ysb.customer, reads the current owner row of every
IMEI in ysb.install_iot_owner, and prints the exact UPDATE that would run.
Performs no writes and calls no DSS endpoint.

    python preview.py --imeis 869637053418218,869637053418219 --owner "抉择"
    python preview.py --imeis A,B --owner 6236
"""

import sys
import argparse

import common

SYNC_URL = "https://dss.datian360.com/prod_api/dtwl/sales/install/pushData"


def fmt(value) -> str:
    return "-" if value in (None, "") else str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Device-owner change preview (read-only).")
    parser.add_argument("--imeis", required=True, help="One or more IMEIs, comma separated.")
    parser.add_argument("--owner", required=True,
                        help="New owner: ysb.customer id, or full/partial name.")
    args = parser.parse_args()

    imeis = common.parse_imeis(args.imeis)

    print("=" * 64)
    print("大田修改机主 — 预查询确认（只读）")
    print("=" * 64)

    try:
        plan = common.build_plan(imeis, args.owner)
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

    print(f"\n[2] 机主表核对 (machine.ysb.install_iot_owner, is_deleted=0, {len(imeis)} 台)")
    for imei in imeis:
        row = plan["current"].get(imei)
        if row is None:
            print(f"    - {imei}  [未找到机主记录] -> 跳过")
        elif row["customer_id"] == owner["id"]:
            print(f"    - {imei}  机主={fmt(row['customer_name'])}({fmt(row['customer_id'])})"
                  f"  distributor={fmt(row['distributor_id'])}  [已是目标机主] -> 跳过")
        else:
            print(f"    - {imei}  机主={fmt(row['customer_name'])}({fmt(row['customer_id'])})"
                  f"  distributor={fmt(row['distributor_id'])}"
                  f" -> {owner['name']}({owner['id']})")

    print(f"\n[3] 将执行的 SQL (共 {len(plan['targets'])} 行)")
    for line in plan["sql"].splitlines():
        print(f"    {line}")

    print(f"\n[4] 变更后调用 DSS 同步接口 (每台一次)")
    print(f"    POST {SYNC_URL}")
    print(f'    body  {{"imei": "<每台 IMEI>"}}   (Authorization: <token>)')

    print("\n[5] 结论")
    if plan["missing"]:
        print(f"    [WARN] {len(plan['missing'])} 台在机主表中不存在，将被跳过：{', '.join(plan['missing'])}")
    if plan["unchanged"]:
        print(f"    [INFO] {len(plan['unchanged'])} 台已是目标机主，不重复写入")
    print(f"    [OK] 将修改 {len(plan['targets'])} 台设备的机主 -> {owner['name']}({owner['id']})，"
          f"随后推送 DSS 同步。")
    print("    确认后执行 update_owner.py（同一组参数 + --yes）。")


if __name__ == "__main__":
    main()
