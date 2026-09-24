# dt-iot-import

外部 IoT 数据导入技能：解析 Excel 结构 → 构建字段映射 → 用户评审 → 调用 DT 生产接口
`POST https://dss.datian360.com/prod_api/schedule/job/externalIotImport/import` 入库 iot 表。

按照 [Agent Skills](https://agentskills.io) 开放格式编写，仓库级位置 `.agents/skills/`（Codex
等支持该约定的 Agent 可直接发现；CodeBuddy 通过 `.codebuddy/skills/dt-iot-import` 指针入口使用）。

## 前置条件

- Python 3 + `openpyxl`、`requests`（均已安装于当前环境）
- 环境变量 `DT_USERNAME` / `DT_PASSWORD`（生产平台账号，脚本自动登录换 token；**禁止硬编码 token**）
- 命令均在仓库根目录执行

## 快速用法

```bash
# 1. 解析 Excel 结构（sheet / 表头行 / 前几行内容）
python .agents/skills/dt-iot-import/scripts/inspect_excel.py --file "E:/tmp/农机具信息表(6).xlsx"

# 2. （Agent 按 SKILL.md Step 2 构建 mapping，经用户评审后）试跑校验，不写库
python .agents/skills/dt-iot-import/scripts/import_iot.py \
  --file "E:/tmp/农机具信息表(6).xlsx" --sheet 1 --header-row 1 --source HD \
  --mapping '{"imei":"终端主机编号*","factory":"终端生产厂家*", ...}' --no-db

# 3. 去掉 --no-db 正式导入
```

完整流程与评审要求见 [SKILL.md](SKILL.md)。

## 目录结构

```
dt-iot-import/
├── SKILL.md                    # Agent 流程（Step 1-5 + 字段表 + 失败处置表）
├── scripts/
│   ├── inspect_excel.py        # 解析 Excel 结构（只读）
│   ├── import_iot.py           # 上传导入（写生产；--no-db 可试跑）
│   └── dss_auth.py             # 登录换 token（逻辑取自 py-company/tools/dss_auth.py）
└── README.md
```

## 注意

- **整文件校验**：任意一行有错 → 全部拒绝、不入库；同批 imei 重导是覆盖更新
- 数据行上限 5000；`source` 必须显式传（HD/XX/LS/BD 或空串），服务端对 null 会 NPE
- 若单元格为公式且无缓存值，`inspect_excel.py` 可能读为空——请在 Excel 另存为值后重试
- 失败时完整明细写入 `<Excel同目录>/<文件名>_failDetail.json`
