---
name: dt-owner-modify
description: "大田修改机主/经销商：给一批 IMEI 与目标机主（可再加目标经销商），在 machine 库核对机主与客户，改 install_iot_owner.customer_id/distributor_id、install_iot.company_id/install_distributor_company_id、install_iot_machine.distributor_id，以及归属企业 machine.iot.owner_company_id/owner_company（119 MySQL 源库必须先改，再改 17 PG public.iot 副本），最后逐台调用 DSS 同步接口（pushData，同 push_ysb）。必须先在 preview 里确认，再加 --yes 执行。NOT auto-triggered by natural language — invoke this skill explicitly (e.g. /dt-owner-modify) before running any of its scripts."
argument-hint: "IMEI（可多个）、新机主（id 或名称）、新经销商（可选，id 或名称）"
---

# 大田修改机主 / 经销商

把一台或多台设备的**机主**（`ysb.install_iot_owner.customer_id`）改成指定客户；若同时给经销商，则把 6 处经销商/归属企业字段一并改成该企业，然后调用 DSS 同步接口把变更推到平台。只接受**显式调用**，不响应任何自然语言触发。

> **归属企业（owner_company）存在于两个库**：`119 MySQL machine.iot` 是源库，`17 PG public.iot` 是它的副本、会被平台反向同步覆盖。**必须先改 119，再改 17**；只改 17 会在几秒后被旧值回写，且回读 17 当时可能仍显示"已改"而误判成功。核验必须两个库都查。

## 术语与字段

| 术语 | 库字段 | 参数 | 说明 |
|---|---|---|---|
| 机主表 | `ysb.install_iot_owner` | — | 一个 IMEI 只有一条 `is_deleted = 0` 的有效行（唯一索引 `idx_install_iot_owner_unique_on_active`） |
| 机主 | `install_iot_owner.customer_id` → `ysb.customer.id` | `--owner` | 可给 id，也可给全名/部分名称；只接受 `ysb.customer.status = 10` |
| 经销商 | `basic.company.id/name` | `--distributor` | 只接受 `basic.company.status = 10`；名称从 basic.company 取 |
| 机主所属分发商 | `ysb.customer.company_ids` | — | 同名机主多条时用它优先匹配（见下） |

经销商要改的 6 个字段（按执行顺序）：

| # | 库 / 表 | 字段 |
|---|---|---|
| 1 | `machine.iot`（**119 MySQL**，`prod_192.168.5.119_machine`）— 归属企业**源库** | `owner_company_id` + `owner_company`（名称） |
| 2 | `ysb.install_iot_owner`（17 PG） | `distributor_id` |
| 3 | `ysb.install_iot`（17 PG） | `company_id` |
| 4 | `ysb.install_iot`（17 PG） | `install_distributor_company_id` |
| 5 | `ysb.install_iot_machine`（17 PG） | `distributor_id` |
| 6 | `public.iot`（17 PG）— **119 的副本**，写入后会被平台同步对齐 | `owner_company_id` + `owner_company`（名称） |

不再修改 dss 的 `contract.iot`。

## 输入

| 输入 | 必填 | 示例 |
|---|---|---|
| IMEI 列表 | 是 | `673555585146926,673555585138721` |
| 新机主 | 是（id 或名称） | `7219` / `安徽省农垦集团淮南农场有限公司` |
| 新经销商 | 否（id 或名称） | `14756` / `寿县大唐农机销售有限公司` |

## Step 0: 环境检查

```bash
python "E:/Dev/jianglei/skills/dt-owner-modify/scripts/check_env.py"
```

检查 dbx CLI、`DT_USERNAME`/`DT_PASSWORD`、连接 `prod_192.168.5.17_machine`（PG）与 `prod_192.168.5.119_machine`（MySQL）、两张 ysb 表与 `machine.iot` 可读。只输出 PASS/FAIL，**不输出凭据值**。任一 FAIL 即停止。

## Step 1: 预查询并展示（只读）

```bash
python "E:/Dev/jianglei/skills/dt-owner-modify/scripts/preview.py" \
  --imeis "673555585146926,673555585138721" \
  --owner "安徽省农垦集团淮南农场有限公司" --distributor "寿县大唐农机销售有限公司"
```

展示七段（全部只读，不调 DSS）：

1. `[1] 新机主` — 解析结果（id / 名称 / status），同名多条时写明按哪个 distributor 命中
2. `[2] 新经销商` — 解析结果（来自 `basic.company`）
3. `[3] 机主表核对` — 逐台现机主，以及该台**仍未一致的经销商字段**
4. `[4] 将执行的 SQL` — machine 库单条多表语句
5. `[5] 将执行的 SQL` — 119 MySQL `machine.iot`（仅给了经销商时）
6. `[6] DSS 同步` — 接口与请求体
7. `[7] 结论` — `[OK]` 或 `[ABORT]`

**必须把这段输出给用户看，等用户明确确认后才进入 Step 2。**

## Step 2: 获取 token

```bash
TOKEN=$(python "E:/Dev/jianglei/skills/dt-owner-modify/scripts/get_token.py")
```

## Step 3: 执行（写入）

```bash
python "E:/Dev/jianglei/skills/dt-owner-modify/scripts/update_owner.py" \
  --imeis "673555585146926,673555585138721" \
  --owner "安徽省农垦集团淮南农场有限公司" --distributor "寿县大唐农机销售有限公司" \
  --token "$TOKEN" --yes
```

- 无 `--yes` 时拒绝写入（防止跳过确认）。
- 顺序：**先登录拿 token**（拿不到就整体中止，避免改了库却推不了同步）→ **119 MySQL `machine.iot`** → 17 machine 库单条多表语句（ysb 四表 + `public.iot`）→ 回读全部字段（含 119）校验 → 逐台 POST 同步。119 必须先写，否则 17 的改动会被平台按旧值回写。
- 17 machine 库的 4 张表在执行后按表打印命中行数，未命中的 IMEI 会列出；119 侧打印 MySQL 的 `Rows matched / Changed`。
- 回读不一致、119 写入失败或同步失败时退出码 1。
- `--dry-run` 只打印 SQL 与同步调用，不写库、不联网。

## 实际执行的 SQL

machine 库（一条语句，四张表；仅给经销商时）：

```sql
with o as (
    update ysb.install_iot_owner
       set customer_id = <机主 id>, distributor_id = <经销商 id>, update_time = now()
     where is_deleted = 0 and imei in (...)
    returning imei
), i as (
    update ysb.install_iot
       set company_id = <经销商 id>, install_distributor_company_id = <经销商 id>, update_time = now()
     where is_deleted = 0 and imei in (...)
    returning imei
), m as (
    update ysb.install_iot_machine
       set distributor_id = <经销商 id>, update_time = now()
     where is_deleted = 0 and imei in (...)
    returning imei
), p as (
    update public.iot
       set owner_company_id = <经销商 id>, owner_company = '<经销商名称>'
     where imei in (...)
    returning imei
)
select 'owner' as tbl, imei from o
union all select 'install', imei from i
union all select 'machine', imei from m
union all select 'iot', imei from p
```

119 MySQL 库（**先执行**，归属企业源库）：

```sql
update machine.iot
   set owner_company_id = <经销商 id>, owner_company = '<经销商名称>'
 where imei in (...)
```

17 PG 的 `public.iot` 是它的副本：脚本随后写一次，平台同步也会把 119 的值对齐过来。核验时两个库都要查，只有 17 通过不算成功。

只改机主（不给 `--distributor`）时仍是单表单条：

```sql
update ysb.install_iot_owner
   set customer_id = <机主 id>, update_time = now()
 where is_deleted = 0 and imei in (...)
returning id, imei, customer_id
```

## DSS 同步

同 `push_ysb.py`：逐台一次 POST，`Authorization` 直接放 token（不带 `Bearer`）。

```http
POST https://dss.datian360.com/prod_api/dtwl/sales/install/pushData
Content-Type: application/json
Authorization: <token>

{"imei": "673555585146926"}
```

HTTP 200 且有业务码时校验 `code ∈ {0, 200, 20000}` 且 `success != false`；失败条目记录后继续下一台（库已改，不回滚）。

## 中止条件

| 情况 | 行为 |
|---|---|
| 新机主 0 条 | `[ABORT]`，确认名称或改用 id |
| 新机主多条同名 | 优先取 `company_ids` 含**目标经销商 id**（未给则用设备当前 distributor_id）的一条；未命中则任取一条，并在 `注:` 写明 |
| 新机主多条不同名 | 先按经销商命中 `company_ids`；仍未命中才 `[ABORT]`，列出候选（含 status / 设备数 / company_ids） |
| 新机主 `status != 10` | `[ABORT]`，拒绝写入 |
| 119 MySQL 写入失败 | 打印 `[WARN]`，仍继续 17 与同步，退出码 1（此时 17 的归属可能被回写，须重跑） |
| 经销商 0 条 / 多条无法唯一确定 | `[ABORT]`，列出候选，要求改用 id |
| IMEI 在机主表中无有效行 | `[WARN]`，跳过该台，其余继续 |
| 所有 IMEI 都已一致 / 都不存在 | `[ABORT]`，无事可做 |
| 无 `--yes` | 拒绝写入 |
| token 获取失败 | 未写库即退出 |

## 环境要求

- `DT_USERNAME` / `DT_PASSWORD`（登录凭据，仅脚本读取）
- `dbx` CLI + 连接 `prod_192.168.5.17_machine`（PG machine）与 `prod_192.168.5.119_machine`（MySQL machine，改经销商时需要）
- 两个连接都必须允许写入（脚本带 `--allow-writes`）
- Python 3.10+（仅标准库）

## 脚本清单

| 脚本 | 用途 | 只读/写入 |
|---|---|---|
| `check_env.py` | 环境检查 | 只读 |
| `get_token.py` | 登录拿 token | 只读 |
| `common.py` | 共用：多表状态读取、机主/经销商解析、SQL 组装 | 只读 |
| `preview.py` | 预查询并展示将执行的两段 SQL（119 MySQL + 17 machine） | 只读 |
| `update_owner.py` | 改库（119 MySQL → 17 machine）+ 回读校验（两库）+ DSS 同步 | 写入 |
