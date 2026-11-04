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
更关键的是第二层分叉：**G1 这道「硬关卡」有四种彼此独立的方式会交出 `verdict=PASS`**
（漏传 `ioc`、指错工程根、传任意文本当日志、日志里有 `KO` 而核验器不认），
而 `ioc_field` 一个换行就能写入能力边界之外的外设键；再往外一层，发版前的三道机器门禁
也都能在证据不全时保持绿灯。即：**问题不在代码跑不起来，而在 agent 会拿到没有依据的绿。**

| 级别 | 条数 | 含义 |
|---|---|---|
| **P0** | **10** | 会让 agent 拿到**全绿但结论不成立**的结果、让 MCP 能力链整体不可达、让 `.ioc` 内容被静默污染，或让发版门禁形同虚设 |
| **P1** | **17** | 显著影响 agent 判断、可靠性或证据完整性 |
| **P2** | **10** | 效率 / 可维护性 / 文档清晰度改进（多为合并列示） |

> 计数口径：初稿为 P0 4 / P1 12 / P2 8；四个分面回传后补齐假绿、注入、发布门禁三类，
> 并把 `A-5` 由 P1 升 P0、`A-20` 并入 `A-21`、架构分面第 4 项降 P2 并入 `B-4`，
> 按「一条缺陷只计一次」去重后为 **10 / 17 / 10 = 37 条**。分歧与裁定见 §5.5、§5.7、§2.8。

**十条 P0（按失效面分四组）**：

| 组 | 编号 | 一句话 |
|---|---|---|
| 操作面把 agent 引错路 | `A-1` | SKILL 的「MCP 通道」列外部 server 工具，与本包 3 个工具零交集 ⇒ 装了 MCP 却不会被调用 |
| 操作面把 agent 引错路 | `A-5` | SKILL/README/TASKBOARD 仍写「无硬件 / Phase 2 挂起」，与已达成的 L5 相反 ⇒ agent 拒绝执行已验证能力，且去「真源」复核会二次得到同一错误结论（**初稿 P1，定稿升 P0**） |
| G1 交出没有依据的 pass | `A-11` | `expect_pins` 有 / `ioc` 无 → 引脚级检查静默 `skip`，`verdict` 仍 `pass`（**主审 L2 只读实测**） |
| G1 交出没有依据的 pass | `A-14` | `--project-root` 指错目录 → 静默退回单文件扫描，`verdict` 仍 `pass`（**主审 L2 只读实测**） |
| G1 交出没有依据的 pass | `A-17` | 核验器不认 CubeMX 的 `KO` 行，也不认「日志是不是日志」：拿 `references/README.md` 当 `--log` 可得 `verdict=PASS errors=0`（**分面可复跑实跑**） |
| 证据与内容完整性 | `A-7` | MCP 通道根本不落 `verify.json`，而全流程把它当 L4 证据 ⇒ 证据链断 |
| 证据与内容完整性 | `A-21` | `ioc_field set` 的 `value` 含 `\r\n` 即可向 `.ioc` 注入任意键（含非 GPIO 外设），击穿能力边界且不触发路径白名单（**纯内存复现坐实**） |
| 发版门禁不设防 | `A-22` | `check_release.py` 只比本地版本轴，不查 npm / Release / 台账；`--network` 只 WARN 且 `npm view` 未带官方 registry |
| 发版门禁不设防 | `A-23` | `publish.yml` 的 `workflow_dispatch` 可在无 tag / 无 Release / 看板未收口的提交上发版 |
| 发版门禁不设防 | `A-24` | `npm_mcp_handshake.mjs` 在 CI 恒 SKIP 的 T6 上仍输出 `[HANDSHAKE SMOKE] PASS`、rc=0 |

**最该先处理的四批**：① 堵假绿（A-11 / A-14 / A-17 + A-4）：三条一起加进
`validate_evidence_inputs()` 并补四个负样本；② 修操作面（A-1 + A-5 + A-10 + A-12），
一次把「本包工具面 / 通道判据 / Phase 2 现状 / L2 命令 / 回滚口径」写对，投入最小、收益最大；
③ 堵注入与讲清证据口径（A-21 双层拒绝换行 + A-7 写明 MCP 走 `structuredContent`）；
④ 补发版门禁（A-22 / A-23 / A-24），让 D35 / GATE-3.1 不再完全靠人。

**发版判断**：本轮审定**不改实现**。所列问题均不影响 `0.7.2` 已发布产物的运行正确性
（A-22/23/24 是对**下一次**发版的门禁缺口，不是对已发版的追责），
但 ①②③ 落在随包分发的 `SKILL.md` / `lib` / `scripts` 里，修完需要新补丁版才能到达 npm 用户；
建议与下一批文档修订合并成**一次**补丁版，不必单独为审定报告发版。

---

## 1. 范围、方法与边界

| 项 | 内容 |
|---|---|
| 代码面 | `lib/server.mjs`（726 行）、`bin/cubeone-mcp.mjs`（5 行）、`package.json`、`scripts/` 4 个脚本（`verify_generation.py` 1713 行 / `regen.sh` 556 行 / `ioc_backup.py` 486 行 / `ioc_field.py` 317 行） |
| Agent 面 | `SKILL.md`（416 行 / 19 274 字符 / 31 719 UTF-8 字节）、`references/` 6 份（35 121 字符）、`README.md` |
| 工程面 | `tests/`（8 个文件，pytest 94 / Node 37）、`.github/workflows/{ci,publish}.yml`、`tools/` 5 个、`docs/` 49 份 md（约 40.8 万字符） |
| 状态面 | `docs/TASKBOARD.md`（36 条任务 / 28 完成）、`docs/DECISIONS.md` D1–D36、`docs/releases/` 台账 |
| 实测（只读） | `python tools/check_taskboard.py` rc=0、`check_release.py` rc=0、`pytest -q` **94 passed**、文档相对链接 0 断链、CI success |

> **分面回传说明（定稿更正）**：四个只读分面的结论**均已并入**。
> MCP 架构 / agent 效率 / 功能性三分面先回传；测试·CI·发布分面在初稿之后补回，
> 主审据其结论**撤回了初稿「发布链扎实、不要动」的判断**（§5.6），
> 并新增 §5.7 的三条发布门禁 P0、A-25–A-28 与 B-10。
> 凡定 P0 的都由主审做了可复现核实或逐条核对分面实跑证据；
> 两条被驳回 / 降级，理由见 §4.6、§5.5。
> 分面之间的定级分歧与去重过程见 §2.8、§4.2、§4.8、§5.2、§5.5、§5.7
> ——**审定不是把四分面输出相加**，这一点本身就是报告结论的一部分。
>
> **引用约定**：`§x.y` 带本报告上下文时指**本报告**章节（如「见 §4.8」）；
> 带文件名上下文时指**被审文档**章节（如 `SKILL.md:394` §6、`SKILL.md:83` §0.3、
> `phase2-bringup-2026-11-04.md:175`），不带文件名的 `§0.3` / `§6.1` 一律按就近的文件名理解。
> 所有行号以**审定基线 `76e28dc`** 为准；定稿只改本报告，不改被审文件，故行号不漂移。

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

`lib/server.mjs` 是薄封装层，靠一批「手写约定」与脚本对齐；以下 3 处约定没有对齐，
且都会把 agent 引向错误的排障方向（第 4 处经分面口径对齐后降为 P2）：

| # | 位置 | 现象 | 后果 / 建议 |
|---|---|---|---|
| 1 | `lib/server.mjs:587–596`（对照同文件 `:20–22` 的注释） | 任何 `res.error` 都被写成「**无法启动 Python** … 处置：改 `CUBEONE_PYTHON`」，且**丢弃** stdout/stderr/诊断。但 `ETIMEDOUT`（`:312` 的 120 s 超时）与 `ENOENT` 是两类完全不同的失败 | 大日志核验或冷启动超时会被指引去改 Python 路径。注释里已明确「两类失败措辞有意不同、不要合并」，代码却合并了 ⇒ **自相矛盾**。建议按 `res.error.code` 分支 |
| 2 | 三个 schema 都写了 `additionalProperties:false`（`:202–280`），但 `validateArgs()`（`:421–474`）只遍历 `props` | MCP SDK **不做** JSON Schema 校验；拼错参数名（如 `projectRoot` 代替 `project_root`）被静默忽略 | **与 §4.2 / A-11 同根，按一条计、不重复计数**：agent 以为传了保证，实际 `skip` + `verdict=pass`。建议在 `validateArgs` 加一行未知键拒绝（成本 3 行） |
| 3 | `lib/server.mjs:319–327` `readJson()` 用裸 `catch { return null }` 吞掉一切读取/解析错误 | 结构化结论落盘失败时 `structured=null`，仍可能走成功分支：核验器 `verdict=fail` 会被改判成「执行层失败」文案；`pass` 则悄悄少了 `structuredContent` | 把解析失败作为独立诊断字段返回，至少写进 stderr / `summary.notes` |
| ~~4~~ | `lib/server.mjs:239` 写「backup=默认」、`:253` `required` 含 `action`、`:554–557` 才有 fallback | 客户端按 description 省掉 `action` → 入口校验**响亮拒绝**（`isError`），fallback 永远到不了 | **架构分面主动降为 P2**：是文档-门禁口径不一致，**无数据损失、无假绿**；并入 B-4。三方口径取一即可 |

> **分面口径对齐记录（2026-11-04，定稿前）**：架构分面随后发来修订，
> ① 撤回最初「本分面无 P0」的结论，确认 `value` 换行注入为 P0（与功能性分面 P0-3 是**同一条**，
> 按一条计，见 §4.10 / A-21）；② 把上表第 4 项降为 P2；③ 明确第 2 项与假绿清单同源、归并计数。
> 主审采纳这三点，总表按「一条缺陷只计一次」重算 —— 详见 §6。
>
> **「存疑 → 复现 → 定级」的过程留痕**：架构分面最初提出换行注入时主审标为「待实测、不入计数」，
> 功能性分面随后用纯内存复现坐实，才升级为 P0。审定时不把猜测当结论。

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

> **主审裁定（分面口径分歧）**：功能性分面核对契约后认为
> 「`--expect-pins` 没配 `--ioc` 就 skip」是**已登记的设计取舍**（`references/verify-contract.md` 与
> `inputSchema` 都写了），建议并进假绿清单而不单列新 P0；效率分面则明确反对把已登记的 skip 设计
> 过滤掉。主审**保留 A-11 为 P0**，理由是：契约登记的只是「skip 语义」，
> 而这里的问题是「**调用方已经明确要求引脚级保证，工具层却既不拒绝也不警告，仍交出 `verdict=pass`**」——
> 前者是判据设计，后者是工具契约，两者不是一回事。修复也不改判据语义，
> 只需在 `validateArgs` 加一条联动规则（与 A-8 子项 2 的未知键拒绝合并实现，按一条计）。

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

### 4.6 复核、降级与一条环境事实（防止把线索当结论）

| 待核判断 | 主审核实 | 裁定 |
|---|---|---|
| 审稿中出现过「SKILL 的 CLI 命令跑不通，`regen.sh` 没有 `--main-c` / `--mxproject` / `--log`」 | `scripts/regen.sh:75/78/79` 的 usage 与 `:137–141` 的解析明确支持 `-l,--log` / `--main-c` / `--mxproject`；`SKILL.md:88–92` 那条命令是**裸调 `verify_generation.py`**，`--help` 显示 8 个参数全部受支持 | **不成立，不计入发现**；只留「两套入口参数面不同、SKILL 没讲清何时用哪个」作 P2 文档清晰度 |
| 分面 P2-7「`regen.sh` 硬编码 Windows 路径，Linux 开箱不可用」 | 默认值可用 `ST_CUBEMX_JRE` / `ST_CUBEMX_EXE` 覆盖（`regen.sh:80–81`），`SKILL.md:124` §1.1 与 D1 已明确登记「本机锁 6.18.1、路径见 §0.2」，是有意的本机工具约束 | **已登记，不计为新发现**；降为 P2「未来可自动探测安装路径」 |
| 分面主动澄清「POSIX↔Windows 路径在 `regen.sh` → 核验器链上可能出错」 | 分面用 `config load` 相对/绝对 × `project path` 相对/绝对 × `--project-root` 相对/绝对 实跑 6 种组合，**G1 全部 `0/0/0`、无假红**；CubeMX 与 Python 各自处理边界 | **不是 bug，不计入发现** —— 这条澄清避免了一个很常见的误报方向 |

> **审定不是把分面输出相加**：分面给的是线索，主审对每条 P0 都做可复现核实；
> 不成立的要驳回、已登记的要降级，否则报告本身会成为新的失真源。
> 相应地，§4.1 / §4.8 的两条 P0 都有**可复跑的命令与完整输出**，不是静态推断。

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

### 4.8 【P0 / A-17】核验器不认 CubeMX 的 `KO` 行，且对「日志是不是日志」零识别（有实跑证据）

这是本轮**证据最硬**的一条。功能性分面做了两次可复跑实验，主审复核了对应代码路径：

**实验一：拿一份完全无关的 Markdown 当生成日志**

```bash
python scripts/verify_generation.py \
  --log references/README.md \
  --main-c testbeds/_verifier-regen/g474/Core/Src/main.c \
  --mxproject testbeds/_verifier-regen/g474/.mxproject \
  --expect GPIO --project-root testbeds/_verifier-regen/g474 \
  --ioc testbeds/_verifier-regen/g474/stm32-g474-template.ioc \
  --expect-pins PC13=GPIO_Output
# → verdict=PASS  errors=0  warnings=0  rc=0
#   log_cannot_map / main_init_present / main_init_called / pins_present /
#   mxproject_abs_path / mx_script_abs_path / syscalls_path 全 pass
```

**实验二：拿一份含 2 个 `KO`、0 个 `Cannot map` 的真实生成日志**

```text
docs/logs/phase0/t1.8-s3/…/s3-probe2-raw.log  →  verdict=PASS  errors=0  warnings=0
```

**代码根因（两个独立缺口）**：

1. `scripts/verify_generation.py` **全文没有 `KO` 正则**；唯一的 `KO` 判据在
   `scripts/regen.sh:403–408` 的生成后检查里。也就是说 `regen.sh` 包住的时候能挡，
   **直调核验器 / CLI 等价通道 / MCP 的 `verify_generation` 工具全都不设防**。
   SKILL.md §3A 把「逐行 `OK` 不是 `KO`」列为三级确认的第 1 条，
   但这条确认在核验器里**没有任何落点**。
2. `:1671–1674` 读 `--log` / `--main-c` / `--mxproject` 时不做任何形态校验；
   `check_log_cannot_map()`（`:584–618`）只扫 `Cannot map` 与判空，
   一份 8 KB 的 Markdown 会被当成「无命中 ⇒ pass」，`:604–609` 的「日志为空」warn 都触发不了。

**为什么必须 P0**：G1 是本项目宣称的「硬关卡」「非 GPIO 路径上唯一的安全网」
（`SKILL.md:32`）。现在这层网对「日志内容完全不相干」和「CubeMX 明确回 `KO`」
两种情形都返回全绿，而 agent 拿到的 `verdict=pass` 会被当成可执行构建的授权。
配合 §4.2（`expect_pins`/`ioc`）、§4.5（`project_root`）两条，
**四种不同方式都能让 G1 交出没有依据的 pass** —— 这是系统性问题，不是单点 bug。

**建议**（按代价排序）：① `verify_generation.py` 增加 `log_ko_lines` 判据，
或至少把 `KO` 命中直接计 `errors`；② 增加「日志形态」前置判据
（CubeMX 特征行 / 最小行数 / 是否含 `config load`/`project generate` 回显），
不满足判 fail 而非 warn；③ 把这两条与 §4.2、§4.5 的前置校验合并成
一个 `validate_evidence_inputs()`，四个负样本一起进回归。

> **编号澄清（功能性分面定稿前特别提示，主审采纳）**：有分面把「`json_out` 不落盘」
> 与本节误当成同一条 P0 来合并。**两者同根（都缺「本次生成的可追溯物证」），
> 但表现与优先级主体不同，本报告按两条 P0 分别保留**：
> - **A-17（本节）＝ 判据可靠性面的头号假绿**：核验器读任意文本 / 含 `KO` 的日志都判
>   `verdict=PASS`，是**结论本身错**，修复点是核验器判据，P0 主体；
> - **A-7（§2.7）＝ 证据持久化缺口**：MCP 把结构化结论读回即删，不落 `verify.json`，
>   是**证据留不住**，修复点是 MCP 返回 / 落盘策略，为同根的从属表现。
>
> 若按「证据持久化」一条成文，A-17 会被写成配置 / 效率问题而降级 —— 这是本次汇总要避免的失真。
> 两条都保持 **P0**，但修的时候可以在同一个 `validate_evidence_inputs()` 批次里一起做。

### 4.9 【P1 / A-18~A-20 + P2】`regen.sh` 编排链的功能性发现

| 编号 | 级别 | 事实（分面实跑 / 主审核实） | 建议 |
|---|---|---|---|
| **A-18** | P1 | `--expect`/`-e` 等**带值选项漏给参数**时，`regen.sh:137–199` 的 `shift 2` 在 `$2` 不存在时不改变参数个数 ⇒ **无限循环**。分面用 `timeout 5` 复现：OOM/超时而非「参数错误」。`:132` 的 `while [ $# -gt 0 ]` 没有迭代上限；`:203–209` 的路径检查又在循环之后，救不了它 | 每个 `shift 2` 前判 `${2:-}` 为空就 `die 2`；或给 while 加迭代上限。补一条「缺参必须 2 秒内退 2」的用例 |
| **A-19** | P1 | `regen.sh:556` 用 `exit "$VERIFY_RC"` 透传核验器退出码，但 `VERIFY_RC=9009`（WindowsApps Python 桩）、`127`、被信号杀死等都会原样透传；`references/regen-exit-codes.md` 约定的 `{0,1,2}` 契约在 shell 层被破坏 | 显式映射：只把 `0/1` 透传，其余统一归一成 `2` 并打印原始码 |
| ~~A-20~~ → 并入 **A-21** | P0 | **能力边界在工具层完全没有落点**（与 §4.10 的换行注入同根，按一条 P0 计）：`SKILL.md:3`、`:29–31`、`references/capability-boundary.md:54` 都宣称「非 GPIO 外设增改没有工具能力」，但 `lib/server.mjs` 的 `CAPABILITY_NOTE` 只是 description 文字，`validateArgs` 不检查键名，`scripts/ioc_field.py:147+` 的 `set_value()` 对任意键通用。分面实测 `set key PA9.Signal value USART1_TX` → `changed=true`、`rc=0`，工具既不拒绝也不警告 | 不要求「权限层拦截」（能力层 ≠ 权限层，见 `capability-boundary.md:8–10`），但至少应：① `ioc_field set` 命中 `*.Signal=非 GPIO` / `Mcu.IP*` 时返回显式文案「该改动超出工具能力，须手改 .ioc/GUI 并强制过 G1」；② 在 `structuredContent` 加 `capability_warning` 字段，让 agent 可机读，而不是只靠读 SKILL |
| B-9 | P2 | 脚本链杂项（分面逐条静态核实）：`*.ioc.bak.sha256` **未进 `.gitignore`**（实测 `NOT-IGNORED`），与 `ioc_backup.py:27–28`「不污染 git status」的注释矛盾；`--dry-run` 仍执行 `mkdir -p`（`:216–218`、`:240–245`）⇒ 纯预演会建目录；超时分支在 `rollback` **之前**就打印「本次已从备份回滚」（`:451` vs `:515`），失败时序上是不实陈述；三脚本对 BOM/CRLF 的口径不一致 + 无文件锁（两个 MCP 会话同时 `set` 同一 `.ioc` 会 lost-update，属**未登记的真实竞态**）；`resolve_init_symbol` 在多定义时 FAIL 造成假红（分面静态复现） | 逐条小修；竞态建议至少在文档登记，或用 `O_EXCL` 锁文件 |

> §4.9 的 BOM/并发竞态**是已登记 TOCTOU 之外的另一类并发问题**：TOCTOU 说的是路径校验与打开之间，
> 这里说的是「读-改-写整个 `.ioc`」没有互斥，两者不要混为一谈。

---

### 4.10 【P0 / A-21】`ioc_field set` 的 `value` 含换行即可向 `.ioc` 注入任意键（纯内存复现已坐实）

两个分面独立提出、并由功能性分面完成复现；主审据此把先前「存疑」升级为 P0：

- `lib/server.mjs:563–565` 用 `--` 把 `action/key/value` 作为位置参数传给 Python；
  `spawnSync` 的 argv **允许字符串里含 `\r` / `\n`**，入口 `validateArgs()`（`:421–474`）只查类型 / enum / 必填，
  **不查内容**。
- `scripts/ioc_field.py:147+` 的 `set_value()` 按行读写 `.ioc`，`value` 未做换行拒绝。
  分面用纯内存构造 `value = "GPIO_Output\r\nMcu.IP5=USART1\r\nPA9.Signal=USART1_TX"` 复现：
  工具回 `changed=true` / `rc=0`，**一次 `set` 把三行写进了 `.ioc`**。

**为什么是 P0 而不只是「能力边界没护栏」**：

1. 它同时击穿了两条红线 —— `SKILL.md:3/29–31` 宣称「非 GPIO 外设增改没有工具能力」，
   而这里只要一个换行就能写入 `Mcu.IP5=USART1`；
   `SKILL.md:79–80` 与 D9 的「只在 testbeds 副本里写」由路径白名单守着，
   但**注入的是内容而不是路径**，白名单看不见。
2. 它让 §4.9 A-20 从「能改一个键」升级为「能**新增任意键**」，
   且 `ioc_backup` 的 SHA-256 sidecar 只能证明「还原到了这份被改过的文件」，
   **证明不了没被注入**（备份发生在写之前，内容本身已被污染）。
3. G1 对「参数级 / 漏 `IPParameters`」失明（已登记限制），
   所以注入后的 `.ioc` 很可能生成出**日志干净、构建通过、但外设不存在**的固件 ——
   正是本项目最反对的假绿形态。

**建议**：`validateArgs()` 与 `set_value()` 双层拒绝 `key` / `value` 中的 `\r` / `\n`
（或显式转义并写进 `structuredContent`），返回 `isError` 而不是静默写入；
补负样本回归（含 CRLF / LF / 尾部空格变体）。与 A-20 是**同一处修复**，按一条 P0 计。

> **按一条计**：架构分面已确认这与功能性分面 P0-3 是同一条，
> 总表只记 A-21，不重复计数。

---

## 5. 测试 / CI / 发布 / 文档一致性

### 5.1 两道机器校验都没有覆盖「操作面状态」

`tools/check_taskboard.py` 校验快照 / 证据路径 / tag，`tools/check_release.py` 校验四处版本轴 + 发布正文。
两者都不读 `SKILL.md` / `README.md` 里的**状态陈述**。结果就是下面这张表：

### 5.2 【P0 / A-5】过期 / 自相矛盾陈述清单（L5 已达成，操作面仍写「无硬件」）

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

> **定级更正（主审采纳效率分面补充，A-5 由 P1 升 P0）**：初稿把它当「文档漂移」，
> 分面补出的三条证据说明它其实会让 agent **得出并执行错误结论**：
> ① `SKILL.md` **内部自相矛盾** —— `:83`（§0.3 红线 2）已引用同一份 phase2 报告的 F4 现场
> （「烧录成功 + 寄存器正确 + 人眼无现象」），`:276` 也吸收了「2026-11-04 实测」的超时结论，
> 而 `:378` / `:394` 仍写「无硬件」「本节一律按**无能力**对待」；
> ② frontmatter `:3` 把「烧进去看看」「串口有输出吗」列为**触发词**，命中后 agent 按 §6
> 会直接回复「无硬件不支持」，不会去用 `phase2-bringup-2026-11-04.md:193–209` 已有的复现命令
> ⇒ **走错路径概率接近 1**；
> ③ `:327` 说 L5「一律缺」而 §4 提交模板 `:349` 又要求声明 `L<n>` ⇒ agent 无法为已达 L5 的场景
> 正确声明等级，只能降级报 L3/L4 或反过来报错；
> ④ **代价补强（效率分面 + 测试/CI/发布分面共同补出，不新增条目）**：
> `SKILL.md:413`（§7）把 agent 明确导向 `docs/TASKBOARD.md`「唯一状态真源」，
> 而 TASKBOARD.md 的 Phase 2 六项 / GATE 关卡**同样写「挂起 / 无硬件」**（见 A-28）。
> agent 在 §6 读到「按无能力对待」后去真源复核，会**第二次得到同样的错误结论**
> ⇒ 错误路径被钉死、几乎无法自纠。这也正好坐实「`check_taskboard.py` 只校验表↔快照内部一致、
> 抓不到与事实不符」的危害：**真源自洽但仍然错**。
>
> 与 A-1 的区别：A-1 让 agent **绕开 MCP 工具**，A-5 让 agent **放弃整个 Phase 2 能力**，
> 两条都是「能力宣称与实际可达性脱节」，但路径独立，按两条 P0 计。
>
> **修法必须分段更新，不能整体翻转**（分面建议，主审认同）：
> 已达 L5 的（烧录 / 寄存器回读 / 目视 / LED 现象）→ §6.1 改「已实测（2026-11-04）」、
> §3 L5 行去掉「一律缺」、§6 标题去掉「挂起」；
> **仍未覆盖的要如实保留** —— 串口段（phase2 报告 `:175` 明确「本工程未启用任何 USART」）、
> `pio device monitor` 未实测 ⇒ `:96` 只保留 monitor 的「未实测」、`:134` 拆成
> 「烧录已实测 / 串口未实测」；`:78` 的 GATE-2.1 安全确认**保留**，只去掉「无硬件」前提；
> §7 参考清单补上 `docs/reports/phase2-bringup-2026-11-04.md`（它是 L5 真源，却唯一没被 §7 列出）。

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
| `releases/2026-11-04-v0.7.2.md` | 当前版本的发布正文；`docs/README.md:57` 反而把 `v0.7.1` 标成「当前版本」｜**仍未补** |
| `reports/phase2-bringup-2026-11-04.md` | **唯一的 L5 证据报告**，接板首日的全部结论都在这里｜✅ 本轮已补入索引 |
| `reports/t0-redaction-audit.md` | 脱敏审计结论（安全相关）｜**仍未补** |
| `reports/audit-2026-11-04-agent-engineer.md` | 本报告｜✅ 本轮已补入索引 |

> 效率分面复核后特别提示：按**当前 HEAD** 计，真漏项已从 4 个降到 **2 个**
> （`v0.7.2` 发布正文、`t0-redaction-audit.md`）；本报告不把已补入的两项继续算作缺口。

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

**裁定**：保留为发现，并在 §5.2 逐条列出 11 处位置。
**级别以定稿为准**：初稿定 **P1**，效率分面与测试/CI/发布分面补出「错误路径被真源二次确认、
触发词直接命中、L5 无法声明」三条代价后，主审**升为 P0**（完整依据见 §5.2 的定级更正框）。
本节的「排除 vs 保留」之争与级别之争是两件事，不要据此把 A-5 读回 P1。

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

**发布链复核结论（经测试/CI/发布分面补充后修正）**：**工程细节扎实，但门禁层有三条 P0 缺口**，
因此初稿「这一段是扎实的，不要动」的判断**已被主审撤回**，三条缺口见 §5.7。
下面这些确实做得好、修门禁时不要顺手拆掉：
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

### 5.7 【P0×3 / P1×4 / P2】发布与门禁链（测试/CI/发布分面，主审复核）

| 编号 | 级别 | 事实 | 后果 / 建议 |
|---|---|---|---|
| **A-22** | **P0** | `tools/check_release.py` 自称「版本轴 + 发布正文 + 未发版提醒」的**机器校验**，三条判据实际只查：本地四处版本同值、tag 存在、发布正文文件存在、HEAD 领先提醒；**不查** npm registry 上该版本是否真在、GitHub Release 是否存在、`docs/releases/README.md` 台账是否回填、工作区是否干净、CI 是否绿。`--network` 的 `npm_dist_tags()`（`:233–263`）只打 WARN、rc 仍 0，且 `npm view` 未带官方 `--registry` | 本机 `npm view` 默认读 npmmirror（只同步到 0.7.1/0.7.0），绿灯可能建立在错误数据源上；`docs/releases/README.md` 把 `check_release` 绿当「三证齐全」证据之一 ⇒ **「轴一致」被当成「发布收口」**。建议：改名或补齐判据；发版 SOP（D35）明确「哪些机器查、哪些人核」；`npm view` 显式官方源；台账回填加机械校验 |
| **A-23** | **P0** | `.github/workflows/publish.yml` 的 `on:` 同时含 `workflow_dispatch` 与 `release: published`，但 `publish` job **不校验 tag == package.json、不校验 Release 存在、不跑 `check_release.py` / `check_taskboard.py`**；只跑 `pytest tests/ -q` | 手动 dispatch 可在任意 master 提交上发版 ⇒ 无 tag / 无 Release / 看板未收口也能把包推出去。D35 / GATE-3.1 的「发版前证据包 + 用户明确放行」目前**完全靠人**，机器不设防。建议：job 开头加 `check_release.py --network`（判红）+ `check_taskboard.py` + `github.ref`/tag 一致性；dispatch 要求输入 tag 或收窄为仅 release 事件 |
| **A-24** | **P0** | `tools/npm_mcp_handshake.mjs` 在 CI 的 ubuntu node 22 档只带 `--ci`、**没带 `--require-materials`**，缺素材时 T6（`verify_generation` 真调用）恒 SKIP | **措辞精确化（分面更正，主审采纳）**：不是「完全静默」—— `skipCheck()` 会打 `⏭ SKIPPED: …`，但 **headline 与退出码只看 `fail`**，于是 `pass=11 skip=1` 仍输出 `[HANDSHAKE SMOKE] PASS` ⇒ 绿灯被读成「MCP 工具通道全测过」。建议：headline 改成 `PASS (with N SKIP)` 并把 skip 写进 Job Summary，或给 CI 提供真素材让 T6 真跑 |

**P1 四条**：

| 编号 | 事实 |
|---|---|
| A-25 | **R1 三项裁决新增分支零覆盖**：`log_tail_stalled_at_loadconfig()` / `report_migrate_stall()` / `--fail-fast-on-migrate` 与超时回滚路径在 `tests/` 里没有对应用例；`tests/test_regen_preflight.py` 只测三档前置提示。详见下方「R1 具体缺陷」 |
| A-26 | **测试数字四套口径**：`74 / 77 / 72 / 94`（Python）、`37`（Node）、`12`（冒烟）、`pass=11 skip=1`（CI）散落在看板 / README / 发布正文，多数是不同时间点快照却没标基准，读者无法判断哪个是当前值 |
| A-27 | `check_taskboard.py` 判据③只做**全局代理**（「存在任意 v0.6/v0.7 tag ⇒ T3.5 不得待开始」），不校验当前版本 tag；`TAG_RE = ^v0\.[67]\.\d+` 把版本前缀钉死，发到 `v0.8.0` 后该判据**自动失效且不会报警** |
| A-28 | **状态真源内部与事实不符、且散文与表格自相矛盾**：`docs/TASKBOARD.md:46–48` 仍写「**当前会话无硬件**（GATE-D 已确认，Phase 2 整体后移）」、Phase 2 六项（T2.1–T2.6）与 `:172–174` 的 GATE-2.0/2.1/2.2 **全为「挂起」**，而 `:158` 的 R2 行已是「已完成 / **L5**」；`:204` 快照里 Phase 2 仍是 `0 完成 / 6 挂起`；散文写「批次表 10 条、合计 **35**」而 `:207` 表格与 `:208` 合计行是 **11 / 36**。`check_taskboard.py` 只校验表↔快照内部自洽，所以 `rc=0` 抓不到「账算对了、事实错了」。⚠️ 本轮**未擅自改状态真源**（会连锁改快照），留作独立批次 |

> **R1 零覆盖的三个具体缺陷（功能性分面补充，主审采纳；按 A-25 一条计，不重复计数）**：
> ① `regen.sh:232–246` 的超时归因是「尾部 10 行宽匹配」，成功日志尾部若含 `Begin LoadConfig`
> 且窗口内无 `Change cursor` 就会**误归因**；② `:451` 的「本次已从备份回滚」打印在
> `:515` 的 `rollback_project` **之前**，是时序上的不实陈述；③ 提示匹配按「行首 + 精确字符串」，
> 值变体（大小写 / 尾随空格）会漏。
> **补测不能只加 happy-path**，必须含负样本与值变体。好消息是素材现成：
> `docs/logs/phase4/02-first-generate.log`、`04-first-generate-retry.log` 已入库，
> `phase2-bringup-2026-11-04.md` 还记了一次「真超时但尾部未命中 ⇒ 不能归因」的现场
> ⇒ 可直接做自动回归，不必造假素材（这也符合本仓 T6 有意保留 SKIP 的取舍）。

**P2 合集（B-10）**：散文数字与表格口径不一（A-28 已列）、D 编号重号、
「三证 / 四证」口径不统一、若干测试为「只查字符串包含」的弱断言、
跨平台差异未在测试里覆盖、`.coverage` 陈旧产物、
owner 声明与实际改动角色冲突（`SKILL.md:416`）、历史 CI job 数（2 vs 7）未标时间点。

**分面特别提示（主审照录，避免误报）**：
`docs/guides/gate-2.0-checklist.md:174` 的 F4「首烧目标勘误」**已在当前 HEAD 完成**，
审定不得把它报成「未做」；`docs/releases/2026-11-04-v0.7.2.md` 里三条 CLI 命令
与脚本 argparse **逐一对得上**，这是发布正文里少见地经得起复核的一处。

---

## 6. 发现总表

> 「需发版」= 修改落在随 npm 包分发的文件（SKILL.md / lib / scripts / package.json）里，
> 修完要新补丁版才能到达用户；纯 CI / 仓库文档改动不需要。

**合计 37 条：P0 10 / P1 17 / P2 10**。一条缺陷只计一次；
分面重复提出的合并到同一编号，定级变化以定稿为准，过程留在 §2.8 / §5.2 / §5.5 / §5.7。

**P0（10 条）**

| 编号 | 级别 | 标题 | 章节 / 关键证据 | 需发版 |
|---|---|---|---|---|
| **A-1** | **P0** | SKILL 的「MCP 通道」列外部 server 工具，与本包 3 个工具零交集 ⇒ MCP 能力不可达 | §2.2 `SKILL.md:43`, `:127–134` vs `lib/server.mjs:190–281` | 是 |
| **A-5** | **P0** | SKILL/README/TASKBOARD 仍写「无硬件 / Phase 2 挂起」，与已达成的 L5 相反；真源复核会二次确认错误路径 | §5.2 逐条 11 处；§5.5 主审裁定；**初稿 P1 → 定稿 P0** | 是 |
| **A-7** | **P0** | MCP 通道不落 `verify.json`，而全流程把它当 L4 证据 | §2.7 `lib/server.mjs:297–329` vs `SKILL.md:351` | 是 |
| **A-11** | **P0** | `expect_pins` 有 / `ioc` 无 → 静默 `skip`，`verdict` 仍 `pass`（主审 L2 只读实测） | §4.2 `verify_generation.py:920–928`, `:1429`；`lib/server.mjs:421–474` | 是 |
| **A-14** | **P0** | `--project-root` 指错目录 → 静默退回单文件扫描，`verdict` 仍 `pass`（主审 L2 只读实测） | §4.5 `verify_generation.py:406–446` | 是 |
| **A-17** | **P0** | 核验器不认 `KO` 行、也不认日志形态：`references/README.md` 当 `--log` ⇒ `verdict=PASS errors=0`（分面可复跑实跑） | §4.8 `verify_generation.py:584–618`, `:1671–1674` vs `regen.sh:403–408` | 是 |
| **A-21** | **P0** | `ioc_field set` 的 `value` 含 `\r\n` 可注入任意 `.ioc` 键；**含 A-20「能力边界无护栏」**（纯内存复现坐实） | §4.10 `lib/server.mjs:563–565`, `scripts/ioc_field.py:147+`；§4.9 | 是 |
| **A-22** | **P0** | `check_release.py` 只比本地版本轴，不查 npm / Release / 台账；`--network` 只 WARN 且未带官方 registry | §5.7 `tools/check_release.py:233–263` | 否 |
| **A-23** | **P0** | `publish.yml` 的 `workflow_dispatch` 可在无 tag / 无 Release / 看板未收口时发版 | §5.7 `.github/workflows/publish.yml` | 否 |
| **A-24** | **P0** | T6 恒 SKIP 时 `npm_mcp_handshake.mjs` 仍输出 `[HANDSHAKE SMOKE] PASS`、rc=0 | §5.7 `tools/npm_mcp_handshake.mjs` + `ci.yml` node 22 档 | 否 |

**P1（17 条）**

| 编号 | 级别 | 标题 | 章节 / 关键证据 | 需发版 |
|---|---|---|---|---|
| A-2 | P1 | `readOnlyHint=true` 与实际写盘、三处文档口径矛盾 | §2.3 `lib/server.mjs:201`, `SKILL.md:142–145` | 是 |
| A-3 | P1 | 随包 SKILL 的 7 个 `docs/` 引用是死链（含接板清单、板卡对照） | §2.5 `package.json:25–36` | 是 |
| A-4 | P1 | 「`--log` 必须是真日志」只有文档护栏；空日志仅 warn，仍 `pass` | §4.1 `verify_generation.py:604–618`, `:1429` | 是 |
| A-6 | P1 | 状态真源与操作面之间无机器校验，漂移可再次发生 | §5.1 两道校验均不读 SKILL/README | 否（CI） |
| A-8 | P1 | MCP 层与脚本层契约未对齐（**3 子项**：ETIMEDOUT 误归因 / 未知参数静默 / `readJson` 吞错；第 4 项降 P2 并入 B-4） | §2.8 `lib/server.mjs:587–596`, `:421–474`, `:319–327` | 是 |
| A-9 | P1 | 返回文本含必然失效的临时路径；「verdict/checks」提示对 2/3 工具不成立 | §3.4 `verify_generation.py:1705`, `lib/server.mjs:613` | 是 |
| A-10 | P1 | SKILL 的 L2 命令引用本仓不存在的 `stdio_port.c` / `AGENTS.md` | §3.5 `SKILL.md:318`, `:329–336` | 是 |
| A-12 | P1 | SKILL 第 2 步与第 5 步回滚口径自相矛盾，`git checkout --` 会丢用户改动 | §4.3 `SKILL.md:230–231`, `:287` | 是 |
| A-13 | P1 | `docs/README.md` 索引真漏项 **2 个**（0.7.2 正文 / 脱敏审计；另 2 项本轮已补），且把 0.7.1 标「当前版本」 | §5.4 脚本比对 49 份 md | 否 |
| A-15 | P1 | `spawnSync` 同步阻塞 + 120 s，单 server 串行，超时又被误归因（与 A-8①叠加） | §2.4 `lib/server.mjs:310–317` | 是 |
| A-16 | P1 | `physical()` 全链解析失败时退回纯词法路径（fail-open） | §2.9 `lib/server.mjs:128–146` | 是 |
| A-18 | P1 | `regen.sh` 带值选项漏参时 `shift 2` 不改变参数个数 ⇒ 死循环（`timeout 5` 复现） | §4.9 `regen.sh:132–209` | 是 |
| A-19 | P1 | `exit "$VERIFY_RC"` 透传 `9009` / `127` / 信号码，破坏 `{0,1,2}` 契约 | §4.9 `regen.sh:556` vs `regen-exit-codes.md` | 是 |
| A-25 | P1 | R1 新增分支零测试覆盖（超时归因 / `--fail-fast-on-migrate` / 回滚 / 值变体） | §5.7 `tests/test_regen_preflight.py` | 部分 |
| A-26 | P1 | 测试数字四套口径（74/77/72/94、37、12、pass=11 skip=1）未标基准 | §5.7 看板 / README / 发布正文 | 部分 |
| A-27 | P1 | `check_taskboard.py` 判据③只做全局代理，`TAG_RE` 钉死 `^v0\.[67]` ⇒ 发到 0.8 自动失效 | §5.7 `tools/check_taskboard.py` | 否 |
| A-28 | P1 | TASKBOARD 自身与事实不符、散文 35 与表格 36 自相矛盾；`rc=0` 抓不到「账对、事实错」 | §5.7 `docs/TASKBOARD.md:46–48`, `:158`, `:204–208` | 否 |

**P2（10 条，含合并列示）**

| 编号 | 级别 | 标题 | 章节 / 关键证据 | 需发版 |
|---|---|---|---|---|
| B-1 | P2 | 触发词覆盖本包做不到的 4 类任务；返回噪声与 12 000 字符尾部截断 | §3.2/§3.3 `SKILL.md:3`, `lib/server.mjs:611–614` | 是 |
| B-2 | P2 | 无 `outputSchema`；`structuredContent` 无体积上限；长 stdout 会截掉首行 `verdict` | §3.3 `lib/server.mjs:190–281` | 是 |
| B-3 | P2 | 单写者名分、工具数量措辞、发布台账「当前版本」、D 编号四处小漂移 | §5.3 `SKILL.md:416`, `:413`, `README.md:271` | 否 |
| B-4 | P2 | `ListTools` 夹带内部字段；临时目录写盘未声明；bin 可执行位 / Promise 未 catch；SDK 95 包依赖；**含 §2.8 降级第 4 项**（`action` 默认三方口径） | §2.9 / §2.8 | 部分 |
| B-5 | P2 | 编码加固未覆盖 `tools/*`；`--log` 读入前无形态校验；`regen.sh` 参数组合缺负样本 | §4.7 | 否 |
| B-6 | P2 | 两套入口参数面不同，SKILL 未讲清何时用哪个（F-04 误报驳回后的有效部分） | §4.6 | 否 |
| B-7 | P2 | 硬编码 Windows CubeMX 路径（已有 env 覆盖、已登记），可升级为自动探测 | §4.6 | 部分 |
| B-8 | P2 | `regen.sh` 头部 sandbox 约定注释与代码不逐条对应 | §4.7 | 部分 |
| B-9 | P2 | `*.ioc.bak.sha256` 未忽略；`--dry-run` 仍 `mkdir -p`；回滚时序不实；BOM/CRLF 口径不一；双会话 lost-update 竞态；`resolve_init_symbol` 假红 | §4.9 | 部分 |
| B-10 | P2 | 散文/表格口径、D 编号重号、三证/四证、弱断言、跨平台未覆盖、`.coverage` 陈旧、owner 冲突、历史 job 数未标时间点 | §5.7 | 否 |

**未计入发现（去重 / 驳回 / 已登记）**：
`A-20`（能力边界无护栏，与 `A-21` 同根 ⇒ 并入 A-21）、
架构分面「换行注入猜想」（**已由分面纯内存复现坐实**，升级为 A-21，不再算存疑）、
功能性分面 F-04（主审核实为误报，§4.6）、F-07 硬编码路径（已登记，§4.6，仅留 B-7 改进项）、
「POSIX↔Windows 路径」6 种组合实跑全绿（不是 bug，§4.6）、
`gate-2.0-checklist.md` F4 勘误与 0.7.2 发布正文三条 CLI 命令（**已在当前 HEAD 完成 / 经复核正确**，§5.7）、
以及 §4.4 列出的 6 类已登记已知限制。

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

1. **先堵假绿（最优先，因为会产出错误结论）**：A-11 参数联动、A-14 工程根有效性、
   A-17 `KO` 行 / 日志形态、A-4 空日志，四条合并成一个 `validate_evidence_inputs()`
   加进 `verify_generation.py` 与 `validateArgs`；配四个负样本回归（漏传 `ioc` 不能 pass、
   工程根指到空目录不能 pass、传任意文本当日志不能 pass、日志含 `KO` 不能 pass）。
   不改判据语义、只补前置校验，风险最低、收益最高。
2. **堵内容注入**：A-21 在 `validateArgs()` 与 `set_value()` 双层拒绝 `key`/`value` 中的
   `\r`/`\n`，返回 `isError`；同时给非 GPIO 键加 `capability_warning`（把 A-20 的能力边界
   从「只有 SKILL 文字」变成 agent 可机读的字段）。补 CRLF / LF / 尾空格变体负样本。
3. **修操作面**：A-1 + A-5 + A-10 + A-12 合批处理，一次把 SKILL.md 的
   「本包 3 个工具 / 通道判据 / Phase 2 现状（分段更新，串口段如实保留未实测）/ L2 命令 /
   回滚口径 / D 编号 / 触发词」写对，README.md 与 docs/README.md 同步；
   A-5 还要同步 `docs/TASKBOARD.md` 的 Phase 2 与 GATE 状态（与 A-28 一起做，会连锁改快照，
   **必须单独一批并跑 `check_taskboard.py`**）。**投入最小、收益最大**的一批。
4. **讲清证据口径**：A-7 在 SKILL 第 5 步写清「走 MCP 时证据是 `structuredContent`，
   不产生 `verify.json`」，顺手修 A-9 死路径提示与 A-8 的三处契约缺口
   （其中「未知参数拒绝」只需 3 行，且与第 1 批共用 `validateArgs`）。
5. **补发版门禁**：A-22 给 `check_release.py --network` 加官方 registry + 台账 / Release 判红；
   A-23 在 `publish.yml` job 开头跑 `check_release.py` / `check_taskboard.py` 并校验 tag；
   A-24 把 SKIP 数写进 headline 与 Job Summary。**注意别把 `check_release.py` 挂进 CI**
   （§5.6 已说明那是有意取舍），门禁只加在发布流。
6. **补随包可达性与机制化**：A-3（两份指南进 `files` + 注明 `docs/` 仅仓库可见）、
   A-2 注解、A-16 fail-open、A-15 阻塞调用；A-6 的 CI 状态词扫描 + A-13 索引完整性检查；
   A-25 用 `docs/logs/phase4/` 现成素材补 R1 负样本回归（不必造假素材）。
7. P2（B-1…B-10）按顺手程度并入同一补丁版，不必单独开发。

> **不建议**为修这些单独发一个紧急版：0.7.2 的运行正确性没有受影响，
> 但 1–4、6 批里落在 `SKILL.md` / `lib` / `scripts` 的部分**合并成一次补丁版**
> 才不会让用户连着升级三次；第 5 批（CI / 发布流）与仓库文档随时可改，不必等版本。

**本次审定未修改任何实现文件**；F4 标注（`76e28dc`）与本报告是两笔独立产物。

---

## 9. 附录：核对数据

```text
审定基线 HEAD     76e28dc（9fac316..76e28dc 已推 origin/master，CI 41801100803 success）
报告落盘          三笔只改 docs/ 的提交（初稿 / 分面回传补注 / 定稿去重与统计统一）
CI                41801100803 success
pytest            94 passed in 93.73s
check_taskboard   rc=0（36 条 / 28 完成 / 0 进行中 / 6 挂起 / 1 待开始 / 1 已关闭）
check_release     rc=0（0.7.2 四处同值、tag v0.7.2、发布正文在位；HEAD 领先属正常）
F4 批次文档检查    7 份受检文件 / 0 断链
tools/list        3（verify_generation / ioc_backup / ioc_field）
SKILL.md          416 行 / 19 274 字符 / 31 719 字节
references/       6 份 / 35 121 字符
docs/             49 份 md / 407 599 字符（不随 npm 包分发）
最终发现计数      P0 10 / P1 17 / P2 10 = 37 条（一条缺陷只计一次）
报告定稿自查      917 行 / 46 731 字符 / 20 张表 0 列数不一致 / 37 个编号一一对应 / 0 个 Markdown 外链
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
| 报告定稿自查 | 编号定义 vs 全文引用、20 张表列数、章节引用、反引号路径存在性 | 37 个编号一一对应（`A-20` 已显式并入 `A-21`）、0 列数不一致、0 个 Markdown 外链；未解析的路径 token 均为裸文件名、包名、占位符或 A-10「仓内不存在」的举证本身 |

> 临时空目录建在系统 temp 后立即清理；所有 Python 片段都设了 `PYTHONDONTWRITEBYTECODE=1`，
> **未修改仓库内任何文件**（本报告与 `docs/README.md` 索引两处文档新增除外）。
