# 生成核验器契约（schema `platform32.verify_generation/2`）

> 手册页 · owner: `skill-author` · 以实现为准：`scripts/verify_generation.py`
> 完整契约（含实现细节与测试证据）：`docs/reports/t1.2-verifier-contract.md`
> 本页是**下游消费方视角**的摘要，供 `SKILL.md` 引用。

## 1. CLI

```bash
python scripts/verify_generation.py \
    --log <CubeMX 原始生成日志> \
    --main-c <工程>/Core/Src/main.c \
    --mxproject <工程>/.mxproject \
    --expect GPIO,TIM4,USART2 \
    [--project-root <工程根>] \
    [--allow-signal VP_RIF_VS_RIF1] \
    [--json-out <path>] [--report-md <path>]
```

| 参数 | 必填 | 说明 |
|---|---|---|
| `--log` | ✅ | **必须是 CubeMX 进程原始 stdout/stderr 重定向文件**（理由见 `SKILL.md` §0.4） |
| `--main-c` | ✅ | 生成的 `Core/Src/main.c` —— **唯一**能证明外设是否真的被生成的文件 |
| `--mxproject` | ✅ | 生成的 `.mxproject`（查盘符绝对路径） |
| `--expect` | ✅ | 期望外设；逗号/分号/空白分隔，大小写不敏感，去重转大写；`""` = 不查外设 |
| `--project-root` | ❌ | 扫描其下 `**/*.mx`；**不传则该检查 `skip`** |
| `--ioc` | ❌ | `.ioc` 路径，供 `pins_present` 读 `<PIN>.Signal`；**不传则该检查 `skip`** |
| `--expect-pins` | ❌ | 期望引脚，形式 `PIN=SIGNAL`（如 `PB0=GPIO_Output`）；**可重复、可逗号分隔**（与 `--allow-signal` 同 UX）。**不传则该检查 `skip`** |
| `--allow-signal` | ❌ | 可重复、可逗号分隔；**默认不预置**（`regen.sh` 才预置 D8）。**按抽出的信号名精确匹配**，见 §4.1 |
| `--json-out` / `--report-md` | ❌ | 自动建父目录 |

## 2. 退出码

| 码 | 含义 | 该怎么办 |
|---|---|---|
| `0` | 全部通过（**允许** `warn`，如 D9） | 可继续 `pio run` |
| `1` | 存在 `fail` 级问题 | **禁止**继续，必须回滚或修 `.ioc` |
| `2` | 输入/IO/参数错误（文件不存在、读不了、报告写不了） | 修命令，**不代表配置有问题** |

> `regen.sh` 复用 `2` 表达"前置拒绝/环境错误，未执行生成"——与"跑了但结果不对"（`1`）严格分开。

## 3. JSON 结构（`/2`）

```json
{"schema":"platform32.verify_generation/2",
 "verdict":"pass|fail",
 "checks":[{"id":"...","status":"pass|warn|fail|skip","blocking":true,"detail":"..."}],
 "summary":{"errors":0,"warnings":0,"checked_peripherals":["GPIO"],
            "notes":["main_init_called: --expect 为空，跳过 main() 调用检查"]},
 "inputs":{"log":"…","main_c":"…","mxproject":"…","project_root":"…",
           "expect":["GPIO"],"allow_signals":[],
           "effective_allow_signals":["VP_RIF_VS_RIF1"]},
 "tool":{"name":"regen.sh","version":"1.1.0"}}
```

### 字段语义

- **`blocking`（bool）**：该检查**失败时**是否阻塞交付。**不随本次 `status` 变化**。
  `blocking: true` **不等于**"这条报错了"——它只在 `status` 为 `fail` 时才生效。
  判断本次有没有问题，只看 `verdict` 与各条 `status`。
- **`summary.notes`**：所有 `skip` 项的 detail，形成 `"<check_id>: <detail>"`。
  这是"任何 skip 必须解释原因"的**机读落点**。
  **自检**：`checks` 里有 `skip` 而 `notes` 为空 = 实现退化，**按缺陷报 issue**，不要手写补。
- **`inputs.effective_allow_signals`**：实际生效的白名单（含 `regen.sh` 预置项）。
  直调时等于 `allow_signals`。存在的唯一目的：消灭"同一份日志、两个入口、两种结论"。
- **取参一律从 `inputs` 读**。`/1` 的顶层 `expect` / `allow_signals` 在 `/2` 不再是契约字段。
- **`tool`** 保持对象（不用字符串），便于将来扩展 `driver` 等字段。

## 4. 七项检查的判定细则

`checks` 数组**恒为 7 条**，顺序固定：
`log_cannot_map` → `main_init_present` → `main_init_called` → **`pins_present`** →
`mxproject_abs_path` → `mx_script_abs_path` → `syscalls_path`。

### 4.1 `log_cannot_map`（`blocking: true`）

- 命中 `Cannot map` 行 → 若该行信号名在 `--allow-signal` 白名单内 → 降为 `warn`；否则 `fail`。
- **白名单匹配以"抽出的信号名"为准（精确、大小写不敏感），不是整行子串匹配**；只有抽不出名字时
  才退回子串。原因（✅ 实测）：曾出现 `--allow-signal` 双向失效——正则回溯把**字面量 `signal`**
  当成信号名，于是 ① 把已知噪音加白名单永远匹配不上（**假 FAIL**）；
  ② `--allow-signal signal` 一次放行**所有**圆括号形态（**假 PASS，D5 守卫被绕过**）。
  修复后实测：带 `VP_TIM4_VS_ClockSourceINT` → `warn`/PASS/rc=0；不带 → FAIL/rc=1；
  带 `signal` → 仍 FAIL/rc=1（不再能"用一个短词关掉守卫"）。
- 另有 `OptionalMessage_ERROR`（如 G474 的 `VP_RIF_VS_RIF1`，D8）**不计入判定**。
- **空日志/纯空白 → `warn`**（"无法确认生成是否真的跑过"），`verdict` 仍可能是 pass。
  **"日志干净"必须由真实日志证明，不能由空文件证明。**

#### 证据现状：该检查目前没有真实样本

`docs/logs/` 里所有 `Cannot map` 命中均来自**核验器自己的报告文本**，负样本是构造 fixture
（`tests/fixtures/log_cannot_map_missing_s_prefix.txt`）。**原因已查明**——失败被提前拦截在不同层：

| 路线 | 命令层 | 生成日志层 |
|---|---|---|
| `set pin` 写非法信号名 | `KO` | 根本没走到生成 |
| 手改 `.ioc` 写坏信号名 | — | **可能出现 `Cannot map`** |
| 手改 `.ioc` 漏白名单 | — | 日志干净什么都不报 |

⇒ **该检查的定位是"防 D5 回归的守卫"，不是高频命中项。**
S3 的任务是给出真实样本，**或者证明该路径在本机不可达——"证明不可达"本身就是交付结论。**

### 4.2 `main_init_present`（`blocking: true`）

- 每个期望外设都必须有 `MX_<P>_Init(` 的**定义**。
- UART 走后缀候选匹配（`MX_USART2_UART_Init`）。
- 期望外设一个都没找到 → `fail`。
- `--expect ""` → `skip`。

### 4.3 `main_init_called`（`blocking: true`）

- 每个 `MX_*_Init(` 都要在 `main()` 体内**被调用**；被注释掉的调用不算（先剥 C 注释再比）。
- 两种 `skip`：`--expect ""`；或"一个定义都没找到"（同一根因只在 4.2 报 fail，避免双计）。
  detail 会写"另有 N 个外设无定义、未参与本项：TIM4"——**这行是重要线索**。
- `main.c` 里找不到 `int main(void)` 函数体 → `fail`。

### 4.4 `pins_present`（`blocking: true`，**默认 `skip`**）

**存在理由**：`cubemx_configure` 可能回 `ok=True`（上游判据只有"退出码 0 且无整行 `KO`"）而 `.ioc`
实际没改；生成成功、`MX_GPIO_Init` 本来就在（PC13 在用），于是外设级检查全 pass ——
用户以为改动生效了，其实什么都没发生。**这是 D5/H-6 的引脚级版本，比整只外设被丢更常见。**

判定（任一不满足即 `fail`）：

1. `.ioc` 里存在 `<PIN>.Signal`，且取值与期望**大小写不敏感**一致；
2. 该引脚所属端口的时钟使能出现在 `main.c`（`__HAL_RCC_GPIOx_CLK_ENABLE()`）——
   这一条才让"引脚真的进了生成物"可验证，而不只是"`.ioc` 里写了个键"。

两种 `skip`（detail 会写明原因）：

| 情况 | 结果 |
|---|---|
| 未传 `--expect-pins` | `skip`（"未提供 --expect-pins，跳过引脚级检查（v1.1 的外设级保证不含引脚增量）"） |
| 传了 `--expect-pins` 但没给 `--ioc` | `skip`（"无法读取 `<PIN>.Signal`"） |

> ⚠️ **默认 `skip` 是设计取舍，不是遗漏**：不传 `--expect-pins` 就等于放弃这层保护，
> 此时"加一个引脚"仍然只有外设级盲区。**路径 A 的正确做法永远带上它。**

### 4.5 `mxproject_abs_path`（`blocking: true`）

- `.mxproject` 出现 `[A-Za-z]:[\\/]` 盘符路径 → `fail`（换机不可复现，P4）。

### 4.6 `mx_script_abs_path`（`blocking: true`，**三态**）

扫描 `<project-root>/**/*.mx`：

| 情况 | 判定 |
|---|---|
| 占位符 `__[A-Z_]+__` 未替换 | `warn` |
| 绝对路径归一化后 **== 本工程根** | `pass` |
| 绝对路径归一化后 **≠ 本工程根** | `fail` |
| 未传 `--project-root` | `skip` |

**为什么不是"有盘符就 fail"**：CubeMX 脚本**不支持变量**，必须硬写绝对路径
（`TEMPLATE-PLACEHOLDERS.md` A1）⇒ "有盘符"是合规状态，只有"指向别的工程"才是错。

**G474 上会稳定出现 1 条 `warn`，这是预期**：`scripts/cubemx-init.mx:5` 的 `__PROJECT_DIR__`
是"从裸 MCU 新建工程"脚本的占位符；G474 没配模板时天然未替换 ⇒ `warn`、`verdict` 仍 `pass`。
**预期条数恒为 1；≥2 条 = 异常必须查。** 不要为消掉它去改那个脚本。

### 4.7 `syscalls_path`（**`blocking: false`**，唯一不阻塞的一项）

- 同一行里**同时**出现 `syscalls.c`/`sysmem.c` **且**含异常关键字
  （`FileNotFoundException`/`ioexception`/`exception`/`拒绝访问` 等）→ `warn`。
- 只提到文件名不误报 ⇒ 这条 `warn` 基本可当 D9 的确定性证据。
- 含义：这两个 newlib 桩本次未更新，属 CubeMX 已知缺陷，**不阻塞交付**。

## 5. 保证边界（最重要的一条免责声明）

> **`verdict: pass` 的保证范围取决于你传了什么。** 三段式（D30.2）：

| 层级 | 保证类型 | 说明 |
|---|---|---|
| 外设级（整只外设没被丢） | ✅ **无条件保证** | 4.2 + 4.3 |
| **引脚级**（在已有外设内部加一个引脚） | ⚠️ **有条件保证：仅当显式传 `--expect-pins`（+ `--ioc`）** | 4.4；不传则 `skip`，**不冒充通过** |
| **参数级** 与 `.ioc` 内部计数/排序自洽 | ❌ **明确不保证** | `Prescaler` 是否进 `IPParameters`、`Mcu.PinsNb` 是否 +1；v2 known limitation |

**为什么引脚级默认是真空**：`MX_GPIO_Init` 在模板里本来就有（PC13 在用），
所以"加一个 PB0"时外设级检查全都不会变红——`configure` 说成功、生成成功、核验 PASS，
**而 `.ioc` 可能一个字都没改**。这正是 4.4 存在的唯一理由。

**参数级失明的典型场景**（🚨 与 `set pin` 无关）：`set pin PB0 GPIO_Output` 路径下
CubeMX **不写** `PB0.PinState=`、也不需要白名单，`main.c` 直接生成
`HAL_GPIO_WritePin(..., GPIO_PIN_RESET)`（默认电平）。实测：`.ioc` 无 `PinState` 键 +
`main.c` 有 `WritePin(RESET)`，两者同时成立且不矛盾。
**真正的风险在"要非默认初始电平"**：走 `set gpio parameters … PinState=GPIO_PIN_SET` 或手改
`.ioc` 时，该键是否进 `PB0.GPIOParameters` 白名单决定生效与否（D3 有 PC13 的实例）。
**`pins_present` 对这个差别也失明**（它只查 `Signal` 与时钟使能）。

⇒ 任何"我要 PB0 输出高电平"的请求，**核验通过不等于电平生效**，必须在汇报里明说。

## 6. `/1` → `/2` 迁移

`/2` 的三处破坏性变更：`level: string` → `blocking: bool`；`expect`/`allow_signals` 移入 `inputs`；
语义细化（`blocking` 与 status 解耦）。三处都属于"会静默出错"，所以升了 schema 号。

`/1` 的历史产物（`docs/logs/phase1/regen-success/`、`regen-rollback/`、`s1-dryrun-regen/`）
是 **`/1` 历史证据，不作可消费样本**。
