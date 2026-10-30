---
name: dt-owner-modify
description: "大田修改机主：给一批 IMEI 与目标机主，在 machine 库核对设备机主记录（ysb.install_iot_owner）与新机主（ysb.customer），把 customer_id 改为新机主 id，再逐台调用 DSS 同步接口（pushData，同 push_ysb）。必须先在 preview 里确认，再加 --yes 执行。NOT auto-triggered by natural language — invoke this skill explicitly (e.g. /dt-owner-modify) before running any of its scripts."
argument-hint: "IMEI（可多个）、新机主（id 或名称）"
---

# 大田修改机主

把一台或多台设备的**机主**（`ysb.install_iot_owner.customer_id`）改成指定客户，然后调用 DSS 同步接口把变更推到平台。只接受**显式调用**，不响应任何自然语言触发。

## 术语

| 术语 | 库字段 | 脚本参数 | 说明 |
|---|---|---|---|
| 机主表 | `ysb.install_iot_owner` | — | 一个 IMEI 只有一条 `is_deleted = 0` 的有效行（库上有唯一索引 `idx_install_iot_owner_unique_on_active`） |
| 机主 | `customer_id` | `--owner` | 指向 `ysb.customer.id`；可给 id，也可给全名/部分名称 |
| 新机主 | `ysb.customer` | `--owner` | 只接受 `status = 10`（正常）的客户 |
| 分发商 | `install_iot_owner.distributor_id` | — | 与 `ysb.customer.company_ids` 关联；同名机主多条时用它做优先匹配 |
| 机主所属分发商 | `ysb.customer.company_ids` | — | 客户归属的分发商 id（文本，可能多个） |

## 输入

| 输入 | 必填 | 示例 |
|---|---|---|
| IMEI 列表 | 是 | `871126596485125,864924075165940` |
| 新机主 | 是（id 或名称，可部分） | `6236` / `姜雷` → id=6236 |

## Step 0: 环境检查

```bash
python "E:/Dev/jianglei/skills/dt-owner-modify/scripts/check_env.py"
```

检查 dbx CLI、`DT_USERNAME`/`DT_PASSWORD`、连接 `prod_192.168.5.17_machine`、两张 ysb 表可读。只输出 PASS/FAIL，**不输出凭据值**。任一 FAIL 即停止。

## Step 1: 预查询并展示（只读）

```bash
python "E:/Dev/jianglei/skills/dt-owner-modify/scripts/preview.py" \
  --imeis "871126596485125,864924075165940" --owner "姜雷"
```

展示五段（全部只读，不调 DSS）：

1. `[1] 新机主` — `ysb.customer` 按 id / 精确名 / 模糊名解析，显示 id、名称、status；同名多条时按设备 `distributor_id` 命中 `company_ids` 选取，并在 `注:` 里说明
2. `[2] 机主表核对` — 逐台查 `install_iot_owner`（`is_deleted = 0`），显示现机主 id/名称、`distributor` → 目标机主；未找到或已一致的单列标注
3. `[3] 将执行的 SQL` — 实际 UPDATE 语句（含 `returning`）
4. `[4] DSS 同步` — 接口地址与请求体
5. `[5] 结论` — `[OK]` 或 `[ABORT]`

**必须把这段输出给用户看，等用户明确确认后才进入 Step 2。**

## Step 2: 获取 token

```bash
TOKEN=$(python "E:/Dev/jianglei/skills/dt-owner-modify/scripts/get_token.py")
```

## Step 3: 执行（写入）

```bash
python "E:/Dev/jianglei/skills/dt-owner-modify/scripts/update_owner.py" \
  --imeis "871126596485125,864924075165940" --owner "姜雷" --token "$TOKEN" --yes
```

- 无 `--yes` 时拒绝写入（防止跳过确认）。
- 顺序：**先登录拿 token**（拿不到就整体中止，避免改了库却推不了同步）→ 单条 UPDATE（`--allow-writes`）→ 回读校验 → 逐台 POST 同步。
- 输出 `individual OK/FAIL` + `updated / unchanged / missing / synced` 汇总；回读不一致或同步失败时退出码 1。
- `--dry-run` 只打印 SQL 与同步调用，不写库、不联网。

## 实际执行的 SQL

```sql
update ysb.install_iot_owner
   set customer_id = <新机主 id>,
       update_time = now()
 where is_deleted = 0
   and imei in ('<每台 IMEI>')
returning id, imei, customer_id
```

只改 `customer_id` 与 `update_time`；`distributor_id`、`customer_origin`、`submit_flag`、`update_user_id` 保持原值。

## DSS 同步

同 `push_ysb.py`：逐台一次 POST，`Authorization` 直接放 token（不带 `Bearer`）。

```http
POST https://dss.datian360.com/prod_api/dtwl/sales/install/pushData
Content-Type: application/json
Authorization: <token>

{"imei": "871126596485125"}
```

HTTP 200 且有业务码时校验 `code ∈ {0, 200, 20000}` 且 `success != false`；失败条目记录后继续下一台（库已改，不回滚）。

## 中止条件

| 情况 | 行为 |
|---|---|
| 新机主 0 条 | `[ABORT]`，确认名称或改用 id |
| 新机主多条同名 | 优先取 `company_ids` 含设备 `distributor_id` 的一条；未命中则任取一条（`status = 10` 优先），并在 `注:` 中写明取了哪个 id |
| 新机主多条不同名 | 同样先按 `distributor_id` 命中 `company_ids`；仍未命中才 `[ABORT]`，列出候选（最多 20 条，含 status / 设备数 / company_ids） |
| 新机主 `status != 10`（如 -10 停用） | `[ABORT]`，拒绝写入 |
| IMEI 在机主表中无有效行 | `[WARN]`，跳过该台，其余继续 |
| 所有 IMEI 都已一致 / 都不存在 | `[ABORT]`，无事可做 |
| 无 `--yes` | 拒绝写入 |
| token 获取失败 | 未写库即退出 |

## 环境要求

- `DT_USERNAME` / `DT_PASSWORD`（登录凭据，仅脚本读取）
- `dbx` CLI + 连接 `prod_192.168.5.17_machine`（库 `machine`，schema `ysb`）
- 该连接必须允许写入（脚本带 `--allow-writes`）
- Python 3.10+（仅标准库）

## 脚本清单

| 脚本 | 用途 | 只读/写入 |
|---|---|---|
| `check_env.py` | 环境检查 | 只读 |
| `get_token.py` | 登录拿 token | 只读 |
| `common.py` | 共用：dbx 查询、机主解析、SQL 组装 | 只读 |
| `preview.py` | 预查询并展示将执行的 SQL | 只读 |
| `update_owner.py` | 改库 + 回读校验 + DSS 同步（`--dry-run` 只打印） | 写入 |
