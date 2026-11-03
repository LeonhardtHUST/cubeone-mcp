# cubeone-mcp 工程化完备计划（2026-11-04）

> 定位：从"修复完成"（M0–M3 已收口，0.6.2 / 0.7.0 已发布）到"**工程化完备**"的路线图。
> 依据：2026-11-04 00:2x 对仓库实测的审核（7 项发现，见 §0）。
> 纪律：沿用既定规矩——Conventional Commits + 验证等级、每项独立 commit、GATE 先问后做、
> `tools/check_taskboard.py` 每次看板改动后必跑。
> 本计划**未经用户批准不开工**（2026-11-04 00:24 用户指示：先审核、定方向、写计划）。

---

## 0. 审核发现（计划的输入，全部实测）

| # | 级别 | 发现 | 对应批次 |
|---|---|---|---|
| 1 | 🔴 | npm 包 `files` 带的注册指南是错的那本（`mcp-registration.md` 讲外部双 server；真正讲本包注册与 `CUBEONE_*` 的 `npm-publish-and-codebuddy.md` 没进包），且两本均无 0.7.0 fail-closed 说明 | C0 |
| 2 | 🟡 | M3 的 5 个 commit 未发版（`ioc_field` master=1.1.0，npm 0.7.0 里=1.0.0） | C0 |
| 3 | 🟡 | CI 全 ubuntu；win32 分支（大小写归一/junction/cp936）CI 零覆盖。Public 仓库 windows runner 免费 | C1 |
| 4 | 🟡 | 工具通道端到端（handshake 12 项）依赖 gitignored 的 testbeds 素材，只在 Leon 本机验证过 | C1 |
| 5 | ⚪ | `package-lock.json` 仍被 `.gitignore:49` 忽略，CI 用 `npm install` | C2 |
| 6 | ⚪ | 无覆盖率数字与底线 | C2 |
| 7 | ⚪ | Phase 2 整体挂起，但其中"改配置→生成→核验→构建"四段无板可做 | C3 |

**"完备"的定义（六个维度）**：D1 发布物完备（包内容正确、指南与行为一致、版本轴可机器校验）；
D2 质量门禁完备（CI 双平台、覆盖率有底线、端到端进 CI）；D3 用户接入完备（注册→自检→迁移全链路文档）；
D4 硬件段就绪（接板即可开工，预案先行）；D5 治理完备（发布全流程机械校验，人不做算术）；
D6 可维护性（贡献入口、文档导航）。

---

## 1. 批次总览

| 批次 | 内容 | 目标版本 | 依赖 | 预估 | 维度 |
|---|---|---|---|---|---|
| **C0 修正与发版** | 修注册指南 + 换包内指南 + 发 0.7.1 | **0.7.1** | 用户批准 | 1–2 h | D1/D3 |
| **C1 门禁完备** | Windows CI + 冒烟 fixtures 化进 CI | 不发版 | C0（顺手同批亦可） | 2–3 h | D2 |
| **C2 机械化** | lock 入库 + 覆盖率底线 + 版本轴校验脚本 | 不发版 | — | 2 h | D2/D5 |
| **C3 硬件预演** | S4 前四段无板预演 + GATE-2.0 清单成文 | 不发版 | CubeMX 本机可用 | 2–4 h | D4 |
| **C4 可维护性** | CONTRIBUTING / 模板 / 文档导航 / 索引页 | 不发版 | — | 1–2 h | D6 |
| **Phase 2 正式段** | 烧录 / 串口 / L5（原计划不变） | — | GATE-2.0 接板 | 1–2 天 | D4 |

执行序：**C0 → C1 → C2 → C4 可穿插；C3 随时（等的是板子，不是依赖）**。

---

## 2. C0 · 修正与发版（P0——用户可见缺口）

### C0.1 注册指南重写与换包（🔴 发现 1）

1. `docs/guides/npm-publish-and-codebuddy.md`（本包真正的注册指南）：
   - 补 0.7.0 起 `CUBEONE_ALLOWED_ROOTS` **未设 = 拒绝**（BREAKING 标注 + 迁移）；
   - 补 `CUBEONE_ALLOW_NO_ROOTS` / `CUBEONE_REQUIRE_ROOTS` 的语义与取舍；
   - 补**注册后自检**一节：`node tools/npm_mcp_handshake.mjs`（源码用户）或
     「tools/call 一次 `ioc_field get`，看返回是否含 `allowed_roots=…`」两条路径（npm 用户）；
   - 白名单示例从"至少覆盖工程所在盘根，如 `D:\Projects`"**收紧**为"只给实际工程目录"——
     盘根等于没设防，这句是 0.6 时代的话，0.7.0 语义下必须改。
2. `package.json` 的 `files`：`docs/guides/mcp-registration.md` → **`docs/guides/npm-publish-and-codebuddy.md`**
   （或两本都带：`mcp-registration.md` 讲双通道背景，留着无妨，但**主指南必须是后者的名字出现在 README/SKILL 引用链上**）。
3. `README` 快速开始与 `SKILL.md` §0.1/§371 的引用统一指到正确指南；`mcp-registration.md` 头部加一句
   「本页讲 vscode-cube-mcp / platformio.mcp 两个外部 server；**本包自身的注册见另一本**」防误读。
4. 验证：`npm pack --dry-run` 清单出现正确指南；`node tools/npm_mcp_handshake.mjs` 全绿。
   **提交**：`docs(guides): 注册指南对齐 0.7.0 默认拒绝并换入包内（L1）`

### C0.2 发 0.7.1（🟡 发现 2）

- 版本三处 bump 0.7.1（tag/pkg/SKILL）；内容 = M3 的 5 个未发版 commit + C0.1。
- Release 正文照例入库 `docs/releases/`，说明"0.7.1 = 0.7.0 的文档与脚本修正，无行为变更
  （唯一例外：`ioc_field` 的 get 报错文案区分多行歧义/不存在，脚本轴 1.0.0→1.1.0）"。
- 严格走 GATE-3.1（第三次正规执行）：CI 绿 → 出示 → 用户确认 → tag → Release → npm → 看板回填。
  **提交**：`chore(release): v0.7.1 修正批次（含验证等级汇总表）`

### C0.3 用户侧白名单落地（你说的第 1 条）

- 前置是 C0.1（指南先对，配置才有得抄）。
- 动作：在本机 MCP 客户端注册条目 `env` 加 `CUBEONE_ALLOWED_ROOTS`（**只给工程目录**，不给盘根）；
  重启客户端；跑一次自检（C0.1 新增的那节）。
- 属**用户配置操作**，不产 commit；看板不记行（不在仓库交付面内），但可在 D35 里记一条
  「0.7.1 后主用机已配置白名单」的事实。

---

## 3. C1 · 门禁完备（D2）

### C1.1 Windows CI job（🟡 发现 3）

- `ci.yml` 新增 `pytest-windows`（或并入现 job 换 matrix `os: [ubuntu, windows]`，**只 pytest + node 单测**，
  不复制 lint——shellcheck/py_compile 与平台无关）。
- 收益清单（现在 CI 零覆盖的 win32 面）：`checkPath` 大小写归一（组2-4，ubuntu 上是 skip）、
  junction 绕出（组2-6，ubuntu 走的是 symlink 分支）、`path.delimiter=';'`、spawn 行为差异。
- 注意：Windows runner 冷启动慢（~1–2 min），Public 仓库**免费**但别做矩阵——单 job 即可；
  `npm install` 在 Windows 上也慢，node 单测 job 可只在 ubuntu 跑（win32 逻辑测试在 pytest+node 均有，
  node 那份更要紧，**node 单测也进 Windows job**，忍这 1 分钟）。
- **提交**：`ci: 增加 Windows job 覆盖 win32 路径分支（L1）`

### C1.2 冒烟 fixtures 化进 CI（🟡 发现 4）

- 目标：`tools/npm_mcp_handshake.mjs` 的 12 项在 CI 上可跑，不再依赖 Leon 本机的 testbeds。
- 路径：建 `tests/fixtures/e2e/` 最小素材集——一个小 `.ioc`（现成的 `ioc_g474_template.txt` 改名即可）、
  假 `main.c`（复用 `main_g474_template.c`）、假 CubeMX log（复用 `log_clean.txt`）、假 `.mxproject`。
  handshake 脚本加素材定位回退：`testbeds/` 找不到时用 `tests/fixtures/e2e/`。
- **分两步走，别一口吃**：
  1. 先做"无素材版"：T1/T2/T3/T3b/T7/T9/T10/T11（纯协议+门禁，不碰 Python 素材）直接进 CI；
  2. T4/T5/T6/T8 依赖 `.ioc`，等 fixtures 就位后补进。
- **提交**：`test(mcp): 冒烟进 CI——无素材段先行（L1）` + `test(mcp): e2e fixtures 化补齐素材段（L2）`

### C1.3 Node 覆盖率（顺带）

- `node --test --experimental-test-coverage tests/node/*.test.mjs` 只在 **Node 22 档**开（18 无此能力），
  先**只报告不设门槛**——数字出来再定底线（拍脑袋设门槛必翻车）。
- **提交**：`ci: Node 22 档输出单测覆盖率报告（L1）`

---

## 4. C2 · 机械化（D5）

### C2.1 package-lock 入库（⚪ 发现 5，你说的第 3 条）

1. `.gitignore` 删 `package-lock.json` 行；`git add package-lock.json`（43KB，一次性）。
2. `ci.yml` node job：`npm install` → **`npm ci`**，`actions/setup-node` 开 `cache: npm`；
   注释同步改（现在那段"为什么不能用 npm ci"的理由作废，改成"lock 已入库"）。
3. 验证：CI 绿（`npm ci` 走 lock 且命中缓存）。
- **提交**：`build(npm): lock 入库，CI 升级 npm ci 与依赖缓存（L1）`

### C2.2 Python 覆盖率底线

- dev-only 依赖 `pytest-cov`（`scripts/` 运行时仍是纯标准库，不破坏零依赖原则——**测试工具链不是运行时依赖**，这条边界要写进 CONTRIBUTING）。
- 先跑一次拿基线，底线 = 基线 - 1pp（只防回退，不追指标）。
- **提交**：`test: 引入 pytest-cov 并设覆盖率回退底线（L2）`

### C2.3 版本轴校验脚本 `tools/check_release.py`

- 判据：① `git tag` 最新版号 == `package.json.version` == SKILL frontmatter == SKILL 正文状态行
  （D33 §33.2 的机器化，人不再肉眼对四行）；② 该版本在 npm `dist-tags` 上存在（需网络，本地跑、CI 可选）；
  ③ `docs/releases/` 有对应正文文件；④ master 领先 tag 的 commit 数 > 0 时打印提醒
  「有未发版改动，下次发版记得收口」。
- 接入：发布前手动跑 + 可选挂 CI lint job（②的网络查询加超时降级）。
- **提交**：`feat(tools): 版本轴与发布收口校验脚本（L2）`

### C2.4 发布 SOP 成文（D35）

- 把 0.6.2/0.7.0 两次实跑的流程固化成一页：GATE-3.1 证据包清单 → tag → Release → npm →
  看板回填 → `check_taskboard.py` → `check_release.py`。含两个已踩的坑（release 事件 workflow 取自
  tag 点、幂等守卫对旧 tag 的不可追溯性）。
- **提交**：`docs(decisions): D35 发布流程 SOP（L0）`

---

## 5. C3 · 硬件段预演（D4，不等板子的部分）

### C3.1 S4 前四段无板预演

- S4 全链 = 改配置 → 生成 → 核验 → 构建 → **烧录 → 串口**（后两段等板）。
- 现在就能做：在 `testbeds/` 的 `NUEDC_2027/G474_01_gpio` 副本上，把前四段完整走一遍并产出 L4 证据链
  （现有 S1 已做过 G474 模板，但 **NUEDC 工程是另一份 `.ioc`，工程特异性问题是 S1 测不出来的**）。
- 产出：`docs/reports/s4-dryrun-*.md`；如遇坑（引脚冲突/外设缺失）当场修，属计划内。
- **提交**：`test(scenario): S4 无板预演前四段（L4）`

### C3.2 GATE-2.0 接板清单成文

- 一页 checklist：探针型号与 doctor 预期输出、供电/共地、目标板安全确认（不接执行器）、
  COM 口发现命令、首烧目标（用已构建的 S4 产物）、串口预期（boot log 还是裸 printf）。
- 板子到手当天照单执行，不再临场翻文档。
- **提交**：`docs(guides): GATE-2.0 接板日清单（L0）`

### C3.3 T3.3 占位

- SKILL.md 终版的「Phase 2 实测状态」节先立骨架（占位标注"无硬件不做能力宣称"），
  接板后填数——终版任务从"待开始"转"进行中"。

---

## 6. C4 · 可维护性（D6）

| 项 | 动作 |
|---|---|
| CONTRIBUTING.md | 怎么跑三层测试、提交规范（type(scope) + L 等级）、单写者原则、**"scripts 运行时零依赖，测试工具链不算运行时依赖"** 的边界声明、L0–L5 定义引用 |
| issue/PR 模板 | `.github/ISSUE_TEMPLATE/` + `PULL_REQUEST_TEMPLATE.md`（PR 模板直接印上"贴 pytest/node/handshake 三条尾行 + L 等级声明"） |
| 文档导航 | `docs/README.md` 一页索引：计划 → 决策 → 看板 → 报告 → 发布台账，各一行的"什么时候看" |
| releases 索引 | `docs/releases/README.md`：版本 × 内容 × 三证链接对照表（手写一次，之后发版追加） |
| ruff（决策点） | 倾向**最小集**（E/F/W + line-length 120，dev-only）。若嫌引入依赖，可不做——现有 77 例测试已经守住了大部分回归面，ruff 只是小钱换风格一致性 |

---

## 7. 执行序与里程碑

```
C0.1 修指南 ──► C0.2 发 0.7.1 ──► C0.3 用户配白名单（无 commit）
      │
      └──► C1.1 Windows CI ──► C1.2 冒烟进 CI（两步）──► C1.3 覆盖率报告
C2.1 lock ──► C2.2 覆盖率底线 ──► C2.3 check_release ──► C2.4 D35
C3.1 S4 预演（随时，CubeMX 在本机）   C3.2/C3.3（随时）
C4（收尾穿插）
GATE-2.0 接板 ──► Phase 2 正式段（烧录/串口/L5，原计划不变）
```

里程碑判据：
- **M-C0**：npm 0.7.1 的包内指南正确、用户本机白名单已配（自检通过）
- **M-C1**：CI 出现 Windows job 且 win32 分支真跑（skip 数下降）
- **M-C2**：`npm ci` + 缓存生效；`check_release.py` 一条命令核完版本轴
- **M-C3**：S4 前四段 L4 证据链落盘 + 接板清单成文
- **M-C4**：新人 clone 后 30 分钟内能跑通三层测试并知道去哪看文档

---

## 8. 风险与决策点（开工前要你点头的）

| # | 决策点 | 我的倾向 | 反方理由 |
|---|---|---|---|
| 1 | Windows CI 加不加 | **加**（免费、补唯一盲区） | Windows job 慢 1–2 分钟；本仓单人维护，本机就是 Windows，CI 价值打折——但"本机测过"正是 0.6.x 时代 CI 三次全红的教训来源 |
| 2 | 冒烟进 CI 的深度 | **两步走**（无素材段先行） | 一步到位需要先建 fixtures，若假素材造得不真（log 格式差异），T6 可能假红——分步可控 |
| 3 | lock 入库 | **入**（可复现 + 缓存） | 每次 SDK 升级多一个 43KB diff 的 review 噪音 |
| 4 | 覆盖率底线 | **只防回退，不追指标** | 指标一旦成为 KPI 就会催生为覆盖而覆盖的测试 |
| 5 | ruff | **最小集**或**不做**（二选一） | 引 dev 依赖；现有测试密度已较高 |
| 6 | CHANGELOG.md | **不做**，`docs/releases/` + 索引页已够 | 单文件 CHANGELOG 与 docs/releases/ 必然二源失真 |
| 7 | 2.0 核验器（删顶层弃用字段） | **不排期**，留给真实的 schema 变更需求 | 无消费者催促的破坏版是纯成本 |

---

## 9. 与既有计划的关系

- 原 `docs/2026-11-03-agent-team-plan.md`（Phase 0–3）：已完成 24/25（仅 T3.3 待开始，阻塞于 Phase 2）。
- `docs/2026-11-03-remediation-plan.md`（M0–M4）：M0–M3 已完成；**M4（Phase 2 接板段）并入本计划 §5/§7 的 C3 + Phase 2 正式段**，原计划不再单独维护。
- 本计划所有批次沿用：看板记行 + `check_taskboard.py` 校验 + GATE 纪律 + D33 版本轴 + D34 治理元规则。

---

*审核于 2026-11-04 00:2x 完成（全部结论有实测命令支撑）；计划待用户批准后按 §7 执行序开工。*
