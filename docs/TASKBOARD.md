# 任务看板（TASKBOARD）— 唯一状态真源

> **owner：`skill-author`**（建板与格式维护）。**状态列的更新权归各任务 Owner**，别人不得代改。
> 上游：`docs/2026-11-03-agent-team-plan.md`（下称"计划"）、`docs/2026-11-03-execution-research.md`（下称"调研报告"）。
> 交接协议见计划 §5.2：新 Agent 入场按 `本文件` → `docs/DECISIONS.md` → 计划对应 Phase 节 的顺序读，即可无缝接手。

最后更新：2026-11-04 · 更新者：software-engineer（**R1 批次（已完成）**：三项裁决落地。① `scripts/regen.sh` 生成前读 `ProjectManager.AskForMigrate` 并**按可判定性分两级**（D36①）——`true` **且** 版本戳落后于锁定基线 → **4 行 `[regen][warn]`**（因果 + **可直接复制执行**的置 `false` 命令与真实路径 + GUI 迁移替代路径 + 指向 P1）；`true` **但** 版本戳一致 → **一行 `[regen]` info**（不喊，也不沉默：基线是**常量**，不代表你机器上的版本）；`false` / 读不到 → **什么都不打**。**为什么分两级**：一律 warn 会因"每次 `project generate` 都写回 true"而每次刷 4 行黄字，真风险被淹（**警告常态化 = 没有警告**）；只在落后时输出又会因基线是常量而在「工程戳 6.18.1 / 本机装 6.19.0」这类错配上**静默掉会挂死的那一例**——两个极端都已写进 D36① 的否决记录。新增 **opt-in** `--fail-fast-on-migrate`（**只看该键、不叠加版本戳判断**；置位则打完提示后退 `2`），默认关闭；生成**超时**（`RC=124`）后按日志**末行附近**（尾部 10 个非空行，且窗口内无 `Change cursor`/`Initializing MCU`/`End LoadConfig`）是否停在 `Begin LoadConfig()` 做**定向诊断**——命中才判为迁移对话框挂死（"这不是你的工程坏了" + 两条处置 + 指向 P1），**未命中只报超时并明确写"不能归因"**（避免"看起来有解释其实没解释"）。② `references/regen-exit-codes.md` 补 §4.1（告警/开关语义表 + 为什么不直接退 2）、§4.2（超时诊断两种形态对照表）、§4.3，退出码 `2` 的来源列新增该开关。③ `references/pitfalls.md` P1 末尾"待批准项"改**已定结论**，判据段同步。④ `docs/DECISIONS.md` 追加 **D36**（① 告警策略 / ② 不做时钟参数判据 / ③ 核验器 2.0 维持不排期，每条含决定·理由·代价·什么情况下重新考虑）。⑤ `SKILL.md` 的 regen 用法、退出码表、P1 索引与 §6.1 同步。**未动** `lib/`、`tests/`、`tools/`、`.github/`、`scripts/*.py`（本轮不碰 Python 脚本行为）。批次表 10 条、合计 35 ｜ **上一版**：R0.7.2 补丁发版（**已完成**，三证齐全：tag `v0.7.2` → Release → npm `0.7.2`；版本三处 bump + README 版本表两处 + `docs/releases/2026-11-04-v0.7.2.md` 成文，两处**用户可见缺陷**按「症状 / 谁会遇到 / 怎么验证已修」三段写全，判据语义变更（`Core/Src/*.c` 多文件扫描 + 无 project-root 时降 warn）单列一节；**本批不含任何逻辑改动**）

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
| `software-engineer` | **T0.4 冒烟实现**（`tools/mcp_smoke.py`，1481 行）：写权限 `tools/` 下新建冒烟脚本；**不含** `scripts/`、`tests/`、`SKILL.md`。**M0 回填期追加一段临时授权**：经 lead 转派，本角色获 `docs/DECISIONS.md` / `docs/TASKBOARD.md` / `README.md` 的文档写权（任务 R-G1/R-A2/R-A3/R-A4/R-A5），改动留工作区由 lead 统一提交。**M1–M3 批次再授权**（经 lead 逐批派发）：`lib/server.mjs`、`scripts/ioc_backup.py`、`scripts/verify_generation.py`、`scripts/ioc_field.py`、`scripts/regen.sh`、`tools/check_taskboard.py`、`.github/workflows/ci.yml`、`references/`、`docs/DECISIONS.md`、`docs/TASKBOARD.md`、`README.md`；**始终不含** `tests/`、`tools/npm_mcp_handshake.mjs`、`SKILL.md` 的版本号、`package.json` 的版本号（这三处归 QA / lead） | `platform-lead` |
| `software-engineer-2` | **M2/M3 实现副手**（本角色入册见 D34 §34.2(2)）：授权面与 `software-engineer` 的 M1–M3 批同级，按 lead 逐批派发执行；M2 负责 R-C1②/R-C2/R-C3/R-C4 与 0.7.0 文档 bump，M3 负责 R-E1–R-E4。**禁止**改 `tests/`、`tools/npm_mcp_handshake.mjs`、`testbeds/`，禁止 `git add/commit/push/tag`（提交权归 lead） | `platform-lead` |
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

### M1 修复批次（实为 M1–M3 整改批次；段标签沿用旧名，脚本按它统计）

> 本批次表由 2026-11-03 修复计划新增，**计入 §4 快照但单列一段**（Phase 0–3 的 25 条口径不变）。
> 表名沿革：M1 期间叫「M1 修复批次」，自 M2/M3 起本表实为**整改批次表**；§4 快照仍沿用
> `M1 修复批次` 作为段标签，`tools/check_taskboard.py` 的 `SECTION_LABELS` 按它匹配
> ——**改标签必须同时改脚本，否则脚本会判「无法归入已知分段」并 exit 1**（这条机制自测过）。
> ⚠️ 本表的行**不得被空行拆断**：Markdown 里空行之后的一行 `|` 不再属于原表，
> 校验脚本会把它当成表外内容而漏计（M2 行曾因此漏统计，M3 首跑抓到并已修）。
> **段标签沿用「M1 修复批次」是历史原因（本段首行是 M1）**：新增批次请**继续在本表追加行**，
> 不要另起一段——另起一段会让 §4 快照与脚本统计**同时多一段**（`SECTION_LABELS` 里没有它，
> 脚本会直接判「无法归入已知分段」并 exit 1）。要真正改名需三处联动：本表标题 +
> §4 快照行标签 + 脚本 `SECTION_LABELS`。

| 任务ID | 任务 | Owner | 依赖 | 状态 | L 等级 | 证据链接 |
|---|---|---|---|---|---|---|
| M1 | 接缝修复 R-B1–R-B6 + Node 测试基建 R-D1/R-D2 + R-C1 第一步 + 版本 bump **0.6.2** | software-engineer（实现）/ software-qa-engineer（单测） | M0（D33 在册） | 已完成（三证齐全） | L2（本地四连验 + CI 全绿） | **发布三证（2026-11-03 22:04）**：tag `v0.6.2`（`b8f1857`，三处版本同值 0.6.2）→ GitHub Release `cubeone-mcp v0.6.2`（正文入库 `docs/releases/2026-11-03-v0.6.2.md`）→ npm `cubeone-mcp@0.6.2`（`2026-11-03T14:04:53Z`，Trusted Publisher，17 files / 82.1 kB）→ 本行回填。**CI**：run `41649454775` 全绿 6 job（pytest 3.11/3.13 各 **74 passed**；node 18/20/22 各 **31 passed / 1 skipped**，skip 为仅 win32 有意义的大小写用例；脚本检查绿）。**`lib/server.mjs` 六项**：R-B1 退出码白名单（含 `[<tool>][not-found]` 域内结论例外 + Traceback 优先，计划 §7 风险条要求）、R-B2 子进程 `PYTHONIOENCODING=utf-8`、R-B3 `validateArgs`（required/enum/类型/条件必填）、R-B4 `--` 分隔 + `--json-out` 前置到 `--` 之前、R-B6 未知工具动态清单、R-D1 七个纯函数导出；**另含 R-C1①** `CUBEONE_REQUIRE_ROOTS` opt-in 严格模式（五组合实测：默认→启动 / `=1`+空→exit1 / `=true`+有→启动 / `=YES`+空→exit1 / `=0`→启动）。**`tests/node/server.test.mjs`（QA 写）32 例** → `node --test tests/node/*.test.mjs` **32/32**（Node 22.22.2 与 **18.20.8** 双档）。**CI**：`.github/workflows/ci.yml` 新增 `node` job，**三档矩阵 18/20/22**。**冒烟**：`tools/npm_mcp_handshake.mjs` 新增 T10 → `docs/logs/phase1/npm-mcp/handshake.log`（**11 PASS**）。**pytest 74 passed**。**⚠️ R-B2 的验证边界（如实记录，勿读成"纸面修复"）**：本机 ANSI 代码页 = **cp65001(UTF-8)**，且运行环境已注入 `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1` / `LC_ALL=C.UTF-8`，三组对照（摘 `PYTHONIOENCODING`、`PYTHONUTF8=0`、连 `LANG/LC_ALL` 一起摘）**都造不出 cp936 分支** ⇒ 属**验证对象在本机不可达**，不是没验证；T10 保留作回归守卫，在真实 cp936 机器上才体现。**两条只有真跑才发现的缺陷**：① `node --test <目录>` 在 Node 18 展开、Node 22(Windows) 当模块加载报 `MODULE_NOT_FOUND` ⇒ 命令一律用 glob 形式（计划书 R-D1/R-D2/收口节已同步更正）；② `package-lock.json` 被 `.gitignore:49` 忽略（不入库）⇒ CI 不能用 `npm ci`（缺 lock 必红），改 `npm install` 且不开 `cache: npm`（依赖为精确版本 `1.32.2`，无 semver 漂移） |
| M2 | 安全加固 **R-C1②**（默认 fail-closed + `CUBEONE_ALLOW_NO_ROOTS` 逃生门）/ **R-C2**（`realpath` 物理路径）/ **R-C3**（restore 原子化 + 备份完整性摘要）/ **R-C4**（`report_md` 披露）+ 版本 bump **0.7.0（BREAKING）** | software-engineer（实现）/ software-qa-engineer（测试基线） | M1（0.6.2 已收口） | 已完成（三证齐全） | L2（本地三验 + CI 全绿） | **发布三证（2026-11-03 16:09Z / 次日 00:09 本地）**：tag `v0.7.0`（`64a9a01`，三处版本同值 0.7.0）→ GitHub Release `cubeone-mcp v0.7.0`（正文入库 `docs/releases/2026-11-03-v0.7.0.md`）→ npm `cubeone-mcp@0.7.0`（`dist-tags.latest = 0.7.0`，Trusted Publisher）→ 本行回填。CI run `41670927604` 六 job 全绿；**其中 lint job 的看板校验首次以 `fetch-depth: 0` 真实读到 tag**（note 行给出 `v0.6.1, v0.6.2, v0.7.0`，判据③ 未降级）。 `lib/server.mjs`：`envTruthy` 统一真值解析（`REQUIRE_ROOTS`/`ALLOW_NO_ROOTS` 共用）、`checkPath` 空白名单→`reason:"no-roots"`、`physical()` 逐级上溯最近存在的祖先（防 junction 绕出且不误拒未生成文件）、拒绝文案分「无白名单」与「越界（附物理落点）」两种；`scripts/ioc_backup.py`：sidecar `<name>.ioc.bak.sha256`、restore 两阶段（先全量校验再逐个 `os.replace`）、不一致 rc=2 + `[ioc_backup][integrity]`；文档：README/SKILL 的 BREAKING 迁移说明、`references/regen-exit-codes.md` 补退出码 2 的第二来源。**验证**：`node --test tests/node/*.test.mjs` **37 passed / 0 skipped**（新增 2-5a/b/c 逃生门真值表、2-6 junction 绕出、2-7 未生成文件不误拒、5b-1 无白名单被拒）；`pytest` **77 passed**（restore 三例）；`npm_mcp_handshake.mjs` **12/12 PASS**（新增 T11）；CI run `41662550646` 六 job 全绿。**收口缺口**：tag `v0.7.0` 已在本地打好（指向 `64a9a01`），**尚未 push** ⇒ Release 与 npm 两证未产出，按 D33 §33.2 记为「进行中」，不得提前写「已完成」 |
| M3 | 机制固化 **R-E1**（看板一致性校验脚本 + CI 接入）/ **R-E2**（DECISIONS **D34** 治理元规则）/ **R-E3**（弃用字段口径统一为 v2.0 移除）/ **R-E4**（F7/F8/F11/F12 + README 环境注记）。**不发版** | software-engineer | M1（与 M2 并行） | 已完成 | L2（脚本自测 + pytest/node/handshake 三连回归） | `tools/check_taskboard.py`（新增，纯标准库，三组判据：快照↔任务表逐段逐状态 + 小计/合计自算、证据路径存在性（跳过 `docs/logs/` 并计数、剥 `:行号`、跳过通配符）、发布一致性（tag 含 `v0.6.*`/`v0.7.*` 时 T3.5 不得「待开始」））；`.github/workflows/ci.yml` 的 lint job 增一步（放在"脚本入口冒烟"之前）；`docs/DECISIONS.md` **D34**（五条：形态变更元规则 / 角色入册协议 / L 等级降级须批准 / 节奏条款 / 模板化）；`scripts/verify_generation.py` 弃用口径改「v1.x 保留兼容、schema `/2` 起读 `inputs.*`、v2.0 移除」+ docstring 补第 7 项 `pins_present`；`scripts/ioc_field.py` get 区分「多行歧义（附行号）」与「不存在」；`tools/mcp_smoke.py` 归属注释；`scripts/regen.sh:24` 本机 PATH 注释；README FAQ 增 pytest `--basetemp` 注记。**脚本自测**：本仓看板 `exit 0`；副本故意改坏一处 → `exit 1` 并指名「§4 快照 / Phase 1 / 已完成：任务表 9 / 快照 8」。**首跑即抓到两处真缺陷**：M2 行被空行拆出表外（漏统计）、§4 快照缺「阻塞」列（六态中有一态无处可写），均已修 |
| C0 | **修正与发版**：重写本包真正的注册指南（补 0.7.0 fail-closed + 注册后自检）、换包内指南（两本都带、主指南为 `npm-publish-and-codebuddy`）、`mcp-registration.md` 加防误读头、版本 bump **0.7.1**（带出 M3 的 `ioc_field` 1.1.0 与 5 个未发版 commit） | software-engineer | — | **已完成**（三证齐全） | L2（pytest 77 / node 37 / handshake 12 / 看板 rc=0；发版三证待收口） | 待发版收口（C0.2：tag `v0.7.1` → GitHub Release → npm 0.7.1 → 三证回填本行）。已落地：`docs/guides/npm-publish-and-codebuddy.md` 重写（顶部 0.7.0 BREAKING 区块、env 表 3→5 行、白名单口径由"盘根"收紧为"只给工程目录"、新增 §2 注册后自检、反直觉点补第 9 条、文件头归属说明）；`docs/guides/mcp-registration.md` 加防误读 blockquote；`package.json` 的 `version` 与 `files`（补入主指南）；`SKILL.md` version/状态行；`README.md` 版本表两行；`docs/releases/2026-11-04-v0.7.1.md` **审核发现（触发本批）**：0.7.0 默认拒绝上线但**没写进任何随包指南**，且包里那本讲的是两个外部 server ⇒ 用户按包内指南配完必被拦、且无从自查，属**交付缺口**，本版补齐 **三证（2026-11-04 00:5x）**：tag `v0.7.1`（`5ecc0b7`）→ Release （正文 `docs/releases/2026-11-04-v0.7.1.md`）→ npm `0.7.1`（`dist-tags.latest`，18 files；包内已含两本指南，主指南为 `npm-publish-and-codebuddy.md`）。CI run `41677753063` 绿。 |
| C1 | **门禁完备**：Windows CI job（补 win32 分支的大小写归一 / junction / `path.delimiter` 覆盖）+ 冒烟 fixtures 化进 CI（handshake 不再依赖 gitignored 的 testbeds） | software-engineer | C0 | **已完成** | L2（本地等价校验；CI 实跑待网络恢复） | **代码已落地**：`ci.yml` 新增 `windows` job（windows-latest 单 job，pytest 3.13 + Node 22；**Node 步骤显式 `shell: bash`**——Windows 默认 pwsh 不展开 glob，会把 `tests/node/*.test.mjs` 当字面量传给 node 报 MODULE_NOT_FOUND，这是 M1 真机踩过的形态）；`tools/npm_mcp_handshake.mjs` 改为三计数（pass/fail/**skip**）+ 新增 `--require-materials`（SKIP 即失败）与 `--ci`（不落盘证据）；素材定位顺序 `testbeds/ → tests/fixtures/e2e/`；新建 `tests/fixtures/e2e/board.ioc`（取 `ioc_g474_template.txt`，含 `MxCube.Version=6.18.1`）；ubuntu node 22 档接入 `--ci` 冒烟。**两处为进 CI 而修的真缺陷**：① T9 原写死 `C:\Windows\win.ini`，在 Linux 上会被 resolve 到**仓内**、变成"文件不存在"而非"越界"（只在 Windows 成立的用例）→ 改为"仓库根上一级"的跨平台界外路径；② T6 **有意保留 SKIP**：需 CubeMX 原始日志 + 真实工程 `main.c`/`.mxproject` 三者自洽，造假日素材极易拼出 `verdict=pass` 的假绿（取舍写进脚本注释与本表）。**实测形态**：本机 `--require-materials` 12/12；模拟无 testbeds 环境（去 `testbeds/`、去 `docs/logs/` 的副本）→ `pass=11 fail=0 skip=1`，`SKIPPED` 行点名 T6。**待收口**：CI 实跑绿灯（网络不通，push 不可能，如实记「进行中」）。**Windows job 首跑即抓到真缺陷并已修（run `41682180849`）**：`scripts/` 三个脚本的 stdout 里有 `→` `←` `·` `…`，GitHub Windows runner 控制台是 **cp1252**，`print` 抛 `UnicodeEncodeError` → 脚本 rc=1 → `test_ioc_backup.py` 三条用例全红。**这不是 CI 环境怪、也不是测试问题**：CLI 通道（不经 MCP、直接 `python scripts/xxx.py`）在英文 Windows 上必崩，MCP 通道只因封装层注入 `PYTHONIOENCODING=utf-8` 才幸免，本机 UTF-8 代码页永远暴露不出来 —— **这正是加 Windows CI 的直接产出**（呼应 T3.1 的"纯本地开发永远发现不了这类缺陷"）。修法（**两版，第二版才定稿**）：三个脚本各加 `_harden_console_streams()`（`main()` 第一句、argparse 之前）。第一版「只把 errors 改成 `backslashreplace`」是**半对**——管道编码被污染成 cp1252 时中文整体退化成 `\u7f3a`，不崩但读不了，CI 因此第二次红（断言 `"缺少完整性摘要" in stdout` 失败）。**定稿按输出目标分流**：非 TTY（管道/重定向，即 `regen.sh` 重定向与 MCP 封装层抓管道）**强制 `encoding="utf-8"`**——机器消费路径，UTF-8 唯一无歧义、封装层本来就按 UTF-8 解码；TTY **保留控制台自身编码**（中文 Windows=cp936，中文正常）只换 errors（cp1252 遇到 `→` 转义成 `\u2192` 而不是崩）。**管道要可解析、控制台要可阅读**，两者不能一条规则通吃。**不删中文、不把 `→` 换成 `->`**（改文案只治一处）。回归用例 `tests/test_console_encoding.py`（**10 例**）：管道路径用 `PYTHONIOENCODING=cp1252|ascii|cp936` + `PYTHONUTF8=0` 污染，断言 rc 正确、无 traceback、**中文与 `→` 原样可读**（含 CI 上刚红的那条 `缺少完整性摘要`），并防退化成 `\uXXXX`；TTY/管道**分支选择**用行为桩机械验证（`reconfigure` 入参逐字比对）；TTY 的"视觉正确"无自动回归，注释里写明改动后须人工在 cp936 控制台跑一次。**前后对照实测**：移除加固的副本在 `PYTHONIOENCODING=ascii` 下 `UnicodeEncodeError: 'ascii' codec can't encode character '\u2192'` + rc=1；加固后同一工程 rc=0、输出 `\u2192` **CI 证据（2026-11-04 00:48Z）**：run `41749543653` 七 job 全绿——`windows` job 首跑抓到 charmap 崩溃（cp1252 控制台打印 `→` 抛 UnicodeEncodeError），修法两版才定：只换 errors 会把中文整体转义（读不了），最终改为 **TTY 感知**（管道强制 UTF-8、控制台保留原编码 + backslashreplace）；Node 22 档冒烟 `pass=11 skip=1`（T6 缺素材，显式点名）。 |
| C2 | **机械化**：`package-lock.json` 入库并改回 `npm ci`、Python 覆盖率底线、Node 覆盖率报告、版本轴校验脚本 `tools/check_release.py`、发布 SOP（D35）成文 | software-engineer | — | **已完成** | L2（脚本自测 + lock/覆盖率本地实测；CI 实跑待网络） | **已落地**：① `.gitignore` 删 `package-lock.json` 行（并加注释说明为何入库）+ 补 `.coverage*`/`coverage.xml`/`htmlcov/` 忽略；lock 重新生成使根 version 对齐 **0.7.1**（原为 0.6.2 遗留），`npm ci --dry-run` 通过、`@modelcontextprotocol/sdk` 仍 **1.32.2**；② `ci.yml` 的 node job（ubuntu + windows）`npm install` → **`npm ci`** + `cache: npm`，旧注释改写为"lock 已入库（C2.1），可复现 + 缓存命中"；③ pytest job 装 `pytest-cov==7.0.0` 并加 `--cov=scripts --cov-report=term-missing:skip-covered --cov-fail-under=36`：**基线实测 37%**（3.11.9 与 3.13.14 两档同值；ioc_backup 29% / ioc_field 40% / verify_generation 39%），底线取基线 -1pp，注释写明"只防回退、不追指标"且该数字**低估**真实覆盖面（多数用例用子进程调脚本）；④ 新增 `tools/check_release.py`（纯标准库，判据：最新 tag == package.json == SKILL frontmatter == README 两处；`docs/releases/` 正文存在；领先提交数只提醒；`--network` 查 npm dist-tags 失败仅 warning；`--tag`/`--repo-root` 支持自测）；⑤ `docs/DECISIONS.md` 追加 **D35** 发布 SOP（9 步流水线 + 两句"不可交换"的关系 + 两个已踩坑）；⑥ README 增**依赖边界声明**（`scripts/` 运行时零依赖，pytest/pytest-cov 属测试工具链）。**三坏样本自测**：改 package.json → 判据①红；删发布正文 → 判据②红；`--tag v0.9.9` → ①+② 双红。**待收口**：CI 实跑（`npm ci` 命中缓存 + 覆盖率步骤） **已完成并随 C1 同批验证**（lock 入库 + `npm ci`/cache 生效；pytest-cov 基线 37%，底线 36；`check_release.py` 三判据；D35 SOP）。 |
| C3 | **硬件段预演**：S4 前四段（改配置→生成→核验→构建）无板预演 + GATE-2.0 接板清单成文 + T3.3 占位说明 | software-engineer | CubeMX 本机可用 | 已完成 | **L3**（构建）+ **L2**（核验执行了但结论不可用）——**非 L4** | `docs/reports/s4-dryrun-g474_01_gpio.md`（预演正文）+ `docs/guides/gate-2.0-checklist.md`（接板清单）+ `SKILL.md` §6.1/§6.2（Phase 2 状态骨架与两个接板坑）。**四段实测**：① 改 `PC13.PinState SET→RESET`，`.ioc` diff 1 行（L2）；② CubeMX 真生成 **62 s**、退出码 0、**无 KO**、生成物只动 `Core/Src/gpio.c` + `main.c`（L3）；③ 核验 **verdict=FAIL errors=2** —— `main_init_present` / `pins_present` 两条 fail **全是结构性误判**（工程 `CoupleFile=true`，`MX_GPIO_Init` 定义在 `gpio.c:42`、时钟使能在 `gpio.c:48`，`main.c:90` 只有调用；核验器只扫 `--main-c`）⇒ 判据执行了但结论不可用（L2）；④ `pio run` **SUCCESS**：**FLASH 5104 B / 512 KB（0.97%）· RAM 1664 B / 128 KB（1.27%）**（`--print-memory-usage` 口径；PIO 自带 size 的 4624/124 不计 stack/heap，P3 现场实例）（L3）。**三个发现**：**F1** 核验器在「每外设一对 `.c/.h`」工程上会把正确生成判成"外设被静默丢弃"（假失败，比漏报更伤人，修复需改 `scripts/`，本批无授权）；**F2** 重新生成静默改掉 `PLLN 100→85`（SYSCLK 推算 200 MHz→170 MHz，**原 `main.c` 与自身 `.ioc` 本就不一致**，200 MHz 超 G474 上限），7 项核验一条都看不见 ⇒ 接板前必须逐条解释 diff；**F3** `AskForMigrate` 会被 `project generate` **写回 `true`**（推翻既有 P1 结论："纯 generate 不写回"），且版本戳更旧时 `-q` 生成会**挂死 300 s**（实测停在 `Begin LoadConfig()`）。**F1/F3 已于同日修复**（见 §5 最后一条）。**原仓只读**：改前改后 `Project.ioc` sha256 均为 `9705d211…b47b`。证据日志：原始日志落 `docs/logs/phase4/`（该目录自 2026-11-04 起被 `.gitignore:79` 忽略，**仅本地**）；`docs/logs/phase0`、`docs/logs/phase1` 的历史日志**仍入库**（78 个 tracked 文件，见 `git ls-files docs/logs`） |
| C4 | **可维护性**：CONTRIBUTING 贡献入口、提交模板、文档导航/索引页 | software-engineer | — | 已完成 | L0（纯文档） | `CONTRIBUTING.md`（新建：三层测试及各自期望尾行、`type(scope): 中文简述（Lx）` 提交规范与硬性禁止、**单写者原则**表、**依赖边界**声明"scripts 运行时零依赖 / pytest-cov 属测试工具链"、L0–L5 指向 README、文档导航、常见失败处置）；`.github/ISSUE_TEMPLATE/bug_report.md` + `feature_request.md`（bug 模板带脱敏提醒与"先排除四件事"清单；feature 模板要求写**可机器判定的判据**并对非 GPIO 需求预警）+ `.github/PULL_REQUEST_TEMPLATE.md`（直接印上三条测试尾行 + L 等级声明 + 关联看板行 + 九条勾选清单）；`docs/README.md`（新建：一页索引，状态真源 / 计划 / 报告 / 发布台账 / 指南各一行"什么时候看"）；`docs/releases/README.md`（新建：**版本 × 内容 × 三证**对照表，v0.1.0 / v0.1.1 / 0.6.0 / v0.6.1 / v0.6.2 / v0.7.0 / v0.7.1 逐行列全，标注 0.6.1 正文为事后补发、0.6.0 无 tag 无 Release 属"发了但未收口"）；`README.md` 顶部与文档索引加 `CONTRIBUTING.md` / `docs/README.md` 链接。相对链接已逐条校验（4 个新页 + README 全部可达） |
| R0.7.2 | **补丁发版 0.7.2**：版本三处 bump（`package.json` / `SKILL.md` frontmatter / 状态行）+ `README.md` 版本表两处同步；发布正文 `docs/releases/2026-11-04-v0.7.2.md` 成文（两处用户可见缺陷修复按「症状 / 谁会遇到 / 怎么验证已修」三段写，判据语义变更（`CoupleFile` 多文件扫描）**单列一节**并说明"为什么不降级成永远 warn"）；看板回填。**不含任何逻辑改动** | software-engineer | C0–C4 | **已完成** | L2（pytest 94 / node 37 / 冒烟 12 / 看板 rc=0；`check_release.py` 在打 tag 前**预期 FAIL**，见正文发布时序） | 待发版收口（tag `v0.7.2` → GitHub Release → npm `0.7.2` → 三证回填本行）。已落地：`package.json` 的 `version`、`SKILL.md` version 与状态行、`README.md` 版本表两处、`docs/releases/2026-11-04-v0.7.2.md`。**未动**：`lib/`、`scripts/`、`tests/`、`tools/`、`.github/`、`references/` **三证（2026-11-04 09:33Z）**：tag `v0.7.2`（`d002d0d`）→ Release → npm `cubeone-mcp@0.7.2`（官方 registry `dist-tags.latest=0.7.2`，18 files）。CI run `41754212053` 七 job 全绿。 **注意**：本机 `npm view` 读的是 npmmirror 镜像，镜像只同步到 0.7.0/0.7.1，核证须用 `--registry=https://registry.npmjs.org/`。 |
| R1 | **`AskForMigrate` 分级提示与超时诊断（D36①）**：`regen.sh` 生成前分级输出 + opt-in `--fail-fast-on-migrate` + 超时后按日志形态定向诊断；`references/regen-exit-codes.md` §4.1–§4.3、`references/pitfalls.md` P1、`SKILL.md` 三处同步；`docs/DECISIONS.md` 追加 **D36**（三项裁决）。**不发版** | software-engineer | R0.7.2（v0.7.2 已收口） | **已完成** | L1（`bash -n` + 路径真跑）+ L2（命令级真跑；超时用假 java 返 `124` 模拟，**未真等 300 s**） | **设计**：`true` + 版本戳**落后** → 4 行 `[regen][warn]`（含可直接复制的 `ioc_field set … false`）；`true` + 版本戳**一致** → 一行 `info`（不喊也不沉默）；`false`/读不到 → 静默。**为什么分级**：一律 warn 会因「每次生成都写回 true」而每次刷黄、真风险被淹；一律只在落后时输出又会因基线是**常量**而在错配（工程戳 6.18.1 / 本机 6.19.0）时**静默掉会挂死的那一例**——两个极端都记进 D36① 的否决记录。`--fail-fast-on-migrate` **只看该键**（不叠加版本戳判断），置位则退 `2`。超时（`RC=124`）按日志**尾部 10 个非空行**判定：命中 `Begin LoadConfig` 且窗口内无 `Change cursor`/`Initializing MCU`/`End LoadConfig` → 定向诊断（两条处置）；未命中 → **只报超时并明写「不能归因」**（反向对照：回放 638 行真实成功日志未被误判）。**自验**：`bash -n` OK；三档路径各真跑；`--dry-run` 也触发前置检查；`pytest` **94 passed**、`node` **37/37**、`check_taskboard` / `check_release` 均 `rc=0`。**过程中两条用例曾断言 D19 旧行为**（`true`+版本一致→静默、且要求出现已被 P1 推翻的「无实测卡死证据」字样），已同批按三档重写（`…_is_info_only_when_version_matches` / `…_warns_when_version_is_older`）。|
| R2 | **接板首日（X-Pulse）**：真板走「改配置 → 生成 → 核验 → 构建 → 烧录 → 回读 → 目视」，并把现场发现回写进 `docs/guides/gate-2.0-checklist.md` | software-engineer | C3（无板预演）、GATE-2.0 | **已完成** | **L5**（全链：配置改动 → 生成 → G1 PASS → 构建 → 烧录 `Verified OK` → 寄存器回读 → 目视一致） | **探测**：`STLINK V2J35S7`（`0483:3748`）· 3.24 V · `DPIDR 0x2ba01477` · `IDCODE 0x20036469`（`DEV_ID 0x469`）。**第一次烧 C3 产物（NUEDC 工程，PC13/14/15）**：`Verified OK`、回读 `MODER=0x57FFFF00`／`ODR=0x0000C000` ⇒ 配置确实落到硬件，但**板上无灯**——查出实板为 **X-Pulse**：RGB 在 **PC0/PC1/PC2、共阳低电平点亮**，**PC13 只到排针无 LED**（F4）。**改走实板工程**：从 X-Pulse 模板建 `testbeds/xpulse-min`（原仓 md5 前后一致），`set pin PC2 GPIO_Output` → `.ioc` 变更（`Mcu.PinsNb 4→5`）→ 生成（`DIE469`，`MX_GPIO_Init` 内 `Pin=LED_RED_Pin|GPIO_PIN_2` 且初始 `GPIO_PIN_RESET`）→ **G1 `verdict=PASS` 7/7**（`pins_present` 命中 `PC2.Signal=GPIO_Output`）→ 构建 SUCCESS（RAM 44 B / Flash **3168 B**）。**烧录**：首次 `Error: open failed`（`VID_0483` 设备数=0，探针物理掉线）→ 插回后 `upload` **`Verified OK`**。**回读**：`MODER=0xF7FFFFDF`（PC2=01 推挽输出）、`ODR=0x00000000`（**bit2=0** ⇒ PC2 低）、`PC=0x08000D08`（在 Flash 运行）。**目视**：**红灯亮、绿/蓝灭**，与寄存器一致。⇒ 工具改的配置变成了可见现象，两条独立判据互证。**产出**：`docs/reports/phase2-bringup-2026-11-04.md`（含 F4 引脚须对板 / F5 300 s 超时偏紧 / F6 超时未误归因）；`gate-2.0-checklist.md` §1 增「引脚与实板一致」、§1.1 openocd 探测配方、§2.2.1 超时指引、§2.4 `set pin` 写盘时机 |

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
| **GATE-3.1** | 发布前 | GATE-1.2（含 T3.1–T3.3） | ✅ **已通过**（0.6.2 首次正规执行；历史三次为事后补审） | **2026-11-03 22:00 向用户出示证据并取得放行**：CI 全绿（run `41649454775`）+ 本地四连验（pytest 74 / node 32 / handshake 11 / CI 等价 7 项）+ 变更摘要（8 个 commit）+ 已知限制清单，用户裁定「授权全链发版」。随后 tag → Release → npm → 本看板回填四证齐全。**历史缺口**：`v0.1.0`/`v0.1.1`/`v0.6.1` 三次 tag 均未过本关卡即打出，npm `0.6.0`/`0.6.1` 亦未经关卡——已按 D33 §33.2 记为"事后补审"，不追认其合规性。**第二次正规执行（0.7.0，2026-11-03 23:17 本地）**：因 M2 属 BREAKING，单独向用户出示「六 job 全绿 + 本地三验 37/77/12 + 迁移说明 + tag 内容边界（M3 不发版，不污染 0.7.0）」并取得放行；随后 tag `v0.7.0` → Release → npm `0.7.0` → 看板回填。**首次出现「先签发放行、后被平台策略拦下 push」的插曲**：用户二次授权后完成推送，tag 与 Release 未受影响 |

---

## 3. 证据目录约定

| 目录 | 内容 | owner | 是否入库 |
|---|---|---|---|
| `docs/logs/phase0/` … `docs/logs/phase3/` | 命令输出、doctor 自检、构建日志 | 各任务 owner | 否（`.gitignore` 局部忽略，仅本地） |
| `docs/reports/` | 核验 JSON、审计报告、场景证据链 | verifier-dev / scenario-tester | 是 |
| `docs/evaluations/` | T3.4 选做评估报告；当前唯一文件 `docs/evaluations/2026-11-03-t3.4-closure.md`（T3.4 关闭结论，三项各一句） | evaluator | 是 |
| `docs/backups/` | `mcp.json` 等个人配置的改前备份 | env-agent | 是（据 T0.2 DoD"备份到仓内"） |

---

## 4. 进度快照（截至 2026-11-04，含 M1/M2/M3 整改批次与 C0–C4 完备批次）

> ⚠️ **本区由 `tools/check_taskboard.py` 逐格校验，禁止手写猜数字。**
> 校验命令：`python tools/check_taskboard.py`（CI 的 `lint` job 每次必跑，不一致即 `exit 1`）。
> **脚本只校验、不改写本区**——数字仍要人来改，但改错了会被机器抓住并指名到「哪一段、哪个状态、
> 表里几 / 快照几」。改任务表后**必须跑一遍脚本**。
>
> 六种状态**全部入列**（含 `阻塞`）：少一列就意味着那一态没有落点，被阻塞的任务会从快照里消失
> 而不报错。M3 首跑即因此判红，故补齐。

| 阶段 | 任务数 | 已完成 | 进行中 | 挂起 | 待开始 | 已关闭 | 阻塞 |
|---|---|---|---|---|---|---|---|
| Phase 0 | 5 | **5**（T0.1–T0.5） | 0 | 0 | 0 | 0 | 0 |
| Phase 1 | 9 | **9**（T1.1–T1.9） | 0 | 0 | 0 | 0 | 0 |
| Phase 2 | 6 | 0 | 0 | **6**（T2.1–T2.6） | 0 | 0 | 0 |
| Phase 3 | 5 | **3**（T3.1、T3.2、T3.5） | 0 | 0 | **1**（T3.3） | **1**（T3.4） | 0 |
| ‹Phase 0–3 小计› | **25** | **17** | **0** | **6** | **1** | **1** | **0** |
| M1 修复批次 | 11 | **11**（M1、M2、M3、C0、C1、C2、C3、C4、R0.7.2、R1、R2） | 0 | 0 | 0 | 0 | 0 |
| **合计** | **36** | **28** | **0** | **6** | **1** | **1** | **0** |

> 校验口径：Phase 0–3 内 `已完成 17 + 挂起 6 + 待开始 1 + 已关闭 1 = 25`；再加批次表的
> `已完成 10（M1/M2/M3/C0–C4/R0.7.2/R1）= 10` ⇒ **35**。合计行、小计行均由脚本自算比对。
> **两段分开统计**是为了不让整改批次污染原计划的 25 条口径（`T0.5` 的"25 条任务"、§0 各处引用都按 Phase 0–3 计数）。
> M1 已于 0.6.2 收口、M2 已于 0.7.0 收口、C0 已于 0.7.1 收口（均三证齐全）；M3 不发版，内容随 **0.7.1**（C0）带出。
> C1–C4 已于 **2026-11-04 00:51** 收口（CI run `41749893723` 七 job 全绿，含新增 `windows` job——
> 该 job 首跑即抓出「CLI 在 cp1252 控制台崩溃」这个**已在用户手里**的缺陷，是 C1 的直接产出）。
> **R0.7.2 已收口**（三证齐全：tag `v0.7.2` / GitHub Release / npm `0.7.2`，CI run `41754212053` 七 job 全绿）。
> **R1 置「已完成」的依据**：`scripts/regen.sh` 的**分级前置提示**（落后→4 行 warn / 一致→1 行 info /
> `false`→静默）+ 超时定向诊断（命中 `Begin LoadConfig` 才归因，否则明说"不能归因"）+
> `--fail-fast-on-migrate`（只看该键为不为 true）均已落地；三处文档（`regen-exit-codes` §4.1–§4.3 /
> `pitfalls` P1 / `SKILL.md`）与 `docs/DECISIONS.md` **D36** 同步成文。六条路径真跑，`pytest` **94 passed**、
> `node --test` **37/37**、两道机器校验 `rc=0`。
> **为什么不按"未提交"记「进行中」**：本批次自己的 DoD 就是"行为 + 文档 + 决策记录三者对齐且可复核"，
> 提交权归 lead（见 §0.4.1），提交动作发生在收口之后；若 lead 认为"未落地 commit"即不算完成，
> 把本行状态与 §4 的那两格改回「进行中」即可（脚本会立刻核对，不会静默放过）。
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
| 2026-11-03 | **M3 机制固化（R-E1–R-E4）**：新增 `tools/check_taskboard.py`（三组判据，纯标准库）并接入 CI `lint` job；`docs/DECISIONS.md` 追加 **D34**（形态变更元规则 / 角色入册协议 / L 等级降级须批准 / 节奏条款 / 模板化）；弃用字段口径统一为「v1.x 保留兼容、v2.0 移除」；F7/F8/F11/F12 批量清理 + README 环境注记。**首跑即抓到两处真缺陷**（脚本第一次对自己生效就有产出）：① 批次表里 M2 行被一行空行拆出表外 → 统计漏 1 条（Markdown 里空行后的 `\|` 不再属于原表）；② §4 快照缺「阻塞」列 → 六种状态里有一态无处可写。均已修，并把这个坑写进表头注。§4 快照同步为 28 条（19/1/6/1/1/0），小计与合计改由脚本自算比对 | software-engineer |
| 2026-11-04 | **M3 机制固化落地**：新增 `tools/check_taskboard.py`（616 行，纯标准库）并入 CI `lint` job；该 job 的 checkout 显式 `fetch-depth: 0`，否则判据③（tag vs T3.5）会静默降级成 note。**首跑即抓到两处真缺陷**：批次表 M2 行被一行空行截出表外（统计漏 1 条）、§4 快照缺「阻塞」列（该态无处落点）。同批：D34 治理元规则、弃用口径统一到 v2.0（字段未删）、F7/F8/F11/F12 与 README FAQ 注记 | software-engineer-2 |
| 2026-11-04 | **M2 收口（0.7.0 发布，BREAKING）**：tag `v0.7.0`（`64a9a01`）→ Release（正文入库 `docs/releases/2026-11-03-v0.7.0.md`）→ npm `0.7.0`（`latest`）→ 本表回填。GATE-3.1 第二次正规执行（因 BREAKING 单独请示）。**插曲**：用户先放行、push 随后被平台策略拦下一次，按纪律未自行重试；用户明确授权全部 git 操作后完成推送，tag/Release 未受影响 | lead |
| 2026-11-04 | **C0–C4 完备批次入册（C0 进行中）**：批次表追加 5 行（C0 修正与发版 / C1 门禁完备 / C2 机械化 / C3 硬件段预演 / C4 可维护性），§4 快照同步为批次 8 条、合计 33 条。**C0 已完成代码与文档**：重写本包真正的注册指南（补 0.7.0 fail-closed + 新增「注册后自检」）、`mcp-registration.md` 加防误读头、`package.json` 的 `files` 补入主指南、版本 bump 0.7.1（三处）、`docs/releases/2026-11-04-v0.7.1.md`。**触发原因是一条交付缺口**：0.7.0 的默认拒绝没写进任何随包指南，且包内那本讲的是两个外部 server ⇒ 用户按包内指南配完必被拦、且无从自查。**三证未产出 ⇒ C0 记「进行中」** | software-engineer |
| 2026-11-04 | **C1 + C2 落地（均记进行中，等 CI 实跑）**：`ci.yml` 新增 `windows` job（win32 分支唯一真跑处；Node 步骤必须 `shell: bash`，pwsh 不展开 glob）；`tools/npm_mcp_handshake.mjs` 改三计数（pass/fail/skip）+ `--require-materials` + `--ci`，素材按 `testbeds/ → tests/fixtures/e2e/` 定位，新增 `tests/fixtures/e2e/board.ioc`；lock 入库（根 version 对齐 0.7.1）+ CI 改 `npm ci` + `cache: npm`；pytest 加 `pytest-cov==7.0.0` 与 `--cov-fail-under=36`（基线实测 37%，3.11/3.13 同值）；node 22 档输出覆盖率（不设门槛）；新增 `tools/check_release.py`（版本轴 + 发布正文 + 未发版提醒，三坏样本自测通过）；`docs/DECISIONS.md` 追加 **D35** 发布 SOP；README 增依赖边界声明。**两处为进 CI 而修的真缺陷**：T9 的 `C:\Windows\win.ini` 在 Linux 上会被 resolve 到仓内（假红）→ 改跨平台界外路径；T6 需三者自洽素材，**有意保留 SKIP** 而不造假绿。**未完成**：CI 实跑（网络不通，push 不可能） | software-engineer |
| 2026-11-04 | **C4 文档 + C3 预演落地**：新建 `CONTRIBUTING.md`（三层测试/提交规范/单写者原则/依赖边界）、`.github/ISSUE_TEMPLATE/{bug_report,feature_request}.md`、`.github/PULL_REQUEST_TEMPLATE.md`、`docs/README.md`、`docs/releases/README.md`（版本 × 内容 × 三证，7 个版本逐行）、`docs/guides/gate-2.0-checklist.md`；`SKILL.md` §6 增 Phase 2 状态骨架（占位，不改版本号）；S4 前四段在 `testbeds/nuedc/G474_01_gpio` 副本上真跑：改 `PC13.PinState`（diff 1 行）→ 生成 62 s 无 KO → **核验 FAIL errors=2 但查明为结构性误判**（`CoupleFile=true`，定义在 `gpio.c`，核验器只扫 `main.c`）→ `pio run` SUCCESS（**Flash 5104 B / RAM 1664 B**）。**两个额外发现**：F2 重新生成把 `PLLN 100→85`（原 `main.c` 与自身 `.ioc` 不一致，200 MHz 超限）；F3 `AskForMigrate` 被 `project generate` 写回 `true` 且旧版本戳会挂死 `-q`（推翻 P1 旧结论）。原仓只读（sha256 前后一致） | software-engineer |
| 2026-11-04 | **F1/F3 缺陷修正 + 控制台编码加固（P1 批次）**：① **F1**：`verify_generation.py` 的定义类判据改为多文件扫描——给 `--project-root` 时扫 `Core/Src/*.c`（含 `main.c`）拼接判断，报出的定义位置经 `origin_of()` 换算回**原文件行号**（如 `定义 Core/Src/gpio.c:L42`）；未给 `--project-root` 且 `.ioc` 里 `ProjectManager.CoupleFile=true` 时，`main_init_present` / `pins_present` 由 fail **降 warn** 并把理由写进 `summary.notes`（**仅此一种情形**；`CoupleFile=false` 或给了 project-root 仍严格判 fail）。`regen.sh` 本就带 `--project-root`，主路径自动获益。**实测**：NUEDC 工程由 `verdict=FAIL errors=2` → **`verdict=PASS errors=0`**（`main_init_present` 报 `定义 Core/Src/gpio.c:L42`）；原 `_verifier-regen/g474` 仍 **PASS**（仅既有 1 条 `mx_script_abs_path` 预期 warn）。新用例 `tests/test_verify_multifile.py` 7 项（多文件 pass / 单文件仍 fail / CoupleFile=true 降 warn / CoupleFile=false 不降 / `.ioc` 读取器 / 行号换算）。契约 `references/verify-contract.md` §4.2/§4.3/§4.4 写入判据语义变更。② **F3**：`references/pitfalls.md` P1 改写为实测结论（保留被推翻的旧判断作留档，注明实测日期与 `docs/logs/phase4/` 证据），`SKILL.md` 两处 P1 引用同步；**`regen.sh` 行为未动**（"版本戳更旧 + 该键 true 时直接退 2"列为待批准项）。③ 控制台编码：三脚本加固 + `tests/test_console_encoding.py` 3 例（详见 C1 行） | software-engineer |
| 2026-11-04 | **R0.7.2 补丁发版入册（进行中，只做文档与版本号）**：`package.json` `version`、`SKILL.md` frontmatter `version` 与正文状态行、`README.md`「三个版本号」表两处 → 全部 **0.7.2**；新建 `docs/releases/2026-11-04-v0.7.2.md`（**开头点明是补丁版、无新增能力**，随后把两处**用户可见缺陷**按「症状 / 谁会遇到 / 怎么验证已修」写全：① CLI 在 cp1252/cp936 控制台打印 `→` 抛 `UnicodeEncodeError` 退出 1——修法是**按输出目标分流**，非 TTY 强制 UTF-8、TTY 保留控制台编码 + `backslashreplace`；② 核验器对 `ProjectManager.CoupleFile=true` 工程假失败——`MX_<P>_Init` 与 `__HAL_RCC_*_CLK_ENABLE()` 在 `Core/Src/<periph>.c`，而旧判据只读 `main.c`）；**判据语义变更单列一节**（`--project-root` 下扫 `Core/Src/*.c` 且行号换算回原文件；无 project-root + `CoupleFile=true` 降 warn 并写 `notes`，仅此一种情形），并论证"**为什么不降级成永远 warn**"——它是在非 GPIO 路径（只能手改 `.ioc`）上唯一能抓住"漏 `IPParameters`、日志干净什么都不报"的判据，废掉它等于在风险最高处静默拆网；**假失败比漏报更伤，但废掉检查同样不可接受**，故取"能读到真相就严格判、读不到就如实降级并自曝"。工程化批次（Windows CI 双平台 / lock 入库 + `npm ci` / 覆盖率底线 36 vs 基线 37 / `check_release.py` / D35 SOP / 贡献者文档）各一句不抢戏。验证等级表：pytest **94**（较 0.7.1 的 77 增 17 例——编码用例扩到 **10 例**（C1 收口时）＋ `test_verify_multifile.py` 7 例）/ Node **37** / 冒烟本机 **12** / CI `pass=11 skip=1`（**T6 缺素材，显式点名**）/ CI run `41749893723` 七 job 全绿。已知限制四条如实写（TOCTOU / **参数级失明**（`PLLN` 类改动 7 项看不见）/ T6 在 CI 恒 SKIP / TTY 分支无自动回归）。**`lib/`、`scripts/`、`tests/`、`tools/`、`.github/`、`references/` 一律未动**（提交权归 lead） | software-engineer |
| 2026-11-04 | **R1 批次（D36 三项裁决落地）**：`scripts/regen.sh` 新增**生成前分级提示**——读 `.ioc` 的 `ProjectManager.AskForMigrate` 后按**可判定性**分两级：`true` **且** 版本戳落后于锁定基线 → **4 行 `[regen][warn]`**（说明"该键 true 且版本戳落后时 `-q` 会停在 `Begin LoadConfig()` 直到超时"+ **可直接复制执行**的置 `false` 命令含真实绝对路径 + GUI 迁移替代路径 + 指向 P1）；`true` **但** 版本戳一致 → **一行 `[regen]` info**（不喊也不沉默：基线是**常量**，不代表你机器上真实安装的版本）；`false` / 读不到 → **什么都不打**。**为什么分级而不是两个极端**：一律 warn 会因 `project generate` 每次都写回 `true` 而**每次 regen 刷 4 行黄字**，用户很快学会无视 `[regen][warn]`（**警告常态化 = 没有警告**，旧文案"无实测卡死证据，仅作提示"正是这样被忽略的）；只在落后时输出、一致时**完全静默**则会在「工程戳 6.18.1 / 本机装 6.19.0」这类错配上判"不落后"→ **正好漏掉会挂死的那一例**（用错的判据换来的安静比吵闹更危险）。两个极端都写进 D36① 的否决记录。新增 **opt-in** `--fail-fast-on-migrate`（置位则退 `2`，给 CI / 批处理，默认关闭）。生成**超时**（`RC=124`）分支改为**定向诊断**：检查日志**末行附近**（尾部 10 个非空行且窗口内无 `Change cursor`/`Initializing MCU`/`End LoadConfig`）是否停在 `Begin LoadConfig()`——命中才判为迁移对话框挂死并给两条处置 + 指向 P1；**未命中只报超时并明确写"不能归因"**（把所有超时都归给一个原因，是另一种"看起来有解释其实没解释"）。**为什么不做"见到 `true` 就退 2"**（D36①）：不启动 CubeMX 就无法可靠得知当前安装版本（`EXPECTED_CUBEMX_VERSION` 是基线**常量**、非探测结果），判不出"版本戳是否更旧"，只凭该键拒跑会误拦「同版本、能正常生成」的合法工程——**误拦的代价高于一次 5 分钟挂起**。同批：`references/regen-exit-codes.md` 补 §4.1（告警/开关语义表 + 为什么不退 2）、§4.2（超时诊断两形态对照表 + 为何不能全文件 grep：成功日志里也有该行，实测 638 行中在第 314 行）、§4.3；`references/pitfalls.md` P1"待批准项"→**已定结论**、判据段与头部日期同步；`docs/DECISIONS.md` 追加 **D36**（② **不做时钟参数判据**——期望值无可信来源、比对退化成和自我比、半吊子判据比没有更糟、真防线是生成前后 diff + 接板清单；③ **核验器 2.0 维持不排期**——触发条件=真实 schema `/3` 需求或顶层字段造成误用；并明确 D19「单独出现不告警」**作废**、D19 原文保留）。**六条路径真跑**：info 档（`true`+版本一致 → 一行 info 且 `[regen][warn]` 里 `AskForMigrate` 计数 0）/ warn 档（`true`+6.18.0 → 4 行）/ 开关（`rc=2`、不打生成命令，版本一致时同样 `rc=2`）/ 不误伤（`false` 工程 0 条输出、尾行与改动前一致）/ 诊断命中（假 java 回放 `docs/logs/phase4/02-first-generate.log` 真实末 3 行 + 返 `124` → "这不是你的工程坏了" + 两条处置）/ 诊断未命中（回放真实成功日志全文 638 行 → 明说"不能归因"）。`pytest` **94 passed**（两条用例已按三档语义重写：原版断言的是 D19 旧行为且引用了已被 P1 推翻的"无实测卡死证据"字样） | software-engineer |
| 2026-11-04 | **F4 后续：testbed 板卡标注（纯文档，L0）**：`/testbeds/` 被 `.gitignore:9` 整体忽略 ⇒ 写进 testbed 目录的标注 **clone 后不存在**，故新建 `docs/guides/testbeds-board-map.md` 作为唯一随仓分发的真源：登记两个绑定实板工程（`testbeds/nuedc/G474_01_gpio` → **NUEDC 原板** PC13/14/15；`testbeds/xpulse-min` → **X-Pulse** PC0/1/2、共阳低电平点亮、PC13 无 LED）与全部模板/一次性副本（不得当首烧目标），并指出 G474 模板 README 自称「面向 Penguins-G474」却默认 PC13 闪灯、与 `xpulse.h` 冲突 ⇒ **板级事实以板级头文件/原理图为准，不以 `.ioc` 的 `GPIO_Label` 或模板 README 猜**。同步四处：`gate-2.0-checklist.md` §0/§1/§5（**勘误 §5 旧版「唯一首烧目标 = NUEDC 工程」**，改为按板选目标，并把「工程与板是否同一块」前置为观察表第一嫌疑）、`docs/README.md` §5 索引、`SKILL.md` §0.3 红线 2、`phase2-bringup-2026-11-04.md` §5 第 4 条置「已完成」。**不改任务表与 §4 快照**（本批是文档标注，不是新任务），`check_taskboard.py` / `check_release.py` 均 `rc=0` | lead |
| 2026-11-04 | **全量审定（agent 工程师视角，只读）**：产出 `docs/reports/audit-2026-11-04-agent-engineer.md`（四个只读分面：MCP 架构 / agent 效率 / 功能性 / 测试·CI·发布·文档一致性，加主审逐文件交叉核对）。发现按 P0/P1/P2 分级、逐条带 `文件:行号` 证据与「已做得好、不要改」清单。**两条 P0 由主审做纯内存 L2 复现**：① `expect_pins` 有而 `ioc` 无 ⇒ 引脚级 `skip` 但 `verdict=pass`；② `--project-root` 指到存在但空的目录 ⇒ 静默退回单文件扫描仍 `pass`。**驳回一条分面 P0 误报**（「`regen.sh` 没有 `--main-c`/`--mxproject`/`--log`」——usage 与参数解析均支持，SKILL 那条是裸调核验器），并把「硬编码 Windows 路径」降级为已登记约束。**定稿去重后 P0 10 / P1 17 / P2 10 = 37 条**（初稿 4/12/8；四分面回传后补入 A-17「任意文本 / 含 `KO` 日志仍 `PASS`」、A-21「`ioc_field` 换行注入任意 `.ioc` 键」、A-22~A-24 发版门禁三类，A-5 由 P1 升 P0，A-20 并入 A-21，架构分面第 4 项降 P2）。**审定全程未改实现**，七批处置建议按优先级列出，建议与下一批文档修订合并发一次补丁版；`docs/README.md` 索引补入 L5 报告与本审定报告。校验：`check_taskboard.py` / `check_release.py` rc=0、F4 批次文档 0 断链、报告 20 张表 0 列数不一致 | lead |
| 2026-11-04 | **下一步工作计划成文（纯文档，L0，未开工）**：新建 `docs/2026-11-04-next-steps-plan.md`，把全量审定 37 条发现收敛为 **W0–W6 七个可执行批次**，每批带「现状（`文件:行号`）→ 动作 → 可机器验收判据」与「不做清单」。**先做逐文件勘察再定计划**，得出六条会改变做法的硬约束：① 「7 项判据 + schema `/2`」是刚性契约（`ci.yml` 冒烟 `grep -q "/2"`、`references/verify-contract.md:238–239` 写明升 schema 的判据）⇒ 修 A-17 **不新增 check id**，改走 `main()` 输入校验退 2 + 复用 `log_cannot_map` 判 `fail`；② `tests/test_verify_generation.py:766 / :586` 两条既有用例把「`skip` / 空日志 `rc=0`」钉死 ⇒ W0 必须**改断言**而非只加用例；③ `run_verify()` 断言 JSON 落盘（`:70–95`）⇒ 负样本必须用 `run_cli()` 直跑；④ A-5/A-28 会连锁改看板任务表 6 行 + GATE 3 行 + §4 表格/散文「合计 35→36」+ T3.3 阻塞说明，故提升为**独立批次 W3**；⑤ `publish.yml` 的 `workflow_dispatch` 是文档化正常入口、幂等 `::warning` 是 D33 补账路径，且新版本发布前 `latest` 必然 ≠ `package.json.version` ⇒ 发布门禁**不带 `--network`**；⑥ `npm_mcp_handshake.mjs` 已有 SKIP 三数并列 + `--require-materials` 严格模式（`:32/:128/:372/:376`）⇒ A-24 只改 headline 措辞、**不把 SKIP 翻成 FAIL**。另核对 `tests/fixtures/log_clean.txt`（17 行，含 `[INFO] STM32CubeMX` / `LoadConfig:` / `Generating code under`）确认宽松日志形态判据不误伤正样本。**本批按 `docs/README.md` §2「计划不回改」约定，只新增计划与索引行、不回改三份旧计划；不改任务表、不改 §4 快照、未执行任何 W 批次**。待用户裁决 D-1（0.7.3 vs 0.8.0）等五个决策点后开工。校验：`check_taskboard.py` / `check_release.py` rc=0、`pytest -q` 94 passed、文档 0 断链 | lead |
