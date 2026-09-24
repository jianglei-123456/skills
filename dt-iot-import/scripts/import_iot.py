#!/usr/bin/env python3
"""外部 IoT 数据导入：上传 Excel + 字段映射到 /job/externalIotImport/import。

命令在仓库根目录执行，例如：

    python .agents/skills/dt-iot-import/scripts/import_iot.py \
      --file "E:/tmp/农机具信息表(6).xlsx" --sheet 1 --header-row 1 --source HD \
      --mapping '{"imei":"终端主机编号*", ...}'

说明：
- --mapping 为 JSON 字符串，也支持 @mapping.json 从文件读取
- --source 必传（HD/XX/LS/BD；无需前缀传空串）。服务端对 null 会 NPE
- --no-db 只校验不入库（可作导入前试跑）；默认 db=true、pushMq=false
- token 默认由环境变量 DT_USERNAME / DT_PASSWORD 登录换取，--token 可覆盖
- 退出码：0=导入成功；1=失败（失败明细完整写入 <Excel同目录>/<文件名>_failDetail.json）
"""

import argparse
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dss_auth import get_token_from_env

IMPORT_URL = "https://dss.datian360.com/prod_api/schedule/job/externalIotImport/import"
TIMEOUT = 600          # 请求超时（秒）；服务端逐行校验+翻译，行多时耗时较长
FAIL_PREVIEW = 50      # stdout 上展示的失败明细条数上限

REQUIRED_FIELDS = {
    "imei": "机具编号",
    "factory": "终端生产厂家",
    "customerName": "服务主体",
    "company": "农机生产厂家",
    "category": "品目",
    "saleProvince": "销售省",
    "saleCity": "销售市",
    "saleCounty": "销售县",
}
OPTIONAL_FIELDS = {
    "factoryNumber": "出厂编号",
    "model": "型号",
    "engineNumber": "发动机编号",
    "licensePlate": "车牌",
    "installDate": "安装日期",
    "dischargeName": "排放标准",
    "saleTown": "销售镇",
    "driverName": "机手姓名",
    "driverPhone": "机手电话",
    "customerPhone": "手机号",
}


def die(msg: str) -> None:
    sys.stderr.write(msg + "\n")
    sys.exit(1)


def load_mapping(raw: str) -> dict:
    if raw.startswith("@"):
        path = raw[1:]
        if not os.path.isfile(path):
            die(f"mapping 文件不存在: {path}")
        with open(path, encoding="utf-8-sig") as f:
            raw = f.read()
    try:
        mapping = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"mapping 不是合法 JSON: {e}")
    if not isinstance(mapping, dict) or not mapping:
        die("mapping 必须是非空 JSON 对象（字段名 -> 表头名）")

    missing = [f"{k}({REQUIRED_FIELDS[k]})" for k in REQUIRED_FIELDS
               if not str(mapping.get(k) or "").strip()]
    if missing:
        die("mapping 缺少必填字段: " + "、".join(missing))
    blank_optional = [f"{k}({OPTIONAL_FIELDS[k]})" for k in OPTIONAL_FIELDS
                      if k in mapping and not str(mapping[k]).strip()]
    if blank_optional:
        sys.stderr.write("提示: 以下可选字段值为空，将按未映射处理: "
                         + "、".join(blank_optional) + "\n")
    unknown = [k for k in mapping if k not in REQUIRED_FIELDS and k not in OPTIONAL_FIELDS]
    if unknown:
        sys.stderr.write("提示: 以下键不是接口字段，服务端会忽略: " + "、".join(unknown) + "\n")
    return mapping


def describe_fail(detail: dict) -> str:
    parts = []
    if detail.get("rowNo"):
        parts.append(f"rowNo={detail['rowNo']}")
    if detail.get("imei"):
        parts.append(f"imei={detail['imei']}")
    parts.append(f"字段: {detail.get('field') or '-'}")
    parts.append(str(detail.get("reason") or ""))
    return " | ".join(parts)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="外部 IoT 数据导入（Excel + mapping -> /job/externalIotImport/import）")
    parser.add_argument("--file", required=True, help="Excel 文件路径（.xlsx / .xls）")
    parser.add_argument("--mapping", required=True, help="映射 JSON；@文件 形式从文件读取")
    parser.add_argument("--source", required=True,
                        help="imei 前缀来源：HD/XX/LS/BD；无需前缀传空串 \"\"")
    parser.add_argument("--header-row", type=int, default=3, help="表头行号（1 开始，默认 3）")
    parser.add_argument("--start-row", type=int, help="数据起始行（1 开始，默认表头行+1）")
    parser.add_argument("--sheet", type=int, default=1, help="工作表序号（1 开始，默认 1）")
    parser.add_argument("--no-db", action="store_true", help="只校验不入库（试跑用）")
    parser.add_argument("--push-mq", action="store_true", help="入库同时推送 MQ（默认不推）")
    parser.add_argument("--token", help="现成 token（缺省用环境变量自动登录获取）")
    args = parser.parse_args()

    path = args.file
    if not os.path.isfile(path):
        die(f"文件不存在: {path}")
    if not path.lower().endswith((".xlsx", ".xls")):
        die("仅支持 .xlsx / .xls 文件")
    if args.header_row < 1:
        die("--header-row 必须大于 0")
    start_row = args.start_row if args.start_row else args.header_row + 1
    if start_row <= args.header_row:
        die("--start-row 必须大于 --header-row")

    mapping = load_mapping(args.mapping)
    if args.source is None:
        die("--source 不能为 None")

    token = args.token
    if not token:
        try:
            token = get_token_from_env()
        except RuntimeError as e:
            die(str(e))

    db_flag = not args.no_db
    print(f"文件: {path}")
    print(f"参数: sheet={args.sheet} | headerRowNo={args.header_row} | startRow={start_row} "
          f"| source={args.source!r} | db={str(db_flag).lower()} | pushMq={str(args.push_mq).lower()}")
    print(f"mapping: {json.dumps(mapping, ensure_ascii=False)}")
    print("token: 已获取" if token else "token: 缺失")

    data = {
        "mapping": json.dumps(mapping, ensure_ascii=False),
        "source": args.source,
        "headerRowNo": str(args.header_row),
        "startRow": str(start_row),
        "sheetNo": str(args.sheet),
        "db": str(db_flag).lower(),
        "pushMq": str(args.push_mq).lower(),
    }
    headers = {"Authorization": token}

    t0 = time.time()
    try:
        with open(path, "rb") as f:
            resp = requests.post(
                IMPORT_URL, headers=headers, data=data,
                files={"file": (os.path.basename(path), f, "application/octet-stream")},
                timeout=TIMEOUT)
    except Exception as e:
        die(f"请求失败: {e}")
    elapsed = time.time() - t0

    print(f"HTTP {resp.status_code} | 耗时 {elapsed:.1f}s")
    try:
        body = resp.json()
    except ValueError:
        die("响应不是 JSON（前 500 字符）: " + resp.text[:500].replace("\n", " "))

    code = body.get("code")
    msg = body.get("msg")
    payload = body.get("data")
    print(f"业务码: code={code} | msg={msg}")

    if not isinstance(payload, dict):
        die("导入失败：响应中没有结果数据（参数或权限问题，见上方 msg）")

    success = bool(payload.get("success"))
    total = payload.get("total")
    ok_count = payload.get("successCount")
    fails = payload.get("failDetail") or []

    print(f"结果: success={str(success).lower()} | 总行数 {total} | 成功 {ok_count}")

    if success:
        sys.exit(0)

    if fails:
        fail_path = os.path.splitext(path)[0] + "_failDetail.json"
        try:
            with open(fail_path, "w", encoding="utf-8") as f:
                json.dump(fails, f, ensure_ascii=False, indent=2)
            print(f"失败明细 {len(fails)} 条（完整明细: {fail_path}）:")
        except OSError as e:
            print(f"失败明细 {len(fails)} 条（写入明细文件失败: {e}）:")
        for detail in fails[:FAIL_PREVIEW]:
            print("  " + describe_fail(detail))
        if len(fails) > FAIL_PREVIEW:
            print(f"  ... 其余 {len(fails) - FAIL_PREVIEW} 条见明细文件")
    sys.exit(1)


if __name__ == "__main__":
    main()
