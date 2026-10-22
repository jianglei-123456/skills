---
name: dt-sale-update
description: "DT 销售信息更新：按 SKU 在 dss.contract.product 查终端型号/品目，把一台或多台 IMEI 的销售时间、通讯服务期、归属企业（iot 字段 ownerCompany）更新到 DT 平台（updateSaleInformation）。归属企业只给简称也能查出全名与 id。NOT auto-triggered by natural language — invoke this skill explicitly (e.g. /dt-sale-update) before running any of its scripts."
argument-hint: "IMEI（可多个）、SKU、目标归属企业（可选销售日期）"
---

# DT 销售信息更新

按 SKU 与目标归属企业，更新一台或多台 IMEI 设备在 DT 平台上的**销售信息**（销售/发货时间、通讯服务期、归属企业、终端型号）。只接受**显式调用**，不响应任何自然语言触发。

## 术语

| 术语 | iot 字段 | 脚本参数 | 说明 |
|---|---|---|---|
| 归属企业 | `ownerCompany` / `ownerCompanyId` | `--owner-company` | 设备的归属/销售主体，可给简称，脚本到 `basic.company` 模糊匹配出全名与 id |
| 产品 SKU | `sku` | `--sku` | 到 `contract.product` 取 `typeId1/2/3`、`terminalName`、`terminalModel` |

## 输入

| 输入 | 必填 | 示例 |
|---|---|---|
| IMEI 列表 | 是 | `650200496009244,650200496009245` |
| SKU | 是 | `AA000002` |
| 目标归属企业 | 是（可给简称） | `抉择` → `阜阳市抉择农机销售有限公司` |
| 销售日期 | 否（默认今天） | `--date 2026-10-08` |

## Step 0: 环境检查

```bash
python "E:/Dev/jianglei/skills/dt-sale-update/scripts/check_env.py"
```

检查 dbx CLI、`DT_USERNAME`/`DT_PASSWORD`、两个 dbx 连接（`prod_192.168.5.129_dss_owner`、`prod_192.168.5.17_machine`）。只输出 PASS/FAIL，**不输出凭据值**。任一 FAIL 即停止。

## Step 1: 获取 token

```bash
TOKEN=$(python "E:/Dev/jianglei/skills/dt-sale-update/scripts/get_token.py")
```

## Step 2: 预查询并展示（只读）

```bash
python "E:/Dev/jianglei/skills/dt-sale-update/scripts/preview.py" \
  --token "$TOKEN" \
  --imeis "650200496009244,650200496009245" \
  --sku AA000002 --owner-company "抉择" [--date 2026-10-08]
```

展示五段（全部只读）：

1. `[1] 合同产品` — `contract.product` 按 sku 取 `typeId1/2/3`、`terminalName`、`terminalModel`
2. `[2] 归属企业` — `basic.company` 精确匹配失败后退化为模糊匹配，显示全名与 id
3. `[3] 设备当前信息` — 逐台 `queryByImei`，显示现有归属企业/sku/sellTime/服务期；未查到的标注 `[未查到设备记录]`
4. `[4] 将提交的 JSON` — 实际请求体（每台仅 `imei` 不同）
5. `[5] 结论` — `[OK]` 或 `[ABORT]`（含候选企业列表）

**必须等用户确认后才进入 Step 3。**

## Step 3: 执行更新（写入）

```bash
python "E:/Dev/jianglei/skills/dt-sale-update/scripts/update_sale.py" \
  --token "$TOKEN" \
  --imeis "650200496009244,650200496009245" \
  --sku AA000002 --owner-company "抉择" [--date 2026-10-08] --yes
```

- 无 `--yes` 时拒绝写入（防止跳过确认）。
- 逐台串行 POST `updateSaleInformation`；**首个失败即停止**，打印各台 OK/FAIL 与 `updated / failed / skipped` 汇总。
- 任一台业务码非成功（`code` 不在 `0/200/20000` 或 `success=false`）即视为失败。

## Step 4: 验证（可选）

```bash
python "E:/Dev/jianglei/skills/dt-sale-update/scripts/query_by_imei.py" \
  --token "$TOKEN" --imei 650200496009244
```

核对 `ownerCompany`、`sku`、`sellTime`、`commServiceBeginDate/EndDate`。

## 请求体

固定 13 个字段，`ownerCompanyTypeCode` / `ownerCompanyTypeName` **不传**：

| 字段 | 来源 |
|---|---|
| `imei` | 用户输入（逐台） |
| `sku` | 用户输入 |
| `typeId1` / `typeId2` / `typeId3` | `contract.product.type_id1/2/3`（`is_deleted = 0`） |
| `terminalName` | `contract.product.product_name` |
| `terminalModel` | `contract.product.product_type` |
| `ownerCompany` / `ownerCompanyId` | `basic.company.name` / `.id` |
| `sellTime` / `sendTime` / `commServiceBeginDate` | `--date`（默认今天）`00:00:00` |
| `commServiceEndDate` | 起始日期 +1 个自然年（2/29 → 2/28） |

```json
{
  "sku": "AA000002",
  "imei": "650200496009244",
  "typeId1": 67, "typeId2": 1, "typeId3": 343,
  "sellTime": "2026-10-08 00:00:00",
  "sendTime": "2026-10-08 00:00:00",
  "ownerCompany": "阜阳市抉择农机销售有限公司",
  "terminalName": "北斗定位终端",
  "terminalModel": "DTBDT216N",
  "ownerCompanyId": 87531,
  "commServiceEndDate": "2027-10-08 00:00:00",
  "commServiceBeginDate": "2026-10-08 00:00:00"
}
```

## 中止条件

| 情况 | 行为 |
|---|---|
| sku 查不到 / 匹配多行 / 缺 `type_id*`、`product_name`、`product_type` | `[ABORT]`，不写入 |
| 企业 0 条 | `[ABORT]`，确认企业名 |
| 企业多条、名字全相同 | 自动取 `status = 10`（正常）的一条；若仍有多条则 `[ABORT]` |
| 企业多条、名字不同 | `[ABORT]`，列出候选（最多 20 条，含 status），要求更精确的名称 |
| 设备 `queryByImei` 查不到 | `[WARN]`，仍按 body 写入（接口可能直接创建记录） |
| 无 `--yes` | 拒绝写入 |

## 环境要求

- `DT_USERNAME` / `DT_PASSWORD`（登录凭据，仅脚本读取）
- `dbx` CLI + 两个连接：`prod_192.168.5.129_dss_owner`（dss）、`prod_192.168.5.17_machine`（machine）
- Python 3.10+（仅标准库）

## 脚本清单

| 脚本 | 用途 | 只读/写入 |
|---|---|---|
| `check_env.py` | 环境检查 | 只读 |
| `get_token.py` | 登录拿 token | 只读 |
| `query_by_imei.py` | 查设备信息 | 只读 |
| `common.py` | 共用：dbx 查询、产品/企业解析、body 组装、日期 | 只读 |
| `preview.py` | 预查询并展示最终 JSON | 只读 |
| `update_sale.py` | 逐台提交更新（`--dry-run` 只打印） | 写入 |
