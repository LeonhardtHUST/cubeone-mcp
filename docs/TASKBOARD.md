# 任务看板（TASKBOARD）— 唯一状态真源

> **owner：`skill-author`**（建板与格式维护）。**状态列的更新权归各任务 Owner**，别人不得代改。
> 上游：`docs/2026-11-03-agent-team-plan.md`（下称"计划"）、`docs/2026-11-03-execution-research.md`（下称"调研报告"）。
> 交接协议见计划 §5.2：新 Agent 入场按 `本文件` → `docs/DECISIONS.md` → 计划对应 Phase 节 的顺序读，即可无缝接手。

最后更新：2026-11-03 22:10 · 更新者：lead（**M1 收口与发布三证回填**：0.6.2 tag/Release/npm 三证落行、GATE-3.1 由"事后补审"改为"已通过"、T3.5 补 v0.6.1 Release 链接）

---

## 0. 读板须知

### 0.1 状态取值（只有这六种，不要自创）

| 状态 | 含义 | 谁可以写 |
|---|---|---|
| `已完成` | DoD 全部满足**且证据已落盘**（证据列有可点开的路径） | 任务 Owner |
| `进行中` | 已开工，尚无完整证据 | 任务 Owner |
| `待开始` | 未被认领或依赖未满足 | 任务 Owner / lead |
| `挂起` | 有明确的**外部阻塞**（如无硬件、等用户决策），不是"没做" | lead（挂起通常来自关卡） |
| `阻塞` | 依赖任务失败或卡壳 >30 分钟，已在升级路径上 | 任务 Owner |
| `已关闭` | 经裁决判定**不做**：有裁决理由与裁决人。不是未完成，**不计入 `待开始`** | lead（必须写明理由与裁决人） |

> **`已关闭` 与 `挂起` 的区别（必须分清，否则快照算不平）**：
> `挂起` 是**外部阻塞**——条件满足后会回到任务表开工（如 Phase 2 等接板）；
> `已关闭` 是**裁决终止**——不会再开工，理由是"做了也没有消费者"这类结论。
> 二者都不是"没做"，但只有 `挂起` 会回来。
>
> **为什么要正式增设第六种**：T3.4 早就被写成"不做（已关闭）"，而本表头却声明"只有这五种"——状态名不在册，快照就归不进任何一档，M3 的 `tools/check_taskboard.py` 也没法校验。把它入册后，看板、快照、校验脚本三者才共用一套口径。当前唯一实例：T3.4。

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

### 0.4 角色登记

> 目的：解审定异议 2（"角色表与实名不符、计划外角色无人记账"）。
> 角色名一律以 `docs/2026-11-03-agent-team-plan.md` §0.1 的角色表为准，**不另起名**。

#### 0.4.1 计划外角色（计划里没有、实际出场的）

| 角色（Agent 名） | 授权范围 | 授权人 |
|---|---|---|
| `software-engineer` | **T0.4 冒烟实现**（`tools/mcp_smoke.py`，1481 行）：写权限 `tools/` 下新建冒烟脚本；**不含** `scripts/`、`tests/`、`SKILL.md`。**M0 回填期追加一段临时授权**：经 lead 转派，本角色获 `docs/DECISIONS.md` / `docs/TASKBOARD.md` / `README.md` 的文档写权（任务 R-G1/R-A2/R-A3/R-A4/R-A5），改动留工作区由 lead 统一提交 | `platform-lead` |
| `software-qa-engineer` | **T0.4 复核**：独立复跑冒烟、审议判据 `ok = (not isError) and not text_failed` 是否成立（该判据源于 D31 的实测反例）；只读 + 提修正建议，**不改实现代码** | `platform-lead` |
| `release-engineer` | **T3.1**（`.github/workflows/ci.yml`）与 **T3.2**（`README.md` 定稿）的独占写权；后由 lead 接手收口（T3.1 收口 commit `996d19a` / `b14fba5`，T3.2 `b14fba5` / `3ee4387`） | `platform-lead` |

> 记账口径：计划外角色**出场即登记**，写清"授权到哪些路径"。不写授权范围的登记等于没登记——下次换人时无法判断他能不能改那个文件。

#### 0.4.2 计划 8 角色的出场情况

| 角色（Agent 名） | 出场情况 | 承担的任务 / 未出场原因 |
|---|---|---|
| `platform-lead` | **已出场** | T0.1（GATE-D 六项问询并落盘）、T3.5（三个 tag 与两个 GitHub Release）、全程 GATE 裁决与验收复核（D12 / D27 的独立复核）、本表交接协议维护 |
| `env-agent` | **已出场** | T0.2（`mcp.json` 改前备份与提议 diff；按 D12 降级为文档交付）、T0.3（`platformio.mcp` 安装 + doctor + 握手）、`.ioc` 全量取证（D24 的依据）、v1.1 冻结版第三方复核（`67dd940`） |
| `verifier-dev` | **已出场** | T1.2（`scripts/verify_generation.py` v1.2，7 check id / schema `/2`）、T1.3（`scripts/regen.sh`）、`tests/` 全量单测（74 例）与 `docs/reports/t1.2-verifier-contract.md`；死代码清理 `e20adba` |
| `skill-author` | **已出场** | T0.5（建本看板）、T1.1（仓骨架 + `.gitignore` + remote）、T1.4 / T1.9（`SKILL.md` v0.6.0，350 行）、`references/` 五个手册页、D30 / D22 相关判据的表述 |
| `scenario-tester` | **已出场** | T1.5（`testbeds/` 四副本）、T1.6（S1 全链）、T1.7（S2 只读审计）、T1.8（S3 负路径 + `set pin` 能力边界四语法探测，D25 的依据） |
| `hil-agent` | **未出场** | 专属任务 T2.3 / T2.4 / T2.6 全部依赖 GATE-2.0 接板；本会话无硬件（D7 已裁定 Phase 2 整体后移）。**不是漏排班**——接板日第一顺位启用 |
| `ci-agent` | **未出场** | 计划 §4.1 把 T3.1 分配给本角色，执行期**改派**给计划外的 `release-engineer`（见 0.4.1）；按单写者原则 `.github/` 不可两人同写，故未并行启用，避免同一 workflow 双写冲突 |
| `evaluator` | **未出场** | T3.4 三项评估经裁决为"推迟（① ②）/ 不做（③）"——**没有结论可给，就没有评估工作**，故未指派。这也是 `docs/evaluations/` 长期为空目录的原因（现由 `docs/evaluations/2026-11-03-t3.4-closure.md` 落盘关闭结论，目录已非空） |

---

## 1. 任务表

> 列：`任务ID | 任务 | Owner | 依赖 | 状态 | L 等级 | 证据链接`
> `—` 表示无依赖；`待补` 表示证据尚未产出（不是"已完成但忘了贴"）。

### Phase 0：装配（0.5 天，全部 L1 可验）

| 任务ID | 任务 | Owner | 依赖 | 状态 | L 等级 | 证据链接 |
|---|---|---|---|---|---|---|
| T0.1 | 执行 GATE-D 决策问询，结论写入 `docs/DECISIONS.md` | platform-lead | — | 已完成 | L0 | `docs/DECISIONS.md`（用户已确认 6 项；文件正文待 lead 落盘，当前为 T1.1 占位） |
| T0.2 | 改动 `mcp.json` 以注册两个 server | env-agent | T0.1 | **已完成（降级为建议）** | L1 | **按 D12 不替用户改配置**：产出 `docs/backups/mcp.proposed.diff`（含内联 `ST_CUBEMX_EXE`/`ST_CUBEMX_ALLOWED_ROOTS`/`ST_CUBEMX_TIMEOUT=300`、`platformio.mcp` 经 `uvx` + `PLATFORMIO_MCP_POLICY=build_only`、`stm32-stlink` 保持 disabled），改前备份脱敏入库（`mcp.json.bak-*.redacted.json`，JWT 残留 0）。注册动作留给用户，注册指南见 `docs/guides/mcp-registration.md` |
| T0.3 | 安装并自检 `uvx platformio.mcp doctor` | env-agent | T0.2 | 已完成 | L1 | `docs/logs/phase0/platformio-mcp-install.log`（0.2.0 安装成功）、`platformio-mcp-doctor.log`（`ok:true`，Core 6.2.0 / policy build_only）、`platformio-mcp-handshake.log`（协议 `2025-11-25`，**40 个工具**，`HANDSHAKE PASS`） |
| T0.4 | 逐 server **工具调用级**冒烟：`cubemx_help`、`cubemx_load`（对 G474 只读）、`pio_system_info`、`pio_list_devices` | software-engineer（实现）+ software-qa-engineer（复核） | T0.2、T0.3 | 已完成 | L1 | `tools/mcp_smoke.py`（**1481 行**，**sha256 `43e0641c…`**，git blob `1c669d43…`）+ `docs/logs/phase0/mcp-smoke.log`（**4/4 通过，`SMOKE PASS`**，`cubemx_help` 127ms / `cubemx_load` 25.4s / `pio_system_info` 2.8s / `pio_list_devices` 1.8s）+ `mcp-smoke-negative.log`（`--negative-control`，**exit=1、`SMOKE FAIL`、`必需调用通过 2/4（缺 cubemx_help、cubemx_load）`**）。**只读性有证据**：`.ioc` sha256 前后均为 `f57b1d33…`。**已知缺口**：`isError=True` 分支未执行验证（负向对照只到"前置命令不存在"就 SKIP），见 release notes 已知限制。**v0.1.1 已升级**：判据从 `ok = not isError` 改为 `ok = (not isError) and not text_failed`——因为实测 `.ioc` 为垃圾内容时 CubeMX 弹模态框挂住、被超时强杀后 server 返回 `"[FAIL exit=None]…"` 但 **`isError=False`**，旧判据会把这次彻底失败判成 PASS。三条路径实测：越界 `isError=True`→FAIL、缺失 `isError=True`→FAIL、**执行失败 `isError=False`+`[FAIL`→改前 PASS / 改后 FAIL**。新证据 `docs/logs/phase0/mcp-smoke-error.log`。**历史口径（v0.1.1 时）**：929 行 / `4fb474e9…`——脚本随判据升级而增长，引用一律以现行值为准 |
| T0.5 | 建 `docs/TASKBOARD.md` 任务看板 | skill-author | T0.1 | 已完成 | L0 | 本文件（25 条任务 + GATE 表 + 证据约定，已投入实际使用） |

### Phase 1：MVP 无硬件闭环（2–3 天）

| 任务ID | 任务 | Owner | 依赖 | 状态 | L 等级 | 证据链接 |
|---|---|---|---|---|---|---|
| T1.1 | 建仓库骨架 + `.gitignore`（testbeds、logs 局部）+ GitHub remote push | skill-author | Phase 0 | 已完成 | L0 | commit `9b89a10` `chore: 建仓骨架与 .gitignore`（12 files/+842）；remote `https://github.com/LeonhardtHUST/cubeone-mcp`（Public，default `main`） |
| T1.2 | **核验器 v1.2** `scripts/verify_generation.py`：**7 个**固定 check id（`log_cannot_map` / `main_init_present` / `main_init_called` / **`pins_present`** / `mxproject_abs_path` / `mx_script_abs_path` / `syscalls_path`），`blocking: bool` 取代 `level`，JSON schema 升 **`/2`**（参数收进 `inputs`），`--project-root` 扫 `.mx` 三态，`--expect-pins` 引脚级 | verifier-dev | T1.1 | 已完成 | L2 | **v1.1 轮 61 passed / 0 failed** → `docs/logs/phase1/t1.2-pytest.log`；**v1.2 轮复核 74 passed** → `docs/logs/phase1/t1.2-pytest-v1.2-recheck.log`（`--basetemp` 干净目录重跑，2026-11-03 21:18）；引脚级正负样本 `docs/logs/phase1/v1.2-pins/`；契约 `docs/reports/t1.2-verifier-contract.md`（v1.2，含 §1.5 保证边界与 §4.1 实测） |
| T1.3 | `scripts/regen.sh`：备份 `.ioc`+`.mxproject` → 前置检查（`--require-clean` 可选 / 版本戳与迁移提示只读）→ CubeMX 生成（cwd=工程根，timeout≥240s，**查日志整行 `KO`**）→ 核验 → 失败**从备份**回滚并打印 `Core/` 状态 | verifier-dev | T1.2 | 已完成 | L4（生成核验，未跑 pio） | 真跑：`docs/logs/phase1/regen-v1.1-success/`（rc=0）、`regen-v1.1-rollback/`（rc=1，`.ioc`/`.mxproject` 恢复后 sha256 与生成前一致）；KO 判据/脏 `.ioc`/`--require-clean` 由 `tests/test_regen_preflight.py`（11 例）覆盖 |
| T1.4 | **SKILL.md 初稿**：流程编排知识（双通道调用、G1 核验强制、L 等级声明、提交文案模板、陷阱速查 P/D/H 索引） | skill-author | T1.2 | 已完成 | L0 | `SKILL.md` **v0.6.0**（350 行，对齐核验器 1.2.0：7 项 / schema `/2`）+ 5 个手册页。commit：`4e8f4ee` 拆分 · `944c3e8` 对齐 1.2.0 · `ae9b997` 三段式 · `071b6aa` S3 修正 · `03d6e1d` 评审修正。**同行评审已过**（lead 逐条对照代码与模板 `AGENTS.md:105-110` 抽查 9 项判据，提出 4 处机械层问题并已修复：代码围栏破损、`D1–D26`→`D1–D30`、不存在的 `ci-agent`、`compatibility` 与 CI 矩阵不一致） |
| T1.5 | 建 `testbeds/`：克隆三个模板仓 + `stm32-digital-clock` 副本（本地路径 clone，不碰原仓） | scenario-tester | T1.1 | 已完成 | L1 | `docs/logs/phase1/t1.5-testbeds.log`（4 副本就绪；原仓快照一致） |
| T1.6 | **场景 S1（改配置）**：G474 testbed 加 GPIO 输出/改 PinState：审计 → 备份 → 改配置 → 生成 → 核验 → `pio run` → `git diff` 汇报 → 按规范 commit | scenario-tester | T1.3、T1.4、T1.5 | 已完成 | L4 + L3 | `docs/reports/t1.6-s1-report.md` + `docs/logs/phase1/s1-*`。7 项 pass、构建 SUCCESS **12.06 s**（口径以 `docs/logs/phase1/s1-build.log:141` 为准；**release notes 与 README 里的 10.95 s 是 12:33 的 `build-s1-final` 复跑值，不再复用**）、**Flash 3 744→3 792（+48）/ RAM 1 584 不变**、实质改动仅 2 文件、`USER CODE` 零触碰。**DoD 补充（lead 采纳）**：`--project-root` 下**预期**出现 **1 条** `mx_script_abs_path: warn`（`scripts/cubemx-init.mx:5` 的 `__PROJECT_DIR__` 占位符未替换），`verdict` 仍须 `pass`；**≥2 条 = 异常要查**（实测正是 1 条） |
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
| T3.1 | CI 流水线：**实测修正为** `pytest` matrix（Python 3.11 / 3.13）+ 脚本静态检查（`bash -n` / `py_compile` / YAML）+ 同名测试函数硬门禁（后者覆盖前者 = 死代码，见 `e20adba`）+ 不依赖 CubeMX 的入口冒烟。**原计划的 `pio run` matrix 未实现**：本仓无 `platformio.ini`，模板工程在 `testbeds/`（gitignored），且 CubeMX 无法在 ubuntu runner 运行 ⇒ 端到端不进 CI（原因已写进 workflow 注释） | release-engineer → lead（接手收口） | T1.6 | 已完成 | L1（本地等价校验） | `.github/workflows/ci.yml`（2 job / 8 步）+ commit `996d19a` / 去重 `b14fba5`。本地等价校验：pytest 74 passed、`bash -n` OK、`py_compile` OK、YAML 可解析、重名检查 `declared=72 collected=74 dup=0`、`regen.sh` 缺参 `rc=2`。**Actions 已实测通过**：run `41585670440`（`7db26e7`）→ overall **success**，`pytest 3.11` / `pytest 3.13` 各 **74 passed**、`脚本检查` 12 步全过。**首次运行三次全红**，根因是测试依赖 Windows 上真实存在的 `C:/ST/STM32CubeMX/**` 路径（`regen.sh:313/314` 的 `[ -f ]` 检查），已用存根注入消除（`8d3b5d5` + `7db26e7`）——**纯本地开发永远发现不了这类缺陷** |
| T3.2 | README 定稿：定位、能力边界（只可靠代做普通 GPIO）、7 项检查表、保证边界三段式、L0–L5、退出码、两条红线、文档索引 | release-engineer → lead（接手收口） | T1.9、T2.5 | 已完成 | L0 | `README.md` 203 行 + commit `b14fba5` / `3ee4387`。本地校验：无失效链接、L0–L5 与模板 `AGENTS.md:105-110` 逐字一致、Python 宣称范围收紧为 3.11+（= CI 覆盖范围）。**原计划的架构图未做**（三 server 职责已在 `references/` 与 `docs/guides/` 覆盖，README 用文档索引替代、避免重复展开） |
| T3.3 | SKILL.md 终版：合并 Phase 2 串口/烧录增补；附 L 等级自查清单 | skill-author | T2.4 | 待开始 | L1 | 待补：定稿 commit（**阻塞于 Phase 2 挂起**——§6 串口/烧录段无硬件、不做能力宣称，故终版实质等同现版 v0.6.0） |
| T3.4 | 选做评估（只读，产出报告不改代码）：① CubeMX 2.1.1 兼容性（同一 `.ioc` 双版本生成 diff）② CMake 流可行性 ③ strtt RTT 是否引入 | —（本轮不做） | 各自独立 | 已关闭 | — | **关闭理由**：① 本机只装了 6.18.1，要做得再装第二个 CubeMX 版本（数百 MB + 许可交互），而 v0.1.0 的结论不依赖它；②③ 无用户需求，做了也没有使用者。**不产出报告，是因为没有结论可给**——不写"待评估"，避免下一个人以为有人在跟。**关闭结论已落盘**：`docs/evaluations/2026-11-03-t3.4-closure.md`（三项各一句：①推迟 / ②推迟 / ③不做） |
| T3.5 | 发布：打 tag `v0.1.0` + release notes（含验证等级汇总表：哪些 L3、哪些 L5） | platform-lead | T3.1–T3.3 | 已完成 | L1 | **三证核对（`git tag -l` + `gh release list`）**：① tag `v0.1.0` → GitHub Release `cubeone-mcp v0.1.0`（正文含 L0–L5「已验证到什么程度」表；**计划称正文 122 行，实测 71 行**——`gh release view v0.1.0 --json body` 计数，以实测为准）；② tag `v0.1.1` → GitHub Release `cubeone-mcp v0.1.1`；③ tag `v0.6.1` → **Release 已于 2026-11-03 22:07 补发**（`cubeone-mcp v0.6.1 — 首个 MCP 工具通道版本（Release 正文事后补发）`，正文入库 `docs/releases/2026-11-03-v0.6.1-backfill.md`）⇒ 三证齐全；补发触发了一次 `Publish npm` 假红（run `41650583470`，根因：`release` 事件的 workflow 取自 tag 点 `8f99fb0`，早于守卫提交），已按 D33 §33.4.1 记账。④ tag `v0.6.2` → Release + npm 见下方 M1 行。remote 已于 T1.1 建好。**注**：T3.5 之后计划外又发布了 npm `0.6.0` / `0.6.1` 两条（MCP 工具通道），其授权与版本轴规则见 `docs/DECISIONS.md` **D33** |

### M1 修复批次（`docs/2026-11-03-remediation-plan.md` §2，目标 **0.6.2**）

> 本批次由 2026-11-03 修复计划新增，**计入 §4 快照但单列一行**（Phase 0–3 的 25 条口径不变）。
> M3 的 `tools/check_taskboard.py` 落地时要把本表按"Phase 0–3 + 批次表"两段统计，否则两处计数会打架。

| 任务ID | 任务 | Owner | 依赖 | 状态 | L 等级 | 证据链接 |
|---|---|---|---|---|---|---|
| M1 | 接缝修复 R-B1–R-B6 + Node 测试基建 R-D1/R-D2 + R-C1 第一步 + 版本 bump **0.6.2** | software-engineer（实现）/ software-qa-engineer（单测） | M0（D33 在册） | 已完成（三证齐全） | L2（本地四连验 + CI 全绿） | **发布三证（2026-11-03 22:04）**：tag `v0.6.2`（`b8f1857`，三处版本同值 0.6.2）→ GitHub Release `cubeone-mcp v0.6.2`（正文入库 `docs/releases/2026-11-03-v0.6.2.md`）→ npm `cubeone-mcp@0.6.2`（`2026-11-03T14:04:53Z`，Trusted Publisher，17 files / 82.1 kB）→ 本行回填。**CI**：run `41649454775` 全绿 6 job（pytest 3.11/3.13 各 **74 passed**；node 18/20/22 各 **31 passed / 1 skipped**，skip 为仅 win32 有意义的大小写用例；脚本检查绿）。**`lib/server.mjs` 六项**：R-B1 退出码白名单（含 `[<tool>][not-found]` 域内结论例外 + Traceback 优先，计划 §7 风险条要求）、R-B2 子进程 `PYTHONIOENCODING=utf-8`、R-B3 `validateArgs`（required/enum/类型/条件必填）、R-B4 `--` 分隔 + `--json-out` 前置到 `--` 之前、R-B6 未知工具动态清单、R-D1 七个纯函数导出；**另含 R-C1①** `CUBEONE_REQUIRE_ROOTS` opt-in 严格模式（五组合实测：默认→启动 / `=1`+空→exit1 / `=true`+有→启动 / `=YES`+空→exit1 / `=0`→启动）。**`tests/node/server.test.mjs`（QA 写）32 例** → `node --test tests/node/*.test.mjs` **32/32**（Node 22.22.2 与 **18.20.8** 双档）。**CI**：`.github/workflows/ci.yml` 新增 `node` job，**三档矩阵 18/20/22**。**冒烟**：`tools/npm_mcp_handshake.mjs` 新增 T10 → `docs/logs/phase1/npm-mcp/handshake.log`（**11 PASS**）。**pytest 74 passed**。**⚠️ R-B2 的验证边界（如实记录，勿读成"纸面修复"）**：本机 ANSI 代码页 = **cp65001(UTF-8)**，且运行环境已注入 `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1` / `LC_ALL=C.UTF-8`，三组对照（摘 `PYTHONIOENCODING`、`PYTHONUTF8=0`、连 `LANG/LC_ALL` 一起摘）**都造不出 cp936 分支** ⇒ 属**验证对象在本机不可达**，不是没验证；T10 保留作回归守卫，在真实 cp936 机器上才体现。**两条只有真跑才发现的缺陷**：① `node --test <目录>` 在 Node 18 展开、Node 22(Windows) 当模块加载报 `MODULE_NOT_FOUND` ⇒ 命令一律用 glob 形式（计划书 R-D1/R-D2/收口节已同步更正）；② `package-lock.json` 被 `.gitignore:49` 忽略（不入库）⇒ CI 不能用 `npm ci`（缺 lock 必红），改 `npm install` 且不开 `cache: npm`（依赖为精确版本 `1.32.2`，无 semver 漂移） |

---

## 2. 关卡（GATE）状态表

> 关卡未过 = 下游任务不得开工。由 `platform-lead` 向用户发起问询。

| 关卡 | 触发时机 | 前置 | 状态 | 结论 / 备注 |
|---|---|---|---|---|
| **GATE-D** | Phase 0 开工 | — | ✅ **已通过** | 6 项决策已由用户确认（D1 锁 6.18.1 / D2 装 platformio.mcp / D3 CMake 砍出 MVP / D4 FW_H7 接板日 / D5 现在建 Public remote / D6 ST-Link+SWD）。落盘见 `docs/DECISIONS.md` |
| **GATE-0** | T0.2 改动 `mcp.json` **前** | GATE-D | ✅ **已通过**（D12 用户裁定） | 关卡**走过了**（问询 → 用户裁定），裁定结果是"不改"：用户否决写入 `mcp.json` 并界定项目范围，T0.2 因此降级为文档交付（`docs/guides/mcp-registration.md`），见 D12。T0.4 全绿，Phase 0 收口 |
| **GATE-1.1** | T1.2 完成后 | GATE-0 | ✅ **视为通过**（条件满足、证据链齐；未走演示流程，事后补记） | 核验器 API 稳定性由下游实跑反证——T1.3 的 `regen.sh` 与 T1.6 的 S1 都直接依赖它且通过；单测 74 passed。**未单独向用户演示**，此项为事后追认 |
| **GATE-1.2** | Phase 1 收口 | GATE-1.1 | ✅ **视为通过**（条件满足、证据链齐；未走演示流程，事后补记） | S1–S3 三场景证据链齐（`docs/reports/t1.6-s1-report.md` / `t1.7-*` / `t1.8-*` + 日志 + 核验 JSON），D27 已由 lead 独立复核。**未向用户演示 S1 全链**，事后补记 |
| **GATE-2.0** | Phase 2 开工 | GATE-1.2 | 挂起 | 用户接板请求（ST-Link + 目标板、告知 SWD/供电/共地）；**当前无硬件，已按降级方案把烧录段整体后移** |
| **GATE-2.1** | 首次烧录前 | GATE-2.0 | 挂起 | 安全确认：目标板不在驱动执行器/继电器 |
| **GATE-2.2** | Phase 2 收口 | GATE-2.1 | 挂起 | S4 全链演示 + L5 证据归档 |
| **GATE-3.1** | 发布前 | GATE-1.2（含 T3.1–T3.3） | ✅ **已通过**（0.6.2 首次正规执行；历史三次为事后补审） | **2026-11-03 22:00 向用户出示证据并取得放行**：CI 全绿（run `41649454775`）+ 本地四连验（pytest 74 / node 32 / handshake 11 / CI 等价 7 项）+ 变更摘要（8 个 commit）+ 已知限制清单，用户裁定「授权全链发版」。随后 tag → Release → npm → 本看板回填四证齐全。**历史缺口**：`v0.1.0`/`v0.1.1`/`v0.6.1` 三次 tag 均未过本关卡即打出，npm `0.6.0`/`0.6.1` 亦未经关卡——已按 D33 §33.2 记为"事后补审"，不追认其合规性 |

---

## 3. 证据目录约定

| 目录 | 内容 | owner | 是否入库 |
|---|---|---|---|
| `docs/logs/phase0/` … `docs/logs/phase3/` | 命令输出、doctor 自检、构建日志 | 各任务 owner | 否（`.gitignore` 局部忽略，仅本地） |
| `docs/reports/` | 核验 JSON、审计报告、场景证据链 | verifier-dev / scenario-tester | 是 |
| `docs/evaluations/` | T3.4 选做评估报告；当前唯一文件 `docs/evaluations/2026-11-03-t3.4-closure.md`（T3.4 关闭结论，三项各一句） | evaluator | 是 |
| `docs/backups/` | `mcp.json` 等个人配置的改前备份 | env-agent | 是（据 T0.2 DoD"备份到仓内"） |

---

## 4. 进度快照（截至 2026-11-03 22:10，含 M1 修复批次）

> ⚠️ **本区由 M3 的 `tools/check_taskboard.py` 生成/校验，禁止手写。**
> 在脚本落地前（M0 阶段）本节由人一次性重算，之后任何人改任务表都必须跑脚本，不许手改数字。

| 阶段 | 任务数 | 已完成 | 进行中 | 挂起 | 待开始 | 已关闭 |
|---|---|---|---|---|---|---|
| Phase 0 | 5 | **5**（T0.1–T0.5） | 0 | 0 | 0 | 0 |
| Phase 1 | 9 | **9**（T1.1–T1.9） | 0 | 0 | 0 | 0 |
| Phase 2 | 6 | 0 | 0 | **6**（T2.1–T2.6） | 0 | 0 |
| Phase 3 | 5 | **3**（T3.1、T3.2、T3.5） | 0 | 0 | **1**（T3.3） | **1**（T3.4） |
| ‹Phase 0–3 小计› | **25** | **17** | **0** | **6** | **1** | **1** |
| M1 修复批次 | 1 | 0 | **1**（M1，待发版收口） | 0 | 0 | 0 |
| **合计** | **26** | **17** | **1** | **6** | **1** | **1** |

> 校验口径：Phase 0–3 内 `已完成 17 + 挂起 6 + 待开始 1 + 已关闭 1 = 25`；再加 M1 批次的 1 条「进行中」= **26**。
> **两段分开统计**是为了不让整改批次污染原计划的 25 条口径（`T0.5` 的"25 条任务"、§0 各处引用都按 Phase 0–3 计数）。
> M1 一旦发版收口，该行改为「已完成」，合计变 18 已完成 / 0 进行中。
> 上一版快照（`7 已完成 / 4 进行中 / 8 待开始`）与任务表实际状态**三重不符**——审定发现②的直接证据。

> **T1.2 / T1.3 已由 verifier-dev 回填（v1.1 定稿）**：核验器 6 个 check id + `blocking` + schema `/2`；
> `regen.sh` 改为**查 KO**判生成成败、默认允许脏 `.ioc`（失败从备份恢复）、不拦不改 `AskForMigrate`。
> 证据：`docs/logs/phase1/t1.2-pytest.log`（v1.1 轮 61 passed）、`docs/logs/phase1/t1.2-pytest-v1.2-recheck.log`（v1.2 轮 74 passed）、`docs/logs/phase1/regen-v1.1-*/`；
> 契约：`docs/reports/t1.2-verifier-contract.md`。**GATE-1.1 已按"视为通过"记录（见 §2，未走演示流程）。**
> `pins_present`（引脚级第 7 项）已在 **v1.2** 落地：未改动的 G474 基线 + `--expect-pins PB0=GPIO_Output` → **fail**（外设级全 pass），`PC13=GPIO_Output` → pass。S1 建议在 `regen.sh` 加 `--expect-pins`，并用外部断言做交叉验证。

GitHub remote：`D5 = 是`，仓址 `https://github.com/LeonhardtHUST/cubeone-mcp`（Public），由 T1.1 创建。

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
| 2026-11-03 | 采纳 S3 实测（`scenario-tester`）：`log_cannot_map` 由"无真实样本"改为**有 1 例可复现实例**（`s3b-regen/cubemx-generate.log:321`，触发路径是手改 `.ioc`；CLI `set pin` 路径在命令层 `KO`、不可达）；补 S3 两组证据对照（`s3b` 响亮 / `s3b2` 静默）；`--ioc` 提醒限定为"直调时"，`regen.sh` 自动传；§0.4 理由①由"若带此类前缀"升级为**实测**（真实 `Cannot map` 行级别是 `[INFO]`，必被 `NOISE_RE` 过滤） | skill-author |
| 2026-11-03 | **M0 治理回填（R-A2）**：T3.5 由 `待开始` 改 `已完成`（三 tag 逐条核对 + `v0.6.1` release 缺口按 D33 补发）；§0.1 增设第六种状态 `已关闭`（裁决终止 ≠ 挂起，快照与校验脚本统一口径）；§4 快照按任务表真实值重算（17/0/6/1/1）并加"禁止手写"注；GATE-0 / 1.1 / 1.2 / 3.1 状态修正；新增 **§0.4 角色登记**（3 个计划外角色 + 8 个计划角色出场情况） | software-engineer |
| 2026-11-03 | **M0 证据指针修正（R-A4 / R-A5）**：重跑并归档 `docs/logs/phase1/t1.2-pytest-v1.2-recheck.log`（**74 passed**），T1.2 行消掉无对应证据的"69"（改为 v1.1 轮 61 / v1.2 轮 74 双口径）；T0.4 行统一为 **1481 行 / sha256 `43e0641c…`**（929 行 / `4fb474e9…` 降为历史注记）；T1.6 构建时长统一 **12.06 s**（10.95 s 为复跑值，不再复用）；T3.4 关闭结论落盘 `docs/evaluations/2026-11-03-t3.4-closure.md`（该目录不再是空壳） | software-engineer |
| 2026-11-03 | **M1 接缝修复批次开工并完成代码**：`lib/server.mjs` R-B1/B2/B3/B4/B6 + R-D1 导出；`tools/npm_mcp_handshake.mjs` 增 T10；`ci.yml` 增 `node` job；`package.json`/`SKILL.md`/frontmatter 三处 bump **0.6.2**；新增 §1「M1 修复批次」表（不计入 25 条快照）。**两条只有真跑才发现的缺陷已修正**：`node --test <目录>` 在 Node 18/22 行为相反（CI 改 glob）、`package-lock.json` 被 `.gitignore` 忽略（CI 不能 `npm ci`）。**R-B2 的 cp936 分支在本机不可达**（ANSI 代码页已是 cp65001），已在表中如实标注为"验证对象不可达"而非"纸面修复"。⚠️ 未打 tag、未 push | software-engineer |
| 2026-11-03 | **R-C1 第一步（0.6.2 随 M1）落地**：`CUBEONE_REQUIRE_ROOTS` opt-in 严格模式（未配白名单则启动退出 1，**默认行为不变**）；`envFootnote()` 与启动横幅的「未设置」改为能读出后果的措辞；README 新增「安全默认值」节、`SKILL.md` §0 加同源警告。五组合实测：默认→启动、`=1`+空→exit 1、`=true`+有→启动、`=YES`+空→exit 1、`=0`→启动 | software-engineer |
| 2026-11-03 | **M1 收口（0.6.2 发布）**：tag `v0.6.2`（`b8f1857`）→ GitHub Release（正文入库 `docs/releases/2026-11-03-v0.6.2.md`）→ npm `cubeone-mcp@0.6.2`（Trusted Publisher，`14:04:53Z`）→ 本表回填。GATE-3.1 首次正规执行：22:00 出示 CI 绿 + 四连验 + 变更摘要，用户裁定「授权全链发版」。**发布正文入库 `docs/releases/` 是新增约定**：正文不再只存在于 GitHub 页面 | lead |
| 2026-11-03 | **v0.6.1 Release 补发 + 一次假红记账**：补发成功（三证补齐）；触发 `Publish npm` run `41650583470` 失败——`release` 事件的 workflow 取自 tag 点 `8f99fb0`，早于幂等守卫提交 `f830b55`，旧版 `::error` 判红。**保留红灯不删 Release**，根因与可推广教训记入 D33 §33.4.1 | lead |
