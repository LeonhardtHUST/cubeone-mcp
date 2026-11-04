# cubeone-mcp 全量审定报告（agent 工程师视角）

> **审定对象**：`cubeone-mcp` 仓库 + npm 包 `cubeone-mcp@0.7.2`，基线 commit `76e28dc`（CI run `41801100803` success）。
> **日期**：2026-11-04 　**身份**：agent 工程师（以「这个东西交给 AI agent 用，能不能可靠、省事地完成任务」为第一判据）。
> **维度**：MCP 架构 / agent 效率 / 功能性 / 测试·CI·发布 / 文档一致性。
> **方法**：四个只读分面并行审定 + 主审逐文件交叉核对；只读，**未改动任何实现、未跑写盘生成、未烧板、未发版**。
> **证据口径**：每条发现带 `文件:行号`；仓库已登记的已知限制不重复计为发现，只在相关处注明「已登记」。

---

## 0. 结论摘要

**一句话**：代码质量（尤其安全门禁与退出码映射）明显高于同类薄封装层的平均水准，
但**「MCP 包实际提供什么」与「Agent 操作面 SKILL.md 宣称什么」已经分叉**——
本包只暴露 3 个工具，SKILL.md 的「MCP 通道」表列的却是 6 个**外部 server** 的工具，
而 SKILL.md 的 Phase 2 整节仍停在「无硬件、整体挂起」，与 `9fac316` 已达成的 **L5** 相反。
这不是文案瑕疵：**一个按 SKILL.md 行动的 agent，会判定走 CLI 通道、绕开本包的结构化结论，
并拒绝执行一项已经在真板上验证过的能力**。

| 级别 | 条数 | 含义 |
|---|---|---|
| **P0** | 4 | 会让 agent 拿到**全绿但结论不成立**的结果，或让 MCP 能力链整体不可达 |
| **P1** | 12 | 显著影响 agent 判断、可靠性或证据完整性 |
| **P2** | 8 | 效率 / 可维护性 / 文档清晰度改进（多为合并列示） |

**四条 P0**：
1. `A-1` SKILL 的「MCP 通道」列的是外部 server 工具，与本包 3 个工具零交集 ⇒ 装了 MCP 却不会被调用；
2. `A-7` MCP 通道根本不落 `verify.json`，而全流程把它当 L4 证据 ⇒ 证据链断；
3. `A-11` `expect_pins` 有 / `ioc` 无 → 引脚级检查静默 `skip`，`verdict` 仍 `pass`（**L2 只读实测**）；
4. `A-14` `--project-root` 指错目录 → 静默退回单文件扫描，`verdict` 仍 `pass`（**L2 只读实测**）。

**三个最该先处理的**：① 修操作面（A-1 + A-5：本包工具面 / 通道判据 / Phase 2 现状）；
② 给核验器加两条前置护栏（A-11 参数联动 + A-14 工程根有效性 + A-4 日志真实性）；
③ 讲清 MCP 与 CLI 两套证据口径（A-7），避免 agent 交出拼出来的 `verify.json`。

**发版判断**：本轮审定**不改实现**。所列问题均不影响 `0.7.2` 已发布产物的运行正确性，
但 ① ② 属「随包分发的 Agent 操作面」内容，修完需要新补丁版才能到达 npm 用户；
建议与下一批文档修订合并发版，不必单独为审定报告发版。

---

## 1. 范围、方法与边界

| 项 | 内容 |
|---|---|
| 代码面 | `lib/server.mjs`（726 行）、`bin/cubeone-mcp.mjs`（5 行）、`package.json`、`scripts/` 4 个脚本（`verify_generation.py` 1713 行 / `regen.sh` 556 行 / `ioc_backup.py` 486 行 / `ioc_field.py` 317 行） |
| Agent 面 | `SKILL.md`（416 行 / 19 274 字符 / 31 719 UTF-8 字节）、`references/` 6 份（35 121 字符）、`README.md` |
| 工程面 | `tests/`（8 个文件，pytest 94 / Node 37）、`.github/workflows/{ci,publish}.yml`、`tools/` 5 个、`docs/` 49 份 md（约 40.8 万字符） |
| 状态面 | `docs/TASKBOARD.md`（36 条任务 / 28 完成）、`docs/DECISIONS.md` D1–D36、`docs/releases/` 台账 |
| 实测（只读） | `python tools/check_taskboard.py` rc=0、`check_release.py` rc=0、`pytest -q` **94 passed**、文档相对链接 0 断链、CI success |

**没做**：不动实现、不跑 CubeMX 生成 / `pio` 构建 / 烧录（会写盘或需硬件）、不跑 npm 打包实测、
不复核真板现象（沿用 `phase2-bringup-2026-11-04.md` §3.6 的 L5 证据）。
因此凡涉及「运行态行为」的判断，本文标注为**静态推定**，不当作实测结论。

---

## 2. MCP 架构审定

### 2.1 实际工具面只有 3 个，且都是「判据 / 备份 / 字段」类

`lib/server.mjs:190–281` 的 `TOOL_DEFS` 共 3 项：`verify_generation`、`ioc_backup`、`ioc_field`；
`SCRIPTS` 映射（`lib/server.mjs:285–289`）也只指向 3 个 Python 脚本。
`tests/node/server.test.mjs:527–551` 与 `tools/npm_mcp_handshake.mjs:202–203` 都把 `tools/list == 3` 钉死，
`docs/guides/npm-publish-and-codebuddy.md:57–63` 也如实列出这 3 个工具。
**实现、测试、注册指南三者一致，这一层没问题。**

问题出在**操作面**：`package.json:4` 的 description 与 `SKILL.md:3` 的 frontmatter 都宣称
「STM32 工程全流程编排：改配置 → 生成 → 核验 → 构建 → 烧录」「双通道执行：已注册 MCP 走工具通道」，
但本包 MCP 不提供生成 / 构建 / 烧录 / 只读审计中的任何一个。

### 2.2 【P0】SKILL.md 的「MCP 通道」列的是外部 server，与本包 3 个工具零交集

证据链：

| 位置 | 写的什么 |
|---|---|
| `SKILL.md:127–134` §1.2「双通道对照」 | MCP 通道列 `cubemx_load` / `cubemx_configure` / `cubemx_generate` / `pio_build` / `pio_size_report` / `flash_standalone` —— **6 个全是 `vscode-cube-mcp` / `platformio.mcp` 外部 server 的工具**，本包 3 个工具一个都没出现 |
| `SKILL.md:43` §0.1 | 通道判据写成「`cubemx_help` / `pio_system_info` 调用成功 → MCP 通道；调用不存在 → CLI 通道」——探针仍然是**外部 server** 的工具 |
| `SKILL.md:119–125` §1.1 | 「本仓自研（唯一不可替代的部分）」列的是 `scripts/*.py` **文件路径**，不是 MCP 工具名 / 参数 |
| `docs/guides/npm-publish-and-codebuddy.md:98` | 注册本包后「工具数量应为 **3**」 |

**推演（静态）**：用户按 npm 指南只注册 `cubeone-mcp` → `tools/list` 返回 3 个本包工具 →
agent 读 SKILL.md 按 §0.1 探 `cubemx_help` → 不存在 → 判定「CLI 通道」→ 全程跑 `scripts/*.py` 与 `regen.sh`，
**不使用 `structuredContent`、不使用 `isError` 白名单映射、不使用 MCP 的策略/路径门禁**。
即：本包的 MCP server 被装上并连上了，却因为操作面的指引而**不被调用**；
而 agent 自以为遵循了 SKILL.md 的「双通道」规则。

**为什么这是 P0 而不是文案问题**：它让整条 MCP 能力链在最常见的部署形态下不可达，
且失败是**静默的**——CLI 通道确实能跑完任务、返回成功，没有任何报错会暴露「走错了通道」。

**建议**：在 SKILL.md §1.1 与 §1.2 之间插入「本包 MCP 工具面（3 个）」小节，逐个给出工具名 /
必填参数 / 返回里该读哪个字段（`verdict` / `summary.notes` / `structuredContent`）；
把 §0.1 的通道判据改成**分别探测两类 server**（本包工具 / 外部 server），并明确
「本包 3 个工具只覆盖第 2、5 步，其余步骤无论哪条通道都要 CLI 或外部 server」。
`SKILL.md:3` 的 description 相应把「全流程编排」改成「全流程编排（MCP 工具通道仅覆盖核验 / 备份 / 键读写）」。

### 2.3 【P1】协议层 `readOnlyHint` 与工具实际写盘行为矛盾

`lib/server.mjs:201` 给 `verify_generation` 打了 `annotations: { readOnlyHint: true }`，
但同一工具的 `report_md` 参数（`lib/server.mjs:228`、`buildArgs` 的 `:553`）会**写一份 Markdown 报告文件**，
且 `gateArgs` 在 `read_only` 下**明确放行**（`SKILL.md:142–145` 也专门解释了「读工具写盘」）。
`docs/guides/npm-publish-and-codebuddy.md:61` 的工具表又写「写操作？**否**」——
于是同一个工具在**协议注解 / SKILL / 注册指南**三处有三种口径。

后果：客户端若按 `readOnlyHint` 做权限 UI、自动批准或审计归类，会把一次写盘当成只读放行。
**建议**：`readOnlyHint` 改为 `false`（或去掉该注解），并在 description 里点明「`report_md` 会写盘」；
注册指南表格同步改成「否（除 `report_md` 外）」。

### 2.4 【P1 / A-15】`spawnSync` 同步阻塞，单 server 串行

`lib/server.mjs:310–317` 用 `spawnSync(..., { timeout: 120_000 })`。
stdio server 在工具调用期间**阻塞事件循环**，多 agent / 多工具并发请求会排队；
`verify_generation.py` 要读整份 CubeMX 日志（实测可达 638 行以上），120 s 上限与
`regen.sh` 的 300 / 480 s 生成超时不在同一量纲（虽然 MCP 侧不跑生成，但会跑大日志核验）。
**建议**：改 `spawn` 异步 + 每请求可取消；或在文档里注明「本 server 单并发、超时 120 s」。

### 2.5 【P1】随包分发的 SKILL.md 里，9 个 `docs/` 引用有 7 个是死链

`package.json:25–36` 的 `files` 白名单只带 `SKILL.md`、`references/`、两份注册指南、
`bin/`、`lib/`、4 个脚本。而 SKILL.md（**随包**）引用了 9 个 `docs/*.md`：

| 引用 | 是否在 npm 包内 |
|---|---|
| `docs/guides/mcp-registration.md`、`npm-publish-and-codebuddy.md` | ✅ 在 |
| `docs/DECISIONS.md`、`docs/TASKBOARD.md`、`docs/guides/gate-2.0-checklist.md`、`docs/guides/testbeds-board-map.md`、`docs/releases/2026-11-04-v0.7.2.md`、`docs/reports/phase2-bringup-2026-11-04.md`、`docs/reports/t1.2-verifier-contract.md` | ❌ **不在** |

MCP 的 `ReadResource` 也只暴露 `SKILL.md` + `references/*.md`（`lib/server.mjs:620–636`），
所以 agent 通过 MCP 资源同样读不到这 7 份。
其中 `gate-2.0-checklist.md`（接板日清单）与 `testbeds-board-map.md`（F4 刚建的板卡对照，
且 `SKILL.md:79–83` 新指向它）是**执行时必须能打开**的两页。

**建议（二选一，属发布物内容决策，本轮未擅自改）**：
① 最小修复——把这两份指南加进 `files`，并在 SKILL.md 顶部注明「`docs/` 其余路径仅在 GitHub 仓库内可见」；
② 彻底方案——把 `docs/DECISIONS.md`、`docs/TASKBOARD.md`、`docs/reports/t1.2-verifier-contract.md`
一并入包，并把它们注册成 MCP resources。改 `files` 需**下一次发版**才生效。

### 2.6 安全模型复核：这一层是扎实的，不要动

主审逐行核对 `lib/server.mjs:74–182`、`421–543`：路径白名单默认 fail-closed、
`realpath` 逐级上溯防 junction 绕出、`envTruthy` 单一实现、`isExecFailure` 白名单制
（把 `9009` / 裸 exit 1 / Traceback 都判成执行层失败）、`--` 分隔防 value 被 argparse 当选项、
`validateArgs` 只回显参数名不回显 `undefined`。这些设计与注释里的论证自洽，且被 Node 测试覆盖。
**TOCTOU 残余风险已在 `lib/server.mjs:125–127` 如实登记，不计为发现。**

---

### 2.7 【P0】MCP 通道根本不落 `verify.json`，而全流程把它当 L4 证据

`runPython()`（`lib/server.mjs:297–307`）把 `--json-out` **强制指向 `mkdtempSync` 建的临时目录**，
`:328–329` 读回后立即 `rmSync(tmpDir, recursive: true, force: true)`。
而 `SKILL.md:215–217`（第 0 步）、`§4` 提交模板（`:351`）、`docs/TASKBOARD.md` 的 L4 口径、
`docs/guides/gate-2.0-checklist.md` 全都在说「`verify.json` 是 L4 的证据本体」。

后果：走 MCP 通道时，`verify.json` **根本不存在**；MCP 的 `structuredContent` 只在本次响应里，
客户端不落盘、下次会话取不回来。agent 若照 SKILL 去 `docs/logs/phaseN/.../verify.json` 找证据，
会拿到「文件不存在」；**更坏的是它可能自己拼一个 `verify.json` 来交差**（项目最反对的假证据）。

`scripts/verify_generation.py:1705` 还会把那个临时路径打印进 stdout：
`[platform32] JSON 报告：<临时目录>/out.json`，而该目录在返回前已被删
⇒ **返回文本里给了一个必然失效的路径**（P1，见 §3.4）。

**建议**：① 明确区分「MCP 响应内的 `structuredContent`」与「CLI 落盘的 `verify.json`」，
在 SKILL 第 5 步写清「走 MCP 时证据 = 客户端保存的 `structuredContent`，不产生 `verify.json`」；
② 给 `runPython` 加一个可选 `evidence_dir`（受白名单校验）以便需要时落盘；
③ 至少在返回文本里**不要打印将被删除的临时路径**。

---

### 2.8 【P1】MCP 层与 Python 脚本层的契约没有对齐（架构分面，主审逐条复核）

`lib/server.mjs` 是薄封装层，靠一批「手写约定」与脚本对齐；以下 4 处约定没有对齐，
且**每一处都会把 agent 引向错误的排障方向**：

| # | 位置 | 现象 | 后果 / 建议 |
|---|---|---|---|
| 1 | `lib/server.mjs:587–596`（对照同文件 `:20–22` 的注释） | 任何 `res.error` 都被写成「**无法启动 Python** … 处置：改 `CUBEONE_PYTHON`」，且**丢弃** `res.error.code` 之外的 stdout/stderr/诊断。但 `ETIMEDOUT`（`:312` 的 120 s 超时）与 `ENOENT` 是两类完全不同的失败 | 大日志核验或 Windows 冷启动超时会被指引去改 Python 路径，而真实原因是超时。注释里已明确「两类失败措辞有意不同、不要合并」，代码却合并了 ⇒ **自相矛盾**。建议按 `res.error.code` 分支，并把 res 的诊断带进文本 |
| 2 | `lib/server.mjs:202–280` 三个 schema 都写了 `additionalProperties:false`，但 `validateArgs()`（`:421–474`）只遍历 `props` | MCP SDK **不做** JSON Schema 校验（架构分面已确认）；拼错参数名（如 `projectRoot` 代替 `project_root`）会被静默忽略 | 与 §4.2 的 `expect_pins`/`ioc` 同源：agent 以为传了保证，实际 `skip` + `verdict=pass`。建议在 `validateArgs` 里加一行未知键拒绝（成本 3 行） |
| 3 | `lib/server.mjs:239` description 写「backup=备份(**默认**)」、`:253` `required` 却含 `action`、`:554–557` `buildArgs` 在 `action` 缺省时才 fallback 到 backup | 客户端按 description 省掉 `action` → 入口校验直接 `isError` 拒绝，fallback 分支永远到不了 | 三方口径取一：要么 `action` 移出 `required` 并真默认，要么删掉「默认」二字 |
| 4 | `lib/server.mjs:319–327` `readJson()` 用裸 `catch { return null }` 吞掉一切读取/解析错误 | 结构化结论落盘失败时 `structured=null`，仍可能走成功分支：核验器 `verdict=fail` 会被 `isExecFailure` 改判成「执行层失败」文案；`verdict=pass` 则悄悄少了 `structuredContent` | 把解析失败作为独立诊断字段返回，至少写进 stderr 与 `summary.notes`，不要静默 |

> **存疑未证实（不入发现计数）**：架构分面提出 `ioc_field` 的 `key`/`value` 含换行时可能注入
> `.ioc` 的多行内容（`lib/server.mjs:563–565` 与 `scripts/ioc_field.py:147+`）。
> 主审判断需要构造真实 `.ioc` 才能确认 `set_value` 的行匹配行为，本轮只读审定**未实测**，
> 标为「待验证」，不写成确定缺陷。

### 2.9 【P2】架构层的其它改进点（合并列示，不逐条展开）

- `ListTools` 直接返回 `TOOL_DEFS`（`lib/server.mjs:663`），把内部字段 `pathArgs` / `writeActions`
  一起发给客户端 —— 协议噪声，且暴露内部实现；建议只投影协议字段。
- `readOnlyHint` 矛盾见 §2.3（架构分面定 P2，主审因「客户端会据此做权限/自动批准判断」定为 **P1**）。
- **【主审升为 P1 / A-16】** `physical()`（`:128–146`）在整条链 `realpathSync` 都失败时
  **退回纯词法路径**（`return abs`），与 `checkPath` 的「物理路径才是判据」承诺不一致。
  架构分面定 P2，主审因为「路径白名单是本项目唯一的核心安全边界，异常路径上不该 fail-open」
  升为 P1；建议解析失败时返回拒绝，而不是放行。⚠️ 这是 §2.6「安全模型扎实」的**唯一例外**。
- `mkdtempSync` 在系统临时目录建目录（`lib/server.mjs:298`）与 SKILL.md「只读审计不写盘」的措辞有出入，
  虽然它不碰用户工程，但白名单之外的写盘应如实声明。
- `structuredContent` 无体积上限；而 `textResult` 的 `tail(12000)`（`:291–294`）对长 `stdout`
  **只保留末尾**，`render_console` 第一行的 `verdict=PASS` 可能被截掉 ——
  agent 若只扫文本首行会漏掉结论（有 `structuredContent` 兜底，故 P2）。
- `bin/cubeone-mcp.mjs` 权限 `100644`（无可执行位），Windows 经 npm shim 可用，POSIX 依赖 npm 生成 shim；
  `main()` 返回的 Promise 未 `.catch()`，无 `uncaughtException` / 信号处理（`:694–708`）。
- `@modelcontextprotocol/sdk` 精确锁 `1.32.2`，`npm ls` 显示传递依赖约 95 包 —— 对 3 个工具的薄封装偏重，
  但这是 SDK 选型代价，不建议为此换自研协议栈。
- `npm pack --dry-run` 证明 `files` 白名单**运行所需的 4 个脚本 / 2 本指南 / SKILL / references 齐全**
  （架构分面结论，主审认同）。⚠️ 这与 §2.5 不矛盾：**运行所需齐全 ≠ 操作面引用的文档齐全**；
  前者是「能不能跑」，后者是「agent 按 SKILL 指路能不能找到那份文档」。

> **§2.6 修正**：安全模型整体仍属「不要动」的一档，但 `physical()` 的 fail-open 降级（本 §2.9 第 3 条）
> 是一个真实缺口，不应被「整体扎实」盖过去；建议在修 A-2 时顺手一并处理。

---

## 3. agent 效率审定

### 3.1 操作面体量与信息架构

`SKILL.md` 416 行 / 19 274 字符，frontmatter description 单条 485 字符；
`references/` 另有 35 121 字符。两者合计约 **5.4 万字符**（≈ 2 万 token 量级），
而 `docs/` 还有 40.8 万字符不随包分发。
**对 agent 的实际代价**：每次会话若把 SKILL + references 全读进上下文，光操作面就占掉可观窗口；
而 SKILL.md 又反复用「见 D5 / H-6 / P1 / D36」指向**包内不存在**的文档（§2.5），
agent 要么盲猜、要么再向用户要文件，形成「读了但仍缺关键事实」的二次往返。

### 3.2 典型任务调用链量化（按 SKILL.md §2 的 0–8 步）

| 典型任务 | 按 SKILL 现有步骤 | 本包 MCP 工具能覆盖的步骤 | 结论 |
|---|---|---|---|
| 「给工程加一个 GPIO 并验证」 | 第 0/1/2/3A/4/5/6/7/8 步（9 步） | **第 2 步**（`ioc_backup`）、**第 5 步**（`verify_generation`）；第 3A 的 `set pin` 属 CubeMX 命令，不是 `ioc_field` 的键写入 | **2 / 9 步**；生成、构建、diff、提交全靠 CLI / 外部 server |
| 「生成后帮我核一遍」 | 第 5 步 + 汇报 | **第 5 步**（一次 `verify_generation` 调用，返回 `structuredContent`） | **1 次调用即可**，这是本包效率最高的路径 |
| 「只读审计一个 .ioc」 | 第 1 步 + 第 7 步 | 只能 `ioc_field get` **单键**；无引脚表 / 时钟树工具（`cubemx_load` 是外部 server） | 需要 **N 次调用**（N = 关心的键数），或退回直接读文件 |

**效率结论**：本包的工具粒度适合「一次核验」「一次备份」「改一个键」，但 SKILL.md 的触发词
（`SKILL.md:3`）包含「pio 构建」「Flash/RAM 多少」「烧进去看看」「串口有输出吗」——
这些本包**一个都做不到**，却会触发本 SKILL，agent 得先读完 416 行才发现要走 CLI。
**建议**：description 里把触发词收敛到核验 / 备份 / 键读写三类，其余标注「本仓流程文档负责，需 CLI 通道」。

### 3.3 返回契约：结构化和文本各有一半

做得好：`textResult()`（`lib/server.mjs:375–380`）在有结构化结论时同时给
`content[0].text` 与 `structuredContent`，错误用 `isError=true`，
且 `envFootnote()`（`:388–399`）三态显式写出「这次被限制在哪」——agent 不必猜配置。
代价：每次返回固定多一段脚注 + `--- stdout ---` + 尾部 12 000 字符截断（`:291–294`、`:611–614`），
短调用里**噪声占比可能高于正文**；`tail()` 只留末 12 000 字符，长日志的关键头部会被截掉
（虽有 `structuredContent` 兜底，但 agent 若只读 text 就会漏）。
`TOOL_DEFS` 没有 `outputSchema`，返回 `structuredContent` 缺一份机器可校验的形状声明。

### 3.4 【P1】返回文本里有死路径，以及一句对 2/3 工具不成立的提示

- `lib/server.mjs:613` 对所有落了 JSON 的调用都追加
  `--- 结构化结论见 structuredContent（verdict / checks / summary.notes）---`。
  但 `ioc_field.py:280–284` 与 `ioc_backup.py` 的 payload 里**没有** `verdict` / `checks` / `summary.notes`
  （前者是 `{ioc, action, key, value, line}`）。agent 照这句去解析会扑空。
- `scripts/verify_generation.py:1705` 打印的 `JSON 报告：<临时路径>` 在 MCP 下指向已删除目录（见 §2.7）。
- 失败分支的 stderr 里也可能带同一路径（`lib/server.mjs:605`）。

**建议**：提示按工具分流（核验器才说 `verdict/checks`）；把 `JSON 报告：` 行改成
「JSON 已通过 MCP structuredContent 返回」或仅在 `--json-out` 由调用方显式指定时打印绝对路径。

### 3.5 【P1】SKILL 的 L2 命令引用本仓根本不存在的文件

`SKILL.md:329–336` 给的 L2 主机回归命令要求
`Core/Src/stdio_port.c`、`test/stdio_port_test.c`，并把 L2 定义成「主机 gcc 回归」；
而本仓根目录下**这两个文件都不存在**（主审 `ls` 实测），`AGENTS.md` 也不在仓内
（`SKILL.md:318` 说 L 等级定义来自模板 `AGENTS.md §3`）。
段落末尾还写着 `pio run` —— 那是 L3 的动作，混在 L2 命令块里。

后果：agent 想声明 L2 时照抄命令必报 `No such file or directory`，
然后要么误降等级、要么自己造文件。**建议**：把这段标成「引自模板仓、本仓不适用」，
或替换成本仓真实存在的 L2 等价物（pytest / Node 单测），并明确「本仓 L2 = 命令级真跑」。

---

## 4. 功能性审定：假绿风险

### 4.1 【P1】「`--log` 必须是 CubeMX 原始日志」只有文档护栏，代码层零校验

`SKILL.md:95–102` 用红色警示写明了这条：MCP 封装层会删掉 `INFO`/`WARN` 行，
而真实的 `Cannot map` 行恰恰是 `[INFO]` ⇒ 传 MCP 返回文本会**假阴性且 `verdict` 仍 PASS**。
仓库对风险的认知是充分的；问题在于**防护 100% 压在 agent 自觉上**：

- `check_log_cannot_map()`（`scripts/verify_generation.py:584–618`）只做两件事：扫 `Cannot map` 正则、
  判空。传进来的若是 MCP 返回文本（非空、但 `INFO` 行已被删），`:611` 直接返回 `STATUS_PASS`
  「生成日志无 'Cannot map' 命中」——**这正是文档警告的假绿形态，代码没有任何特征校验**；
- `:604–609` 空日志只给 `STATUS_WARN`，而 `verdict` 只看 `errors`（`:1429`
  `"verdict": "fail" if errors else "pass"`）⇒ **空日志 = `verdict=pass` + 1 条 warn**。
  agent 通常只读 `verdict`，warn 极易被忽略。

**建议**：加一条前置的「日志真实性」判据（blocking），例如要求日志含 CubeMX 特征行
（`Begin LoadConfig` / `Time for Copy HAL` / 至少 N 行 / `config load` 回显等）且行数下限；
不满足时 `verdict=fail`（或新增 `unknown` 态），并在 `summary.notes` 写明。
把安全边界从 prompt 下沉到代码，才符合「agent 会犯错」这个前提。

### 4.2 【P0】`expect_pins` 与 `ioc` 没有联动校验，引脚级检查静默 skip 但 `verdict` 仍 pass

`check_pins_present()`（`scripts/verify_generation.py:920–928`）里：
传了 `--expect-pins` 却没传 `--ioc` → 直接 `STATUS_SKIP`，理由写进 `summary.notes`；
而 `:1429` 的 `verdict` **只看 `errors`** ⇒ 结果仍是 `verdict=pass`。

`SKILL.md:247–248` 其实已经提醒「直调核验器时还要同传 `--ioc`，否则该项 skip」，
但 `lib/server.mjs:214–222` 的 `inputSchema` 把两者都设成**可选**，
`validateArgs()`（`:421–474`）只查必填 / enum / 类型，**不查这个配对**；
`buildArgs()`（`:549–551`）也照传不误。

后果（这是本项目最忌讳的形态）：agent 明确表达了「我要检查 PC2=GPIO_Output」，
拿到 `verdict=pass`，以为引脚级已验证，实际上**一次都没查**。
`summary.notes` 里虽有解释，但 skip 不升 warn、不进 `errors`，只读 verdict 的消费者完全看不见。
与 §4.1 的「假绿」叠加后，一次 MCP 核验可以同时含「日志不是真日志」+「引脚没查」，仍然全绿。

**只读实测（本轮主审，L2；导入模块后在内存里调 `check_pins_present`，未写任何文件）**：

```text
expect_pins 有 / ioc 无              -> status=skip  | 传了 --expect-pins 但没给 --ioc，无法读取 <PIN>.Signal，跳过引脚级检查
expect_pins 有 / ioc 有但不符         -> status=fail  | 1/1 个期望引脚没有真正生效：PC2: .ioc 里 PC2.Signal=GPIO_Input
expect_pins 有 / ioc 有且符合         -> status=pass  | 全部 1 个期望引脚都在 .ioc 与生成物中对上
expect_pins 无 / ioc 无              -> status=skip  | 未提供 --expect-pins，跳过引脚级检查
```

即：**只要漏传 `ioc`，判据就从「能抓错的 fail」退化成「什么都不做的 skip」**，
而 `verdict` 对两者一视同仁地只看 `errors`（`:1429`）。这不是文档提醒能兜住的形态。

**建议**：`validateArgs` 加一条联动规则（`expect_pins` 非空 ⇒ 必须给 `ioc`，否则 `isError=true`）；
或在 `check_pins_present` 把该情形升为 `fail`（既然调用方明确要求了引脚级保证）。
配套补回归用例：只给 `expect_pins` 不给 `ioc` 必须**不能**得到 pass。

### 4.3 【P1】SKILL 内部对「失败后怎么回滚」自相矛盾，且其中一种做法会丢用户改动

| 位置 | 写的什么 |
|---|---|
| `SKILL.md:230–231`（第 2 步） | 「手改的回滚**只能靠这份备份**，别指望 `git checkout`（会连带丢掉用户其他未提交改动）」 |
| `SKILL.md:287`（第 5 步） | 「`1` 或 `verdict: fail` → **立即回滚**（`ioc_backup.py --restore` **或 `git checkout --`**）」 |
| `scripts/regen.sh:113`、`:325–347` | 「失败回滚从**备份**恢复，不是 git checkout」；且 `:347` 明确 `Core/` **不自动回滚**（只打印 git 状态，便于看清生成动了什么） |

第 5 步给了两个不等价的选项，其中一个正是第 2 步与 `regen.sh` 明确否定的；
另外 `regen.sh:96` 已声明「退出码 1 = 已从备份回滚」，
所以第 5 步的「立即回滚」在走 `regen.sh` 时是**重复动作**（可能把用户生成后的合法改动也退掉）。

**建议**：第 5 步改成「若走 `regen.sh`，它已自动回滚 `.ioc`/`.mxproject`，只需读 `verify.json` 定位原因；
只有裸调核验器时才手动 `ioc_backup.py --restore`」，**删掉 `git checkout --` 这个选项**。

### 4.4 已登记、因此**不计为新发现**的风险（避免审定时重复计数）

| 风险 | 登记位置 |
|---|---|
| 7 项判据对 `PLLN` 等参数级改动失明 | `SKILL.md` §1.3/§5、`references/verify-contract.md`、D36② |
| 非 GPIO 外设增改没有工具能力 | `SKILL.md:24–39`、`references/capability-boundary.md` |
| `ioc_field set` 对键名无白名单，漏 `IPParameters` 会「日志干净什么都不报」 | `references/capability-boundary.md:66`（这是能力层，不是权限层，见该文件 `:8–10`） |
| `report_md` 在 `read_only` 下仍写盘 | `SKILL.md:142–145`（但**协议注解**未同步，见 §2.3） |
| 白名单不防 TOCTOU | `lib/server.mjs:125–127` |
| T6 在 CI 恒 SKIP | `docs/TASKBOARD.md` C1 行、`tools/npm_mcp_handshake.mjs` 注释 |

主审核实 `scripts/ioc_field.py` 确实对 `key` 无白名单（`set_value()` 为通用键值写入），
但这与 `capability-boundary.md` 的分层定义一致，**不是实现缺陷**；只在 §4.1 的组合风险里需要留意。

---

### 4.5 【P0】`--project-root` 指错目录时静默退回单文件模式，`verdict` 仍 pass（L2 实测）

F1 修复（`0.7.2`）让核验器在给了 `--project-root` 时扫 `Core/Src/*.c`，
但 `_read_source_texts()`（`scripts/verify_generation.py:406–446`）对「目录存在却没有 `Core/Src`」
和「`Core/Src` 是空的」这两种情形都直接 `return segments`（只剩 `main.c`），
`mx_script_abs_path` 因此 `skip`，而 `verdict` 只看 `errors`（`:1429`）。

**只读实测（主审，纯内存 `verify_documents()`；临时空目录在系统 temp，未碰仓库）**：

```text
project_root=None                  verdict=pass  errors=0  (mx_script_abs_path=skip)
project_root=/definitely/not/exist verdict=fail  errors=1  (mx_script_abs_path=fail)
project_root=存在但空的工程根        verdict=pass  errors=0  (mx_script_abs_path=skip)  ← 假绿
project_root=有 Core/Src 但为空      verdict=pass  errors=0  (mx_script_abs_path=skip)  ← 假绿
```

也就是说：
- 指到**完全不存在**的路径 → 有 `fail`，能挡住；
- 指到**存在但不对**的目录（拼错一层、指到父目录、指到刚 clone 还没生成的空壳）→
  **静默退化成「没传 project-root」**，只扫 `main.c`，并给出 `verdict=pass`。

这恰好是 F1（CoupleFile 工程假失败）修复的**反向漏洞**：修复让多文件扫描生效，
却没验证「这个目录到底是不是工程根」，于是在 `CoupleFile=true` 工程上，
一个指错的 `--project-root` 会把「定义在 `gpio.c`」重新变成「看不见」，而且这次**不报错**。

**建议**：`verify_documents()` 入口加一条 blocking 前置判据 —— 给了 `project_root` 却找不到
`Core/Src/main.c` 或该目录下无任何 `.c` ⇒ `fail`（或至少 `warn` + 写 `summary.notes` 并让 `verdict` 不能是纯 `pass`）；
`regen.sh` 已自己拼对路径，主链不受影响，主要保护「agent 裸调核验器」这条路径。

### 4.6 功能性分面的两条定级，主审不予采纳（记录在案）

| 分面结论 | 主审核实 | 裁定 |
|---|---|---|
| **F-04（定为 P0）**：SKILL 的 CLI 示例命令跑不通，`regen.sh` 没有 `--main-c` / `--mxproject` / `--log` | `scripts/regen.sh:75/78/79` 的 usage 与 `:137–141` 的解析明确支持 `-l,--log` / `--main-c` / `--mxproject`；`SKILL.md:88–92` 那条命令是**裸调 `verify_generation.py`**（不是 `regen.sh`），`--help` 显示 8 个参数全部受支持 | **误报，不计入发现**。真正存在的只是「两套入口的参数面不同、SKILL 没讲清什么时候用哪个」，降为 P2 文档清晰度 |
| **F-07（定为 P2）**：`regen.sh` 硬编码 Windows 路径，Linux 开箱不可用 | 该默认值可用 `ST_CUBEMX_JRE` / `ST_CUBEMX_EXE` 覆盖（`regen.sh:80–81`），`SKILL.md:124` §1.1 与 D1 已明确登记「本机锁 6.18.1、路径见 §0.2」，是有意的本机工具约束 | **已登记，不计为新发现**；可作为未来「自动探测安装路径」的 P2 改进 |

> 这两条写进来是为了说明：**审定不是把四个分面的输出相加**。分面给的是线索，
> 主审对每条 P0 都做了可复现核实，误报要驳回，否则报告本身就成了新的失真源。

### 4.7 功能性分面的其余改进点（P2，合并列示）

- `scripts/verify_generation.py:1671–1674` 在 `--log` / `--main-c` / `--mxproject` 读入前**不做任何形态校验**
  （不是 CubeMX 日志 / 不是 C 源码 / 不是 ini 都能进判据），与 §4.1 是同一个根因的两面。
- `scripts/ioc_field.py:147+` 的键匹配/多行歧义处理细节、`regen.sh` 的 `--skip-generate`
  与 `--dry-run` 组合行为，建议补参数化负样本（功能性分面指出当前 `tests/` 未覆盖）。
- `tools/check_release.py` / `check_taskboard.py` / `mcp_smoke.py` 未套用三脚本的
  TTY 感知编码加固 —— 它们不打 `→` 故当前不崩，但属**同一类缺陷的未覆盖区**，
  加固函数应提到共享模块而不是复制三份（这也是 `envTruthy` 那条已做对的做法）。
- `scripts/regen.sh` 头部 sandbox 相关的 5 条约定注释，与代码里实际的 cwd / 权限检查
  并非逐条对应，建议对齐或删掉过时条目。

---

## 5. 测试 / CI / 发布 / 文档一致性

### 5.1 两道机器校验都没有覆盖「操作面状态」

`tools/check_taskboard.py` 校验快照 / 证据路径 / tag，`tools/check_release.py` 校验四处版本轴 + 发布正文。
两者都不读 `SKILL.md` / `README.md` 里的**状态陈述**。结果就是下面这张表：

### 5.2 【P1】过期 / 自相矛盾陈述清单（L5 已达成，操作面仍写「无硬件」）

| 位置 | 原文片段 | 当前事实 | 建议 |
|---|---|---|---|
| `SKILL.md:20` | 「Phase 2 烧录段无硬件，整体挂起（D7）」 | `9fac316` 已 L5（红灯亮、绿蓝灭 + 寄存器回读） | 改为「Phase 2 首板 L5 已达成，见 `docs/reports/phase2-bringup-2026-11-04.md`」 |
| `SKILL.md:96` | 「⚠️ Phase 2 才用、**未实测**：`pio run -t upload`」 | 已实测 `Verified OK` | 改「已实测（CLI 通道）」并给证据路径 |
| `SKILL.md:134` | 「烧录串口 ⚠️ Phase 2 未实测」 | 烧录已实测；**串口仍未做**（两句要拆开） | 拆分：烧录 ✅ / 串口 ⚠️ 未启用 USART |
| `SKILL.md:327` | 「L5 …（当前无硬件，一律缺）」 | L5 已有完整证据 | 改为证据要求：烧录日志 + 现象 + 独立判据 |
| `SKILL.md:353` | 「实板：未验证（无硬件）」（提交模板） | 模板应允许写 L5 | 改成条件项 |
| `SKILL.md:376–394` §6 整节 | 「串口与烧录（Phase 2，挂起）」「占位骨架，无硬件不填能力宣称」+ 5 行「未实测（无硬件）」 | 首板 L5 达成；探针 / 烧录 / 寄存器 / 目视均有实测；串口仍未做 | 整节重写为「已达成 / 未覆盖」两栏 |
| `README.md:176` | 「本仓当前无硬件」 | 已有 X-Pulse + ST-Link V2 实测 | 改为「首板 L5 已达成」 |
| `README.md:287` | 「Phase 2 挂起：实板烧录验证（L5）需要接板后继续」 | 已完成 | 删除或改为已完成 |
| `docs/README.md:14` / `:85` | 「D1–D35」 | 已到 **D36** | 改 D1–D36 |
| `SKILL.md:413` | 「决策 D1–D30 见 `docs/DECISIONS.md`」 | 已到 D36，且三处口径互不相同 | 统一为 D1–D36 |

`git log -- SKILL.md` 显示 `9fac316`（L5 收口）之后 SKILL.md **只被 `76e28dc` 改过 §0.3 一处**，
§6 从来没有同步过 —— 说明这不是一次漏改，而是**状态真源与操作面之间没有机器校验的结构性缺口**。

**建议（机制）**：给 CI `lint` job 加一条轻量扫描，禁止 `SKILL.md` / `README.md` 出现
「无硬件 / 整体挂起 / 未实测（无硬件）」等已失效状态词，
并校验 `docs/README.md` 的 D 编号与 `DECISIONS.md` 最大编号一致。
成本很低，但能把这次这类漂移挡在提交前。

### 5.3 【P2】其它一致性观察

- `SKILL.md:416` 写「**本文件只由 skill-author 改**」，而仓库实际由 lead / software-engineer /
  本轮 agent 工程师多次修改（含 `76e28dc`）；单写者边界的名分与执行已脱节，建议改为「改动须由 lead 转派」。
- `README.md:271` 写 `mcp_smoke.py`「真实调用 4 个工具」，而 `tools/list` 是 3 个；
  应为「4 次调用 / 4 个场景」，避免与注册指南的「工具数量应为 3」冲突。
- `docs/README.md:57` 把 `2026-11-04-v0.7.1.md` 标成「当前版本」，实际 `latest = 0.7.2`。
- CI 顶层 4 个 job（`pytest` / `node` / `windows` / `lint`）经 matrix 展开为 7 个，
  与 D35 修正后的口径一致 —— **不是问题**，此处记录以免后续误判。

---

### 5.4 【P1】`docs/README.md` 索引漏掉了最关键的几份当期文档

主审用脚本比对 `docs/` 下 49 份 md 与 `docs/README.md` 的提及情况：
18 份未被提及，其中 14 份是 `docs/logs/**` 下的原始证据（索引已声明只给目录级说明，可豁免），
**其余 4 份是真漏项**：

| 漏项 | 为什么不该漏 |
|---|---|
| `releases/2026-11-04-v0.7.2.md` | 当前版本的发布正文；`docs/README.md:57` 反而把 `v0.7.1` 标成「当前版本」 |
| `reports/phase2-bringup-2026-11-04.md` | **唯一的 L5 证据报告**，接板首日的全部结论都在这里 |
| `reports/t0-redaction-audit.md` | 脱敏审计结论（安全相关） |
| `reports/audit-2026-11-04-agent-engineer.md` | 本报告（本轮交付时已补入索引） |

`docs/releases/README.md:21` 里 **0.7.2 台账行是齐的**，所以问题只在总索引漂移。
结合 §5.2 的 D 编号与版本措辞，说明这个「一页索引」缺机器校验。

### 5.5 分面口径分歧与主审裁定（记录在案，避免结论被误读）

效率分面把 `SKILL.md` 的「Phase 2 挂起（D7）」当成**已登记的历史决策**排除在发现之外。
主审逐行复核后**不采纳**这一排除，理由：

- D7 是「本会话无硬件 ⇒ Phase 2 整体后移」的**当时决策**，其状态落点在 `docs/TASKBOARD.md`；
  该看板 R2 行现为「**已完成 / L5**」，GATE-2.0 已过，`phase2-bringup-2026-11-04.md` §5 已写「四段全部走通」。
- 操作面（SKILL.md / README.md）**没有同步**，仍在 §6 用 5 行「未实测（无硬件）」告诉 agent
  「在那之前本节一律按『无能力』对待」（`SKILL.md:394`）。
- 因此这不是「已登记的限制」，而是**状态真源与操作面之间的漂移**，且会直接改变 agent 的行为
  （拒绝执行一项已验证的能力、把可声明 L5 的结论压成 L3）。
- 佐证：`git log -- SKILL.md` 显示 `9fac316` 之后 SKILL.md 只被 `76e28dc` 改过 §0.3 一行组，§6 从未动过。

**裁定**：保留为 **P1（A-5）**，并在 §5.2 逐条列出 11 处位置。

---

### 5.6 测试覆盖与发布链（测试/CI/发布分面维度，主审合并复核）

**覆盖空白（与 §4 的三条 P0/P1 一一对应，这是最该补的一类测试）**：
`tests/` 共 8 个文件，`tests/node/server.test.mjs` 把退出码白名单（组 1，12 条）、
路径白名单（组 2）、env 解析（组 7）钉得很死，`tests/test_verify_generation.py`（40 KB）
与 `test_verify_multifile.py`（12 KB）覆盖 7 项判据与多文件扫描。
但主审检索确认，以下四项**没有任何用例**：

| 空白 | 对应发现 |
|---|---|
| 传非真生成日志 / 空日志时的 `verdict` | A-4 |
| `expect_pins` 有而 `ioc` 无 | A-11 |
| `project_root` 指到存在但空的工程根 | A-14 |
| `readOnlyHint` / `report_md` 写盘语义 | A-2 |

⇒ 这四条都是「测试没抓到」而不是「测了没过」，补负样本即可，不需要重构。

**覆盖率门槛偏薄**（P2）：`.github/workflows/ci.yml:78–79` 用 `--cov=scripts --cov-fail-under=36`，
而基线实测 37%（看板 C1 行）⇒ 只剩 **1 个百分点**余量。
新增一个未覆盖的分支就可能把 CI 判红，反过来也说明这个门槛几乎不提供保护；
建议要么随覆盖率上升逐步抬门槛，要么改成「只允许下降不超过 N 点」的相对门禁。

**CI / 发布链复核结论：这一段是扎实的，不要动**：
- 顶层 4 个 job（`pytest` / `node` / `windows` / `lint`）经 matrix 展开为 7 个，与 D35 修正后口径一致；
- `lint` job 显式 `fetch-depth: 0`，理由写清了「浅克隆会让判据③静默降级成 note」——
  这是把「静默跳过等于假装检查过」落到配置层的范例；
- `check_release.py` **故意不挂 CI**（`ci.yml:255+` 注释），因为本仓长期存在未发版改动，
  挂上会每次都红 ⇒ 判据失去信息量。这个取舍是对的，**不要因为本报告 A-6 的建议就把它挂进 CI**；
  A-6 要新增的是「操作面状态词扫描」，与版本轴校验是两件事；
- `shellcheck` 非阻塞但用 `::warning` + Job Summary 显式留痕，不是 `|| true` 掩耳盗铃；
- `.github/workflows/publish.yml`：发布前跑同版本 `pytest==9.2.0`、
  显式 `npm install -g npm@latest`（OIDC 要求 ≥11.5.1）、`id-token: write` + `--provenance`、
  幂等护栏用 `::warning` 跳过而非判红（D33 补发历史 Release 的必然路径），
  且 `npm view` 显式带官方 `--registry` —— 恰好绕开了本机 npmmirror 只同步到 0.7.1 的坑。
- T6 在 CI 恒 SKIP 已登记（C1 行），且脚本会**点名** SKIP，不是静默跳过。

---

## 6. 发现总表

> 「需发版」= 修改落在随 npm 包分发的文件（SKILL.md / lib / scripts / package.json）里，
> 修完要新补丁版才能到达用户；纯 CI / 仓库文档改动不需要。

| 编号 | 级别 | 标题 | 章节 / 关键证据 | 需发版 |
|---|---|---|---|---|
| **A-1** | **P0** | SKILL 的「MCP 通道」列外部 server 工具，与本包 3 个工具零交集 ⇒ MCP 能力不可达 | §2.2 `SKILL.md:43`, `:127–134` vs `lib/server.mjs:190–281` | 是 |
| **A-7** | **P0** | MCP 通道不落 `verify.json`，而全流程把它当 L4 证据 | §2.7 `lib/server.mjs:297–329` vs `SKILL.md:351` | 是 |
| **A-11** | **P0** | `expect_pins` 有 / `ioc` 无 → 静默 `skip`，`verdict` 仍 `pass`（L2 实测） | §4.2 `verify_generation.py:920–928`, `:1429`；`lib/server.mjs:421–474` | 是 |
| **A-14** | **P0** | `--project-root` 指错目录 → 静默退回单文件扫描，`verdict` 仍 `pass`（L2 实测） | §4.5 `verify_generation.py:406–446` | 是 |
| A-2 | P1 | `readOnlyHint=true` 与实际写盘、三处文档口径矛盾 | §2.3 `lib/server.mjs:201`, `SKILL.md:142–145`, 注册指南 `:61` | 是 |
| A-3 | P1 | 随包 SKILL 的 7 个 `docs/` 引用是死链（含接板清单、板卡对照） | §2.5 `package.json:25–36`, `lib/server.mjs:620–636` | 是 |
| A-4 | P1 | 「`--log` 必须是真日志」只有文档护栏；空日志仅 warn，仍 `pass` | §4.1 `verify_generation.py:604–618`, `:1671–1674`, `:1429` | 是 |
| A-5 | P1 | SKILL/README 共 11 处停在「无硬件 / 挂起」，与已达成的 L5 相反 | §5.2 逐条清单；§5.5 主审裁定 | 是 |
| A-6 | P1 | 状态真源与操作面之间无机器校验，漂移可再次发生 | §5.1 两道校验均不读 SKILL/README | 否（CI） |
| A-8 | P1 | MCP 层与脚本层契约未对齐（4 子项：ETIMEDOUT 误归因 / 未知参数静默 / `action` 默认三方矛盾 / `readJson` 吞错） | §2.8 `lib/server.mjs:587–596`, `:421–474`, `:239/253`, `:319–327` | 是 |
| A-9 | P1 | 返回文本含必然失效的临时路径；「verdict/checks」提示对 2/3 工具不成立 | §3.4 `verify_generation.py:1705`, `lib/server.mjs:613` | 是 |
| A-10 | P1 | SKILL 的 L2 命令引用本仓不存在的 `stdio_port.c` / `AGENTS.md` | §3.5 `SKILL.md:318`, `:329–336` | 是 |
| A-12 | P1 | SKILL 第 2 步与第 5 步回滚口径自相矛盾，其中 `git checkout --` 会丢用户改动 | §4.3 `SKILL.md:230–231`, `:287`, `regen.sh:113` | 是 |
| A-13 | P1 | `docs/README.md` 索引漏掉 0.7.2 正文 / L5 报告 / 脱敏审计 / 审定报告，且把 0.7.1 标「当前版本」 | §5.4 脚本比对 49 份 md | 否 |
| A-15 | P1 | `spawnSync` 同步阻塞 + 120 s，单 server 串行，超时又被误归因（与 A-8①叠加） | §2.4 `lib/server.mjs:310–317` | 是 |
| A-16 | P1 | `physical()` 全链解析失败时退回纯词法路径（fail-open），与「物理路径才是判据」承诺冲突 | §2.9 `lib/server.mjs:128–146` | 是 |
| B-1 | P2 | 触发词覆盖本包做不到的 4 类任务；返回噪声与 12 000 字符尾部截断 | §3.2/§3.3 `SKILL.md:3`, `lib/server.mjs:291–294`, `:611–614` | 是 |
| B-2 | P2 | 无 `outputSchema`；`structuredContent` 无体积上限；长 stdout 会截掉首行 `verdict` | §3.3 `lib/server.mjs:190–281`, `:375–380` | 是 |
| B-3 | P2 | 单写者名分、工具数量措辞、发布台账「当前版本」、D 编号四处小漂移 | §5.3 `SKILL.md:416`, `:413`, `README.md:271`, `docs/README.md:57` | 否 |
| B-4 | P2 | `ListTools` 夹带内部字段；临时目录写盘未声明；bin 可执行位 / Promise 未 catch；SDK 95 包依赖 | §2.9 | 部分 |
| B-5 | P2 | 编码加固未覆盖 `tools/*`；`--log` 读入前无形态校验；`regen.sh` 参数组合缺负样本 | §4.7 | 否 |
| B-6 | P2 | 两套入口（regen.sh / verify_generation.py）参数面不同，SKILL 未讲清何时用哪个 | §4.6 F-04 降级后的有效部分 | 否 |
| B-7 | P2 | 硬编码 Windows CubeMX 路径（已有 env 覆盖、已登记），可升级为自动探测 | §4.6 F-07 降级 | 否 |
| B-8 | P2 | `regen.sh` 头部 sandbox 约定注释与代码不逐条对应 | §4.7 | 否 |

**未计入发现**：功能性分面 F-04（主审核实为误报，§4.6）、F-07（已登记，§4.6）、
架构分面的换行注入猜想（待实测，§2.8）、以及 §4.4 列出的 6 类已登记已知限制。

---

## 7. 已做得好、不要改

1. **退出码白名单制**（`lib/server.mjs:346–361`）：把 `9009`、裸 exit 1、Traceback、
   `[not-found]` 标记、落了 JSON 的 `verdict=FAIL` 分开处理。这是同类封装层最常出错的地方，
   注释还写清了「为什么不用只认 exit 2」——**别简化成 `status !== 0`**。
2. **默认 fail-closed 的路径白名单 + 物理路径上溯**（`:74–182`）：`realpath` 逐级找最近存在祖先，
   避免「目标不存在时退化成词法路径」造成的假失败；拒绝文案把 `no-roots`（配置缺失）与
   `越界`（路径选错）分开说，直接给可复制的 env 配置。
3. **`--` 分隔与参数入口校验**（`:421–474`、`:558–566`）：防 `value` 以 `-` 开头被 argparse
   当选项（`--dry-run` 静默改写盘语义），防 `undefined` 拼进命令行产生「文件不存在：undefined」。
4. **分级提示与超时定向归因**（`scripts/regen.sh`，D36①）：不误拦、不静默、不告警疲劳；
   超时只在日志尾部命中 `Begin LoadConfig()` 才归因，否则明说「不能归因」——
   这个「宁可承认不知道」的设计在 F5 现场已被真机验证过。
5. **判据单点归属**：JS 侧只做协议 / 门禁 / 退出码映射，所有判据都在 Python 脚本里
   （`lib/server.mjs:3–6`），`verify_generation.py` 的 `summary.notes` 把每个 `skip` 的原因落盘。
   两道机器校验（`check_taskboard` / `check_release`）也是同一思路的延伸。
6. **stdout 纪律与启动自检**：所有日志走 `console.error`（`lib/server.mjs:646`、`:704`），
   stdio JSON-RPC 通道不被污染；`CUBEONE_REQUIRE_ROOTS` 的 fail-fast 放在 `server.connect()` **之前**
   （`:640–656`），避免「连上了但每次调用都被拒」这种最难排障的形态。
   启动横幅与 `envFootnote()` 用同一套三态口径，运维第一眼就能分辨严格 / 宽松 / 有白名单。
7. **`envTruthy` 单一实现 + 测试钉死**（`:88–99`）：`CUBEONE_REQUIRE_ROOTS` 与
   `CUBEONE_ALLOW_NO_ROOTS` 这对「收紧 / 放宽」对偶开关共用一份解析逻辑，
   `tests/node/server.test.mjs` 组 7-1 用 10 条断言把取值契约固定住 —— 复制第二份解析函数
   是这类代码最典型的静默降级来源，这里避免了。
8. **`--json-out` 的插入位置**（`:303–307`）：识别 `--` 并把选项插到它前面，
   否则 `ioc_field` 的位置参数结构会让 argparse 把 `--json-out` 当位置参数。
   这个细节说明作者真的读过下游 argparse 的参数契约。

---

## 8. 处置建议（按优先级，不排期、不擅自改实现）

1. **先堵假绿（最优先，因为会产出错误结论）**：A-11 参数联动校验、A-14 `--project-root` 有效性判据、
   A-4 日志真实性判据，三条一起加进 `verify_generation.py` / `validateArgs`，
   并补负样本回归（「只给 expect_pins 不给 ioc 必须不能 pass」「空日志必须不能 pass」
   「project_root 指到空目录必须不能 pass」「传 MCP 返回文本必须不能 pass」）。
   这三条都不改判据语义，只补前置校验，风险最低。
2. **修操作面**：A-1 + A-5 + A-10 + A-12 合批处理，一次把 SKILL.md 的
   「本包 3 个工具 / 通道判据 / Phase 2 现状 / L2 命令 / 回滚口径 / D 编号 / 触发词」写对，
   README.md 与 docs/README.md 同步。**投入最小、收益最大**的一批。
3. **讲清证据口径**：A-7 在 SKILL 第 5 步写清「走 MCP 时证据是 `structuredContent`，不产生 `verify.json`」，
   顺手修 A-9 的死路径提示与 A-8 的 4 处契约缺口（其中「未知参数拒绝」只需 3 行）。
4. **补随包可达性**：A-3 选最小方案（两份指南进 `files` + 顶部注明 `docs/` 仅仓库可见）；
   A-2 注解、A-16 fail-open、A-15 阻塞调用一并处理。
5. **机制化**：A-6 的 CI 状态词扫描（防操作面再次漂移）+ A-13 的索引完整性检查。
6. P2（B-1…B-8）按顺手程度并入同一补丁版，不必单独开发。

> **不建议**为修这些单独发一个紧急版：0.7.2 的运行正确性没有受影响，
> 但 1–4 批都落在随包文件里，**合并成一次补丁版**才不会让用户连着升级三次。

**本次审定未修改任何实现文件**；F4 标注（`76e28dc`）与本报告是两笔独立产物。

---

## 9. 附录：核对数据

```text
HEAD              76e28dc（9fac316..76e28dc 已推 origin/master）
CI                41801100803 success
pytest            94 passed in 93.73s
check_taskboard   rc=0（36 条 / 28 完成 / 0 进行中 / 6 挂起 / 1 待开始 / 1 已关闭）
check_release     rc=0（0.7.2 四处同值、tag v0.7.2、发布正文在位；HEAD 领先 8 提交属正常）
文档相对链接      7 份受检文件 / 0 断链
tools/list        3（verify_generation / ioc_backup / ioc_field）
SKILL.md          416 行 / 19 274 字符 / 31 719 字节
references/       6 份 / 35 121 字符
docs/             49 份 md / 407 599 字符（不随 npm 包分发）
```

### 9.1 本轮做过的只读实测（L2，均不写仓库文件）

| 目的 | 做法 | 结果 |
|---|---|---|
| 复核 `tools/list` 与打包白名单 | 静态比对 `TOOL_DEFS` / 注册指南 / handshake 断言 / `package.json.files` | 3 个工具，四处一致；但 SKILL 引用的 9 个 `docs/*.md` 有 7 个不在包内 |
| 复核 SKILL 引用是否在仓内存在 | 脚本解析 `SKILL.md` 的仓内路径 | 20 条中 19 条存在，仅 `docs/logs/phaseN/` 是占位符 |
| 复核 `docs/README.md` 索引 | 脚本比对 `docs/**/*.md`（49 份）与索引提及 | 18 份未提及，14 份是可豁免的 logs 证据，4 份真漏项 |
| **复现 A-11** | `importlib` 载入 `verify_generation.py`，内存里调 `check_pins_present()` 四种入参 | `expect_pins` 有 / `ioc` 无 → `skip`；有 `ioc` 且不符 → `fail`；符合 → `pass` |
| **复现 A-14** | 内存里调 `verify_documents()`，`project_root` 分别取 `None` / 不存在 / 空目录 / 有空 `Core/Src` | 后两种 `verdict=pass`（`mx_script_abs_path=skip`），不存在的反而 `fail` |
| 复核分面 F-04（疑似误报） | `regen.sh` usage + 参数解析 + `verify_generation.py --help` | 参数全部存在，SKILL 的命令是裸调核验器 ⇒ 误报 |
| 报告自查 | 相对链接解析 + 相邻表格列数比对 | 0 断链 / 0 列数不一致 |

> 临时空目录建在系统 temp 后立即清理；所有 Python 片段都设了 `PYTHONDONTWRITEBYTECODE=1`，
> **未修改仓库内任何文件**（本报告与 `docs/README.md` 索引两处文档新增除外）。
