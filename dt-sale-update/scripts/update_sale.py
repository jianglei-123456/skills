#!/usr/bin/env python3
"""Update DT sale information for one or more IMEIs.

Builds the body from contract.product (dss) + basic.company (machine) and posts
updateSaleInformation sequentially. Requires --yes (the user must confirm the
preview first). Stops at the first failure and reports what was updated.

    python update_sale.py --token "$TOKEN" --imeis A,B \
        --sku AA000002 --owner-company "抉择" [--date 2026-10-08] --yes
"""

import sys
import json
import argparse
import urllib.request
import urllib.error

import common

UPDATE_URL = "https://dss.datian360.com/prod_api/dtwl/updateSaleInformation"
USER_AGENT = "PostmanRuntime-ApipostRuntime/1.1.0"
OK_CODES = {"0", "200", "20000"}


def post_update(token: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(UPDATE_URL, data=data, method="POST")
    req.add_header("Accept", "*/*")
    req.add_header("Accept-Encoding", "gzip, deflate, br")
    req.add_header("Authorization", token)
    req.add_header("Connection", "keep-alive")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def judge(resp) -> tuple[bool, str]:
    """Best-effort business-status judgement on an HTTP 200 response."""
    if not isinstance(resp, dict):
        return True, str(resp)[:200]
    code = resp.get("code", resp.get("status"))
    message = resp.get("message") or resp.get("msg") or ""
    ok = True
    if resp.get("success") is False:
        ok = False
    if code is not None and str(code) not in OK_CODES and resp.get("success") is not True:
        ok = False
    return ok, f"code={code} message={message}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Update DT sale info for IMEIs.")
    parser.add_argument("--token", required=True, help="Login token from get_token.py.")
    parser.add_argument("--imeis", required=True, help="One or more IMEIs, comma separated.")
    parser.add_argument("--sku", required=True, help="Product sku (e.g. AA000002).")
    parser.add_argument("--owner-company", required=True,
                        help="Owner company name, may be partial.")
    parser.add_argument("--date", help="Sale date YYYY-MM-DD (default: today).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the bodies and exit without posting.")
    parser.add_argument("--yes", action="store_true",
                        help="Confirm the user reviewed the preview; required to write.")
    args = parser.parse_args()

    imeis = common.parse_imeis(args.imeis)
    try:
        start = common.parse_day(args.date)
    except ValueError:
        sys.stderr.write(f"[ABORT] --date must be YYYY-MM-DD, got '{args.date}'\n")
        sys.exit(2)

    try:
        plan = common.build_plan(args.sku, args.owner_company, imeis, start)
    except common.AbortError as e:
        print(f"[ABORT] {e.message}")
        for line in e.details:
            print(f"        {line}")
        sys.exit(2)

    if args.dry_run:
        for imei, body in plan["bodies"]:
            print(f"[DRY-RUN] {imei}")
            print(json.dumps(body, ensure_ascii=False, indent=2))
        sys.exit(0)

    if not args.yes:
        sys.stderr.write(
            "[ABORT] refusing to write without --yes. Run preview.py, show the data "
            "to the user, then re-run with --yes.\n"
        )
        sys.exit(2)

    company = plan["company"]
    print(f"[INFO] ownerCompany={company['name']} (id={company['id']})  "
          f"sku={plan['product']['sku']}  date={start.isoformat()}  "
          f"devices={len(plan['bodies'])}")

    done, failed = [], []
    for idx, (imei, body) in enumerate(plan["bodies"], 1):
        prefix = f"[{idx}/{len(plan['bodies'])}] {imei}"
        try:
            resp = post_update(args.token, body)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            print(f"{prefix} -> FAIL  HTTP {e.code}: {detail}")
            failed.append(imei)
            break
        except urllib.error.URLError as e:
            print(f"{prefix} -> FAIL  request failed: {e.reason}")
            failed.append(imei)
            break

        ok, summary = judge(resp)
        print(f"{prefix} -> {'OK' if ok else 'FAIL'}  {summary}")
        if not ok:
            print(json.dumps(resp, ensure_ascii=False, indent=2))
            failed.append(imei)
            break
        done.append(imei)

    print("\n[SUMMARY]")
    print(f"    updated: {len(done)}/{len(plan['bodies'])}"
          + (f"  ({', '.join(done)})" if done else ""))
    if failed:
        remaining = [i for i, _ in plan["bodies"] if i not in done and i not in failed]
        print(f"    failed:  {', '.join(failed)}")
        if remaining:
            print(f"    skipped: {', '.join(remaining)}")
        sys.exit(1)
    print("    all devices updated.")


if __name__ == "__main__":
    main()
