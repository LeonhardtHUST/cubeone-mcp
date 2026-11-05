# 文档索引（docs/）

> 一页索引。**不确定看哪一页时先看这里**——本目录下每个文件都在下表有一行"什么时候看"。
> 顶层面向使用者的文档在仓库根：[`README.md`](../README.md)（定位与能力边界）、
> [`SKILL.md`](../SKILL.md)（Agent 操作面）、[`CONTRIBUTING.md`](../CONTRIBUTING.md)（怎么改、怎么测）。

---

## 1. 状态真源（**只有两页是"真源"，其余都是解释**）

| 文档 | 什么时候看 |
|---|---|
| [`TASKBOARD.md`](TASKBOARD.md) | **唯一状态真源**：任务表 + GATE 关卡 + §4 快照 + 角色登记 + §5 变更记录。改它之后必须跑 `python tools/check_taskboard.py`（rc=0） |
| [`DECISIONS.md`](DECISIONS.md) | **唯一决策真源**：D1–D36。想知道"为什么这样设计、哪些旧结论被推翻"看这里；发版流程见 **D35**（含 §35.6 机器查 vs 人工核），版本轴治理见 **D33**，治理元规则见 **D34** |

> 两页的分工：**看板说"做到哪一步了"，决策说"为什么这么定"**。
> 两者冲突时以决策为准并修看板——看板是执行快照，决策是规则。

## 2. 计划（四份判断快照，**不回改**）

| 文档 | 什么时候看 |
|---|---|
| [`2026-11-03-agent-team-plan.md`](2026-11-03-agent-team-plan.md) | 想知道最初的 Phase 0–3 排班、角色表、GATE 设计（原始蓝图）｜**已归档** |
| [`2026-11-03-execution-research.md`](2026-11-03-execution-research.md) | 想知道开工前的调研结论（工具选型、CubeMX 能力探测）｜调研，非计划 |
| [`2026-11-03-remediation-plan.md`](2026-11-03-remediation-plan.md) | 想知道 M0–M3 整改批次要解决什么（审定发现①–⑤与 R-A/R-B/R-C/R-D/R-E 编号出处）｜**已归档** |
| [`2026-11-04-engineering-completeness-plan.md`](2026-11-04-engineering-completeness-plan.md) | 想知道 C0–C4 完备批次（7 项审核发现、门禁/机械化/硬件预演/可维护性）｜**已归档**，目标版本写的是 0.7.1，C3 已被接板首日 L5 取代 |
| [`2026-11-04-next-steps-plan.md`](2026-11-04-next-steps-plan.md) | **当前唯一执行依据 · 当前执行中**：全量审定 37 条发现的 W0–W6 整改批次、逐条验收判据、六条勘察硬约束、发版策略；D-1~D-5 用户裁决已落 §5，按 W0→W6 逐批独立 commit、停在 **GATE-3.1 之前**（不打 tag / 不建 Release / 不发 npm） |

> 为什么计划不回改：已交付的计划是**某个时间点的判断快照**，改写它会让"当时怎么想的"消失（D32/D34 §34.2(5)）。
> 需要更正就追加勘误链接，不要动原文。
>
> **取代关系**：前三份计划的目标批次（Phase 0–3 / M0–M4 / C0–C4）均已交付或已被 L5 取代，
> 一律只作历史参考，**其批次号不再沿用**；新工作按 `2026-11-04-next-steps-plan.md` 的 W0–W6 执行。

### 2.1 勘误与遗留项登记（2026-11-04 · C7 追加，**不回改任何旧计划 / 旧报告原文**）

> 按本节开头「计划是时点快照、更正只追加勘误」的约定，以下四条**只追加**：上文与
> [`reports/2026-11-04-w0w6-implementation-design.md`](reports/2026-11-04-w0w6-implementation-design.md)
> 的既有章节（§5.3 / §5.4 仍是 B-2 与 lost-update 的原始登记处）**一个字都不改**。

1. **勘误（编排 §0.2 的预判遗漏）**：实现编排 §0.2 只复核了「W0-4 形态校验会影响哪些既有正向
   用例」，**未预判到 W0-2（给了 `--project-root` 必须有 `Core/Src/*.c`）同样会让既有正向合成
   夹具失效**。C1 已按「**补素材、不放宽判据**」正确解决：`tests/test_verify_generation.py` 的
   `make_fake_project()` 补 `Core/Src/main.c`（`_read_source_texts()` 会跳过 main.c，判据断言零影响）、
   `write_cannot_map_log()` 补 C1/C2 两类日志头、`test_mx_script_without_any_script_is_skip` 的
   临时工程同样补齐。处理已由主理人验收采信。**给后续轮次的约束**：凡合成日志当 `--log` 须满足
   ≥2 类 CubeMX 特征；凡传 `--project-root` 的测试工程须含 `Core/Src/*.c`。
2. **B-2 遗留（后续排期，本轮不做）**：无 `outputSchema`、`structuredContent` 无体积上限、
   `lib/server.mjs` 的 `tail(s, n=12000)` 只保留末 12000 字符、会截掉 `render_console()` 首行
   `verdict`。C6 只去死路径回显 + 提示分派，**未触碰 `tail()` / `outputSchema`**。原始登记见编排
   文档 §5.3；不新增任务卡、不改 §6 明确不做清单。
3. **双会话 lost-update 竞态（已知限制，仅文档登记、不上文件锁）**：同一工程目录上并发执行两个
   会话时，`ioc-backup.json` / `*.ioc.bak` / `.ioc` 可能互相覆盖；`ioc_backup.py` 的 SHA-256
   完整性校验能**检测**部分覆盖但不能**阻止**。规避：遵守单写者原则，不同时用两个会话改同一工程；
   后续若确需并发再评估 `flock` / 锁文件 + 锁超时 + 负样本。原始登记见编排文档 §5.4；
   **本轮不改实现、不上锁、不新增任务卡**。
4. **`regen.sh:276` 精确小写 `true` 的已知边界**：`[ "$IOC_MIGRATE" = "true" ]` 只认精确小写，
   `TRUE` / `True` / 带尾空格的 `true ` 会漏（审定报告 :733 列为「会漏」）。C7 的 W6-3 值变体
   用例**如实断言当前行为（不拦截 / 不告警）以锁住边界**，**不修判据**——改判据属范围扩张且与
   D36① 冲突。将来若要放宽，须与 D36①、`pitfalls.md` P1、本仓 `regen-exit-codes.md` §4.1 同批修订。
5. **CRLF 归一口径（0.7.4 B 组：方案 2 为硬纪律、方案 1 为可选自检）**：
   - **陷阱**：**`git status` 干净 ≠ 工作区逐字节等于 index**。`.gitattributes` 的 `text=auto`
     让 index 存 LF，而工作区文件可以仍是 CRLF——`git status` 按**归一化后**比较，所以看不见这层差异。
     后果是**本机 `npm pack` 的体积与 CI / registry 不一致**（0.7.3 实测 `138.1 kB` vs `137.6 kB`），
     当前实测 `git ls-files --eol | grep -c "w/crlf"` = **21** 个文件属这种情况。
   - **硬纪律（方案 2，必须）**：**发版证据只认 CI 的 LF pack**（本机 `npm pack` 尺寸不作证据）。
     落点见 [`releases/README.md`](releases/README.md) 顶部「发版证据口径」。
   - **可选自检（方案 1，不产生 commit）**：只在 `git status` **干净**时执行（有未提交改动先 commit/stash，
     `git checkout --` 会覆盖工作区）：

     ```bash
     git status --porcelain                  # 必须先为空
     git config core.autocrlf                # 期望 false 或 input
     git ls-files --eol | awk '$0 ~ /w\/crlf/ {print $NF}' | while IFS= read -r f; do
       git checkout -- "$f"                  # 只按 .gitattributes 重新落行尾，内容不变
     done
     git ls-files --eol | grep -c "w/crlf"   # 期望 0
     git status --porcelain                  # 期望仍为空（无内容改动）
     npm pack --dry-run | tail -3            # 此时本机尺寸才与 CI 同口径
     ```

   - **清零不是硬要求**：方案 1 是**环境操作、不持久**（CubeMX / 编辑器保存后 CRLF 可能再现），
     用它冒充"已根治"反而制造错觉。**硬纪律是发版走 CI**，`w/crlf` 计数**如实记录、不声称清零**。
6. **两处"已知不一致"登记（0.8.0 发版前 QA 发现，本轮不改、只登记）**：
   - **F-2 陈旧锁 + `--lock-timeout 0` 的第一次尝试仍会退 2**：锁文件已陈旧时，"回收 → 重试"
     发生在**同一轮循环内**，而 `timeout=0` 的截止时间在循环开始时就算好了，所以第一次仍可能
     直接超时。这属编排 §3.4 的**预期行为**（`0` 的语义就是"只尝试一次、立即超时"，不是"必然
     成功"），**不是缺陷**；可优化的是**文案**——应提示"锁已陈旧并已回收，请重试一次"，而不是
     让使用者以为有活进程占着。**待后续改文案**（不改退出码语义）。
   - **F-4 `outputSchema` 里 `_meta` 的声明粒度不一致**：`verify_generation` 把 `_meta` 展开成
     五个字段，而 `ioc_backup` / `ioc_field` 只写 `{ "type": "object" }`。这是**细化程度**的差异，
     **不影响任何客户端**：`_meta` 本身是可选字段，且三处都**没有** `additionalProperties: false`，
     两种写法的校验行为等价。若要统一，属 schema 打磨，与判据无关。
7. **两项证据口径的补正（0.8.0 发版后 QA 指出，只登记、不改已发布正文）**：
   - **F-2 正文里不该再给 `w/crlf` 的具体区间**：0.8.0 正文已知限制 #7 写了「实测在 20–21 之间」，
     而 QA 当时实测是 **24**。既然同一条已经声明"该计数**不是稳定证据**、随文档写盘变动"，
     就**不该再给数字**——给了数字，读者就会拿它当判据，然后发现对不上。**后续正文只写
     「`w/crlf` > 0 时本机 pack 一律不作证据，证据只认 CI 的 LF pack」，不给任何具体值。**
   - **F-3 发版证据宜指「发版 commit」那条 CI run**：0.8.0 的看板行与正文当时引用的是 `41957633547`
     （**Q2b commit `d37edd2`** 的 run），而发版 commit `9771145` 的 run 是 `41958307841`。
     三条（`41957633547` / `41958307841` / 回填 commit `aa8d1ed` 的 `41958846283`）**都是 7/7 绿**，
     结论没有虚假，只是**指向错了对象**——发版证据要能回答"发版那个 commit 本身绿不绿"。
     看板行已改正；**正文不改**（改它会再破一次与 Release body 的对应关系）。
   - ⇒ 附带的**新纪律**已写进 [`releases/README.md`](releases/README.md) 的「发版证据口径」：
     `--notes-file` 必须指向 `git show HEAD:<path>` 导出的 **LF** blob（或先把工作区文件重检出为 LF），
     判据是"与 **HEAD blob** 逐字一致"，不是"与工作区文件一致"。

## 3. 报告与证据（`reports/`）

| 文档 | 什么时候看 |
|---|---|
| [`reports/t1.2-verifier-contract.md`](reports/t1.2-verifier-contract.md) | **要消费 `verify.json` 或自己实现核验器时**——7 个 check id 的完整契约、保证边界、`/1→/2` 迁移 |
| [`reports/t1.6-s1-report.md`](reports/t1.6-s1-report.md) | 想知道一次**完整成功链路**长什么样（改配置 → 生成 → 核验 → 构建，含 Flash/RAM 数字） |
| [`reports/t1.6-s1-runbook.md`](reports/t1.6-s1-runbook.md) / [`-prep.md`](reports/t1.6-s1-prep.md) / [`-baseline.md`](reports/t1.6-s1-baseline.md) / [`-dryrun.md`](reports/t1.6-s1-dryrun.md) | 要**复现 S1 场景**时按 runbook → prep → baseline → dryrun 顺序读 |
| [`reports/t1.7-s2-audit-stm32-digital-clock.md`](reports/t1.7-s2-audit-stm32-digital-clock.md) | 想做**只读审计**（不动盘，产出引脚表/时钟树/构建结果）时的范例 |
| [`reports/t1.8-s3-report.md`](reports/t1.8-s3-report.md) | 想知道**核验器能抓什么、抓不到什么**（故意写坏 `.ioc` 的正反对照） |
| [`reports/t1.8-s3-prep.md`](reports/t1.8-s3-prep.md) | S3 负路径实验的准备记录（构造坏样本的方法） |
| [`reports/t0-cubemx-configure-signature.md`](reports/t0-cubemx-configure-signature.md) | 要调 `cubemx_configure` 的 `commands` 透传时——源码级签名与坑 |
| [`reports/t0-askformigrate-evidence.md`](reports/t0-askformigrate-evidence.md) | 遇到 `.ioc` 生成后 `AskForMigrate` 被写成 `true` 时（P1 陷阱的证据） |
| [`reports/t0-regen-sh-review.md`](reports/t0-regen-sh-review.md) | 想审 `regen.sh` 的判据设计（查 KO vs 查退出码） |
| [`reports/t0-skill-v11-checklist.md`](reports/t0-skill-v11-checklist.md) / [`t0-v11-independent-check.md`](reports/t0-v11-independent-check.md) | 想知道 SKILL 与核验器 v1.1 的对照检查清单与第三方复核结论 |
| [`reports/s4-dryrun-g474_01_gpio.md`](reports/s4-dryrun-g474_01_gpio.md) | 想知道**无板能做的前四段**（改配置→生成→核验→构建）在真实 NUEDC 工程上的结果（Phase 2 接板前的预演） |
| [`reports/phase2-bringup-2026-11-04.md`](reports/phase2-bringup-2026-11-04.md) | **接板首日 L5 证据**：X-Pulse 板级引脚、F4/F5/F6 三个现场坑、烧录 + 寄存器回读 + 目视双判据 |
| [`reports/audit-2026-11-04-agent-engineer.md`](reports/audit-2026-11-04-agent-engineer.md) | **全量审定报告（agent 工程师视角）**：MCP 架构 / agent 效率 / 功能性 / 测试·CI·发布 / 文档一致性，P0–P2 分级发现与逐条证据 |
| [`reports/t0-redaction-audit.md`](reports/t0-redaction-audit.md) | **脱敏审计结论**：`mcp.json` 改前备份的明文凭据与脱敏红线核对（安全相关） |
| [`reports/2026-11-04-w0w6-incremental-prd.md`](reports/2026-11-04-w0w6-incremental-prd.md) | **W0–W6 增量 PRD / 范围确认**：37 条发现的用户故事与逐字沿用计划 §3 的可机器验收判据 |
| [`reports/2026-11-04-w0w6-implementation-design.md`](reports/2026-11-04-w0w6-implementation-design.md) | **W0–W6 实现编排**：精确到文件 / 函数 / 行号 / commit / 验收命令，含 Q-1~Q-5 裁决落地与 C0–C7 文件集 |
| [`reports/2026-11-04-v074-v080-incremental-prd.md`](reports/2026-11-04-v074-v080-incremental-prd.md) | **0.7.4–0.8.0 增量 PRD / 范围确认**：A–F 六组用户故事与可机器验收判据、两版发布性质、Q1–Q5 |
| [`reports/2026-11-04-v074-v080-implementation-design.md`](reports/2026-11-04-v074-v080-implementation-design.md) | **0.7.4–0.8.0 实现编排**：P1–P5 / Q1–Q3 逐 commit 文件集与验收矩阵、`outputSchema` 草案、64 KiB 裁剪算法、文件锁 API |

> 原始日志在 [`logs/`](logs/)（**被 `.gitignore` 局部忽略，只在做实验的机器上存在**）：
> `phase0/`–`phase4/` 下是 CI 上拿不到的命令输出。报告里引用日志路径时，**不要指望别人 clone 后能看到**。
>
> **测试数字口径（A-26 / B-3）**：文档与看板里出现的 `74 / 77 / 94 / 127 / 136 / 145 / 154 passed`、
> Node 例数 `31 / 32 / 37 / 41 / 42`、覆盖率 `37%` 都是**各批次时点的快照**，不是恒定基线。
> 引用时以当次实跑输出为准：`python -m pytest tests/ -q`（基准 **2026-11-04（0.7.4 P4 后）：154 passed**）与
> `node --test tests/node/*.test.mjs`（基准 **2026-11-04（0.7.4 P4 后）：42 passed**）；
> 覆盖率基准 `pytest --cov=scripts tests/ -q` **37%**（CI 底线 36%，2026-11-04）。
> **不跨批次复用旧数字充本次证据**（`SKILL.md` §3 第 4 条）。

## 4. 发布台账（`releases/`）

| 文档 | 什么时候看 |
|---|---|
| [`releases/README.md`](releases/README.md) | **版本 × 内容 × 四证对照表**（tag / Release 正文 / npm / 看板回填），查"某个版本改了什么、证据齐不齐" |
| [`releases/2026-11-05-v0.8.0.md`](releases/2026-11-05-v0.8.0.md) | **当前版本（v0.8.0）**：契约增强 minor——`outputSchema`（新增可选字段）/ `structuredContent` 64 KiB 上限（超限头尾保留 + `_meta`，未超限不注入）/ `tail()` 头尾保留 / `.cubeone-lock` 并发锁。**输入契约与 7 项判据零改动** |
| [`releases/2026-11-04-v0.7.4.md`](releases/2026-11-04-v0.7.4.md) | 历史版本（0.7.4）：收尾补丁版——0.7.3 包体积双口径澄清、发版证据只认 CI LF pack（CRLF 纪律）、`tools/*` 编码加固、版本轴扩到**五处** |
| [`releases/2026-11-04-v0.7.3.md`](releases/2026-11-04-v0.7.3.md) | 历史版本（0.7.3）：审定整改 W0–W6 的补丁版——堵 G1 四类假绿（证据不成立统一 rc=2 且不落报告）、`.ioc` 双层拒绝换行注入、`regen.sh` 退出码归一；**一处 BREAKING behavior**，判据零改动 |
| [`releases/2026-11-04-v0.7.2.md`](releases/2026-11-04-v0.7.2.md) | 历史版本（0.7.2）：两处用户可见缺陷修复 + 判据语义变更（`Core/Src/*.c` 多文件扫描）；四证齐全，版本轴同值（口径见 `DECISIONS.md` **D35 §35.7**，现为五处） |
| [`releases/2026-11-04-v0.7.1.md`](releases/2026-11-04-v0.7.1.md) | 历史版本（0.7.1，文档与脚本修正，无行为变更） |
| [`releases/2026-11-03-v0.7.0.md`](releases/2026-11-03-v0.7.0.md) | **BREAKING**：路径白名单默认翻转（未设 `CUBEONE_ALLOWED_ROOTS` = 拒绝所有路径参数） |
| [`releases/2026-11-03-v0.6.2.md`](releases/2026-11-03-v0.6.2.md) | M1 接缝修复批次（退出码白名单 / 入参校验 / 编码 / Node 单测基建） |
| [`releases/2026-11-03-v0.6.1-backfill.md`](releases/2026-11-03-v0.6.1-backfill.md) | 首个 npm / MCP 工具通道版本；**正文为事后补发**（见 D33 §33.4） |

## 5. 指南（`guides/`）

| 文档 | 什么时候看 |
|---|---|
| [`guides/npm-publish-and-codebuddy.md`](guides/npm-publish-and-codebuddy.md) | **要注册本包（`npx cubeone-mcp`）或配 `CUBEONE_*` 时看这本**——含 0.7.0 BREAKING 迁移、env 表、**注册后自检**、发布流程与 9 个反直觉坑 |
| [`guides/mcp-registration.md`](guides/mcp-registration.md) | 要把 **`vscode-cube-mcp` / `platformio.mcp` 两个外部 server** 接进客户端时看这本（与本包注册是两件事） |
| [`guides/gate-2.0-checklist.md`](guides/gate-2.0-checklist.md) | **接板日**（GATE-2.0）当天的执行清单：探针/供电/共地/安全确认/COM 口/首烧目标/串口预期 |
| [`guides/testbeds-board-map.md`](guides/testbeds-board-map.md) | **选 testbed / 首烧之前先看**：哪个副本面向哪块板、LED 引脚与有效电平、哪些只是模板不能烧（F4 后续；`testbeds/` 被忽略，这页才是随仓库分发的真源） |

## 6. 其它

| 路径 | 什么时候看 |
|---|---|
| [`evaluations/2026-11-03-t3.4-closure.md`](evaluations/2026-11-03-t3.4-closure.md) | 想知道 T3.4 三项评估为什么"推迟/不做"（**关闭结论**，不是待办） |
| [`backups/`](backups/) | `mcp.json` 改前备份（`*.redacted.json` 为脱敏版）。⚠️ **含明文凭据的那份不得外传**，脱敏红线见 `guides/mcp-registration.md` §6 |

---

## 不知道该看哪页时

1. 要**用**这个工具 → 根目录 [`README.md`](../README.md) 的「能力边界」+ [`SKILL.md`](../SKILL.md)
2. 要**改**这个工具 → [`CONTRIBUTING.md`](../CONTRIBUTING.md)（三层测试 + 提交规范 + 单写者原则）
3. 要**判断进度** → [`TASKBOARD.md`](TASKBOARD.md) §4 快照
4. 要**判断历史决策** → [`DECISIONS.md`](DECISIONS.md) 目录（D1–D36）
5. 要**判断某个结论可不可信** → 看该结论标注的 L 等级（README「验证等级」），以及 `reports/` 里对应报告的"已知限制"
