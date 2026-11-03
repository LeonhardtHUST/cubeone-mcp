# T0 · `cubemx_configure` 实测签名与行为（源码级定论）

> 产出时间：2026-11-03 · owner：`env-agent` · 验证等级：**L1（源码读取 + 版本核对）**，第 7 节列出未实测项
> 目的：解决计划 T1.6「用 `cubemx_configure` 给 G474 加一个 GPIO 输出」与模板仓 `docs/TOOLING-cubemx.md` §4「`cubemx_configure` 是纯脚本透传，真正能配外设的是 `cubemx_new_project`」之间的表述冲突。
> 源码版本：`vscode-cube-mcp` **v0.4.2**（uv tool 安装），文件 `C:\Users\Leon\AppData\Roaming\uv\tools\vscode-cube-mcp\Lib\site-packages\cubemx_mcp.py`（1250 行）

---

## 0. 结论速览

| 问题 | 定论 |
|---|---|
| `cubemx_configure` 是"纯脚本透传"吗？ | **是**。模板仓 §4 的说法**正确**：它只做 `config load` → `commands` 逐行 → `config saveas`，不注入文本、不补白名单 |
| 那它能不能配外设？ | **能**。`commands` 里直接写 CubeMX 原生 `set mode/pin/gpio/ip` 命令即可。模板仓 §4 的"真正能配外设的是 `cubemx_new_project`"应理解为"**只有 new_project 会自动做文本补丁**"，而非"configure 配不了外设" |
| T1.6 用 `cubemx_configure` 加 GPIO 可行吗？ | **可行，且是 G474 的唯一可行路径**——本机 `templates/` 里**只有 `STM32F103C8T6.ioc`，没有 G474 模板**，`cubemx_new_project(mcu="STM32G474VETx")` 会直接抛"未找到模板"。见 §4 |
| 返回值可信吗？ | **不可全信**。`ok=True` 只代表"退出码 0 且无整行 `KO`"；CubeMX 的静默丢弃（`Cannot map`）**不会**让 configure 报错 → **G1 核验不可省**（呼应调研报告 C2 / Gap-G1） |

---

## 1. `cubemx_configure` 签名

**代码位置**：`cubemx_mcp.py:880-893`

```python
@mcp.tool()
def cubemx_configure(ioc: str, commands: list) -> str:
```

| 参数 | 类型 | 必填 | 约束 / 语义 |
|---|---|---|---|
| `ioc` | `str` | **是**（无默认值） | `.ioc` **绝对路径**；经 `_ioc_path()` → `_check_path()` 双重校验：必须存在、后缀 `.ioc`、且落在 `ST_CUBEMX_ALLOWED_ROOTS` 白名单内 |
| `commands` | `list[str]` | **是**（无默认值） | CubeMX 原生脚本命令，逐行原样透传。例：`["set mode USART1 Asynchronous", "set pin PB13 GPIO_Output"]` |

**实际喂给 CubeMX 的脚本**（`:889-891`，逐字）：

```
config load "<ap>"
<commands[0]>
<commands[1]>
...
config saveas "<ap>"
```

三个必须知道的点：

1. **用的是 `config saveas` 而不是 `config save`**。模板仓 `TOOLING-cubemx.md` §3.7 明确记录："`config saveas` 会同时改 `ProjectName` / `ProjectFileName`"。→ 若 `.ioc` 文件名与 `ProjectName` 不一致，写回后两者会被强制对齐，产生**额外的非预期 diff**。T1.6 的 `git diff` 汇报要能解释这一行。
2. **没有文本注入，也没有白名单补丁**：源码里 `_ensure_ip_param` / `_remove_ip_param` / `_inject_tim_*` 这些补丁函数**只被 `cubemx_new_project` 调用**，`cubemx_configure` 一个都没调用。
3. `.ioc` 会被**原地覆盖**（`saveas` 回同一路径）→ 调用前必须备份（`scripts/ioc_backup.py` 的职责），并保证 `git status` 干净。

---

## 2. 执行机制 `_run_script`（`:126-162`）

所有工具最终都落到这一个函数，行为逐条如下：

```python
fd, tmp = tempfile.mkstemp(prefix="cubemx_mcp_", suffix=".txt")
# 写入 script.strip() + "\n" + "exit\n"，编码 UTF-8
proc = subprocess.Popen([CUBEMX_EXE, "-q", tmp], stdout=PIPE, stderr=PIPE,
                        text=True, encoding="utf-8", errors="replace",
                        cwd=os.path.dirname(CUBEMX_EXE) or None)
stdout, stderr = proc.communicate(timeout=TIMEOUT_SECONDS)
```

| 行为 | 细节 | 影响 |
|---|---|---|
| 启动方式 | `[CUBEMX_EXE, "-q", tmp]`，即直接执行 `STM32CubeMX.exe` | 与调研报告 §2.1 记录的 `java -jar STM32CubeMX.exe -q` **等价**（exe 是 launch4j 包装），但 exe 直启会多一层 JVM 拉起开销 |
| 工作目录 | `cwd = CubeMX 安装目录` | **脚本里的相对路径以 CubeMX 目录为基准**，不是以工程目录为基准 → 写 `.mx` 脚本时**必须用绝对路径** |
| 编码 | 子进程 `encoding="utf-8", errors="replace"` | 与调研报告 C6「CubeMX2 有编码坑，脚本须 UTF-8 无 BOM」一致；临时文件以 UTF-8 写出、无 BOM ✔ |
| 超时 | `TIMEOUT_SECONDS` = `int(env ST_CUBEMX_TIMEOUT or 240)` | 配置里给 300s，满足调研"≥240s" |
| 超时处置 | `taskkill /PID <pid> /T /F`（`_kill_process_tree`） | 连子 Java 进程一起杀，不留文件锁 |
| 并发 | 全局 `_LOCK` 串行化 | CubeMX 有单实例锁，并发会互踩，已防 |
| 输出清洗 | `_cleanup` → `NOISE_RE` 过滤空行 | 见 §3 |
| 成功判定 | `ok = returncode == 0 and 无任何整行 "KO"` | 见 §3 风险 |

---

## 3. 判定语义与两个必须知道的风险

### 3.1 `ok=True` ≠ 配置生效（G1 的立论依据）

`ok` 只检查两件事：退出码为 0，输出里没有独立的 `KO` 行。

- 写错命令语法 → CubeMX 打印 `KO` → 返回 `[FAIL]` ✔ 能抓住
- **写错信号名 / 参数没进白名单 → 外设被静默丢弃，不产生 `KO`，返回 `[OK]`** ✘ 抓不住

这与调研报告 C2 完全一致：*"信号名写错只在日志留一行 `Cannot map signal`，生成仍返回'成功'，外设被静默丢弃"*。
**⇒ 任何 `.ioc` 改动后都必须跑 G1 核验器，不能凭 MCP 返回值判定成功。** 这是 S3 负路径场景的直接依据。

### 3.2 噪声正则可能吃掉 `Cannot map` 行 —— G1 不要消费 MCP 返回文本

`_cleanup` 用的过滤正则（`:72-77`，逐字）：

```python
NOISE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[(INFO|WARN|DEBUG|TRACE)\]|"
    r"^(Picked up|log4j[: ]|[A-Z][a-z]{2} \d{2}, \d{4} \d{1,2}:\d{2}:\d{2} (AM|PM)|"
    r"WARNING: Could not open|Configure log4j|Cannot load)",
    re.MULTILINE,
)
```

- 若 `Cannot map signal ...` 那行的**行首带 `YYYY-MM-DD HH:MM:SS,mmm [WARN]` 前缀** → 匹配第一条分支 → **被静默删掉**；
- 模板仓实测到的 G474 噪音行形态是 `[INFO] ImportTextPane:234 - (OptionalMessage_ERROR) ...`（**不带时间戳**）→ 不匹配正则 → 会保留；
- `Cannot load` 被显式列入噪声（它其实可能是真错误），需注意区分。

**⇒ 给 verifier-dev 的硬要求：G1 核验器必须读取 CubeMX 的原始 stdout / 日志文件，不要解析 MCP 工具返回的清洗后文本。** 否则 S3 负路径可能因"证据被上游过滤掉"而误判为 PASS。

#### 3.2.1 补充实证（2026-11-03 12:10，基于真实 CubeMX 日志）

`scenario-tester` 的 S1 干跑留下了真实 CubeMX 原始日志 `docs/logs/phase1/s1-dryrun-setcube.log`（606 行），据此把上面的"未实测"补成**已确认**：

**CubeMX 真实日志行格式（确认为带前缀）**：

```
2026-11-03 12:06:13,445 [INFO] ImportTextPane:234 - (OptionalMessage_ERROR) Pin5 (VP_RIF_VS_RIF1) cannot be retrieved for this MCU
```

⇒ 行首**确实是** `YYYY-MM-DD HH:MM:SS,mmm [LEVEL]`，**精确命中 `NOISE_RE` 第一条分支**。结论细化：

| 级别 | 是否被 `NOISE_RE` 删除 | 依据 |
|---|---|---|
| `[INFO]` | **会删** | 正则级别集合含 INFO |
| `[WARN]` | **会删** | 同上 |
| `[DEBUG]` / `[TRACE]` | **会删** | 同上 |
| `[ERROR]` | **不会删** | 正则级别集合**不含 ERROR**（这是个可利用的缝隙） |

**样本量与适用范围（只到观测，不外推）**

| 指标 | 实测值 | 来源 |
|---|---|---|
| 样本 | CubeMX 6.18.1 单次运行，**606 行** | `docs/logs/phase1/s1-dryrun-setcube.log` |
| 行首匹配 `<timestamp> [LEVEL]` 的行 | **586 行** | 同上（其余 20 行是脚本回显与 log4j 提示） |
| 以 `[LEVEL]` **裸开头**（无时间戳）的行 | **0 行** | 同上 |
| `[WARN]` 行数 | **140 行，全部带时间戳前缀** | 同上 |
| `[INFO]` 行数 | **446 行** | 同上 |
| `[ERROR]` 行数 | **0 行** | 同上（故"ERROR 不被过滤"是**代码事实**，非样本观测） |
| `Cannot map` 命中 | **0 次** | 同上；另两份 S3 探针日志（598 / 603 行）同样是 **0 次** |

⇒ **可以说**：在该样本中，140 条 `[WARN]` **全部**带时间戳前缀，`NOISE_RE` 会整行删除它们；`[ERROR]` 不在级别集合内（代码事实）。
⇒ **不能说**：`Cannot map signal` 一定以 `[WARN]` 记录、因而一定被 MCP 通道吃掉 —— **三份样本里 `Cannot map` 一次都没出现**，该行的真实级别仍是空白，需 S3 造出该行才能定案（见 §7 第 3 项）。
**结论不因"样本里没有"而变弱也不因"看着像"而变强：G1 读原始日志的处置对两种情形都成立，故无需等 S3 再动手。**

> 顺带验证了 `NOISE_RE` 的设计：它其余分支在真实日志里**确有对应**——
> `log4j user configuration file not found`（命中 `log4j[: ]`）、
> `Configure log4j with default settings`（命中 `Configure log4j`）、
> `Nov 03, 2026 12:10:56 PM java.util.prefs...`（命中 `MMM DD, YYYY h:mm:ss (AM|PM)`）、
> `WARNING: Could not open/create prefs root node ...`（命中 `WARNING: Could not open`）。
> 而脚本回显 `config load "..."` / `OK` **不匹配任何分支、会保留** —— 这正是 `KO` 检测得以工作的前提（`:161` 靠整行 `KO` 判失败）。

两项直接后果：

1. 模板仓已知的 `VP_RIF_VS_RIF1` 诊断噪音（`[INFO] ... cannot be retrieved`）**在 MCP 返回文本里看不到，在原始日志里看得到**。若 G1 从 MCP 返回值取日志，会"看不到这条噪音"——看似是好事，实则说明**过滤规则正在改变证据**，不可接受。
2. 若 `Cannot map signal` 由 CubeMX 以 `[WARN]` 记录 → MCP 通道会吃掉；若以 `[ERROR]` 记录 → 会保留。**级别仍未定案**，但判据已明确：**只要 G1 读原始日志，两种情形都能覆盖**。

**同批实证的其他收获**：

- **`set pin PB0 GPIO_Output` 被 6.18 接受**，CubeMX 逐条回显 `OK`（日志末尾可见 `OK` / `set pin PB0 GPIO_Output` / `OK` / `config saveas "..."` / `OK`），退出码 0。⇒ §7 未实测项 1、2 中"命令语法是否可用"已定：**语法可用**（但 `.ioc` 是否新增 `GPIOParameters` 白名单仍需看 diff，仍未定案）。
- 成功命令回显裸行 `OK`、失败回显 `KO` → `_run_script` 的 `ok = 无整行 KO` 判定**在本机语义上成立**；但它抓不到静默丢弃这一点不变。

---

## 4. `cubemx_new_project` 的 `commands` 与它为什么帮不上 G474

**签名**（`:940-982`）：

```python
def cubemx_new_project(project_name: str, project_dir: str,
                       mcu: str = "STM32F103C8T6", commands: list = None,
                       template: str = "", toolchain: str = "CMake",
                       couple_files: bool = True, clock_source: str = "HSE",
                       pll_mul: int = 9) -> str:
```

**它比 configure 多做的四件事**：

1. **文本改写模板 .ioc**：`_patch_ioc_identity()`（`:241-339`）——写 `ProjectName`/`ProjectFileName`、`toolchain`、`couple_files`、`clock_source`/`pll_mul`。**这是真文本注入**，所以"不做文本注入"只对 `configure` 成立，对 `new_project` 不成立。
2. `config load` + `commands` + `config saveas`（与 configure 同一套）
3. **TIM 三条伪命令走文本注入**（正则匹配后调 `_inject_tim_internal_clock` `:340` / `_inject_tim_pwm` `:554` / `_inject_tim_input_capture` `:611`）：
   - `set ip parameters TIMx ClockSource TIM_CLOCKSOURCE_INTERNAL [Prescaler n] [Period n]`
   - `set ip parameters TIMx PWM <pin> <signal> [Prescaler n] [Period n] [Pulse n]`
   - `set ip parameters TIMx InputCapture <pin> <signal> [Prescaler n] [Period n]`
   → 这三条命令**只有走 `cubemx_new_project` 才会被转成 6.18 验证过的标准表达**；走 `cubemx_configure` 就是原样透传，会踩"GUI 仍显示 ETR / set mode TIMx 一律 KO"的坑。**GPIO 命令没有这个特殊待遇，所以 GPIO 走 configure 没问题。**
4. 生成后搬 `.ioc` 到工程目录 + HSE 丢失告警（`:1082-1096`）

**致命限制（本次实测发现，直接影响 T1.6 排期）**：

`_project_template()`（`:196-216`）只在三个位置找 `{mcu}.ioc`：

```
<site-packages>/templates/            ← 唯一有内容的
<uv tool>/templates/
<sys.prefix>/templates/
```

而本机 `C:\Users\Leon\AppData\Roaming\uv\tools\vscode-cube-mcp\templates\` 里**只有 `STM32F103C8T6.ioc` 一个文件**（4119 B）。

**⇒ `cubemx_new_project(mcu="STM32G474VETx")` 会抛 `ValueError: 未找到模板 STM32G474VETx.ioc`，并只列出 `STM32F103C8T6.ioc` 一个可用项。**
（补一个 G474 模板需要先用 CubeMX GUI 新建 G474 工程另存为 `templates/STM32G474VETx.ioc`，属于"改第三方工具安装目录"，本次不做，也不建议做。）

**⇒ 结论：G474 场景（T1.6 / S1）只能走 `cubemx_configure` 或 `cubemx_script`，这正是计划 T1.6 的写法，不需要改计划。**

---

## 5. 对 T1.6 的建议方案（G474 加一个 GPIO 输出）

### 5.1 MCP 通道（若客户端已注册）

```
1. cubemx_load(ioc="...stm32-g474-template.ioc")            # 只读审计，确认 PC13/SWD 占用
2. cubemx_export_pinout(ioc=...)                             # 可选，拿引脚表基线
3. [git status 必须干净] + scripts/ioc_backup.py 备份 .ioc
4. cubemx_configure(
     ioc="<abs>/stm32-g474-template.ioc",
     commands=[
       "set pin PB0 GPIO_Output",
       "set gpio parameters PB0 GPIO_Label=LED_GREEN"
     ])
5. cubemx_generate(ioc="<abs>/stm32-g474-template.ioc")
6. G1 核验（**读原始日志**）：无 Cannot map + main.c 有 MX_GPIO_Init
7. git diff 汇报（预期：.ioc 新增 PB0 相关行 + Mcu.Pin*/PinsNb 变化 + 重新生成的 Core/ 文件）
8. pio run
```

- **初始电平（可选）**：模板里 PC13 的"输出 + 初始高"依赖两条一起写（`TOOLING-cubemx.md` §3.5）：
  ```ini
  PC13.GPIOParameters=PinState
  PC13.PinState=GPIO_PIN_SET
  PC13.Signal=GPIO_Output
  ```
  对应 CLI 推测为追加 `"set gpio parameters PB0 PinState=GPIO_PIN_SET"`，**该语法未实测**（§7-2）。若 S1 只需要一个翻转的 LED，**建议首跑先不设 PinState**，把变量降到最少；确需初始电平再加，并在核验器里检查 `main.c` 是否出现 `HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, GPIO_PIN_SET)`。
- **引脚选择**：模板 `.ioc` 现占用 `PC13`(GPIO_Output)、`PA13/PA14`(SWD)、`VP_SYS_VS_Systick`、`VP_SYS_VS_DBSignals`，`PB0` 空闲。但**最终选哪根脚要看实板 LED 接在哪**——S1 前由 scenario-tester 确认板上丝印，别只按 .ioc 空闲推导。

### 5.2 CLI 等价通道（D12 要求，Phase 1 实际主用）

写一个 `.mx` 脚本（**绝对路径**，因为 `cwd` 是 CubeMX 安装目录）：

```
config load "D:/Projects/GitHub/cubeone-mcp/testbeds/g474/stm32-g474-template.ioc"
set pin PB0 GPIO_Output
set gpio parameters PB0 GPIO_Label=LED_GREEN
config saveas "D:/Projects/GitHub/cubeone-mcp/testbeds/g474/stm32-g474-template.ioc"
exit
```

执行：

```
"C:\ST\STM32CubeMX\STM32CubeMX.exe" -q <script.mx>
```

对照：模板仓自带的 `scripts/cubemx-generate.mx` 用的是 `config load stm32-g474-template.ioc`（**相对名**），之所以能跑是因为模板仓的调用方先 `cd` 到了工程目录。**CLI 通道要么 cd 到工程目录，要么写绝对路径**，别照抄相对名。

### 5.3 失败/回退决策树

| 现象 | 判定 | 处置 |
|---|---|---|
| 返回 `[FAIL] ... KO` | 命令语法不被接受，`.ioc` 未被改（`saveas` 未执行到） | 换 `cubemx_script` 重试 / 查 `cubemx_help(topic="gpio")`；无需回滚 |
| 返回 `[OK]` 但 `.ioc` 无 `PB0` 相关行 | `saveas` 前的 set 被忽略 | `git checkout -- *.ioc` 回滚，换走文本编辑 + 手工补 `GPIOParameters` 白名单 |
| 返回 `[OK]`、`.ioc` 有 `PB0.Signal=GPIO_Output`，但 `main.c` 无 `MX_GPIO_Init` | **静默丢弃**（C2 场景） | `git checkout` 回滚；把该现象记成 G1 的正样本证据 |
| `.ioc` 的 `ProjectName` 被改写 | `config saveas` 的已知副作用（§3.7） | 提交前确认是否为预期，必要时改回 `config save` 形态 |

---

## 6. 代码依据清单

| 主题 | 位置 | 关键内容 |
|---|---|---|
| `cubemx_configure` 签名与脚本拼装 | `cubemx_mcp.py:880-893` | `config load` → commands → `config saveas` |
| 白名单校验 | `cubemx_mcp.py:86-93` `_check_path` | 绝对路径 + `startswith(root + sep)`，防 `ProjectsX` 前缀绕过 |
| `.ioc` 校验 | `cubemx_mcp.py:165-171` `_ioc_path` | 存在性 + `.ioc` 后缀 |
| 脚本执行与超时 | `cubemx_mcp.py:126-162` `_run_script` | `[CUBEMX_EXE,"-q",tmp]`、`cwd=CubeMX 目录`、`taskkill /T /F` |
| 噪声过滤正则 | `cubemx_mcp.py:72-77` `NOISE_RE` | 时间戳+级别前缀、`Cannot load` 等被删 |
| 成功判定 | `cubemx_mcp.py:161` | `returncode==0 and 无整行 "KO"` |
| `cubemx_new_project` 签名 | `cubemx_mcp.py:940-982` | 8 参数，含 `commands` / `template` |
| 模板查找（G474 缺失的根因） | `cubemx_mcp.py:196-216` `_project_template` | 只找 `templates/{mcu}.ioc` |
| 模板目录实际内容 | `...uv/tools/vscode-cube-mcp/templates/` | **仅 `STM32F103C8T6.ioc`** |
| .ioc 身份文本改写 | `cubemx_mcp.py:241-339` `_patch_ioc_identity` | `ProjectName`/`toolchain`/`couple_files`/时钟 |
| TIM 三伪命令注入 | `cubemx_mcp.py:340/554/611` | 仅 new_project 调用 |
| RCC 白名单补丁 | `cubemx_mcp.py:219-238` | 仅 new_project 链路 |
| 内置指南（GPIO 写法） | `cubemx_mcp.py:670-720` `_GUIDE` | `set pin PB13 GPIO_Output` / `set gpio parameters PB13 GPIO_Label LED` |
| 模板侧已知坑 | `template-mcu-STM32G474-series/docs/TOOLING-cubemx.md` §3.5（GPIOParameters 白名单）/ §3.6（VP_RIF 噪音）/ §3.7（saveas 副作用） | — |

---

## 7. 未实测项（如实标注，不要当结论用）

| # | 未定项 | 谁来定 | 怎么定 |
|---|---|---|---|
| 1 | `set pin PBx GPIO_Output` 是否会自动补 `PBx.GPIOParameters` 白名单 | ~~scenario-tester~~ **已定案（2026-11-03 12:25）** | **不写白名单**，且**不需要**：实测 `testbeds/_s1-dryrun/g474` 无 `PB0.GPIOParameters`，而 `main.c` 仍完整生成 PB0 的 GPIO 初始化（`__HAL_RCC_GPIOB_CLK_ENABLE` / `GPIO_MODE_OUTPUT_PP` / `HAL_GPIO_Init`）。白名单只在需要**额外参数**（如 `PinState`）时才必要。详见 `t0-regen-sh-review.md` §6.3 |
| 2 | `set gpio parameters PBx PinState=GPIO_PIN_SET` 语法是否被 6.18 接受 | scenario-tester（同上，若需要初始电平） | 看是否返回 `KO`；再看 `main.c` 有无 `HAL_GPIO_WritePin` |
| 3 | `Cannot map signal` 行的**级别**（INFO/WARN 会被 MCP 过滤，ERROR 不会） | scenario-tester（T1.8/S3 负路径） | 故意写错信号名，抓原始日志看该行是 `[WARN]` 还是 `[ERROR]`；**G1 读原始日志则无需关心**（见 §3.2.1） |
| 4 | `cubemx_configure` 在 G474 上的单次耗时 | scenario-tester | 调研记录单次生成约 60s；超时已设 300s。S1 干跑实测 `12:05:53 → 12:06:25` ≈ **32s**（仅 set pin + saveas，未 generate） |

前三项都应在 S1/S3 首跑时顺手定案，**定案后回填本文件并升到 L2/L3**。
