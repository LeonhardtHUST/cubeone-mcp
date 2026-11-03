---
name: platform32-mcp
description: "STM32 工程全流程编排：把 .ioc 改配置（vscode-cube-mcp）→ 代码生成 → 生成核验（G1 强制关卡）→ PlatformIO 构建（platformio.mcp）→（接板后）烧录与串口验证（stm32-stlink-mcp）串成一条带 L0–L5 验证等级声明的流水线，并输出符合模板 AGENTS.md 提交规范的 commit。当用户说「改一下这个 ioc」「加一个 GPIO / UART / ADC 通道」「CubeMX 重新生成代码」「生成完帮我核一遍」「有没有被静默丢弃的外设」「pio 构建一下」「Flash/RAM 占多少」「烧进去看看」「串口有输出吗」「这个模板工程跑不起来」时使用。只读审计不写盘；任何写操作前必须先备份 .ioc 并报告将改动的对象，生成后必须跑核验器并如实声明验证等级；不替用户提交未经核验的代码，不碰 testbeds/ 之外的模板原仓。"
version: 0.2.0
agent_created: true
license: MIT
compatibility: Python 3.8+（核验器只依赖标准库）；需要已注册的 vscode-cube-mcp / platformio.mcp 两个 MCP server（stm32-stlink-mcp 仅 Phase 2 烧录段需要）；路径白名单与动作档位见 §0
---

# platform32-mcp：STM32 生成 / 核验 / 构建 / 烧录编排

> **状态：v0.2.0 初稿（T1.4）。** §1「能力索引」中的核验器接口仍是 `TODO(T1.2)` 占位，
> 等 verifier-dev 交付 `scripts/verify_generation.py` 后回填；正文其余部分已可执行。
> Phase 2 的烧录/串口段（§6）本会话无硬件，整体待接板（决策 D7）。

三个领域 MCP server 各管一段，**没有任何一个 server 管"改完有没有真的生效"**。
本 Skill 存在的理由就是补上那一段：把 `.ioc` 改动、代码生成、生成核验、构建、
（接板后的）烧录与串口验证串成一条有据可查的流水线，并且**每个环节都留下可核验的证据**，
否则不许声明完成。

---

## 本文可信度标注

本文每条结论都标来源，**不要**把三类混为一谈：

| 标记 | 含义 | 你敢不敢依赖 |
|---|---|---|
| ✅ | 本机实测，证据在 `docs/logs/` 指定路径 | 可以 |
| 📄 | 引自模板仓文档（已在远端仓库公开，见 `references/README.md`） | 可以，但要按链接回原文看上下文 |
| ⚠️ | 尚未实测的推断/待办 | **不要**，等实测填回来 |

未标注的一律按 ⚠️ 处理。**本文不许出现第四个来源。**

---

## 0. 硬前提

### 0.1 三个 server 的可用性自检

开工第一步，逐个确认，**任何一个不通就停手报错，不许降级成"手改文本绕过"**：

| Server | 自检调用 | 期望 | 证据 |
|---|---|---|---|
| vscode-cube-mcp | `cubemx_help` | 返回 9 个工具：`cubemx_load` / `cubemx_configure` / `cubemx_generate` / `cubemx_new_project` / `cubemx_remove_peripheral` / `cubemx_add_source` / `cubemx_export_pinout` / `cubemx_script` / `cubemx_help` | ✅ `docs/logs/phase0/vscode-cube-mcp-handshake.log`（协议版本 `2025-11-25`，`tools_count: 9`） |
| platformio.mcp | `pio_system_info`、`pio_list_devices` | `ok: true`；`policy` 字段必须是本次要用的档位 | ✅ `docs/logs/phase0/platformio-mcp-doctor.log` |
| stm32-stlink-mcp | `doctor`（`dist/index.js doctor`） | `probes` 非空 | 仅 Phase 2 需要，当前 `disabled`（✅ `docs/DECISIONS.md` D7） |

### 0.2 mcp.json 的 env 内联（改前必看）

CubeMX 与 PlatformIO 的行为由 **server 进程的 env** 决定，不是由本机用户级环境变量决定：

| 变量 | 值 | 作用 |
|---|---|---|
| `ST_CUBEMX_EXE` | `C:\ST\STM32CubeMX\STM32CubeMX.exe` | CubeMX **不在** `C:\Program Files\STMicroelectronics\...`；写错会报找不到 |
| `ST_CUBEMX_ALLOWED_ROOTS` | `D:\Projects;C:\Users\Leon\WorkBuddy` | **路径白名单**。换工作目录必须同步改，否则报"路径不在允许范围内" |
| `ST_CUBEMX_TIMEOUT` | `300` | 单次生成含 JVM 启动 + CMSIS 拷贝，本机约 **1 分钟量级**；阈值不要设小 |
| `PLATFORMIO_MCP_POLICY` | `build_only`（默认） | 动作档位：构建/查尺寸可用，烧录会被拒 |
| `PLATFORMIO_MCP_PIO` | `C:\Users\Leon\.platformio\penv\Scripts\pio.exe` | 显式指定 pio 可执行文件，避免 PATH 歧义 |

✅ 证据：`docs/logs/phase0/platformio-mcp-doctor.log`（`policy: build_only`、`core_version: 6.2.0`、
`pio_command` 与上表一致）。📄 变量语义引自模板仓 `docs/TOOLING-cubemx.md` §4。

### 0.3 三条红线

1. **`PLATFORMIO_MCP_POLICY=build_only` 时绝不烧录**。要烧录必须显式升档，并在
   `docs/TASKBOARD.md` / commit 正文里留下升档与回退的记录。升档属于改动用户配置，
   须经 `team-lead` 向用户确认（GATE 流程）。
2. **只在 `testbeds/` 的克隆副本里做写操作**。`D:\Projects\GitHub\` 下三个 `template-mcu-*` 模板仓、
   `NUEDC_2027`、`HUSTRadio`、`leonskill-*` **一律只读**（✅ `docs/DECISIONS.md` D9）。
3. **生成后不核验 = 没做**。见 §2 第 5 步。CubeMX 对 `.ioc` 的错误是**非致命**的：
   信号名写错只留一行日志，`project generate` 仍返回成功，外设被静默丢弃（📄 `AGENTS.md` §2.3、D5）。

---

## 1. 能力索引

| 想做的事 | 入口 | 状态 |
|---|---|---|
| **生成核验（G1 强制关卡）** | `scripts/verify_generation.py` | `TODO(T1.2)`：接口（入参 / 退出码 / JSON 字段）待 verifier-dev 定稿后回填，**在回填前不要调用、不要猜参数** |
| 备份 → 生成 → 核验 三步封装（失败自动回滚 `.ioc`） | `scripts/regen.sh` | `TODO(T1.2)`：同上，归 T1.3 |
| 单独备份 `.ioc` | `scripts/ioc_backup.py` | `TODO(T1.2)`；临时替代见 §2 第 2 步 |
| 只读审计：引脚表 / 时钟树 / 构建数字（场景 S2） | `cubemx_load`、`cubemx_export_pinout`、`pio_build`、`pio_size_report` | ✅ 可用 |
| 改外设配置 | `cubemx_configure`、`cubemx_new_project`（`commands` 参数） | ✅ 可用；语义见 §2 第 3 步 |
| 生成代码 | `cubemx_generate` | ✅ 可用 |
| 构建 / 错误定位 / 尺寸 | `pio_build`、`pio_size_report`、`pio_decode_backtrace` | ✅ 可用（`build_only` 档位内） |
| 烧录 / 串口 / 探针排障 | `flash_standalone`、`pio_monitor_capture`、`pio_port_diagnose` | ⚠️ Phase 2，无硬件未实测 |

> **参数签名一律以运行时 `cubemx_help` / 各 server 的工具描述为准**，本文不复述签名。
> 理由：三个 server 都在活跃迭代（`platformio.mcp` 0.2.0、`vscode-cube-mcp` 0.4.2），
> 文档里抄一份签名必然与实现漂移，抄错比不抄更危险。

---

## 2. 标准流程（写操作，八步）

适用：用户要"改 `.ioc` 里的某个外设/引脚/时钟，然后重新生成并构建"。
**只读审计（S2）跳过 2–6，直接做 1 + 7**。

### 第 0 步 · 前置检查

- `git status` 必须干净（只允许 `testbeds/`、`docs/logs/` 下被忽略的产物存在）。
  有未提交改动 → 先问用户，别把用户的手改混进本次 diff。
- `.ioc` 路径必须在 `ST_CUBEMX_ALLOWED_ROOTS` 内（§0.2）。
- 确认 `PLATFORMIO_MCP_POLICY` 档位够用且**只够用**（要构建不要烧录就别升档）。

### 第 1 步 · 只读审计（不改一个字节）

用 `cubemx_load` 回读当前 `.ioc`，用 `cubemx_export_pinout` 取引脚表。产出**改动前的基线**：
当前启用了哪些外设、哪些引脚是什么模式、时钟树关键键值。

这一步的价值在于**回滚时有对照物**，并且能证明"这个外设原本就不存在"而不是"被我们改没了"。

### 第 2 步 · 备份 `.ioc`

```bash
cp <project>.ioc <project>.ioc.bak    # .gitignore 已忽略 *.ioc.bak
```

⚠️ `scripts/ioc_backup.py`（`TODO(T1.2)`）交付后改用脚本；在此之前上面这条 `cp` 就是合规做法。
**备份必须先落盘再做第 3 步**——CubeMX 的写回是不可逆的（📄 `AGENTS.md` §2.3）。

### 第 3 步 · 改配置（禁止文本注入）

- 📄 语义差异（引自模板仓 `docs/TOOLING-cubemx.md` §4）：`cubemx_configure` 是**纯脚本透传**
  （把 CubeMX `set` 命令序列发给 CLI），真正能"从零描述外设"的是 `cubemx_new_project` 的 `commands` 参数。
  用哪个取决于"已有 `.ioc` 增量改"还是"新工程"——不确定就先 `cubemx_help` 看当前实现。
- **不要手改 `.ioc` 文本**。手改仅限极小改动，且必须补两处白名单（📄 `TEMPLATE-PLACEHOLDERS.md` D3）：
  - 每个外设一行 `<IP>.IPParameters=a,b,c`，只有列进去的 key 才被识别；
  - 每个引脚一行 `<Pin>.GPIOParameters=...`（例：`PC13.GPIOParameters=PinState` 才让 `PC13.PinState` 生效）。
- **信号名带 `S_` 前缀**（📄 D4）：PA0 上 TIM2 通道 1 的正确写法是 `S_TIM2_CH1_ETR`，
  写成 `TIM2_CH1_ETR` 会失败。以本机 `C:\ST\STM32CubeMX\db\mcu\<型号>.xml` 为准，先查库再写。

### 第 4 步 · 生成

调用 `cubemx_generate`。两个已知坑，生成前扫一眼：

- **`ProjectManager.AskForMigrate` 会被写回 `true`**（📄 D7 / `TOOLING-cubemx.md` §3.3）。
  模板里提交的是 `false`。无头模式若卡在 `Begin LoadConfig()` 后不再输出，
  先把它改回 `false` 再跑（那是模态迁移框在等人点）。
- **`project path` 会再追加一层工程名**（📄 `TOOLING-cubemx.md` §3.1）：
  `project path D:\scratch\gen` + `project name foo` → 产物落到 `D:\scratch\gen\foo\`。
  想落到仓库根目录，用 `config load` + `project generate`（按 `.ioc` 所在目录生成）。

### 第 5 步 · **生成核验（G1，硬关卡）**

```
TODO(T1.2)：此处待 verifier-dev 交付后填写——
  - 调用方式与入参
  - 退出码语义（0 = 通过？非 0 各代表什么）
  - JSON 报告字段（哪一项对应"外设被静默丢弃"）
  - 白名单参数怎么传（D8 的 VP_RIF_VS_RIF1 噪音必须能容忍）
```

**在 `TODO(T1.2)` 回填前，人工兜底核验清单**（📄 `AGENTS.md` §2.3 + D5，缺一不可）：

1. 生成日志里**没有** `Cannot map`；也没有与本次改动相关的 `OptionalMessage_ERROR`。
   例外：`Pin5 (VP_RIF_VS_RIF1) cannot be retrieved for this MCU` 是 **G474 已知噪音**（D8），
   加了它不算失败，**也不要为它删外设去"修"**。
2. 本次期望的每个外设，在 `Core/Src/main.c` 里都有 `MX_xxx_Init()` 的**定义**，
   **并且**在 `main()` 里被**调用**。只有定义没有调用，等于没初始化（这是 H-6 的典型表现）。
3. `.mxproject` 里**没有盘符绝对路径**：`grep -c "[A-Z]:" .mxproject` 应为 0（📄 §3.2）。
   出现了说明是"先生成到别处再搬回来"留下的绝对路径，需要原地 `config load` + `project generate` 一次。
4. `syscalls.c` / `sysmem.c` 的叠加路径告警（`FileNotFoundException: <工程目录>\D:\...`）
   只降级为 **warning**，不判失败（📄 D9）：这两个文件是 newlib 桩，本就很少变。

**核验不过 → 立即回滚**：`git checkout -- <project>.ioc`（或从 `.ioc.bak` 恢复），
**不许**"先构建看看能不能过"再决定要不要管。静默丢弃的外设能构建成功，这正是它危险的地方。

### 第 6 步 · 构建

`pio_build`，然后 `pio_size_report`。**必须记录 PlatformIO 报告的 Flash / RAM 字节数**，
这是 L3 的证据本体，不是"构建成功"三个字（📄 `AGENTS.md` §3 末段）。

构建失败时用 `pio_build` 的结构化错误（解析成 `file:line`）定位，不要整段贴日志给用户。

### 第 7 步 · 汇报 diff

```bash
git diff --stat
git diff -- '*.ioc' '*.mxproject'
```

- **逐条说明**被改动的文件属于哪一类：`.ioc`（意图）／`Core/**`（生成物）／
  `.mxproject`（工具元数据）／`Drivers/**`（不该出现）。
- **`USER CODE BEGIN/END` 块之外的任何改动都要单独点名**（📄 `AGENTS.md` §2.2）：
  块外的用户代码会在下次生成时被覆盖，属于必须告知用户的风险。
- ⚠️ 若 `Core/**` 的 diff 是"整体重排"而不是"局部增删"，先查 `editor.formatOnSave`（D1），
  这是 clang-format 在保存时重排，与本次意图无关，**要单独开 `style:` 提交或直接丢弃**。
- `Drivers/`、`Makefile`、`startup_*.s`、`*.ld` 出现在 diff 里 = 出错信号（📄 `AGENTS.md` §2.4）：
  这些由 PlatformIO framework 提供，已在 `.gitignore` 排除。

### 第 8 步 · 提交

按 §4 的模板写。**不允许**只写"生成代码"。

---

## 3. 验证等级声明（L0–L5）

📄 定义来自三个模板仓的 `AGENTS.md` §3，本仓原样沿用，**不重新定义**。
提交正文必须写明"做到了哪一级"，没验证就写"未验证"。

| 等级 | 做什么 | 适用 | 在本仓里算什么证据 |
|---|---|---|---|
| **L0** 未验证 | 只读检查 | 仅限纯文档 | 无证据。**纯文档改动才允许 L0** |
| **L1** 静态 | 人工核对文件内容一致性 | 文档、配置 | 核对记录（看了哪个文件、比了哪一处） |
| **L2** 主机回归 | 主机 gcc 跑可主机编译的代码 | 动了 `Core/Src/stdio_port.c` 这类 | `gcc` 命令 + 通过输出 |
| **L3** 构建 | `pio run` | **任何影响编译的改动** | PlatformIO 的 Flash / RAM 字节数 |
| **L4** 生成核验 | CubeMX 重新生成后核对 `main.c` 的 `MX_xxx_Init` 与日志 | **任何 `.ioc` 改动（必须）** | 核验器 JSON / 人工兜底清单结果 |
| **L5** 实板 | 烧录 + 观察现象（LED / 串口 / 波形） | 影响运行时行为的改动 | 烧录日志 + 现象描述（当前无硬件，一律缺） |

### 3.1 主机回归命令（L2，不需要开发板）

```bash
mkdir -p .pio/host-test
gcc -std=c11 -Wall -Wextra -Werror Core/Src/stdio_port.c test/stdio_port_test.c -o .pio/host-test/stdio-test && ./.pio/host-test/stdio-test
gcc -std=c11 -Wall -Wextra -Werror -DTEST_BACKEND Core/Src/stdio_port.c test/stdio_port_test.c -o .pio/host-test/stdio-backend-test && ./.pio/host-test/stdio-backend-test
pio run
```

### 3.2 三条不许混的边界

1. **`.ioc` 改动没有 L4 就是没做完**，不是"L3 也算过"。
2. **构建通过 ≠ 能用**（📄 `AGENTS.md` §3）。影响运行时行为的改动必须 L5；本会话无硬件，
   所以这类改动只能如实写"L3，实板未验证"。
3. **不要复用旧构建数字当本次证据**（📄 同上）。改了代码就重跑，没重跑就明说没跑。

---

## 4. 提交文案模板

📄 规范来自 `AGENTS.md` §1，此处给可直接套用的模板。

```
<type>(<scope>): <中文简述，动词开头，≤50 字，不加句号>

为什么这么改（不要复述 diff）。

验证等级：L<n> — <实际执行的命令与结果>
  - 生成核验：<核验结论 / 人工兜底清单逐条结果>
  - 构建：Flash <bytes> / RAM <bytes>（pio run）
  - 实板：未验证（无硬件）
已知风险：<本次没覆盖到的部分>
```

- `<type>` 只能取：`feat` `fix` `docs` `chore` `refactor` `test` `build` `ci` `perf` `style` `revert`。
- `<scope>`：`ioc` `pio` `board` `vscode` `scripts` `core` `git` `docs`。
- **一个提交只做一件事**：格式化/行尾归一必须单独开 `style:` / `chore:`，不许和功能改动混提交。
- **硬性禁止**（📄 `AGENTS.md` §1.5）：`git push --force`（含 `-f`）、`--no-verify`、
  `--no-gpg-sign`、以及**提交信息里的任何 AI 署名尾注**（`Co-Authored-By: <AI>`、`Generated by ...`）。

---

## 5. 陷阱速查

只给"症状 → 判据 → 处置"和原文链接，**不复制原文**。
D1–D9 出自模板仓 `TEMPLATE-PLACEHOLDERS.md` §D，H-1–H-6 出自 `docs/HAL-PITFALLS.md`。

> ⚠️ **链接注意**：`HAL-PITFALLS.md` **只存在于 `template-mcu-STM32F103C8T6` 与
> `template-mcu-STM32H723-series` 两仓，G474 仓没有这个文件**。
> 链接必须指向 F103 / H723，不要指向 G474。完整 URL 见 `references/README.md`。

### 5.1 D 系列（工具/模板层）

| # | 症状 | 判据 | 处置 |
|---|---|---|---|
| D1 | `Core/**` 保存后出现与本次无关的整体重排 diff | 编辑器 `editor.formatOnSave: true` | 处理 `Core/**` 时关掉它，或加 `// clang-format off` |
| D2 | 只有行尾变化的巨大 diff | `git ls-files --eol` 显示 CRLF/LF 混杂 | 严格按仓库既有策略，**不提交纯行尾变化** |
| D3 | 写了参数但 CubeMX 当没看见 | 对应 `<IP>.IPParameters` / `<Pin>.GPIOParameters` 白名单里没有这个 key | 两处一起补 |
| D4 | 信号名"对"但配置失败 | 少了 `S_` 前缀（应为 `S_TIM2_CH1_ETR`） | 查 `db/mcu/<型号>.xml` 再写 |
| D5 | **生成返回成功，外设却没了** | 日志有 `Cannot map signal` | 这就是"静默丢弃"，走 §2 第 5 步 |
| D6 | 新克隆仓库 `Drivers/` 只有 `.gitkeep` | 这是**预期**的，HAL/CMSIS 由 PlatformIO framework 提供 | 不要试图提交 `Drivers/` |
| D7 | 无头生成卡在 `Begin LoadConfig()` 不动 | `ProjectManager.AskForMigrate=true` | 改回 `false` 再跑 |
| D8 | G474 日志总有 `Pin5 (VP_RIF_VS_RIF1) cannot be retrieved` | 属 6.18.1 的 G4 数据库噪音，与本次引脚无关 | **忽略**，不要为它删外设 |
| D9 | 日志报 `FileNotFoundException: <工程目录>\D:\...\syscalls.c`，这两文件不更新 | 叠加路径问题 | 只需从 FW 模板目录复制或删后重生成；**不判生成失败** |

### 5.2 H 系列（HAL 运行期）

| # | 症状 | 判据 | 处置 |
|---|---|---|---|
| H-1 | UART 能发不能收 | `HAL_UART_Receive_IT()` 不代替 NVIC 配置；`.ioc` 里该 USART 的 NVIC 是否启用 | 先配 NVIC 并重生成，再查 MSP 优先级与 `HAL_NVIC_EnableIRQ()`、IRQ handler |
| H-2 | `Base_Start` 后 READY 自检失败 | `HAL_TIM_Base_Start()` 把整体状态置 BUSY；`HAL_TIM_IC_Start_DMA()` 查的是**通道**状态 | 分别检查整体状态 / 通道状态 / 返回值，别把两个状态机混为一谈 |
| H-3 | 停一次捕获 DMA 后共享时基不动了 | `HAL_TIM_IC_Stop_DMA()` 会 `__HAL_TIM_DISABLE()`，但有其他通道开着时不清 CEN | 明确计数器的唯一管理者，或改用独立定时器 |
| H-4 | 高频采集偶发 `CC1OF` | `HAL_TIM_IC_Start_DMA()` 的"开通道→起 DMA→开请求"窗口会丢捕获 | 在采集协议层控制启动顺序；清标志只能当"允许丢启动段"的特定策略，会掩盖真实溢出 |
| H-5 | 初始化失败后串口一个字都没有 | 故障可能发生在 UART 初始化之前；`Error_Handler()` 关中断进死循环 | **保留**模板的停机行为；容错降级路径必须单独设计并验证，不要简单改成 return |
| H-6 | **新增外设没落入生成物，日志还没 `Cannot map`** | 加载后写回的 `.ioc`、生成日志、`MX_xxx_Init()` 的定义**和**调用、HAL 模块开关、MSP、IRQ/NVIC 逐项核对 | 用 GUI 配一遍并比对差异；"日志无错误"只是条件之一 |

> H-6 是 G1 核验器存在的**唯一理由**：它是"返回成功但什么都没做"的静默失败，
> 所以 §2 第 5 步才必须是硬关卡，不能只是"建议检查"。

---

## 6. 串口与烧录（Phase 2，**本会话挂起**）

> ⚠️ 当前无硬件，本节**不做任何能力宣称**。T2.1–T2.6 全部挂起至 GATE-2.0 接板日
> （✅ `docs/DECISIONS.md` D7、`docs/TASKBOARD.md` 第 2 节）。

`TODO(T3.3)` 待接板后填写：

- `flash_standalone` 的 `reset` / `run` 语义与烧录后现象判据；
- `pio_monitor_capture` 抓 boot log 的波特率/超时约定；
- 板上无 VCP 时改外接 USB-TTL 的接线与方案；
- 探针被拔 / 串口被占用时 `pio_port_diagnose` 与 `doctor` 的错误分类读法；
- L5 证据的留存形式（烧录日志 + 现象描述/照片）。

**在实测之前，任何关于烧录的说法都只能写成"未验证"。**

---

## 7. 参考与依赖

- 模板仓关键文档的**链接**（不复制内容）：`references/README.md`。
- 任务与进度真源：`docs/TASKBOARD.md`；已确认决策（含 D1–D11）：`docs/DECISIONS.md`。
- 执行计划与调研报告：`docs/2026-11-03-agent-team-plan.md`、`docs/2026-11-03-execution-research.md`。
- 单写者边界（计划 §0.2-1）：`scripts/`、`tests/` → verifier-dev；
  `SKILL.md`、`docs/`、`README.md`、`references/` → skill-author；`testbeds/` → scenario-tester；
  `.github/` → ci-agent。**本文件只由 skill-author 改**，别人要改请走 lead 转派。

---

## 8. 变更记录

| 版本 | 日期 | 变更 | 任务 |
|---|---|---|---|
| 0.1.0 | 2026-11-03 | 建骨架：frontmatter + 章节大纲 + TODO 标记 | T1.1 |
| 0.2.0 | 2026-11-03 | 初稿：§0 硬前提、§2 八步流程、§3 L0–L5 判据、§4 提交模板、§5 陷阱速查全部写完；§1 核验器接口留 `TODO(T1.2)`；§6 挂起 | T1.4 |
| 待定 | — | 回填 §1 核验器接口 + 同行评审 | T1.2 → T1.4 |
| 待定 | — | 定稿（吸收 S1–S3 实测教训） | T1.9 |
| 待定 | — | 合并 Phase 2 串口/烧录增量 + L 等级自查清单 | T3.3 |
