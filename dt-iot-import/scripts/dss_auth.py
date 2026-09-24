#!/usr/bin/env python3
"""大田平台（dss.datian360.com）登录 token 获取模块。

从环境变量 DT_USERNAME / DT_PASSWORD 读取凭据，调用登录接口换取 access_token。
逻辑与请求头取自 py-company/tools/dss_auth.py，保持一致。
"""

import json
import os
import urllib.error
import urllib.request

LOGIN_URL = "https://dss.datian360.com/prod_api/auth/v1/login"

# 移动端/微信浏览器 UA，与原登录请求保持一致
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 "
    "Mobile/15E148 Safari/604.1 wechatdevtools/1.06.2412050 "
    "MicroMessenger/8.0.5 Language/zh_CN webview/"
)

ENV_USERNAME = "DT_USERNAME"
ENV_PASSWORD = "DT_PASSWORD"


def get_token(username: str, password: str) -> str:
    """用账号密码换取 token；任何失败都抛 RuntimeError（消息不含凭据）。"""
    payload = {
        "username": username,
        "password": password,
        "sysFlag": 5,
        "type": 3,
    }
    req = urllib.request.Request(
        LOGIN_URL, data=json.dumps(payload).encode("utf-8"), method="POST"
    )
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
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"登录 HTTP 错误 {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"登录请求失败: {e.reason}") from None

    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        raise RuntimeError(f"登录响应不是 JSON:\n{body}") from None

    # token 实际形态: data.result.access_token，兼容几种包装
    token = (
        result.get("data", {}).get("result", {}).get("access_token")
        or result.get("data", {}).get("access_token")
        or result.get("access_token")
        or result.get("token")
    )
    if not token:
        raise RuntimeError(
            "登录成功但响应中没有 token:\n"
            + json.dumps(result, ensure_ascii=False, indent=2)
        )
    return token


def get_token_from_env() -> str:
    """从环境变量读取凭据并获取 token；凭据缺失时抛 RuntimeError。"""
    username = os.environ.get(ENV_USERNAME)
    password = os.environ.get(ENV_PASSWORD)
    if not username or not password:
        raise RuntimeError(
            f"缺少环境变量 {ENV_USERNAME} / {ENV_PASSWORD}（生产平台登录凭据）"
        )
    return get_token(username, password)
