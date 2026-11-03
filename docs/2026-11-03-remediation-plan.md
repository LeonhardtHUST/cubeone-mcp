# cubeone-mcp 修复计划（依据 2026-11-03 交付审定报告）

> 生成时间：2026-11-03 · 依据：`.workbuddy/audit/2026-11-03-审定报告.md`（含四份分报告）
> 审定结论：有条件通过——🔴 0 项、🟡 10 项；本计划将其全部收敛为可执行任务
> 提交纪律：全部走 Conventional Commits（`type(scope): 中文简述`）+ 验证等级声明；禁止 AI 署名尾注
> 硬关卡：本计划含 2 处用户决策门（R-G1、R-G2），未确认不得执行对应动作

---

## 0. 总览：批次、版本与依赖

| 批次 | 内容 | 目标版本 | 依赖 | 预估 |
|---|---|---|---|---|
| **M0 治理回填** | 状态记账/决策记录/证据指针修正（纯文档，零代码风险） | 不发版 | R-G1 用户确认 | 0.5–1 h |
| **M1 接缝修复** | server.mjs 四处代码修复 + Node 测试基建 + 发布物补全 | **0.6.2** | M0（D33 先行） | 2–3 h |
| **M2 安全加固** | 白名单 fail-closed / realpath / restore 原子化 | **0.7.0** | M1 | 1–2 h |
| **M3 机制固化** | 看板防呆脚本 + CI 一致性校验 + 治理元规则入册 | 不发版 | M0 | 1 h |
| **M4 硬件阶段** | Phase 2 接板后任务（不变，沿用原计划 §3） | — | GATE-2.0 接板 | 原计划 1–2 天 |

执行顺序：**M0 → M1（发 0.6.2）→ M2（发 0.7.0）与 M3 可并行 → M4 等接板**。

---

## 1. M0 · 治理回填（对应审定报告 §1.2 高危发现与异议 1/3/7）

### R-G1（用户决策门）npm 工具通道的追溯认定 → DECISIONS D33

- **问题**：npm/MCP 化（bin/lib/publish.yml/包 0.6.1）推翻调研报告「不是又一个 MCP server」的架构决策，零决策记录、零用户授权（审定报告发现①，最高危）。
- **动作**：由执行方向用户出示本条，二选一并落 `docs/DECISIONS.md` D33：
  - **方案 a（推荐）**：追溯认定 npm 通道为正式交付物形态。理由：产物本身架构评级 A、动态测评 94.1%、给 MCP 注册提供了标准通道。D33 须写明：① 追溯授权；② 版本轴治理规则（见下）；③ 此后任何形态/技术栈/发布渠道变更必须先开 GATE。
  - **方案 b**：判定为范围失控，冻结 npm 线（停止 publish、README 标注 unmaintained），后续回归「Skill + 脚本 + 文档」形态。
- **版本轴治理规则（随 D33 固化，解异议 7）**：单轴对外——`git tag = package.json = SKILL.md frontmatter`（如 v0.6.2/0.6.2/0.6.2）；核验器 `verify_generation.py` 保持独立 1.x 轴（判据契约演进）；**每次 tag 必须同时有 GitHub Release + npm 发布 + 看板回填，三者缺一视为发布未收口**。
- **验收**：DECISIONS.md 出现 D33（含用户确认时间与方式）；`grep -c "D33" docs/DECISIONS.md` ≥ 1。
- **提交**：`docs(decisions): D33 追溯认定 npm 工具通道并固定版本轴治理（验证等级：L0）`

### R-A2 TASKBOARD 回填（三重失真修正，审定发现②）

`docs/TASKBOARD.md` 逐处修正：

1. **T3.5 行**：`待开始` → `已完成`；补证据：tag `v0.1.0`（GitHub Release 122 行含 L 等级表）、`v0.1.1`、`v0.6.1`（tag 有、release 无——按 D33 规则补发 v0.6.1 release notes 或在行内注明补发计划）。
2. **§4 进度快照**：重算为任务表真实值（Phase 0: 5/5、Phase 1: 9/9、Phase 2: 0/6 挂起、Phase 3: 4/5 含 T3.4 关闭）；快照区头部加注「本区由 M3 的校验脚本生成/校验，禁止手写」。
3. **GATE 状态表**：GATE-0 → `✅已通过（D12 用户裁定）`；GATE-1.1/1.2 → `✅视为通过（条件满足，证据链齐；未走演示流程，事后补记）`；GATE-3.1 → `⚠️事后补审（v0.1.0/v0.6.1 发布未过本关卡，0.6.2 起严格执行）`。
4. **角色入册**：§0 角色表增「计划外角色登记」小节：`software-engineer`/`software-qa-engineer`（T0.4 冒烟实现与复核）、`release-engineer`（T3.1/T3.2，后由 lead 收口）——各写一行授权范围；同时记录计划 8 角色中 evaluator/hil-agent/ci-agent 的出场情况（解异议 2）。
- **提交**：`docs(taskboard): 回填 T3.5/GATE 状态、重算快照并补计划外角色入册（L0）`

### R-A3 README 版本表对齐（审定发现 S1/Y5——npm 公开页正展示错误版本）

- `README.md:224-234`「三个版本号，别混」表：仓库发布标签 `v0.1.1`→`v0.6.2（发布后）`、SKILL.md version `0.6.0`→`0.6.2`；并在该节加一句**发布轴规则**引用（指向 D33）。
- **提交**：`docs(readme): 版本表对齐 0.6.x 实况并引用 D33 版本轴规则（L0）`

### R-A4 证据指针修正（审定发现③，69-vs-61）

1. 重跑 `python -m pytest tests/ -q --basetemp <干净目录> > docs/logs/phase1/t1.2-pytest-v1.2-recheck.log`，归档当前真实数字（74 passed）。
2. `docs/TASKBOARD.md` T1.2 行：「69 passed」改为「v1.1 轮 61 passed（t1.2-pytest.log）；v1.2 轮复核 74 passed（…-recheck.log）」，消除无对应的 69。
3. `docs/reports/t1.2-verifier-contract.md:312` 同步更正。
4. T0.4 行的行数/指纹双口径：统一为当前值（1481 行 / sha256 以 `git hash-object tools/mcp_smoke.py` 重算），历史值移入括号注记。
5. T1.6 构建时长口径：统一 12.06s（s1-build.log 为准），release notes 的 10.95s 在 M1 发版说明中不再复用。
- **提交**：`docs(taskboard): 修正证据指针并归档 v1.2 轮 pytest 复核日志（L1）`

### R-A5 docs/evaluations 化石处置（审定异议 7 附带项）

- 产出 3 段各一句话的微型报告 `docs/evaluations/2026-11-03-t3.4-closure.md`：① CubeMX 2.1.1 兼容性=推迟（单版本机器，成本不匹配）；② CMake 流=推迟（无用户需求）；③ strtt RTT=不做（无使用者）。落盘后 `docs/evaluations/` 不再是空目录，TASKBOARD §3 该行证据列补链接。
- **提交**：`docs(evaluations): T3.4 关闭结论落盘消除空目录化石（L0）`

---

## 2. M1 · 接缝修复 + 测试基建（目标 0.6.2）

> 全部改动集中在 `lib/server.mjs`（399 行）与 `package.json`；每项先写测试再改实现（F4 的教训：安全门禁在 JS 侧却零测试）。

### R-B1 退出码映射白名单化（F1，审定最重要代码发现）

**位置**：`lib/server.mjs:214-217`（`isExecFailure`）+ `callTool` 调用点（:316/:318）。

**现状缺陷**：只认 `error / status===null / status===2`。WindowsApps Python 桩 exit 9009 → `isError=false`；Python 未捕获异常 exit 1 → 被误判为「域内结论」，traceback 混进正文。

**改法**（新增 `structured` 入参）：

```js
function isExecFailure(res, structured) {
  if (res.error) return true;            // ENOENT / ETIMEDOUT / EACCES
  if (res.status === null) return true;  // 被信号杀死 / 超时
  if (res.status === 0) return false;
  if (res.status === 1) {
    // exit 1 是域内结论「仅当」核验器落了结构化 JSON；裸 exit 1（崩溃）按执行失败
    return structured == null || /Traceback \(most recent call last\)/.test(res.stderr || "");
  }
  return true; // 其余一切码（含 9009 商店桩）：执行层失败，isError=true
}
```

`callTool` 中两处调用改为 `isExecFailure(res, structured)`。`head` 组装行（:316）同步。

**回归用例**（进 R-D1）：status 0→false；1+有 JSON→false；1+无 JSON→true；1+stderr 含 Traceback→true；2→true；9009→true；null→true；error→true。

**验收**：单测全绿；手工对照——`CUBEONE_PYTHON=C:\Windows\System32\cmd.exe` 类桩不可用时仍报可读错误（ENOENT 路径已有 U4.5 实测范式）。
**提交**：`fix(mcp): 未知退出码与裸崩溃一律按执行层失败处理（L2）`

### R-B2 子进程注入 PYTHONIOENCODING（F2，一行修复）

**位置**：`lib/server.mjs:192-197` spawnSync options。

```js
res = spawnSync(pythonExe(), fullArgs, {
  encoding: "utf8",
  timeout: 120_000,
  maxBuffer: 16 * 1024 * 1024,
  windowsHide: true,
  env: { ...process.env, PYTHONIOENCODING: "utf-8" },
});
```

**验收**：在中文 Windows 上经 MCP 通道触发一次 `input-error`（如 `--log` 指向不存在文件），返回文本中文无乱码（现有 `npm_mcp_handshake.mjs` 只断言 structuredContent，测不出此问题——需补一条断言 stdout 中文可读）。
**提交**：`fix(mcp): 子进程注入 PYTHONIOENCODING 消除 cp936 中文乱码（L2）`

### R-B3 工具入口执行 inputSchema 必填校验（U4.4 唯一 FAIL）

**位置**：`lib/server.mjs` 新增 `validateArgs()`，在 `callTool`（:294-299）`gateArgs` 之前调用。

**规则**（轻量实现，不引第三方 AJV——保持零依赖）：
- `required` 数组逐项：`undefined/null` → 错误（注意 `expect` 合法空串，只查存在不查长度）；
- `action` 的 enum 校验；
- 类型抽查：`string` 字段非 string、`array` 字段非数组、`boolean` 字段非布尔 → 错误；
- 错误返回 `textResult("[cubeone-mcp][参数错误] 缺少必填参数 log / main_c / …（见 tools/list 的 inputSchema）", undefined, true)`——杜绝 `undefined` 透传到 Python 的误导消息。

**验收**：`tools/call verify_generation {}` → isError=true 且消息为参数错误清单，不含字面量 `undefined`；正样本调用不受影响。
**提交**：`feat(mcp): 工具入口执行 inputSchema 必填与类型校验（L2）`

### R-B4 ioc_field 位置参数加 `--` 分隔（F9/Y3）

**位置**：`lib/server.mjs:286-290`（`buildArgs` ioc_field 分支）。

**改法**：选项在前、`--` 之后只放位置参数，杜绝 value 以 `-`/`--` 开头被 argparse 当选项（`-h` 假成功、`--dry-run` 静默改写盘语义）：

```js
} else if (toolName === "ioc_field") {
  if (a.action === "set" && a.dry_run) args.push("--dry-run");
  args.push("--ioc", a.ioc, "--");
  args.push(a.action, a.key);
  if (a.action === "set" && a.value !== undefined) args.push(a.value);
}
```

**注意**：需同步核对 `scripts/ioc_field.py` 的 argparse 定义顺序（位置参数 action/key/value 均在 `--` 后可正确解析；`--dry-run` 已前置）。若脚本侧对 `--` 后取参有假设，按脚本实际行为调整。
**验收**：单测：`value="-h"`、`"--dry-run"`、`"--evil"` 经 buildArgs 后均在 `--` 之后；e2e：set value="-h" 在 read_only+full 两策略下行为符合预期（full 下真实写盘值为 `-h` 字面量而非打印 help）。
**提交**：`fix(mcp): ioc_field 位置参数加 -- 分隔防选项语义误读（L2）`

### R-B5 npm 发布物补全（F3）

**位置**：`package.json:25-33` `files` 数组。

- 增 `"scripts/regen.sh"`（SKILL.md §1.1 称其「唯一不可替代」，必须随包）；
- 增 `"docs/guides/mcp-registration.md"`（SKILL.md §0.1 引用它，npm 用户当前看不到）；
- 同步在 `SKILL.md` §1.1 表格 regen.sh 行加一句：「包内可用，但编排 CubeMX 生成需本机存在 CubeMX/JRE（路径可用 `ST_CUBEMX_JRE`/`ST_CUBEMX_EXE` 覆盖）」。

**验收**：`npm pack --dry-run` 清单出现两文件；CI publish.yml 的 pack 预检步骤自动覆盖。
**提交**：`build(npm): 发布物补 regen.sh 与 MCP 注册指南（L1）`

### R-B6 未知工具消息改进（低优先，顺手）

**位置**：`lib/server.mjs:295-297`。消息从 `未知工具：no_such_tool` 扩为附可用工具清单：`未知工具：no_such_tool。可用：verify_generation / ioc_backup / ioc_field`。

### R-D1 Node 层最小单测（F4——安全门禁在 JS 却零测试）

**新增**：`tests/node/server.test.mjs`（node:test + node:assert，零新依赖）。

为可测性，`lib/server.mjs` 将以下纯函数追加到既有 `export`（`main` 已导出，不改协议行为）：`isExecFailure`、`checkPath`、`buildArgs`、`validateArgs`、`policy`、`allowedRoots`。

**用例集（≥18 例）**：

| 组 | 覆盖 |
|---|---|
| isExecFailure | R-B1 的 8 个状态矩阵 |
| checkPath | 白名单内放行；`D:\Projects` vs `D:\ProjectsEvil` 前缀撞车拒绝；`..\` 越界拒绝；win32 大小写归一放行；roots 未设 → ok+note（0.6.2 行为快照，0.7.0 改 fail-closed 后更新期望） |
| buildArgs | ioc_field 的 `--` 分隔（R-B4）；verify_generation 数组型参数逐个透传 |
| validateArgs | 缺 required；expect 空串合法；action 越界 enum |
| e2e（可选，CI 上跑） | spawn `node bin/cubeone-mcp.mjs` → initialize → tools/list 断言 3 工具 required 非空 → `tools/call verify_generation {}` 断言参数错误且无 `undefined` 字样 |

**验收**：`node --test tests/node/*.test.mjs` 全绿（**命令已更正**：原写目录形式 `node --test tests/node/`，
实测 Node 22.22.2 会把目录当模块加载并报 `MODULE_NOT_FOUND`，而 Node 18.20.8 会递归展开 —— 同一条命令
跨版本不可移植。CI 因此改用 shell glob，见 `.github/workflows/ci.yml` 的 node job 注释）。
**提交**：`test(mcp): Node 层最小单测覆盖门禁、退出码映射与参数校验（L2）`

### R-D2 CI 增加 Node job

**位置**：`.github/workflows/ci.yml` 新增 job `node`（ubuntu + node 18/20/22 matrix，`actions/setup-node@v5`），步骤：checkout → setup-node → `npm install` → `node --test tests/node/*.test.mjs`（**文件 glob，不是目录**，原因见 R-D1 验收段的跨版本实测）。注意 18 为 engines 下限，正好守住语法兼容。

**验收**：Actions run 全绿（参照 T3.1 首跑三次全红的教训：本 job 不依赖任何本机路径/素材，e2e 用临时目录样本）。
**提交**：`ci: 增加 Node 测试矩阵守护 MCP 封装层（L1）`

### M1 收口：0.6.2 发版流程（严格走关卡，修复「发布不留痕」）

1. 前置：M0 全部合入（D33 在册）→ `python -m pytest tests/ -q` 74+ 全绿 → `node --test tests/node/*.test.mjs` 全绿 → `node tools/npm_mcp_handshake.mjs` 冒烟 PASS（含 R-B2 的中文断言增补）。
2. 版本三处同步 bump 0.6.2：`package.json` / `SKILL.md` frontmatter /（发版时）git tag。
3. README 版本表指向 0.6.2；TASKBOARD 新增「M1 修复批次」任务行并即时更新。
4. **R-G2（用户决策门）= GATE-3.1 正规执行**：向用户出示 CI 绿 + 文档包 + 变更摘要，确认后才打 tag。
5. `chore(release): v0.6.2 修复批次（含验证等级汇总表）` → tag `v0.6.2` → push → GitHub Release（含 L 等级表）→ CI Trusted Publisher 自动发 npm。
6. **发布后回填（半小时内）**：TASKBOARD 记录 tag/release/npm 三证齐全——这是对审定「发布线做事不留痕」的直接闭环。

---

## 3. M2 · 安全加固（目标 0.7.0，行为变更版）

### R-C1 白名单 fail-open → fail-closed（Y1）

**分两步**：
- **0.6.2（随 M1）**：README 安全节与 `SKILL.md` §0 增显式警告：「`CUBEONE_ALLOWED_ROOTS` 未设置 = 无路径限制（每次调用会回显『未设置』）」；新增可选 env `CUBEONE_REQUIRE_ROOTS=1`：设置后未配置 roots 时 server 启动即退出（stderr 说明配置方法）。
- **0.7.0**：默认 fail-closed（未设 roots 拒绝所有路径参数），显式逃生门 env `CUBEONE_ALLOW_NO_ROOTS=1` 保留旧行为并在返回文本标注「宽松模式」。README/SKILL.md 同步 BREAKING 说明。

**提交**：`feat(mcp): 未设白名单默认拒绝并保留显式宽松逃生门（L2）`

### R-C2 路径校验解析物理路径（Y2/F14）

**位置**：`lib/server.mjs` `checkPath`（:61-72）。

```js
import { realpathSync } from "node:fs";
function physical(p) {
  try { return realpathSync(p); } catch { return path.resolve(p); } // 不存在的路径退化为词法解析
}
```

校验时对 root 与目标均取 `physical()` 后再前缀比较（win32 双侧 lowercase）。白名单内 junction/symlink 指向界外 → 物理路径界外 → 拒绝。**残余风险如实写进注释**：TOCTOU（校验后链接被换）不防，威胁模型为 agent 误操作而非对抗者。

**验收**：单测新增：临时目录内建 junction（Windows `mklink /J`；CI 用 symlink）指向界外 → checkPath 拒绝。
**提交**：`feat(mcp): 路径白名单解析物理路径防 junction 绕出（L2）`

### R-C3 restore 原子化 + 完整性核对（F6）

**位置**：`scripts/ioc_field.py` 无关；`scripts/ioc_backup.py:147-173` restore 分支。

- 还原改为：写临时文件（同目录 mkstemp）→ `os.replace` 覆盖 `.ioc`（与 backup 对称的原子标准）；
- 还原前核对 `.ioc.bak` 的 sha256 与 backup 记录（backup JSON 已存摘要）一致，不一致拒绝还原并报「备份疑似被篡改/部分写入」；
- 单测：`tests/test_ioc_backup.py` 增 3 例（还原成功后 sha256 等于原件、损坏 .bak 拒还原、还原中途模拟失败不留半份——可通过临时文件命名断言）。

**提交**：`fix(scripts): restore 原子化并复核备份完整性（L2）`

### R-C4 report_md 写行为披露（Y4）

- `lib/server.mjs` verify_generation 工具 description 增：「report_md 会写 Markdown 报告文件——read_only 下也允许（属证据输出），路径仍受白名单校验」；
- `SKILL.md` §1.3 同步一句。若 R-G1 方案 b（冻结 npm 线）被选，此项照做（脚本直调同样存在）。

---

## 4. M3 · 机制固化（解审定对原计划的 7 条异议）

### R-E1 看板防呆：一致性校验脚本 + CI 步骤（异议 3 的机器纪律）

**新增** `tools/check_taskboard.py`（纯标准库，零依赖）：
1. 解析 `docs/TASKBOARD.md` 任务表 → 统计各状态数 → 与 §4 快照数字比对，不一致 exit 1；
2. 抽取证据链接列的仓内路径 → 逐一 `os.path.exists`，缺失 exit 1（可抓住「指向 gitignored/未归档文件」类失真）；
3. 一致性规则：`git tag` 含 `v0.6.x` 时 T3.5 不得为「待开始」（防重复发布事故——审定报告 §三.6 的直接风险）；
4. **CI 接入**：ci.yml 增一步 `python tools/check_taskboard.py`。

**验收**：脚本对当前（M0 修正后的）看板跑通 exit 0；故意改坏一处状态能被抓（自测）。
**提交**：`feat(tools): 看板一致性校验脚本并入 CI 防状态失真（L2）`

### R-E2 治理元规则入册（异议 1/4/5，写入 DECISIONS D34）

`docs/DECISIONS.md` 新增 D34「形态演进与治理元规则」：
1. **形态变更元规则**：任何改变交付物形态/技术栈/发布渠道的演进，无论多小，必须先开 GATE（用户确认）+ DECISIONS 条目，缺一不得合入；
2. **角色入册协议**：计划外角色须记入 TASKBOARD 角色登记节（授权人+范围）；计划角色表改双列（出场/未出场+原因）；
3. **L 等级降级须批准**：DoD 声明的 L 等级下调须 lead 批准 + DECISIONS 条目 + 看板标注「原 Lx → 实 Ly」；
4. **节奏条款**：进度超前时时间盈余默认归属「提前交付+加强验证」，扩围需显式授权；
5. 后续 Phase 计划文档以此为模板增补（不回改已交付的 2026-11-03 计划，仅追加勘误链接）。

**提交**：`docs(decisions): D34 形态演进元规则与角色/L等级治理条款（L0）`

### R-E3 弃用字段口径统一（F5）

`scripts/verify_generation.py:1226-1245`：弃用提示从「将于 v1.2 删除」改为「v1.x 保留兼容；schema /2 起请读 `inputs.*`，v2.0 移除顶层字段」；`references/verify-contract.md` §3 同步改口。**不实际删字段**（避免破坏 structuredContent 消费者，删除留给 2.0 破坏版）。

**提交**：`fix(scripts): 弃用字段口径统一为 v2.0 移除（L1）`

### R-E4 Nit 批量清理（F7/F8/F11/F12 + 环境注记）

| 项 | 动作 |
|---|---|
| F7 | `verify_generation.py:29-43` docstring 检查项表补第 7 项 `pins_present` |
| F8 | `ioc_field.py:124-127` get 遇同名多行时区分「多行歧义」与「不存在」两种报错 |
| F11 | `tools/mcp_smoke.py` 头部加归属注释「冒烟对象为 vscode-cube-mcp（外部 server），非本包通道；本包冒烟见 npm_mcp_handshake.mjs」 |
| F12 | `regen.sh:24` 硬编码 PortableGit PATH 行加注释「本机便利项，他机无害可删；macOS BSD sort 无 -V 为已知边界」 |
| 环境注记 | README FAQ 增：pytest 临时根堆积可能被安全软件拦截清理 → 用 `--basetemp`（齐回归实测发现） |

**提交**：`chore(scripts): 审计 Nit 批量清理与 README FAQ 增补（L1）`

---

## 5. M4 · Phase 2（接板后，沿用原计划不变）

按 `docs/2026-11-03-agent-team-plan.md` §3 执行 GATE-2.0（接板确认）→ T2.1–T2.6 → GATE-2.1（首次烧录安全确认）→ GATE-2.2（S4 收口）。唯一增补：

- **T3.3（SKILL.md 终版）**：接板后合并 §6 串口/烧录实测数据再定稿，并在 frontmatter 补「Phase 2 实测状态」；在此之前保持 v0.6.1/0.6.2 现状声明「无硬件不做能力宣称」（现状处理正确，无需提前动作）。
- 烧录/串口全部动作**过 R-E2 的元规则检验**（涉及交付能力宣称形态时同样走 GATE）。

---

## 6. 任务总表（执行序）

| 序 | ID | 任务 | 文件 | 批次 | 用户门 | 验证 |
|---|---|---|---|---|---|---|
| 1 | R-G1 | D33 npm 通道追溯认定 + 版本轴规则 | docs/DECISIONS.md | M0 | **✋必须** | grep D33 |
| 2 | R-A2 | 看板回填（T3.5/快照/GATE/角色） | docs/TASKBOARD.md | M0 | — | R-E1 脚本跑通 |
| 3 | R-A3 | README 版本表 | README.md | M0 | — | 人工核对 0.6.2 |
| 4 | R-A4 | 证据指针修正 + 归档复核日志 | TASKBOARD/reports/logs | M0 | — | 日志尾 74 passed |
| 5 | R-A5 | evaluations 微型报告 | docs/evaluations/ | M0 | — | 目录非空 |
| 6 | R-B1 | isExecFailure 白名单化 | lib/server.mjs:214 | M1 | — | node 单测 8 例 |
| 7 | R-B2 | PYTHONIOENCODING | lib/server.mjs:192 | M1 | — | 中文报错无乱码 |
| 8 | R-B3 | inputSchema 校验 | lib/server.mjs:294 | M1 | — | e2e 无 undefined |
| 9 | R-B4 | ioc_field `--` 分隔 | lib/server.mjs:286 | M1 | — | value="-h" 落盘字面量 |
| 10 | R-B5 | files 补 regen.sh/指南 | package.json | M1 | — | npm pack --dry-run |
| 11 | R-B6 | 未知工具消息 | lib/server.mjs:295 | M1 | — | e2e |
| 12 | R-D1 | Node 单测 | tests/node/ | M1 | — | `node --test tests/node/*.test.mjs` |
| 13 | R-D2 | CI Node job | .github/workflows/ci.yml | M1 | — | Actions 绿 |
| 14 | R-G2 | **0.6.2 发版（GATE-3.1 正规执行）** | 全仓 | M1 | **✋必须** | tag+release+npm+看板四证 |
| 15 | R-C1 | fail-closed 两步走 | server.mjs/README/SKILL | M2 | — | 0.7.0 单测更新 |
| 16 | R-C2 | realpath 白名单 | lib/server.mjs:61 | M2 | — | junction 单测 |
| 17 | R-C3 | restore 原子化 | scripts/ioc_backup.py:147 | M2 | — | pytest 3 例 |
| 18 | R-C4 | report_md 披露 | server.mjs/SKILL.md | M2 | — | 文档核对 |
| 19 | R-E1 | 看板校验脚本 + CI | tools/check_taskboard.py | M3 | — | exit 0 / 抓错自测 |
| 20 | R-E2 | D34 治理元规则 | docs/DECISIONS.md | M3 | — | grep D34 |
| 21 | R-E3 | 弃用口径统一 | verify_generation.py:1226 | M3 | — | 契约文档一致 |
| 22 | R-E4 | Nit 批量 | 多文件 | M3 | — | pytest + 人工 |
| 23 | — | Phase 2 接板任务（原计划） | — | M4 | GATE-2.0/2.1 | L5 证据链 |

## 7. 风险与回滚

- **R-B1 行为变更风险**：exit 1 且无 structuredContent 的合法路径（若存在）会被升为 isError。缓解：先用 e2e 跑一遍 U3.2b fail 样本确认域内 FAIL 恒有 JSON 落盘；若有例外，把该路径列入白名单并注释原因。
- **R-B4 传参顺序风险**：argparse 对 `--` 的消费行为以 `ioc_field.py` 实测为准，先写单测锚定再改。
- **R-C1（0.7.0 fail-closed）**：破坏现有「未设 roots 即用」的用户。缓解：0.6.2 先给一个版本的显式警告 + opt-in 严格模式，release notes 写明迁移方法。
- **回滚原则**：每项独立 commit（禁大杂烩提交），出问题按 SKILL.md §4 单项 revert；发版类操作以 tag 为锚。
- **全局红线（沿用）**：只在本仓改动；不碰 testbeds/ 与模板原仓；烧录类动作仍走 GATE-2.1。

---

*本计划为审定报告的直接执行件。执行时每完成一项在 TASKBOARD 增行记账（含证据链接），M1/M2 发版严格走 R-G2 与 D33 版本轴规则。*
