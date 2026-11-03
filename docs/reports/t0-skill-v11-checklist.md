# T0 只读核对：v1.1 契约 vs 当前实现（差异清单）

> 作者：`skill-author` · 时间：2026-11-03 12:1x · 性质：**只读审计**
> 本次核对未修改、未运行、未暂存任何他人文件；所有结论均可用下方命令复现。
> 用途：给 `team-lead` 判断哪些并入 v1.1、哪些留 v1.2，再由 lead 一次性转给 `verifier-dev`。
> **本文件不是契约，不构成对 `verifier-dev` 的需求单**；以 `docs/reports/t1.2-verifier-contract.md` 为准。

## 0. 审计时的文件快照（复现基线）

| 文件 | mtime | 大小 |
|---|---|---|
| `scripts/verify_generation.py` | 12:10:45 | 47256 |
| `scripts/regen.sh` | 12:10:16 | 19216 |
| `scripts/ioc_field.py` | 12:08:09 | 9335 |
| `scripts/ioc_backup.py` | 11:53:06 | 9459 |
| `tests/test_verify_generation.py` | 12:13:32 | 27593 |
| `tests/test_ioc_field.py` | 12:12:59 | 6044 |
| `tests/test_regen_preflight.py` | 12:13:14 | 7431 |

⚠️ 这是**时间点快照**。`verifier-dev` 正在两个 commit 之间作业，mtime 之后的行号/内容可能已变；
若与本文件不符，**以代码当前状态为准**，本文件只用于定位"漏改项"。

复现命令：

```bash
grep -n '^SCHEMA\|^CHECK_[A-Z_]* = ' scripts/verify_generation.py
grep -n 'add_argument' scripts/verify_generation.py | tail -12
grep -c 'expect_pins\|pins_present' scripts/verify_generation.py scripts/regen.sh
grep -n 'require-clean\|allow-dirty-ioc\|RESET_ASK_FOR_MIGRATE' scripts/regen.sh
grep -n 'effective_allow_signals\|report_inputs' scripts/verify_generation.py
```

## 1. 优先级定义

| 级别 | 含义 | 处置建议 |
|---|---|---|
| **P0** | 会让**当前这版 commit 立刻不成立**：对外输出已与契约不一致，或与已定决策正面冲突 | 本轮必须改，不能留给 v1.2 |
| **P1** | v1.1 收口前必须改，但**可随第 7 项 `pins_present` 一起**进同一个 commit | 并入 v1.1 |
| **P2** | 不影响正确性，属文档/契约完备性 | 留 v1.2 |

## 2. 🔴 需要 lead 优先裁决的 3 条（P0）

### P0-1 · `schema` 仍是 `/1`，但形状已经变了

- **现状**：`SCHEMA = "platform32.verify_generation/1"`；`blocking: bool` 已生效（`CheckResult.blocking`，`to_dict()` 输出 `"blocking"`），`level` 已不存在。
- **冲突**：lead 裁决是"三处破坏性变更 ⇒ 升 `/2`"。**现在是最坏的一种中间态**：对外仍宣称 `/1`，但 `/1` 的消费者按 `level` 读会拿到 `None`（静默降级），且无法从 schema 号区分拿到的是旧 `/1` 还是新形状。
- **建议**：`SCHEMA` 改 `platform32.verify_generation/2`（一行改动），随本轮任意 commit 落地。

### P0-2 · `regen.sh` **默认会向 `.ioc` 写入**（复位 `AskForMigrate`），与"不注入"决策正面冲突

- **现状**（`scripts/regen.sh`）：
  - `RESET_ASK_FOR_MIGRATE=1`（第 84 行，**默认开**）
  - `--keep-ask-for-migrate` 才置 `0`（第 116 行，**opt-out**）
  - 第 381–389 行：生成/核验**之后**，若 `ProjectManager.AskForMigrate == true`，调用
    `ioc_field.py set ProjectManager.AskForMigrate false` **改写 `.ioc`**，并写 `ioc-normalization.json`。
- **冲突**：lead 对 P1 的处置是"**不拦、不改、不注入**"；`DECISIONS`/D19 的表述也建立在不注入的前提上；上一版 `regen.sh` 的注释还写着"本脚本不在 `.ioc` 上做文本注入"。现在默认行为与之相反。
- **风险面**：
  1. 它会**在核验通过之后**改动 `.ioc`，即"报告证明的是 A 状态，交付的是 B 状态" —— 与 G1"证据对应当前工作树"的前提矛盾；
  2. S1 的 diff 判据（`git diff HEAD --numstat -w`）会把这次注入算进"预期外改动"，导致判据假失败或需要为它开例外；
  3. 使用者若在 `testbeds/` 副本上跑，注入本身无害；但在**用户自己的工程**上跑，等于未经同意改了 `.ioc`。
- **建议（择一，由 lead 定）**：
  - (a) **改为 opt-in**：默认 `RESET_ASK_FOR_MIGRATE=0`，新增 `--reset-ask-for-migrate` 显式开启；
  - (b) **完全移除注入**：只 `log_warn`，把"改不改"留给使用者（与 P1 三元结构一致）；
  - (c) 保留默认，但**必须在核验之前**做且**重新核验**，否则证据与交付物不对应。
- 我的倾向：**(b)**。理由：`true` 状态下 `-q` 是否阻塞至今零证据（D19 三元结构第 2 条），为一个未证实的风险引入默认写操作，收益/风险不匹配；且 (b) 的成本最低（删一段）。

### P0-3 · `--require-clean` 与 `--allow-dirty-ioc`：**当前没有矛盾，但反转没做**

- **现状**：`--require-clean` **不存在**（全文 0 次）；`--allow-dirty-ioc` 仍是**旧语义**（默认拒绝脏 `.ioc`，第 115/192 行）。
- **直接回答 lead 的标红问题**：**不是"两者并存"**。当前状态自洽，只是与"默认反过来"的决议不一致。所以**不存在必须先拆掉的矛盾状态**，改动可以随 v1.1 一起做，不急。
- **需要 lead 明确的一点**：反转后 `--allow-dirty-ioc` 是**删除**还是**保留为 no-op 别名**？保留会留下"两个参数语义相反"的隐患；删除会让现有调用者（含我文档里的示例）报错，但报错是显式的、可接受。**建议删除**。

## 3. 🟡 并入 v1.1 的 4 条（P1）

### P1-1 · `inputs` 未收全，`expect` / `allow_signals` 仍在顶层

- **现状**：`report_inputs` = `{log, main_c, mxproject, project_root}` + `effective_allow_signals`；
  而 `expect`、`allow_signals` 仍写在**报告顶层**（第 1028–1030 行附近）。
- **契约要求**（lead 裁决）：全部收进 `inputs`。
- **风险**：若直接把顶层删掉，现有消费方（我的文档、S1–S3、将来 CI）会静默取到 `None`。
- **建议**：`inputs` 收全的**同时保留顶层同名键一个版本**，并在 `summary.notes` 里加一条
  `"deprecated: expect/allow_signals moved to inputs"`；v1.2 再删顶层。这样 `/2` 的迁移是渐进的。

### P1-2 · `--expect-pins` / `pins_present` 未实现（第 7 项未开始）

- **现状**：`expect_pins` 在 `verify_generation.py` 与 `regen.sh` 均 **0 次**；`pins_present` **0 次**；`CHECK_*` 常量共 **6 个**（`log_cannot_map` / `main_init_present` / `main_init_called` / `mxproject_abs_path` / `mx_script_abs_path` / `syscalls_path`），缺第 7 个。
- 符合 lead 描述（第 7 项未开始），**无需额外动作**，此处仅登记以免收口时漏数。

### P1-3 · `mx_script_abs_path` 有 check id 与 `--project-root`，但零测试、三态未自证

- **现状**：`CHECK_MX_SCRIPT_ABS_PATH = "mx_script_abs_path"` 已定义；`--project-root` 已加（不传则该项 skip，help 已写清）。
- **缺口**：lead 反馈"`.mx` 检查一条测试都没有"。三态（占位符未替换→`warn` / 归一化 == 工程根→`pass` / ≠→`fail`）**没有测试就等于没有验证**，尤其"归一化后比较"极易在 Windows 上被 `\` vs `/`、大小写、`..` 段坑到。
- **建议**：至少三个用例（占位符、等值、不等值）+ 一个 Windows 路径分隔符混用的用例。

### P1-4 · `inputs.ioc` 与 `--ioc` 参数缺失

- **现状**：`verify_generation.py` 没有 `--ioc` 参数，`inputs` 里也没有 `ioc` 键。
- **背景**：lead 的最终 7 项清单里没有 `ioc_ask_for_migrate` / `ioc_version_stamp`（已降级为 `regen.sh` 行为），**所以 `--ioc` 可能确实不需要**。
- **但**：lead 给的 `inputs` 全集里列了 `ioc`。**二选一请 lead 定**：
  (a) `inputs.ioc` 一并删掉（推荐，与"不做 ioc 相关 check"一致）；(b) 保留 `--ioc` 仅用于留痕。
- 我倾向 (a)：没有 check 消费它，留痕价值低于"参数越多越要维护"的成本。

## 4. 🟢 已一致 / 值得写进契约的 3 条（P2）

### P2-1 · `tool` 保持对象 ✓

- **现状**：`"tool": {"name": "verify_generation.py", "version": __version__}` —— 与 lead 最终裁决一致（对象而非字符串），**无需改动**。
- 附带：`regen.sh` 调用核验器时不会改这个字段，所以"是谁跑的"这一点目前**只能靠 `inputs.effective_allow_signals` 与外部日志区分**，不能靠 `tool`。若将来要区分入口，`tool` 需要加 `driver` 字段（v1.2）。

### P2-2 · `summary.notes` 是个好设计，建议写进契约

- **现状**：`summary.notes` 收集所有 `skip` 项的 detail（`f"{check_id}: {detail}"`）。
- **价值**：它正好把"**任何 skip 必须解释原因**"这条纪律变成**机读字段**，而不是靠人写散文。我的 §1.4/§4 可以直接说"skip 的解释读 `summary.notes`"。
- **建议**：写进契约（目前它不在 lead 给的 schema 里，属实现先行的好扩展）。

### P2-3 · `/1` 三份历史产物缺迁移说明

- **现状**：`docs/logs/phase1/regen-success/verify.json`、`regen-rollback/verify.json`、`s1-dryrun-regen/` 都是 `/1` 形状（含 `level`、顶层 `expect`）。
- **缺口**：契约文档里还没写"这三份标为 `/1` 历史证据、不作可消费样本"。
- **影响**：不影响代码，但会让后来者拿旧样本对照新文档，误以为文档写错。

## 5. 汇总表（10 行）

| # | 级别 | 项 | 现状 | 建议动作 | 会让当前 commit 不成立？ |
|---|---|---|---|---|---|
| 1 | **P0** | `schema` 未升 `/2` | 仍 `/1`，但已有 `blocking`、无 `level` | 改一行常量 | **是** |
| 2 | **P0** | `regen.sh` 默认注入 `.ioc` 复位 `AskForMigrate` | `RESET_ASK_FOR_MIGRATE=1` 默认开，`--keep-ask-for-migrate` 才关 | 建议改为只告警（opt-in 或移除） | **是**（与"不注入"决策冲突） |
| 3 | **P0** | `--require-clean` vs `--allow-dirty-ioc` | **无矛盾**：前者不存在，后者仍是旧语义（默认拒绝脏） | 反转时**删除** `--allow-dirty-ioc` | 否（自洽，但与决议不符） |
| 4 | P1 | `expect`/`allow_signals` 未进 `inputs` | 仍在顶层 | 进 `inputs` + 顶层保留一版 + `notes` 标 deprecated | 否 |
| 5 | P1 | `--expect-pins`/`pins_present` 未实现 | 各 0 次；`CHECK_*` 共 6 个 | 随第 7 项落地 | 否（未开始） |
| 6 | P1 | `mx_script_abs_path` 三态零测试 | check id 与 `--project-root` 已有，测试无 | 补 ≥4 例（含 Windows 分隔符混用） | 否 |
| 7 | P1 | `inputs.ioc` / `--ioc` 缺失 | 均不存在 | **建议直接删掉该字段**（无 check 消费） | 否 |
| 8 | P2 | `tool` 保对象 | ✅ 已是对象 | 无需改；v1.2 可加 `driver` | 否 |
| 9 | P2 | `summary.notes` 承载 skip 解释 | ✅ 已实现，未入契约 | 写进契约 | 否 |
| 10 | P2 | `/1` 历史产物迁移说明 | 未写 | 契约里加一句 | 否 |

## 6. 一句话结论

**当前实现离 v1.1 收口只差三件硬事**：① `schema` 升 `/2`（一行）；② `regen.sh` 的默认 `.ioc` 注入必须回到"只告警"（否则证据与交付物不对应，且违反已定决策）；③ 第 7 项 `pins_present` 及其测试。
第 3 条 lead 关心的"参数矛盾"**并不存在**——`--require-clean` 压根没实现，现在只是旧语义还在。其余 7 条都是渐进可做的完备性问题。
