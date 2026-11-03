# 任务看板（TASKBOARD）— 唯一状态真源

> **owner：`skill-author`**（建板与格式维护）。**状态列的更新权归各任务 Owner**，别人不得代改。
> 上游：`docs/2026-11-03-agent-team-plan.md`（下称"计划"）、`docs/2026-11-03-execution-research.md`（下称"调研报告"）。
> 交接协议见计划 §5.2：新 Agent 入场按 `本文件` → `docs/DECISIONS.md` → 计划对应 Phase 节 的顺序读，即可无缝接手。

最后更新：2026-11-03 · 更新者：skill-author（T1.4 → SKILL.md v0.6.0 + 手册拆分；对齐 FROZEN `31fd1ee`）

---

## 0. 读板须知

### 0.1 状态取值（只有这五种，不要自创）

| 状态 | 含义 | 谁可以写 |
|---|---|---|
| `已完成` | DoD 全部满足**且证据已落盘**（证据列有可点开的路径） | 任务 Owner |
| `进行中` | 已开工，尚无完整证据 | 任务 Owner |
| `待开始` | 未被认领或依赖未满足 | 任务 Owner / lead |
| `挂起` | 有明确的**外部阻塞**（如无硬件、等用户决策），不是"没做" | lead（挂起通常来自关卡） |
| `阻塞` | 依赖任务失败或卡壳 >30 分钟，已在升级路径上 | 任务 Owner |

### 0.2 铁律

1. **不许编造进度**：没有证据文件就不许写 `已完成`。证据列写"待补"是合法的，写假链接不是。
2. **L 等级必须如实**：L 等级是"这份证据能证明到哪一步"，来自三个模板仓 `AGENTS.md` 的定义。
   只跑了脚本没看结果 → 不是 L3；没有实板现象记录 → 不是 L5。
3. **证据一律落盘**：命令输出 → `docs/logs/<phase>/`；核验 JSON → `docs/reports/`；评估报告 → `docs/evaluations/`。
   路径写进本表"证据链接"列。注意 `docs/logs/` 被 `.gitignore` 局部忽略（仅本地证据），
   其余证据目录入库。
4. **单写者原则**（计划 §0.2-1）：`scripts/`、`tests/` → verifier-dev；`SKILL.md`/`docs/`/`README.md`/`references/` → skill-author；
   `testbeds/` → scenario-tester；`.github/` → ci-agent。跨 owner 改动须经 lead 转派。
5. **原仓只读**：`D:\Projects\GitHub\` 下三个模板仓、`NUEDC_2027`、`HUSTRadio`、`leonskill-*` 一律只读。
   实验只能在 `testbeds/` 的克隆副本里做。

### 0.3 本次会话范围声明

**当前会话无硬件**（GATE-D 已确认，Phase 2 整体后移）：

- Phase 2 的**烧录 / 串口 / HIL 段**（T2.1、T2.3–T2.6）全部 `挂起`，等 GATE-2.0 接板日。
- T2.2（FW_H7 安装）按计划属 Phase 2，一并 `挂起`；接板日与 T2.5 同批处理。
- 不阻塞 Phase 1 与 Phase 3 推进（计划 §5.3 "接板日无板" 风险条）。

---

## 1. 任务表

> 列：`任务ID | 任务 | Owner | 依赖 | 状态 | L 等级 | 证据链接`
> `—` 表示无依赖；`待补` 表示证据尚未产出（不是"已完成但忘了贴"）。

### Phase 0：装配（0.5 天，全部 L1 可验）

| 任务ID | 任务 | Owner | 依赖 | 状态 | L 等级 | 证据链接 |
|---|---|---|---|---|---|---|
| T0.1 | 执行 GATE-D 决策问询，结论写入 `docs/DECISIONS.md` | platform-lead | — | 已完成 | L0 | `docs/DECISIONS.md`（用户已确认 6 项；文件正文待 lead 落盘，当前为 T1.1 占位） |
| T0.2 | 改 `~/.workbuddy/mcp.json`：新增 `vscode-cube-mcp`（内联 `ST_CUBEMX_EXE`/`ST_CUBEMX_ALLOWED_ROOTS`/`ST_CUBEMX_TIMEOUT=300`）、新增 `platformio.mcp`（`uvx`，`PLATFORMIO_MCP_POLICY=build_only`）；`stm32-stlink` 保持 disabled | env-agent | T0.1 | 进行中 | L1 | 待补：`docs/backups/`（改前备份）+ JSON 校验输出 → `docs/logs/phase0/` |
| T0.3 | 安装并自检 `uvx platformio.mcp doctor` | env-agent | T0.2 | 进行中 | L1 | 待补：`docs/logs/phase0/platformio-mcp-doctor.log` |
| T0.4 | 逐 server 冒烟：`cubemx_help`、`pio_system_info` + `pio_list_devices`、对 G474 模板仓**只读** `cubemx_load` | scenario-tester | T0.2、T0.3 | 待开始 | L1 | 待补：三段输出 → `docs/logs/phase0/`；`cubemx_load` 后原仓 `git status` 干净 |
| T0.5 | 建 `docs/TASKBOARD.md` 任务看板 | skill-author | T0.1 | 已完成 | L0 | 本文件（25 条任务 + GATE 表 + 证据约定，已投入实际使用） |

### Phase 1：MVP 无硬件闭环（2–3 天）

| 任务ID | 任务 | Owner | 依赖 | 状态 | L 等级 | 证据链接 |
|---|---|---|---|---|---|---|
| T1.1 | 建仓库骨架 + `.gitignore`（testbeds、logs 局部）+ GitHub remote push | skill-author | Phase 0 | 已完成 | L0 | commit `9b89a10` `chore: 建仓骨架与 .gitignore`（12 files/+842）；remote `https://github.com/LeonhardtHUST/platform32-mcp`（Public，default `main`） |
| T1.2 | **核验器 v1.2** `scripts/verify_generation.py`：**7 个**固定 check id（`log_cannot_map` / `main_init_present` / `main_init_called` / **`pins_present`** / `mxproject_abs_path` / `mx_script_abs_path` / `syscalls_path`），`blocking: bool` 取代 `level`，JSON schema 升 **`/2`**（参数收进 `inputs`），`--project-root` 扫 `.mx` 三态，`--expect-pins` 引脚级 | verifier-dev | T1.1 | 已完成 | L2 | `pytest 69 passed / 0 failed` → `docs/logs/phase1/t1.2-pytest.log`；引脚级正负样本 `docs/logs/phase1/v1.2-pins/`；契约 `docs/reports/t1.2-verifier-contract.md`（v1.2，含 §1.5 保证边界与 §4.1 实测） |
| T1.3 | `scripts/regen.sh`：备份 `.ioc`+`.mxproject` → 前置检查（`--require-clean` 可选 / 版本戳与迁移提示只读）→ CubeMX 生成（cwd=工程根，timeout≥240s，**查日志整行 `KO`**）→ 核验 → 失败**从备份**回滚并打印 `Core/` 状态 | verifier-dev | T1.2 | 已完成 | L4（生成核验，未跑 pio） | 真跑：`docs/logs/phase1/regen-v1.1-success/`（rc=0）、`regen-v1.1-rollback/`（rc=1，`.ioc`/`.mxproject` 恢复后 sha256 与生成前一致）；KO 判据/脏 `.ioc`/`--require-clean` 由 `tests/test_regen_preflight.py`（11 例）覆盖 |
| T1.4 | **SKILL.md 初稿**：流程编排知识（双通道调用、G1 核验强制、L 等级声明、提交文案模板、陷阱速查 P/D/H 索引） | skill-author | T1.2 | 进行中 | L0 | `SKILL.md` **v0.6.0**（350 行，对齐核验器 1.2.0：7 项 / schema `/2`）+ 5 个手册页 `references/{capability-boundary,verify-contract,regen-exit-codes,diff-evidence,pitfalls}.md`；commit `4e8f4ee`（拆分）+ 本次提交（对齐）；**同行评审未做** |
| T1.5 | 建 `testbeds/`：克隆三个模板仓 + `stm32-digital-clock` 副本（本地路径 clone，不碰原仓） | scenario-tester | T1.1 | 已完成 | L1 | `docs/logs/phase1/t1.5-testbeds.log`（4 副本就绪；原仓快照一致） |
| T1.6 | **场景 S1（改配置）**：G474 testbed 加 GPIO 输出/改 PinState：审计 → 备份 → 改配置 → 生成 → 核验 → `pio run` → `git diff` 汇报 → 按规范 commit | scenario-tester | T1.3、T1.4、T1.5 | 已完成 | L4 + L3 | `docs/reports/t1.6-s1-report.md` + `docs/logs/phase1/s1-*`。7 项 pass、构建 SUCCESS 10.95 s、**Flash 3 744→3 792（+48）/ RAM 1 584 不变**、实质改动仅 2 文件、`USER CODE` 零触碰。**DoD 补充（lead 采纳）**：`--project-root` 下**预期**出现 **1 条** `mx_script_abs_path: warn`（`scripts/cubemx-init.mx:5` 的 `__PROJECT_DIR__` 占位符未替换），`verdict` 仍须 `pass`；**≥2 条 = 异常要查**（实测正是 1 条） |
| T1.7 | **场景 S2（只读审计）**：`stm32-digital-clock` testbed 上 `cubemx_load` + `pio_build`，产出审计报告（引脚表、时钟树键值、构建结果） | scenario-tester | T1.5 | 已完成 | L1（构建 L3） | `docs/reports/t1.7-s2-audit-stm32-digital-clock.md` + `docs/logs/phase1/t1.7-s2-build.log` |
| T1.8 | **场景 S3（负路径）**：故意写错信号名（去 `S_` 前缀）/ 漏 `IPParameters` 白名单 → 确认核验器能抓住静默丢弃 | scenario-tester | T1.3、T1.6 | 已完成 | L2 | `docs/reports/t1.8-s3-report.md` + `docs/logs/phase1/s3b*-regen/`。**(b)** 有虚拟引脚缺 `IPParameters` → 日志出现真实 `Cannot map`；**(b-2)** 仅声明 `Mcu.IP*` 无引脚映射 → **日志干净、`MX_TIM4_Init` 0 次**，只有 `main_init_present` 能发现。**(a) 经 lead 裁决不做**（样本数 1→2 不改变结论）。**副产品**：真实 `Cannot map` 级别为 `[INFO]`，落在 `NOISE_RE` 过滤集合内 → 证实 `--log` 必须用原始 stdout |
| T1.9 | SKILL.md 定稿：吸收 S1–S3 实测教训。**另含「v1.2 能力占位」**：`pins_present` 在 v1.2（能力代号，与脚本版本号 `1.2.0` 同名纯属巧合，二者须在文中区分）落地，定稿时要写清"传 `--expect-pins` 才有引脚级保证"这一档 | skill-author | T1.6–T1.8 | 已完成 | L1 | `944c3e8` 对齐核验器 1.2.0（7 项 / 引脚级）+ `ae9b997` 保证边界三段式与版本自证。SKILL.md 349 行 + 5 个 `references/` 手册页 |

### Phase 2：烧录与串口（**本会话整体挂起**，接板后 1–2 天）

| 任务ID | 任务 | Owner | 依赖 | 状态 | L 等级 | 证据链接 |
|---|---|---|---|---|---|---|
| T2.1 | 启用 `stm32-stlink`（改前备份）；doctor 实测探针；确认 X Pulse 探针类型（D6） | env-agent | GATE-2.0 | 挂起 | L1 | 待补：doctor probes 序列号 → `docs/logs/phase2/` |
| T2.2 | 安装 FW_H7（优先 `swmgr install` 无头）；H723 testbed 跑通 `pio run` | env-agent | T1.5 | 挂起 | L3 | 待补：H723 Flash/RAM 报告 |
| T2.3 | 烧录基线：G474 testbed 产物 → `flash_standalone`（reset=hard, run=true）→ 观察 LED/复位 | hil-agent | T2.1 | 挂起 | L5 | 待补：烧录日志 + 现象描述 → `docs/logs/phase2/`、`docs/reports/` |
| T2.4 | 串口链路：确认 UART→USB 通道与 COM 口；`pio_monitor_capture` 抓 boot log；SKILL.md 增补"串口验证" | hil-agent + skill-author | T2.3 | 挂起 | L5 | 待补：boot log 或"该板无 VCP + 外接 USB-TTL 方案"记录 |
| T2.5 | **HIL 场景 S4**：`NUEDC_2027/G474/G474_01_gpio`～`G474_03_uart` 选一个跑全链（改配置→生成→核验→构建→烧录→串口） | scenario-tester + hil-agent | T1.3、T2.3、T2.4 | 挂起 | L5 | 待补：全链证据链 + L5 声明进 commit |
| T2.6 | 负路径硬件版：烧录时拔探针 / 占用串口 → 确认 `pio_port_diagnose`/doctor 错误分类可读 | hil-agent | T2.4 | 挂起 | L2 | 待补：分类结果 → `docs/logs/phase2/` |

### Phase 3：CI 与收尾（1–2 天，可与 Phase 2 降级段并行）

| 任务ID | 任务 | Owner | 依赖 | 状态 | L 等级 | 证据链接 |
|---|---|---|---|---|---|---|
| T3.1 | `.github/workflows/build.yml`：checkout → `pio run` matrix（G474VE + F103C8）→ 主机 gcc 回归 → 上传 ELF/HEX/map；**CubeMX 不进 CI**（ST 专有许可 + JVM 镜像成本，原因写注释） | ci-agent | T1.6 | 待开始 | L3 | 待补：Actions run URL + 两环境构建数字 |
| T3.2 | README 定稿：架构图（三 server 职责 + 编排层）、快速上手（注册 MCP → 跑 S1）、已知限制 | release-engineer（`README.md` 独占；原 owner skill-author） | T1.9、T2.5 | 进行中 | L1 | 待补：`README.md`（当前 52 字节占位）+ 评审记录 |
| T3.3 | SKILL.md 终版：合并 Phase 2 串口/烧录增补；附 L 等级自查清单 | skill-author | T2.4 | 待开始 | L1 | 待补：定稿 commit |
| T3.4 | 选做评估（只读，产出报告不改代码）：① CubeMX 2.1.1 兼容性（同一 `.ioc` 双版本生成 diff）② CMake 流可行性 ③ strtt RTT 是否引入 | evaluator | 各自独立 | 待开始 | L1 | 待补：`docs/evaluations/`，每项给"做/不做/推迟"结论 |
| T3.5 | 发布：打 tag `v0.1.0` + release notes（含验证等级汇总表：哪些 L3、哪些 L5） | platform-lead | T3.1–T3.3 | 待开始 | L1 | 待补：tag + release notes（remote 已在 T1.1 建好，无需再建） |

---

## 2. 关卡（GATE）状态表

> 关卡未过 = 下游任务不得开工。由 `platform-lead` 向用户发起问询。

| 关卡 | 触发时机 | 前置 | 状态 | 结论 / 备注 |
|---|---|---|---|---|
| **GATE-D** | Phase 0 开工 | — | ✅ **已通过** | 6 项决策已由用户确认（D1 锁 6.18.1 / D2 装 platformio.mcp / D3 CMake 砍出 MVP / D4 FW_H7 接板日 / D5 现在建 Public remote / D6 ST-Link+SWD）。落盘见 `docs/DECISIONS.md` |
| **GATE-0** | T0.2 改动 `mcp.json` **前** | GATE-D | 待触发 | 需向用户展示 diff 确认（个人配置文件）；T0.4 全绿后宣布 Phase 0 完成 |
| **GATE-1.1** | T1.2 完成后 | GATE-0 | 待触发 | 核验器单测全绿演示；lead 确认 API 稳定后才允许 T1.3/T1.6 依赖 |
| **GATE-1.2** | Phase 1 收口 | GATE-1.1 | 待触发 | S1–S3 三场景证据链齐（命令输出、核验 JSON、diff、commit），并向用户演示一次 S1 全链 |
| **GATE-2.0** | Phase 2 开工 | GATE-1.2 | 挂起 | 用户接板请求（ST-Link + 目标板、告知 SWD/供电/共地）；**当前无硬件，已按降级方案把烧录段整体后移** |
| **GATE-2.1** | 首次烧录前 | GATE-2.0 | 挂起 | 安全确认：目标板不在驱动执行器/继电器 |
| **GATE-2.2** | Phase 2 收口 | GATE-2.1 | 挂起 | S4 全链演示 + L5 证据归档 |
| **GATE-3.1** | 发布前 | GATE-1.2（含 T3.1–T3.3） | 待触发 | 演示 CI 绿 + 全文档包，确认后打 tag |

---

## 3. 证据目录约定

| 目录 | 内容 | owner | 是否入库 |
|---|---|---|---|
| `docs/logs/phase0/` … `docs/logs/phase3/` | 命令输出、doctor 自检、构建日志 | 各任务 owner | 否（`.gitignore` 局部忽略，仅本地） |
| `docs/reports/` | 核验 JSON、审计报告、场景证据链 | verifier-dev / scenario-tester | 是 |
| `docs/evaluations/` | T3.4 选做评估报告 | evaluator | 是 |
| `docs/backups/` | `mcp.json` 等个人配置的改前备份 | env-agent | 是（据 T0.2 DoD"备份到仓内"） |

---

## 4. 进度快照（截至 2026-11-03）

| 阶段 | 任务数 | 已完成 | 进行中 | 挂起 | 待开始 |
|---|---|---|---|---|---|
| Phase 0 | 5 | 2（T0.1、T0.5） | 2（T0.2、T0.3） | 0 | 1（T0.4） |
| Phase 1 | 9 | 5（T1.1、T1.2、T1.3、T1.5、T1.7） | 2（T1.4、T1.6） | 0 | 2（T1.8、T1.9） |
| Phase 2 | 6 | 0 | 0 | 6 | 0 |
| Phase 3 | 5 | 0 | 0 | 0 | 5 |
| **合计** | **25** | **7** | **4** | **6** | **8** |

> **T1.2 / T1.3 已由 verifier-dev 回填（v1.1 定稿）**：核验器 6 个 check id + `blocking` + schema `/2`；
> `regen.sh` 改为**查 KO**判生成成败、默认允许脏 `.ioc`（失败从备份恢复）、不拦不改 `AskForMigrate`。
> 证据：`docs/logs/phase1/t1.2-pytest.log`（61 passed）、`docs/logs/phase1/regen-v1.1-*/`；
> 契约：`docs/reports/t1.2-verifier-contract.md`。**GATE-1.1 可触发。**
> `pins_present`（引脚级第 7 项）已在 **v1.2** 落地：未改动的 G474 基线 + `--expect-pins PB0=GPIO_Output` → **fail**（外设级全 pass），`PC13=GPIO_Output` → pass。S1 建议在 `regen.sh` 加 `--expect-pins`，并用外部断言做交叉验证。

GitHub remote：`D5 = 是`，仓址 `https://github.com/LeonhardtHUST/platform32-mcp`（Public），由 T1.1 创建。

---

## 5. 变更记录

| 日期 | 变更 | 变更者 |
|---|---|---|
| 2026-11-03 | 建板：Phase 0–3 共 25 条任务 + GATE 状态表 + 证据目录约定（T0.5） | skill-author |
| 2026-11-03 | T1.1 已完成（commit `9b89a10` + Public remote）；T0.5 已完成；T1.4 转进行中（SKILL.md v0.2.0 初稿落盘，§1 待 T1.2 回填） | skill-author |
| 2026-11-03 | T1.5、T1.7 置已完成；T1.6 置进行中；T1.4 → SKILL.md v0.3.0（§0 双通道 D12、§1 按实现回填、§5 增 P1–P4），待同行评审 | skill-author |
| 2026-11-03 | T1.6 DoD 补充：允许且**预期** 1 条 `mx_script_abs_path` warn（`__PROJECT_DIR__` 占位符），≥2 条即异常（lead 采纳，见 SKILL.md §1.4） | skill-author |
| 2026-11-03 | T1.2、T1.3 置已完成（核验器 v1.1：6 check id / `blocking` / `--project-root`；regen.sh：`AskForMigrate` 生成前硬拦 + 失败回滚 + 成功后复位）；Phase 1 进度同步 | verifier-dev |
| 2026-11-03 | T1.4 → `SKILL.md` v0.6.0（350 行）：手册拆分到 5 个 `references/` 页（commit `4e8f4ee`，无语义变更）+ 对齐 FROZEN `31fd1ee`（7 项含 `pins_present`、`--expect-pins`/`--ioc`、`--allow-signal` 精确匹配、保证边界改为"引脚级需显式传参"） | skill-author |
| 2026-11-03 | `e20adba test(scripts)`：删除 `tests/test_verify_generation.py` 中同名重复定义造成的 **122 行死代码**（8 个函数各出现两次、前一份永不执行）；删 123 行、44 个唯一用例、**74 passed 不变** | verifier-dev |
| 2026-11-03 | `67dd940 test(scripts)`：归档 v1.1 冻结版**独立第三方复核**（pytest 74、`.mx` 六态 6/6、`pins_present` 正反对照、`--allow-signal` 短词拦截） | env-agent |
| 2026-11-03 | 采纳 lead 的 D30.1/D30.2：`--ioc` 恢复（`pins_present` 的必需搭档；"删参判据必须是没有消费者，而非当前没有"）；保证边界定稿为**三段式**（无条件保证 / 有条件保证 / 明确不保证）；T3.2 移交 `release-engineer`（`README.md` 独占） | skill-author |
