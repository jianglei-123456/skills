#!/usr/bin/env python3
"""Pre-flight preview for the DT sale-info update (read-only).

Resolves the sku -> product and the (partial) company name -> full name/id,
reads the current device values, and prints the exact JSON that would be
posted. Performs no writes.

    python preview.py --token "$TOKEN" \
        --imeis 650200496009244,650200496009245 \
        --sku AA000002 --owner-company "抉择" [--date 2026-10-08]
"""

import sys
import json
import argparse

import common
import query_by_imei as query_mod


def current_device(token: str, imei: str) -> dict | None:
    try:
        resp = query_mod.query_by_imei(token, imei)
    except SystemExit:
        return None
    return resp.get("data", {}).get("result") or None


def fmt(value) -> str:
    return "-" if value in (None, "") else str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="DT sale-info update preview (read-only).")
    parser.add_argument("--token", required=True, help="Login token from get_token.py.")
    parser.add_argument("--imeis", required=True,
                        help="One or more IMEIs, comma separated.")
    parser.add_argument("--sku", required=True, help="Product sku (e.g. AA000002).")
    parser.add_argument("--owner-company", required=True,
                        help="Owner company name, may be partial.")
    parser.add_argument("--date", help="Sale date YYYY-MM-DD (default: today).")
    args = parser.parse_args()

    imeis = common.parse_imeis(args.imeis)
    try:
        start = common.parse_day(args.date)
    except ValueError:
        sys.stderr.write(f"[ABORT] --date must be YYYY-MM-DD, got '{args.date}'\n")
        sys.exit(2)

    print("=" * 64)
    print("DT 销售信息更新 — 预查询确认（只读）")
    print("=" * 64)

    try:
        plan = common.build_plan(args.sku, args.owner_company, imeis, start)
    except common.AbortError as e:
        print(f"\n[ABORT] {e.message}")
        for line in e.details:
            print(f"        {line}")
        sys.exit(2)

    product, company = plan["product"], plan["company"]
    print(f"\n[1] 合同产品 (sku={product['sku']}, dss.contract.product)")
    print(f"    typeId1/2/3      {product['typeId1']} / {product['typeId2']} / {product['typeId3']}")
    print(f"    terminalName     {product['terminalName']}")
    print(f"    terminalModel    {product['terminalModel']}")

    match_label = "精确匹配" if plan["company_match"] == "exact" else "模糊匹配"
    print(f"\n[2] 归属企业 (输入「{args.owner_company}」, {match_label}, machine.basic.company)")
    print(f"    id={company['id']}  {company['name']}")
    if plan["company_note"]:
        print(f"    注: {plan['company_note']}")

    print(f"\n[3] 设备当前信息 (queryByImei, {len(imeis)} 台)")
    missing = []
    for imei in imeis:
        device = current_device(args.token, imei)
        if not device:
            missing.append(imei)
            print(f"    - {imei}  [未查到设备记录]")
            continue
        print(
            f"    - {imei}"
            f" | 归属企业={fmt(device.get('ownerCompany'))}({fmt(device.get('ownerCompanyId'))})"
            f" | sku={fmt(device.get('sku'))}"
            f" | 型号={fmt(device.get('model'))}"
            f" | sellTime={fmt(device.get('sellTime'))}"
            f" | 服务期={fmt(device.get('commServiceBeginDate'))} → {fmt(device.get('commServiceEndDate'))}"
        )

    print(f"\n[4] 将提交的 JSON (共 {len(imeis)} 台，仅 imei 不同)")
    sample = dict(plan["bodies"][0][1])
    sample["imei"] = "<每台 IMEI>"
    for line in json.dumps(sample, ensure_ascii=False, indent=2).splitlines():
        print(f"    {line}")

    print("\n[5] 结论")
    if missing:
        print(f"    [WARN] {len(missing)} 台未查到设备记录，接口将按上述 body 直接写入：")
        print(f"           {', '.join(missing)}")
    print(f"    [OK] 将更新 {len(imeis)} 台设备（销售日期基准 {start.isoformat()}）。")
    print("    确认后执行 update_sale.py（同一组参数 + --yes）。")


if __name__ == "__main__":
    main()
