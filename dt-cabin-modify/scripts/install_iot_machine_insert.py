#!/usr/bin/env python3
"""Insert machine info for a device (write step, 2nd of 3).

Lookups (via dbx):
  - company:  select id,name from basic.company where name = '<company>'
  - model:    select id,model,category_id1,category_id2,category_id3,class_name3
              from model.model where company_id = <companyId> and model = '<model>'
              (note: actual columns use underscores: category_id1/2/3)

Dynamically generated:
  - factoryNumber: 6 random alphanumeric chars + "000000" (12 chars total)
  - productionDate: today (YYYY-MM-DD)

Everything else stays at the sample values.

    python install_iot_machine_insert.py --token "$TOKEN" --imei YS0285093740549
    [--company "第一拖拉机股份有限公司"] [--model "LP2204-C"]
"""

import os
import re
import sys
import json
import random
import string
import subprocess
import argparse
import urllib.request
import urllib.error
from datetime import datetime

INSERT_URL = "https://dss.datian360.com/prod_api/dtbd/installIotMachine/insert"
DBX_CONN = "prod_192.168.5.17_machine"

# Reference sample body (only the fields below are replaced).
DEFAULT_BODY = {
    "bn": "140617.2",
    "timestamp": 1787909927,
    "token": "337e9cc2f753e12b146d4bad5f2d9ae425cb26a8",
    "terminal": 25,
    "_origin": 74,
    "user_key": "",
    "_zui": "da39a3ee5e6b4b0d3255bfef95601890afd80709",
    "submitFlag": 1,
    "imei": "",                 # user-provided
    "factoryNumber": "",        # generated: 6 alnum + 000000
    "cardHead": "",
    "categoryId3": "",          # from model lookup
    "categoryId2": "",          # from model lookup
    "categoryId1": "",          # from model lookup
    "categoryName3": "",        # from model lookup (class_name3)
    "companyId": 0,             # from company lookup
    "company": "",              # from company lookup
    "model": "",                # from model lookup
    "modelId": 0,               # from model lookup
    "productionDate": "",       # today
    "addType": 1,
    "carNumber": "",
    "engineNumber": "",
    "workType": 223,
    "cardNationalEmblem": "",
    "fullname": "",
    "card": "",
    "mobile": "",
    "nameplateThumb": "https://img4.nongji360.com/n/dv/2026/08/28173844478864.png",
    "machineThumb": "https://img4.nongji360.com/n/dv/2026/08/28173838348869.png",
}

HEADERS = {
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 "
                  "Mobile/15E148 Safari/604.1 wechatdevtools/1.06.2412050 "
                  "MicroMessenger/8.0.5 Language/zh_CN webview/",
    "from-source": "ddnf",
    "content-type": "application/json",
    "Accept": "*/*",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://servicewechat.com/wx28cce5671e85ea09/devtools/page-frame.html",
}


def dbx_query(sql: str) -> list:
    """Run one dbx query, return rows (list of dicts)."""
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


def lookup_company(name: str) -> dict:
    rows = dbx_query(f"select id,name from basic.company where name = '{name}';")
    if not rows:
        sys.stderr.write(f"[ABORT] Company '{name}' not found in {DBX_CONN} basic.company.\n")
        sys.exit(2)
    first = rows[0]
    if isinstance(first, dict):
        return {"id": first.get("id"), "name": first.get("name")}
    return {"id": first[0], "name": first[1]}


def lookup_model(company_id, model: str) -> dict:
    sql = ("select id,model,category_id1,category_id2,category_id3,class_name3 "
           f"from model.model where company_id = {company_id} and model = '{model}';")
    rows = dbx_query(sql)
    if not rows:
        sys.stderr.write(f"[ABORT] Model '{model}' not found for company_id={company_id}.\n")
        sys.exit(2)
    first = rows[0]
    if isinstance(first, dict):
        return {
            "modelId": first.get("id"),
            "model": first.get("model"),
            "categoryId1": first.get("category_id1"),
            "categoryId2": first.get("category_id2"),
            "categoryId3": first.get("category_id3"),
            "categoryName3": first.get("class_name3"),
        }
    return {
        "modelId": first[0], "model": first[1],
        "categoryId1": first[2], "categoryId2": first[3],
        "categoryId3": first[4], "categoryName3": first[5],
    }


def gen_factory_number() -> str:
    """6 random alphanumerics + 6 zeros = 12 chars total."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6)) + "000000"


def post_insert(token: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(INSERT_URL, data=data, method="POST")
    for k, v in HEADERS.items():
        req.add_header(k, v)
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"POST HTTP error {e.code}: {e.read().decode('utf-8', 'replace')}\n")
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write(f"POST request failed: {e.reason}\n")
        sys.exit(1)
    except json.JSONDecodeError:
        sys.stderr.write("POST response was not JSON.\n")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Insert DT machine info by IMEI.")
    parser.add_argument("--token", help="Login token. (required, from get_token.py).")
    parser.add_argument("--imei", required=True, help="Device IMEI.")
    parser.add_argument("--company", default="第一拖拉机股份有限公司",
                        help="Company name (looked up in dbx).")
    parser.add_argument("--model", default="LP2204-C",
                        help="Model name (looked up in dbx).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Build body without POSTing.")
    args = parser.parse_args()

    token = args.token
    if not token:
        sys.stderr.write("Missing token. Pass --token.\n")
        sys.exit(1)

    company = lookup_company(args.company)
    model_info = lookup_model(company["id"], args.model)

    body = dict(DEFAULT_BODY)
    body["imei"] = args.imei
    body["factoryNumber"] = gen_factory_number()
    body["productionDate"] = datetime.now().strftime("%Y-%m-%d")
    body["company"] = company["name"]
    body["companyId"] = company["id"]
    body["model"] = model_info["model"]
    body["modelId"] = model_info["modelId"]
    body["categoryId1"] = model_info["categoryId1"]
    body["categoryId2"] = model_info["categoryId2"]
    body["categoryId3"] = model_info["categoryId3"]
    body["categoryName3"] = model_info["categoryName3"]

    if args.dry_run:
        print("[DRY-RUN] Would POST to %s" % INSERT_URL)
        print(json.dumps(body, ensure_ascii=False, indent=2))
        sys.exit(0)

    result = post_insert(token, body)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
