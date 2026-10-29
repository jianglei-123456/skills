# 开发环境

本仓库各 skill 依赖的工具与运行时。每个条目：它是什么、在这里干什么、怎么装。

## 数据库

### DBX CLI — 命令行工具

数据库命令行工具 `dbx`（npm 包名 `@dbx-app/cli`）。用纯 bash 访问数据库已有的命名连接：列出连接、查看表与字段、执行只读查询、输出可直接喂给模型的 schema 上下文，不依赖 MCP。

- 在本仓库的作用：`dbx`、`dt-cabin-modify`、`dt-sale-update`、`ysb-data-export` 等 skill 都通过它查库。
- 文档：https://dbxio.com/en/docs/getting-started ｜ 仓库：https://github.com/t8y2/dbx
- 安装：`npm install -g @dbx-app/cli`（npm 启动器需 Node.js 18.18.0+，原生二进制本身不需要 Node）
- 备选：`brew tap t8y2/tap && brew install dbx-cli`；或 GitHub Release 里 `packages-v*` 的独立二进制（Windows 为 `dbx-cli-win32-x64.zip`）
- 验证：`dbx doctor`、`dbx connections list`
- 注意：连接不在 CLI 里创建，CLI 只使用已存在的连接名。

### DBX Desktop — 桌面客户端（DBX client）

同一项目的开源、轻量桌面数据库客户端（图形界面），用来管理连接、浏览表、直接执行 SQL。CLI 与它共用同一份连接存储；`open`、`dbml`、`docs` 以及部分数据库类型需要它的本地 bridge 在运行，否则 CLI 会报 `DBX_NOT_RUNNING`。

- 在本仓库的作用：数据库连接在这里创建和维护（agent 不会也不能创建连接）；bridge 未启动时依赖它的命令会失败。
- 官网：https://dbxio.com ｜ 下载：https://github.com/t8y2/dbx/releases
- 安装（Windows）：`winget install t8y2.dbx`，或 `scoop bucket add dbx https://github.com/t8y2/scoop-bucket && scoop install dbx`，或从 Releases 下 `.msi` 安装包
- 其他平台：macOS `brew install --cask dbx`；Linux 可用 Flatpak；多人共享可自托管 Web 版（Docker）
- 验证：启动后 `dbx doctor` 里 bridge 相关字段正常，`dbx connections list` 能看到连接
