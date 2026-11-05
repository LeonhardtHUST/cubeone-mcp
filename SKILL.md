---
name: cubeone-mcp
description: "STM32 生成核验与 .ioc 键级工具包：本包 MCP 只暴露 3 个工具（verify_generation / ioc_backup / ioc_field），用于「生成后核验（G1 硬关卡）」「备份/还原 .ioc」「单键读写 .ioc」，并附完整操作流程文档。**能力边界（先读）：只能可靠代做普通 GPIO 级改动（新增引脚/改模式/改上下拉）；UART/SPI/TIM/ADC 等非 GPIO 外设的增改没有工具能力，必须手改 .ioc 或走 GUI，并强制过 G1。** 触发词收敛为：「生成完帮我核一遍」「有没有被静默丢弃的外设」「改一下这个 ioc / 加一个 GPIO」「备份/还原 .ioc」「读/改 .ioc 某个键」。⚠️ 以下不属本包工具能力，命中时按 SKILL.md 的 CLI 等价通道与流程文档处理，不要期望 MCP 工具直接完成：「pio 构建 / Flash-RAM 尺寸」「烧进去看看 / 烧录」「串口有输出吗 / 串口捕获」「加一路串口/SPI/定时器（非 GPIO 外设增改）」。只读审计不写盘；写操作前必须备份 .ioc，生成后必须跑核验器并如实声明验证等级；不碰 testbeds/ 之外的模板原仓。"
version: 0.8.0
agent_created: true
license: MIT
compatibility: Python 3.11+（CI 仅覆盖 3.11 / 3.13，更早版本未验证）；CubeMX 6.18.1（路径见 §0.2）；PlatformIO Core 6.x；MCP 可选，未注册用 §0.4
---

# cubeone-mcp：STM32 生成 / 核验 / 构建 / 烧录编排

> **本文件是操作面，不是手册。** 逐条细则在 `references/`：`capability-boundary.md`（能力边界）·
> `verify-contract.md`（核验器契约）· `regen-exit-codes.md`（`regen.sh`）· `diff-evidence.md`（取证判据）·
> `pitfalls.md`（陷阱全文）。证据可信度：**✅** 本机实测 ｜ **📄** 引自模板仓/官方文档 ｜ **⚠️** 未实测。
> 状态：v0.8.0 —— **契约增强 minor：MCP 输出侧升级，输入契约与判据零改动**——三工具补 **`outputSchema`**
> （新增可选字段）、`structuredContent` 加 **64 KiB 上限**（超限头尾保留 + `_meta` 告警，未超限不注入）、
> `tail()` 改**头尾保留**（首行 `verdict` 不再被截掉）、`ioc_field` / `ioc_backup` 加**并发文件锁**
> （`.cubeone-lock`，超时 rc=2）。核验器仍 **1.2.0**（7 项 / schema `/2`），`inputSchema` 的
> required / enum / additionalProperties **一字未改**。详见 `docs/releases/2026-11-05-v0.8.0.md`。
> **0.7.4 = 收尾补丁版（无 BREAKING、无新增能力）**：0.7.3 包体积双口径澄清、发版证据**只认 CI 的 LF pack**
> （CRLF 纪律）、`tools/*` 编码加固、版本轴扩到**五处**（含 `package-lock.json` 根两处，见 `docs/DECISIONS.md`
> **D35 §35.7**）。**0.7.3 = 审定整改 W0–W6 的补丁版**：**无新增能力，但有一处 BREAKING behavior**——证据不成立时
> `verify_generation.py` 由「静默放过」改判**退出码 2 且不落 `--json-out` / `--report-md`**；`ioc_field` 双层拒绝含
> 换行符的 key / value（退出码 2），见 `docs/releases/2026-11-04-v0.7.3.md`。**0.7.2 = 0.7.1 的缺陷修复与工程化批次**：
> **无新增能力**，但核验器有一处**判据语义变更**（`ProjectManager.CoupleFile=true` 的工程改扫 `--project-root` 下
> `Core/Src/*.c`，见 `references/verify-contract.md` §4.2；两处用户可见缺陷的修复见 `docs/releases/2026-11-04-v0.7.2.md`）。
> **0.7.0：路径白名单默认 fail-closed（BREAKING）**，迁移见 §0.2；同批含 `ioc_backup` 备份完整性摘要与原子还原、
> `realpath` 防 junction 绕出。**0.7.1 = 文档与脚本修正，无行为变更**（注册指南随包下发并对齐 0.7.0 默认拒绝；
> `ioc_field` 脚本轴 **1.1.0**：get 区分「多行歧义」与「键不存在」）。**Phase 2 首板 L5 已达成（2026-11-04）**：
> 烧录 / 寄存器回读 / 目视一致见 `docs/reports/phase2-bringup-2026-11-04.md`；串口段与 `pio device monitor` 仍未实测。

> 📦 **随包可达性（W4-3 / D-4 裁决）**：npm 包里只有 `SKILL.md`、`references/`、两本注册指南
> （`docs/guides/mcp-registration.md`、`docs/guides/npm-publish-and-codebuddy.md`）**与两本接板指南**
> （`docs/guides/gate-2.0-checklist.md`、`docs/guides/testbeds-board-map.md`）——后两本已进
> `package.json` 的 `files`，接板日必备。**其余 `docs/` 全部「仅仓库可见」**（clone 仓库才看得到）：
> `docs/reports/*`（含 L5 真源 `docs/reports/phase2-bringup-2026-11-04.md`）、`docs/releases/*`、
> `docs/DECISIONS.md`、`docs/TASKBOARD.md`、`docs/README.md`、`docs/logs/*`、`docs/evaluations/*` 等。
> 按本文件去找这些文件时若不在包内，请回仓库取；**不要把它们当成随包死链去"修"**。

## 0. 硬前提

### 0.0 第零层：能力边界（先读，否则后面全白读）

**能可靠代做**：普通 GPIO 级改动（新增引脚 / 改模式 / 改上下拉）；`set pin PB0 GPIO_Output` 被 6.18
接受、回显 `OK`、`.ioc` 确实变化（✅）。

**不代做（没有能力，不是"还没实现"）**：UART / SPI / TIM / ADC / I2C 等非 GPIO 外设的增改。
证据（✅ D25）：`set pin PA0 S_TIM2_CH1_ETR`、`set pin PA1 USART2_TX` 一律回 **`KO`**；`set ip parameters …`
回 **`OK` 却一字未改** `.ioc`；**两类退出码都是 0** ⇒ 非 GPIO 只能**手改 `.ioc` 或 GUI → 强制过 G1
→ 人工过 H-6 清单**（§2 路径 B）。**因此：G1 核验器不是辅助工具，而是非 GPIO 路径上唯一的安全网。**

失败被拦截的层次不同，抓法也不同（详见 `references/capability-boundary.md` §4）：`set pin` 写错信号名 →
命令层 `KO`｜手改 `.ioc` 写坏信号名 → **可能出 `Cannot map`**｜手改漏 `IPParameters` → **日志干净什么都不报**
（只有 `main_init_present` 能抓）。

**四层优先级**：能力层（能不能做）> 路径层（`ALLOWED_ROOTS`）> 动作层（`POLICY`）> 流程层（G1 + L 等级）。
**能力层失败=做不了，权限层失败=不让做，流程层失败=做错了**——加白名单不会让你能配串口。

### 0.1 通道选择（与路径选择是两件事）

**判据只看本包**：注册后做一次 `tools/list`，返回里含本包 3 个工具
（`verify_generation` / `ioc_backup` / `ioc_field`，与 `lib/server.mjs` 的 `TOOL_DEFS` 一一对应）
⇒ **MCP 通道可用**；不含 ⇒ 走 **CLI 等价通道**（§0.4）。**不要用 `cubemx_help` / `pio_system_info`
或任何外部 server 的工具是否可调来判断本包通道**——那是另一条通道、另一组 server，与本包无关。
注册：**本包（npm 通道）**见 `docs/guides/npm-publish-and-codebuddy.md`（含 0.7.0 起 fail-closed 的白名单配置与注册后自检）；`vscode-cube-mcp` / `platformio.mcp` 两个**外部 server** 见 `docs/guides/mcp-registration.md`。本仓不替用户改 `mcp.json`（D12）。
**两条通道都不可用时停手报错**，不许挑着核验绕过 G1。
是否存在 MCP 只决定"用哪种方式调"；**要改什么**才决定"这件事能不能做"——**先判 0.0，再判 0.1。**

#### 两套入口的参数面（B-6：何时用哪个）

| | CLI 直调（`scripts/verify_generation.py` 等） | MCP 通道（本包 3 工具） |
|---|---|---|
| 何时用 | 要落 `verify.json` / `report_md` 证据文件、写 CI 脚本、或在 `regen.sh` 编排里被调 | Agent 在会话里做一次核验 / 备份 / 键读写，或需要路径白名单 + 写策略门禁 |
| 参数名 | `--log` `--main-c` `--mxproject` `--expect` `--project-root` `--ioc` `--expect-pins` `--allow-signal` `--json-out` `--report-md` | `log` `main_c` `mxproject` `expect` `project_root` `ioc` `expect_pins` `allow_signal` `report_md`（**snake_case**） |
| 判据真源 | 同一份 Python 脚本（MCP 只是薄封装，`spawnSync` 调它） | 同左 |
| 证据落点 | `--json-out` 生成 `verify.json` | `structuredContent`（**不生成 `verify.json`**） |

⚠️ MCP 通道**拒绝未知键**（`additionalProperties:false` 已落地）：`projectRoot` / `mainC` 这类 camelCase
会被判 `isError`，正确写法是 `project_root` / `main_c`；`expect_pins` 与 `ioc` 必须同时给。
⚠️ **MCP 返回文本有噪声**：`content[0].text` 固定带环境脚注与 `--- stdout ---` 段。
**0.8.0 起 `tail()` 改为头尾保留**（头 2 000 + 尾 10 000，中间插 `…(截断 N 字符)…`），所以
`render_console()` 首行的 `verdict` **不再被截掉**；但文本仍是摘要 ⇒ **结论一律以 `structuredContent` 为准**（B-1）。

⚠️ **`structuredContent` 有 64 KiB 上限**（0.8.0 起，`MAX_STRUCTURED_BYTES = 65536`，按 `JSON.stringify`
后的 UTF-8 字节数）。超限时**头尾保留 + 字段级裁剪**（长字符串留头 3 072 + 尾 1 024、长数组留前 50 项），
并注入 `structuredContent._meta = {truncated, original_bytes, limit_bytes, policy, truncated_fields}`；
**未超限时完全不注入 `_meta`**（与 0.7.x 形态逐字节一致）。
消费方**不得假设 `structuredContent` 永不截断**：看到 `_meta.truncated === true` 时，头部字段
（`verdict` / `action` / `summary` 的计数）仍完整，但 `checks[].detail` / `inputs` 可能已被裁剪——
要完整 `detail` 请走 CLI 通道的 `--json-out`。

⚠️ 三个工具都声明了 **`outputSchema`**（0.8.0 起的**新增可选字段**，旧客户端忽略不报错）。它描述的是
「`structuredContent` 存在时的形状」，**不是判据真源**——7 项判定的唯一真源仍是 `verify_documents()`；
`checks[].id` 的 `enum` 只是把 F-1 契约显式化。执行失败 / 输入错误时只有文本 + `isError`，
**可能没有** `structuredContent`。

⚠️ **并发写锁**（0.8.0 起）：`ioc_field` 真写盘（`set` 且非 `--dry-run`）与 `ioc_backup` 的
`backup` / `restore`，会先对**工程目录**加排他锁 `.cubeone-lock`（`os.open(O_CREAT|O_EXCL)`，
Win32 上等价 `CreateFileW(CREATE_NEW)`，**不依赖 `fcntl`**；同一套代码跨平台）。
拿不到锁就等 `--lock-timeout`（**默认 10s**，CLI 可调；MCP 侧不新增参数、用默认值），
超时 ⇒ **rc=2 + `isError`**、stderr `[<tool>][lock-timeout]`、`.ioc` **一个字节都不动**。
`--list` / `get` / `--dry-run` 是只读，**不加锁**；锁文件存活超 300s 视为陈旧、自动回收。
⚠️ 本锁只覆盖这两个脚本的**进程级**互斥；`regen.sh` 的**跨步骤**并发仍不在范围内
（两个 `regen.sh` 同时跑同一工程仍可能互踩——v0.7.3 已知限制保留，别把这条锁当万能钥匙）。

### 0.2 CubeMX / PlatformIO 定位（两通道共用）

CubeMX = `C:\ST\STM32CubeMX\STM32CubeMX.exe`（📄 不在 `C:\Program Files\…`），JRE 同目录
`jre\bin\java.exe`；版本 **6.18.1 / `DB.6.0.181`**（D1，**以 exe 属性或运行日志为准，别信 `.ioc` 版本戳**，P2）；
单次生成约 60 s、仅 `set pin`+`saveas` 约 32 s ⇒ **超时 ≥240 s**。
PlatformIO = `C:\Users\Leon\.platformio\penv\Scripts\pio.exe`（Core 6.2.0）。

MCP 通道另有 env：`ST_CUBEMX_EXE`、`ST_CUBEMX_ALLOWED_ROOTS`（白名单，换目录必须同步改）、
`ST_CUBEMX_TIMEOUT=300`、`PLATFORMIO_MCP_POLICY=build_only`、`PLATFORMIO_MCP_PIO`。

**工具通道自己的 env**：`CUBEONE_ALLOWED_ROOTS`（路径白名单）、`CUBEONE_POLICY`（`read_only` 默认 / `full`）、
`CUBEONE_PYTHON`、`CUBEONE_ALLOW_NO_ROOTS`（宽松逃生门）、`CUBEONE_REQUIRE_ROOTS`（冗余：默认已严格）。

> 🔴 **0.7.0 起 `CUBEONE_ALLOWED_ROOTS` 未设置 = 拒绝所有路径参数（BREAKING）。**
> 返回文本会以 `[cubeone-mcp][策略拦截] 未配置 CUBEONE_ALLOWED_ROOTS，0.7.0 起默认拒绝所有路径参数。`
> 开头，并给出配置方法。**迁移方法（二选一，改完重启客户端）**：
> ① 在注册条目的 `env` 里配白名单，多个用系统分隔符（Windows `;`，POSIX `:`）——
> `"CUBEONE_ALLOWED_ROOTS": "D:\\Projects;C:\\Users\\you\\WorkBuddy"`；
> ② 确实需要访问任意路径，显式设 `"CUBEONE_ALLOW_NO_ROOTS": "1"`（宽松模式，**不建议**；返回文本会标注
> `allowed_roots=未设置(宽松模式：本次调用无路径限制，CUBEONE_ALLOW_NO_ROOTS 生效)`）。
>
> **为什么把 fail-open 当默认值是错的**：默认值不会自己说话——能跑通就被当成"被限制住了"，用户
> **全程处于无保护状态却不自知**。安全默认值只能是"默认拒绝、显式放行"：写下来的放宽才会被看见、被复核。
> 白名单比的是**物理路径**（`realpath`），白名单内 junction/symlink 指向界外同样被拒（文案会打物理落点）；
> 残余风险：不防 TOCTOU（校验后链接被换），威胁模型是误操作而非对抗者。
> `CUBEONE_REQUIRE_ROOTS=1` 仍可用但**冗余**：设不设都不改变路径判定，只多一条"启动即退出"的 fail-fast；
> 与 `CUBEONE_ALLOW_NO_ROOTS` 同时为真时**以后者为准**。

### 0.3 三条红线

1. **要烧录就必须显式确认**（MCP 下 `build_only` 会拒；CLI 下没人拦，见 §0.5）。属 L5，需 GATE-2.1。
2. **只在 `testbeds/` 的克隆副本里做写操作**；`D:\Projects\GitHub\` 下模板仓、`NUEDC_2027`、
   `HUSTRadio`、`leonskill-*` **一律只读**（✅ D9）。**接板 / 选首烧目标前先查
   `docs/guides/testbeds-board-map.md` §2.1**：同是 `STM32G474VETx` 也可能是两块板卡完全不同的工程
   （NUEDC 原板 PC13/14/15 vs X-Pulse PC0/1/2 共阳低亮）；烧错时"烧录成功 + 寄存器正确 + 人眼无现象"，
   见 F4 / `docs/reports/phase2-bringup-2026-11-04.md`。
3. **生成后不核验 = 没做**：CubeMX 对 `.ioc` 错误是非致命的，外设会被静默丢弃（📄 D5 / H-6）。

### 0.4 CLI 等价通道

```bash
"C:\ST\STM32CubeMX\jre\bin\java.exe" -jar "C:\ST\STM32CubeMX\STM32CubeMX.exe" -q "<工程>\scripts\cubemx-generate.mx"
"C:\Users\Leon\.platformio\penv\Scripts\pio.exe" run -d "<工程>"
python scripts/verify_generation.py --log <原始日志> --main-c "<工程>\Core\Src\main.c" \
    --mxproject "<工程>\.mxproject" --project-root "<工程>" --expect GPIO \
    --allow-signal VP_RIF_VS_RIF1 --json-out <证据目录>\verify.json
```

> 📝 上面是 **CLI 直调**：`--json-out` 会真的落一份 `verify.json`。**MCP 通道不生成
> `verify.json`**（证据是 `structuredContent`，见 §0.1 与 §2 第 5 步）；两条通道别混。

Phase 2 烧录命令 `pio run -d <工程> -t upload` **已实测（2026-11-04，CLI 通道）**：
`Verified OK` + 寄存器回读 + 目视一致，见 `docs/reports/phase2-bringup-2026-11-04.md`；
**`pio device monitor` 仍未实测**（本工程未启用 USART，见 §6.2）。烧录前仍须过 GATE-2.1 安全确认。

#### 🔴 `--log` 只接受 CubeMX 原始 stdout 重定向文件，**禁止传任何 MCP 工具返回值**

两个独立理由，任一成立就够：① MCP 的 `NOISE_RE` 删掉 `INFO`/`WARN`/`DEBUG`/`TRACE` 行（`[ERROR]` 保留），
而**实测真实 `Cannot map` 行就是 `[INFO]` 级别**（`s3b-regen/cubemx-generate.log:321`）⇒ 它在 MCP 返回
文本里**必然不存在** → **假阴性**且 `verdict` 仍 PASS；② `syscalls.c`/`sysmem.c` 的叠加路径异常**只在 stdout
的 `NoEcho` 行** ⇒ 即使不走 MCP、**只要"只读文件"也会错过它**。

> **自检**：手上只有 MCP 返回文本 → **先别跑核验**，换 CLI 重定向重跑一遍生成。

### 0.5 CLI 通道的技术真空

路径层（`ALLOWED_ROOTS`）与动作层（`POLICY`）在 CLI 回退通道上**都不存在**，只剩流程层（G1 + L 等级）。
**连"成功与否"都判不了**：CubeMX 退出码恒为 0；MCP 的 `cubemx_configure` 至少还判"无整行 `KO`"，
**CLI 手跑 `java -q` 时没有任何人查 `KO`。**

> **本项目不对 CLI 通道提供任何技术性拦截保障，只提供约定。** 不注册 MCP = 自愿放弃前两层保护。
> ⚠️ 但**不要**读成"CLI 通道不安全所以别用"——它是大多数用户的唯一路径。正确做法：知道真空在哪、
> 用流程补（烧录走 GATE-2.1；只在副本改配置；改动后必做 §2 三级确认）。

## 1. 能力索引

### 1.1 本仓自研（唯一不可替代的部分）

| 能力 | 入口 |
|---|---|
| **生成核验（G1 硬关卡）** | `scripts/verify_generation.py` —— 契约见 `references/verify-contract.md` |
| 备份 → 生成 → 核验 → 失败回滚 | `scripts/regen.sh <工程> [-e …] [-o …] [--require-clean] [--fail-fast-on-migrate]` —— 见 `references/regen-exit-codes.md`。**包内可用**，但编排 CubeMX 生成需本机存在 CubeMX/JRE（路径可用 `ST_CUBEMX_JRE`/`ST_CUBEMX_EXE` 覆盖） |
| `.ioc` 字段读写 / 备份还原 | `scripts/ioc_field.py`、`ioc_backup.py --project <工程根> [--restore\|--list]`。备份会同时落 `<name>.ioc.bak.sha256` 旁路摘要；`--restore` 先校验摘要再原子替换（不一致 → 拒还原、退出码 2、`.ioc` 不动；无摘要的旧备份 → 警告后照常还原）。**不要手删/手改 `.bak.sha256`**——删了就等于放弃篡改检测。0.8.0 起写盘前加 `.cubeone-lock`（`--lock-timeout` 默认 10s，超时 rc=2 且不动文件） |

### 1.2 工具面：本包 3 工具 与 外部 server（两条通道，别混）

**表 A · 本包 MCP 的 3 个工具**（`lib/server.mjs` 的 `TOOL_DEFS`，`tools/list` 与下表一一对应；
判据全在 Python 脚本里，JS 层只做参数校验 / 路径白名单 / 退出码映射）：

| 工具 | 做什么 | 主要参数 |
|---|---|---|
| `verify_generation` | **G1 生成核验硬关卡**（7 项 / schema `/2`），退出码 0/1/2 | `log` `main_c` `mxproject` `expect`；可选 `project_root` `ioc` `expect_pins` `allow_signal` `report_md` |
| `ioc_backup` | `.ioc` 备份 / 还原 / 清单（SHA-256 凭据） | `project` `action`（`backup` / `restore` / `list`） |
| `ioc_field` | `.ioc` **单键**读 / 写（保留 CRLF、原子写） | `ioc` `action`（`get` / `set`）`key`；`set` 时 `value`，可加 `dry_run` |

**表 B · 外部 server（另一条通道，不属于本包，本包无法调用也不负责）**：
`cubemx_load` / `cubemx_configure` / `cubemx_generate`（`vscode-cube-mcp`）、
`pio_build` / `pio_size_report` / `flash_standalone` / `pio_monitor_capture`（`platformio.mcp`）等。
它们是否注册，与本包 `tools/list` 是否可用**无关**；注册与排障见 `docs/guides/mcp-registration.md`
（该文件描述外部 server；本包注册见 `docs/guides/npm-publish-and-codebuddy.md`）。

| 想做的事 | 本包 3 工具 | CLI 等价通道 / 外部 server |
|---|---|---|
| 只读回读 `.ioc` | `ioc_field get`（**单键**） | 直接读 `.ioc`（ini）；引脚表 ⚠️ `csv pinout`；`cubemx_load` 属外部 server |
| 备份 / 还原 `.ioc` | `ioc_backup` | `scripts/ioc_backup.py --project <工程根> [--restore\|--list]` |
| **G1 生成核验** | `verify_generation` | `scripts/verify_generation.py`（见 §0.4 / §1.3） |
| **改普通 GPIO** | 本包无 `set pin` 能力 | `set pin` 命令写进 `.mx`；`cubemx_configure` 属外部 server |
| **改非 GPIO 外设** | ❌ **没有这个能力** | ❌ 同样没有 → 手改 `.ioc` / GUI（§2 路径 B） |
| 生成 / 构建 / 尺寸 / 烧录 | 本包不提供 | §0.4 CLI；`cubemx_generate` / `pio_build` / `pio_size_report` / `flash_standalone` 属外部 server。烧录 **已实测（2026-11-04）**，串口 `pio device monitor` **未实测** |

### 1.3 核验器契约要点（schema `/2`）

四个必填：`--log` `--main-c` `--mxproject` `--expect`（`""` = 不查外设）。
可选：`--project-root`（不传则该检查 `skip`）、`--ioc` + `--expect-pins PIN=SIGNAL`（引脚级检查，见 §1.4
第 4 项；`--expect-pins` 可重复、可逗号分隔）、`--allow-signal`（**默认为空**）、`--json-out`、`--report-md`。

> 📝 **`--report-md` 是写行为**：它会生成一份 Markdown 报告文件。`CUBEONE_POLICY=read_only` 下**也允许**
> （属证据输出，与 `.ioc` 写操作不是一回事），但**路径仍受白名单校验**——报错目录落在
> `CUBEONE_ALLOWED_ROOTS` 之外时同样被拒（0.7.0 未配白名单则直接拒绝）。反馈这类"读工具写盘"的
> 行为差异时，不要说成"read_only 下完全不写盘"。

- **退出码**：`0` 通过（可含 `warn`）；`1` 有 `fail`；`2` 输入/IO/参数错。
- **`blocking: true` 不等于"这条报错了"**——它只在 `status` 为 `fail` 时生效。
  判断本次有没有问题，**只看 `verdict` 与各条 `status`**。
- **`--allow-signal` 按"抽出的信号名"精确匹配**（大小写不敏感），**不是整行子串匹配**；抽不出名字才退回
  子串。这是防"用短词关掉守卫"（`--allow-signal signal` 不再放行全部圆括号形态）。
- **`summary.notes`** 收集所有 `skip` 的原因（`"<check_id>: <detail>"`），是"skip 必须解释"的机读落点。
  **自检**：有 `skip` 而 `notes` 为空 = 实现退化，**报 issue**，不要手写补。
- **`inputs.effective_allow_signals`** 是实际生效的白名单：直调为空、`regen.sh` 预置 D8。两处默认值不同**是有意设计**（核验器纯净 / 封装层便利），差异靠这个字段可见；取参一律从 `inputs` 读。
- **版本自证**：`verify_generation.py --version` → `1.2.0 (schema platform32.verify_generation/2)`；本文的 7 项判据与 `--expect-pins` 即该版本行为。
- JSON 全文、七项细则、`/1→/2` 迁移：`references/verify-contract.md`。

### 1.4 七项检查（`checks` 恒为 7 条，顺序固定）

| # | id | `blocking` | 一句话判据 |
|---|---|---|---|
| 1 | `log_cannot_map` | `true` | 日志无 `Cannot map`；命中 `--allow-signal` 降 `warn`。空日志 → `warn` |
| 2 | `main_init_present` | `true` | 每个期望外设有 `MX_<P>_Init(` **定义**（UART 走后缀匹配） |
| 3 | `main_init_called` | `true` | 每个 `MX_*_Init(` 在 `main()` 体内**被调用**（注释掉的不算） |
| 4 | **`pins_present`** | `true` | 每个 `--expect-pins PIN=SIGNAL`：`.ioc` 的 `<PIN>.Signal` **大小写不敏感**一致，**且** `main.c` 有 `__HAL_RCC_GPIOx_CLK_ENABLE()`。**不传 `--expect-pins`（或没给 `--ioc`）→ `skip`** |
| 5 | `mxproject_abs_path` | `true` | `.mxproject` 无 `[A-Za-z]:[\\/]` 盘符路径 |
| 6 | `mx_script_abs_path` | `true` | **三态**：占位符未替换→`warn`；归一化==工程根→`pass`；≠→`fail` |
| 7 | `syscalls_path` | **`false`** | `syscalls.c`/`sysmem.c` + 同行异常关键字 → `warn`，**不阻塞**（D9） |

- **`skip` ≠ 通过 ≠ 失败**：`--expect ""` 使 2/3 都 `skip`；外设全无定义时 3 也 `skip`（同根因只在 2 报一次
  fail）；**4 默认 `skip`，须显式传 `--expect-pins`（直调时还需 `--ioc`）才有结论**；**写证据必须解释原因**
  （读 `summary.notes`）。**G474 上第 6 项稳定出现 1 条 `warn`**（`cubemx-init.mx:5` 的 `__PROJECT_DIR__` 占位符），`verdict` 仍 `pass`——**预期条数恒为 1，≥2 条 = 异常必须查**。
- `log_cannot_map` 的真实实例与"CLI 路径不可达"对照（S3 两组证据）见 `references/verify-contract.md` §4.1。**两项没有 check 是有意的**：`ioc_ask_for_migrate`（核验器跑在生成之后，等它看见人已白等 → 归 `regen.sh` 告警）、`ioc_version_stamp`（提交卫生 → 归 P2）。

#### 🔴 保证边界（最重要的一条免责声明）

> **`verdict: pass` 的保证范围取决于你传了什么（三段式，D30.2）：**
> - **无条件保证**：外设级（整只外设没被丢，第 2/3 项）。
> - **有条件保证**：引脚级——**仅当显式传 `--expect-pins`（+ `--ioc`）**；不传 → `skip`，**不冒充通过**。
> - **明确不保证**：参数级与 `.ioc` 内部计数/排序自洽（`Prescaler` 是否进 `IPParameters`、
>   `Mcu.PinsNb` 是否 +1），v2 known limitation。

**为什么引脚级默认是真空**：`MX_GPIO_Init` 本来就有（PC13 在用），所以"加一个 PB0"时外设级检查全都
不变红——`configure` 说成功、生成成功、核验 PASS，**而 `.ioc` 可能一个字都没改**。这就是第 4 项存在的
唯一理由；**不传它等于放弃这层保护**。

**参数级失明**：核验不查参数是否生效（`PinState`/`Prescaler`，见 `references/verify-contract.md` §5）
⇒ **核验通过 ≠ 电平生效，必须在汇报里明说。**

### 1.5 `regen.sh` 退出码（`1` 与 `2` 的区别是关键）

| 码 | 含义 |
|---|---|
| `0` | 生成 + 核验通过 |
| `1` | **跑过了但结果不对**（日志有整行 `KO`，或核验 FAIL）；**已从备份回滚** |
| `2` | **压根没跑**（`--require-clean` 命中脏 `.ioc`、`--fail-fast-on-migrate` 命中 `AskForMigrate=true`、目录不存在、找不到 CubeMX/java、缺 `.mx`、`--expect` 解析失败） |

看到 `2` **不要去翻核验报告**——报告根本没生成。
⚠️ **`KO` 判据必要不充分**：抓不到 `set ip parameters` 那种"回 OK 却静默空操作"，
**不要让"没 KO"读成"成功了"**（完整判据见 `references/diff-evidence.md` §1）。

## 2. 标准流程

### 路径判定（动手前第一件事）

普通 GPIO（新增引脚 / 改模式 / 改上下拉）→ **路径 A**（透传可做）；
任何非 GPIO（UART / SPI / TIM / ADC / I2C 增改）→ **路径 B**（无透传能力）；
只读审计 → 跳 2–6，做 1 + 7。

**判错的代价不对称**：B 当 A 做 → 全绿但功能不存在的固件；A 当 B 做 → 只是多花手改功夫。
**拿不准就按 B 处理。**

### 第 0 步 · 前置检查

判能力边界 → 选路径 → 核对 CubeMX/pio 路径 → 核验器可用性（`verify_generation.py --version` 应显示 `/2`，
不可用就不许进第 3 步）→ `git status` 记"哪些文件被碰过"（**只作线索，不作判据**）。`.ioc` 已有未提交
改动时先问用户：那是他正在改的，还是本次要处理的？

### 第 1 步 · 只读审计（不改一个字节）

MCP 用 `ioc_field get`（单键）/ CLI 直接读 `.ioc`。产出**改动前基线**（启用了哪些外设、引脚模式、时钟树
关键键值）——回滚时有对照物，并能证明"这外设原本就不存在"。

### 第 2 步 · 备份 `.ioc`

```bash
python scripts/ioc_backup.py --project <工程根> --json-out <证据目录>/ioc-backup.json
```

SHA-256 就是"确实还原了原件"的凭据。**唯一回滚口径（全文通用）**：**改配置前先用
`ioc_backup` 备份 → 失败时从这份备份回滚**（`ioc_backup.py --restore`，或 `regen.sh` 的自动回滚）。
⛔ 不要依赖版本控制回退来还原 `.ioc`：那会连带丢掉用户同目录里其他未提交改动，
而备份只还原本次动过的文件。第 5 步、§4 提交模板、`references/` 一律按这一口径。

### 第 3A 步 · 改配置（普通 GPIO）

`set pin <PIN> <MODE>` 写进只含 `set` 命令的 `.mx`，在 `config load` 已有 `.ioc` 之后执行。

#### 🔴 三级确认（缺一不可，**退出码不作判据**）

1. **回显** 逐行 `OK` 不是 `KO`（**必要不充分**：`set ip parameters` 回 `OK` 却什么都不改）；
2. **diff** `git diff HEAD --numstat -w <工程>/*.ioc` **必须非 0**（唯一能证明真写进去了）；
3. **G1** pass，且 `--expect` 覆盖本次全部外设。

**引脚级落地判据（核验器不查，必须自查）**：`Mcu.PinsNb == 变更前 + 新增数`、
存在 `Mcu.Pin\d+=PB0`、`Mcu.Pin1..N` 连续无空洞。
❌ **不要断言 `Mcu.Pin5=PB0`**——新增引脚会插入 `Mcu.Pin1` 位置、原 1–5 整体后移（✅ D24.3）。

**让第 4 项真正生效**：加 `--expect-pins PB0=GPIO_Output`。⚠️ **直调 `verify_generation.py` 时**还要同传
`--ioc`，否则该项 `skip`、引脚增量仍是真空；**走 `regen.sh` 无需关心（`--ioc` 由脚本自动传）**。

### 第 3B 步 · 改配置（非 GPIO，**无透传能力**）

只能手改 `.ioc` 文本或 GUI。四条硬要求：

1. **必须补白名单**（📄 D3）：`<IP>.IPParameters=a,b,c`；`<Pin>.GPIOParameters=...`。
   不在白名单的 key 会被**静默忽略**。
2. **必须记录改前 SHA-256**（第 2 步的 `ioc-backup.json`）——唯一可靠的回滚锚点。
3. **必须过 G1**，`--expect` 覆盖全部涉及外设（漏写 = 漏检）。
4. **必须人工过 H-6 清单**：`MX_xxx_Init` 定义**和**调用、HAL 模块开关、MSP 时钟/GPIO/DMA、NVIC。

**信号名带 `S_` 前缀**（📄 D4）：PA0 上 TIM2 通道 1 是 `S_TIM2_CH1_ETR`（查 `db/mcu/<型号>.xml`）。

> 🚨 **3B 不可降级为 L3 交差。** L3 只证明"能编译"，而 3B 的风险恰是"外设静默缺失但仍能编译"。

### 第 4 步 · 生成

MCP `cubemx_generate` / CLI §0.4。**stdout/stderr 必须重定向到文件**（§0.4 硬禁令）。
`regen.sh` 的 `-e` 省略会从 `Mcu.IP*` **全量推导**（≠ 你本次期望的）；`--out` 默认落 `/tmp`
（故意不污染 `git status`），要入库时显式指到 `docs/logs/phaseN/<场景>/`。

**行为约束**：`regen.sh` **不修改** `.ioc` 中 `ProjectManager.AskForMigrate` 的值；生成后它为 `true`
属 CubeMX 的正常结果（`saveas` 与 `project generate` 都会写回），**不要在提交前手工复位**。
**但生成前会读它**，并**按可判定性分两级**（D36①）：`true` + **版本戳落后基线** → 4 行 `[regen][warn]`（附可直接复制的置 `false` 命令）；`true` + **版本戳一致** → 一行 `info`
（不喊也不沉默：基线是**常量**、不代表你机器上的版本）；`false`/读不到 → 什么都不打。
上面两档在 `--dry-run` 下也照样输出。需要"宁可退 `2` 也不要挂住"的场景（CI / 批处理）加
`--fail-fast-on-migrate`（**只看该键**，不叠加版本戳判断）。
生成长时间无输出时先查 `MxCube.Version` 是否低于本机版本——**这条是因果结论**（2026-11-04 实测：
旧版本戳 + `AskForMigrate=true` 会让 `-q` 挂死 300 s，日志停在 `Begin LoadConfig()`；
置 `false` 后同一脚本 62 s 成功）。超时后 `regen.sh` 还会按日志形态给**定向诊断**：
只有末行附近真停在 `Begin LoadConfig()` 才判为此因，否则明确说"不能归因"。
见 `references/pitfalls.md` P1 与 `references/regen-exit-codes.md` §4.1 / §4.2。

### 第 5 步 · **生成核验（G1，硬关卡）**

调用见 §1.3，判据见 §1.4。**先分清证据落点（W4-1）**：

- **CLI 直调**（`scripts/verify_generation.py --json-out <路径>`）→ 落 `verify.json`（+ 可选 `--report-md`）。
  提交模板里「见 verify.json 的 summary.notes」指的是这一通道。
- **MCP 通道**（`verify_generation` 工具）→ **证据 = `structuredContent`**（`verdict` / `checks` /
  `summary.notes`）；`--json-out` 由封装层指向系统临时目录、读完即删，**不产生 `verify.json`**，
  返回文本里也不会给一个可打开的 JSON 路径。需要落盘证据就显式传 `report_md`（写 Markdown 报告，
  路径仍受白名单校验）。⛔ 不要在 MCP 调用后去找 `verify.json`，也不要把 MCP 返回文本当日志再喂给 `--log`。

要点：

- **`--expect` 写本次期望存在的每个外设**（漏写 = 漏检，多写 = 假失败），以第 3 步的**意图**为准。
- **`1` 或 `verdict: fail` → 立即从第 2 步的 `ioc_backup` 备份回滚**（`ioc_backup.py --restore`）；**不许**"先构建看看能不能过"——静默丢弃的外设**能构建成功**。
- `2` = 我们自己的输入错了（路径/文件），**不是配置有问题**，别误报给用户。
- 任何 `skip` 都要解释原因；`syscalls_path` 的 `warn` 不阻塞但要写进汇报。
- **必须提醒"保证边界"**：核验 PASS ≠ 引脚级/参数级生效。

### 第 6 步 · 构建

`pio_build` / `pio run -d <工程>` + 尺寸。**必须记录 Flash / RAM 字节数**（L3 的证据本体）。
⚠️ PIO 内置 size **不计** stack/heap 预留：对外报数以 `--print-memory-usage` 或 bin 实际字节为准，
**并注明口径**（P3）。

### 第 7 步 · 汇报 diff

```bash
git diff HEAD --numstat -w          # 判据：工作区 vs HEAD，忽略空白
git ls-files --eol <被报 M 的文件>   # 定性：CRLF 噪音 vs 真改动
```

- **必须带 `HEAD`**：S1 流程含 `git add`，一旦暂存，不带基准的 `--numstat -w` 返回 **0 个文件**（"假干净"）。`-w` 只忽略空白 ⇒ **为 0 表示"没有语义改动"，不是"没有改动"**。
- **`git status` 会过度报告**：`* text=auto eol=lf` 下工作区是 CRLF，`git add` 之前生成文件恒被列 `M`。
  **改一个 GPIO 报 8 个 M 是正常的**；两个工具必须配对用（`-w` 盲区表见 `references/diff-evidence.md`）。
- **`.ioc` 大 diff 只有一个成因**：版本不匹配导致的迁移重写（`grep MxCube.Version` 判断）——匹配 →
  异常、必逐条解释；不匹配 → 预期，拆独立 `chore(ioc):` 提交。619/106 是 `6.17.0→6.18.1` 的观测值，
  **不是阈值**，以当次 `numstat` 为准。
- **必须单独点名**：`USER CODE BEGIN/END` 块外的改动、`Core/**` 的整体重排（查 D1）。
  出错信号：`Drivers/`、`Makefile`、`startup_*.s`、`*.ld` 出现在 diff 里。

### 第 8 步 · 提交

按 §4。**不允许**只写"生成代码"。

## 3. 验证等级（L0–L5；定义沿用模板仓 `AGENTS.md` §3，**模板仓，本仓不含**）

| 等级 | 做什么 | 本仓算什么证据 |
|---|---|---|
| **L0** | 只读检查，仅限纯文档 | 无证据 |
| **L1** | 人工核对文件内容一致性 | 核对记录 |
| **L2** | 命令级真跑（本仓等价物：Python / Node 回归） | `python -m pytest tests/ -q` 与 `node --test tests/node/*.test.mjs` 的通过输出 |
| **L3** | `pio run` | Flash / RAM 字节（注明口径） |
| **L4** | 重新生成后核对 `main.c` 与日志 | `verify.json`（CLI 通道）或 MCP 的 `structuredContent`（`verdict` + 各 `status`） |
| **L5** | 烧录 + 独立判据 + 观察现象 | **已实测（2026-11-04）**：烧录日志（`Verified OK`）+ 寄存器回读 + 目视一致，见 `docs/reports/phase2-bringup-2026-11-04.md` |

L2 命令（本仓真实可跑，不需要开发板；**模板仓的 `Core/Src/stdio_port.c` /
`test/stdio_port_test.c` gcc 回归属模板仓，本仓不含，勿照抄**）：

```bash
python -m pytest tests/ -q
node --test tests/node/*.test.mjs
python tools/check_taskboard.py
python tools/check_release.py
```

**四条不许混**：① `.ioc` 改动没有 L4 = 没做完（L3 不能顶）；② **3B 不可降级为 L3**；
③ 构建通过 ≠ 能用，影响运行时的必须 L5；④ 不复用旧构建数字充本次证据。

## 4. 提交文案模板

```
<type>(<scope>): <中文简述，动词开头，≤50 字，不加句号>

为什么这么改（不要复述 diff）。

路径：A（GPIO 透传）/ B（非 GPIO 手改）                     ← 必填
验证等级：L<n> — <实际执行的命令与结果>
  - 三级确认：回显 <OK/KO> / diff <numstat> / G1 verdict=<pass|fail> errors=<n> warnings=<n>
  - 跳过的检查：见 verify.json 的 summary.notes（无则"无"；notes 空但有 skip = 报 issue）
  - 保证边界：外设级通过；引脚级<传/未传 --expect-pins>；参数级未验证        ← 必填
  - 构建：Flash <bytes> / RAM <bytes>（注明口径）｜ 实板：已达 L5 时写「L5 证据见 docs/reports/phase2-bringup-2026-11-04.md」；本批未做实板验证就如实写「本批未做实板验证」，不套用旧状态词
已知风险：<本次没覆盖到的部分>
```

`<type>`：`feat` `fix` `docs` `chore` `refactor` `test` `build` `ci` `perf` `style` `revert`；
`<scope>`：`ioc` `pio` `board` `vscode` `scripts` `core` `git` `docs`。
**一个提交只做一件事**（格式化/行尾/版本戳重写单独开 `style:` / `chore(ioc):`）。
**硬性禁止**（📄 模板仓 `AGENTS.md` §1.5，**模板仓，本仓不含**）：`push --force`、`--no-verify`、`--no-gpg-sign`、**任何 AI 署名尾注**。

## 5. 陷阱索引（全文见 `references/pitfalls.md`）

| # | 症状 → 处置 |
|---|---|
| P1 | `AskForMigrate`：`project generate` **也会写回 `true`**（旧判断「不改」已被 2026-11-04 实测推翻）；版本戳更旧 + 该键为 `true` 时 `-q` **挂死 300 s**（置 `false` 后 62 s 成功）。`regen.sh` **不改值、默认不拦**，但**生成前分级提示**（落后→`warn` / 一致→一行 `info` / `false`→静默；`--fail-fast-on-migrate` 只要该键为 true 即退 `2`），超时后按日志形态定向诊断。执行者仍必须自己先确认它是 `false` |
| P2 | 只改 1 个 GPIO 却 619/106 重写 → 版本戳不匹配，拆 `chore(ioc):` |
| P3 | Flash/RAM 对不上 → PIO size 不计 stack/heap，以链接器/bin 为准 |
| P4 | `.mxproject` 干净但换机跑不了 → `.mx` 写死绝对路径（指向本工程是合规） |

**D 系列（工具层）**：D1 `formatOnSave` 重排 ｜ D2 纯行尾 diff ｜ D3 白名单漏 key ｜ D4 缺 `S_` 前缀 ｜ D5 `Cannot map`
静默丢弃 ｜ D6 `Drivers/` 只有 `.gitkeep` 正常 ｜ D7 同 P1（**以 P1 为准**）｜ D8 `VP_RIF_VS_RIF1` 忽略 ｜ D9 `syscalls` 不阻塞。
**H 系列（HAL 运行期）**：H-1 UART 能发不能收（NVIC）｜ H-2 TIM 状态机混用 ｜ H-3 停 DMA 关共享时基 ｜ H-4 `CC1OF` ｜
H-5 `Error_Handler` 后无诊断 ｜ **H-6 新增外设没落进生成物且日志干净**。⚠️ `HAL-PITFALLS.md` 只在 F103C8T6 与 H723 仓。
（D / H / P 系列的完整定义见模板仓 `TEMPLATE-PLACEHOLDERS.md` 与 `HAL-PITFALLS.md`，**模板仓，本仓不含**。）

## 6. 串口与烧录（Phase 2，分段更新 2026-11-04）

**已达 L5（2026-11-04 实测）**：探针识别（ST-Link V2）、`pio run -t upload` 烧录
（`Verified OK`）、寄存器回读（GPIOC MODER / ODR）、目视现象（红灯亮、绿蓝灭）。
全链证据与复现命令见 `docs/reports/phase2-bringup-2026-11-04.md`；F4（首烧目标选错板）
与 F5（300 s 默认超时偏紧）两个坑也在该报告。烧录仍须先过 **GATE-2.1 安全确认**（§0.3 红线 1）。

**仍未覆盖（如实保留，不冒充已验证）**：串口段（本工程未启用任何 USART，见 §6.2）、
`pio device monitor` / `pio_monitor_capture` 的波特率与超时、无 VCP 时外接 USB-TTL、
探针/串口异常的错误分类。**这些不是"工具能力不足"的托词，是本次没做的实测**；
要做需先在 `.ioc` 配 USART（非 GPIO 外设，超出本工具能力 ⇒ 手改 `.ioc` / GUI + 强制过 G1）。

### 6.1 Phase 2 实测状态（按 2026-11-04 实测分段）

| 段 | 状态 | 证据 / 还缺什么 |
|---|---|---|
| 探针识别 / doctor | **已实测（2026-11-04）** | `docs/reports/phase2-bringup-2026-11-04.md` §1：`STLINK V2J35S7`、`DPIDR 0x2ba01477`、3.2387 V |
| 烧录（reset/run 语义） | **已实测（2026-11-04）** | 同报告 §2：`Verified OK` + `Resetting Target`；复现命令见 §6 |
| 寄存器回读 | **已实测（2026-11-04）** | 同报告 §2：`GPIOC MODER 0x57FFFF00` / `ODR 0x0000C000`；PC2 输出且 ODR bit2=0 |
| 目视 / LED 现象 | **已实测（2026-11-04）** | 同报告 §4：X-Pulse 板红灯亮、绿蓝灭，与配置一致（F4 为选错板的教训） |
| 串口捕获（波特率/超时） | **未实测** | 本工程未启用 USART；需 boot log 原文 + 波特率 + 超时参数 |
| `pio device monitor` / 无 VCP 外接 USB-TTL | **未实测** | 需接线说明 + 抓到的字节流 |
| 探针/串口异常分类 | **未实测** | 需每一类的错误文案原文 + 判定依据 |

> **接板日怎么走**：照 `docs/guides/gate-2.0-checklist.md` 从上往下执行——它已包含 C3.1 预演暴露的
> 三个前置项（`AskForMigrate` 必须先关、Keil 工程要先补 `platformio.ini`、生成物 diff 必须逐条解释）。
> 上表「未实测」三行**保持未实测直到有真实证据**，不要因为 L5 已达成就连带标成已完成；
> 已达成的四行则可以正常声明 L5（§3 表格、§4 提交模板同口径）。

### 6.2 一个已知的接板坑（C3.1 预演实测，接板前先解决）

- **串口段可能要换工程**：预演用的 `NUEDC_2027/G474/G474_01_gpio` **没有启用任何 USART**（`Mcu.IP*` 只有
  NVIC/RCC/SYS/TIM17），所以"串口验证"必须换带 USART 的工程，或先给该工程加外设——
  而**非 GPIO 外设的增改没有工具能力**（§0.0），只能手改 `.ioc`/走 GUI 并强制过 G1。
- **首次生成会挂死**：`.ioc` 版本戳低于本机 CubeMX 且 `ProjectManager.AskForMigrate=true` 时，无 GUI 的 `-q`
  生成会弹模态框并挂住直到超时（实测 300 s；置 `false` 后 62 s 成功）。且该键**会被 `project generate`
  写回 `true`**，每次拿旧工程生成前都要重新确认。`regen.sh` 会在生成前**分级提示**
  （版本戳落后→`warn`；一致→一行 `info`，因为基线是常量、不代表你机器上的版本），
  `--fail-fast-on-migrate` 只要该键为 `true` 即退 `2`，超时后按日志形态定向诊断。
  详见 `references/pitfalls.md` P1 与接板清单 §2.1。

## 7. 参考与依赖

- 手册页 `references/`：`capability-boundary` / `verify-contract` / `regen-exit-codes` /
  `diff-evidence` / `pitfalls`；外部资料链接见 `references/README.md`。
- **L5 真源（首板实测全链证据）**：`docs/reports/phase2-bringup-2026-11-04.md`（烧录 / 寄存器回读 / 目视 / 复现命令）。
- **npm 包（MCP 工具通道，`npx cubeone-mcp`）**：`docs/guides/npm-publish-and-codebuddy.md`；
  外部 server 的注册与排障：`docs/guides/mcp-registration.md`（**描述外部 server；模板仓 / 外部资料，本仓不含正文**）。
- 状态真源 `docs/TASKBOARD.md`；决策 **D1–D36** 见 `docs/DECISIONS.md`；核验器完整契约
  `docs/reports/t1.2-verifier-contract.md`；版本历史见 git log。
- **单写者边界（按实际执行修正，B-3）**：`scripts/` + `lib/` 由同一人串行改，
  `SKILL.md` / `docs/` 由另一人改，`tests/` 跟随对应实现改，看板连锁批次单独一人一次写完；
  **本文件的改动须由 lead 转派**，不再声明"只由 skill-author 改"。
