#!/usr/bin/env python3
"""Fetch the DT platform login token.

Reads username/password from environment variables (DT_USERNAME, DT_PASSWORD),
calls the login endpoint, and prints the token. Designed to be piped into the
next step of the cabin-modify flow, e.g.:

    TOKEN=$(python get_token.py)
"""

import os
import sys
import json
import urllib.request
import urllib.error

LOGIN_URL = "https://dss.datian360.com/prod_api/auth/v1/login"

# Mobile/WeChat browser UA, matching the original curl request.
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 "
    "Mobile/15E148 Safari/604.1 wechatdevtools/1.06.2412050 "
    "MicroMessenger/8.0.5 Language/zh_CN webview/"
)

# Credential environment variable names. Override by exporting these first.
ENV_USERNAME = "DT_USERNAME"
ENV_PASSWORD = "DT_PASSWORD"


def get_token(username: str, password: str) -> str:
    payload = {
        "username": username,
        "password": password,
        "sysFlag": 5,
        "type": 3,
    }
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(LOGIN_URL, data=data, method="POST")
    req.add_header("Connection", "keep-alive")
    req.add_header("Authorization", "")
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("content-type", "application/json")
    req.add_header("Accept", "*/*")
    req.add_header("Sec-Fetch-Site", "cross-site")
    req.add_header("Sec-Fetch-Mode", "cors")
    req.add_header("Sec-Fetch-Dest", "empty")

    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"Login HTTP error {e.code}: {e.read().decode('utf-8', 'replace')}\n")
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write(f"Login request failed: {e.reason}\n")
        sys.exit(1)

    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        sys.stderr.write(f"Login response was not JSON:\n{body}\n")
        sys.exit(1)

    # Pull the token. Real shape: data.result.access_token.
    token = (
        result.get("data", {}).get("result", {}).get("access_token")
        or result.get("data", {}).get("access_token")
        or result.get("access_token")
        or result.get("token")
    )
    if not token:
        sys.stderr.write(f"Login succeeded but no token found in response:\n{json.dumps(result, ensure_ascii=False, indent=2)}\n")
        sys.exit(1)

    return token


def main() -> None:
    username = os.environ.get(ENV_USERNAME)
    password = os.environ.get(ENV_PASSWORD)
    if not username or not password:
        sys.stderr.write(
            f"Missing credentials. Export {ENV_USERNAME} and {ENV_PASSWORD} first.\n"
            f"  export {ENV_USERNAME}='<your-username>'\n"
            f"  export {ENV_PASSWORD}='<your-password>'\n"
        )
        sys.exit(1)

    token = get_token(username, password)
    # Print ONLY the token so it can be captured: TOKEN=$(python get_token.py)
    print(token)


if __name__ == "__main__":
    main()
