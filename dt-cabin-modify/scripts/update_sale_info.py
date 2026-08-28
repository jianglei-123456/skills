#!/usr/bin/env python3
"""Update DT cabin sale information for a device (Step 3).

Flow:
  1. Query device by IMEI (reuse query_by_imei.py logic).
  2. Look up the new owner company id/name in the machine DB via dbx.
  3. Decide whether to update:
       - query found AND ownerCompany has a value AND ownerCompany != new name
         -> update
       - query NOT found (empty) -> update using the default template body
       - query found AND ownerCompany already equals new name -> skip (no-op)
       - company name not found in DB -> abort with error
  4. POST updateSaleInformation with the recomputed body.

Usage:
    python update_sale_info.py --token "$TOKEN" --imei <imei> \
        --owner-company "新疆中昆天拖重工有限公司"

The owner company name is what the user said to change it to.
"""

import os
import sys
import json
import subprocess
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timedelta

UPDATE_URL = "https://dss.datian360.com/prod_api/dtwl/updateSaleInformation"
DBX_CONN = "prod_192.168.5.17_machine"
USER_AGENT = "PostmanRuntime-ApipostRuntime/1.1.0"

# Default update body — fields the user did NOT ask to change use these
# literal values (from the reference curl example). Overridden below.
DEFAULT_BODY = {
    "sku": "A8010003",
    "typeId1": 67,
    "typeId2": 311,
    "typeId3": 353,
    "sellTime": "",            # -> now
    "sendTime": "",            # -> now
    "terminalSn": "",
    "ownerCompany": "",        # -> from dbx
    "terminalName": "车载智能座舱（前装整车版）",
    "terminalModel": "HTSPBDS2.0.1",
    "ownerCompanyId": 0,       # -> from dbx
    "commServiceEndDate": "",  # -> now + 3 years
    "commServiceBeginDate": "",  # -> now
    "ownerCompanyTypeCode": 20,
    "ownerCompanyTypeName": "生产企业",
    "terminalFactoryNumber": "",
}

# Fields we copy verbatim from the query result into the update body when the
# device was found (so we don't clobber existing data we don't intend to change).
COPY_FIELDS = [
    "sku", "typeId1", "typeId2", "typeId3", "terminalSn",
    "terminalName", "terminalModel", "ownerCompanyTypeCode",
    "ownerCompanyTypeName", "terminalFactoryNumber", "imei",
]


def today_str() -> str:
    """Current date with 00:00:00 time (the API truncates to day anyway)."""
    return datetime.now().strftime("%Y-%m-%d 00:00:00")


def plus_years_str(years: int) -> str:
    return (datetime.now() + timedelta(days=365 * years)).strftime("%Y-%m-%d 00:00:00")


def query_device(token: str, imei: str) -> dict | None:
    """Return the device result dict, or None if not found.

    Imports query_by_imei in-process to avoid subprocess encoding issues.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "query_by_imei",
        os.path.join(os.path.dirname(__file__), "query_by_imei.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        resp = mod.query_by_imei(token, imei)
    except SystemExit as e:
        sys.stderr.write(f"Query failed (exit {e.code}).\n")
        sys.exit(1)
    result = resp.get("data", {}).get("result")
    if not result:
        return None
    return result


def lookup_company(name: str) -> dict:
    """Look up company id/name in the machine DB. Abort if not found."""
    sql = f"select id,name from basic.company where name= '{name}';"
    # dbx is a shell shim (node wrapper), so resolve it through bash.
    # The SQL uses single quotes for the name; wrap the whole command in
    # double quotes for bash. Avoid json.dumps (it adds stray double quotes).
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
    rows = resp.get("rows", [])
    if not rows:
        sys.stderr.write(
            f"[ABORT] Company '{name}' not found in {DBX_CONN} basic.company. "
            f"No update performed.\n"
        )
        sys.exit(2)
    # dbx --json returns rows as objects: {"id":..., "name":...}
    first = rows[0]
    if isinstance(first, dict):
        return {"id": first.get("id"), "name": first.get("name")}
    # fallback: column-ordered list [id, name]
    return {"id": first[0], "name": first[1]}


def build_body(imei: str, company: dict, device: dict | None) -> dict:
    body = dict(DEFAULT_BODY)
    body["imei"] = imei
    # Recomputed fields.
    body["sellTime"] = today_str()
    body["sendTime"] = today_str()
    body["commServiceBeginDate"] = today_str()
    body["commServiceEndDate"] = plus_years_str(3)
    # Company from dbx.
    body["ownerCompany"] = company["name"]
    body["ownerCompanyId"] = company["id"]
    # When the device was found, copy current values so we don't overwrite
    # real data with the template defaults.
    if device:
        for f in COPY_FIELDS:
            if f in device and device[f] not in (None, ""):
                body[f] = device[f]
    return body


def post_update(token: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(UPDATE_URL, data=data, method="POST")
    req.add_header("Accept", "*/*")
    req.add_header("Accept-Encoding", "gzip, deflate, br")
    req.add_header("Authorization", token)
    req.add_header("Connection", "keep-alive")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"Update HTTP error {e.code}: {e.read().decode('utf-8', 'replace')}\n")
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write(f"Update request failed: {e.reason}\n")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Update DT cabin sale info by IMEI.")
    parser.add_argument("--token", help="Login token. (required, from get_token.py).")
    parser.add_argument("--imei", required=True, help="Device IMEI.")
    parser.add_argument("--owner-company", required=True,
                        help="New owner company name (what the user wants it changed to).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Build and print the update body, but do not POST.")
    args = parser.parse_args()

    token = args.token
    if not token:
        sys.stderr.write("Missing token. Pass --token.\n")
        sys.exit(1)

    device = query_device(token, args.imei)

    # Decision logic.
    if device is not None:
        current_owner = device.get("ownerCompany")
        if current_owner and current_owner == args.owner_company:
            print(f"[SKIP] ownerCompany already equals '{args.owner_company}'. No update performed.")
            sys.exit(0)
        # else: found and differs (or current empty) -> proceed
    # device is None (not found) -> proceed with template body

    company = lookup_company(args.owner_company)  # aborts if not found
    body = build_body(args.imei, company, device)

    if args.dry_run:
        print("[DRY-RUN] Update body that would be posted:")
        print(json.dumps(body, ensure_ascii=False, indent=2))
        sys.exit(0)

    print(f"[INFO] Posting update for imei={args.imei}, ownerCompany={company['name']} (id={company['id']})")
    result = post_update(token, body)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
