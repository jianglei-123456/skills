# dt-owner-modify — 大田修改机主

给定一批 IMEI 和目标机主，把 machine 库 `ysb.install_iot_owner.customer_id` 改成目标
`ysb.customer.id`，再逐台调用 DSS 同步接口（`/dtwl/sales/install/pushData`，与
`push_ysb.py` 相同），把变更推到平台。

## 前置

- `dbx` CLI，连接 `prod_192.168.5.17_machine`（需允许写）
- 环境变量 `DT_USERNAME` / `DT_PASSWORD`

```bash
python scripts/check_env.py
```

## 用法

```bash
# 1) 预查询（只读）—— 把输出给用户看，确认后再往下走
python scripts/preview.py --imeis "871126596485125,864924075165940" --owner "姜雷"

# 2) 拿 token
TOKEN=$(python scripts/get_token.py)

# 3) 执行（改库 + 同步）
python scripts/update_owner.py --imeis "871126596485125,864924075165940" \
  --owner "姜雷" --token "$TOKEN" --yes
```

`--owner` 可给 `ysb.customer.id`（如 `6236`）或名称（全名/部分名称，模糊匹配）。
未加 `--yes` 只做校验、不写库。
