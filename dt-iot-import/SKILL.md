---
name: dt-iot-import
description: "外部 IoT 数据导入：解析 Excel 结构、构建字段映射，经用户评审后调用 DT 平台 /job/externalIotImport/import 写入生产 iot 表。仅显式调用，评审通过前不发起任何写入。"
disable-model-invocation: true
---

# 外部 IoT Excel 导入

把外部渠道（HD / XX / LS / BD）的农机具信息表 Excel 导入 DT 生产环境 iot 表。

- 接口：`POST https://dss.datian360.com/prod_api/schedule/job/externalIotImport/import`（multipart：Excel 文件 + `mapping` JSON；网关前缀 `schedule` 转发到 dss-job 服务）
- 服务端整文件校验：**任意一行有错 → 全部拒绝、不入库**；数据行上限 **5000**；按 imei 插入或覆盖更新
- 命令均在 **仓库根目录**（dss 项目根）执行；脚本目录：`.agents/skills/dt-iot-import/scripts/`

**评审闸门（铁律）**：Step 3 未经用户明确确认，不得运行 Step 4 的导入。

流程：解析结构 → 构建映射 → 用户评审 → 执行导入 → 结果处理

## 前置条件

环境变量 `DT_USERNAME` / `DT_PASSWORD`（生产平台账号，导入脚本自动登录换 token）。token 只存在于内存与请求头，禁止写入任何文件或输出。

## Step 1 解析 Excel 结构

```bash
python .agents/skills/dt-iot-import/scripts/inspect_excel.py --file "<Excel路径>" [--sheet N] [--rows 5]
```

输出每个工作表：有效行列数、前几行内容（带引号、空白可见）、表头行/数据起始行建议、非空数据行数。

完成标准：确定 ①目标 sheet ②表头行号与数据起始行 ③表格每一列与下方字段表的对应关系。多工作表逐个处理，每表一套 mapping 与参数。

## Step 2 构建 mapping 与参数

mapping 的键 = 字段名；值 = Excel 表头文字（服务端 trim 后逐字匹配）。

| 键 | 中文名 | 必填 | 样例表头（按实际表头逐字取值） |
|---|---|---|---|
| `imei` | 机具编号 | ✓ | `终端主机编号*` / `机具识别器号*` |
| `factory` | 终端生产厂家 | ✓ | `终端生产厂家*` |
| `customerName` | 服务主体 | ✓ | `服务主体名称*` |
| `company` | 农机生产厂家 | ✓ | `农机生产厂家*` / `农具生产厂家*` |
| `category` | 品目 | ✓ | `农机品目*` / `农具品目*` |
| `saleProvince` | 销售省 | ✓ | `所在省/自治区/直辖市*` |
| `saleCity` | 销售市 | ✓ | `所在地市/州/盟*` |
| `saleCounty` | 销售县 | ✓ | `所在区/县市/旗*` |
| `factoryNumber` | 出厂编号 | | `农机出厂编号*` / `农具出厂编号*` |
| `model` | 型号 | | `农机型号*` / `农具型号*` |
| `engineNumber` | 发动机编号 | | `发动机编号` |
| `licensePlate` | 车牌 | | `农机车牌*` |
| `installDate` | 安装日期 | | `终端安装日期*` |
| `dischargeName` | 排放标准 | | `排放标准`（国三/国四） |
| `saleTown` | 销售镇 | | `所在乡镇/街道*` |
| `driverName` | 机手姓名 | | `机手姓名*` |
| `driverPhone` | 机手电话 | | `机手电话*` |
| `customerPhone` | 手机号 | | `服务主体手机号` |

规则：

- 值为表头原文，照抄 inspect 输出中带引号的文字（如 `"农机品目*"` 必须带 `*`）；接口未用到的列（如 所在村/社区、作业类型）不放进 mapping
- 8 个必填键缺一不可；缺任何一个 → 停止并告知用户 Excel 缺少对应列
- `source` 必传（`HD`/`XX`/`LS`/`BD`；确实不需要前缀时传空字符串）：imei 不以 source 开头时服务端自动补前缀（HD 会把补前缀后的值转大写）。服务端对 null 会 NPE，必须显式给值
- headerRowNo / startRow / sheetNo 用 Step 1 的结论

完成标准：mapping 覆盖全部 8 个必填键，且每个值都能在表头行中找到。

## Step 3 用户评审（闸门）

向用户展示以下内容，等待明确确认（"可以 / 执行 / OK"）：

- **文件 / sheet / headerRowNo / startRow / 非空数据行数**（>5000 提示需拆分）
- **mapping 对照表**：每行 = 字段键 ← Excel 表头（标注必填/可选）
- **source 及 imei 补齐示例**：取第 1 行真实值演示，如 `10BA58FC → HD10BA58FC`
- **db / pushMq 开关**：是否入库、是否推 MQ

用户提出任何修改 → 回到 Step 2 重新构建。**未确认不得进入 Step 4。**

## Step 4 执行导入

```bash
python .agents/skills/dt-iot-import/scripts/import_iot.py \
  --file "<Excel路径>" --sheet 1 --header-row 1 --source HD \
  --mapping '{"imei":"终端主机编号*", ...}'
```

- `--mapping` 也支持 `@mapping.json` 从文件读取
- 想先验证不写数据：加 `--no-db` 试跑（服务端完成全部校验与翻译，但不入库、不推 MQ；通过后去掉 `--no-db` 重跑）
- 入库同时推 MQ 加 `--push-mq`（默认不推）
- `--token` 可传现成 token（默认环境变量自动登录）

完成标准：退出码 0（= 接口 success=true）；失败时得到完整失败明细（脚本打印前 50 条，完整明细文件路径在输出中）。

## Step 5 结果处理

按失败明细逐条处置：

| 失败原因（示例） | 处置 |
|---|---|
| `机具编号不能为空` 等必填为空 | 补 Excel 对应单元格 |
| `未找到对应的公司: X` | X 与平台企业库不匹配；改用平台登记的企业名称 |
| `未找到品目或品目层级不完整: X` | 品目名需能匹配平台三级品目（如 `拖拉机`、`旋耕机`） |
| `未找到地区: X`（销售省/市/县） | 地区名需逐级匹配平台行政区域 |
| `表头中未找到字段[X]对应的列: Y` | mapping 值与表头不一致；照抄带引号的表头原文（含 `*`）后重设该键 |
| `未读取到表头行，请检查 headerRowNo 参数` | headerRowNo 与真实表头行不符；回到 Step 1 确认 |
| `数据行数超过 5000 行限制` | 拆成多个文件分批导入 |

处理完所有错误后（修 Excel 或修 mapping）→ 回到 Step 3 重新评审，不得跳过。

导入成功即已写生产库；同批 imei 重复导入为覆盖更新，不产生重复行。
