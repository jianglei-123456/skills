#!/usr/bin/env python3
"""Update user info for a device (final step).

Body is just {"imei": "..."}. Called after the three install-insert
endpoints, with a 5s delay after the previous step (see --delay).

    python update_user_info.py --token "$TOKEN" --imei YS0285093740549 [--delay 5]
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error

UPDATE_URL = "https://ss-iot.dtwl360.com/api/usersUser/updateUserInfo"

HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "User-Agent": "PostmanRuntime-ApipostRuntime/1.1.0",
}


def post_update(token: str, imei: str) -> dict:
    data = json.dumps({"imei": imei}).encode("utf-8")
    req = urllib.request.Request(UPDATE_URL, data=data, method="POST")
    for k, v in HEADERS.items():
        req.add_header(k, v)
    # Sample curl uses a bare {{token}} placeholder (no "Bearer " prefix).
    req.add_header("Authorization", token)
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
    parser = argparse.ArgumentParser(description="Update user info by IMEI.")
    parser.add_argument("--token", help="Login token. (required, from get_token.py).")
    parser.add_argument("--imei", required=True, help="Device IMEI.")
    parser.add_argument("--delay", type=float, default=0,
                        help="Seconds to wait before POSTing (5s after the previous step).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the request, but do not POST.")
    args = parser.parse_args()

    token = args.token
    if not token:
        sys.stderr.write("Missing token. Pass --token.\n")
        sys.exit(1)

    if args.dry_run:
        print("[DRY-RUN] Would POST to %s with {\"imei\":\"%s\"}" % (UPDATE_URL, args.imei))
        sys.exit(0)

    if args.delay > 0:
        print(f"[WAIT] Sleeping {args.delay}s before final update...")
        time.sleep(args.delay)

    result = post_update(token, args.imei)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
