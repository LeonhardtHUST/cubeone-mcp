# cubeone-mcp 0.7.4 → 0.8.0 增量 PRD（两阶段：收尾 + 契约增强）

> **定位**：标准 SOP 第 1 阶段增量范围确认，供架构师做实现编排。**简单 PRD，不做竞品/市场分析。**
> **前置事实（已完成）**：`v0.7.3` 已于 2026-11-04 发布并**四证齐全**——tag `v0.7.3` / GitHub Release / npm `0.7.3`（Trusted Publisher + provenance）/ 看板与台账回填；HEAD `8fc07e3`，`git status` 干净，CI 7 job 全绿。
> **依据**：`docs/DECISIONS.md` D33（版本轴 + 四证收口）、D35（九步 SOP + §35.6 机器查/人工核边界）；`docs/README.md` §2.1（勘误与遗留项登记，B-2 与 lost-update 的原始登记处）；`docs/reports/2026-11-04-w0w6-implementation-design.md` §5.3/§5.4；`docs/releases/2026-11-04-v0.7.3.md`（v0.7.3 发版核证的「验证等级」表与「已知限制」）；`docs/releases/README.md`（台账）；`docs/reports/audit-2026-11-04-agent-engineer.md`（B-2 / B-5 / B-9 / B-10）。
> **本文不做**：不重写 D33/D35、不新增判据、不回改任何旧计划/旧报告/已发布正文、不动 §6 明确不做清单。

---

## 0. 项目信息

| 项 | 值 |
|---|---|
| Language | 简体中文 |
| Programming Language | 沿用现栈、无前端 UI（Vite + React + MUI + Tailwind 默认栈**不适用**）：Python（`scripts/`、`tools/`、`tests/`）+ Node.js ESM（`lib/`、`tests/node/`、`tools/*.mjs`）+ Bash（`scripts/regen.sh`）+ GitHub Actions YAML |
| Project Name | `cubeone_mcp_v074_v080` |
| 基线 | HEAD `8fc07e3`（工作区干净，实测 `git status --porcelain` 为空） |
| 版本策略 | `0.7.4`（patch）→ `0.8.0`（minor）**连续两版**，先收尾再增强 |
| 交付方式 | **实现 + 直接发版**，两版均走 D35 九步流水线（用户已预授权） |

**原始需求复述**：在 v0.7.3 已收口的基础上，**先**用 0.7.4 把发版后独立核证暴露的两条 Minor（包体积双口径、`_KO_LINE_RE` 大小写复测提示）与三项工程遗留（CRLF 归一处置、`tools/*` 编码加固、B-10 杂项）收干；**再**用 0.8.0 兑现两项升级契约定向的遗留增强（B-2：三工具 `outputSchema` + `structuredContent` 体积上限 + `tail()` 截断修复；并发文件锁）。**不含核验器加固**（W0-4 防伪造、W0-2 工程根内容校验本轮不做）；硬件项跳过、如实保留挂起。

---

## 1. 两版目标与范围边界

### 1.1 0.7.4 目标（一句话）

**把 v0.7.3 发版后独立核证暴露的两条 Minor 与三项工程遗留收干收净的补丁版——不触碰 MCP 契约、不改 7 项判据语义。**

**做（A–D 四组，详见 §2）**：A 两条 QA Minor；B CRLF 归一处置；C `tools/*` 编码加固；D B-10 杂项。

**不做**：不改 MCP 工具清单/参数契约；不改 `verify_generation.py` 的 7 项判据与 schema；**不改已发布的 `docs/releases/2026-11-04-v0.7.3.md`**（见 §1.3）。

### 1.2 0.8.0 目标（一句话）

**兑现两项遗留增强——让 MCP 通道对客户端更可消费（`outputSchema` + `structuredContent` 体积上限 + `tail()` 头尾保留）、对并发更安全（`ioc_backup`/`ioc_field` 文件锁）的 minor 版。**

**做（E–F 两组，详见 §2）**：E B-2；F 并发文件锁。

**不做**：不改 7 项判据/schema `/2`（核验器加固不在本档）；不加硬件依赖。

### 1.3 全局不做清单（两版共同硬约束，逐条照裁决与 §6）

1. **F-1 刚性契约不动**：7 个 `CHECK_*` / `CHECK_ORDER` / `schema platform32.verify_generation/2` 不动，**不新增第 8 个 check id**。
2. **不含核验器加固**：W0-4 防伪造日志、W0-2 工程根内容校验**本轮不做**（用户选的是 0.7.4 收尾 + 0.8.0 契约增强，不含第三档）。
3. **硬件项跳过**：T2.2 / T2.4 / T2.5 / T2.6 / T3.3 无新增硬件证据、本工程未启用 USART，**如实保留挂起，不得写成已实测**。
4. **§6 现有不做清单继续有效**：不做时钟/参数级判据（D36②）；不把 `check_release.py` 挂进 CI；不把 handshake 的 SKIP 翻成 FAIL、不给 CI 造假素材（F-6）；不删 `workflow_dispatch`、不把幂等 `::warning` 改回判红（F-5）；不回改旧计划/旧报告原文；不动 `testbeds/` 模板原仓；不为修这些单独起紧急版。
5. **不改已发布正文**：`docs/releases/2026-11-04-v0.7.3.md` **一字不改**——改它会破坏「Release 正文与入库文件逐字一致」这条已在 v0.7.3 成立的证据（§35.6 人工核第 2 项）。包体积历史口径只在 **0.7.4 正文与台账**中澄清（A①）。

---

## 2. 用户故事与可机器验收判据（A–F 六组）

> 判据均可追溯到 `docs/README.md §2.1`、v0.7.3 发版核证（`docs/releases/2026-11-04-v0.7.3.md` 验证等级/已知限制）、D33/D35、审定报告对应编号，或本轮用户裁决事实；不凭空自创。

### A 组 · v0.7.3 发版后 QA 两条 Minor（0.7.4）

**用户故事**：作为**维护发版证据的人**，我需要把 0.7.3 遗留的两处口径瑕疵（包体积双口径、`KO` 正则大小写依赖）在 0.7.4 说清楚且不动已发布正文，以便「正文与入库文件逐字一致」的证据不被破坏、后续也不会因 CubeMX 改大小写而静默漏检。

| 编号 | 范围要点 | 可机器验收判据 | 判据出处 |
|---|---|---|---|
| A① 包体积口径 | 0.7.3 正文 `138.1 kB` 是**本机 CRLF** pack，台账/看板/registry `137.6 kB` 是 **CI LF** pack；根因是工作区文件 `w/crlf`，去掉 CR 后包内文件尺寸与 registry 逐字节相等 | ① `git diff -- docs/releases/2026-11-04-v0.7.3.md` **为空**（已发布正文零改动）；② 0.7.4 正文与台账同时出现 `138.1 kB`（本机 CRLF）与 `137.6 kB`（CI LF / registry）并注明差异根因；③ 台账 `docs/releases/README.md` §2 对 0.7.3 行的口径澄清到位 | `docs/releases/2026-11-04-v0.7.3.md:231`（138.1 kB）；`docs/releases/README.md:44`（137.6 kB）；本轮用户核证事实（去 CR 后包内文件与 registry 逐字节相等） |
| A② `_KO_LINE_RE` 大小写 | 核验器整行 `KO` 正则为 `^\s*KO\s*$`，**大小写敏感**（`ko`/`Ko` 不命中）；CubeMX 若改版输出小写将静默漏检 | 在 `references/regen-exit-codes.md:76` 旁**追加一句**「CubeMX 改版需复测此正则（大小写敏感，`ko`/`Ko` 不命中）」；`scripts/verify_generation.py` 的 `_KO_LINE_RE` **本体不改**（`git diff` 该正则无变更） | `references/regen-exit-codes.md:76`（大写、独占一行）；`docs/releases/2026-11-04-v0.7.3.md:88`（`_KO_LINE_RE = ^\s*KO\s*$`） |

### B 组 · CRLF 归一处置（0.7.4）

**用户故事**：作为**在本机跑 `npm pack` 核对证据的维护者**，我需要一个**明确、可复现**的判据来区分「本机 CRLF pack」与「CI LF pack」，以便不会把本机尺寸当成发版证据、也不会陷入每次手动重检出的循环。

**实测基线（本轮勘察确认）**：`git ls-files --eol` 有 **21 个文件 `w/crlf`（工作区 CRLF / index LF）**，与 team-lead 口径一致；`.gitattributes:7-8` 要求 `*.py`、`*.md` 为 `text eol=lf`。因 `git status` 按归一化后判脏，故工作区仍显示干净——**CRLF 可在下次运行 CubeMX/编辑器保存后再次出现**。

**推荐方案（二选一，PRD 立场）**：**方案 2 为硬纪律（发版证据只认 CI LF pack），方案 1 为可选的本机发版前自检（不产生 commit）**。理由：方案 1（强制重新检出）能消除本机 21 个 `w/crlf`，但它是**环境操作**、不持久（每次 clone / 工具写回可能重现）、且因 `git status` 归一化本就显干净，容易误判「已根治」；方案 2 把证据锚到 CI 的干净 LF checkout，可复现、可审计、与 §35.6 人工核第 3 项一致。**是否彻底采纳方案 1 见 Q1。**

| 方案 | 动作 | 验收判据 |
|---|---|---|
| 方案 1 强制重检出（选做，不产生内容 commit） | 先 `git config core.autocrlf`（应 `false`/`input`）确保属性生效，再对 21 个 `w/crlf` 文件 `git checkout --`，使其按 `.gitattributes eol=lf` 落为 LF | `git ls-files --eol \| grep -c "w/crlf"` == **0**；`git status --porcelain` 仍为空（无内容 commit）；`npm pack --dry-run` 尺寸与 CI/registry 口径一致（137.6 kB 量级） |
| 方案 2 文档纪律（推荐，硬约束） | 在发版 SOP/正文与 `docs/releases/README.md` 写明「发版证据只认 CI 的 LF pack；本机 pack 尺寸不作为证据，除非先确认 `git ls-files --eol` 无 `w/crlf`」 | 文档含该声明；0.7.4/0.8.0 正文的包内容证据取自 **CI LF pack**；`git ls-files --eol` 状态如实记录（不声称已清零） |

### C 组 · B-5 `tools/*` 编码加固（0.7.4）

**用户故事**：作为**在 Windows 上运行门禁脚本的维护者**，我需要 `tools/check_release.py`、`tools/check_taskboard.py`、`tools/npm_mcp_handshake.mjs` 的读写统一 UTF-8 且对非 UTF-8/非 ASCII 输入不崩，以便不同控制台编码下门禁不会因编码问题误红或异常退出。

| 编号 | 范围要点 | 可机器验收判据 | 判据出处 |
|---|---|---|---|
| C · B-5 | 三个 `tools/*` 的读写统一 UTF-8；补「非 UTF-8 / 非 ASCII 输入不崩」负样本 | ① 三处文件读写显式 `encoding="utf-8"`（Python）/ 明确 `utf8`（Node）；② 新增负样本：喂非 UTF-8 字节 / 非 ASCII 路径或文本 ⇒ 不抛未捕获异常、给出可读错误；③ `python -m pytest tests/ -q` 与 `node --test tests/node/*.test.mjs` 全绿 | 审定报告 §6 P2 表 **B-5**（`§4.7`：编码加固未覆盖 `tools/*`）；`docs/README.md §2.1`（弱断言类遗留） |

### D 组 · B-10 杂项（0.7.4）

**用户故事**：作为**核对文档一致性的审阅者**，我需要散文/表格口径、D 编号、三证/四证措辞、owner、历史 job 数等杂项逐条对齐并能机器验的补断言，以便文档不再因口径漂移误导人。

| 编号 | 范围要点 | 可机器验收判据 | 判据出处 |
|---|---|---|---|
| D · B-10 | ① 散文/表格口径一致；② D 编号无重号、`docs/README.md` D 上限 == `DECISIONS.md` 最大号；③ 三证/四证措辞统一为 D33「四证」；④ 弱断言加强；⑤ `.coverage` 陈旧产物不入库；⑥ owner 冲突（`SKILL.md:416`）修正；⑦ 历史 job 数标时间点 | ① `python tools/check_taskboard.py` rc=0 且 `git diff` 散文数字与表格一致；② `ci.yml` 的 D 编号扫描（已是 `::error`）对 `docs/README.md` == `DECISIONS.md` 最大号（当前 D36）判绿；③ 全文「三证/四证」措辞统一为「四证（tag+Release+npm+看板）」，`git grep` 无残留「三证」歧义；④ `.coverage` 无入库（`git ls-files` 不含）；⑤ 历史 job 数标注时间点 | 审定报告 §5.7 **B-10**；`docs/README.md §2.1(1)(4)`；`docs/DECISIONS.md` D35 §35.2 step2（job 数 7）；`SKILL.md:416`（owner） |

### E 组 · B-2 `outputSchema` + `structuredContent` 体积上限 + `tail()` 截断（0.8.0）

**用户故事**：作为**被 MCP 客户端自动解析返回的 Agent/调用方**，我需要三个工具声明 `outputSchema`、`structuredContent` 有明确体积上限与截断规则、且 `tail()` 不再截掉首行的 `verdict`，以便我读到的结构化结果形状可预期、结论不被静默吞掉。

| 编号 | 范围要点 | 可机器验收判据 | 判据出处 |
|---|---|---|---|
| E · B-2 | ① `verify_generation` / `ioc_backup` / `ioc_field` 三工具补 `outputSchema`；② `structuredContent` 增体积上限（超限的截断/告警行为写清）；③ `lib/server.mjs:291–294 tail(s, n=12000)` 当前「只保留末 12000 字符」会截掉 `render_console()` 首行 `verdict`——**修复或改为头尾保留** | ① `tools/list` 三工具均含 `outputSchema`，且字段与各自 `structuredContent` 一致；② 存在明确的体积上限常量与截断逻辑，超限时有可读告警（字段/文案可验证）；③ `tail()` 改造后，长输出下 `render_console()` 首行 `verdict` **仍可见**（新增测试断言长 stdout 场景首行保留）；④ `node --test tests/node/*.test.mjs` 全绿 | `docs/README.md §2.1(2)`（B-2 原始登记，明确「C6 未触碰 `tail()`/`outputSchema`」）；编排文档 `§5.3`（`lib/server.mjs:291–294 tail(s, n=12000)`）；审定报告 **B-2**（`§3.3`） |

### F 组 · 并发文件锁（0.8.0）

**用户故事**：作为**可能同时开两个会话改同一工程的用户**，我需要 `ioc_backup`/`ioc_field` 对同一 `.ioc` / `ioc-backup.json` 加锁并在冲突时给出明确失败语义，以便双会话不再发生 lost-update、且单写者既有流程完全不受影响。

| 编号 | 范围要点 | 可机器验收判据 | 判据出处 |
|---|---|---|---|
| F · lost-update | `scripts/ioc_backup.py` / `scripts/ioc_field.py` 对同一 `.ioc` / `ioc-backup.json` 加锁（flock 或锁文件 + 超时 + 负样本） | ① 双进程并发负样本：两进程同时写同一目标 ⇒ **至少一个**明确失败（退出码稳定、错误可读），不再静默互相覆盖；② 锁失败/超时的退出码在文档与代码一致（见 Q3）；③ **单写者顺序流程零回归**（既有 pytest/node 用例全绿）；④ Windows 下有可运行实现（`flock` 不可用时的替代，见 Q3） | `docs/README.md §2.1(3)`（lost-update 原始登记：「后续若确需并发再评估 `flock`/锁文件 + 锁超时 + 负样本」）；编排文档 `§5.4`；审定报告 **B-9**（`§4.9`） |

---

## 3. 发布性质

### 3.1 0.7.4 —— patch（**无 BREAKING**）

- **性质**：补丁版。无新增能力、不改 MCP 工具清单与参数契约、不改 7 项判据/schema `/2`。
- **正文必写**：① 「无 BREAKING」明确声明；② 澄清 0.7.3 包体积双口径（`138.1 kB` 本机 CRLF vs `137.6 kB` CI LF，去 CR 后包内文件与 registry 逐字节相等，**不追改已发布 0.7.3 正文**）；③ `_KO_LINE_RE` 大小写复测提示；④ CRLF 处置口径（方案 2 硬纪律）；⑤ tools 编码加固与 B-10 杂项摘要。
- **升级建议**：无行为变化的用户可不升；需要证据口径一致性的维护者应升。

### 3.2 0.8.0 —— minor（**三项正文必写项**）

- **性质**：minor 版，**不破坏 F-1 契约**（仍 7 项判据 / schema `/2`），但有**客户端可感知的行为变化**，正文必须写清：
  1. **`outputSchema` 对 MCP 客户端是否可忽略**：`outputSchema` 为**新增可选字段**，旧客户端忽略不报错；但声明「读取 `structuredContent` 的消费者应同时容忍/忽略 `outputSchema` 缺失或新增」。
  2. **`structuredContent` 截断行为**：明确**体积上限阈值**、超限时**保留方向**（如头尾保留/尾部截断）、是否附**告警字段/文案**；消费方不得假设 `structuredContent` 永不截断。
  3. **文件锁超时/失败的失败语义**：锁冲突/超时时工具的**退出码**、是否 `isError`、**单写者顺序流程是否完全不受影响**、Windows 下的实现约束（`flock` 不可用）。
- **兼容性结论**：`outputSchema` 向后兼容（旧客户端忽略）；`structuredContent` 截断与 `tail()` 修复**改变返回文本/结构形态**、文件锁**新增并发失败语义**——这三项须在正文「BREAKING / 行为变化」节逐条说明，但它们不等于破坏 7 项判据契约。

---

## 4. 每版验收口径（0.7.4 与 0.8.0 各自执行一遍）

**① 四条固定命令**（每版发版前必跑、须全绿）：
```bash
python -m pytest tests/ -q
node --test tests/node/*.test.mjs
python tools/check_taskboard.py
python tools/check_release.py          # 发版前不带 --network；发布后核证才带
```

**② `npm pack --dry-run`**：清单须含 `docs/guides/` 四本指南；尺寸口径以 **CI LF pack** 为准（见 §2 B 组）；本机如仍有 `w/crlf` 须如实标注，不冒充 CI 证据。

**③ 版本轴五处同值（含 `package-lock.json` 根两处）**：

| # | 位置 | 当前 | 发版时 |
|---|---|---|---|
| 1 | `package.json` → `version` | `0.7.3` | 目标版本 |
| 2 | `package-lock.json` → 根 `version`（`line 3`） | `0.7.3` | 目标版本 |
| 3 | `package-lock.json` → `packages[""].version`（`line 9`） | `0.7.3` | 目标版本 |
| 4 | `SKILL.md` → frontmatter `version` | `0.7.3` | 目标版本 |
| 5 | `README.md` → 「三个版本号」表两处（`仓库发布标签` + `SKILL.md version`，同值视为一处发布轴） | `v0.7.3` / `0.7.3` | 目标版本 |

> **契约差异提示**：D35 §35.6 与 `check_release.py` 判据① 现口径是**四处**（tag = package.json = SKILL frontmatter = README 两处），**不含 `package-lock.json`**。本轮 team-lead 要求「五处（含 package-lock 根两处）」= 新增上表 #2/#3。**要机器可验，需在 0.7.4 D 组把 `check_release.py` 判据①扩展到 package-lock 根两处**（见 Q2）。`git tag` 与 `verify_generation.py --version`（核验器轴 `1.2.0`）**不并入发布轴**（D33 §33.2：核验器轴故意独立）。

**④ 发版按 D35 九步（step 0–9，照抄勿跳步）**：step0 版本轴同值 → step1 本地四项自验（含 `node tools/npm_mcp_handshake.mjs --require-materials`）→ step2 CI 全绿（含 Windows，job 数以 `ci.yml` 为准当前 **7**）→ step3 GATE-3.1 证据包（向用户出示，**用户明确放行**）→ step4 打 tag → step5 GitHub Release（正文先入库）→ step6 npm 发布（Trusted Publisher / `--registry official`）→ step7 看板回填（当场做）→ step8 两道机器校验（`check_taskboard.py` rc=0 + `check_release.py --network` rc=0）→ step9 npmmirror 同步（可选）。**顺序红线**：4 在 5/6 前、7 在 8 前（D35 §35.2）。

**⑤ §35.6 机器查 vs 人工核**：机器查（`check_release.py --network`：版本轴/tag/正文/官方 registry dist-tags/台账/工作区；`check_taskboard.py`：任务表↔快照、证据路径、当前版本 tag 存在时 T3.5 不得待开始）；人工核（CI success 逐 job、Release 正文与入库文件逐字一致、npm 页面可见性/tarball、用户明确放行、BREAKING 与迁移提示写进正文）。

---

## 5. 待确认问题（Open Questions）与停止线

> 以下为实现层需架构师/主理人明确的点（非新增用户裁决项）。PRD 已给出倾向，最终由架构师在实现编排中定案并回传主理人。

| # | 待确认问题 | PRD 倾向 |
|---|---|---|
| Q1 | **B 组 CRLF 归一处置选哪个方案**（强制重检出 vs 仅文档纪律） | 推荐**方案 2 硬纪律（发版证据只认 CI LF pack）+ 方案 1 作为可选本地发版前自检（不产生 commit）**；若团队要求彻底清零，则采纳方案 1 并保留方案 2 纪律。理由见 §2 B 组 |
| Q2 | **版本轴「五处」是否要 `check_release.py` 扩展校验 `package-lock.json` 根两处** | 建议**是**：本轮 team-lead 口径为「五处（含 package-lock 根两处）」，而现判据①只查四处；扩到 #2/#3 才能让「五处」机器可验（落 0.7.4 D 组） |
| Q3 | **F 组文件锁的退出码语义 + Windows 实现约束** | 锁失败/超时建议沿用 `{0,1,2}` 三分法（输入/环境错误退 **2**），**不得**新增破坏契约的码；Windows 无 `flock`，用锁文件（`O_CREAT|O_EXCL` + 超时回收）或 `msvcrt.locking`；**单写者顺序流程必须零回归** |
| Q4 | **E 组 `structuredContent` 体积上限阈值与截断算法** | 由架构师给**具体阈值**与**保留方向**（建议头尾保留、中间省略并附告警字段）；`tail()` 修复优先保证首行 `verdict` 可见 |
| Q5 | **E 组 `outputSchema` 的具体结构** | 由工程师按各工具 `structuredContent` 反推并与之一致；PRD 只要求「存在且字段自洽、对旧客户端可忽略」，具体 schema 由实现定 |

**停止线**：
- 两版**均严格按 D35 九步**；step3 GATE-3.1 证据包须向用户出示并**获明确放行后方可打 tag**（step3→step4），**不跳步**。
- step4 push 若被平台策略拦下：**停手报告，不自行重试**（D35 §35.2 step4）。
- **不触碰** F-1 契约 / §6 不做清单 / W0-4·W0-2 / 硬件项；**不改** 已发布 `docs/releases/2026-11-04-v0.7.3.md`。
- 硬件项 T2.2/T2.4/T2.5/T2.6/T3.3 如实保留挂起，**不得**为让看板变绿而标已实测。
- 本 PRD 完成即交架构师；PM 不自行实现、不直接发版。

---

## 6. 版本轴与发布边界

- **本两版均授权发版**（与上一轮「停在 GATE-3.1 前」不同）：`0.7.4`、`0.8.0` 各自完整走 D35 九步至收口，但每版仍须 step3 用户明确放行后才打 tag。
- **版本轴按 `0.7.4` → `0.8.0` 递进**；每次升版须**五处同值**（§4 ③），`package-lock.json` 根两处一并改，`git tag` 与 `verify_generation.py --version`（`1.2.0`）不并入发布轴。
- **四证收口**（D33 §33.2）：每版必须同时具备 tag + GitHub Release 正文（含验证等级表）+ npm 发布（Trusted Publisher）+ 看板回填，缺一视为未收口。
- **不把已发布正文当可改对象**：`docs/releases/2026-11-04-v0.7.3.md` 冻结；历史包体积口径只在 0.7.4 正文与台账澄清（A①）。
- **核验器契约固定**：两版结束 `verify_generation.py` 仍 `1.2.0` / 7 项判据 / schema `/2`，无第 8 个 check id。

---

> 本文是 `8fc07e3` 时点的**两阶段增量范围确认**，不是新计划；与 D33/D35/`docs/README.md §2.1` 冲突时以后者原文为准。实现位移按 `docs/README.md §2` 追加勘误，**不回改本文与旧文档**。
