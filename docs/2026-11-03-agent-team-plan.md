# platform32-mcp 多 Agent 团队执行计划

> 生成时间：2026-11-03 · 生成者：计划 Agent
> 上游文档：`docs/2026-11-03-execution-research.md`（执行前调研报告，下称"调研报告"）
> 用途：把调研报告 §6 的 Phase 0–3 展开为**逐 Phase 的 Agent 团队分工子计划**，执行 Agent 据此组建团队并开工。
> 文中 L0–L5 验证等级、提交规范引用三个模板仓的 `AGENTS.md`，不在此复述。

---

## 0. 总则（所有 Phase 适用）

### 0.1 核心团队模型

角色化命名 + 按 Phase 机动加员。核心四角色全程在场，专有角色按阶段入场：

| 角色（Agent 名） | 类型 | 职责范围 | 入场 Phase |
|---|---|---|---|
| `platform-lead` | 编排（Team Lead） | 维护共享任务列表、拆派任务、把关验收关卡、唯一面向用户的发言人（AskUserQuestion/汇报）、集成合并 | 0–3 全程 |
| `env-agent` | 环境装配 | MCP 注册、工具安装、doctor/冒烟、固件包管理；**唯一有权改 `~/.workbuddy/mcp.json` 和动 `C:\ST` 相关环境的角色** | 0、2 |
| `verifier-dev` | 核验器开发 | `verify_generation.py` 及单测（Gap-G1），后续所有生成核验的维护者 | 1（主力）、2 |
| `skill-author` | Skill/文档工程 | platform32-mcp 仓库骨架、SKILL.md、references、README | 1、3 |
| `scenario-tester` | 端到端场景 | 在克隆副本上跑全链场景与负路径测试（Phase 1 无硬件；Phase 2 转 HIL） | 1、2 |
| `hil-agent` | 硬件在环 | 烧录、串口、实板验证、探针排障 | 2（专有） |
| `ci-agent` | CI 工程 | GitHub Actions workflow、产物归档 | 3（专有） |
| `evaluator` | 技术评估 | CubeMX2 适配评估、CMake 流评估、strtt RTT 评估（只读，产出评估报告，不改代码） | 3（选做） |

### 0.2 协作协议

1. **单写者原则**：每个文件/目录同一时刻只有一个 owner；跨 owner 改动须经 `platform-lead` 转派。仓库内分工：
   - `scripts/`、`tests/` → `verifier-dev`
   - `SKILL.md`、`docs/`、`README.md`、`references/` → `skill-author`
   - `testbeds/`（场景克隆区）→ `scenario-tester`
   - `.github/` → `ci-agent`
2. **状态落盘可交接**：Agent 不跨会话持记忆。所有进行中状态必须写进仓库文件（任务看板 `docs/TASKBOARD.md` + 各自工作日志），任何角色可被换人不丢进度。
3. **验证等级声明**：每条任务 DoD 必须写明达到的 L 等级（L0–L5）；`platform-lead` 验收时核对证据（命令输出/生成物 diff）。
4. **提交纪律**（继承模板 `AGENTS.md`）：Conventional Commits（`<type>(<scope>): <中文简述>`）；禁止 force push / `--no-verify`；**禁止 AI 署名尾注**；提交正文如实写验证等级。
5. **升级路径**：卡壳 >30 分钟或需要用户决策 → 停手，报 `platform-lead`；涉及用户资产（mcp.json、原模板仓、硬件）→ 必须 AskUserQuestion 确认。
6. **用户决策门**（gate，标记为 **GATE-x**）：到达关卡时由 `platform-lead` 向用户发起问询，未确认不得进入下一步。

### 0.3 全局开工前置：GATE-D（决策问询）

`platform-lead` 在 Phase 0 第一步执行，把调研报告 §8 的 6 个决策点一次性问完（AskUserQuestion，分两批）：

| 编号 | 决策 | 推荐值 | 影响的下游任务 |
|---|---|---|---|
| D1 | CubeMX 版本锁 6.18.1？ | 是 | 全部生成流程 |
| D2 | platformio.mcp 用外部包？ | 是，装；CLI 回退通道保留 | T0.3、Phase 1 构建 |
| D3 | CMake 流砍出 MVP？ | 是（Phase 3 评估） | T3.4 |
| D4 | FW_H7 何时装？ | Phase 2 顺手装 | T2.2 |
| D5 | GitHub remote 现在建？ | 是（`LeonhardtHUST/platform32-mcp`） | T1.1 |
| D6 | 烧录默认探针 ST-Link/SWD？ | 是（X Pulse 板接板日确认） | T2.1 |

---

## 1. Phase 0 子计划：装配（0.5 天，全部 L1 可验）

**目标**：三个 MCP server 在客户端可用，为 Phase 1 提供工具面。
**团队**：`platform-lead` + `env-agent`（`scenario-tester` 可提前入场做冒烟，建议入场）。

### 1.1 任务分解

| ID | 任务 | Owner | 依赖 | DoD（含 L 等级） |
|---|---|---|---|---|
| T0.1 | 执行 GATE-D 决策问询，结论写入 `docs/DECISIONS.md` | platform-lead | — | 6 项决策有记录，L0 |
| T0.2 | 修改 `~/.workbuddy/mcp.json`：新增 `vscode-cube-mcp`（env 内联 `ST_CUBEMX_EXE=C:\ST\STM32CubeMX\STM32CubeMX.exe`、`ST_CUBEMX_ALLOWED_ROOTS=D:\Projects;C:\Users\Leon\WorkBuddy`、`ST_CUBEMX_TIMEOUT=300`）；新增 `platformio.mcp`（`uvx platformio.mcp`，env：`PLATFORMIO_MCP_POLICY=build_only`、`PLATFORMIO_MCP_PIO=C:\Users\Leon\.platformio\penv\Scripts\pio.exe`）；`stm32-stlink` 保持 disabled（Phase 2 再启） | env-agent | T0.1（D1/D2） | 改前备份 mcp.json 到仓内 `docs/backups/`；JSON 语法校验通过；L1 |
| T0.3 | 安装并自检 platformio.mcp：`uvx platformio.mcp doctor` | env-agent | T0.2 | doctor 输出归档 `docs/logs/phase0/`；L1 |
| T0.4 | 逐 server 冒烟：`cubemx_help`（vscode-cube-mcp）、`pio_system_info` + `pio_list_devices`（platformio.mcp）、对 G474 模板仓**只读** `cubemx_load` | scenario-tester | T0.2、T0.3 | 三段输出落盘；`cubemx_load` 不产生任何文件改动（`git status` 验证）；L1 |
| T0.5 | 建 `docs/TASKBOARD.md` 任务看板（后续所有 Phase 的状态板） | skill-author（或 lead 兼） | T0.1 | 看板含全部 Phase 任务与状态列；L0 |

### 1.2 关卡

- **GATE-0**：T0.2 改动 `mcp.json` 前由 `platform-lead` 向用户展示 diff 确认（用户个人配置文件）；T0.4 全绿后宣布 Phase 0 完成。

### 1.3 并行泳道

```
platform-lead:  T0.1 ──► GATE-0 确认 ───────────► GATE-0 收尾
env-agent:            T0.2 ──► T0.3 ──┐
scenario-tester:                └───► T0.4（冒烟）
```

---

## 2. Phase 1 子计划：MVP 无硬件闭环（2–3 天）

**目标**：打通"改 .ioc → 生成 → 核验 → 构建 → 汇报"全链（无需硬件），产出 platform32-mcp 主体。
**团队**：`platform-lead` + `verifier-dev` + `skill-author` + `scenario-tester`（4 人）。

### 2.1 仓库分工快照

```
platform32-mcp/
├── SKILL.md                    ← skill-author
├── scripts/
│   ├── verify_generation.py    ← verifier-dev
│   ├── regen.sh                ← verifier-dev
│   └── ioc_backup.py           ← verifier-dev
├── tests/                      ← verifier-dev（核验器单测）
├── testbeds/                   ← scenario-tester（模板仓克隆副本，.gitignore 掉）
├── references/                 ← skill-author（链接三个模板仓文档，不复制内容）
├── docs/                       ← skill-author + lead（含 TASKBOARD、DECISIONS、logs）
└── .gitignore                  ← lead（新增 /testbeds/）
```

### 2.2 任务分解

| ID | 任务 | Owner | 依赖 | DoD（含 L 等级） |
|---|---|---|---|---|
| T1.1 | 建仓库骨架 + GitHub remote（若 D5=是）+ `.gitignore`（testbeds、logs 局部） | skill-author | Phase 0 | push 成功；结构符合 leonskill 惯例；L0 |
| T1.2 | **核验器 v1** `verify_generation.py`：输入（生成日志路径、`main.c` 路径、`.mxproject` 路径、期望外设清单）；检查项：① 日志无 `Cannot map`（白名单容忍 `VP_RIF_VS_RIF1` 噪音，调研报告 D8）② 期望的每个外设有对应 `MX_xxx_Init()` 定义**且**在 `main()` 中被调用 ③ `.mxproject` 无盘符绝对路径 ④ `syscalls.c`/`sysmem.c` 的叠加路径告警单独降级为 warning；输出 JSON 报告 | verifier-dev | T1.1 | 单测覆盖：正样本（G474 模板现有日志/生成物）、负样本（去 `S_` 前缀信号名、缺白名单参数、TIM4 被静默丢弃复现 H-6）≥5 例；`pytest` 全绿；L2 |
| T1.3 | `regen.sh`：封装"备份 .ioc → `cubemx_generate` → `verify_generation.py`"三步，失败即 `git checkout .ioc` 回滚 | verifier-dev | T1.2 | 在 G474 testbed 实跑一次成功 + 一次失败回滚；L3（不涉构建） |
| T1.4 | **SKILL.md 初稿**：流程编排知识（何时用 cubemx_load/configure/generate、G1 核验强制、L 等级声明、提交文案模板、陷阱速查 D1–D9/H-1–H-6 链接） | skill-author | T1.2（引用核验器用法） | 同行评审（lead + verifier-dev）通过；L0 |
| T1.5 | 建 `testbeds/`：克隆三个模板仓 + `stm32-digital-clock` 副本（`git clone` 本地路径，不碰原仓） | scenario-tester | T1.1 | 四副本就绪且原仓 `git status` 无变化；L1 |
| T1.6 | **场景 S1（改配置）**：G474 testbed 加一个 GPIO 输出（或改 PinState）：`cubemx_load` 审计 → 备份 → `cubemx_configure`/`cubemx_generate` → 核验 → `pio_build` → `git diff` 汇报 → 按规范 commit | scenario-tester | T1.3、T1.4、T1.5 | `pio run` 成功且报告 Flash/RAM 字节；核验 JSON pass；diff 仅含预期文件；L3 |
| T1.7 | **场景 S2（只读审计）**：`stm32-digital-clock` testbed 上 `cubemx_load` + `pio_build`，产出审计报告（引脚表、时钟树键值、构建结果） | scenario-tester | T1.5 | 审计报告落盘 `docs/reports/`；L1 |
| T1.8 | **场景 S3（负路径）**：故意写错信号名（去 `S_` 前缀）/ 漏 `IPParameters` 白名单 → 确认核验器能抓住静默丢弃 | scenario-tester | T1.3、T1.6 | 核验器对两种注入各报 FAIL 且给出原因；L2 |
| T1.9 | SKILL.md 定稿：吸收 S1–S3 的实测教训（跑不通的地方改文档或改脚本） | skill-author | T1.6–T1.8 | 定稿 commit；L1 |

### 2.3 并行泳道

```
skill-author:   T1.1 ──────────────► T1.4 ──────────────► T1.9
verifier-dev:   T1.2 ──► T1.3 ──────────────┘              │
scenario-tester:      T1.5 ──► T1.6 ──► T1.7 ──► T1.8 ─────┘
platform-lead:  持续验收 + GATE-1.1 + GATE-1.2
```

### 2.4 关卡

- **GATE-1.1**（T1.2 完成后）：核验器单测全绿演示，lead 确认 API 稳定后才允许 T1.3/T1.6 依赖它。
- **GATE-1.2**（Phase 收口）：S1–S3 三场景证据链齐（命令输出、核验 JSON、diff、commit），lead 向用户汇报并演示一次 S1 全链。

---

## 3. Phase 2 子计划：烧录与串口（接板后 1–2 天）

**目标**：实板打通"构建 → 烧录 → 串口验证"扩展链；补齐 H723 前置。
**团队**：`platform-lead` + `env-agent` + `hil-agent` + `scenario-tester` + `verifier-dev`（机动）。

### 3.1 阻塞前置：GATE-2.0（用户接板）

- 由 `platform-lead` 向用户发起：请接 ST-Link + 任一目标板（推荐 Penguins-G474 或 X Pulse），告知接线（SWD、供电、共地）。
- 接板确认方式：`hil-agent` 跑 `node .../stmcp/dist/index.js doctor`（probes 非空）+ `pio device list`（出现 USB 串口）。
- **无板降级方案**（用户暂时无板时）：Phase 2 仅执行 T2.2（FW_H7）与 T2.5（串口工具预检/文档），烧录类任务挂起，先行进入 Phase 3。此降级需在 GATE-2.0 一并向用户确认。

### 3.2 任务分解

| ID | 任务 | Owner | 依赖 | DoD（含 L 等级） |
|---|---|---|---|---|
| T2.1 | 启用 `mcp.json` 中 `stm32-stlink`（改前备份）；doctor 实测探针；确认 X Pulse 探针类型（D6） | env-agent | GATE-2.0 | probes 列出序列号；L1 |
| T2.2 | 安装 FW_H7：优先 `swmgr install`（无头），失败转 GUI；之后 H723 testbed 跑通 `pio run`（首次联网拉 framework-stm32cubeh7） | env-agent | T1.5（testbed 在） | H723 构建 Flash/RAM 报告落盘；L3 |
| T2.3 | 烧录基线：G474 testbed 构建产物 → `flash_standalone`（reset=hard, run=true）→ 观察 LED/复位行为 | hil-agent | T2.1 | 烧录日志 + 现象描述（照片/文字）落盘；L5 |
| T2.4 | 串口链路：确认板上 UART→USB 通道与 COM 口；`pio_monitor_capture` 抓 boot log；SKILL.md 增补"串口验证"一节 | hil-agent + skill-author | T2.3 | 抓到有效 boot log 或明确记录该板无 VCP（走外接 USB-TTL 的方案写文档）；L5 |
| T2.5 | **HIL 场景 S4**：`NUEDC_2027/G474/G474_01_gpio`～`G474_03_uart` 中选一个：改一个外设配置 → 生成 → 核验 → 构建 → 烧录 → 串口验证输出 | scenario-tester + hil-agent | T1.3、T2.3、T2.4 | 全链证据链 + L5 声明进 commit；L5 |
| T2.6 | 负路径硬件版：烧录时拔探针/占用串口 → 确认 `pio_port_diagnose`/doctor 的错误分类可读 | hil-agent | T2.4 | 分类结果落盘；L2 |

### 3.3 并行泳道

```
GATE-2.0（用户接板）
   │
env-agent:      T2.1 ──► T2.2（与烧录无依赖，并行）
hil-agent:      T2.1 后 ──► T2.3 ──► T2.4 ──► T2.6
scenario-tester:              └──────────► T2.5 ──► 汇报
skill-author:                     T2.4 的文档增量 ──► SKILL.md 更新
```

### 3.4 关卡

- **GATE-2.1**：首次烧录前，`hil-agent` 必须经 lead 向用户确认目标板可安全中断（正在驱动执行器/继电器的板不接）。
- **GATE-2.2**（收口）：S4 全链演示给用户；L5 证据归档。

---

## 4. Phase 3 子计划：CI 与收尾（1–2 天，可与 Phase 2 降级段并行）

**目标**：CI 模板、文档定稿、选做评估、发布。
**团队**：`platform-lead` + `ci-agent` + `skill-author` + `evaluator`（选做）。

### 4.1 任务分解

| ID | 任务 | Owner | 依赖 | DoD（含 L 等级） |
|---|---|---|---|---|
| T3.1 | GitHub Actions workflow 模板（`.github/workflows/build.yml`）：checkout → `pio run` matrix（G474VE + F103C8 环境）→ 主机 gcc 回归（模板 §3 命令）→ 上传 ELF/HEX/map 产物；**CubeMX 不进 CI**，原因注释写明（ST 专有软件许可 + JVM 镜像成本） | ci-agent | T1.6 | workflow 在 platform32-mcp 或模板仓 fork 上跑绿；matrix 两环境都有构建数字；L3 |
| T3.2 | README 定稿：架构图（三 server 职责 + 编排层）、快速上手（注册 MCP → 跑 S1 场景）、已知限制 | skill-author | T1.9、T2.5 | 同行评审过；L1 |
| T3.3 | SKILL.md 终版：合并 Phase 2 的串口/烧录增补；附 L 等级自查清单 | skill-author | T2.4 | 定稿 commit；L1 |
| T3.4 | 选做评估（产出报告不改代码）：① CubeMX 2.1.1 兼容性（同一 .ioc 双版本生成 diff 对比）② CMake 流可行性（CLT CMake + 模板源码）③ strtt RTT 是否值得引入 | evaluator | 各自独立 | 评估报告落 `docs/evaluations/`，每项给"做/不做/推迟"结论；L1 |
| T3.5 | 发布：建 GitHub remote（若 D5 当时选了否）、打 tag `v0.1.0`、发布说明（含验证等级汇总表：哪些功能 L3、哪些 L5） | platform-lead | T3.1–T3.3 | tag + release notes；L1 |

### 4.2 并行泳道与关卡

```
ci-agent:      T3.1 ─────────────┐
skill-author:  T3.2 ∥ T3.3 ──────┼──► GATE-3.1 ──► T3.5
evaluator:     T3.4（独立，仅文档）┘
```
- **GATE-3.1**（发布前）：lead 向用户演示 CI 绿 + 全文档包，确认后打 tag。

---

## 5. 跨阶段事项

### 5.1 里程碑与用户触点汇总

| 触点 | 时机 | 形式 |
|---|---|---|
| GATE-D | Phase 0 开工 | 6 项决策问询（AskUserQuestion 两批） |
| GATE-0 | mcp.json 改动前 | diff 展示确认 |
| GATE-1.2 | Phase 1 收口 | S1 全链演示 |
| GATE-2.0 | Phase 2 开工 | 接板请求（含无板降级确认） |
| GATE-2.1 | 首次烧录前 | 安全确认 |
| GATE-2.2 | Phase 2 收口 | S4 HIL 演示 |
| GATE-3.1 | 发布前 | CI + 文档包确认 |

### 5.2 交接协议（防 Agent 换人丢状态）

1. `docs/TASKBOARD.md`：唯一状态真源（任务 ID、owner、状态、证据链接），每个角色完成/开始任务时即时更新。
2. 证据一律落盘：命令输出存 `docs/logs/<phase>/`，核验 JSON 存 `docs/reports/`，路径写进 TASKBOARD。
3. 换人规则：新 Agent 入场先读 `TASKBOARD.md` + `docs/DECISIONS.md` + 本文件对应 Phase 节，即可无缝接手。

### 5.3 风险升级矩阵

| 触发 | 处置 |
|---|---|
| 核验器漏报静默丢弃（S3 失败） | verifier-dev 24h 内修不出 → 降级 SKILL.md 加"人工必核清单"，问题挂 issue |
| mcp.json 注册后 server 起不来 | env-agent 对照各 server 文档排障（doctor），仍失败 → 报 lead 问用户是否降级为 Skill 直调 CLI |
| pio_build 在 testbed 诡异失败 | 先跑 `pio pkg update` 排除包漂移；版本锁定值（模板 B7）被上游破坏 → 挂 issue 不擅自升级 |
| 接板日无板 | 走 GATE-2.0 的降级方案，Phase 2 烧录段整体后移，不阻塞 Phase 3 |
| 用户原仓被误改 | 硬规则：所有实验仅限 `testbeds/`；lead 每次验收检查三个模板仓 + NUEDC 原仓 `git status` 必须干净 |

### 5.4 提交里程碑规划（Conventional Commits）

```
chore: 建仓骨架与 .gitignore                    (T1.1)
feat(scripts): 生成核验器 v1 与单测             (T1.2/T1.3)
docs(skill): SKILL.md 初稿                      (T1.4)
feat(tests): S1–S3 场景证据与负路径用例          (T1.6–T1.8)
docs: SKILL.md 定稿与 README                    (T1.9/T3.2/T3.3)
ci: 增加构建 matrix 工作流                      (T3.1)
chore(release): v0.1.0                          (T3.5)
```
