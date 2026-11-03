# npm 包（MCP 工具通道）发布与 CodeBuddy 注册全记录

> 产出时间：2026-11-03 · 验证等级：**L2/L4**（真实握手 + 真实工具调用，证据见 `docs/logs/phase1/npm-mcp/`）
> 适用对象：要在自己机器上用 `npx cubeone-mcp` / `vpx cubeone-mcp` 的人，以及要复现发布流程的维护者。
> **所有结论均为本机实测**（Windows 11 / npm 10.9.7 / vite+ 0.x / CodeBuddy CN），标注 ✅ 的都踩过实证。

---

## 0. 交付物是什么

`cubeone-mcp` 仓库本体（Skill + Python 脚本 + 文档 + CI）不变；npm 包是它的**MCP 工具通道**：

```
MCP 客户端（CodeBuddy / Claude Desktop / WorkBuddy…）
   └─ command: vpx（或 npx）        ← 包执行器，自动从 registry 拉包
       └─ node bin/cubeone-mcp.mjs  ← Node 版 stdio MCP server（薄封装层）
           └─ spawn python 脚本     ← 判据全部在这里（单写者边界，JS 侧不重实现）
               ├─ scripts/verify_generation.py   （G1 生成核验）
               ├─ scripts/ioc_backup.py          （备份 / 还原 / 清单）
               └─ scripts/ioc_field.py           （.ioc 键读 / 写）
```

- 包名：[`cubeone-mcp`](https://www.npmjs.com/package/cubeone-mcp)（未加 scope），版本与仓库对齐（首发 `0.6.0`）
- `files` 白名单只带 `bin/ lib/ scripts/*.py SKILL.md references/`——testbeds/docs **不进包**（`npm pack --dry-run` 实测 15 文件 / 63.4 kB）
- 三个 Python 脚本全是纯标准库 ⇒ 机器上只要有 **Python 3.11+**（`python` 在 PATH 或 `CUBEONE_PYTHON` 指定），**无需 pip install 任何东西**

### 工具清单（`tools/list` 实测 3 个）

| 工具 | 包装的脚本 | 写操作？ | read_only 下 |
|---|---|---|---|
| `verify_generation` | verify_generation.py（schema /2，7 项检查） | 否 | ✅ 可用 |
| `ioc_backup`（backup/restore/list） | ioc_backup.py | restore 是 | backup/list ✅；restore ❌ 拒绝 |
| `ioc_field`（get/set） | ioc_field.py | set 是 | get ✅；set 仅 `dry_run=true` |

**退出码 → isError 映射**（与脚本约定一致）：`0`=OK；`1`=域内结论（核验 FAIL / 键不存在，**isError=false**，结论看 structuredContent 的 JSON）；`2` 或 spawn 失败=执行层错误（isError=true）。JS 侧把 `spawnSync` 的 `status` 当退出码——**不是 `exitCode`**（那是异步 ChildProcess 的属性，✅ 实测踩过）。

**资源**：`resources/list` 暴露 `cubeone://docs/SKILL.md` 与 `cubeone://docs/references/*.md`（7 项），能力边界文档随包可读。

### 环境变量（注册条目的 `env`）

| 变量 | 作用 | 建议 |
|---|---|---|
| `CUBEONE_POLICY` | 写策略门禁：`read_only`（默认）/ `full` | 日常 read_only；要改 `.ioc` 时升级 full 并重启客户端 |
| `CUBEONE_ALLOWED_ROOTS` | 路径前缀白名单，`;` 分隔（与 `ST_CUBEMX_ALLOWED_ROOTS` 同构） | 至少覆盖工程所在盘根，如 `D:\Projects` |
| `CUBEONE_PYTHON` | Python 解释器绝对路径；缺省回退 `python` | PATH 里有 python.exe 就不用设 |

---

## 1. 注册到 MCP 客户端（CodeBuddy 实测 ✅）

`C:\Users\<你>\.codebuddy\mcp.json` 的 `mcpServers` 里新增（改前先备份原文件）：

```json
"cubeone-mcp": {
  "command": "vpx",
  "args": ["cubeone-mcp"],
  "env": {
    "CUBEONE_POLICY": "read_only",
    "CUBEONE_ALLOWED_ROOTS": "D:\\Projects"
  }
}
```

生效三步：**重启客户端**（配置是启动时读的）→ 连接器页面出现 `cubeone-mcp` → 点**信任**。工具数量应为 **3**，不对就是没接上。

- `vpx`（vite+ 的包执行器）与 `npx` 等价，本机实测 `vpx cubeone-mcp` 冷启动（含 registry 拉包）握手成功、3 工具、真实调用返回 `MxCube.Version=6.18.1`（✅ 证据 `docs/logs/phase1/npm-mcp/vpx-coldstart.log`）
- 首次运行要下载包与依赖（`@modelcontextprotocol/sdk` 一支 95 包），之后走缓存秒起

---

## 2. 发布流程

### 2.1 手动发布（passkey 账号的实际路径 ✅）

```bash
# 注意：--registry 用分写+引号（见 §3.4 的拆参坑）
npm publish --registry "https://registry.npmjs.org/" --access public
```

TTY 里会走 **auth/cli 浏览器确认流**：

```
Authenticate your account at:
https://www.npmjs.com/auth/cli/<uuid>
Press ENTER to open in the browser...
+ cubeone-mcp@0.6.0
```

浏览器里用 passkey 确认，终端自动继续。**这条 URL 只在 TTY 里显示**；非 TTY（脚本/agent 派生）下 EOTP 且 URL 被打码（✅ 实测，winpty 强造 pty 也救不回来，见 §3.5）。

### 2.2 自动发布（Trusted Publisher / OIDC）

`.github/workflows/publish.yml` 已就位：`workflow_dispatch` 或 GitHub Release 触发，
`id-token: write` + `npm publish --provenance`，**全程无 token / secret**。

**一次性绑定（必须在 npmjs.com 网页做）**：

1. 打开 `https://www.npmjs.com/package/cubeone-mcp/access`（或包页 → Settings → Trusted Publisher）
2. 绑定 GitHub：仓库 `LeonhardtHUST/cubeone-mcp`，workflow 文件名 `publish.yml`，environment 留空
3. 以后发版：bump `package.json` version（与 SKILL.md 对齐）→ push → Actions 手动触发（或发 Release）

**工作流里的两道护栏**：已发布版本直接红（防覆盖）；发布前跑与 CI 同版本（pytest==9.2.0）的单元测试。

### 2.3 已知前提

- 发布必须指定 `--registry https://registry.npmjs.org/`——本机默认 registry 是 npmmirror 镜像，不带这个参数发布到镜像上等于没发（§3.1）
- 包对 npmmirror 的可见性：发布后 npmmirror 不自动即时同步，手动 `curl -X PUT https://registry.npmmirror.com/cubeone-mcp/sync` 触发（✅ 实测秒同步）

---

## 3. 反直觉点合集（本机实测，复现发布前先读）

1. **默认 registry = npmmirror 掩盖 token 失效**：`npm whoami` 打到镜像上报 `ENEEDAUTH`，让人误以为只是没登录；实际 npmjs 侧的 `_authToken` 早已 401。诊断方法：`npm whoami --registry=https://registry.npmjs.org/`。
2. **granular Publish token 照样 EOTP**：npm 正在收紧"bypass 2FA"类 token（登录时的官方公告），新发的 Publish 类型 token 发布时仍要第二要素，别指望"给个 token 就能静默发"。
3. **passkey 账号没有 6 位码**：2FA 走安全密钥的账号，TOTP 这条路不存在，正确路径就是 §2.1 的 `auth/cli` 浏览器确认流；`npm account 2fa` 设置页里找不到"OTP 设置"不是你找错了地方。
4. **`--registry=<url>` 连写会被拆参**：本机实测（bash 与 pwsh 都复现）`npm publish --registry=https://...` 被解析成 `registry="https"` + 把 `//registry.npmjs.org/` 当路径（`ENOENT: D:\registry.npmjs.org\package.json`）。**必须分写并加引号**：`npm publish --registry "https://registry.npmjs.org/"`。
5. **非 TTY 下 auth/cli URL 被打码**：agent/脚本环境跑 publish 只会看到 EOTP，URL 是 `***`；winpty 强造 pty 在无控制台的沙箱里启动即崩（winpty.cc 断言），`script` 在 Git Bash 里不存在。结论：**发布这一步要么人在真终端里做，要么走 CI OIDC**。
6. **`spawnSync` 的退出码字段是 `status`**：`exitCode` 恒为 `undefined`（那是异步 ChildProcess 的字段）。MCP 层 isFirstVersion 就因为这个把 `exit=undefined` 写进了返回头。
7. **OIDC 信任发布要求 npm ≥ 11.5.1**：ubuntu-latest 的 Node 22 自带 npm 10.x，必须在 CI 里显式 `npm install -g npm@latest`，否则发布步骤 ENEEDAUTH（多个开源仓因此长期全红）。
8. **从 MSYS 环境派生原生 exe 时 PATH 是 POSIX 格式**：`/c/...:...` 传给 vpx/node 这类 Windows 程序解析不了（表现为"找不到 npm"）。只影响测试脚本；真实 MCP 客户端是原生进程，无此问题。

---

## 4. 自检与证据

| 内容 | 位置 |
|---|---|
| MCP 握手 + 9 项工具通道冒烟（10/10 PASS） | `docs/logs/phase1/npm-mcp/handshake.log`（脚本 `tools/npm_mcp_handshake.mjs`） |
| vpx 冷启动（握手 + 真实调用） | `docs/logs/phase1/npm-mcp/vpx-coldstart.log`（脚本 `tools/npm_vpx_coldstart.mjs`） |
| 包内容基线 | `npm pack --dry-run` = 15 文件 / 63.4 kB / sha512-4vbi8UZPiSdb1 |
| 线上包 | <https://www.npmjs.com/package/cubeone-mcp> |

故障速查：

| 现象 | 处置 |
|---|---|
| 客户端里工具数不是 3 | 没重启 / 没信任 / vpx 拉包失败——看客户端 MCP 日志 |
| 工具返回 "无法启动 Python" | 设 `CUBEONE_PYTHON` 指向 python.exe 绝对路径，重启客户端 |
| 工具返回 "[越界]" | 路径不在 `CUBEONE_ALLOWED_ROOTS`，加根目录（`;` 分隔）后重启 |
| set/restore 被拒 | 这是 read_only 策略在拦截；`CUBEONE_POLICY=full` 并重启 |
| `npm view` E404 但包刚发 | npmmirror 未同步，`curl -X PUT https://registry.npmmirror.com/<pkg>/sync` |
