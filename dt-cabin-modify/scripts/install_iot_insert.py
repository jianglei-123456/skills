#!/usr/bin/env python3
"""Insert an install record for a device (write step, 1st of 3).

Body uses the reference sample verbatim except `imei`, which is replaced
with the user-provided value. Auth header is `Bearer <token>`.

    python install_iot_insert.py --token "$TOKEN" --imei YS0285093740549
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error

INSERT_URL = "https://dss.datian360.com/prod_api/dtbd/installIot/installIotInsert"

# Reference sample body (only imei is replaced).
DEFAULT_BODY = {
    "bn": "140617.2",
    "timestamp": 1787909566,
    "token": "6ba4d63bc4d616e2c017292b5d51d38574faf072",
    "terminal": 25,
    "_origin": 74,
    "user_key": "",
    "_zui": "da39a3ee5e6b4b0d3255bfef95601890afd80709",
    "submitFlag": 1,
    "origin": 1,
    "autoSave": 1,
    "typeId1": "67",
    "typeId2": "311",
    "typeId3": "353",
    "imei": "",  # replaced
    "terminalType": "A8",
    "userName": "姜雷",
    "thumb": "https://img4.nongji360.com/n/dv/2026/08/28173238378778.png",
    "installPositionThumb": "https://img4.nongji360.com/n/dv/2026/08/28173243493504.png",
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
    parser = argparse.ArgumentParser(description="Insert DT install record by IMEI.")
    parser.add_argument("--token", help="Login token. (required, from get_token.py).")
    parser.add_argument("--imei", required=True, help="Device IMEI (replaces sample imei).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the body, but do not POST.")
    args = parser.parse_args()

    token = args.token
    if not token:
        sys.stderr.write("Missing token. Pass --token.\n")
        sys.exit(1)

    body = dict(DEFAULT_BODY)
    body["imei"] = args.imei

    if args.dry_run:
        print("[DRY-RUN] Would POST to %s" % INSERT_URL)
        print(json.dumps(body, ensure_ascii=False, indent=2))
        sys.exit(0)

    result = post_insert(token, body)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
