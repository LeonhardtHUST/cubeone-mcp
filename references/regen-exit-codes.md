# `regen.sh` 行为与退出码

> 手册页 · owner: `skill-author` · 以实现为准：`scripts/regen.sh` · 最后核对：2026-11-03
> 本页是 `SKILL.md` §1.5 与 §2 第 0 / 第 4 步的展开。

## 1. 用法

```bash
bash scripts/regen.sh <工程目录> [-e GPIO,TIM4] [-o <证据目录>] [--require-clean] [--dry-run] [--skip-generate]
```

它把四件事串成一条：**备份 `.ioc` → 生成 → 核验 → 失败回滚**。

| 选项 | 语义 |
|---|---|
| `-e, --expect <list>` | 期望外设。**可省略**——省略时从 `.ioc` 的 `Mcu.IP*` 自动推导（滤掉 `NVIC/RCC/SYS/DBGMCU` 再补 `GPIO`） |
| `-l, --log <path>` | 生成日志路径（默认 `<out>/cubemx-generate.log`） |
| `-m, --mx <script.mx>` | CubeMX 脚本（默认 `<工程>/scripts/cubemx-generate.mx`） |
| `-o, --out <dir>` | 证据目录。默认 `${TMPDIR:-/tmp}/platform32-regen`，**故意不落在工程里**（避免污染 `git status`）；要入库时显式指到 `docs/logs/phaseN/<场景>/` |
| `--java` / `--cube` | 覆盖解释器/exe 路径 |
| `--timeout <sec>` | **最小 240**（低于自动抬到 240 并告警）；默认 300。单次生成实测约 60 s |
| `--allow-signal <sig>` | 透传给核验器；**默认预置 `VP_RIF_VS_RIF1`**（D8） |
| `--no-default-allow` | 不预置 D8 白名单（严格模式） |
| `--require-clean` | `.ioc` 有未提交**内容**改动时直接退 `2`；**默认允许脏** |
| `--skip-generate` | 跳过生成，只做备份 + 核验（重跑核验用） |
| `--dry-run` | 只打印将执行的命令，不落盘 |

> ⚠️ **自动推导 `-e` 不等于"你本次期望的"**：它是"全量"语义（`.ioc` 里所有 `Mcu.IP*`）。
> 要精确控制就显式传 `-e`，否则漏检/多检都会落到你头上。

## 2. 退出码（`1` 与 `2` 的区别是这条工具最重要的设计）

| 码 | 含义 | 你该做什么 |
|---|---|---|
| `0` | 生成 + 核验通过 | 继续 `pio run` |
| `1` | **跑过了但结果不对**：日志出现整行 `KO`，或核验 FAIL；**已从备份回滚** `.ioc`/`.mxproject` | 看日志与核验报告 |
| `2` | **压根没跑**：前置拒绝或环境错误（`--require-clean` 命中脏 `.ioc`、工程目录不存在、找不到 CubeMX/java、缺 `.mx`、`--expect` 解析失败、**备份 `.ioc` 失败**） | **不要去翻核验报告**——报告根本没生成 |

一句话：**`1` 是"跑了但错了"，`2` 是"没跑"。**

### ⚠️ `2` 还有一个来源：`ioc_backup.py` 的备份完整性校验失败

回滚走 `ioc_backup.py --restore`，而它在还原前会核对 `.ioc.bak` 与旁路摘要 `<name>.ioc.bak.sha256`：

| 情形 | `ioc_backup.py --restore` | `regen.sh` 看到的后果 |
|---|---|---|
| 摘要一致 | 退出码 `0`，原子替换 `.ioc` | 正常回滚 |
| 摘要不一致（篡改 / 部分写入） | 退出码 **`2`** + `[ioc_backup][integrity] 备份疑似被篡改或部分写入：…`，**`.ioc` 一个字节都不动** | 视为"还原失败"，**退化为 `git checkout -- '*.ioc'`**（`rollback_project`） |
| 无旁路摘要（旧版备份） | 退出码 `0` + stdout `[ioc_backup][warn] 缺少完整性摘要（旧版备份），已跳过校验` | 正常回滚，但**这层篡改检测不生效** |

⇒ **`regen.sh` 的退出码 `2` 也可能表示"备份不可信"**，不只是"参数错"。看到 `[ioc_backup][integrity]`
就去查 `.bak` 是怎么坏的（磁盘/同步软件/中途被杀），**不要**把它当成参数问题；此时 `.ioc`
仍是生成后的状态，可先 `git diff` 确认再用 git 回滚。
`regen.sh` 本身只判"非 0 即失败"，没有对 `2` 的专门分支——这是有意的：两种失败的正确续作都是
"别信备份，改用 git"。

## 3. 成功判据是两条，退出码不在其中

```
① 生成日志里没有整行 KO
② 核验器 verdict = pass
```

**为什么不用退出码**：CubeMX **退出码恒为 0**（D25：脚本层回 `KO` 也返回 0）。
实现里用的是整行匹配 `^[[:space:]]*KO[[:space:]]*$`（大写、独占一行）。

### ⚠️ `KO` 判据是**必要不充分**条件

它只能抓"脚本层被 CubeMX 拒绝"（如 `set pin` 写非法信号名）。
**抓不到"命令被静默忽略"**——`set ip parameters …` 会回 `OK`、无 `KO`，却**一字未改** `.ioc`。
脚本自己也会打这行提示：

> 生成阶段：退出码 0 且无 KO。**无 KO 只是必要条件，不是成功证明** ——
> `set ip parameters` 这类命令会回 OK、无 KO，却静默空操作；最终以核验为准。

⇒ **不要让"没 KO"读成"成功了"。** 完整判据见 `diff-evidence.md` 的三级确认。
另注：`KO` 判据是 `regen.sh` 的能力，**手跑 `java -q` 时没有这层保护**。

## 4. `AskForMigrate` 的行为约束（操作纪律，不是建议）

> **`regen.sh` 不修改** `.ioc` 中 `ProjectManager.AskForMigrate` 的值。
> 生成后该值可能为 `true`，属 CubeMX `saveas` 的正常结果，**不要在提交前手工复位**。

补充两条事实（判据来源，详见 `docs/DECISIONS.md` D19）：

- `config save`/`saveas` 会整体重写 `.ioc` 并把该值写成 `true`；**纯 `project generate` 不改写
  `.ioc`**（`regen.sh` 默认路径实测前后 sha256 逐字节相同）。
- `true` 状态下 `-q` 是否阻塞**至今零证据**。**零证据 ≠ 无风险**，但也**不构成拦的理由**。
  若生成长时间无输出，先查 `MxCube.Version` 是否低于本机版本（**排障建议，不是因果结论**）。

## 5. 脏工作区语义（1.2.0 起反转）

- **默认允许脏**：失败时从备份恢复 `.ioc`，所以不需要工作区干净。
- `--require-clean` 才严格：`.`ioc` 有未提交内容改动 → 直接退 `2`，**不执行生成**。
- 旧的 `--allow-dirty-ioc` 已删除（两个语义相反的开关并存是陷阱）。
