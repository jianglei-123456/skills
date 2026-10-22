# dt-sale-update — DT 销售信息更新

按 SKU 解析终端型号/品目，把一台或多台 IMEI 的销售时间、通讯服务期与归属企业（iot 字段 `ownerCompany`）更新到 DT 平台（`updateSaleInformation`）。**必须显式调用本 skill**（如 `/dt-sale-update`）才会运行，不响应任何自然语言触发。

## 术语

| 术语 | iot 字段 | 脚本参数 | 说明 |
|---|---|---|---|
| **归属企业** | `ownerCompany` / `ownerCompanyId` | `--owner-company` | 设备归属/销售主体，可给简称，从 `basic.company` 模糊匹配出全名与 id |
| **产品 SKU** | `sku` | `--sku` | 从 `contract.product` 取 `typeId1/2/3`、`terminalName`、`terminalModel` |

## 前置条件

| 项 | 要求 | 检查命令 |
|---|---|---|
| Python 3 | 3.10+（仅标准库） | `python --version` |
| dbx CLI | 已安装（Node 18.18+） | `dbx --version` |
| dbx 连接 A | `prod_192.168.5.129_dss_owner`（dss 库） | `dbx connections list` |
| dbx 连接 B | `prod_192.168.5.17_machine`（machine 库） | `dbx connections list` |
| 环境变量 | `DT_USERNAME`、`DT_PASSWORD` | 见下 |

一条命令检查全部前置条件（只报状态，不输出凭据值）：

```bash
python "E:/Dev/jianglei/skills/dt-sale-update/scripts/check_env.py"
```

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `DT_USERNAME` | 是 | 登录用户名 |
| `DT_PASSWORD` | 是 | 登录密码 |

> token 不是用户提供的变量：`get_token.py` 用上述凭据登录后取得，再通过 `--token` 传给后续脚本。

```powershell
$env:DT_USERNAME = "你的用户名"
$env:DT_PASSWORD = "你的密码"
```

## dbx 连接配置

两个连接缺一不可（在 **DBX Desktop** 中创建，agent 不会也不能创建连接）：

| 配置项 | 连接 A（dss） | 连接 B（machine） |
|---|---|---|
| 名称（Name） | `prod_192.168.5.129_dss_owner` | `prod_192.168.5.17_machine` |
| 类型（Type） | PostgreSQL | PostgreSQL |
| 主机（Host） | `192.168.5.129` | `192.168.5.17` |
| 端口（Port） | `5432` | `19990` |
| 数据库（Database） | `dss` | `machine` |

> 名称必须完全一致（脚本按名查找）；端口不要用默认 5432 套到 machine 上。

### 涉及的表

| 连接 | 表 | 用途 |
|---|---|---|
| dss | `contract.product` | 按 `sku` 查 `type_id1/2/3`、`product_name`、`product_type`（过滤 `is_deleted = 0`） |
| machine | `basic.company` | 按名字（或简称）查 `id`、`name` |

## 使用流程

> 由 AI 代理执行；人工只需提供输入并在预览后确认。

### 第 1 步：确认输入

| 输入 | 必填 | 示例 |
|---|---|---|
| IMEI 列表 | 是 | `650200496009244,650200496009245` |
| SKU | 是 | `AA000002` |
| 目标归属企业 | 是（可给简称） | `抉择` |
| 销售日期 | 否（默认今天） | `2026-10-08` |

### 第 2 步：环境检查

```bash
python "E:/Dev/jianglei/skills/dt-sale-update/scripts/check_env.py"
```

### 第 3 步：获取 token

```bash
TOKEN=$(python "E:/Dev/jianglei/skills/dt-sale-update/scripts/get_token.py")
```

### 第 4 步：预查询并展示（只读，等待确认）

```bash
python "E:/Dev/jianglei/skills/dt-sale-update/scripts/preview.py" \
  --token "$TOKEN" --imeis "650200496009244,650200496009245" \
  --sku AA000002 --owner-company "抉择" --date 2026-10-08
```

输出包含：合同产品（typeId/terminalName/terminalModel）、归属企业全名与 id、每台设备的当前归属企业/sku/销售时间/服务期、最终 JSON、结论（`[OK]` / `[ABORT]`）。**必须等待用户确认。**

### 第 5 步：执行更新（写入）

```bash
python "E:/Dev/jianglei/skills/dt-sale-update/scripts/update_sale.py" \
  --token "$TOKEN" --imeis "650200496009244,650200496009245" \
  --sku AA000002 --owner-company "抉择" --date 2026-10-08 --yes
```

- `--yes` 表示用户已确认；缺失时脚本拒绝写入。
- `--dry-run` 只打印每台 body，不发起请求。
- 逐台串行提交，首个失败即停止，并输出 `updated / failed / skipped`。

### 第 6 步：验证

```bash
python "E:/Dev/jianglei/skills/dt-sale-update/scripts/query_by_imei.py" \
  --token "$TOKEN" --imei 650200496009244
```

核对 `ownerCompany`、`sku`、`sellTime`、`commServiceBeginDate/EndDate`。

## 请求体

固定 13 个字段；`ownerCompanyTypeCode` / `ownerCompanyTypeName` 不传。

| 字段 | 来源 |
|---|---|
| `imei` | 用户输入（逐台） |
| `sku` | 用户输入 |
| `typeId1/2/3` | `contract.product.type_id1/2/3` |
| `terminalName` | `contract.product.product_name` |
| `terminalModel` | `contract.product.product_type` |
| `ownerCompany` / `ownerCompanyId` | `basic.company.name` / `.id` |
| `sellTime` / `sendTime` / `commServiceBeginDate` | `--date`（默认今天）`00:00:00` |
| `commServiceEndDate` | +1 个自然年（2/29 → 2/28） |

## 脚本清单

| 脚本 | 用途 | 只读/写入 |
|---|---|---|
| `check_env.py` | 环境检查（dbx、变量、两个连接） | 只读 |
| `get_token.py` | 登录拿 token | 只读 |
| `query_by_imei.py` | 查设备信息 | 只读 |
| `common.py` | dbx 查询、产品/企业解析、body 组装、日期工具 | 只读 |
| `preview.py` | 预查询并展示最终 JSON | 只读 |
| `update_sale.py` | 逐台提交更新 | 写入 |

## 故障排查

- **`[ENV FAIL]`**：按 FAIL 项逐条修复（安装 dbx / 设置变量 / 建连接）。
- **`[ABORT] sku ... not found`**：该 SKU 不在 `contract.product`（或 `is_deleted = 1`），确认 SKU。
- **`[ABORT] company ... not found`**：企业名不在 `basic.company`，确认企业全名。
- **`[ABORT] company ... matches N rows`**：简称命中多个不同名的企业，按列出的候选（含 `status`）改用更精确的名称。
- **同名企业多条**（`basic.company` 常见：一条 `status=10` 正常 + 一条 `status=-10` 停用）：自动取正常的一条并在预览中注明「同名多条，已取 status=10」。
- **`[未查到设备记录]`**：该 IMEI 在 DT 平台无记录，流程仍会按 body 写入（可能直接创建）。
- **`update_sale.py` 报业务失败**：脚本会打印该台的完整响应 JSON；修正后从失败的那台重跑（已成功的可去掉）。
