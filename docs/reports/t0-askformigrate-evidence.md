# T0 · `AskForMigrate` 二值判定（`-q` 是否会因 `true` 阻塞）

> 产出时间：2026-11-03 · owner：`env-agent`（只读复核，未启动 CubeMX）· 验证等级：**L1**（全部基于已落盘证据的字节级比对）
> 触发：lead 对 B2 的裁决需要先钉死一个前提——"`AskForMigrate=true` 会导致 `-q` 阻塞"。本报告给出二值答案。
> 复核对象：`docs/logs/phase1/regen-success/`（第 1 次）、`docs/logs/phase1/regen-rollback/`（第 2 次）、`docs/logs/phase1/s1-dryrun-setcube.log`

---

## 0. 一句话结论

**第 2 次生成开始前，`.ioc` 里 `AskForMigrate` 是 `false`，不是 `true`。**

但**关键修正**：它之所以是 `false`，**不是因为"写回发生了却消失"，而是因为第 1 次运行根本没写过 `.ioc`**——`regen.sh` 用的 `cubemx-generate.mx` 只有 `config load` + `project generate`，**没有 `save`/`saveas`**，而 `project generate` 不改写 `.ioc`（两次运行前后 `.ioc` sha256 逐字节相同）。

⇒ 因此：
- 我原来担心的「**`regen.sh` 纯 generate 连跑会自锁**」→ **不成立，撤回**（B3 的前提错了）。
- 但「**`true` 是否阻塞 `-q`**」→ **本次证据无法回答，仍是空白**：两次运行都是 `false → false`，从未有 `true` 状态被 `-q` 加载过。

---

## 1. 二值判定：直接证据

### 1.1 硬证据 A —— 两次备份快照的 sha256 完全相同

`docs/logs/phase1/regen-success/ioc-backup.json`（第 1 次，11:58:42）：

```json
"timestamp": "2026-11-03T11:58:42+08:00",
"ioc": "...\\_verifier-regen\\g474\\stm32-g474-template.ioc",
"bytes": 4792,
"sha256": "d0bf5be00e1a51e43bc6e6f6e3279dafd2b58bb6f3932313c397b0653c3536ed"
```

`docs/logs/phase1/regen-rollback/ioc-backup.json`（第 2 次，11:59:47）：

```json
"timestamp": "2026-11-03T11:59:47+08:00",
"ioc": "...\\_verifier-regen\\g474\\stm32-g474-template.ioc",
"bytes": 4792,
"sha256": "d0bf5be00e1a51e43bc6e6f6e3279dafd2b58bb6f3932313c397b0653c3536ed"
```

**第 1 次跑完到第 2 次开始之间，`.ioc` 一个字节都没变。**

### 1.2 硬证据 B —— 第 2 次的起始值就是 `false`

`regen.sh:182` 在每次运行**开始时**检查：

```bash
if grep -q '^ProjectManager\.AskForMigrate=true' "${IOC_FILES[0]}" 2>/dev/null; then
  log_warn "检测到 ProjectManager.AskForMigrate=true（D7）..."
```

`docs/logs/phase1/regen-rollback/console.log` 全文 **24 行，无任何 `AskForMigrate` 告警**（grep 命中 0）。同理第 1 次的 `console.log`（`regen-success`，28 行）也无告警。

⇒ 两次运行**起始时都是 `false`**（若为 `true`，脚本必然打印两行 warn）。

### 1.3 硬证据 C —— 当前态仍是 `false`，且与备份同 sha

```text
$ grep -n 'AskForMigrate' testbeds/_verifier-regen/g474/stm32-g474-template.ioc
46:ProjectManager.AskForMigrate=false
$ sha256sum testbeds/_verifier-regen/g474/stm32-g474-template.ioc
d0bf5be00e1a…3536ed
$ sha256sum testbeds/_verifier-regen/g474/stm32-g474-template.ioc.bak
d0bf5be00e1a…3536ed
```

⇒ **`project generate` 全程没有改写 `.ioc`**（原始 `.ioc` 与 `.ioc.bak` 同 sha）。

---

## 2. 为什么"写回没发生"——真正的机制

### 2.1 `regen.sh` 用的 `.mx` 里没有 save/saveas

`testbeds/_verifier-regen/g474/scripts/cubemx-generate.mx` 全文：

```
config load stm32-g474-template.ioc
SetStructure Advanced
project generate
exit
```

=> 只有 `project generate`，**没有 `config save` / `config saveas`**。这解释了 1.3 的 sha 完全不变。

### 2.2 对照：执行过 `config saveas` 的那份副本变成了 `true`

`testbeds/_s1-dryrun/g474/stm32-g474-template.ioc`（S1 干跑副本，该次脚本含 `config saveas`）：

```text
$ grep -n 'AskForMigrate' testbeds/_s1-dryrun/g474/stm32-g474-template.ioc
49:ProjectManager.AskForMigrate=true
```

⇒ **`AskForMigrate` 的写回由 `save`/`saveas` 触发，不由 `project generate` 触发。**

### 2.3 修正后的因果链

| 流程 | 是否改写 `.ioc` | `AskForMigrate` 结果 | 谁受影响 |
|---|---|---|---|
| `cubemx-generate.mx`（`config load` + `project generate`，即 `regen.sh` 的默认路径） | **否**（sha 不变） | 保持原值（本工程 `false`） | **无自锁风险** |
| `config saveas`（MCP `cubemx_configure` / `cubemx_new_project` / S1 干跑） | **是**（整体重写） | 变 `true` | 之后任何加载该 `.ioc` 的无头运行 |

**所以真正会进入 `true` 状态的，是"先改配置（saveas）再生成"的组合流——也就是 S1 自己的流程**，而不是 `regen.sh` 连跑。

---

## 3. 对 lead 三条裁决的回应

| 裁决 | 我的回应 |
|---|---|
| B2「不采纳 `die 2`」 | **同意，且现在有证据支持**：`regen.sh` 纯 generate 路径不会产生 `true`，加 `die 2` 只会误伤那些 `.ioc` 是从别处（含 saveas）带来的工程 |
| 「若第 2 次起始是 `false`（说明写回没留下痕迹）→ 改判默认中止」 | **前提不成立**：写回**根本没发生**，不是"发生后又消失"。按机制判定，不应因此改判 |
| 「`true` 单独不阻塞，结论封版」 | **不能封版**：两次都是 `false → false`，`true` 状态从未被 `-q` 加载过。现有证据只能证伪"regen.sh 会自锁"，**不能**证伪"true 不阻塞" |
| B3 的 `--require-clean` 默认方向调整 | 改动本身无害（`saveas` 流程确实会弄脏 `.ioc`），但**理由要换**：不是"D7 让 `regen.sh` 自锁"，而是"MCP 改配置（saveas）会重写 `.ioc`，需要提交纪律"。建议 DECISIONS/TASKBOARD 按后者措辞，否则留下一个错误的技术前提 |

---

## 4. 补一次实验就能定案（成本 ≈ 60s，靶子已就位）

`testbeds/_s1-dryrun/g474` 的 `.ioc` **已经是 `true`**（§2.2），且该目录是一次性丢弃副本。在它上面跑一次纯 generate（`config load` + `project generate`，不 saveas）：

- **正常 ~60s 结束** → `true` 不阻塞，B2 彻底封版，`regen.sh` 保持只 warn；
- **超时/卡住** → `true` 会阻塞，此时**也要注意不是 `regen.sh` 的默认路径会踩**，而是 S1 的 configure→generate 组合流；处置应是"改动配置后立刻把该字段改回 `false`"或在 `regen.sh` 里加前置修字段（但那属于 .ioc 文本注入，与脚本 §约定 "不做 .ioc 文本注入" 冲突，需 lead 裁决）。

**我不建议由我来跑**：`_s1-dryrun/` 与 `testbeds/` 归 `scenario-tester`，且我的边界是不在他人 testbed 上生成/覆盖文件。建议转给 `scenario-tester`，在 S1 正式跑时**顺带记录**这一条（S1 本来就会走到 `saveas` → `generate`，等于自动做掉这次实验），无需额外开靶。

**给 S1 的一句话要求**：在 `configure`（saveas）之后、`generate` 之前，把 `.ioc` 里 `ProjectManager.AskForMigrate` 的实际值记进证据日志；generate 结束后再记一次。这一行数据就能永久封版 D7。

---

## 5. 我没有做的事（边界声明）

- **未启动 CubeMX**（全部结论来自已落盘日志与 sha256 比对）。
- **未修改任何 testbed / 模板仓**（`testbeds/_verifier-regen/g474`、`_s1-dryrun/g474`、官方 `template-mcu-STM32G474-series` 均只读）。
- 官方 G474 testbed 未被污染：`sha256 = d0bf5be0…`，`git status --porcelain` 为空，`AskForMigrate=false`（`:46`）。
