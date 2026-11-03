# references/：外部资料放链接，本仓手册放全文

本目录有两个用途，**用同一个问句区分**：

> **"这份内容如果上游改了，我这里会不会过期？"** 会 → **放链接**；不会 → **可以全文**。

## 规矩

1. **外部资料只放链接**（模板仓 / ST 官方文档）：指向 URL 与本地路径，**不复制正文**。
   理由：`AGENTS.md`、`TOOLING-cubemx.md`、`HAL-PITFALLS.md` 是活的文档，会被上游修订；
   复制一份进来必然与上游分叉，读者不知道哪份是对的。
2. **本仓自有手册页可全文**（`capability-boundary.md` 等）：它们只有本仓维护，**不存在第二个源头**，
   所以没有分叉风险。这类页面的定位是"`SKILL.md` 放不下的细则"。
3. **不写代码**：本目录不放脚本，脚本归 `scripts/`（owner: verifier-dev）。
4. **新增条目要带日期**：链接会腐坏，标注"最后核对日期"，腐坏时便于判断该信谁。

最后核对日期：2026-11-03

## 〇、本仓自有手册页（全文本，非链接）

`SKILL.md` 是**操作面**（每次加载都进上下文），本目录是**手册**（按需查阅）。切分原则是
"读者什么时候需要它"，不是按 §号切。

| 手册页 | 什么时候看它 |
|---|---|
| `capability-boundary.md` | 想知道"这件事工具能不能做"，或要 D25 的原始探测数据、四层权限模型、全绿幻觉链 |
| `verify-contract.md` | 要消费 `verify.json`（字段语义、六项判据细则、三态表、保证边界、`/1→/2` 迁移） |
| `regen-exit-codes.md` | 用 `regen.sh`（退出码 `0/1/2`、`KO` 必要不充分、dirty 语义、`AskForMigrate` 行为约束） |
| `diff-evidence.md` | 要证明"真的改了"（三级确认、`numstat -w` vs `status`、`.ioc` 大 diff 归因、引脚级落地判据） |
| `pitfalls.md` | 遇到 P / D / H 系列陷阱，要看全文而非一句话索引 |

> 这五页由 `skill-author` 维护；它们与 `SKILL.md` 的**唯一真源关系**是：判据在手册页展开，
> 操作结论在 `SKILL.md`。两者冲突时**以手册页为准**，并立即修 `SKILL.md`（说明 `SKILL.md` 被压缩时丢了细节）。

## 一、三个模板仓（平台要服务的工程范式，也是流程验收靶子）

三者结构一致：`AGENTS.md`、`TEMPLATE-PLACEHOLDERS.md`、`.ioc`、`platformio.ini`、
`scripts/cubemx-*.mx`、`boards/`。默认分支均为 `master`。

| 仓库 | 远端 | 本地路径（只读参考） |
|---|---|---|
| template-mcu-STM32F103C8T6 | https://github.com/LeonhardtHUST/template-mcu-STM32F103C8T6 | `D:\Projects\GitHub\template-mcu-STM32F103C8T6` |
| template-mcu-STM32G474-series | https://github.com/LeonhardtHUST/template-mcu-STM32G474-series | `D:\Projects\GitHub\template-mcu-STM32G474-series` |
| template-mcu-STM32H723-series | https://github.com/LeonhardtHUST/template-mcu-STM32H723-series | `D:\Projects\GitHub\template-mcu-STM32H723-series` |

> 硬约束：以上三个仓**只读**。本仓任何实验都只能在 `testbeds/` 的克隆副本里做。

### 1.1 本仓直接依赖的关键文档

| 文档 | 作用（本仓为什么需要它） | 远端链接 | 本地路径 |
|---|---|---|---|
| `AGENTS.md` | L0–L5 验证等级定义、提交规范、12 条硬约束——本 Skill 的纪律来源 | https://github.com/LeonhardtHUST/template-mcu-STM32G474-series/blob/master/AGENTS.md | `D:\Projects\GitHub\template-mcu-STM32G474-series\AGENTS.md` |
| `TEMPLATE-PLACEHOLDERS.md` | 占位符 A1–A4、陷阱 **D1–D9**——陷阱速查表的一手来源 | https://github.com/LeonhardtHUST/template-mcu-STM32G474-series/blob/master/TEMPLATE-PLACEHOLDERS.md | `D:\Projects\GitHub\template-mcu-STM32G474-series\TEMPLATE-PLACEHOLDERS.md` |
| `docs/TOOLING-cubemx.md` | 本机 CubeMX CLI 实测大全（§1–§5）、`.mxproject` 绝对路径实测（§3.2）、`syscalls.c`/`sysmem.c` 叠加路径（§3.4） | https://github.com/LeonhardtHUST/template-mcu-STM32G474-series/blob/master/docs/TOOLING-cubemx.md | `D:\Projects\GitHub\template-mcu-STM32G474-series\docs\TOOLING-cubemx.md` |
| `docs/HAL-PITFALLS.md` | 6 个真实故障案例 **H-1–H-6**——核验器负样本的灵感来源。**注意：只在 F103C8T6 与 H723 仓有，G474 仓没有** | https://github.com/LeonhardtHUST/template-mcu-STM32F103C8T6/blob/master/docs/HAL-PITFALLS.md<br>https://github.com/LeonhardtHUST/template-mcu-STM32H723-series/blob/master/docs/HAL-PITFALLS.md | `D:\Projects\GitHub\template-mcu-STM32F103C8T6\docs\HAL-PITFALLS.md`<br>`D:\Projects\GitHub\template-mcu-STM32H723-series\docs\HAL-PITFALLS.md` |
| `docs/BOARD-penguins-g474.md` | Penguins-G474 板级信息（Phase 2 接板时的靶子之一） | https://github.com/LeonhardtHUST/template-mcu-STM32G474-series/blob/master/docs/BOARD-penguins-g474.md | `D:\Projects\GitHub\template-mcu-STM32G474-series\docs\BOARD-penguins-g474.md` |
| `docs/TEMPLATE-UPDATE-AUDIT.md` | 模板升级审计记录（漂移风险判据） | https://github.com/LeonhardtHUST/template-mcu-STM32F103C8T6/blob/master/docs/TEMPLATE-UPDATE-AUDIT.md | `D:\Projects\GitHub\template-mcu-STM32F103C8T6\docs\TEMPLATE-UPDATE-AUDIT.md` |

## 二、多外设变更场景的黄金测试集

| 资源 | 作用 | 远端 | 本地路径 |
|---|---|---|---|
| `NUEDC_2027/G474/` | 10 个渐进式实战工程 `G474_00_empty` → `G474_10_dds_ad9959`（gpio/lcd/uart/adc×3/dac×2/dds），场景 S4 的取材地 | https://github.com/Ink-hust/NUEDC_2027 | `D:\Projects\GitHub\NUEDC_2027\G474` |
| `HUSTRadio/stm32-digital-clock` | F103 实际项目，`.ioc` + `.ioc.bak` 备份惯例；场景 S2（只读审计）的靶子 | 本地仓（`HUSTRadio` 为无 remote 的本地 monorepo） | `D:\Projects\GitHub\HUSTRadio\stm32-digital-clock` |

## 三、三个 MCP server 的一手资料（注册与排障用）

| Server | 形态 | 一手资料 |
|---|---|---|
| vscode-cube-mcp | Python，`uv tool` 安装，`C:\Users\Leon\.local\bin\vscode-cube-mcp.exe` | PyPI / 上游 README（h666zhang，MIT）；能力清单先看 `cubemx_help` 的实时输出 |
| platformio.mcp | Python，`uvx platformio.mcp` | 上游 README（powerdragonfire，MIT）；策略变量 `PLATFORMIO_MCP_POLICY=full/build_only/read_only` |
| stm32-stlink-mcp（`stmcp`） | TypeScript，本机 `C:\Users\Leon\.workbuddy\mcp-servers\stmcp\` | 仓内 `README.md` 与 `dist/index.js doctor` 自检输出 |

## 四、ST 官方文档

| 内容 | 链接 |
|---|---|
| STM32CubeMX 6.18.1 命令行命令表（`load` / `config` / `set` / `csv pinout` / `swmgr install` / `script` 等，`-i`/`-s`/`-q` 三模式） | https://dev.st.com/ |

> 版本锁定：**CubeMX 6.18.1**（GATE-D / D1）。上游文档若已跳到更新版本，以本机实测为准，不要按新版本文档改流程。

## 五、本仓内相关文档

| 文档 | 作用 |
|---|---|
| `../docs/2026-11-03-execution-research.md` | 执行前调研报告（事实性纠正、Gap 分析 G1–G7、风险矩阵） |
| `../docs/2026-11-03-agent-team-plan.md` | 多 Agent 执行计划（任务分解、关卡、提交里程碑） |
| `../docs/DECISIONS.md` | 已确认决策（GATE-D 六项） |
| `../docs/TASKBOARD.md` | 唯一状态真源 |
