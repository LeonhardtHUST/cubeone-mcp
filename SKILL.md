---
name: platform32-mcp
description: "STM32 工程全流程编排：把 .ioc 改配置（vscode-cube-mcp）→ 代码生成 → 生成核验（G1 强制关卡）→ PlatformIO 构建（platformio.mcp）→（接板后）烧录与串口验证（stm32-stlink-mcp）串成一条带 L0–L5 验证等级声明的流水线，并输出符合模板 AGENTS.md 提交规范的 commit。当用户说「改一下这个 ioc」「加一个 GPIO / UART / ADC 通道」「CubeMX 重新生成代码」「生成完帮我核一遍」「有没有被静默丢弃的外设」「pio 构建一下」「Flash/RAM 占多少」「烧进去看看」「串口有输出吗」「这个模板工程跑不起来」时使用。只读审计不写盘；任何写操作前必须先备份 .ioc 并报告将改动的对象，生成后必须跑核验器并如实声明验证等级；不替用户提交未经核验的代码，不碰 testbeds/ 之外的模板原仓。"
version: 0.1.0
agent_created: true
license: MIT
compatibility: Python 3.8+（核验器只依赖标准库）；需要已注册的 vscode-cube-mcp / platformio.mcp / stm32-stlink-mcp 三个 MCP server；路径白名单与动作档位见 references/README.md 指向的模板仓 TOOLING-cubemx.md
---

# platform32-mcp：STM32 生成 / 核验 / 构建 / 烧录编排

> **状态：骨架稿（v0.1.0 skeleton）**
> 本文件当前只包含 frontmatter 与章节大纲，正文由 **T1.4（初稿）** 与 **T1.9（定稿）** 填充，
> Phase 2 的烧录/串口增量由 **T3.3** 合并。凡标 `TODO(T1.4)` / `TODO(T1.9)` / `TODO(T3.3)` 的段落
> 都是待填占位，**不要**当作已完成能力对外宣称。

把 `.ioc` 改动、代码生成、生成核验、构建、（接板后的）烧录与串口验证串成一条有据可查的流水线。
每个环节都必须留下可核验的证据（命令输出 / 核验 JSON / diff / 构建数字），否则不许声明完成。

## 0. 硬前提

TODO(T1.4)：写清三个 MCP server 的可用性检查（`cubemx_help`、`pio_system_info`、`doctor`）、
`~/.workbuddy/mcp.json` 注册项与 env 内联变量、`PLATFORMIO_MCP_POLICY=build_only` 的默认档位，
以及"缺任一 server 时停手报错而不是降级为手改文本"的红线。

## 1. 能力索引

TODO(T1.4)：表格化"想做的事 → 入口"，条目预计包含：

| 想做的事 | 入口 | 状态 |
|---|---|---|
| 生成核验（G1 强制关卡） | `scripts/verify_generation.py` | TODO(T1.2/T1.4)：接口与参数以 verifier-dev 的 T1.2 交付为准 |
| 备份 → 生成 → 核验 三步封装 | `scripts/regen.sh` | TODO(T1.3/T1.4)：失败回滚语义以 T1.3 为准 |
| `.ioc` 备份 | `scripts/ioc_backup.py` | TODO(T1.2/T1.4) |
| 只读审计（引脚表 / 时钟树 / 构建数字） | `cubemx_load` + `pio_build` + `pio_size_report` | TODO(T1.4) |
| 改配置 / 生成代码 | `cubemx_configure` / `cubemx_generate` | TODO(T1.4) |
| 烧录 / 调试 / 串口 | `flash_standalone` / `pio_monitor_capture` | TODO(T3.3)，Phase 2 接板后才有证据 |

## 2. 标准流程（写操作）

TODO(T1.4)：按 T1.6 实跑顺序写五步——① 审计与 `git status` 前置检查 ② `.ioc` 备份
③ `cubemx_configure` / `cubemx_generate` ④ **G1 核验不过即回滚** ⑤ `pio_build` + `git diff` 汇报 + 按规范提交。

## 3. 验证等级声明（L0–L5）

TODO(T1.4)：解释 L0–L5 各自"算什么证据"，并给出一句话判据。
定义来源是三个模板仓的 `AGENTS.md`，此处**只链接不复述**（见第 7 节）。

## 4. 提交文案模板

TODO(T1.4)：Conventional Commits `type(scope): 中文简述` + 正文写验证等级与证据路径；
明确禁止 AI 署名尾注、禁止 `--no-verify`、禁止 force push。

## 5. 陷阱速查

TODO(T1.4)：把模板仓的 D1–D9（`TEMPLATE-PLACEHOLDERS.md`）与 H-1–H-6（`docs/HAL-PITFALLS.md`）
做成"症状 → 判据 → 处置"速查表，**只写链接与一句话判据，不复制原文**。
已知必须覆盖的几条：G474 的 `VP_RIF_VS_RIF1` 日志噪音（D8，核验器白名单容忍）、
`AskForMigrate` 被写回 true 导致无头卡死（D7）、`syscalls.c` / `sysmem.c` 叠加路径不更新（D9）、
CubeMX 静默吞配置错误（C2 / D5 / H-6）。

## 6. 串口与烧录（Phase 2，接板后）

TODO(T3.3)：`pio_monitor_capture` 抓 boot log、`flash_standalone` 的 reset/run 语义、
板上无 VCP 时改外接 USB-TTL 的方案、探针被拔/串口被占用的错误分类读法。
**当前会话无硬件，本节整体后移，不要提前填充推测性内容。**

## 7. 参考与依赖

- 模板仓关键文档链接见 `references/README.md`（**只放链接，不复制内容**）。
- 任务与进度真源：`docs/TASKBOARD.md`；已确认决策：`docs/DECISIONS.md`。
- 执行计划与调研报告：`docs/2026-11-03-agent-team-plan.md`、`docs/2026-11-03-execution-research.md`。

## 8. 变更记录

| 版本 | 日期 | 变更 | 任务 |
|---|---|---|---|
| 0.1.0 | 2026-11-03 | 建骨架：frontmatter + 章节大纲 + TODO 标记 | T1.1 |
| 待定 | — | 正文初稿（流程编排知识） | T1.4 |
| 待定 | — | 定稿（吸收 S1–S3 实测教训） | T1.9 |
| 待定 | — | 合并 Phase 2 串口/烧录增量 + L 等级自查清单 | T3.3 |
