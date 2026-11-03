# MCP 工具链注册指引（可选步骤，不代替用户操作）

> **本页讲的是 `vscode-cube-mcp` / `platformio.mcp` 这两个外部 server。**
> **本包自身的注册（`npx cubeone-mcp`）与 `CUBEONE_*` 配置见 [`npm-publish-and-codebuddy.md`](npm-publish-and-codebuddy.md)**——两页容易看反，先确认你要注册的是哪一个。

> 产出时间：2026-11-03 · owner：`env-agent` · 验证等级：**L1**
> 适用对象：想在自己机器上把 `vscode-cube-mcp` / `platformio.mcp` 接到 MCP 客户端的人
> **重要前提**：`cubeone-mcp` 的交付物是仓库本体（Skill + 核验脚本 + 文档 + CI），**不包含**替用户改全局配置。本文档只提供可复现的注册步骤与实测结论，**所有操作由你自己执行**；本仓库不会、也没有修改你的 `~/.workbuddy/mcp.json`。

---

## 0. 这份文档为什么存在

原计划里 T0.2 是"由 Agent 修改 `~/.workbuddy/mcp.json` 注册两个 server"。用户在 GATE-0 明确否决：**本项目是开发 cubeone-mcp，不是替用户装配本机 MCP 工具链**（见 `docs/DECISIONS.md` D12）。

于是 T0.2 降级为本文档。已经花掉的实测成本不浪费——下面每条结论都是**实测**出来的，不是抄文档：

- 两个 server 都能被**真实拉起**，并用官方 `mcp.client.stdio.ClientSession` 完成 `initialize` + `tools/list` 握手（证据见 `docs/logs/phase0/*handshake.log`）
- 三个**反直觉点**（§4），照文档猜一定会踩

---

## 1. 前置条件

### 1.1 `vscode-cube-mcp`（.ioc 读取/修改/生成）

已安装形态是 **uv tool**（裸可执行文件，不在 PATH 也无所谓，配置里写绝对路径）：

```bash
# 首次安装（如果还没装）
uv tool install vscode-cube-mcp

# 校验安装
uv tool list                       # 应出现 vscode-cube-mcp v0.4.2
uv tool dir                        # 默认 C:\Users\<你>\AppData\Roaming\uv\tools
```

安装后生成的可执行文件（本机实测路径）：`C:\Users\Leon\.local\bin\vscode-cube-mcp.exe`。
**注意**：`.local\bin` 不一定在 PATH 里，但配置里写绝对路径即可，无需改 PATH。

### 1.2 `platformio.mcp`（构建/串口/测试/尺寸分析）

用 `uvx` 免安装运行，**首次调用会自动拉包**。本机实测：

```text
Downloading pydantic-core (2.1MiB) / cryptography (3.6MiB) / pywin32 (6.7MiB)
Installed 31 packages in 1.82s
```

前置条件只有两条：

1. `uv`/`uvx` 可用（本机 `uv 0.11.29`）
2. **PlatformIO Core 已安装**（platformio.mcp 自己不装 Core，只调用它）——本机 `6.2.0`，路径 `C:\Users\<你>\.platformio\penv\Scripts\pio.exe`；用 `PLATFORMIO_MCP_PIO` 显式指定，避免它去猜

### 1.3 CubeMX（仅 `vscode-cube-mcp` 需要）

`ST_CUBEMX_EXE` 指向的 CubeMX **必须存在**，否则 `cubemx_*` 系列工具会在调用时报错（不是启动时报错——server 本身能起来，只是干不了活）。本项目 MVP 锁 **6.18.1**（见 DECISIONS D1）。

---

## 2. 可直接粘贴的配置片段

把下面两段放进你 MCP 配置文件 `mcpServers` 对象里（WorkBuddy 是 `~/.workbuddy/mcp.json`；Claude Desktop 是 `claude_desktop_config.json`，位置见其官方文档）。

> **路径要按你自己的机器改**：下面沿用本机实测路径（`C:\Users\Leon\...`）。换人换机必须替换用户名部分和 `pio.exe` 路径。

```json
    "vscode-cube-mcp": {
      "command": "C:\\Users\\Leon\\.local\\bin\\vscode-cube-mcp.exe",
      "args": [],
      "env": {
        "ST_CUBEMX_EXE": "C:\\ST\\STM32CubeMX\\STM32CubeMX.exe",
        "ST_CUBEMX_ALLOWED_ROOTS": "D:\\Projects;C:\\Users\\Leon\\WorkBuddy",
        "ST_CUBEMX_TIMEOUT": "300"
      }
    },
    "platformio.mcp": {
      "command": "uvx",
      "args": [
        "platformio.mcp"
      ],
      "env": {
        "PLATFORMIO_MCP_POLICY": "build_only",
        "PLATFORMIO_MCP_PIO": "C:\\Users\\Leon\\.platformio\\penv\\Scripts\\pio.exe"
      }
    },
```

### 2.1 每个字段为什么这么写

| 字段 | 值 | 依据 |
|---|---|---|
| `vscode-cube-mcp.command` | 绝对路径 `.exe` | 该工具是 uv tool 装的裸 exe，不在 PATH。用绝对路径最稳 |
| `vscode-cube-mcp.args` | **`[]`（空数组）** | **见 §4.1，这个 exe 不接受任何参数** |
| `ST_CUBEMX_EXE` | CubeMX 6.18.1 的 exe | 源码 `_find_cubemx()`：环境变量优先，其次 PATH，再其次 `ProgramFiles` 常见路径；显式给定最可靠 |
| `ST_CUBEMX_ALLOWED_ROOTS` | `D:\Projects;C:\Users\<你>\WorkBuddy` | **`os.pathsep` 分隔，Windows 即 `;`**。源码 `_allowed_roots()` 逐项 `strip()` 后做前缀校验；**不在白名单内的 `.ioc` 会被直接拒绝** |
| `ST_CUBEMX_TIMEOUT` | `"300"`（**字符串**） | 源码 `int(os.environ.get("ST_CUBEMX_TIMEOUT", "240"))` → 必须能转 int，**写成数字会报类型错**。默认 240，CubeMX 单次生成约 60s，给 300 留余量 |
| `platformio.mcp.command` | `uvx` | 见 §4.3，裸命令能解析 |
| `PLATFORMIO_MCP_POLICY` | `build_only` | 权限档位。另有 `read_only` / `full`。**烧录需要显式升档**，见 §4.2 |
| `PLATFORMIO_MCP_PIO` | `pio.exe` 绝对路径 | 不指定的话它会自行探测；显式指定避免多解释器环境选错 |

**不需要** `"disabled": false`——省略 `disabled` 字段即视为启用（与既有条目的 `npx` 写法一致）。

---

## 3. 注册后怎么生效

1. **重启 MCP 客户端**（WorkBuddy 需重启应用，不是只重开对话窗口）——配置是启动时读的。
2. 在客户端的**连接器 / 工具页面**确认两个 server 出现，并点**"信任"**（首次接入必须人工确认，这是客户端的安全设计）。
3. 确认工具数量（见 §5 的期望值）。数量不对 = 没接上，别急着调工具。

**本文档不代替上述操作**，也不保证你的客户端行为与本文一致——不同客户端的配置键名（`mcpServers` vs `servers`）、信任流程、日志位置都可能不同。

---

## 4. 三个反直觉点（本文档的最大价值）

### 4.1 `vscode-cube-mcp.exe` 不接受任何命令行参数

**实测**：直接 `vscode-cube-mcp.exe --help` **没有任何输出，进程不退出**——因为它没有 argparse，`main()` 就是一句 `asyncio.run(mcp.run_stdio_async())`，`--help` 被完全忽略，进程直接进 stdio 循环等输入。

```python
def main() -> None:
    asyncio.run(mcp.run_stdio_async())
```

**后果**：
- 配置里 `"args": []` 必须是空数组。**不要**加 `--help`、`stdio`、`serve`、`--transport` 之类——任何参数都被忽略，但加了会让后来排障的人误以为参数有意义。
- 想"试着启动它看看"时，看到它挂住不输出**不是故障**，是在等 JSON-RPC 输入。判断它是否健康只有一条路：**走 MCP 协议握手**（§5）。

### 4.2 `build_only` 策略**不隐藏工具**，拦截发生在调用时

**实测**：`PLATFORMIO_MCP_POLICY=build_only` 下 `tools/list` 仍返回 **40 个工具**，其中包含：

```
pio_flash_and_verify   pio_upload   pio_upload_ota   pio_debug_start   ...
```

**后果**：
- **"工具可见" ≠ "可执行"**。看到 `pio_upload` 在列表里就以为能烧录，是错的。
- 需要烧录时必须显式把 `PLATFORMIO_MCP_POLICY` 升到 `full`（并重启客户端），且升级动作本身应该被记录/征求同意。
- 反过来也有好处：做只读/构建类任务时，`build_only` 是**执行期**的安全网，不依赖调用方自觉。本项目 Phase 1 全程 `build_only`；烧录属 Phase 2，需接板后另行确认。

### 4.3 `uvx` 用裸命令即可（不需要绝对路径）

**实测**：用 Node 的 `spawnSync`（**不带 shell**）派生 `uvx`，返回码 0、正常输出 `uvx 0.11.29`——说明客户端通过 PATH 能解析到 pyenv 的 shim（`uvx.bat`）。

- 现有配置里 `npx` 也是裸命令，行为一致。
- 若你的客户端在 spawn 阶段报 `ENOENT` / `EINVAL`（某些客户端的 `spawn` 不处理 `.bat`/`.cmd`），换成绝对路径：
  ```json
  "command": "C:\\Users\\Leon\\.hermes\\bin\\uvx.exe"
  ```
  本机该路径存在且为同版本（`uvx 0.11.29`）。`uv` 的真实二进制位置可用 `where uvx` 查，避开 shim。

---

## 5. 如何复现本文档的验证（推荐自己跑一遍）

不要靠"客户端里看起来在"来判断。用官方 MCP Python SDK 做协议级握手，10 秒出结论。

### 5.1 准备

```bash
# 用一个装了 mcp SDK 的 Python（本机复用了 vscode-cube-mcp 自带的 venv）
C:\Users\Leon\AppData\Roaming\uv\tools\vscode-cube-mcp\Scripts\python.exe -c "import mcp; print('ok')"
# mcp SDK 版本：2.2.0
```

### 5.2 握手脚本（把 §2 的配置条目原样喂进去）

```python
import asyncio, json, os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ENTRY = json.load(open(r"路径\到\你的\mcp.json", encoding="utf-8"))["mcpServers"]["vscode-cube-mcp"]
# 换成 ["platformio.mcp"] 即可测另一个

async def main():
    os.environ.update(ENTRY["env"])
    params = StdioServerParameters(command=ENTRY["command"], args=ENTRY["args"], env={**os.environ})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            init = await asyncio.wait_for(s.initialize(), timeout=120)
            print("protocol:", init.protocol_version)
            print("server  :", init.server_info.name, init.server_info.version)
            tools = await asyncio.wait_for(s.list_tools(), timeout=120)
            print("tools   :", len(tools.tools))
            print(sorted(t.name for t in tools.tools))

asyncio.run(main())
```

### 5.3 期望结果（本机实测值，2026-11-03）

| server | `protocol_version` | `server_info.name` | `tools/list` 数量 | 工具清单要点 |
|---|---|---|---|---|
| `vscode-cube-mcp` | `2025-11-25` | `Vscode_cube_mcp`（`version` 为空串） | **9** | `cubemx_help` / `cubemx_load` / `cubemx_configure` / `cubemx_generate` / `cubemx_export_pinout` / `cubemx_new_project` / `cubemx_remove_peripheral` / `cubemx_add_source` / `cubemx_script` |
| `platformio.mcp` | `2025-11-25` | `platformio` `0.2.0` | **40** | 含 `pio_system_info` / `pio_build` / `pio_size_report` / `pio_list_devices` / `pio_monitor_*` / `pio_flash_and_verify` 等 |

> 数字对不上就是没接对。已知偏差：调研报告早期把 `vscode-cube-mcp` 的工具数写成"~20"，**实测是 9**，以上表为准。

### 5.4 顺带可跑的自检（platformio.mcp 独有）

```bash
# 带上前述 env
uvx platformio.mcp doctor
```

本机实测输出要点：

```json
{
  "ok": true,
  "policy": "build_only",
  "core_version": "6.2.0",
  "python": "3.11.7-final.0",
  "installed_platforms": 2,
  "installed_tools": 27,
  "log_dir": "C:\\Users\\Leon\\.platformio-mcp\\logs"
}
```

子命令全集：`{serve, install, doctor}`，**不带子命令 = stdio 服务**（所以 `args: ["platformio.mcp"]` 就够）。
注意它会写一个仓库外的状态目录 `~/.platformio-mcp/`（放日志），不需要时可直接删。

---

## 6. 脱敏红线（分享/提交前必读）

`~/.workbuddy/mcp.json` **含明文凭据**，本机现有条目里至少有：

- `siyuan` → `headers.Authorization: Token ...`
- `penpot-official-mcp` → URL 里的 `userToken=...`
- `penpot-api` → `env.PENPOT_ACCESS_TOKEN`

**因此**：

1. **不要把 `mcp.json` 原始内容贴进 issue / PR / 对话 / 截图**；
2. 任何备份、diff、示例文件在离开本机前，必须把 `token` / `Authorization` / `*_TOKEN` / `*_KEY` 的值替换为 `***REDACTED***`；
3. 本文档 §2 只给**新增的两个条目**，不包含你原有的其它条目——正好避免把别人的凭据带出来；
4. 若曾把明文备份提交进 git 历史，视为凭据已泄露：**先轮换 token，再考虑清理历史**（顺序不能反）。

本仓库自身遵守同一红线：`docs/backups/` 归 `platform-lead` 管理并负责脱敏（DECISIONS D10 / D11），其它角色不提交该目录。

---

## 7. 故障速查

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `vscode-cube-mcp` 进程秒退 | exe 路径错 / uv tool 被卸 | `uv tool list` 确认；用手写脚本按 §5.2 跑一次看 stderr |
| 启动后无任何输出、也不退出 | **正常**——在等 JSON-RPC | 别用 `--help` 判断死活，走 §5.2 握手 |
| `cubemx_*` 调用报"路径不在白名单内" | `ST_CUBEMX_ALLOWED_ROOTS` 没覆盖该 `.ioc` 所在目录 | 加根目录（`;` 分隔），**重启客户端** |
| `cubemx_*` 调用报找不到 CubeMX | `ST_CUBEMX_EXE` 未生效 | 环境变量是 server 进程级，改完必须重启客户端；用 §5.2 的 `os.environ.update()` 可先本地验证 |
| `platformio.mcp` 拉包失败（网络） | 首次 `uvx` 需下载 31 个包 | 联网重试，或本地 `uv tool install platformio.mcp` 后改 `command` 指向其 exe；**回退方案**：直接调 `pio.exe` CLI（DECISIONS D2 保留了这条路） |
| `uvx` `ENOENT`/`EINVAL` | 客户端 `spawn` 不处理 `.bat` shim | 见 §4.3，改绝对路径 `...\.hermes\bin\uvx.exe` |
| 工具数不是 9 / 40 | 接错了 server 或版本不同 | 核对 `server_info.version`；`uvx platformio.mcp --version` 应为 `0.2.0` |

---

## 8. 相关证据与文档

| 内容 | 位置 |
|---|---|
| 拉包记录 | `docs/logs/phase0/platformio-mcp-install.log` |
| doctor 输出 | `docs/logs/phase0/platformio-mcp-doctor.log` |
| platformio.mcp 握手（40 工具） | `docs/logs/phase0/platformio-mcp-handshake.log` |
| vscode-cube-mcp 握手（9 工具） | `docs/logs/phase0/vscode-cube-mcp-handshake.log` |
| `cubemx_configure` 源码级签名与坑 | `docs/reports/t0-cubemx-configure-signature.md` |
| 为什么不改用户配置 | `docs/DECISIONS.md` D12 |
