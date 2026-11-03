---
name: platform32-mcp
description: "STM32 工程全流程编排：.ioc 改配置 → CubeMX 生成 → 生成核验（G1 强制关卡）→ PlatformIO 构建 →（接板后）烧录与串口验证，带 L0–L5 验证等级声明与符合模板 AGENTS.md 的 commit。**能力边界（先读）：只能可靠代做普通 GPIO 级改动（新增引脚/改模式/改上下拉）；UART/SPI/TIM/ADC 等非 GPIO 外设的增改没有工具能力，必须手改 .ioc 或走 GUI，并强制过 G1。** 双通道执行：已注册 MCP 走工具通道，未注册走 CubeMX CLI + pio CLI 等价通道，判据与证据要求完全相同。当用户说「改一下这个 ioc」「加一个 GPIO」「加一路串口/SPI/定时器」「CubeMX 重新生成」「生成完帮我核一遍」「有没有被静默丢弃的外设」「pio 构建」「Flash/RAM 多少」「烧进去看看」「串口有输出吗」时使用。只读审计不写盘；写操作前必须备份 .ioc，生成后必须跑核验器并如实声明验证等级；不碰 testbeds/ 之外的模板原仓。"
version: 0.6.0
agent_created: true
license: MIT
compatibility: Python 3.11+（CI 仅覆盖 3.11 / 3.13，更早版本未验证）；CubeMX 6.18.1（路径见 §0.2）；PlatformIO Core 6.x；MCP 可选，未注册用 §0.4
---

# platform32-mcp：STM32 生成 / 核验 / 构建 / 烧录编排

> **本文件是操作面，不是手册。** 逐条细则在 `references/`：`capability-boundary.md`（能力边界）·
> `verify-contract.md`（核验器契约）· `regen-exit-codes.md`（`regen.sh`）· `diff-evidence.md`（取证判据）·
> `pitfalls.md`（陷阱全文）。证据可信度：**✅** 本机实测 ｜ **📄** 引自模板仓/官方文档 ｜ **⚠️** 未实测。
> 状态：v0.6.0（对齐核验器 **1.2.0**：7 项 / schema `/2`）。Phase 2 烧录段无硬件，整体挂起（D7）。

## 0. 硬前提

### 0.0 第零层：能力边界（先读，否则后面全白读）

**能可靠代做**：普通 GPIO 级改动（新增引脚 / 改模式 / 改上下拉）；`set pin PB0 GPIO_Output` 被 6.18
接受、回显 `OK`、`.ioc` 确实变化（✅）。

**不代做（没有能力，不是"还没实现"）**：UART / SPI / TIM / ADC / I2C 等非 GPIO 外设的增改。
证据（✅ D25）：`set pin PA0 S_TIM2_CH1_ETR`、`set pin PA1 USART2_TX` 一律回 **`KO`**；`set ip parameters …`
回 **`OK` 却一字未改** `.ioc`；**两类退出码都是 0** ⇒ 非 GPIO 只能**手改 `.ioc` 或 GUI → 强制过 G1
→ 人工过 H-6 清单**（§2 路径 B）。**因此：G1 核验器不是辅助工具，而是非 GPIO 路径上唯一的安全网。**

失败被拦截的层次不同，抓法也不同（详见 `references/capability-boundary.md` §4）：`set pin` 写错信号名 →
命令层 `KO`｜手改 `.ioc` 写坏信号名 → **可能出 `Cannot map`**｜手改漏 `IPParameters` → **日志干净什么都不报**
（只有 `main_init_present` 能抓）。

**四层优先级**：能力层（能不能做）> 路径层（`ALLOWED_ROOTS`）> 动作层（`POLICY`）> 流程层（G1 + L 等级）。
**能力层失败=做不了，权限层失败=不让做，流程层失败=做错了**——加白名单不会让你能配串口。

### 0.1 通道选择（与路径选择是两件事）

`cubemx_help` / `pio_system_info` 调用成功 → **MCP 通道**；调用不存在 → **CLI 通道**（§0.4）。
注册见 `docs/guides/mcp-registration.md`（本仓不替用户改 `mcp.json`，D12）。
**两条通道都不可用时停手报错**，不许挑着核验绕过 G1。
是否存在 MCP 只决定"用哪种方式调"；**要改什么**才决定"这件事能不能做"——**先判 0.0，再判 0.1。**

### 0.2 CubeMX / PlatformIO 定位（两通道共用）

CubeMX = `C:\ST\STM32CubeMX\STM32CubeMX.exe`（📄 不在 `C:\Program Files\…`），JRE 同目录
`jre\bin\java.exe`；版本 **6.18.1 / `DB.6.0.181`**（D1，**以 exe 属性或运行日志为准，别信 `.ioc` 版本戳**，P2）；
单次生成约 60 s、仅 `set pin`+`saveas` 约 32 s ⇒ **超时 ≥240 s**。
PlatformIO = `C:\Users\Leon\.platformio\penv\Scripts\pio.exe`（Core 6.2.0）。

MCP 通道另有 env：`ST_CUBEMX_EXE`、`ST_CUBEMX_ALLOWED_ROOTS`（白名单，换目录必须同步改）、
`ST_CUBEMX_TIMEOUT=300`、`PLATFORMIO_MCP_POLICY=build_only`、`PLATFORMIO_MCP_PIO`。

### 0.3 三条红线

1. **要烧录就必须显式确认**（MCP 下 `build_only` 会拒；CLI 下没人拦，见 §0.5）。属 L5，需 GATE-2.1。
2. **只在 `testbeds/` 的克隆副本里做写操作**；`D:\Projects\GitHub\` 下模板仓、`NUEDC_2027`、
   `HUSTRadio`、`leonskill-*` **一律只读**（✅ D9）。
3. **生成后不核验 = 没做**：CubeMX 对 `.ioc` 错误是非致命的，外设会被静默丢弃（📄 D5 / H-6）。

### 0.4 CLI 等价通道

```bash
"C:\ST\STM32CubeMX\jre\bin\java.exe" -jar "C:\ST\STM32CubeMX\STM32CubeMX.exe" -q "<工程>\scripts\cubemx-generate.mx"
"C:\Users\Leon\.platformio\penv\Scripts\pio.exe" run -d "<工程>"
python scripts/verify_generation.py --log <原始日志> --main-c "<工程>\Core\Src\main.c" \
    --mxproject "<工程>\.mxproject" --project-root "<工程>" --expect GPIO \
    --allow-signal VP_RIF_VS_RIF1 --json-out <证据目录>\verify.json
```

⚠️ Phase 2 才用、**未实测**：`pio run -d <工程> -t upload`、`pio device monitor`（见 §6）。

#### 🔴 `--log` 只接受 CubeMX 原始 stdout 重定向文件，**禁止传任何 MCP 工具返回值**

两个独立理由，任一成立就够：① MCP 的 `NOISE_RE` 删掉 `INFO`/`WARN`/`DEBUG`/`TRACE` 行（`[ERROR]` 保留），
而**实测真实 `Cannot map` 行就是 `[INFO]` 级别**（`s3b-regen/cubemx-generate.log:321`）⇒ 它在 MCP 返回
文本里**必然不存在** → **假阴性**且 `verdict` 仍 PASS；② `syscalls.c`/`sysmem.c` 的叠加路径异常**只在 stdout
的 `NoEcho` 行** ⇒ 即使不走 MCP、**只要"只读文件"也会错过它**。

> **自检**：手上只有 MCP 返回文本 → **先别跑核验**，换 CLI 重定向重跑一遍生成。

### 0.5 CLI 通道的技术真空

路径层（`ALLOWED_ROOTS`）与动作层（`POLICY`）在 CLI 回退通道上**都不存在**，只剩流程层（G1 + L 等级）。
**连"成功与否"都判不了**：CubeMX 退出码恒为 0；MCP 的 `cubemx_configure` 至少还判"无整行 `KO`"，
**CLI 手跑 `java -q` 时没有任何人查 `KO`。**

> **本项目不对 CLI 通道提供任何技术性拦截保障，只提供约定。** 不注册 MCP = 自愿放弃前两层保护。
> ⚠️ 但**不要**读成"CLI 通道不安全所以别用"——它是大多数用户的唯一路径。正确做法：知道真空在哪、
> 用流程补（烧录走 GATE-2.1；只在副本改配置；改动后必做 §2 三级确认）。

## 1. 能力索引

### 1.1 本仓自研（唯一不可替代的部分）

| 能力 | 入口 |
|---|---|
| **生成核验（G1 硬关卡）** | `scripts/verify_generation.py` —— 契约见 `references/verify-contract.md` |
| 备份 → 生成 → 核验 → 失败回滚 | `scripts/regen.sh <工程> [-e …] [-o …] [--require-clean]` —— 见 `references/regen-exit-codes.md` |
| `.ioc` 字段读写 / 备份还原 | `scripts/ioc_field.py`、`ioc_backup.py --project <工程根> [--restore\|--list]` |

### 1.2 双通道对照

| 想做的事 | MCP 通道 | CLI 等价通道 |
|---|---|---|
| 只读回读 `.ioc` | `cubemx_load` | 直接读 `.ioc`（ini）；引脚表 ⚠️ `csv pinout` |
| **改普通 GPIO** | ✅ `cubemx_configure` 的 `commands` 透传 | `set pin` 命令写进 `.mx` |
| **改非 GPIO 外设** | ❌ **没有这个能力** | ❌ 同样没有 → 手改 `.ioc` / GUI（§2 路径 B） |
| 生成 / 构建 / 尺寸 / 烧录 | `cubemx_generate` / `pio_build` / `pio_size_report` / `flash_standalone` | §0.4（尺寸口径见 P3；烧录串口 ⚠️ Phase 2 未实测） |

### 1.3 核验器契约要点（schema `/2`）

四个必填：`--log` `--main-c` `--mxproject` `--expect`（`""` = 不查外设）。
可选：`--project-root`（不传则该检查 `skip`）、`--ioc` + `--expect-pins PIN=SIGNAL`（引脚级检查，见 §1.4
第 4 项；`--expect-pins` 可重复、可逗号分隔）、`--allow-signal`（**默认为空**）、`--json-out`、`--report-md`。

- **退出码**：`0` 通过（可含 `warn`）；`1` 有 `fail`；`2` 输入/IO/参数错。
- **`blocking: true` 不等于"这条报错了"**——它只在 `status` 为 `fail` 时生效。
  判断本次有没有问题，**只看 `verdict` 与各条 `status`**。
- **`--allow-signal` 按"抽出的信号名"精确匹配**（大小写不敏感），**不是整行子串匹配**；抽不出名字才退回
  子串。这是防"用短词关掉守卫"（`--allow-signal signal` 不再放行全部圆括号形态）。
- **`summary.notes`** 收集所有 `skip` 的原因（`"<check_id>: <detail>"`），是"skip 必须解释"的机读落点。
  **自检**：有 `skip` 而 `notes` 为空 = 实现退化，**报 issue**，不要手写补。
- **`inputs.effective_allow_signals`** 是实际生效的白名单：直调为空、`regen.sh` 预置 D8。两处默认值不同**是有意设计**（核验器纯净 / 封装层便利），差异靠这个字段可见；取参一律从 `inputs` 读。
- **版本自证**：`verify_generation.py --version` → `1.2.0 (schema platform32.verify_generation/2)`；本文的 7 项判据与 `--expect-pins` 即该版本行为。
- JSON 全文、七项细则、`/1→/2` 迁移：`references/verify-contract.md`。

### 1.4 七项检查（`checks` 恒为 7 条，顺序固定）

| # | id | `blocking` | 一句话判据 |
|---|---|---|---|
| 1 | `log_cannot_map` | `true` | 日志无 `Cannot map`；命中 `--allow-signal` 降 `warn`。空日志 → `warn` |
| 2 | `main_init_present` | `true` | 每个期望外设有 `MX_<P>_Init(` **定义**（UART 走后缀匹配） |
| 3 | `main_init_called` | `true` | 每个 `MX_*_Init(` 在 `main()` 体内**被调用**（注释掉的不算） |
| 4 | **`pins_present`** | `true` | 每个 `--expect-pins PIN=SIGNAL`：`.ioc` 的 `<PIN>.Signal` **大小写不敏感**一致，**且** `main.c` 有 `__HAL_RCC_GPIOx_CLK_ENABLE()`。**不传 `--expect-pins`（或没给 `--ioc`）→ `skip`** |
| 5 | `mxproject_abs_path` | `true` | `.mxproject` 无 `[A-Za-z]:[\\/]` 盘符路径 |
| 6 | `mx_script_abs_path` | `true` | **三态**：占位符未替换→`warn`；归一化==工程根→`pass`；≠→`fail` |
| 7 | `syscalls_path` | **`false`** | `syscalls.c`/`sysmem.c` + 同行异常关键字 → `warn`，**不阻塞**（D9） |

- **`skip` ≠ 通过 ≠ 失败**：`--expect ""` 使 2/3 都 `skip`；外设全无定义时 3 也 `skip`（同根因只在 2 报一次
  fail）；**4 默认 `skip`，须显式传 `--expect-pins`（直调时还需 `--ioc`）才有结论**；**写证据必须解释原因**
  （读 `summary.notes`）。**G474 上第 6 项稳定出现 1 条 `warn`**（`cubemx-init.mx:5` 的 `__PROJECT_DIR__` 占位符），`verdict` 仍 `pass`——**预期条数恒为 1，≥2 条 = 异常必须查**。
- `log_cannot_map` 的真实实例与"CLI 路径不可达"对照（S3 两组证据）见 `references/verify-contract.md` §4.1。**两项没有 check 是有意的**：`ioc_ask_for_migrate`（核验器跑在生成之后，等它看见人已白等 → 归 `regen.sh` 告警）、`ioc_version_stamp`（提交卫生 → 归 P2）。

#### 🔴 保证边界（最重要的一条免责声明）

> **`verdict: pass` 的保证范围取决于你传了什么（三段式，D30.2）：**
> - **无条件保证**：外设级（整只外设没被丢，第 2/3 项）。
> - **有条件保证**：引脚级——**仅当显式传 `--expect-pins`（+ `--ioc`）**；不传 → `skip`，**不冒充通过**。
> - **明确不保证**：参数级与 `.ioc` 内部计数/排序自洽（`Prescaler` 是否进 `IPParameters`、
>   `Mcu.PinsNb` 是否 +1），v2 known limitation。

**为什么引脚级默认是真空**：`MX_GPIO_Init` 本来就有（PC13 在用），所以"加一个 PB0"时外设级检查全都
不变红——`configure` 说成功、生成成功、核验 PASS，**而 `.ioc` 可能一个字都没改**。这就是第 4 项存在的
唯一理由；**不传它等于放弃这层保护**。

**参数级失明**：核验不查参数是否生效（`PinState`/`Prescaler`，见 `references/verify-contract.md` §5）
⇒ **核验通过 ≠ 电平生效，必须在汇报里明说。**

### 1.5 `regen.sh` 退出码（`1` 与 `2` 的区别是关键）

| 码 | 含义 |
|---|---|
| `0` | 生成 + 核验通过 |
| `1` | **跑过了但结果不对**（日志有整行 `KO`，或核验 FAIL）；**已从备份回滚** |
| `2` | **压根没跑**（`--require-clean` 命中脏 `.ioc`、目录不存在、找不到 CubeMX/java、缺 `.mx`、`--expect` 解析失败） |

看到 `2` **不要去翻核验报告**——报告根本没生成。
⚠️ **`KO` 判据必要不充分**：抓不到 `set ip parameters` 那种"回 OK 却静默空操作"，
**不要让"没 KO"读成"成功了"**（完整判据见 `references/diff-evidence.md` §1）。

## 2. 标准流程

### 路径判定（动手前第一件事）

普通 GPIO（新增引脚 / 改模式 / 改上下拉）→ **路径 A**（透传可做）；
任何非 GPIO（UART / SPI / TIM / ADC / I2C 增改）→ **路径 B**（无透传能力）；
只读审计 → 跳 2–6，做 1 + 7。

**判错的代价不对称**：B 当 A 做 → 全绿但功能不存在的固件；A 当 B 做 → 只是多花手改功夫。
**拿不准就按 B 处理。**

### 第 0 步 · 前置检查

判能力边界 → 选路径 → 核对 CubeMX/pio 路径 → 核验器可用性（`verify_generation.py --version` 应显示 `/2`，
不可用就不许进第 3 步）→ `git status` 记"哪些文件被碰过"（**只作线索，不作判据**）。`.ioc` 已有未提交
改动时先问用户：那是他正在改的，还是本次要处理的？

### 第 1 步 · 只读审计（不改一个字节）

MCP 用 `cubemx_load`，CLI 直接读 `.ioc`。产出**改动前基线**（启用了哪些外设、引脚模式、时钟树
关键键值）——回滚时有对照物，并能证明"这外设原本就不存在"。

### 第 2 步 · 备份 `.ioc`

```bash
python scripts/ioc_backup.py --project <工程根> --json-out <证据目录>/ioc-backup.json
```

SHA-256 就是"确实还原了原件"的凭据。**路径 B 额外要求**：手改的回滚**只能靠这份备份**，
别指望 `git checkout`（会连带丢掉用户其他未提交改动）。

### 第 3A 步 · 改配置（普通 GPIO）

`set pin <PIN> <MODE>` 写进只含 `set` 命令的 `.mx`，在 `config load` 已有 `.ioc` 之后执行。

#### 🔴 三级确认（缺一不可，**退出码不作判据**）

1. **回显** 逐行 `OK` 不是 `KO`（**必要不充分**：`set ip parameters` 回 `OK` 却什么都不改）；
2. **diff** `git diff HEAD --numstat -w <工程>/*.ioc` **必须非 0**（唯一能证明真写进去了）；
3. **G1** pass，且 `--expect` 覆盖本次全部外设。

**引脚级落地判据（核验器不查，必须自查）**：`Mcu.PinsNb == 变更前 + 新增数`、
存在 `Mcu.Pin\d+=PB0`、`Mcu.Pin1..N` 连续无空洞。
❌ **不要断言 `Mcu.Pin5=PB0`**——新增引脚会插入 `Mcu.Pin1` 位置、原 1–5 整体后移（✅ D24.3）。

**让第 4 项真正生效**：加 `--expect-pins PB0=GPIO_Output`。⚠️ **直调 `verify_generation.py` 时**还要同传
`--ioc`，否则该项 `skip`、引脚增量仍是真空；**走 `regen.sh` 无需关心（`--ioc` 由脚本自动传）**。

### 第 3B 步 · 改配置（非 GPIO，**无透传能力**）

只能手改 `.ioc` 文本或 GUI。四条硬要求：

1. **必须补白名单**（📄 D3）：`<IP>.IPParameters=a,b,c`；`<Pin>.GPIOParameters=...`。
   不在白名单的 key 会被**静默忽略**。
2. **必须记录改前 SHA-256**（第 2 步的 `ioc-backup.json`）——唯一可靠的回滚锚点。
3. **必须过 G1**，`--expect` 覆盖全部涉及外设（漏写 = 漏检）。
4. **必须人工过 H-6 清单**：`MX_xxx_Init` 定义**和**调用、HAL 模块开关、MSP 时钟/GPIO/DMA、NVIC。

**信号名带 `S_` 前缀**（📄 D4）：PA0 上 TIM2 通道 1 是 `S_TIM2_CH1_ETR`（查 `db/mcu/<型号>.xml`）。

> 🚨 **3B 不可降级为 L3 交差。** L3 只证明"能编译"，而 3B 的风险恰是"外设静默缺失但仍能编译"。

### 第 4 步 · 生成

MCP `cubemx_generate` / CLI §0.4。**stdout/stderr 必须重定向到文件**（§0.4 硬禁令）。
`regen.sh` 的 `-e` 省略会从 `Mcu.IP*` **全量推导**（≠ 你本次期望的）；`--out` 默认落 `/tmp`
（故意不污染 `git status`），要入库时显式指到 `docs/logs/phaseN/<场景>/`。

**行为约束**：`regen.sh` **不修改** `.ioc` 中 `ProjectManager.AskForMigrate` 的值；生成后它为 `true`
属 CubeMX `saveas` 的正常结果，**不要在提交前手工复位**。（`-q` 是否被它阻塞至今零证据；
生成长时间无输出时先查 `MxCube.Version` 是否低于本机版本——排障建议，非因果结论。见 `references/pitfalls.md` P1。）

### 第 5 步 · **生成核验（G1，硬关卡）**

调用见 §1.3，判据见 §1.4。要点：

- **`--expect` 写本次期望存在的每个外设**（漏写 = 漏检，多写 = 假失败），以第 3 步的**意图**为准。
- **`1` 或 `verdict: fail` → 立即回滚**（`ioc_backup.py --restore` 或 `git checkout --`）；**不许**"先构建看看能不能过"——静默丢弃的外设**能构建成功**。
- `2` = 我们自己的输入错了（路径/文件），**不是配置有问题**，别误报给用户。
- 任何 `skip` 都要解释原因；`syscalls_path` 的 `warn` 不阻塞但要写进汇报。
- **必须提醒"保证边界"**：核验 PASS ≠ 引脚级/参数级生效。

### 第 6 步 · 构建

`pio_build` / `pio run -d <工程>` + 尺寸。**必须记录 Flash / RAM 字节数**（L3 的证据本体）。
⚠️ PIO 内置 size **不计** stack/heap 预留：对外报数以 `--print-memory-usage` 或 bin 实际字节为准，
**并注明口径**（P3）。

### 第 7 步 · 汇报 diff

```bash
git diff HEAD --numstat -w          # 判据：工作区 vs HEAD，忽略空白
git ls-files --eol <被报 M 的文件>   # 定性：CRLF 噪音 vs 真改动
```

- **必须带 `HEAD`**：S1 流程含 `git add`，一旦暂存，不带基准的 `--numstat -w` 返回 **0 个文件**（"假干净"）。`-w` 只忽略空白 ⇒ **为 0 表示"没有语义改动"，不是"没有改动"**。
- **`git status` 会过度报告**：`* text=auto eol=lf` 下工作区是 CRLF，`git add` 之前生成文件恒被列 `M`。
  **改一个 GPIO 报 8 个 M 是正常的**；两个工具必须配对用（`-w` 盲区表见 `references/diff-evidence.md`）。
- **`.ioc` 大 diff 只有一个成因**：版本不匹配导致的迁移重写（`grep MxCube.Version` 判断）——匹配 →
  异常、必逐条解释；不匹配 → 预期，拆独立 `chore(ioc):` 提交。619/106 是 `6.17.0→6.18.1` 的观测值，
  **不是阈值**，以当次 `numstat` 为准。
- **必须单独点名**：`USER CODE BEGIN/END` 块外的改动、`Core/**` 的整体重排（查 D1）。
  出错信号：`Drivers/`、`Makefile`、`startup_*.s`、`*.ld` 出现在 diff 里。

### 第 8 步 · 提交

按 §4。**不允许**只写"生成代码"。

## 3. 验证等级（L0–L5，定义来自模板 `AGENTS.md` §3）

| 等级 | 做什么 | 本仓算什么证据 |
|---|---|---|
| **L0** | 只读检查，仅限纯文档 | 无证据 |
| **L1** | 人工核对文件内容一致性 | 核对记录 |
| **L2** | 主机 gcc 回归 | `gcc` 命令 + 通过输出 |
| **L3** | `pio run` | Flash / RAM 字节（注明口径） |
| **L4** | 重新生成后核对 `main.c` 与日志 | `verify.json`（`verdict` + 各 `status`） |
| **L5** | 烧录 + 观察现象 | 烧录日志 + 现象（当前无硬件，一律缺） |

L2 命令（主机回归，不需要开发板）：

```bash
mkdir -p .pio/host-test
gcc -std=c11 -Wall -Wextra -Werror Core/Src/stdio_port.c test/stdio_port_test.c -o .pio/host-test/stdio-test && ./.pio/host-test/stdio-test
gcc -std=c11 -Wall -Wextra -Werror -DTEST_BACKEND Core/Src/stdio_port.c test/stdio_port_test.c -o .pio/host-test/stdio-backend-test && ./.pio/host-test/stdio-backend-test
pio run
```

**四条不许混**：① `.ioc` 改动没有 L4 = 没做完（L3 不能顶）；② **3B 不可降级为 L3**；
③ 构建通过 ≠ 能用，影响运行时的必须 L5；④ 不复用旧构建数字充本次证据。

## 4. 提交文案模板

```
<type>(<scope>): <中文简述，动词开头，≤50 字，不加句号>

为什么这么改（不要复述 diff）。

路径：A（GPIO 透传）/ B（非 GPIO 手改）                     ← 必填
验证等级：L<n> — <实际执行的命令与结果>
  - 三级确认：回显 <OK/KO> / diff <numstat> / G1 verdict=<pass|fail> errors=<n> warnings=<n>
  - 跳过的检查：见 verify.json 的 summary.notes（无则"无"；notes 空但有 skip = 报 issue）
  - 保证边界：外设级通过；引脚级<传/未传 --expect-pins>；参数级未验证        ← 必填
  - 构建：Flash <bytes> / RAM <bytes>（注明口径）｜ 实板：未验证（无硬件）
已知风险：<本次没覆盖到的部分>
```

`<type>`：`feat` `fix` `docs` `chore` `refactor` `test` `build` `ci` `perf` `style` `revert`；
`<scope>`：`ioc` `pio` `board` `vscode` `scripts` `core` `git` `docs`。
**一个提交只做一件事**（格式化/行尾/版本戳重写单独开 `style:` / `chore(ioc):`）。
**硬性禁止**（📄 `AGENTS.md` §1.5）：`push --force`、`--no-verify`、`--no-gpg-sign`、**任何 AI 署名尾注**。

## 5. 陷阱索引（全文见 `references/pitfalls.md`）

| # | 症状 → 处置 |
|---|---|
| P1 | `AskForMigrate`：`saveas` 写回 `true`、纯 generate 不改；**不拦不改不注入**，`-q` 是否阻塞零证据 |
| P2 | 只改 1 个 GPIO 却 619/106 重写 → 版本戳不匹配，拆 `chore(ioc):` |
| P3 | Flash/RAM 对不上 → PIO size 不计 stack/heap，以链接器/bin 为准 |
| P4 | `.mxproject` 干净但换机跑不了 → `.mx` 写死绝对路径（指向本工程是合规） |

**D 系列（工具层）**：D1 `formatOnSave` 重排 ｜ D2 纯行尾 diff ｜ D3 白名单漏 key ｜ D4 缺 `S_` 前缀 ｜ D5 `Cannot map`
静默丢弃 ｜ D6 `Drivers/` 只有 `.gitkeep` 正常 ｜ D7 同 P1（**以 P1 为准**）｜ D8 `VP_RIF_VS_RIF1` 忽略 ｜ D9 `syscalls` 不阻塞。
**H 系列（HAL 运行期）**：H-1 UART 能发不能收（NVIC）｜ H-2 TIM 状态机混用 ｜ H-3 停 DMA 关共享时基 ｜ H-4 `CC1OF` ｜
H-5 `Error_Handler` 后无诊断 ｜ **H-6 新增外设没落进生成物且日志干净**。⚠️ `HAL-PITFALLS.md` 只在 F103C8T6 与 H723 仓。

## 6. 串口与烧录（Phase 2，挂起）

⚠️ 无硬件，本节不做任何能力宣称。T2.1–T2.6 挂起至 GATE-2.0（D7）。待接板后补：`flash_standalone` /
`pio run -t upload` 的 reset/run 语义、`pio_monitor_capture` 的波特率与超时、无 VCP 时改外接 USB-TTL 方案、
探针/串口异常的错误分类、L5 证据留存形式。

## 7. 参考与依赖

- 手册页 `references/`：`capability-boundary` / `verify-contract` / `regen-exit-codes` /
  `diff-evidence` / `pitfalls`；外部资料链接见 `references/README.md`。
- 状态真源 `docs/TASKBOARD.md`；决策 D1–D30 见 `docs/DECISIONS.md`；核验器完整契约
  `docs/reports/t1.2-verifier-contract.md`；MCP 注册 `docs/guides/mcp-registration.md`；版本历史见 git log。
- **单写者边界**：`scripts/`、`tests/` → verifier-dev；`SKILL.md`、`docs/`、`references/` → skill-author；
  `testbeds/` → scenario-tester；`.github/` → lead 收口（原 `release-engineer`，已收口）。**本文件只由 skill-author 改**。
