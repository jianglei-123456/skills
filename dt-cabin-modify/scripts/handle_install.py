#!/usr/bin/env python3
"""Query install info by IMEI, and delete it if a record exists.

Step 4 of the cabin-modify flow. If the install view endpoint returns a
record, POST to the delete endpoint. If nothing is found, skip the delete
(and the flow proceeds to whatever step comes next).

    python handle_install.py --token "$TOKEN" --imei YS0285093740549

Exit codes: 0 = done (deleted or nothing to delete), 1 = request error.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse

VIEW_URL = "https://dss.datian360.com/prod_api/dtwl/sales/install/view"
DELETE_URL = "https://dss.datian360.com/prod_api/dtwl/sales/install/deleteInstallIot"

# Browser-like headers from the reference curl.
HEADERS = {
    "Sec-GPC": "1",
    "sec-ch-ua-platform": '"Windows"',
    "Referer": "",
    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138"',
    "sec-ch-ua-mobile": "?0",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "DNT": "1",
}


def http_get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    for k, v in HEADERS.items():
        req.add_header(k, v)
    req.add_header("Authorization", token)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"GET HTTP error {e.code}: {e.read().decode('utf-8', 'replace')}\n")
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write(f"GET request failed: {e.reason}\n")
        sys.exit(1)
    except json.JSONDecodeError:
        sys.stderr.write(f"GET response was not JSON.\n")
        sys.exit(1)


def http_post_json(url: str, token: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in HEADERS.items():
        req.add_header(k, v)
    req.add_header("Authorization", token)
    req.add_header("Content-Type", "application/json;charset=UTF-8")
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
        sys.stderr.write(f"POST response was not JSON.\n")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="View/delete install info by IMEI.")
    parser.add_argument("--token", help="Login token. (required, from get_token.py).")
    parser.add_argument("--imei", required=True, help="Device IMEI.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen, but do not call delete.")
    parser.add_argument("--no-delete", action="store_true",
                        help="Only report the install record; never delete it.")
    args = parser.parse_args()

    token = args.token
    if not token:
        sys.stderr.write("Missing token. Pass --token.\n")
        sys.exit(1)

    url = f"{VIEW_URL}?imei={urllib.parse.quote(args.imei)}"
    resp = http_get_json(url, token)

    result = resp.get("data", {}).get("result")
    if not result:
        print("[SKIP] No install record found for imei=%s. Nothing to delete." % args.imei)
        sys.exit(0)

    print("[FOUND] Install record exists for imei=%s" % args.imei)
    if args.no_delete:
        print("[NO-DELETE] --no-delete set: skipping delete, record kept.")
        sys.exit(0)
    if args.dry_run:
        print("[DRY-RUN] Would POST to %s with {\"imei\":\"%s\"}" % (DELETE_URL, args.imei))
        sys.exit(0)

    del_resp = http_post_json(DELETE_URL, token, {"imei": args.imei})
    print(json.dumps(del_resp, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
