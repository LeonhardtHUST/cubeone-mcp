# cubeone-mcp W0–W6 审定整改 · 增量 PRD / 范围确认（2026-11-04）

> **定位**：本文是标准 SOP 第 1 阶段的**增量范围确认**，供架构师做实现编排使用。
> **唯一执行依据**：`docs/2026-11-04-next-steps-plan.md`（W0–W6 任务卡、F-1~F-6、§5 裁决、§5.1 落地约束、§6 不做清单、§7 纪律、§8 证据）。
> **上游输入**：`docs/reports/audit-2026-11-04-agent-engineer.md`（37 条发现：P0 10 / P1 17 / P2 10）。
> **本文不做**：不重写整份计划、不做竞品/市场分析、不新增判据、不回改任何旧计划 / 旧报告 / 实现文件。所有验收判据**逐字沿用计划 §3 原文**。
> **基线**：HEAD `683ee7f`（`docs(plan): 下一步工作计划——审定整改 W0-W6（L0，未开工）`），`origin/master` 同值；版本轴四处 = `0.7.2`，最新 tag `v0.7.2`。
> **工作区时点说明**：`docs/2026-11-04-next-steps-plan.md` 存在主理人写入的**未提交修改**（+28/−9：D-1~D-5 裁决记录、§5.1 落地约束、状态行与 §4(1) 版本措辞）。本文的裁决与执行边界以**该工作区版本**为准；HEAD 版计划尚无 §5 / §5.1，架构师编排时请勿只读 HEAD 版本。该改动非本 PRD 产出，本 PRD 未回改任何旧文件。

---

## 0. 项目信息

| 项 | 值 |
|---|---|
| Language | 简体中文（与用户需求一致） |
| Programming Language | 沿用现栈、无前端 UI：Python（`scripts/`、`tools/`、`tests/`）+ Node.js ESM（`lib/`、`tests/node/`、`tools/*.mjs`）+ Bash（`scripts/regen.sh`）+ GitHub Actions YAML。**默认 Vite + React + MUI + Tailwind 栈不适用**（本轮为既有 CLI/MCP 工具整改，无 GUI 改动） |
| Project Name | `cubeone_mcp_w0w6_remediation` |
| 目标版本（仅准备，不执行） | `0.7.3` 补丁版（D-1）；发布正文**必须**写明 BREAKING behavior 与迁移提示 |
| 用户裁决 | D-1~D-5 已于 2026-11-04 交互问答逐项裁决并写入计划 §5，本轮**无需用户再裁决** |

**原始需求复述**：把审定报告的 37 条发现收敛为 W0–W6 七批可验收、不破坏既有设计的执行卡并**现在开工**；按 W0→W6 全批实现到 **GATE-3.1 之前**，逐批独立 commit、四条验收全绿、推送 `master` 并确认 CI success；**不打 tag、不建 GitHub Release、不发 npm、不回填发版台账**。W3 单独一批、独立 commit，改完立刻跑 `check_taskboard.py`，未实测项如实保留挂起；A-22 补齐 `check_release.py` 判据并保留脚本名与所有既有调用点；两本接板指南加入 `package.json files`。

---

## 1. 产品定义

### 1.1 产品目标（一句话）

**让 Agent 拿到的每一个 `verdict=PASS` / 每一条发版绿灯都有真实证据支撑，且不破坏既有 7 项判据契约与两条合法发布路径。**

三个正交分目标：
1. **消除假绿**：G1 四类假绿 + MCP 未知参数 + `.ioc` 换行注入，一律在输入校验层拒绝或判 `fail`，证据不成立绝不输出 `PASS`。
2. **对齐操作面与真源**：SKILL/README 的工具面、Phase 2 现状、证据口径、回滚口径与代码/看板事实一致，且用 CI 扫描防再次漂移。
3. **补齐发布门禁**：`check_release.py` / `publish.yml` / `ci.yml` 机器可查项补齐，人工核项写进 D35，同时保住 dispatch 与幂等补发路径。

### 1.2 本轮范围边界（严格以 §5.1、§6 为准）

**做什么（必须）**
- W0→W6 全部实现，停在 GATE-3.1 之前；逐批独立 commit（W0/W1 ≥ L2，W3 = L0），四条验收全绿，推送 `master` 并确认 CI success。
- W3 是**独立 commit（L0）**的连锁批次，改完立刻跑 `check_taskboard.py`；**不得**为让脚本变绿而把 T2.2 / T2.6 / 串口 / `pio device monitor` 等未实测项标成完成。
- `check_release.py` **保持原名与所有既有调用点**；补官方 registry、`--network` 下 dist-tags 判红、台账回填 / Release / 工作区 / CI 机器可查项；D35 写清「哪些机器查、哪些人核」。
- 两本接板指南（`docs/guides/gate-2.0-checklist.md`、`docs/guides/testbeds-board-map.md`）进 `package.json files`；其余 `docs/` 在 SKILL 顶部注明「仅仓库可见」。SKILL 顶部说明与 `files` 清单**互为补充，不能只做其一**。
- GATE-3.1 证据包**可以准备并列出**，但不得执行（见 §5 停止线）。

**不做什么（§6 明确不做清单，逐条照录）**
1. **不动** `CHECK_ORDER` / 7 个 check id / schema `/2`（F-1）；不排期核验器 2.0（D36③）。
2. **不做**时钟 / 参数级判据（D36②：期望值无可信来源，半吊子判据比没有更糟）。
3. **不把** `check_release.py` 挂进 CI（`ci.yml` 已写明刻意不挂的理由）。
4. **不把** handshake 的 SKIP 翻成 FAIL、不给 CI 造假素材（F-6）。
5. **不删** `workflow_dispatch`、不把幂等 `::warning` 改回判红（F-5，D33 补账路径）。
6. **不回改**三份旧计划原文（`docs/README.md` §2 约定），只加索引行。
7. **不把未实测能力写成已实测**：串口段、`pio device monitor`、T2.2 / T2.6 如实保留。
8. **不动** `testbeds/` 里的模板原仓；不重跑烧录 / 不重做 L5（沿用 `phase2-bringup-2026-11-04.md` 证据）。
9. **不做**「为修这些单独发紧急版」；一次补丁版带齐。

### 1.3 三条刚性契约（实现时不可破坏）

- **F-1「7 项判据 + schema `/2`」是刚性契约**：`scripts/verify_generation.py:96–113` 的 7 个 `CHECK_*` 与 `CHECK_ORDER`、`ci.yml` 的 `verify_generation.py --version | grep -q "/2"`、`tools/list` / SKILL / 发布正文 / 契约文档的「7 项」口径是同一份契约。**不得新增第 8 个 check id、不得改 schema**。落地方式：把「证据不成立」做成 `main()` 输入校验统一退 `EXIT_INPUT_ERROR = 2`；把「生成确实失败」（整行 `KO`）**复用** `log_cannot_map` 判 `status=fail`（rc=1）。两类都补测试，但 `checks` 数组长度与 id 集合恒为 7。
- **F-5 两条合法路径不可破坏**：① `workflow_dispatch` 是**正常发布入口**（push master → Actions → Run workflow）；② D33 **补发历史 Release** 依赖 `::warning` 幂等跳过分支。因此发布流里跑 `check_release.py` **不带 `--network`**（只校验本地版本轴、tag、正文、工作区），dist-tags 判红**只加在 `--network` 发布后核证路径**（显式带 `--registry=https://registry.npmjs.org/`）；dispatch 增必填 `tag` 输入并校验 `tag == package.json.version`；**不删 dispatch、不把幂等 warning 改回判红**。理由：目标版本尚未发布时 `latest` 必然不等于 `package.json.version`，若当发布前门禁会把正常发版自己卡死。
- **F-6 的合法取舍不可破坏**：`npm_mcp_handshake.mjs` 的 SKIP 是有意取舍（`:160`「宁可 SKIP 也不造假素材」、`--require-materials` 严格模式下 SKIP 即失败、`:372` 已写「SKIPPED（未验证，不代表通过）」）。A-24 **只把 `skip=N` 带进 headline 与 Job Summary**，**不把 SKIP 翻成 FAIL、不给 CI 造假素材**；CI 的 node 22 档仍用 `--ci`，`--require-materials` 行为与退出码不变。

### 1.4 改动面概览（UI Design Draft 等价物）

无 GUI 改动。Agent 可见的「界面」是文档与工具描述：SKILL §1.2 拆成「本包 3 工具」与「外部 server（另一通道）」**两张表**并与 `TOOL_DEFS` 一一对应；SKILL 顶部新增「`docs/` 仅仓库可见」声明；SKILL 第 5 步写清 MCP 证据 = `structuredContent`（不产生 `verify.json`）；`tools/list` 描述同步。其余为脚本 / 测试 / 工作流 / 看板的文本与逻辑改动。

---

## 2. 用户故事与可机器验收判据（W0–W6）

> 判据**逐字沿用计划 §3 原文**，未自创。格式：作为 X / 我需要 Y / 以便 Z。

### W0 · 堵 G1 四类假绿 —— 【P0 · 最高优先】

**用户故事**：作为**依赖 G1 门禁的自动化脚本 / Agent**，我需要「证据不成立」的四类输入一律被拒（退 2 或判 FAIL）而不是拿到 `verdict=PASS`，以便我的绿灯代表真实通过、而非静默的假绿。

**四类假绿（本批最高优先，必须全部堵住）**：① 漏传 `--ioc`（A-11）；② 指错 `--project-root`（A-14）；③ 日志里有整行 `KO` 而核验器不认（A-17①）；④ 拿任意文本 / 空日志当 `--log`（A-17② + A-4）。

**统一做法（计划 §3 原文）**：按 F-1，在 `scripts/verify_generation.py:1635–1660` 的输入校验段新增 `validate_evidence_inputs(...)`，凡「证据不成立」一律退 `2`；`lib/server.mjs:421–474` `validateArgs()` 同步加参数联动，让 MCP 在调用前给可机读错误。唯一例外 W0-3：`KO` 是域内「生成失败」，复用现有判据判 `fail`。

| 编号 | 验收判据（§3 原文） |
|---|---|
| W0-1 / A-11 | 负样本 `run_cli()`：只给 `--expect-pins` 不给 `--ioc` ⇒ rc=2、无 JSON；把 `:766` 用例**拆成两条**：无 flag 仍 `skip`、有 flag 无 ioc 必须 rc=2 |
| W0-2 / A-14 | 负样本：空目录、`Core/Src` 存在但无 `.c` ⇒ 均不得得到 `verdict=PASS`；`tests/test_verify_multifile.py` 补一条 |
| W0-3 / A-17① | 新 fixture `tests/fixtures/log_ko.txt`（2 行 `KO`、0 行 `Cannot map`）⇒ `verdict=FAIL`、rc=1；`regen.sh` 既有用例不受影响 |
| W0-4 / A-17② + A-4 | 四个负样本：`references/README.md`、空日志、随机文本、含 `KO` 真日志 ⇒ 全部不能 `verdict=PASS`；**正向回归**：`tests/fixtures/log_clean.txt`（17 行，首行 `[INFO] STM32CubeMX 6.18.1…`）与 `docs/logs/phase4/` 真实成功日志必须仍 PASS；改 `:586` 断言为 rc=2 |
| W0-5 / A-8② | `tests/node/server.test.mjs` 组 4 增 1 条；`node --test tests/node/*.test.mjs` 全绿 |

**W0 验收命令（§3 原文）**：
```bash
python -m pytest tests/ -q
node --test tests/node/*.test.mjs
python scripts/verify_generation.py --version | grep -q "/2"   # 7 项 / schema 不变
python tools/check_taskboard.py && python tools/check_release.py
```

**W0 不做（§3 原文）**：不把形态校验做成 `warn`（warn 不阻塞，等于没修）；不改 `:1429` 的 `verdict` 计算式；不加第 8 个 check id；不动 `verify_documents()` 的签名与 `CHECK_ORDER`。

> 执行提示（F-2 / F-3，计划 §1）：`test_verify_generation.py:766`（skip）与 `:586`（空日志 rc=0）两条旧断言**必须改 / 拆**，变红是预期不是回归；所有「必须不能 pass」的负样本用 `run_cli()` 直跑，不复用 `run_verify()`（后者断言 JSON 落盘，会掩盖 rc=2）。

### W1 · 堵 `.ioc` 内容注入 + 能力边界可机读

**用户故事**：作为**通过 MCP 改 `.ioc` 字段的 Agent**，我需要 `key`/`value` 含换行时被双层拒绝、且超出 GPIO 能力的写入有可读告警，以便 `.ioc` 不被静默污染、并知道何时必须手改并强制过 G1。

| 编号 | 验收判据（§3 原文） |
|---|---|
| W1-1 / A-21 | 负样本 CRLF / LF / 尾空格三种变体 ⇒ `changed=false`、`.ioc` 行数不变、rc=2；`tests/test_ioc_field.py` 与 Node 组 4 各加一条 |
| W1-2 / A-20 | **不做权限层拦截**（能力层 ≠ 权限层，见 `references/capability-boundary.md:8–10`）；机读字段存在且文案可读即可 |

### W2 · 操作面归位（Agent 看的那几页）

**用户故事**：作为**安装本包后按 SKILL.md 行动的 Agent**，我需要工具面、通道判据、L2 命令、Phase 2 现状与回滚口径都与代码事实一致，以便不会走错通道、拒绝已验证能力、引用不存在的文件或用 `git checkout --` 丢掉用户改动。

| 编号 | 验收判据（§3 原文） |
|---|---|
| W2-1 / A-1 | 全文检索 `cubemx_help` 不再充当通道判据；SKILL 工具表与 `TOOL_DEFS` 一一对应 |
| W2-2 / A-5 | W5-4 的状态词扫描通过后，SKILL/README 不含「无硬件 / 整体挂起 / 一律缺」；§3 的 L5 行可正常声明 L5 |
| W2-3 / A-10 | 脚本解析 SKILL 反引号路径，仓内不存在的引用归零（占位符需显式标注） |
| W2-4 / A-12 | 全文只剩一种回滚口径 |

### W3 · 状态真源归位（连锁批次，单独 commit / L0）

**用户故事**：作为**去 `docs/TASKBOARD.md` 复核状态的人或 Agent**，我需要任务表、GATE、快照、散文合计、索引与 L5 事实一致，以便不会二次得到「无硬件 / 整体挂起」的错误结论；同时未实测能力必须如实保留挂起，不能被「让脚本变绿」的动机抹平。

| 编号 | 验收判据（§3 原文） |
|---|---|
| W3-1 / A-28 | `python tools/check_taskboard.py` rc=0；`git diff` 中散文数字与表格一致；**不得**为了让脚本绿而把未实测项标成完成 |
| W3-2 / A-27 | 构造含 `v0.8.0` 假 tag 的自测副本，判据③仍生效；本仓 rc=0 |
| W3-3 / A-13 / A-26 / B-3 | 脚本比对 `docs/**/*.md` 与索引，真漏项归零；D 编号 = `DECISIONS.md` 最大号 D36 |

> D-2 / §5.1(2)：W3 不与 W0/W1/W2 混在同一 commit；改完**立刻**跑 `check_taskboard.py`。F-4：T2.2 FW_H7、T2.6 负路径、串口 `pio device monitor` 如实保留挂起（`phase2-bringup-2026-11-04.md:175` 明写本工程未启用任何 USART）。

### W4 · 证据口径与随包可达性

**用户故事**：作为**用 npm 包接板的用户**，我需要 MCP 证据口径写对、两本接板指南随包可见、三个工具返回文本各自自洽，以便不会去找一个根本不生成的 `verify.json`、也不会在接板时看不到板卡对照表。

| 编号 | 验收判据（§3 原文） |
|---|---|
| W4-1 / A-7 | 文档口径与代码一致；不出现「MCP 会生成 verify.json」的表述 |
| W4-2 / A-9 | 三个工具的返回文本各自自洽 |
| W4-3 / A-3 | `npm pack --dry-run` 清单含两本指南；SKILL 无随包死链 |
| W4-4 / A-2 / A-8 | `tests/node/server.test.mjs` 组 1 增 ETIMEDOUT 用例；组 4 既有 5 例不受影响 |

### W5 · 发布门禁与防再漂移

**用户故事**：作为**准备发版的维护者**，我需要无 tag / 无 Release / 看板未收口的发版被机器判红、SKIP 不再被读成全测过、状态词漂移被 lint 拦住，以便 GATE-3.1 不再完全靠人；同时正常 dispatch 发版与 D33 补发历史 Release 仍能走通。

| 编号 | 验收判据（§3 原文） |
|---|---|
| W5-1 / A-22 | 对当前 v0.7.2 跑 `--network` rc=0；构造错版本副本 rc≠0；`docs/releases/README.md` 的「三证」措辞同步（F-5） |
| W5-2 / A-23 | 无 tag 输入 ⇒ 红；v0.7.3 正常路径 ⇒ 绿；**D33 补发历史 Release 的 `::warning` 幂等分支保持可走**（F-5） |
| W5-3 / A-24 | CI node 22 档输出可见 `skip=1`；`--require-materials` 行为与退出码不变（F-6） |
| W5-4 / A-6 | 故意注入一个失效状态词 ⇒ lint 红；当前 HEAD 绿。**不要把 `check_release.py` 挂进 CI**——`ci.yml` 注释已写明那会让长期未发版状态每次都红，是刻意取舍 |

### W6 · 编排链与 P2 收尾

**用户故事**：作为**跑 `scripts/regen.sh` 的维护者**，我需要缺参不死循环、退出码守住 `{0,1,2}` 契约、R1 分支有真实负样本覆盖、dry-run 不写盘，以便编排链在异常输入下可诊断、可回归、不误报已回滚。

| 编号 | 验收判据（§3 原文） |
|---|---|
| W6-1 / A-18 | `timeout 5 bash scripts/regen.sh -e` ⇒ 2 秒内退 2 且点名缺参；`tests/test_regen_preflight.py` 加一条 |
| W6-2 / A-19 | 假 Python 桩造 9009 ⇒ 退 2；`references/regen-exit-codes.md` 同步 |
| W6-3 / A-25 | `pytest tests/test_regen_preflight.py -q` 全绿；`regen.sh:451` 在 `:515` rollback 之前打印「已从备份回滚」的时序不实陈述一并修 |
| W6-4 / B-9 等 | `git check-ignore` 命中 sidecar；dry-run 不建目录；超时文案不再宣称已回滚 |

**执行序（§2 原文）**：`W0 → W1 → (W2 ∥ W5) → W3 → W4 → W6 → GATE-3.1`（本轮停在 GATE-3.1 前）。单写者原则（§7）：`scripts/` + `lib/` 由同一人串行改（W0→W1→W4-4），`SKILL.md` / `docs/` 由另一人改，`tests/` 跟随对应实现改，W3 单独一人一次写完。

---

## 3. 需求池 P0 / P1 / P2 归类表

> 与审定报告 §6「发现总表」一一对应，合计 **37 条：P0 10 / P1 17 / P2 10**；「承接批次」按计划 §2 覆盖编号 + §3 任务卡；「随包」指改动落在 `SKILL.md` / `lib/` / `scripts/` / `package.json`，需新补丁版才能到达 npm 用户。

**P0（10 条）**

| 编号 | 发现（简） | 承接批次 | 随包 |
|---|---|---|---|
| A-1 | SKILL「MCP 通道」列外部 server 工具，与本包 3 工具零交集 ⇒ MCP 能力不可达 | W2-1 | 是 |
| A-5 | SKILL/README/TASKBOARD 仍写「无硬件 / Phase 2 挂起」，与 L5 相反（初稿 P1 → 定稿 P0） | W2-2 + W3-1 | 是(W2) / 否(W3) |
| A-7 | MCP 通道不落 `verify.json`，却当 L4 证据 ⇒ 证据链断 | W4-1 | 是 |
| A-11 | `expect_pins` 有 / `ioc` 无 → 静默 `skip`，`verdict` 仍 pass | W0-1 | 是 |
| A-14 | `--project-root` 指错 → 静默退回单文件扫描，`verdict` 仍 pass | W0-2 | 是 |
| A-17 | 核验器不认 `KO` 行、不认日志形态；`references/README.md` 当 `--log` ⇒ `verdict=PASS errors=0` | W0-3 + W0-4 | 是 |
| A-21（含 A-20） | `ioc_field set` 的 `value` 含 `\r\n` 可注入任意 `.ioc` 键（能力边界无护栏并入本条） | W1-1 + W1-2 | 是 |
| A-22 | `check_release.py` 只比本地版本轴；`--network` 只 WARN 且未带官方 registry | W5-1 | 否 |
| A-23 | `publish.yml` 的 `workflow_dispatch` 可在无 tag / 无 Release / 看板未收口时发版 | W5-2 | 否 |
| A-24 | T6 恒 SKIP 时 `npm_mcp_handshake.mjs` 仍输出 `[HANDSHAKE SMOKE] PASS`、rc=0 | W5-3 | 否 |

**P1（17 条）**

| 编号 | 发现（简） | 承接批次 | 随包 |
|---|---|---|---|
| A-2 | `readOnlyHint=true` 与实际写盘、三处文档口径矛盾 | W4-4 | 是 |
| A-3 | 随包 SKILL 的 7 个 `docs/` 引用是死链（含接板清单、板卡对照） | W4-3 | 是 |
| A-4 | 「`--log` 必须是真日志」只有文档护栏；空日志仅 warn，仍 pass | W0-4 | 是 |
| A-6 | 状态真源与操作面之间无机器校验，漂移可再次发生 | W5-4 | 否（CI） |
| A-8（3 子项） | MCP 层与脚本层契约未对齐：ETIMEDOUT 误归因 / 未知参数静默 / `readJson` 吞错 | W0-5（②）+ W4-4（余项） | 是 |
| A-9 | 返回文本含必然失效的临时路径；「verdict/checks」提示对 2/3 工具不成立 | W4-2 | 是 |
| A-10 | SKILL 的 L2 命令引用本仓不存在的 `stdio_port.c` / `AGENTS.md` | W2-3 | 是 |
| A-12 | SKILL 回滚口径自相矛盾，`git checkout --` 会丢用户改动 | W2-4 | 是 |
| A-13 | `docs/README.md` 索引真漏项 2 个，且把 0.7.1 标「当前版本」 | W3-3 | 否 |
| A-15 | `spawnSync` 同步阻塞 + 120 s，超时又被误归因 | W6-4（与 W4-4 同批改 `lib/server.mjs`） | 是 |
| A-16 | `physical()` 全链解析失败时退回纯词法路径（fail-open） | W6-4（同上） | 是 |
| A-18 | `regen.sh` 带值选项漏参时 `shift 2` 不改变参数个数 ⇒ 死循环 | W6-1 | 是 |
| A-19 | `exit "$VERIFY_RC"` 透传 `9009` / `127` / 信号码，破坏 `{0,1,2}` 契约 | W6-2 | 是 |
| A-25 | R1 新增分支零测试覆盖（超时归因 / `--fail-fast-on-migrate` / 回滚 / 值变体） | W6-3 | 部分 |
| A-26 | 测试数字四套口径未标基准 | W3-3 | 部分 |
| A-27 | `check_taskboard.py` 判据③只做全局代理，`TAG_RE` 钉死 `^v0\.[67]` | W3-2 | 否 |
| A-28 | TASKBOARD 自身与事实不符、散文 35 与表格 36 自相矛盾 | W3-1 | 否 |

**P2（10 条，含合并列示）**

| 编号 | 发现（简） | 承接批次 | 随包 |
|---|---|---|---|
| B-1 | 触发词覆盖本包做不到的 4 类任务；返回噪声与 12 000 字符尾部截断 | W2 | 是 |
| B-2 | 无 `outputSchema`；`structuredContent` 无体积上限；长 stdout 会截掉首行 `verdict` | **计划 §2/§3 无承接任务卡（见 §5 待确认问题）** | 是 |
| B-3 | 单写者名分 / 工具数量措辞 / 台账「当前版本」/ D 编号四处小漂移 | W3-3 | 否 |
| B-4 | `ListTools` 夹带内部字段等；含 §2.8 降级第 4 项（`action` 默认三方口径） | W6-4 | 部分 |
| B-5 | 编码加固未覆盖 `tools/*`；`--log` 读入前无形态校验；参数组合缺负样本 | W6-4 | 否 |
| B-6 | 两套入口参数面不同，SKILL 未讲清何时用哪个 | W2 | 否 |
| B-7 | 硬编码 Windows CubeMX 路径，可升级为自动探测 | W6-4 | 部分 |
| B-8 | `regen.sh` 头部 sandbox 约定注释与代码不逐条对应 | W6-4 | 部分 |
| B-9 | `*.ioc.bak.sha256` 未忽略；`--dry-run` 仍 `mkdir -p`；回滚时序不实；双会话 lost-update 竞态等 | W6-4 | 部分 |
| B-10 | 散文/表格口径、D 编号重号、三证/四证、弱断言、`.coverage` 陈旧、owner 冲突、历史 job 数未标时间点 | W6-4 | 否 |

---

## 4. 验收口径

**四条固定命令（§7 原文，每批独立 commit 后必跑、须全绿）**：
```bash
python -m pytest tests/ -q
node --test tests/node/*.test.mjs
python tools/check_taskboard.py
python tools/check_release.py
```

**附加校验（按触发条件加跑，不替换四条）**：
- **改 `SKILL.md` 时加跑版本轴**：校验 `package.json` / `SKILL.md` frontmatter / README 两处**四处仍同值 `0.7.2`**（§7）。注意这是校验一致性，**不是升版**（见 §6）。
- **W0 额外**（§3 W0 验收命令第 3 条）：`python scripts/verify_generation.py --version | grep -q "/2"`，确认 7 项 / schema 不变（F-1 契约）。
- **W3 散文数字人工复核**（§7 + §5.1(2)）：改完**立刻**跑 `check_taskboard.py`，并人工复核散文数字与表格一致；脚本只验「表 ↔ 快照内部自洽」，抓不到「账算对了、事实错了」。
- **W4 随包可达性**（§5.1(4) + W4-3）：`npm pack --dry-run` 清单**必须能看到** `docs/guides/gate-2.0-checklist.md` 与 `docs/guides/testbeds-board-map.md`；SKILL 顶部说明与 `files` 清单互为补充。
- **W5 发布门禁自测**：W5-1 对当前 `v0.7.2` 跑 `--network` rc=0 且构造错版本副本 rc≠0；W5-2 无 tag 输入判红、正常路径判绿且 `::warning` 幂等分支可走；W5-3 CI node 22 档可见 `skip=1`；W5-4 注入失效状态词 lint 判红。
- **推送确认**（D-5 / §7）：推完 `master` 后确认 `git log origin/master..HEAD` 清空 + CI success，即向用户汇报待放行。

**GATE-3.1 证据包（§4(4)，仅准备并列出、不得执行）**：`check_release.py --network` 判绿、`check_taskboard.py` rc=0、`pytest -q` 全绿、`node --test tests/node/*.test.mjs` 全绿、CI success、发布正文三条 CLI 命令与 argparse 逐一对得上、**用户明确放行**。

---

## 5. 待确认问题（Open Questions）与停止线

> **本轮无新增需用户裁决项**：D-1~D-5 已全部裁决。以下为 §5.1(6) 指定「由架构师在实现编排中给出明确方案并回传主理人」的实现层歧义，以及一处计划覆盖缺口，**均不自行扩张范围、不改动 §6 明确不做清单**。

| # | 待确认问题 | 归属 / 建议处理 |
|---|---|---|
| Q-1 | **W4-3「版本号同步」的具体口径**（§5.1(1)）：升版动作属发版批次、不在本轮范围；本轮 `files` 补两本指南时版本号如何处理？ | 由架构师明确；本 PRD 立场：本轮保持 `0.7.2` 不动，仅确保不引入 `version` 与 `tag` 不一致 |
| Q-2 | **F-1 宽松特征行清单的具体取值**（§5.1(6)）：W0-4 要求特征行 OR 且「不可写成严格模板，否则制造新的假红」，清单未枚举 | 由架构师给出明确清单；必须不误伤 `log_clean.txt`（17 行）与 `docs/logs/phase4/` 真实成功日志 |
| Q-3 | **W4-4 的 `action` 三方口径取一**（§5.1(6)）：计划倾向「把『默认』二字删掉，保持 required」 | 由架构师定；不得改动 §6 |
| Q-4 | **B-2 无承接任务卡**：审定报告 P2 的 B-2（无 `outputSchema` / `structuredContent` 体积上限 / 长 stdout 截首行 `verdict`）未出现在计划 §2 覆盖编号或 §3 任何任务卡中 | 请架构师确认是否落入 §6「明确不做」或后续排期；本轮**不自行新增任务卡 / 不扩张范围** |
| Q-5 | **双会话 lost-update 竞态是否上文件锁**（W6-4「至少写进文档登记，是否上文件锁另议」） | 本轮按最小方案仅文档登记，是否上锁由架构师确认 |

**停止线（GATE-3.1 前停，§5.1(5) / D-5）**：
- ✅ 本轮终点：W0→W6 全批实现、逐批独立 commit、四条验收全绿、推送 `master` 并确认 CI success。
- ⛔ **不得执行**：打 tag、创建 GitHub Release、`npm publish`、发布台账回填。GATE-3.1 证据包**可以准备并列出，但不得执行**。
- 推完 `master` 确认 `git log origin/master..HEAD` 清空 + CI success 后，即向用户汇报**待放行**；发版须用户另行明确放行，**不能因为「CI 绿了」就自动打 tag**。

---

## 6. 版本与发布边界（硬边界）

- **本轮不改版本轴**：`package.json` / `SKILL.md` frontmatter / README 两处的升版动作属于**发版批次**，不在 D-5 划定的本轮实现范围内（§5.1(1)）。本轮四处保持 `0.7.2`；改 `SKILL.md` 时「加跑版本轴」是校验四处同值，不是升版。
- **本轮不产生任何 tag / Release / npm 发布**：不打 `v0.7.3` tag、不建 GitHub Release、不 `npm publish`、不回填 `docs/releases/` 发版台账（§5.1(5)、D-5）。
- **D-1 的目标版本 `0.7.3` 仅为发版批次的准备口径**：版本轴按 `0.7.3` 准备、发布正文必须写明 BREAKING behavior 与迁移提示（原本拿 `verdict=PASS` 的四类输入现退 2 或判 FAIL、`ioc_field set` 拒绝换行、MCP 未知参数被拒），但**准备 ≠ 执行**。
- 一次补丁版带齐（§6(9)），**不做**「为修这些单独发紧急版」；W3 / W5 是仓库内改动，随时可推送、不必等版本（§4(5)）。

---

> 本文是 `683ee7f` 时点的**增量范围确认**，不是新计划；与计划冲突时以 `docs/2026-11-04-next-steps-plan.md` §3 / §5.1 / §6 原文为准。后续若实现发生位移，按 `docs/README.md` §2 约定追加勘误链接，**不回改本文与旧计划原文**。
