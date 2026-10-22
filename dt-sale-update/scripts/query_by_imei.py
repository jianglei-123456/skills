#!/usr/bin/env python3
"""Query DT platform device info by IMEI (read-only).

Used by the sale-info update flow to show the device's current values and to
verify the result after the update.

    python query_by_imei.py --token "$TOKEN" --imei YS8182130683910
"""

import sys
import json
import argparse
import urllib.parse
import urllib.request
import urllib.error

QUERY_URL = "https://dss.datian360.com/prod_api/dtwl/iot/queryByImei"
USER_AGENT = "PostmanRuntime-ApipostRuntime/1.1.0"


def query_by_imei(token: str, imei: str) -> dict:
    url = f"{QUERY_URL}?imei={urllib.parse.quote(imei)}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "*/*")
    req.add_header("Accept-Encoding", "gzip, deflate, br")
    req.add_header("Authorization", token)
    req.add_header("Connection", "keep-alive")
    req.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"Query HTTP error {e.code}: {e.read().decode('utf-8', 'replace')}\n")
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write(f"Query request failed: {e.reason}\n")
        sys.exit(1)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        sys.stderr.write(f"Query response was not JSON:\n{body}\n")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Query DT device info by IMEI.")
    parser.add_argument("--token", required=True, help="Login token from get_token.py.")
    parser.add_argument("--imei", required=True, help="Device IMEI to look up.")
    args = parser.parse_args()

    result = query_by_imei(args.token, args.imei)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
