# dt-cabin-modify — DT 座舱信息修改

修改 DT 平台（dss.datian360.com / ss-iot.dtwl360.com）上某 IMEI 设备的归属企业（iot 字段 `ownerCompany`，原称"生产企业"），并重建安装/农机/机主信息。**必须显式调用本 skill**（如 `/dt-cabin-modify`）才会运行，不响应任何自然语言触发。

## 概念澄清

| 术语 | iot 字段 | 脚本参数 | 说明 |
|---|---|---|---|
| **归属企业**（原"生产企业"） | `ownerCompany` / `ownerCompanyId` | `--owner-company` | 设备的归属/销售主体，从 `basic.company` 按名字查 id/name |
| **农机企业**（保持不变） | `company` | `--company` | 农机（机具）关联企业，用于按该企业的 `company_id` 查 `model.model` 型号 |

> 历史命名：**归属企业**此前被称为"生产企业"，现已澄清更名，含义不变；脚本/接口中的参数名（`--owner-company`、`ownerCompany*` 字段）和 `ownerCompanyTypeName` 的接口值"生产企业"均属于既有契约，保持不变。

## 前置条件

| 项 | 要求 | 检查命令 |
|---|---|---|
| Python 3 | 已安装（仅标准库，无第三方依赖） | `python --version` |
| dbx CLI | 已安装（Node 18.18+） | `dbx --version` |
| dbx 连接 | 名为 `prod_192.168.5.17_machine` 的连接存在 | `dbx connections list` |
| 环境变量 | `DT_USERNAME`、`DT_PASSWORD` 已设置 | 见下 |

一条命令检查全部前置条件（只报告状态/缺失项，不输出凭据值）：

```bash
python "E:/Dev/jianglei/skills/dt-cabin-modify/scripts/check_env.py"
```

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `DT_USERNAME` | 是 | 登录用户名 |
| `DT_PASSWORD` | 是 | 登录密码 |

> token 不是用户提供的环境变量：`get_token.py` 用 `DT_USERNAME`/`DT_PASSWORD` 登录后自动获取，再通过 `--token` 传给后续脚本。

设置方式（Windows PowerShell 7）：

```powershell
$env:DT_USERNAME = "你的用户名"
$env:DT_PASSWORD = "你的密码"
```

**安全说明**：凭据只存在于环境变量中，由脚本读取；`check_env.py` 只报告变量是否设置、不输出值，确保凭据不会进入对话上下文。

## dbx 连接配置（重点）

本 skill 需要 `dbx` 指向 **machine 库** 的连接，名称为 **`prod_192.168.5.17_machine`**。

### 检查你的连接

```bash
dbx connections list
```

### 连接不对 / 不存在时，改哪里

**1. 确认连接名**。连接在 **DBX Desktop** 中创建和管理（agent 不会也不能创建连接）。打开 DBX Desktop → Connections，新建或修改连接，设置如下：

| 配置项 | 值 |
|---|---|
| 名称（Name） | `prod_192.168.5.17_machine`（必须完全一致，脚本按此名查找） |
| 类型（Type） | PostgreSQL |
| 主机（Host） | `192.168.5.17` |
| 端口（Port） | `19990` |
| 数据库（Database） | `machine` |

> 常见错误：名称不一致（大小写/多空格）、端口填错（注意是 `19990` 不是默认 `5432`）、数据库名写错。

**2. 改完立即生效**。DBX Desktop 保存后，CLI 无需重启，直接重跑检查：

```bash
python "E:/Dev/jianglei/skills/dt-cabin-modify/scripts/check_env.py"
```

**3. 如果希望换用别的连接**（比如测试环境），不要改脚本里的名字，用环境变量覆盖：

```powershell
$env:DBX_CONNECTION = "你的其他连接名"
```

（脚本默认使用 `prod_192.168.5.17_machine`；DBX CLI 本身也支持用 `DBX_CONNECTION` 指定默认连接。）

### 涉及的表

| 表 | 用途 |
|---|---|
| `basic.company` | 按名字查归属企业 id/name（`select id,name from basic.company where name='...'`） |
| `model.model` | 按 company_id+model 查型号与品目（注意列名是下划线：`category_id1/2/3`、`class_name3`） |

## 正常使用流程

> 本 skill 由 AI 代理执行。以下为代理遵循的完整流程；人工只需提供第 1 步的输入并在第 4 步确认。

### 第 1 步：确认输入

向用户确认：

| 输入 | 必填 | 示例 |
|---|---|---|
| IMEI | 是 | `YS0285093740549` |
| 目标归属企业 | 是 | `潍坊市昱坤农业机械有限公司` |
| 农机企业 | 否（默认 `第一拖拉机股份有限公司`） | `潍坊市昱坤农业机械有限公司` |
| 农机型号 | 否（默认 `LP2204-C`） | `YK2004` |

> 农机企业/型号建议同时给出：写入②会按农机企业查型号（`model.model`），默认值仅在不指定时使用。

### 第 2 步：环境检查

```bash
python "E:/Dev/jianglei/skills/dt-cabin-modify/scripts/check_env.py"
```

检查 dbx CLI、`DT_USERNAME`/`DT_PASSWORD` 环境变量、dbx 连接 `prod_192.168.5.17_machine`。任一 FAIL 即停止，修复后重跑。

### 第 3 步：获取 token

```bash
TOKEN=$(python "E:/Dev/jianglei/skills/dt-cabin-modify/scripts/get_token.py")
```

从环境变量读取凭据登录，输出 `data.result.access_token`。

### 第 4 步：预查询并展示（只读，等待确认）

```bash
python "E:/Dev/jianglei/skills/dt-cabin-modify/scripts/preview.py" \
  --token "$TOKEN" --imei <IMEI> --owner-company "<目标归属企业>" \
  [--company "<农机企业>"] [--model "<农机型号>"]
```

展示以下数据，**必须等待用户确认后才能继续**：

- `[1] 设备当前信息` — 现有归属企业/型号/品目/terminal 等
- `[2] 目标归属企业` — `basic.company` 查出的 id/name
- `[3] 农机企业+型号` — `model.model` 查出的 id/categoryId1-3/class_name3
- `[4] 安装记录` — 是否有安装记录（全流程不再删除，只作展示）
- `[5] 决策汇总` — 是否需要更新、是否有中止条件

任何 `[ABORT]`（企业/型号未查到）出现时流程不得继续。

### 第 5 步：执行全流程（写入）

用户确认后：

```bash
python "E:/Dev/jianglei/skills/dt-cabin-modify/scripts/run_flow.py" \
  --token "$TOKEN" --imei <IMEI> --owner-company "<目标归属企业>" \
  [--company "<农机企业>"] [--model "<农机型号>"] --yes
```

`--yes` 表示用户已确认。流程内部会再跑一遍预查询，然后依次执行：

| 顺序 | 动作 |
|---|---|
| 1 | 更新销售信息：归属企业 + 时间字段（sellTime/sendTime/commServiceBeginDate=今天00:00:00，commServiceEndDate=3年后00:00:00） |
| 2 | 写入① installIotInsert（安装信息，body 示例 + 替换 imei） |
| 3 | 写入② installIotMachine（农机信息：dbx 查 company/model、随机 factoryNumber、productionDate=今天） |
| 4 | 写入③ installIotOwner（机主信息，body 示例 + 替换 imei） |
| 5 | 等待 5s → updateUserInfo |

任一步失败即停止。

### 第 6 步：验证

查询设备确认数据已落库（只读）：

```bash
python "E:/Dev/jianglei/skills/dt-cabin-modify/scripts/query_by_imei.py" \
  --token "$TOKEN" --imei <IMEI>
```

核对 `ownerCompany`、`model`、`sellTime`、`commServiceBeginDate/EndDate`。安装记录用只读方式确认：

```bash
python "E:/Dev/jianglei/skills/dt-cabin-modify/scripts/handle_install.py" \
  --token "$TOKEN" --imei <IMEI> --no-delete
```

> **注意**：验证安装记录必须带 `--no-delete`（只查不删）。全流程不删除安装记录。

### 完整示例

```bash
# 1. 环境检查
python "E:/Dev/jianglei/skills/dt-cabin-modify/scripts/check_env.py"

# 2. 登录
TOKEN=$(python "E:/Dev/jianglei/skills/dt-cabin-modify/scripts/get_token.py")

# 3. 预查询（展示后等用户确认）
python "E:/Dev/jianglei/skills/dt-cabin-modify/scripts/preview.py" \
  --token "$TOKEN" --imei YS0285093740549 \
  --owner-company "潍坊市昱坤农业机械有限公司" \
  --company "潍坊市昱坤农业机械有限公司" --model "YK2004"

# 4. 用户确认后执行
python "E:/Dev/jianglei/skills/dt-cabin-modify/scripts/run_flow.py" \
  --token "$TOKEN" --imei YS0285093740549 \
  --owner-company "潍坊市昱坤农业机械有限公司" \
  --company "潍坊市昱坤农业机械有限公司" --model "YK2004" --yes

# 5. 验证
python "E:/Dev/jianglei/skills/dt-cabin-modify/scripts/query_by_imei.py" \
  --token "$TOKEN" --imei YS0285093740549
```

## 脚本清单

| 脚本 | 用途 | 只读/写入 |
|---|---|---|
| `check_env.py` | 环境检查（dbx/变量/连接） | 只读 |
| `get_token.py` | 登录拿 token | 只读 |
| `query_by_imei.py` | 查设备信息 | 只读 |
| `preview.py` | 预查询全部数据并展示 | 只读 |
| `update_sale_info.py` | 更新归属企业/时间 | 写入 |
| `handle_install.py` | 查安装记录（`--no-delete` 只查不删） | 默认只读 |
| `install_iot_insert.py` | 写入① 安装信息 | 写入 |
| `install_iot_machine_insert.py` | 写入② 农机信息 | 写入 |
| `install_iot_owner_insert.py` | 写入③ 机主信息 | 写入 |
| `update_user_info.py` | 最终 updateUserInfo（前置 5s 等待） | 写入 |
| `run_flow.py` | 全流程串联（无删除步骤） | 写入 |

## 故障排查

- **`[ENV FAIL]`**：按 `check_env.py` 输出的 FAIL 项逐条修复（安装 dbx / 设置变量 / 建连接）。
- **`[ABORT] 企业不存在`**：目标企业不在 `basic.company` 中，流程中止，确认企业名。
- **`[ABORT] 型号不存在`**：型号不在 `model.model`（按农机企业的 company_id 查），确认农机企业和型号。
- **`未找到该终端的用户绑定关系`**（最后一步）：该终端无用户绑定记录，属正常提示，非错误。
