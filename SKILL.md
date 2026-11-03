---
name: platform32-mcp
description: "STM32 工程全流程编排：把 .ioc 改配置 → CubeMX 代码生成 → 生成核验（G1 强制关卡，verify_generation.py）→ PlatformIO 构建 →（接板后）烧录与串口验证 串成一条带 L0–L5 验证等级声明的流水线，并输出符合模板 AGENTS.md 提交规范的 commit。同时提供双通道执行：已注册 MCP（vscode-cube-mcp / platformio.mcp）走工具通道，未注册走 CubeMX CLI + pio CLI 等价通道，两条通道的判据与证据要求完全相同。当用户说「改一下这个 ioc」「加一个 GPIO / UART / ADC 通道」「CubeMX 重新生成代码」「生成完帮我核一遍」「有没有被静默丢弃的外设」「pio 构建一下」「Flash/RAM 占多少」「烧进去看看」「串口有输出吗」「这个模板工程跑不起来」时使用。只读审计不写盘；任何写操作前必须先备份 .ioc 并报告将改动的对象，生成后必须跑核验器并如实声明验证等级；不替用户提交未经核验的代码，不碰 testbeds/ 之外的模板原仓。"
version: 0.3.2
agent_created: true
license: MIT
compatibility: Python 3.8+（核验器只依赖标准库）；CubeMX 6.18.1（路径不固定，见 §0.2）；PlatformIO Core 6.x；MCP 通道可选，未注册时用 §0.4 的 CLI 等价命令
---

# platform32-mcp：STM32 生成 / 核验 / 构建 / 烧录编排

> **状态：v0.3.0 初稿（T1.4）。** §1 已按 verifier-dev 的 T1.2 实现回填，§0/§2/§5 已改为双通道写法。
> 尚未执行：同行评审（team-lead 做）。Phase 2 烧录/串口段（§6）本会话无硬件，整体待接板（决策 D7）。

**本仓交付的是"编排知识 + 核验器 + 文档"，不是替用户装配本机 MCP 工具链**
（✅ `docs/DECISIONS.md` D12）。三个 server 在用户机器上**默认不存在**，
所以本文每一步都必须给出**两条通道**：MCP 工具调用，以及等价的 CLI 命令。
两条通道的**判据与证据要求完全相同**——通道不同只影响"怎么调"，不影响"怎么算过"。

三个领域 server 各管一段，**没有任何一个 server 管"改完有没有真的生效"**。
本 Skill 存在的理由就是补上那一段（G1 核验器），并且**每个环节都留下可核验的证据**，
否则不许声明完成。

---

## 本文可信度标注

本文每条结论都标来源，**不要**把三类混为一谈：

| 标记 | 含义 | 你敢不敢依赖 |
|---|---|---|
| ✅ | 本机实测（含读源码 / 跑 `--help` / 真实运行产物），证据在仓库内路径 | 可以 |
| 📄 | 引自模板仓文档或官方命令表（见 `references/README.md` 的链接） | 可以，但要按链接回原文看上下文 |
| ⚠️ | 尚未实测的推断 / 待办 | **不要**，等实测填回来 |

未标注的一律按 ⚠️ 处理。**本文不许出现第四个来源。**

---

## 0. 硬前提（双通道）

### 0.1 通道选择的唯一判据

先判断"有没有 MCP"，再干活。**不要**默认有，也**不要**默认没有：

| 判定 | 通道 | 说明 |
|---|---|---|
| `cubemx_help`、`pio_system_info` 调用成功 | **MCP 通道** | 优先用，省掉手搓命令行 |
| 上述调用不存在 / 报"未知工具" | **CLI 等价通道** | 用 §0.4 的命令，判据照旧 |

注册方法见 `docs/guides/mcp-registration.md`（✅ 已落盘；注册属用户自己的选择，
**本仓不替用户改 `~/.workbuddy/mcp.json`**，见 `docs/DECISIONS.md` D12）。

**两条通道都不可用时停手报错**，不许降级成"手改 `.ioc` 文本"绕过核验（理由见 §2 第 5 步）。

### 0.2 CubeMX / PlatformIO 的定位（两通道共用）

| 项 | 值 | 备注 |
|---|---|---|
| CubeMX 可执行文件 | `C:\ST\STM32CubeMX\STM32CubeMX.exe` | 📄 **不在** `C:\Program Files\STMicroelectronics\...` |
| 自带 JRE | `C:\ST\STM32CubeMX\jre\bin\java.exe` | 📄 调用方式为 `java -jar STM32CubeMX.exe -q <script.mx>` |
| 版本 | 6.18.1 / `MxDb.Version=DB.6.0.181` | ✅ 锁定值（D1）；**以 exe 属性或运行日志为准，别信 `.ioc` 里的版本戳**（见 P2） |
| 单次生成耗时 | 约 **60 s**（JVM 启动 + CMSIS 拷贝） | ✅ 超时阈值**不得低于 240 s**（`regen.sh` 的最小值） |
| `pio` 可执行文件 | `C:\Users\Leon\.platformio\penv\Scripts\pio.exe` | ✅ Core 6.2.0 |

**MCP 通道额外要求**（仅当走 §0.1 的 MCP 分支）：server 进程的 env 决定行为，
不是本机用户级环境变量——`ST_CUBEMX_EXE`、`ST_CUBEMX_ALLOWED_ROOTS`（**路径白名单**，
换工作目录必须同步改）、`ST_CUBEMX_TIMEOUT=300`、`PLATFORMIO_MCP_POLICY=build_only`、
`PLATFORMIO_MCP_PIO`。✅ 证据：`docs/logs/phase0/`（doctor + 握手日志，`tools_count: 9`）。
**CLI 通道没有白名单保护，所以 §0.3 第 2 条红线在 CLI 通道下更要靠人守。**

### 0.3 三条红线（与通道无关）

1. **要烧录就必须显式确认**。MCP 通道下 `PLATFORMIO_MCP_POLICY=build_only` 会拒绝烧录；
   CLI 通道下**没有任何东西会拦你**，只能靠人不敲 `-t upload`。烧录属于 L5，
   且需经 `team-lead` 向用户确认（GATE-2.1）。
2. **只在 `testbeds/` 的克隆副本里做写操作**。`D:\Projects\GitHub\` 下三个 `template-mcu-*`、
   `NUEDC_2027`、`HUSTRadio`、`leonskill-*` **一律只读**（✅ `docs/DECISIONS.md` D9）。
3. **生成后不核验 = 没做**。CubeMX 对 `.ioc` 的错误是**非致命**的：信号名写错只留一行日志，
   生成仍返回成功，外设被静默丢弃（📄 `AGENTS.md` §2.3、陷阱 D5、H-6）。

### 0.4 CLI 等价通道（每条都给可复制的命令）

```bash
# ① 生成代码（等价于 MCP 的 cubemx_generate）
"C:\ST\STM32CubeMX\jre\bin\java.exe" -jar "C:\ST\STM32CubeMX\STM32CubeMX.exe" -q "<工程>\scripts\cubemx-generate.mx"
#    超时 ≥240s；日志要重定向到文件，核验器必须吃这份日志（§2 第 5 步）

# ② 构建（等价于 pio_build）
"C:\Users\Leon\.platformio\penv\Scripts\pio.exe" run -d "<工程>"

# ③ 生成核验（无 MCP 对应物，G1 本来就只有 CLI）
python scripts/verify_generation.py --log <cubemx.log> --main-c "<工程>\Core\Src\main.c" \
    --mxproject "<工程>\.mxproject" --expect GPIO,TIM4 --allow-signal VP_RIF_VS_RIF1 \
    --json-out <证据目录>\verify.json
```

⚠️ 以下两条 Phase 2 才用，**本会话未实测**：烧录 `pio run -d <工程> -t upload`；
串口 `pio device monitor`（参数以接板后实测为准）。

---

## 1. 能力索引

### 1.1 本仓自研（唯一不可替代的部分）

| 能力 | 入口 | 接口来源 |
|---|---|---|
| **生成核验（G1 硬关卡）** | `scripts/verify_generation.py` | ✅ 读源码 + `--help` 核对 |
| 备份 → 生成 → 核验，失败自动回滚 `.ioc` | `scripts/regen.sh <工程目录> -e GPIO,TIM4` | ✅ 读源码 |
| 单独备份 / 还原 `.ioc` | `scripts/ioc_backup.py --project <工程根> [--restore\|--list] [--json-out]` | ✅ 读源码 |

### 1.2 双通道对照

| 想做的事 | MCP 通道 | CLI 等价通道 |
|---|---|---|
| 只读回读 `.ioc`（审计） | `cubemx_load` | 直接读 `.ioc` 文本（ini 格式，人可读）；引脚表用 ⚠️ `csv pinout`（官方命令表有，本仓未实测） |
| 改外设配置 | 📄 见 §2 第 3 步（工具名待定，**不要**想当然用 `cubemx_configure`） | 写 `.mx` 脚本里的 `set` 命令序列（📄 `stm32-digital-clock/scripts/cubemx-init.mx` 有完整写法） |
| 生成代码 | `cubemx_generate` | §0.4 ① |
| 构建 | `pio_build` | §0.4 ② |
| 尺寸报告 | `pio_size_report` | `pio run` 输出的 Memory Usage，**但必须看 P3** |
| 烧录 / 串口 | `flash_standalone` / `pio_monitor_capture` | ⚠️ §0.4 末两条，Phase 2 未实测 |

> **参数签名一律以运行时为准**：MCP 通道看 `cubemx_help` 与工具描述，CLI 通道看 `--help`。
> 本文只写"已核对过的"签名（1.1 的三个脚本），其余不复述。

### 1.3 `verify_generation.py` 契约（v1.0.0，schema `platform32.verify_generation/1`）

```bash
python scripts/verify_generation.py \
    --log <CubeMX 原始生成日志> \
    --main-c <工程>/Core/Src/main.c \
    --mxproject <工程>/.mxproject \
    --expect GPIO,TIM4,USART2 \
    [--allow-signal VP_RIF_VS_RIF1] \
    [--json-out <path>] [--report-md <path>]
```

- `--log` / `--main-c` / `--mxproject` / `--expect` **四个都必填**（没有默认值）。
  `--expect ""`（空串）= 只查路径类问题、不查外设。
- `--allow-signal` 可重复、可逗号分隔，**默认不预置任何白名单**。
  ⚠️ **直接调脚本时，G474 必须显式加 `--allow-signal VP_RIF_VS_RIF1`**；
  而 `regen.sh` 默认已预置它（用 `--no-default-allow` 关掉）——两处默认值不同，别混。
- **退出码**：`0` = 通过（可含 warning）；`1` = 存在 fail 级问题；`2` = 输入/IO/参数错误
  （`regen.sh` 复用 `2` 表达"前置检查拒绝生成"）。

**JSON 结构**（`--json-out`）：

```json
{"schema":"platform32.verify_generation/1", "verdict":"pass|fail",
 "checks":[{"id":"...","status":"pass|warn|fail|skip","level":"error|warning","detail":"..."}],
 "summary":{"errors":0,"warnings":0,"checked_peripherals":["GPIO"]},
 "inputs":{"log":"...","main_c":"...","mxproject":"..."},
 "expect":["GPIO"], "allow_signals":["VP_RIF_VS_RIF1"],
 "tool":{"name":"verify_generation.py","version":"1.0.0"}}
```

> **读报告的坑**：`level` 是由 `status` **派生**的（`warn`/`skip` → `warning`，其余 → `error`），
> 它表达"这条检查失败时阻不阻塞"，**不表达"本次有没有问题"**。
> 判定请只看 `verdict` 与各条 `status`；`level` 只用于粗筛和展示。
> 真实产物样例：通过样本 `docs/logs/phase1/regen-success/verify.json`；
> **失败样本 `docs/logs/phase1/regen-rollback/verify.json`**（可直接用来对照"fail 长什么样"，
> 写负路径场景文档时引这份，不要自己臆造失败输出）。
> 完整判定细节（含容错匹配规则、`regen.sh` 全部选项）：`docs/reports/t1.2-verifier-contract.md`。

### 1.4 检查项判据

**已实现（v1.0.0，共 5 项）**

| id | 阻塞？ | 判据 | 失败意味着 |
|---|---|---|---|
| `log_cannot_map` | 是 | 日志无 `Cannot map`；命中 `--allow-signal` 的信号降为 warn | 有信号名/引脚映射失败，对应外设大概率被丢弃 |
| `main_init_present` | 是 | 每个期望外设都有 `MX_<P>_Init(` **定义**（UART 走后缀候选匹配，如 `MX_USART2_UART_Init`） | 外设没进生成物（H-6 典型表现） |
| `main_init_called` | 是 | 每个 `MX_*_Init(` 在 `main()` 体内**被调用**（排除被注释掉的调用） | 函数生成了但没跑 = 等于没初始化 |
| `mxproject_abs_path` | 是 | `.mxproject` 无 `[A-Za-z]:[\\/]` 盘符路径 | 换机器不可复现（P4） |
| `syscalls_path` | **否** | 日志出现 `syscalls.c` / `sysmem.c` 叠加路径异常 → **warn** | 这两个 newlib 桩本次未更新，属 CubeMX 已知缺陷 D9，不阻塞 |

> `log_cannot_map` 的 detail 会附带说明：另有 `OptionalMessage_ERROR`（如 G474 的
> `VP_RIF_VS_RIF1`，D8）**不计入判定**。看到它不算失败，也不要为它删外设。

**读报告的三个细节（✅ 已与 verifier-dev 核对实现，2026-11-03）**

1. **`skip` 不等于"通过"，也不等于"失败"**，它表示"这项没检"。两种触发：
   - `--expect ""` → `main_init_present` 与 `main_init_called` 都 `skip`；
   - 期望外设**一个定义都没找到** → `main_init_called` 也是 `skip`（不是 fail）。
     同一个根因只在 `main_init_present` 报一次 fail，避免双计；detail 会写明
     "另有 N 个外设无定义、未参与本项：TIM4"——**这行是重要线索，别跳过**。
   - 写证据时：`skip` 必须解释原因，不能记成"检查通过"。
2. **空日志 → `warn`，不是 `pass`**。日志为空/纯空白时 `log_cannot_map` 报
   "生成日志为空，无法确认生成是否真的跑过"，`verdict` 仍可能是 pass。
   **"日志干净"必须由真实日志证明，不能由空文件证明**——写证据时别把这种 warn 当干净。
3. **`syscalls_path` 要"文件名 + 异常关键字"同时出现才 warn**（`syscalls.c`/`sysmem.c`
   且同一行含 `FileNotFoundException` / `exception` / `拒绝访问` 等）。
   只提到文件名不会误报——所以这条 warn 基本可以当 D9 的确定性证据。

另：JSON 里**没有时间戳**（便于 diff 与快照比对），时间戳只在 `--report-md` 里。
`expect` / `allow_signals` / `tool` 是留痕字段，已写进契约文档。

**书面契约之外的扩展需求（3 项，v1.0.0 未实现）** —— ⚠️ 注意：这 3 项**不在**
`docs/reports/t1.2-verifier-contract.md` 的契约里（该文档 §1.4 只定义 5 个 check id），
是 lead 在 T1.4 派活时提出的**扩展意向**。要在 v1.1 加上，得**先改契约文档**再改实现，
否则下游（本文、S1–S3 场景、CI）会按不同版本的行为各自假设。
**在实现并写入契约之前，不要依赖，也不要在命令里传下表中的新参数**：

| id | 阻塞？ | 拟判据 | 需要的入参 |
|---|---|---|---|
| `mx_script_abs_path` | 是 | `--project-root` 下 `**/*.mx` 无盘符路径；不传则 `skip` | `--project-root <工程根>` |
| `ioc_ask_for_migrate` | 是 | `.ioc` 含 `AskForMigrate=true` → 非交互生成会**阻塞到超时**（P1）；不传则 `skip` | `--ioc <工程根/xxx.ioc>` |
| `ioc_version_stamp` | 否 | `.ioc` 的 `MxCube.Version` 与锁定 6.18.1 不一致 → 重新生成会产生噪音 diff（P2） | `--ioc` |

**这 3 项落地之前的替代做法**（写进 §2 第 5 步，别当成实现了）：

```bash
grep -rn "project path" --include='*.mx' <工程根> | grep -Ei '[A-Za-z]:' # 应为空（P4）
grep -n "AskForMigrate" <工程根>/*.ioc                                  # 应为 false（P1）
grep -n "MxCube.Version" <工程根>/*.ioc                                 # 应为 6.18.1（P2）
```

---

## 2. 标准流程（写操作，八步）

适用：用户要"改 `.ioc` 里的某个外设/引脚/时钟，然后重新生成并构建"。
**只读审计（S2）跳过 2–6，直接做 1 + 7**。每个"做什么"后面都括号标了通道差异。

### 第 0 步 · 前置检查

- §0.1 定通道；§0.2 核对 CubeMX / pio 路径。
- `git status` 必须干净（只允许 `testbeds/`、`docs/logs/` 下被忽略的产物）。
  有未提交改动 → 先问用户，别把用户的手改混进本次 diff。
  （`regen.sh` 默认就会**拒绝**在 `.ioc` 有未提交改动时继续，`--allow-dirty-ioc` 才放行——
  这是为了防止回滚把用户改动一起 checkout 掉。）
- 核验器可用性：`python scripts/verify_generation.py --version` 应打印
  `verify_generation.py 1.0.0 (schema platform32.verify_generation/1)`。
  **核验器不可用就不许进第 3 步**。

### 第 1 步 · 只读审计（不改一个字节）

MCP 通道用 `cubemx_load` 回读；CLI 通道直接读 `.ioc` 文本（ini 格式）。
产出**改动前的基线**：当前启用了哪些外设、哪些引脚是什么模式、时钟树关键键值。

价值在于**回滚时有对照物**，并能证明"这个外设原本就不存在"，而不是"被我们改没了"。

### 第 2 步 · 备份 `.ioc`

```bash
python scripts/ioc_backup.py --project <工程根> --json-out <证据目录>/ioc-backup.json   # 首选
cp <工程>/*.ioc <工程>/*.ioc.bak                                                        # 兜底，.gitignore 已忽略
```

`ioc_backup.py` 会顺带记录 SHA-256（`--json-out` 里有），**这份哈希就是回滚时"确实还原了原件"的凭据**。
`--restore` 从 `.ioc.bak` 还原；`--list` 只看不写。

**备份必须先落盘再做第 3 步**——CubeMX 的写回不可逆（📄 `AGENTS.md` §2.3）。

### 第 3 步 · 改配置（⚠️ 方案待 T1.6 实测确认）

> ⚠️ **这一节的方法论尚在验证中。已确认的只有"能力在哪"，尚未确认"用哪个工具/怎么调"。**

已确认的事实（两个独立证据，📄 见 `docs/DECISIONS.md` 与 `docs/reports/` 的相关记录）：

1. `vscode-cube-mcp` 的 `configure(ioc_path, commands, dry_run, timeout_sec)` —— `commands` 是**顶层必填**，
   **没有任何外设结构化参数**，本质就是把命令序列塞进脚本再执行。**它不是"改外设"的 API。**
2. **配外设的能力在 `.mx` 脚本语言里**：`project name` / `project path` / `set mode` / `set pin` /
   `set gpio` / `set ip` 这一整套，实例见 `HUSTRadio/stm32-digital-clock` 的 `scripts/cubemx-init.mx`。
3. 因此"改已有 `.ioc` 的某个引脚"最可能的正确打法 = **写一份只含 `set` 命令的临时 `.mx`，
   `config load` 已有 `.ioc` 之后执行**——而不是指望 `cubemx_configure` 直接改结构。

**在 T1.6 给出实测结论之前：**

- **不要**相信"`cubemx_configure` 能加 GPIO"这种说法，包括本文的早期版本。
- 需要立刻动手时，退回**已验证**的两条路：CubeMX GUI 改完保存 → 生成；
  或用 `.mx` 脚本显式写 `set` 命令（CLI 通道，§0.4 ①）。
- **不要手改 `.ioc` 文本**。手改仅限极小改动，且必须补两处白名单（📄 D3）：
  每个外设一行 `<IP>.IPParameters=a,b,c`（不在白名单的 key 会被忽略）；
  每个引脚一行 `<Pin>.GPIOParameters=...`（例：`PC13.GPIOParameters=PinState` 才让 `PC13.PinState` 生效）。
- **信号名带 `S_` 前缀**（📄 D4）：PA0 上 TIM2 通道 1 的正确写法是 `S_TIM2_CH1_ETR`，
  写成 `TIM2_CH1_ETR` 会失败。以 `C:\ST\STM32CubeMX\db\mcu\<型号>.xml` 为准，先查库再写。

### 第 4 步 · 生成

生成前**必须**先查 P1（`AskForMigrate`，否则会卡到超时且日志没线索）：

```bash
grep -n "AskForMigrate" <工程根>/*.ioc     # true → 先处理迁移，别硬跑
```

然后 MCP `cubemx_generate` 或 CLI §0.4 ①。**日志必须落到文件**，第 5 步要吃它。
另两个已知坑：`project path` 会再追加一层工程名（📄 `TOOLING-cubemx.md` §3.1）；
`syscalls.c` / `sysmem.c` 叠加路径会让这两个文件不更新（D9，不阻塞）。

一行命令同时做完"备份 + 生成 + 核验 + 失败回滚"的封装是 `regen.sh`：

- `-e, --expect` **可省略**——省略时它从 `.ioc` 的 `Mcu.IP*` **自动推导**（滤掉
  `NVIC/RCC/SYS/DBGMCU` 再补 `GPIO`）。自动推导是"全量"语义，**不等于**"你本次期望的"；
  要精确控制就显式传 `-e`（例：`regen.sh <工程> -e GPIO,TIM4 --out <证据目录>`）。
- `--out` 默认落 `${TMPDIR:-/tmp}/platform32-regen`，**故意不落在工程里**，避免污染 `git status`。
  但当次证据要入库时，显式 `--out docs/logs/phaseN/<场景>/`。
- 还有 `--dry-run`（先看命令）、`--skip-generate`（只重跑核验）、
  `--allow-dirty-ioc`（放行有未提交改动的 `.ioc`，默认拒绝）。

### 第 5 步 · **生成核验（G1，硬关卡）**

```bash
python scripts/verify_generation.py \
    --log <证据目录>/cubemx-generate.log \
    --main-c <工程根>/Core/Src/main.c \
    --mxproject <工程根>/.mxproject \
    --expect GPIO,TIM4 \
    --allow-signal VP_RIF_VS_RIF1 \
    --json-out <证据目录>/verify.json --report-md <证据目录>/verify.md
```

- **`--expect` 写什么**：本次**期望存在**的每个外设。漏写 = 漏检（核验器只查你点名的）；
  多写 = 假失败。以第 3 步的意图为准，不要照抄 `.ioc` 的全文。
- **退出码 1 或 `verdict: "fail"` → 立即回滚**（`ioc_backup.py --restore` 或
  `git checkout -- <工程>/*.ioc`），**不许**"先构建看看能不能过"再决定要不要管。
  静默丢弃的外设**能构建成功**，这正是它危险的地方（H-6）。
- 退出码 2 = 我们自己的输入错了（路径写错/文件不存在），**不是**"配置有问题"，别误报给用户。
- `syscalls_path` 报 warn **不阻塞**，但要写进汇报（D9）。
- 任何一条 `status: "skip"` 都要在汇报里解释原因（`--expect` 空？外设全无定义？），
  **不能当成"通过"**；`log_cannot_map` 因**日志为空**而报 warn 时，先去确认 `--log` 指对了文件。
- **1.4 里那 3 项扩展检查（v1.1 才可能落地）当前必须手工补**，
  用 1.4 末的三条 `grep`，结果一并贴进汇报——**不要**因为"核验器过了"就跳过这三条。

**核验器不可用时不许开工**（第 0 步已查）。它的唯一职责就是抓 H-6 那种"返回成功但什么都没做"，
没有它这条流水线等于没有安全网。

### 第 6 步 · 构建

MCP `pio_build` / CLI `pio run -d <工程>`，然后取尺寸：
MCP `pio_size_report`，CLI 看 `pio run` 的 Memory Usage。
**必须记录 Flash / RAM 字节数**，这是 L3 的证据本体，不是"构建成功"三个字（📄 `AGENTS.md` §3）。

⚠️ **数字要按 P3 校正**：PlatformIO 内置 size **不把 stack/heap 预留算进 RAM**。
要对外报数，以链接器 `--print-memory-usage` 或 bin 实际字节为准，并注明用的是哪一种口径。

构建失败时用 `pio_build` 的结构化错误（解析成 `file:line`）定位，不要把整段日志甩给用户。

### 第 7 步 · 汇报 diff

```bash
git diff --stat
git diff -- '*.ioc' '*.mxproject' 'scripts/*.mx'
```

- **逐条说明**被改动的文件属于哪一类：`.ioc`（意图）／`Core/**`（生成物）／
  `.mxproject`（工具元数据）／`Drivers/**`（不该出现）。
- **`USER CODE BEGIN/END` 块之外的任何改动都要单独点名**（📄 `AGENTS.md` §2.2）：
  块外的用户代码会在下次生成时被覆盖，属于必须告知用户的风险。
- ⚠️ 若 `Core/**` 的 diff 是"整体重排"而不是"局部增删"，先查 `editor.formatOnSave`（D1）：
  那是 clang-format 在保存时重排，与本次意图无关，要单独开 `style:` 提交或直接丢弃。
- ⚠️ 若 `.ioc` 的 diff 是**几百行整文件重写**，先查 P2（版本戳不一致），
  拆成独立的 `chore(ioc):` 提交，别和功能改动混在一起。
- `Drivers/`、`Makefile`、`startup_*.s`、`*.ld` 出现在 diff 里 = 出错信号（📄 `AGENTS.md` §2.4）。

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
| **L3** 构建 | `pio run` | **任何影响编译的改动** | PlatformIO 的 Flash / RAM 字节数（口径见 P3） |
| **L4** 生成核验 | CubeMX 重新生成后核对 `main.c` 的 `MX_xxx_Init` 与日志 | **任何 `.ioc` 改动（必须）** | `verify.json`（`verdict` + 各 `status`） |
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
   这类改动只能如实写"L3，实板未验证"。
3. **不要复用旧构建数字当本次证据**（📄 同上）。改了代码就重跑，没重跑就明说没跑。

---

## 4. 提交文案模板

📄 规范来自 `AGENTS.md` §1，此处给可直接套用的模板。

```
<type>(<scope>): <中文简述，动词开头，≤50 字，不加句号>

为什么这么改（不要复述 diff）。

验证等级：L<n> — <实际执行的命令与结果>
  - 生成核验：verdict=<pass|fail>，errors=<n>，warnings=<n>
    （<证据目录>/verify.json）；未实现的 3 项检查手工结果：…
  - 构建：Flash <bytes> / RAM <bytes>（口径：pio run / --print-memory-usage）
  - 实板：未验证（无硬件）
已知风险：<本次没覆盖到的部分>
```

- `<type>` 只能取：`feat` `fix` `docs` `chore` `refactor` `test` `build` `ci` `perf` `style` `revert`。
- `<scope>`：`ioc` `pio` `board` `vscode` `scripts` `core` `git` `docs`。
- **一个提交只做一件事**：格式化/行尾归一/版本戳重写必须单独开 `style:` / `chore(ioc):`，
  不许和功能改动混提交（📄 §1.4）。
- **硬性禁止**（📄 §1.5）：`git push --force`（含 `-f`）、`--no-verify`、`--no-gpg-sign`、
  以及**提交信息里的任何 AI 署名尾注**（`Co-Authored-By: <AI>`、`Generated by ...`）。

---

## 5. 陷阱速查

只给"症状 → 判据 → 处置"，**不复制原文**。
D1–D9 出自模板仓 `TEMPLATE-PLACEHOLDERS.md` §D，H-1–H-6 出自 `docs/HAL-PITFALLS.md`，
P1–P4 是本项目 Phase 1 的**实跑记录**（✅）。

> ⚠️ **链接注意**：`HAL-PITFALLS.md` **只存在于 `template-mcu-STM32F103C8T6` 与
> `template-mcu-STM32H723-series` 两仓，G474 仓没有这个文件**。链接必须指向 F103 / H723。

### 5.1 P 系列（本项目实跑踩到的，优先级最高）

| # | 症状 | 判据 | 处置 |
|---|---|---|---|
| **P1** | `-q` 生成**卡死到超时**（约 300 s），日志里没有任何有用信息 | `.ioc` 里 `AskForMigrate=true` → 模态迁移框在等人点 | **生成前先查**（§2 第 4 步），命中就先处理迁移，别硬跑硬等 |
| **P2** | 只改了 1 个 GPIO，`.ioc` 的 diff 却是 619 增 / 106 删的整文件重写 | `.ioc` 版本戳（如 6.17.0）≠ 本机 CubeMX（6.18.1） | 重写归重写、功能归功能：拆独立 `chore(ioc):` 提交（否则违反 `AGENTS.md` §1.4 原子性）；版本戳要不要升由用户决定 |
| **P3** | 代码里报的 Flash/RAM 与 `pio run` 输出**对不上**（实测差 1540 B RAM） | PIO 内置 size **不计** stack(1024) + heap(512) 预留 | **以链接器 `--print-memory-usage` 或 bin 实际字节为准**，并在汇报里写明口径 |
| **P4** | `.mxproject` 干净，但换台机器就跑不了 | 绝对路径写死在 `scripts/*.mx`（如 `project path D:\Projects\...`） | 换成相对路径或生成时注入；核验器的 `mx_script_abs_path` 检查**尚未实现**，当前用 §1.4 末的 `grep` 兜 |

### 5.2 D 系列（工具/模板层）

| # | 症状 | 判据 | 处置 |
|---|---|---|---|
| D1 | `Core/**` 保存后出现与本次无关的整体重排 diff | 编辑器 `editor.formatOnSave: true` | 处理 `Core/**` 时关掉它，或加 `// clang-format off` |
| D2 | 只有行尾变化的巨大 diff | `git ls-files --eol` 显示 CRLF/LF 混杂 | 严格按仓库既有策略，**不提交纯行尾变化** |
| D3 | 写了参数但 CubeMX 当没看见 | 对应 `<IP>.IPParameters` / `<Pin>.GPIOParameters` 白名单里没有这个 key | 两处一起补 |
| D4 | 信号名"对"但配置失败 | 少了 `S_` 前缀（应为 `S_TIM2_CH1_ETR`） | 查 `db/mcu/<型号>.xml` 再写 |
| D5 | **生成返回成功，外设却没了** | 日志有 `Cannot map signal` | 这就是"静默丢弃"，走 §2 第 5 步 |
| D6 | 新克隆仓库 `Drivers/` 只有 `.gitkeep` | 这是**预期**的，HAL/CMSIS 由 PlatformIO framework 提供 | 不要试图提交 `Drivers/` |
| D7 | 无头生成卡在 `Begin LoadConfig()` 不动 | `ProjectManager.AskForMigrate=true` | 改回 `false` 再跑（同 P1） |
| D8 | G474 日志总有 `Pin5 (VP_RIF_VS_RIF1) cannot be retrieved` | 属 6.18.1 的 G4 数据库噪音，与本次引脚无关 | **忽略**；直接调核验器时要显式 `--allow-signal VP_RIF_VS_RIF1` |
| D9 | 日志报 `FileNotFoundException: <工程目录>\D:\...\syscalls.c`，这两文件不更新 | 叠加路径问题 | 核验器已降为 warn，**不判失败**；要更新就从 FW 模板目录复制 |

### 5.3 H 系列（HAL 运行期）

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

- `flash_standalone` 与 `pio run -t upload` 的 `reset` / `run` 语义与烧录后现象判据；
- `pio_monitor_capture` / `pio device monitor` 抓 boot log 的波特率、超时约定；
- 板上无 VCP 时改外接 USB-TTL 的接线与方案；
- 探针被拔 / 串口被占用时 `pio_port_diagnose` 与 `doctor` 的错误分类读法；
- L5 证据的留存形式（烧录日志 + 现象描述/照片）。

**在实测之前，任何关于烧录的说法都只能写成"未验证"。**

---

## 7. 参考与依赖

- 模板仓关键文档的**链接**（不复制内容）：`references/README.md`。
- 任务与进度真源：`docs/TASKBOARD.md`；已确认决策（含 D1–D12）：`docs/DECISIONS.md`。
- 执行计划与调研报告：`docs/2026-11-03-agent-team-plan.md`、`docs/2026-11-03-execution-research.md`。
- MCP 注册方法：`docs/guides/mcp-registration.md`（✅ 已落盘）。
- 单写者边界（计划 §0.2-1）：`scripts/`、`tests/` → verifier-dev；
  `SKILL.md`、`docs/`、`README.md`、`references/` → skill-author；`testbeds/` → scenario-tester；
  `.github/` → ci-agent。**本文件只由 skill-author 改**，别人要改请走 lead 转派。

---

## 8. 变更记录

| 版本 | 日期 | 变更 | 任务 |
|---|---|---|---|
| 0.1.0 | 2026-11-03 | 建骨架：frontmatter + 章节大纲 + TODO 标记 | T1.1 |
| 0.2.0 | 2026-11-03 | 初稿：§0 硬前提、§2 八步流程、§3 L0–L5、§4 提交模板、§5 D/H 速查；§1 留 `TODO(T1.2)` | T1.4 |
| 0.3.0 | 2026-11-03 | §0 改双通道（MCP / CLI 等价，D12）；§1 按 T1.2 实现回填（契约 + 5 项已实现判据 + 3 项待实现）；§2 第 3 步标"方案待 T1.6"不再写死工具名；§2 第 5 步改为真实核验器调用；§5 增 P1–P4 | T1.4 |
| 0.3.1 | 2026-11-03 | 勘误：`docs/guides/mcp-registration.md` 已落盘（取消"尚未落盘"）；那 3 项检查改为"书面契约之外的扩展意向"（`t1.2-verifier-contract.md` 只定义 5 项）；补 `regen.sh` 的 `-e` 自动推导与 `--out` 默认值 | T1.4 |
| 0.3.2 | 2026-11-03 | 与 verifier-dev 逐条核对后补：`skip` 的两种触发与"skip 不等于通过"、空日志 → warn（不能当"日志干净"）、`syscalls_path` 的双条件判据、JSON 无时间戳；引 `regen-rollback/verify.json` 作失败样本 | T1.4 |
| 待定 | — | 同行评审（lead 逐条对照 `docs/reports/t1.2-verifier-contract.md`） | T1.4 |
| 待定 | — | 定稿（吸收 S1–S3 实测教训 + `cubemx_configure` 定论） | T1.9 |
| 待定 | — | 合并 Phase 2 串口/烧录增量 + L 等级自查清单 | T3.3 |
