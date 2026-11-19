# 开发环境（本机快照）

> 本机开发环境清单，换电脑时照着重新装一遍。与仓库里的工程代码无关。
> 记录日期：2026-11-19
> 每条只写三项：**定位**（干什么用）、**版本**、**下载来源**（去哪下、下哪个包）。路径不记——都是新装。

---

## 一、基础环境

### Shell — PowerShell 7（pwsh）

- 定位：主力交互 shell（Git Bash 保留给 POSIX 脚本和 skill 命令）。
- 版本：7.6.10
- 下载来源：https://github.com/PowerShell/PowerShell/releases → LTS 版 → `PowerShell-7.6.10-win-x64.msi`

---

## 二、开发环境

### Git

- 定位：版本控制，附带 Git Bash。
- 版本：2.55.0（Git for Windows）
- 下载来源：https://git-scm.com/download/win

### Node.js

- 定位：前端/CLI 工具的运行时；Node 由 fnm 安装和切换，不单独装 Node。
- 版本：fnm 1.39.0，Node v24.18.0（default + lts-latest）
- 下载来源：fnm https://github.com/Schniz/fnm/releases ｜ Node 由 fnm 安装（`fnm install --lts`），包来自 https://nodejs.org/en/download

### Python

- 定位：脚本与数据处理；另有 Python 3.11 和 Anaconda 备用。
- 版本：3.13.5
- 下载来源：https://www.python.org/downloads/windows/

### JDK

- 定位：Java 项目编译运行，三套版本按项目切换。
- 版本：8u202、17.0.16（Oracle）、22.0.1（GraalVM CE 24.0.1，基于 JDK 22）
- 下载来源：JDK 8 https://www.oracle.com/java/technologies/javase/javase8-archive-downloads.html ｜ JDK 17 https://www.oracle.com/java/technologies/javase/jdk17-archive-downloads.html ｜ GraalVM https://github.com/graalvm/graalvm-ce-builds/releases → `graalvm-community-jdk-22.0.1_windows-x64_bin.zip`

### Maven

- 定位：Java 项目构建。
- 版本：3.6.3
- 下载来源：https://archive.apache.org/dist/maven/maven-3/3.6.3/binaries/ → `apache-maven-3.6.3-bin.zip`

---

## 三、开发工具

### IntelliJ IDEA

- 定位：Java/Spring 项目的主力 IDE。
- 版本：2023.3.6（Community）；新装直接装最新版即可。
- 下载来源：https://www.jetbrains.com/idea/download/

### Lithe

- 定位：轻量 IDE，内存占用小，配合 AI 工具看代码用。
- 版本：Windows 桌面版（版本未记）
- 下载来源：https://lithe.top （Windows 提供 `setup.exe` 与 `zip`）

### Apipost

- 定位：接口调试与文档，跟 Apifox 同类，用来调 HTTP 接口。
- 版本：8.2.7
- 下载来源：https://www.apipost.cn/

### DBX CLI

- 定位：命令行访问 DBX 里已建好的数据库连接。
- 版本：0.4.132
- 下载来源：npm 全局包 `@dbx-app/cli` ｜仓库 https://github.com/t8y2/dbx

### DBX Desktop

- 定位：数据库图形客户端，连接在这里创建，CLI 共用。
- 版本：未记
- 下载来源：https://github.com/t8y2/dbx/releases

### codegraph

- 定位：代码智能索引 CLI，对已建 `.codegraph/` 索引的仓库做符号、调用链、影响面查询（本仓库的 codegraph / explain-logic skill 依赖它）。
- 版本：1.6.0
- 下载来源：npm 全局包 `@colbymchenry/codegraph`

### hurl

- 定位：纯文本格式的 HTTP 接口测试工具，用来跑 `.hurl` 用例。
- 版本：8.0.4
- 下载来源：npm 全局包 `@orangeopensource/hurl@8.0.4` ｜上游 https://hurl.dev

---

## 四、AI 工具

### 软件

#### CodeBuddy CLI

- 定位：AI 编码助手，本仓库的 skill 都通过它运行。
- 版本：2.185.0
- 下载来源：npm 全局包 `@tencent-ai/codebuddy-code`

#### dsh（DeepSeek Harness）

- 定位：DeepSeek 的编码智能体，命令行 `dsh` + 桌面版 dsh-desk。
- 版本：CLI 0.1.1-rc.2；桌面版未记（nightly 通道）
- 下载来源：CLI npm 全局包 `@deepseek-ai/dsh` ｜桌面版更新源 https://download.deepseek.com/dsh-desk/feeds/win-x64/

### 配置

#### 全局提示词 `CODEBUDDY.md`

换机时把下面这段整段拷到 `~/.codebuddy/CODEBUDDY.md`：

````markdown
# Global Agent Instructions

> **系统环境**：Windows 11 / 如果要调用windowsshell 使用PowerShell 7

## Codegraph

在已由 CodeGraph 索引的仓库（根目录存在 `.codegraph/` 目录），定位代码时优先使用 CodeGraph 而非 grep/find/search。
调用/codegraph获取命令指导
如果不存在 `.codegraph/` 目录，跳过 CodeGraph。

## DBX
如果想要操作数据库，使用/dbx获取数据库连接指导。

## Maven 编译 JDK 版本切换

当需要 Maven 编译 Java 项目时，按以下规则设置 JDK 版本环境变量：

### JDK 版本判定逻辑

- 检查项目 pom.xml 中的 `<java.version>` 属性

- `<java.version>` 为 8 或更低 → 使用 JDK8

- `<java.version>` 为 11 或更高 → 使用 JDK17

- 无法判断时，先试 JDK8，若编译失败再试 JDK17

### 环境变量设置命令
**在前台环境跑mvn编译，不要在后台执行环境中跑**

**JDK8**（适用于 pom.xml 中 java.version <= 8 的项目）:
```gitbash
export JAVA_HOME="/e/App/Java/jdk1.8.0_202"
export PATH="$JAVA_HOME/bin:$(echo "$PATH" | tr ':' '\n' | grep -v 'Java/jdk' | tr '\n' ':' | sed 's/:$//')"
```

```powershell
$env:JAVA_HOME = "E:\App\Java\jdk1.8.0_202"
$env:Path = "$env:JAVA_HOME\bin;" + ($env:Path -replace '.*?Java\\jdk[^;]*;', '')
```

**JDK17**（适用于 pom.xml 中 java.version >= 11 的项目）:
```gitbash
export JAVA_HOME="/e/App/Java/jdk-17.0.16"
export PATH="$JAVA_HOME/bin:$(echo "$PATH" | tr ':' '\n' | grep -v 'Java/jdk' | tr '\n' ':' | sed 's/:$//')"
```

```powershell
$env:JAVA_HOME = "E:\App\Java\jdk-17.0.16"
$env:Path = "$env:JAVA_HOME\bin;" + ($env:Path -replace '.*?Java\\jdk[^;]*;', '')
```
````

### skills

共 36 个，其中 35 个见 `~/.agents/.skill-lock.json`，1 个单独说明。

#### 本仓库（自建 skill） — `jianglei-123456/skills`（8 个）

- 仓库：https://github.com/jianglei-123456/skills
- 技能：`codegraph`、`dbx`、`dt-cabin-modify`、`dt-iot-import`、`dt-owner-modify`、`dt-sale-update`、`explain-logic`、`ysb-data-export`
- 注：仓库里还有 `codebuddy-session-summary`、`topic-note` 两个未安装。

#### mattpocock/skills（24 个）

- 仓库：https://github.com/mattpocock/skills
- 技能：`ask-matt`、`code-review`、`codebase-design`、`diagnosing-bugs`、`domain-modeling`、`grill-me`、`grill-with-docs`、`grilling`、`handoff`、`implement`、`improve-codebase-architecture`、`prototype`、`research`、`setup-matt-pocock-skills`、`tdd`、`teach`、`to-questionnaire`、`to-spec`、`to-tickets`、`triage`、`wait-what`、`wayfinder`、`wizard`、`writing-for-agents`

#### anthropics/skills（1 个）

- 仓库：https://github.com/anthropics/skills
- 技能：`frontend-design`

#### damusix/skills（1 个）

- 仓库：https://github.com/damusix/skills
- 技能：`hurl`

#### vercel-labs/skills（1 个）

- 仓库：https://github.com/vercel-labs/skills
- 技能：`find-skills`

#### browser-skill（1 个，不在 skill lock 里）

- 腾讯开源的浏览器代理（https://github.com/Tencent/BrowserSkill），让 agent 操作用户已登录的 Chrome/Edge。
- skill 本身不含 `bsk` CLI 和浏览器扩展，这两样要单独装；扩展由用户自己在浏览器里装。
- 两种装法（官方 AGENT_INSTALL.md）：
  - **CodeBuddy**：先装 CLI（PowerShell：`irm https://raw.githubusercontent.com/Tencent/BrowserSkill/main/install.ps1 | iex`），再 `bsk install-skill --harness <id>`（id 用 `bsk install-skill --list --json` 查）。
  - **dsh**：装官方插件 `dsh plugin --profile <profile> add @wxg-prc-cpg/browser-skill-dsh-plugin`，插件已自带 skill，不必再跑 `bsk install-skill`。
