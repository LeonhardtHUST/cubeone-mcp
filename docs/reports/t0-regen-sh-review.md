# T0 · `scripts/regen.sh` 只读审计（路径语义与 S1 阻塞风险）

> 产出时间：2026-11-03 · owner：`env-agent`（只读审计，未改动任何代码）· 验证等级：**L1**（源码逐行 + `bash -n` + G474 testbed `--dry-run` 实测 + MSYS 路径语义决定性测试）
> 被审对象：`scripts/regen.sh`（338 行 / 13533 B，owner: `verifier-dev`）
> 触发原因：`vscode-cube-mcp` 的 `_run_script` 以 **CubeMX 安装目录**为 cwd（`cubemx_mcp.py:142`），而 `regen.sh` 走 CLI 通道——若它按 MCP 通道的假设写相对路径，会在 CubeMX 目录下找 `.ioc` 而失败。审计要回答的就是"会不会白等 300 秒"。

---

## 0. 一句话结论

**`regen.sh` 的路径语义是对的，S1 不会因为 cwd 问题白等**——它在 `run_generate` 里显式 `cd "$PROJECT_DIR"`（`:268-269`），正好规避了这个坑。审计中**没有发现会阻塞 S1 的缺陷**，但发现 **4 个中等/低危问题**和 **1 个必须在 SKILL.md 里写明的反向差异**。

---

## 1. 先确认"做对了"的部分（含实测证据）

### 1.1 cwd 已正确显式切换 —— 这是本次审计最关键的结论

```bash
# scripts/regen.sh:268-269
# CubeMX 脚本里的相对 .ioc 路径要求工作目录 = 工程根目录。
( cd "$PROJECT_DIR" && "${cmd[@]}" ) >"$GEN_LOG" 2>&1
```

模板的 `scripts/cubemx-generate.mx` 内容是**相对路径**：

```
config load stm32-g474-template.ioc
SetStructure Advanced
project generate
exit
```

因为 `regen.sh` 把 cwd 切到了工程根，`config load stm32-g474-template.ioc` 能正确解析 ✔。

> **⚠ 反向差异（必须写进 SKILL.md）**
> | 通道 | cwd | 相对路径写法 |
> |---|---|---|
> | **MCP `cubemx_configure` / `cubemx_generate`** | `os.path.dirname(CUBEMX_EXE)` = `C:\ST\STM32CubeMX` | **必须绝对路径** |
> | **`regen.sh`（CLI）** | `$PROJECT_DIR`（显式 cd） | 相对/绝对都可以 |
>
> 两条通道语义**相反**。用户照 MCP 的结论去写 `regen.sh` 的 `.mx` 不会出错（因为 cd 了），但反过来照 `regen.sh` 的相对路径写法去喂 MCP 工具就会失败，且报错是一句含糊的"文件不存在"。

### 1.2 `.mx` 脚本路径是绝对路径（不存在"临时 .mx 写在哪"的问题）

**纠正一个前提**：`regen.sh` **不生成任何临时 `.mx` 文件**。它是复用工程自带的脚本：

```bash
# :158-166
if [ -z "$MX_SCRIPT" ]; then
  if [ -f "${PROJECT_DIR}/scripts/cubemx-generate.mx" ]; then
    MX_SCRIPT="${PROJECT_DIR}/scripts/cubemx-generate.mx"   # 绝对
  else
    MX_SCRIPT="$(find "${PROJECT_DIR}/scripts" -maxdepth 1 -name '*.mx' ...)"  # 绝对
```

`PROJECT_DIR` 在 `:114` 已被 `cd ... && pwd` 归一化为绝对路径，所以 `$MX_SCRIPT` 一定是绝对路径 ✔。

### 1.3 MSYS 路径自动转换实测有效（否则会踩 `D:\d\...` 的坑）

`regen.sh` 把 MSYS 风格路径 `/d/Projects/...` 直接传给**原生 Windows python** 与 `java.exe`。这在纸面上是风险（原生 python 会把 `/d/...` 解析成 `D:\d\...`）。实测结论：**MSYS 会自动转换裸参数**。

```text
# 决定性测试 1：裸参数传给 native python
$ python -c "import sys;print(sys.argv[1:])" /d/Projects/GitHub
['D:/Projects/GitHub']                                    # ← 已被转换 ✔

# 决定性测试 2：含空格路径
$ python -c "import sys,os;print(sys.argv[1:],os.path.isdir(sys.argv[1]))" "/tmp/path space test"
['C:/Users/Leon/AppData/Local/Temp/path space test'] True  # ← 正确转换 ✔

# 决定性测试 3：真实调用 ioc_backup.py（只读 --list）
$ python scripts/ioc_backup.py --list --project /d/.../testbeds/template-mcu-STM32G474-series
D:\Projects\...\stm32-g474-template.ioc	4792 bytes                # exit=0 ✔
```

⚠ `python -c "...abspath('/d/Projects/GitHub')..."` 会得到 `D:\d\Projects\GitHub`（`exists=False`）——但那是**字符串写在代码里**、不经过 MSYS 参数转换的情形。`regen.sh` 属于后者（真实裸参数），安全。

### 1.4 日志是原始 stdout+stderr（满足 G1 的要求）

```bash
# :269
( cd "$PROJECT_DIR" && "${cmd[@]}" ) >"$GEN_LOG" 2>&1
```

未经过任何 `NOISE_RE` 式过滤 → G1 核验器可以直接读 `$GEN_LOG` 看到**未被上游吞掉**的 `Cannot map` 行 ✔。这正是 `docs/reports/t0-cubemx-configure-signature.md` §3.2 要求的那条。

### 1.5 引号处理完整

`"$PROJECT_DIR"` `"${cmd[@]}"` `"$MX_SCRIPT"` `"$GEN_LOG"` `"$OUT_DIR"` 全部双引号，数组用 `"${cmd[@]}"` 展开。含空格路径已实测通过（见 1.3 测试 2）✔。

### 1.6 `timeout` 确实能杀掉 native Windows 子进程（回答"会不会留僵尸 Java"）

用 native `node.exe` 模拟长任务做前后计数：

```text
baseline node.exe count: 34
$ timeout 3 node.exe -e "setTimeout(()=>{},60000)"
timeout exit=124
immediately after: 34          # ← 无残留
2s after         : 34
```

对照组（不用 timeout，手动 kill 后台 job）：`35 → 34`，同样清干净。
⇒ MSYS `timeout` 对 native 子进程**有效**，不会留下占着 `.ioc` 文件的僵尸进程。

**残留风险（如实标注）**：本次用的替身是 `node.exe`（单进程）。CubeMX 是 JVM，名义上同为单进程，但 JVM 可能派生辅助进程/写锁文件。**首跑仍建议 `tasklist | grep -i java` 复核一次**，这条属未实测项。

---

## 2. 发现的问题（按严重度排序，含行号与改法）

### B1【中】`--help` 输出泄漏代码行

**位置**：`:78`

```bash
usage() {
  sed -n '2,50p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}
```

文件头注释块到**第 45 行**结束（`:46` 是 `set -uo pipefail`）。`2,50p` 多取了 5 行，`--help` 实测尾部输出：

```text
=============================================================================
set -uo pipefail

Git Bash 下 PATH 常缺 coreutils（timeout/cp/…），统一补齐。
export PATH="/c/Users/.../usr/bin:/c/Users/.../bin:$PATH"
```

**改法**：`sed -n '2,50p'` → `sed -n '2,45p'`。

---

### B2【中】`AskForMigrate=true` 只 warn 不中止 —— 这才是"白等 300 秒"的真正入口

**位置**：`:181-185`（**纠正 lead 的猜测：11:56 的版本已经有这个检查了**）

```bash
if grep -q '^ProjectManager\.AskForMigrate=true' "${IOC_FILES[0]}" 2>/dev/null; then
  log_warn "检测到 ProjectManager.AskForMigrate=true（D7）：无头生成可能停在迁移对话框等人工确认；"
  log_warn "若卡住，请手动把它改成 false 后重跑（本脚本不在 .ioc 上做文本注入）"
fi
```

问题：只 `log_warn` 就继续跑 → 无头模式（CI / agent 调用）里没人看 warn，CubeMX 卡在模态迁移框 → **恰好白等到 300s 超时**。

**改法**：默认改为中止，给显式放行开关：
```bash
if grep -q '^ProjectManager\.AskForMigrate=true' "${IOC_FILES[0]}" 2>/dev/null; then
  [ "$ALLOW_MIGRATE" -eq 1 ] || die 2 "检测到 AskForMigrate=true（D7），无头生成会卡在迁移对话框。先改成 false 重跑，或加 --allow-migrate 强行继续：${IOC_FILES[0]}"
  log_warn "--allow-migrate：忽略 AskForMigrate=true，超时风险自负"
fi
```

---

### B3【中】D7 回写与 dirty-ioc 守卫的交互：连跑第二次会被拦

**位置**：`:171-176`（守卫）与 `:181-185`（D7 检查）联合作用

CubeMX 每次生成/保存都会把 `AskForMigrate` 写回 `true`（模板 `TOOLING-cubemx.md` §3.3 / 陷阱 D7）。于是：

```
第 1 次 regen.sh → 成功，但 .ioc 被改成 AskForMigrate=true → .ioc 变脏
第 2 次 regen.sh → die 2「.ioc 存在未提交改动，先提交或 stash 再跑」
```

**这不是逻辑 bug**（要求用户提交是对的，回滚粒度靠 git 也是对的），但 S1/S3 要连跑多轮时会频繁撞墙，且报错信息不会提示"是 CubeMX 自己回写的"。

**改法（建议二选一）**：
- 文档层：S1/S3 的操作清单里写明"每轮之间先 `git add -A .ioc && git commit`"，并在 SKILL.md 的 D7 陷阱条目里点明这个连锁；
- 代码层（更友好）：若 `.ioc` 的 diff **仅含** `ProjectManager.AskForMigrate` 一行，给 `log_warn` + 继续，而不是 `die 2`。

当前态：G474 testbed 的 `ProjectManager.AskForMigrate=false`（`:46`）、`git status --porcelain` 为空 → **现在跑不会被拦** ✔。

---

### B4【低】`--dry-run` 仍打印 `[regen] 全部通过 ✅`

**位置**：`:328-336`（成功横幅）

dry-run 下 `run_backup` / `run_generate` / `run_verify` 三个函数都 `return 0`（`:242` `:265` `:295`），流程一路走到底部横幅。实测输出最后就是：

```text
[regen] 全部通过 ✅
```

明明什么都没跑。对 `--dry-run` 明确的使用者危害不大，但**作为证据留档时会误导**（会把 dry-run 输出误认为真实通过）。

**改法**：在 `:328` 前加 `if [ "$DRY_RUN" -eq 1 ]; then log_info "(dry-run) 未执行任何生成/核验"; exit 0; fi`。

---

### B5【低】`GEN_RC=$?` 取值时机脆弱

**位置**：`:309-316`

```bash
if run_generate; then
  :
else
  GEN_RC=$?
```

当前**行为正确**（进入 `else` 时 `$?` 仍是条件命令的退出码），但中间插任何一行语句就会把 `$?` 覆盖掉，属于易碎写法。

**改法**：
```bash
run_generate
GEN_RC=$?
if [ "$GEN_RC" -ne 0 ]; then
  log_err "CubeMX 生成失败（退出码 ${GEN_RC}）"
  rollback_project
  die 1 "生成失败，已回滚。先看日志：${GEN_LOG}"
fi
```

---

### B6【低】`main.c` / `.mxproject` 路径硬编码

**位置**：`:153-156`

```bash
MAIN_C="${PROJECT_DIR}/Core/Src/main.c"
MXPROJECT="${PROJECT_DIR}/.mxproject"
[ -f "$MAIN_C" ] || die 2 "缺少生成物 Core/Src/main.c：..."
```

假设生成物一定在 `Core/Src/main.c`。模板仓符合，但若目标工程结构不同（或 `couple_files`/工具链差异导致位置变化），会直接 `die 2` 且信息指向"先生成一次"。

**改法**：加 `--main-c` / `--mxproject` 覆盖参数（默认值保持现状），或 `find` 兜底定位。

---

### B7【信息】多 `.ioc` 工程只检查第一个

**位置**：`:182` 用 `"${IOC_FILES[0]}"`，`:150` 的 `find` 允许匹配多个 `.ioc`。多 `.ioc` 工程下 D7 检查会漏。当前 testbed 单 `.ioc`，**无实际影响**，记录备查。

---

## 3. 实测执行记录（我跑了什么、没跑什么）

| 动作 | 命令 | 结果 |
|---|---|---|
| 语法检查 | `bash -n scripts/regen.sh` | OK，无语法错误 |
| dry-run（G474 testbed） | `scripts/regen.sh testbeds/template-mcu-STM32G474-series --dry-run` | 三步全走通，exit 0，**未写任何工程文件**（仅 `mkdir -p /tmp/platform32-regen`） |
| MSYS 路径转换 | 见 §1.3 三个测试 | 全部转换正确 |
| `ioc_backup.py` 只读调用 | `--list --project /d/...G474...` | 正常列出 `.ioc`，exit 0 |
| MSYS `timeout` 杀 native 子进程 | `timeout 3 node.exe -e "setTimeout(()=>{},60000)"` | exit=124，前后计数 34→34，无残留 |

dry-run 展开出的真实命令（原样，可作为 S1 的预期行为基线）：

```bash
# 步骤 1
python /d/.../scripts/ioc_backup.py --project /d/.../testbeds/template-mcu-STM32G474-series \
  --json-out /tmp/platform32-regen/ioc-backup.json
# 步骤 2
cd /d/.../testbeds/template-mcu-STM32G474-series && timeout 300 \
  C:/ST/STM32CubeMX/jre/bin/java.exe -jar C:\ST\STM32CubeMX\STM32CubeMX.exe \
  -q /d/.../testbeds/template-mcu-STM32G474-series/scripts/cubemx-generate.mx \
  > /tmp/platform32-regen/cubemx-generate.log 2>&1
# 步骤 3
python /d/.../scripts/verify_generation.py --log /tmp/platform32-regen/cubemx-generate.log \
  --main-c /d/.../Core/Src/main.c --mxproject /d/.../.mxproject --expect GPIO \
  --json-out /tmp/platform32-regen/verify.json --report-md /tmp/platform32-regen/verify.md \
  --allow-signal VP_RIF_VS_RIF1
```

一并观察到：`--expect` 未指定时按 `.ioc` 推导得到 `GPIO`（`Mcu.IP*` 只有 NVIC/RCC/SYS，被过滤后补 GPIO）✔ 符合预期。

---

## 4. 交给 `verifier-dev` 的改动清单（按优先级）

| # | 优先级 | 位置 | 改动 |
|---|---|---|---|
| 1 | **中** | `:181-185` | `AskForMigrate=true` 默认 `die 2`，新增 `--allow-migrate` 放行开关（B2，唯一真正能造成"白等 300s"的点） |
| 2 | 中 | `:78` | `sed -n '2,50p'` → `'2,45p'`（B1） |
| 3 | 中 | 文档 | S1/S3 操作清单写明"每轮之间先 commit `.ioc`"，或在 `.ioc` diff 仅含 `AskForMigrate` 时降级为 warn（B3） |
| 4 | 低 | `:328` | `--dry-run` 不打"全部通过"（B4） |
| 5 | 低 | `:309-316` | 先存 `GEN_RC=$?` 再判（B5） |
| 6 | 低 | `:153-156` | 加 `--main-c` / `--mxproject` 覆盖参数（B6） |
| 7 | 必做（文档） | SKILL.md | 写明 **MCP 通道 cwd=CubeMX 安装目录 vs regen.sh 通道 cwd=工程根目录** 的反向差异（§1.1） |

---

## 5. 未覆盖 / 未实测（如实标注）

| # | 项 | 说明 |
|---|---|---|
| 1 | 真实 `java -jar STM32CubeMX.exe -q` 的成功/失败路径 | 本次只跑 dry-run，**未真正启动 CubeMX**（避免在他人 testbed 上生成/覆盖文件）。S1 首跑定案 |
| 2 | JVM 超时后是否留残留进程/锁文件 | 用 node.exe 替身证明 `timeout` 有效；CubeMX 本体未实测，建议首跑后 `tasklist \| grep -i java` 复核 |
| 3 | CubeMX 报错时的退出码 | 若 `config load` 失败 CubeMX 仍返回 0，则 `run_generate` 会误判成功（`:270` 直接透传 rc）→ 只能靠步骤 3 核验兜底。这是"CubeMX 静默非致命"的另一面，S3 可顺手验证 |
| 4 | `verify_generation.py` 内部逻辑 | 不在本次审计范围（owner: verifier-dev，其单测见 `docs/logs/phase1/t1.2-pytest.log`） |

---

## 6. 追加：S1 的 diff 判据基线（`config saveas` 重写的精确清单）

> 补充时间：2026-11-03 12:25 · 起因：lead 指出"若 `config saveas` 会重写整个 `.ioc` / `main.c`，则 S1 的『diff 只含预期文件』DoD 会**假失败**"。本节给实测基线，并**纠正两个被引错的数字**。

**实测对象**：`testbeds/_s1-dryrun/g474`（`scenario-tester` 的一次性丢弃副本，执行过 `config saveas`），只读 `git diff --numstat`：

| 文件 | 增 / 删 | 说明 |
|---|---|---|
| `stm32-g474-template.ioc` | **9 / 6** | 16 行变更，见下方逐条归类 |
| `Core/Src/main.c` | **11 / 0** | 全部是 PB0 的 GPIO 初始化，**USER CODE 区无丢失** |
| `.mxproject` | **0** | 未变 |

### 6.1 `.ioc` 的 16 行变更逐条归类

| 变更 | 类别 |
|---|---|
| `Mcu.Pin1..Pin4` 整体后移，`PB0` 插入为 `Mcu.Pin1` | 功能（连带重排） |
| `Mcu.PinsNb=5` → `Mcu.PinsNb=6` | 功能（连带）**← 见 6.2 纠正 1** |
| `+PB0.Signal=GPIO_Output` | **功能**（唯一真正表达"用户意图"的一行） |
| `+PB0.Locked=true` | **噪音**：CubeMX 自动打的锁标记，非用户操作 |
| `-ProjectManager.AskForMigrate=false` → `+true` | **噪音**：`saveas` 副作用（D7） |

**结论：G474（6.18 原生仓）的 `saveas` 重写规模很小（16 行），"diff 只含预期文件"这个 DoD 成立、不会假失败。** 建议 S1 把 diff 白名单写成：

- `.ioc` 允许：`Mcu.Pin[0-9]+`、`Mcu.PinsNb`、`<新引脚>.{Signal,Locked}`、`ProjectManager.AskForMigrate`
- `main.c` 允许：USER CODE 区之外新增的新引脚 GPIO 初始化段
- 其它任何键出现变更 → 视为意外，走回滚

### 6.2 必须纠正的两个数字

**纠正 1 —— `Mcu.PinsNb` 确实从 5 变成 6**

```text
$ grep -nE '^Mcu\.Pin[0-9]+=|^Mcu\.PinsNb=' testbeds/_s1-dryrun/g474/stm32-g474-template.ioc
16:Mcu.Pin0=PC13
17:Mcu.Pin1=PB0
18:Mcu.Pin2=PA13
19:Mcu.Pin3=PA14
20:Mcu.Pin4=VP_SYS_VS_Systick
21:Mcu.Pin5=VP_SYS_VS_DBSignals
22:Mcu.PinsNb=6
```

"`PinsNb` 仍是 5 / 不会自动加 1"**不成立**。若 S1 按此写断言，会**假失败**。
正确断言：`Mcu.PinsNb` == 变更前引脚数 + 新增引脚数（本例 5 + 1 = 6），且 `Mcu.Pin*` 序列连续无重复。

**纠正 2 —— "`main.c` 619 增 / 106 删"不是 G474 的数据**

该数字出自 `docs/DECISIONS.md:75`，原文对象是 **`stm32-digital-clock`**：

> `stm32-digital-clock` 的 `.ioc` 版本戳为 `6.17.0`（共 5 处），本机 CubeMX 锁 6.18.1（D1）。重新生成会产生 **619 增 / 106 删**的整文件重写，而真实功能改动可能只有 9 增 / 1 删。

那是**跨 CubeMX 版本（6.17 → 6.18）迁移**导致的整文件重写。G474 模板是 6.18 原生，实测只有 11 增 / 0 删。
**⇒ 整文件重写的成因是"版本不匹配"，不是 `saveas` 本身。** 两个数字混用会让人误以为原生仓也会整文件重写，从而把 S1 的 diff 判据放得过宽（等于放弃了"diff 只含预期文件"的约束力）。

### 6.3 顺带定案：`GPIOParameters` 白名单（此前列为未实测项）

```text
$ grep -n 'PB0.GPIOParameters' testbeds/_s1-dryrun/g474/stm32-g474-template.ioc
（不存在 —— 未加白名单）
```

`set pin PB0 GPIO_Output` **不写** `PB0.GPIOParameters`；而生成的 `main.c` 仍然完整输出了 PB0 的 GPIO 初始化（`__HAL_RCC_GPIOB_CLK_ENABLE` / `GPIO_MODE_OUTPUT_PP` / `HAL_GPIO_Init`）。

**⇒ 白名单只在需要"额外参数"时才必要**（如 PC13 的 `GPIOParameters=PinState` + `PinState=GPIO_PIN_SET`）。纯输出模式不写白名单也能正确生成。
这解释了模板仓 `TOOLING-cubemx.md` §3.5 为何强调"要初始电平就必须两行一起写"——它约束的是**参数**，不是**引脚模式**。
