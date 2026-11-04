# cubeone-mcp 下一步工作计划：审定发现整改（2026-11-04）

> **定位**：把 [`reports/audit-2026-11-04-agent-engineer.md`](reports/audit-2026-11-04-agent-engineer.md)
> 的 **37 条发现（P0 10 / P1 17 / P2 10）** 收敛成一批**可验收、不破坏既有设计**的执行卡。
> **依据**：审定报告 §8 的七批建议 + 本轮对仓库的逐文件勘察（命令与行号见 §8）。
> **状态**：**已批准，执行中（2026-11-04）**。D-1~D-5 已由用户通过交互问答逐项裁决，结果见 §5；
> 本轮按 W0→W6 全批实施，**停在 GATE-3.1 之前**，不自动打 tag / 建 Release / 发 npm。
> **本次更新范围**：仅更新状态行、§4(1) 的版本措辞与 §5 的裁决记录；§0–§3、§6–§8 的判断与任务卡原文不回改，
> 仍遵守 `docs/README.md` §2「计划是时点快照、更正只追加勘误」的约定。
> **纪律**：Conventional Commits + L 等级声明、每项独立 commit、单写者原则、
> 看板改动后必跑 `tools/check_taskboard.py`、GATE-3.1 发版前证据包 + 用户明确放行。

## 0. 勘察基线

| 项 | 实测值（2026-11-04 17:38 GMT+8） |
|---|---|
| HEAD / 远端 | `74589be`，`origin/master` 同值，`git status` 干净 |
| CI | run `41808391218` **success**，7 个 job 全绿（仅 shellcheck 与 ubuntu-latest 迁移两条非阻塞 warning） |
| 版本轴 | `package.json` = `SKILL.md` frontmatter = README 两处 = `0.7.2`；最新 tag `v0.7.2`；npm `latest = 0.7.2` |
| 机器校验 | `check_taskboard.py` rc=0、`check_release.py` rc=0、`pytest -q` **94 passed in 45.17 s** |
| 审定报告 | `docs/reports/audit-2026-11-04-agent-engineer.md`，917 行 / 46 731 字符 |
| 测试面 | `tests/` 8 个文件（含 `conftest.py`、5 个 Python 测试、`tests/node/server.test.mjs`）+ `tests/fixtures/` 12 项 |

**勘察范围**：`scripts/verify_generation.py`（1713 行）、`scripts/ioc_field.py`、`scripts/regen.sh`、
`lib/server.mjs`（726 行）、`package.json`、`tests/` 全体、`tests/fixtures/` 日志样本、
`tools/check_release.py` / `check_taskboard.py` / `npm_mcp_handshake.mjs`、
`.github/workflows/{ci,publish}.yml`、`SKILL.md`、`README.md`、`docs/TASKBOARD.md`、
`docs/README.md`、`docs/DECISIONS.md`、`references/verify-contract.md`、`.gitignore`、
以及三份既有计划文档。**结论全部带 `文件:行号`，见 §3 任务卡与 §8 附录。**

### 0.1 与既有计划的关系（索引约定：不回改）

[`README.md`](README.md) §2 明确写「计划是某个时间点的判断快照，**不回改**；需要更正就追加勘误链接」。
因此本计划**不改任何旧计划原文**，只在 `docs/README.md` §2 追加一行，并声明取代关系：

| 旧计划 | 现状 | 本计划的处理 |
|---|---|---|
| `2026-11-03-agent-team-plan.md` | Phase 0–3 原始蓝图，已交付 | 归档，历史参考 |
| `2026-11-03-remediation-plan.md` | M0–M3 已完成，M4 已由接板首日完成 | 归档，历史参考 |
| `2026-11-04-engineering-completeness-plan.md` | C0–C4 目标版本写的是 **0.7.1**，现已发到 0.7.2；C3「硬件预演」已被 R2 的 **L5** 取代 | 归档，历史参考；**其批次号 C0–C4 不再用于新工作** |
| **本计划** | 基于 `74589be` 的第 4 份判断快照 | **当前唯一执行依据**，批次号 W0–W6 |

---

## 1. 勘察得出的六条硬约束（决定「怎么改」，比发现清单更重要）

这六条是初读审定报告看不出来、但一旦按字面执行就会把事情做坏的事实。

### F-1 「7 项判据 + schema `/2`」是刚性契约，不能新增 check id

- `scripts/verify_generation.py:96–113` 定义 7 个 `CHECK_*` 常量与 `CHECK_ORDER`；`:1429` 的 `verdict` 只看 `errors`。
- `ci.yml` 冒烟步骤用 `python scripts/verify_generation.py --version | grep -q "/2"` 把 schema 钉死。
- `references/verify-contract.md:238–239` 写明「三处破坏性变更都属于会静默出错，所以升了 schema 号」。
- **影响**：报告 §8 建议「增加 `log_ko_lines` 判据」若照字面做，会新增第 8 个 check id，
  破坏 `tools/list` 描述、SKILL、发布正文、契约文档里的「7 项」口径，却不会被 CI 抓到。
- **落地做法**：**不动 `CHECK_ORDER`、不动 schema**。把「证据不成立」做成 `main()` 的输入校验，
  统一退 `EXIT_INPUT_ERROR = 2`；把「生成确实失败」（整行 `KO`）**复用** `log_cannot_map` 判 `status=fail`（rc=1）。
  两类都要补测试，但 `checks` 数组长度与 id 集合保持 7 个不变。

### F-2 两条既有用例把「旧行为」钉死了，W0 必须改它们，不是只加用例

- `tests/test_verify_generation.py:766` `test_pins_present_skips_without_flag_or_ioc` 明确断言
  「传了 `--expect-pins` 但没给 `--ioc` ⇒ `status=skip` 且 detail 含 `--ioc`」。
- `tests/test_verify_generation.py:586` `test_empty_log_warns_not_passes` 明确断言
  「空日志 ⇒ `result.returncode == vg.EXIT_PASS`」（只有 `log_cannot_map` 是 warn）。
- **影响**：A-11 / A-4 一改，这两条立刻红。**这是预期，不是回归**，但计划里必须写明
  「拆用例 / 改断言」，否则执行者会以为自己改坏了而回滚修复。

### F-3 负样本不能用 `run_verify()` helper

`tests/test_verify_generation.py:70–95` 的 `run_verify()` 里有
`assert json_out.is_file(), "CLI 未生成 JSON 报告"`。输入校验退 2 时**不会**落 JSON，
helper 会先炸在断言上、掩盖真实退出码。
**落地做法**：所有「必须不能 pass」的负样本用 `run_cli()` 直跑，断言 `returncode` 与 stderr，
不复用 `run_verify()`；只有正向用例继续用 helper。

### F-4 A-5 / A-28 会连锁改状态真源，必须单独一批

`docs/TASKBOARD.md` 当前同时存在：`R2` 行「已完成 / **L5**」(`:158`)、
T2.1–T2.6 六项全「挂起」(`:116–121`)、GATE-2.0/2.1/2.2 全「挂起」(`:172–174`)、
`:46–49`「当前会话无硬件」、`:129` T3.3「阻塞于 Phase 2 挂起」、
`:204` 快照 Phase 2 = `0 完成 / 6 挂起`、`:208` 合计 **36**、`:210` 散文却仍写「合计 **35**」。
`tools/check_taskboard.py` 会逐段重算并比对快照。
**落地做法**：W2 先统一操作面口径，W3 **单独一批**改看板（任务表 + GATE + §4 表格 + 散文 + 校验口径 +
T3.3 说明 + §5 变更记录），改完立刻跑 `check_taskboard.py`；不要与 W0/W1 混在同一 commit。
**未实测的项要如实保留挂起**（T2.2 FW_H7、T2.6 负路径、串口 `pio device monitor`）——
`phase2-bringup-2026-11-04.md:175` 明写本工程未启用任何 USART。

### F-5 发布门禁不能卡死两条合法路径

- `publish.yml` 注释把 `workflow_dispatch` 写成**正常发布入口**（"push master 后到 Actions → Run workflow"）；
  幂等护栏用 `::warning` 跳过，是 **D33 补发历史 Release** 的必然路径。
- `check_release.py --network` 查的是 npm `dist-tags`；在**目标版本尚未发布**时，
  `latest` 必然不等于 `package.json.version`。若把「latest == version」当发布前门禁，正常发版会被自己卡死。
- **落地做法**：发布流里跑 `check_release.py` **不带 `--network`**（只校验本地版本轴、tag、正文、工作区），
  `--network` 只用于**发布后核证**；dist-tags 判红逻辑加在 `--network` 路径里，并显式带官方 registry。
  dispatch 增加必填 `tag` 输入并校验 `tag == package.json.version`；**不要删 dispatch，不要把幂等 warning 改回判红**。

### F-6 `handshake` 的 SKIP 是有意取舍，只改措辞

`tools/npm_mcp_handshake.mjs:32–33` 已有 `--require-materials` 严格模式，
`:128–133` 明确「严格模式下 SKIP 即失败」，`:372` 会打 `SKIPPED（未验证，不代表通过）`，
`:376` 汇总行已三数并列 `pass=/fail=/skip=`，`:160` 写明「宁可 SKIP 也不造假素材」。
**落地做法**：A-24 只把 `skip=N` 带进 headline 与 Job Summary，**不把 SKIP 翻成 FAIL、
不给 CI 造假素材**。CI 的 node 22 档仍用 `--ci`。

---

## 2. 批次总览

| 批次 | 目标 | 覆盖编号 | 主要改动面 | 依赖 | 随包 |
|---|---|---|---|---|---|
| **W0** | 堵住 G1 的四类假绿 | A-11 / A-14 / A-17 / A-4 / A-8② | `scripts/verify_generation.py`、`lib/server.mjs`、`tests/` | — | 是 |
| **W1** | 堵 `.ioc` 内容注入 + 能力边界可机读 | A-21 / A-20 | `scripts/ioc_field.py`、`lib/server.mjs`、`tests/` | W0（同改 lib/tests） | 是 |
| **W2** | 操作面归位（Agent 看的那几页） | A-1 / A-5 / A-10 / A-12 / B-1 / B-6 | `SKILL.md`、`README.md` | — | 是 |
| **W3** | 状态真源归位（**连锁批次**） | A-5 / A-28 / A-13 / A-26 / A-27 / B-3 | `docs/TASKBOARD.md`、`docs/README.md`、`tools/check_taskboard.py` | W2 先定口径 | 否 |
| **W4** | 证据口径与随包可达性 | A-7 / A-9 / A-2 / A-3 / A-8 余项 | `SKILL.md`、`lib/server.mjs`、`package.json` | W0/W1 | 是 |
| **W5** | 发布门禁与防再漂移 | A-22 / A-23 / A-24 / A-6 | `tools/check_release.py`、`publish.yml`、`npm_mcp_handshake.mjs`、`ci.yml` | 可与 W2 并行 | 否 |
| **W6** | 编排链与 P2 收尾 | A-18 / A-19 / A-25 / A-15 / A-16 / B-4/B-5/B-7/B-8/B-9/B-10 | `scripts/regen.sh`、`tests/`、`.gitignore`、`docs/` | W0 | 部分 |

**执行序**：`W0 → W1 → (W2 ∥ W5) → W3 → W4 → W6 → GATE-3.1 → 一次补丁版 → W3/W5 的后续校验回填`。
与审定报告 §8 七批的映射：报告 ①= W0、②= W1、③= W2+W4、④= W5、⑤= W3 的机制部分+W5-4、⑥= W3、⑦= W6；
**唯一实质调整**是把 A-28 从「顺手改文档」提升为独立批次 W3（F-4），并把发布门禁批次收紧（F-5/F-6）。

---

## 3. 逐批任务卡

### W0 · 堵 G1 四类假绿（P0，最高优先）

**统一做法**：按 F-1，在 `scripts/verify_generation.py:1635–1660` 的输入校验段新增
`validate_evidence_inputs(...)`，凡「证据不成立」一律退 `2`；
`lib/server.mjs:421–474` `validateArgs()` 同步加参数联动，让 MCP 在调用前给可机读错误。
唯一例外 W0-3：`KO` 是域内「生成失败」，复用现有判据判 `fail`。

| 编号 | 现状（勘察行号） | 动作 | 验收判据（可机器验） |
|---|---|---|---|
| W0-1 / A-11 | `check_pins_present()` `:889–928` 在 `ioc_text=None` 时返回 `skip`；`main()` 输入校验只查 `isfile`；`test_verify_generation.py:766` 断言该 skip | `expect_pins` 非空且 `--ioc` 缺失 ⇒ 退 2，文案点名两个参数；`validateArgs` 加同一联动规则 | 负样本 `run_cli()`：只给 `--expect-pins` 不给 `--ioc` ⇒ rc=2、无 JSON；把 `:766` 用例**拆成两条**：无 flag 仍 `skip`、有 flag 无 ioc 必须 rc=2 |
| W0-2 / A-14 | `main():1650–1660` 只判 `os.path.isdir(project_root)`；`_read_source_texts():406–446` 遇空工程根静默退回单文件扫描 | 给了 `--project-root` 时，`<root>/Core/Src/*.c` 必须非空，否则退 2 并提示「工程根可能选错」 | 负样本：空目录、`Core/Src` 存在但无 `.c` ⇒ 均不得得到 `verdict=PASS`；`tests/test_verify_multifile.py` 补一条 |
| W0-3 / A-17① | 核验器全文无整行 `KO` 正则（`:584–618` 只扫 `Cannot map`）；`regen.sh:403–408, :519–524` 才有，且 `:160` 已有 `test_ko_in_log_fails_generation_with_exit_1` | 在 `check_log_cannot_map()` 内追加整行 `^[[:space:]]*KO[[:space:]]*$` 扫描，命中 ⇒ `status=fail`、detail 写「生成脚本被 CubeMX 拒绝」；**复用 `log_cannot_map` id** | 新 fixture `tests/fixtures/log_ko.txt`（2 行 `KO`、0 行 `Cannot map`）⇒ `verdict=FAIL`、rc=1；`regen.sh` 既有用例不受影响 |
| W0-4 / A-17② + A-4 | `main()` 读 `--log` 只 `isfile`；`check_log_cannot_map():604–609` 空日志仅 `warn`；`references/README.md` 当 `--log` 可得 `verdict=PASS errors=0`；`:586` 断言空日志 rc=0 | `validate_evidence_inputs()` 加**宽松**形态判据：空文件、或不含任一 CubeMX 特征行 ⇒ 退 2。特征行取 OR（`[INFO] STM32CubeMX` / `LoadConfig:` / `Generating code under` / `Code generation finished` 等），**不可写成严格模板**，否则制造新的假红 | 四个负样本：`references/README.md`、空日志、随机文本、含 `KO` 真日志 ⇒ 全部不能 `verdict=PASS`；**正向回归**：`tests/fixtures/log_clean.txt`（17 行，首行 `[INFO] STM32CubeMX 6.18.1…`）与 `docs/logs/phase4/` 真实成功日志必须仍 PASS；改 `:586` 断言为 rc=2 |
| W0-5 / A-8② | `validateArgs():421–474` 只遍历 `props`；三个 schema 的 `additionalProperties:false`（`:202–280`）从未落地 | 加一行未知键拒绝，错误文案列出合法键名（如 `projectRoot` ⇒ 提示应为 `project_root`） | `tests/node/server.test.mjs` 组 4 增 1 条；`node --test tests/node/*.test.mjs` 全绿 |

**W0 验收命令**：
```bash
python -m pytest tests/ -q
node --test tests/node/*.test.mjs
python scripts/verify_generation.py --version | grep -q "/2"   # 7 项 / schema 不变
python tools/check_taskboard.py && python tools/check_release.py
```

**W0 不做**：不把形态校验做成 `warn`（warn 不阻塞，等于没修）；不改 `:1429` 的 `verdict` 计算式；不加第 8 个 check id；不动 `verify_documents()` 的签名与 `CHECK_ORDER`。

### W1 · 堵 `.ioc` 内容注入

| 编号 | 现状（勘察行号） | 动作 | 验收判据 |
|---|---|---|---|
| W1-1 / A-21 | `scripts/ioc_field.py:147–185` `set_value()` 直接 `lines[index] = f"{key}={value}{ending}"`，`key`/`value` 均不过滤换行；`lib/server.mjs:545–566` `buildArgs` 用 argv 传 `value`，`validateArgs` 只查类型/枚举/必填 | **双层拒绝** `\r`/`\n`：`validateArgs()` 对 `key`/`value` 返回 `isError`；`ioc_field.py` 的 `get_value`/`set_value` 入口同样拒绝（CLI 直调也要挡） | 负样本 CRLF / LF / 尾空格三种变体 ⇒ `changed=false`、`.ioc` 行数不变、rc=2；`tests/test_ioc_field.py` 与 Node 组 4 各加一条 |
| W1-2 / A-20 | `CAPABILITY_NOTE`（`lib/server.mjs:186`）只是 description 文字，`validateArgs` 不看键名；`set key PA9.Signal value USART1_TX` 现可成功 | `ioc_field set` 命中 `*.Signal` 非 GPIO / `Mcu.IP*` 时，`structuredContent` 增加 `capability_warning` 字段，文本给出「超出工具能力，须手改 `.ioc`/GUI 并强制过 G1」 | **不做权限层拦截**（能力层 ≠ 权限层，见 `references/capability-boundary.md:8–10`）；机读字段存在且文案可读即可 |

### W2 · 操作面归位

| 编号 | 现状（勘察行号） | 动作 | 验收判据 |
|---|---|---|---|
| W2-1 / A-1 | `SKILL.md:43` 用 `cubemx_help` / `pio_system_info` 探「MCP 通道」；`:127–134` §1.2 表把 6 个**外部 server** 工具列为「MCP 通道」；本包实为 3 工具（`lib/server.mjs:190–281`） | §0.1 判据改为「`tools/list` 是否含本包 3 工具 / 注册后自检」；§1.2 拆成「本包 3 工具」与「外部 server（另一通道，不属于本包）」两张表 | 全文检索 `cubemx_help` 不再充当通道判据；SKILL 工具表与 `TOOL_DEFS` 一一对应 |
| W2-2 / A-5 | 过期点：`SKILL.md:20, :96, :134, :327, :333–334, :353, :376–390, :413`；`README.md:176, :287` | **分段更新，不整体翻转**：已达 L5 的（烧录 / 寄存器回读 / 目视 / LED）改「已实测（2026-11-04）」并指向 `phase2-bringup-2026-11-04.md`；串口段与 `pio device monitor` **如实保留未实测**；GATE-2.1 安全确认保留、只去掉「无硬件」前提；§7 补 L5 报告；`D1–D30` → `D1–D36` | W5-4 的状态词扫描通过后，SKILL/README 不含「无硬件 / 整体挂起 / 一律缺」；§3 的 L5 行可正常声明 L5 |
| W2-3 / A-10 | `SKILL.md:333–334` 引用仓内不存在的 `Core/Src/stdio_port.c` / `test/stdio_port_test.c`；`:318, :360` 引用模板仓的 `AGENTS.md` | 换成仓内真实可跑命令（如 `python -m pytest tests/ -q`），并注明模板仓来源；确属外部文件的显式标注「模板仓，本仓不含」 | 脚本解析 SKILL 反引号路径，仓内不存在的引用归零（占位符需显式标注） |
| W2-4 / A-12 | `SKILL.md:230–231` 与 `:287` 回滚口径冲突，其中 `git checkout --` 会丢用户改动；`regen.sh:113` 本就有备份机制 | 统一为「改前 `ioc_backup` → 失败从备份回滚」，删掉 `git checkout --` 建议 | 全文只剩一种回滚口径 |

### W3 · 状态真源归位（连锁批次，单独 commit）

| 编号 | 现状（勘察行号） | 动作 | 验收判据 |
|---|---|---|---|
| W3-1 / A-28 | `docs/TASKBOARD.md:46–49, :116–121, :129, :158, :172–174, :204, :208, :210` 互相矛盾（详见 F-4） | 按 R2 的 L5 事实重算任务表 / GATE / §4 表格 / 散文合计 35→36 / 校验口径 / T3.3 阻塞说明 / §5 变更记录；**未实测项保留挂起** | `python tools/check_taskboard.py` rc=0；`git diff` 中散文数字与表格一致；**不得**为了让脚本绿而把未实测项标成完成 |
| W3-2 / A-27 | `tools/check_taskboard.py:109` `TAG_RE = ^v0\.[67]\.\d+`；`:521–547` 判据③只做全局代理 | TAG_RE 放宽到 `^v\d+\.\d+\.\d+`；判据③改为校验「当前版本 tag 存在时 T3.5 不得待开始」 | 构造含 `v0.8.0` 假 tag 的自测副本，判据③仍生效；本仓 rc=0 |
| W3-3 / A-13 / A-26 / B-3 | `docs/README.md:14, :85` 写 D1–D35（实际 D36）；`:57` 把 v0.7.1 标「当前版本」；漏索引 `releases/2026-11-04-v0.7.2.md`、`reports/t0-redaction-audit.md`；`SKILL.md:416` 单写者名分、`README.md:271`「4 个工具」；测试数字四套口径未标基准 | 一次性补齐；新增本计划索引行并标「当前执行中」；测试数字统一标注基准日期/命令 | 脚本比对 `docs/**/*.md` 与索引，真漏项归零；D 编号 = `DECISIONS.md` 最大号 D36 |

### W4 · 证据口径与随包可达性

| 编号 | 现状（勘察行号） | 动作 | 验收判据 |
|---|---|---|---|
| W4-1 / A-7 | `lib/server.mjs:297–329` `runPython()` 把 `--json-out` 指向 `mkdtempSync` 临时目录、读完 `rmSync`；`SKILL.md:351` 仍把 `verify.json` 当 L4 证据 | SKILL 第 5 步写清「MCP 通道证据 = `structuredContent`，可另给 `report_md` 落盘，**不产生 `verify.json`**」；`tools/list` 描述同步。**不改临时目录机制**（stdout 纪律与安全模型依赖它） | 文档口径与代码一致；不出现「MCP 会生成 verify.json」的表述 |
| W4-2 / A-9 | `verify_generation.py:1705` 返回必然失效的临时路径；`lib/server.mjs:613` 的「verdict/checks」提示对 2/3 工具不成立 | 去掉死路径回显；提示按工具分派 | 三个工具的返回文本各自自洽 |
| W4-3 / A-3 | `package.json:25–36` `files` 只带 2 本 guides；SKILL 引用的 9 个 `docs/*.md` 有 7 个不在包内 | 最小方案：`files` 补 `docs/guides/gate-2.0-checklist.md` 与 `docs/guides/testbeds-board-map.md`（接板必需），其余在 SKILL 顶部注明「`docs/` 仅仓库可见」；版本号同步 | `npm pack --dry-run` 清单含两本指南；SKILL 无随包死链 |
| W4-4 / A-2 / A-8 | `lib/server.mjs:201` `readOnlyHint=true` 与 `report_md`/`restore` 写盘矛盾；`:587–596` ETIMEDOUT 与 ENOENT 合并成「无法启动 Python」；`:319–327` `readJson()` 裸 catch 吞错；`:239/:253/:554` `action` 默认三方口径 | ① 注解澄清只读语义；② 按 `res.error.code` 分支；③ 解析失败作为独立诊断字段；④ `action` 三方口径取一（倾向：把「默认」二字删掉，保持 required） | `tests/node/server.test.mjs` 组 1 增 ETIMEDOUT 用例；组 4 既有 5 例不受影响 |

### W5 · 发布门禁与防再漂移

| 编号 | 现状（勘察行号） | 动作 | 验收判据 |
|---|---|---|---|
| W5-1 / A-22 | `tools/check_release.py:233–263` `npm_dist_tags()` 未带 `--registry`，docstring 明说「任何失败只降级 WARN」；`check():267` 只查本地四处同值 / tag / 正文存在；`:432` `--network` | ① `npm view` 显式 `--registry=https://registry.npmjs.org/`；② `--network` 下 dist-tags 不一致**判红**（用于发布后核证）；③ 补台账回填 / Release / 工作区干净 / CI 的机器可查项；不能机器查的写进 D35 人工核清单 | 对当前 v0.7.2 跑 `--network` rc=0；构造错版本副本 rc≠0；`docs/releases/README.md` 的「三证」措辞同步（F-5） |
| W5-2 / A-23 | `publish.yml` 的 `on:` 含 `workflow_dispatch` + `release: published`；job 只跑 `pytest tests/ -q`，无 tag / Release / 看板校验 | 在「安装 pytest」之后加门禁步骤：`check_taskboard.py` + `check_release.py`（**不带 `--network`**）+ `tag == package.json.version`；dispatch 增必填 `tag` 输入；release 事件校验 `github.event.release.tag_name` | 无 tag 输入 ⇒ 红；v0.7.3 正常路径 ⇒ 绿；**D33 补发历史 Release 的 `::warning` 幂等分支保持可走**（F-5） |
| W5-3 / A-24 | `npm_mcp_handshake.mjs:375–378` headline 与 rc 只看 `fail`，`pass=11 skip=1` 仍输出 PASS（但 `:32/:128/:372` 已有严格模式与「不代表通过」措辞） | **只改措辞**：headline 带 `(skip=N)`，Job Summary 列出 SKIP 项 | CI node 22 档输出可见 `skip=1`；`--require-materials` 行为与退出码不变（F-6） |
| W5-4 / A-6 | `ci.yml` lint job 现有 `check_taskboard.py`、非阻塞 shellcheck、脚本入口冒烟；无操作面状态词扫描 | lint job 增一条轻量扫描：禁止 SKILL/README 出现「无硬件 / 整体挂起 / 未实测（无硬件）/ 一律缺」，并校验 `docs/README.md` 的 D 编号 == `DECISIONS.md` 最大号 | 故意注入一个失效状态词 ⇒ lint 红；当前 HEAD 绿。**不要把 `check_release.py` 挂进 CI**——`ci.yml` 注释已写明那会让长期未发版状态每次都红，是刻意取舍 |

### W6 · 编排链与 P2 收尾

| 编号 | 现状（勘察行号） | 动作 | 验收判据 |
|---|---|---|---|
| W6-1 / A-18 | `regen.sh:132` `while [ $# -gt 0 ]`；`:136–146` 共 11 处带值选项全用 `shift 2`，`$2` 缺失时参数个数不变 ⇒ 死循环 | 每个 `shift 2` 前判 `${2:-}` 为空即 `die 2`（或抽 `need_value()` helper） | `timeout 5 bash scripts/regen.sh -e` ⇒ 2 秒内退 2 且点名缺参；`tests/test_regen_preflight.py` 加一条 |
| W6-2 / A-19 | `regen.sh:537` `exit "$VERIFY_RC"` 会透传 `9009` / `127` / 信号码，破坏 `{0,1,2}` 契约 | 显式映射：`0/1` 透传，其余归一为 `2` 并打印原始码 | 假 Python 桩造 9009 ⇒ 退 2；`references/regen-exit-codes.md` 同步 |
| W6-3 / A-25 | `tests/test_regen_preflight.py` 只测三档前置提示（`:214/:236/:250`）；超时归因、`--fail-fast-on-migrate`、回滚、值变体零覆盖 | 用现成素材 `docs/logs/phase4/02-first-generate.log`、`04-first-generate-retry.log` 补 ≥4 条负样本（含大小写 / 尾空格变体），**不造假素材** | `pytest tests/test_regen_preflight.py -q` 全绿；`regen.sh:451` 在 `:515` rollback 之前打印「已从备份回滚」的时序不实陈述一并修 |
| W6-4 / B-9 等 | `.gitignore` 缺 `*.ioc.bak.sha256`；`regen.sh:216–218, :240–245` `--dry-run` 仍 `mkdir -p`；A-15 `spawnSync` 阻塞、A-16 `physical()` fail-open；B-4/B-5/B-7/B-8/B-10 杂项 | 逐条小修；双会话 lost-update 竞态**至少写进文档登记**（是否上文件锁另议）；A-15/A-16 与 W4-4 同批改 `lib/server.mjs` 避免并发覆盖 | `git check-ignore` 命中 sidecar；dry-run 不建目录；超时文案不再宣称已回滚 |

---

## 4. 发版策略

1. **随包改动**：W0 / W1 / W2 / W4 / W6 会改 `SKILL.md`、`lib/`、`scripts/`、`package.json`。
   按审定报告 §0 的判断，**合并成一次补丁版**（D-1 裁决定为 `0.7.3`，不再是候选），不要连着升三次。
   D-5 裁决：本轮只完成实现与推送，实际打 tag / 建 Release / 发 npm 留到用户单独放行 GATE-3.1 之后。
2. **发布正文必须写「BREAKING behavior」**：原本会拿到 `verdict=PASS` 的四类输入，
   现在退 `2` 或判 `FAIL`；`ioc_field set` 拒绝换行；MCP 未知参数被拒。
   这不是文案修饰——用户的自动化脚本可能因更严格而变红，需要迁移说明。
3. **三证 / 四证按 D35**：tag `v0.7.3` → GitHub Release → npm `0.7.3`
   （用 `--registry=https://registry.npmjs.org/` 核证，本机默认 npmmirror 只同步到 0.7.1）→ 看板回填。
4. **GATE-3.1 证据包**：`check_release.py --network` 判绿、`check_taskboard.py` rc=0、
   `pytest -q` 全绿、`node --test tests/node/*.test.mjs` 全绿、CI success、
   发布正文三条 CLI 命令与 argparse 逐一对得上、**用户明确放行**。
5. W3 / W5 是仓库内改动（CI、工作流、文档），**随时可推送，不必等版本**。

---

## 5. 开工前需要用户裁决的决策点

| # | 决策点 | 本计划倾向 | 反方理由 / 代价 | **用户裁决（2026-11-04）** |
|---|---|---|---|---|
| D-1 | 目标版本 `0.7.3`（补丁）还是 `0.8.0`（minor） | **0.7.3**：修的是「错误地给出 pass」，属缺陷修复，无新增 API；但正文必须写 BREAKING behavior | 若认为「verdict 语义变化」算破坏性契约，应走 0.8.0；代价是版本轴、文档、台账都要按 minor 重走 | ✅ **0.7.3 补丁版**（采纳倾向）：版本轴按 `0.7.3` 准备；发布正文必须写明 BREAKING behavior 与迁移提示 |
| D-2 | W3（状态真源连锁改动）现在做还是等下一轮 | **现在做，但单独一批**：A-5 是 P0，且 W2 改完操作面后若看板仍写挂起，错误路径仍在 | 连锁改 6 行任务表 + 3 个 GATE + 快照 + 散文，是全部批次里回归面最大的一处 | ✅ **本轮做，单独一批**（采纳倾向）：W3 不与 W0/W1/W2 混在同一 commit，改完立刻跑 `check_taskboard.py`，未实测项如实保留挂起 |
| D-3 | A-22 是给 `check_release.py` 改名，还是补齐判据 | **补齐判据 + 在 D35 写清「哪些机器查、哪些人核」** | 改名会让 D35 / 台账 / SOP 三处引用全变；补齐能保留既有调用点 | ✅ **补齐判据，保留脚本名**（采纳倾向）：`check_release.py` 名称与所有调用点不变，补官方 registry / `--network` 判红 / 可机器查项；D35 写清机器查 vs 人工核边界 |
| D-4 | A-3 是把指南加进 `files`，还是只在 SKILL 顶部加说明 | **两本接板指南加进 `files`，其余加说明** | 多带两份 md 会略增包体积；但接板时看不到 `testbeds-board-map.md` 正是 F4 事故的成因 | ✅ **两本接板指南进 `files`**（采纳倾向）：`docs/guides/gate-2.0-checklist.md` + `docs/guides/testbeds-board-map.md` 入随包清单，其余 `docs/` 在 SKILL 顶部注明「仅仓库可见」 |
| D-5 | 是否现在开工 W0 | **等用户明确放行**；W0 风险最低（前置校验 + 负样本，不改判据语义） | 一旦开工就进入「改随包文件」轨道，最好与 D-1 一起拍板 | ✅ **现在开工，全批实现到 GATE-3.1 前**：W0→W6 全部实现、逐批独立 commit、四条验收全绿、推送 `master` 并确认 CI success；**不**打 tag、**不**建 Release、**不**发 npm，发版需另行明确放行 |

### 5.1 裁决落地约束（团队执行边界）

1. **版本轴**：`package.json` / `SKILL.md` frontmatter / README 两处的升版动作属于发版批次，
   不在 D-5 划定的本轮实现范围内；W4-3「版本号同步」的口径由架构师在实现编排中明确，
   避免 GATE-3.1 前出现 `version` 与 `tag` 不一致。
2. **W3 隔离**：`docs/TASKBOARD.md`、`docs/README.md`、`tools/check_taskboard.py` 的连锁改动
   必须是一个独立 commit（L0），且不得为让脚本变绿而把 T2.2 / T2.6 / 串口等未实测项标成完成。
3. **发布门禁**：`check_release.py` 保持原名与既有调用点；`--network` 的 dist-tags 判红只用于发布后核证，
   `publish.yml` 门禁步骤跑**不带** `--network` 的版本（F-5）；`workflow_dispatch` 与幂等 `::warning` 分支保留。
4. **随包清单**：`npm pack --dry-run` 必须能看到两本接板指南；SKILL 顶部说明与 `files` 清单互为补充，不能只做其一。
5. **停止线**：GATE-3.1 证据包可以准备并列出，但**不得执行**打 tag、创建 GitHub Release、`npm publish`、
   发布台账回填。推完 `master` 确认 `git log origin/master..HEAD` 清空 + CI success 后即向用户汇报待放行。
6. **未裁决事项**：若实现中发现计划未覆盖的新歧义（如 F-1 的宽松特征行清单、W4-4 的 `action` 口径），
   由架构师在实现编排中给出明确方案并回传主理人，不得自行扩张范围或改动 §6「明确不做清单」。

---

## 6. 明确不做清单

1. **不动** `CHECK_ORDER` / 7 个 check id / schema `/2`（F-1）；不排期核验器 2.0（D36③）。
2. **不做**时钟 / 参数级判据（D36②：期望值无可信来源，半吊子判据比没有更糟）。
3. **不把** `check_release.py` 挂进 CI（`ci.yml` 已写明刻意不挂的理由）。
4. **不把** handshake 的 SKIP 翻成 FAIL、不给 CI 造假素材（F-6）。
5. **不删** `workflow_dispatch`、不把幂等 `::warning` 改回判红（F-5，D33 补账路径）。
6. **不回改**三份旧计划原文（`docs/README.md` §2 约定），只加索引行。
7. **不把未实测能力写成已实测**：串口段、`pio device monitor`、T2.2 / T2.6 如实保留。
8. **不动** `testbeds/` 里的模板原仓；不重跑烧录 / 不重做 L5（沿用 `phase2-bringup-2026-11-04.md` 证据）。
9. **不做**「为修这些单独发紧急版」；一次补丁版带齐。

---

## 7. 执行纪律

- **单写者**：`scripts/` + `lib/` 由同一人改（W0→W1→W4-4 串行，避免 R1 那种并发互相覆盖）；
  `SKILL.md` / `docs/` 由另一人改；`tests/` 跟随对应实现改。W3 单独一人一次写完。
- **每批独立 commit**，message 带 L 等级（W0/W1 至少 L2，W3 为 L0，发版批次为 L4 + GATE-3.1）。
- **每批固定四条验收**：`python -m pytest tests/ -q`、`node --test tests/node/*.test.mjs`、
  `python tools/check_taskboard.py`、`python tools/check_release.py`；改 `SKILL.md` 时加跑版本轴。
- **W3 改完必须立刻跑** `check_taskboard.py`，且人工复核散文数字与表格一致（脚本只验表 ↔ 快照内部自洽）。
- **推送**：本机 WorkBuddy 注入的 `HTTPS_PROXY=127.0.0.1:45843` 对 GitHub 返回 502；
  用 `HTTPS_PROXY=http://127.0.0.1:7897 https_proxy=... HTTP_PROXY=... http_proxy=... git -c http.sslBackend=openssl push origin master`，
  推完确认 `git log origin/master..HEAD` 清空 + CI success。
- **发版必须**用户明确放行（GATE-3.1），不能因为「CI 绿了」就自动打 tag。

---

## 8. 附录：本轮勘察证据

> 命令列是本轮实际执行过的等价形式；正则多选一律写成 `-e` 多模式，
> 避免 Markdown 把竖线当列分隔符。

| 勘察对象 | 关键命令 / 位置 | 得出的结论 |
|---|---|---|
| 核验器结构 | `grep -nE` 多模式匹配 `def` / `class` / `CHECK_` / `STATUS_`；`sed -n '1517,1584p'`（argparse）与 `sed -n '1624,1712p'`（main）`scripts/verify_generation.py` | 7 个 `CHECK_*`（`:96–113`）、`verdict` 在 `:1429`、`main()` 输入校验在 `:1635–1660`、全文无 `KO` 正则 |
| MCP 参数层 | `sed -n '190,285p'`、`'415,480p'`、`'545,575p'` `lib/server.mjs` | `validateArgs` 只遍历 `props`；`buildArgs` 用 `--` 传 `key/value`；三个 schema 全写 `additionalProperties:false` |
| 测试面 | `sed -n '1,130p'`、`'584,600p'`、`'760,780p'` `tests/test_verify_generation.py`；`cat tests/conftest.py` | `run_verify()` 断言 JSON 落盘；`:586` 断言空日志 rc=0；`:766` 断言 skip（F-2 / F-3） |
| 日志 fixture | `sed -n '1,25p'` + `wc -l -c` `tests/fixtures/log_clean.txt` | 17 行 / 809 字节，首行 `[INFO] STM32CubeMX 6.18.1…`，含 `LoadConfig:` / `Generating code under` ⇒ 宽松形态判据不会误伤（F-1 / W0-4） |
| 注入点 | `sed -n '140,200p' scripts/ioc_field.py` | `lines[index] = f"{key}={value}{ending}"` 无换行过滤（W1-1） |
| 编排链 | `grep -nE` 多模式匹配 `shift 2` / `exit "\$VERIFY_RC"` / `KO` `scripts/regen.sh` | 11 处 `shift 2`（`:136–146`）、`:537` 透传、`:403–408/:519–524` 才是 KO 检查（W6-1/2、W0-3） |
| 发布链 | `sed -n '230,270p' tools/check_release.py`；`cat .github/workflows/publish.yml`；`grep -nE` 多模式匹配 `PASS` / `SKIP` / `skip=` `tools/npm_mcp_handshake.mjs` | 无官方 registry、只 WARN；dispatch 无门禁；SKIP 已有三数并列与严格模式（F-5 / F-6 / W5） |
| CI | `grep -nE` 多模式匹配 `node --test` / `pytest tests`；`sed -n '/^  lint:/,/^  [a-z]*:/p'` `.github/workflows/ci.yml` | Node 命令 `node --test tests/node/*.test.mjs`；lint job 刻意不挂 `check_release.py` |
| 状态面 | `grep -nE` 多模式匹配 `无硬件` / `挂起` / `一律缺` / `D1–D30` `SKILL.md README.md`；同法匹配 `合计` / `GATE-2` / `T2.` `docs/TASKBOARD.md` | 过期陈述精确行号；散文 35 与表格 36 不一致（F-4 / W2 / W3） |
| 索引与契约 | `sed -n '1,32p' docs/README.md`；`grep -nE` 多模式匹配 `/2` / `迁移` `references/verify-contract.md` | §2「计划不回改」约定；`:238–239` 升 schema 的判据（§0.1 / F-1） |
| 决策真源 | `grep -n '^### D' docs/DECISIONS.md` | 最大编号 **D36**（W3-3 的 D 编号基准） |

> 本计划是 `74589be` 时点的判断快照。后续若实现发生位移，
> 按 `docs/README.md` §2 约定**追加勘误链接**，不要回改原文。
