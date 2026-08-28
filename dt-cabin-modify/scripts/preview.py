#!/usr/bin/env python3
"""Pre-flight preview for the DT cabin modify flow.

Queries everything the flow will need and prints it for user confirmation,
WITHOUT performing any write. The user confirms the shown data, then the
agent runs the full flow.

    python preview.py --token "$TOKEN" --imei YS0285093740549 \
        --owner-company "山东天海重工有限公司" \
        [--company "第一拖拉机股份有限公司"] [--model "LP2204-C"]
"""

import os
import sys
import json
import subprocess
import argparse

DBX_CONN = "prod_192.168.5.17_machine"
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_query_module():
    """Import query_by_imei.py in-process (avoids subprocess encoding issues)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "query_by_imei", os.path.join(SCRIPTS_DIR, "query_by_imei.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def dbx_query(sql: str) -> list:
    cmd = f'dbx query {DBX_CONN} "{sql}" --json'
    out = subprocess.run(cmd, capture_output=True, encoding="utf-8", shell=True)
    if out.returncode != 0:
        sys.stderr.write(f"dbx query failed:\n{out.stderr}\n")
        sys.exit(1)
    try:
        resp = json.loads(out.stdout)
    except json.JSONDecodeError:
        sys.stderr.write(f"dbx response not JSON:\n{out.stdout}\n")
        sys.exit(1)
    if resp.get("error"):
        sys.stderr.write(f"dbx error: {resp['error'].get('message')}\n")
        sys.exit(1)
    return resp.get("rows", [])


def fetch_company(name: str) -> dict | None:
    rows = dbx_query(f"select id,name from basic.company where name = '{name}';")
    if not rows:
        return None
    first = rows[0]
    if isinstance(first, dict):
        return {"id": first.get("id"), "name": first.get("name")}
    return {"id": first[0], "name": first[1]}


def fetch_model(company_id, model: str) -> dict | None:
    sql = ("select id,model,category_id1,category_id2,category_id3,class_name1,"
           "class_name2,class_name3 "
           f"from model.model where company_id = {company_id} and model = '{model}';")
    rows = dbx_query(sql)
    if not rows:
        return None
    first = rows[0]
    if isinstance(first, dict):
        return {
            "modelId": first.get("id"), "model": first.get("model"),
            "categoryId1": first.get("category_id1"),
            "categoryId2": first.get("category_id2"),
            "categoryId3": first.get("category_id3"),
            "className1": first.get("class_name1"),
            "className2": first.get("class_name2"),
            "className3": first.get("class_name3"),
        }
    return {
        "modelId": first[0], "model": first[1],
        "categoryId1": first[2], "categoryId2": first[3], "categoryId3": first[4],
        "className1": first[5], "className2": first[6], "className3": first[7],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-flight preview (read-only).")
    parser.add_argument("--token", help="Login token. (required, from get_token.py).")
    parser.add_argument("--imei", required=True, help="Device IMEI.")
    parser.add_argument("--owner-company", required=True,
                        help="New owner company name (target change).")
    parser.add_argument("--company", default="第一拖拉机股份有限公司",
                        help="Company for the machine insert (dbx lookup).")
    parser.add_argument("--model", default="LP2204-C",
                        help="Model for the machine insert (dbx lookup).")
    args = parser.parse_args()

    token = args.token
    if not token:
        sys.stderr.write("Missing token. Pass --token.\n")
        sys.exit(1)

    print("=" * 60)
    print("DT 座舱信息修改 — 预查询确认")
    print("=" * 60)

    # 1. Current device info (read-only API).
    query_mod = load_query_module()
    print("\n[1] 设备当前信息 (queryByImei)")
    try:
        resp = query_mod.query_by_imei(token, args.imei)
        device = resp.get("data", {}).get("result")
    except SystemExit:
        device = None
    if device:
        print(f"  imei:              {device.get('imei')}")
        print(f"  生产企业:           {device.get('ownerCompany')} (id={device.get('ownerCompanyId')})")
        print(f"  农机型号:           {device.get('model')} (id={device.get('modelId')})")
        print(f"  农机品目:           {device.get('categoryName3')} "
              f"(cat3={device.get('categoryId3')})")
        print(f"  terminalName:      {device.get('terminalName')}")
        print(f"  sku:               {device.get('sku')}")
        print(f"  typeId1/2/3:       {device.get('typeId1')}/{device.get('typeId2')}/{device.get('typeId3')}")
        print(f"  terminalSn:        {device.get('terminalSn')}")
        print(f"  terminalModel:     {device.get('terminalModel')}")
        print(f"  terminalFactory:   {device.get('terminalFactoryNumber')}")
    else:
        print(f"  imei: {args.imei} — 未查到设备记录（流程仍将继续，使用模板数据）")
        device = {}

    # 2. Target owner company (dbx).
    print("\n[2] 目标生产企业 (basic.company via dbx)")
    company = fetch_company(args.owner_company)
    if company:
        print(f"  name: {company['name']}")
        print(f"  id:   {company['id']}")
    else:
        print(f"  [ABORT] 企业 '{args.owner_company}' 在 basic.company 中不存在，流程将中止。")

    # 3. Machine company + model (dbx) — for write step 2.
    #    NOTE: this is the machine company (--company, default 第一拖拉机), NOT
    #    the owner company. The model lookup uses the machine company's id.
    print(f"\n[3] 农机企业+型号 (model.model via dbx, company={args.company})")
    model_info = None
    machine_company = fetch_company(args.company)
    if not machine_company:
        print(f"  [ABORT] 企业 '{args.company}' 在 basic.company 中不存在，流程将中止。")
    else:
        print(f"  农机企业: {machine_company['name']} (id={machine_company['id']})")
        model_info = fetch_model(machine_company["id"], args.model)
        if model_info:
            print(f"  model:         {model_info['model']} (id={model_info['modelId']})")
            print(f"  categoryId1:   {model_info['categoryId1']} {model_info.get('className1')}")
            print(f"  categoryId2:   {model_info['categoryId2']} {model_info.get('className2')}")
            print(f"  categoryId3:   {model_info['categoryId3']} {model_info.get('className3')}")
        else:
            print(f"  [ABORT] 型号 '{args.model}' 在 model.model 中不存在，流程将中止。")

    # 4. Install record check (read-only API).
    print("\n[4] 安装记录 (sales/install/view)")
    try:
        install_url = ("https://dss.datian360.com/prod_api/dtwl/sales/install/view"
                       f"?imei={args.imei}")
        import urllib.request
        req = urllib.request.Request(install_url, method="GET")
        req.add_header("Authorization", token)
        with urllib.request.urlopen(req) as r:
            install_resp = json.loads(r.read().decode("utf-8"))
        install_result = install_resp.get("data", {}).get("result")
        if install_result:
            print(f"  有安装记录 (installUser={install_result.get('installUserName')}, "
                  f"company={install_result.get('company')}) → 将调用删除接口")
        else:
            print("  无安装记录 → 跳过删除")
    except Exception as e:
        print(f"  [WARN] 安装记录查询失败: {e}")

    # 5. Decision summary.
    print("\n[5] 决策汇总")
    if not company or not machine_company or not model_info:
        print("  存在中止条件（生产企业/农机企业/型号未查到），全流程不会执行。")
    else:
        current = (device or {}).get("ownerCompany")
        if current and current == args.owner_company:
            print("  生产企业: 已是目标值，无需更新（跳过更新步骤）")
        else:
            print("  生产企业: 需要更新 (当前=%s → 目标=%s)" % (current, args.owner_company))
        print("  安装记录: 按查询结果执行删除/跳过")
        print("  写入链路: 3 个写入接口 + 5s + updateUserInfo")

    print("\n" + "=" * 60)
    print("确认无误后执行全流程:")
    print(f'  python {os.path.join(SCRIPTS_DIR, "run_flow.py")} \\')
    print(f'    --imei {args.imei} --owner-company "{args.owner_company}" '
          f'--company "{args.company}" --model "{args.model}" --yes')
    print("=" * 60)


if __name__ == "__main__":
    main()
