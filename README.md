# platform32-mcp

让 AI Agent 安全地驱动 **STM32CubeMX** 改 `.ioc` 配置、生成代码，并判断「改的东西到底有没有真的进生成物」。

## 它解决什么问题

STM32 开发里有一种很难发现的失败：

> 你在 CubeMX 里改了配置、点了生成、编译通过、烧进去——**但那个外设根本不存在**，而且没有任何报错。

典型形态（都有实测样本，见 `docs/reports/`）：

| 形态 | 表面现象 | 真实情况 |
|---|---|---|
| 信号名写错 | 生成成功、退出码 0 | 外设被丢弃，日志里只有一行 `[INFO] ... Cannot map signal (...)` |
| 漏了 `IPParameters` 白名单 | 生成成功、日志干净 | 参数被忽略，外设「在」但不按你的设置工作 |
| 只声明 `Mcu.IP3=TIM4` | 生成成功、编译通过 | 整个外设消失，`main.c` 里 `MX_TIM4_Init` 一次都不出现 |

本仓库提供一个**生成核验器（G1）**：生成之后检查日志、`main.c`、`.ioc`，把这三类失败判定出来。它不替代 CubeMX，也不帮你写业务代码——它只回答一个问题：**这次生成的结果，和你要的是不是同一件事。**

## 🔴 能力边界（先读这段，再决定要不要用）

本工具链**能可靠代做的只有普通 GPIO 级改动**（新增引脚 / 改模式 / 改上下拉）。

**非 GPIO 外设（UART / SPI / TIM / ADC …）的增改，工具通道没有这个能力**——不是"还没实现"，是这条路走不通：

| 尝试 | 结果（CubeMX 6.18.1 实测） |
|---|---|
| `set pin PB0 GPIO_Output` | `OK`，`.ioc` 真的变了 ✅ |
| `set pin PA0 S_TIM2_CH1_ETR` | **`KO`**，`.ioc` 不变 ❌ |
| `set pin PA1 USART2_TX` | **`KO`**，`.ioc` 不变 ❌ |
| `set ip parameters TIM2 ...` | **`OK` 但 `.ioc` 一字未变** ❌ ← 最危险 |

第四行是最恶劣的形态：**返回成功、退出码 0、文件没动**。任何"看返回值判断成功"的逻辑都会被骗。

所以非 GPIO 外设的正确做法是：**手改 `.ioc` 文本或用 CubeMX GUI，然后必须过 G1 核验**。核验器在这条路径上不是辅助工具，而是**唯一的安全网**。

> 详细探测记录与四层模型（能力层 > 路径层 > 动作层 > 流程层）见 [`references/capability-boundary.md`](references/capability-boundary.md)。

## 快速开始

依赖：**Python 3.11+**（CI 仅覆盖 3.11 / 3.13，更早版本未验证；脚本全为标准库）、**STM32CubeMX 6.18.1**、**PlatformIO Core**（仅构建/烧录需要）。

```bash
# 1. 跑单元测试，确认脚本本身没问题
python -m pytest tests/ -q          # 期望：74 passed

# 2. 看核验器接受哪些参数
python scripts/verify_generation.py --help

# 3. 对一次已有生成结果做核验
python scripts/verify_generation.py \
  --log  build/cubemx.log \
  --main-c firmware/Core/Src/main.c \
  --mxproject firmware/.mxproject \
  --expect GPIO \
  --json-out report.json
```

一键「备份 → 生成 → 核验 → 失败自动回滚」：

```bash
bash scripts/regen.sh path/to/project -e GPIO
```

## G1 核验器：7 项检查

`schema = platform32.verify_generation/2`，`verify_generation.py --version` 可自证版本。

| # | check id | 检查什么 | 失败是否阻塞 |
|---|---|---|---|
| 1 | `log_cannot_map` | 生成日志里有无 `Cannot map`（外设被丢的根因证据） | 是 |
| 2 | `main_init_present` | 每个期望外设都有 `MX_<IP>_Init()` **定义** | 是 |
| 3 | `main_init_called` | 这些初始化函数在 `main()` 体内**真的被调用**（注释掉的调用不算） | 是 |
| 4 | `pins_present` | 指定引脚的 `<PIN>.Signal` 与生成物里的端口时钟使能都对得上 | 是（需显式启用） |
| 5 | `mxproject_abs_path` | `.mxproject` 里无盘符绝对路径（换机可复现） | 是 |
| 6 | `mx_script_abs_path` | `.mx` 脚本里的路径**指向本工程**（占位符未替换 → warn；指别处 → fail） | 是 |
| 7 | `syscalls_path` | `syscalls.c` / `sysmem.c` 叠加路径异常 | **否**（仅 warning） |

第 4 项**默认 `skip`**，必须显式声明期望引脚才生效：

```bash
python scripts/verify_generation.py ... \
  --expect-pins PB0=GPIO_Output --ioc firmware/project.ioc
```

## 保证边界（三段式，别混为一谈）

| 层级 | 是否保证 |
|---|---|
| **外设级** | ✅ 无条件。`MX_<IP>_Init()` 有定义且被调用，才算这个外设真的在 |
| **引脚级** | ⚠️ **有条件**：仅当显式传 `--expect-pins`（配合 `--ioc`）。不传则 `skip`，**不冒充通过** |
| **参数级** | ❌ **不保证**（v2 计划）。例如 `Prescaler` 是否进了 `IPParameters`、`Mcu.PinsNb` 是否 +1 |

> 这条边界最容易被误读成「核验 PASS 就等于全对」。**它只到外设级（传参时到引脚级）。**

## 验证等级

本项目用 L0–L5 标注每条结论的强度，报告里必须写明等级：

| 等级 | 含义 |
|---|---|
| **L0** 未验证 | 只读检查，仅限纯文档 |
| **L1** 静态 | 人工核对文件内容一致性（文档、配置） |
| **L2** 主机回归 | gcc 编译 + 运行主机侧测试，不需要开发板 |
| **L3** 构建 | `pio run` 通过，**只证明能编译** |
| **L4** 生成核验 | CubeMX 重新生成后核对 `main.c` 的 `MX_xxx_Init` 与日志（G1 判定 7 项） |
| **L5** 实板 | 烧录 + 观察现象（LED / 串口 / 波形）；本仓当前无硬件 |

> 定义沿用模板仓 `AGENTS.md` §3，不另立一套。

已完成的场景实测（数字均可在 `docs/reports/` 找到出处）：

| 场景 | 内容 | 结果 | 等级 |
|---|---|---|---|
| S1 | G474 模板新增一个 GPIO 输出（PB0） | 7 项 pass；构建 10.95 s / 0 告警；**Flash 3 744 → 3 792 B（+48）**、RAM 1 584 B 不变；实质改动仅 `main.c` + `.ioc`，`USER CODE` 块零触碰 | L4 + L3 |
| S2 | 真实工程只读审计（F103 数字钟） | 20 引脚逐条核对；**实际主频 8 MHz**（`.ioc` 里的 `HSE_VALUE` 是未启用的残留值）；构建 17.76 s；Flash 4 136 B / RAM 1 680 B | L1 + L3 |
| S3 | 注入两类错误，验证核验器抓得住 | 有引脚映射但缺白名单 → **日志有 `Cannot map`**；只声明 IP 无引脚映射 → **日志干净，只有 `main_init_present` 能发现** | L2 |

> S3 的第二行是本项目的核心论据：**如果没有 G1，那类错误在编译阶段完全看不见。**

## 退出码语义

| 码 | 含义 | 该做什么 |
|---|---|---|
| `0` | 通过（可含 warning） | 继续 |
| `1` | **跑过了但结果不对，已回滚** | 看是「生成阶段失败」还是「核验阶段失败」，两者排查方向不同 |
| `2` | **压根没跑**（参数错 / 环境缺失 / 前置拒绝） | **不要去看核验报告**，那是白费工夫 |

## 两条红线

### 1. `--log` 只能用 CubeMX 的原始 stdout 重定向文件

**禁止传入 MCP 工具返回值。**

原因不是洁癖：`vscode-cube-mcp` 里有一段 `NOISE_RE`，会把行首带时间戳且级别为 `INFO`/`WARN`/`DEBUG`/`TRACE` 的日志**整行删掉**。而 `Cannot map` 的实测级别正是 **`[INFO]`**：

```
2026-11-03 12:33:47,866 [INFO] ImportTextPane:234 - (OptionalMessage_ERROR) Cannot map signal (VP_TIM4_VS_ClockSourceINT) on pin (...)
```

⇒ 走 MCP 返回值，这行**根本不存在**，`log_cannot_map` 会恒为 `pass`——**负路径假阴性**。

### 2. 判断「改了哪些内容」用 `git diff HEAD --numstat -w`，不要用 `git status`

CubeMX 生成的 `Core/` 文件在工作区是 CRLF，而仓库按 LF 归一化。结果是：**`git status` 报 8 个文件改动，实际只有 2 个有语义改动**，其余 6 个只是行尾差异。

用 `git status` 判「是否越界」会假失败；而 `numstat` 看不到「仅缩进变化」。两个工具各有过报/欠报，**必须配对使用**：

```bash
git diff HEAD --numstat -w          # 语义改动（带 HEAD！否则 git add 后会变成 0）
git ls-files --eol <被报改的文件>    # 区分 CRLF 噪音与真改动
```

## 已知环境坑

**改过 `Core/Inc/*.h` 之后的增量重建会触发全量重编**，某些 agent 运行环境有批量删除保护阈值，删到第 N 个旧 `.o` 时会挂起等人确认。规避方式是换个构建目录，而不是删 `.pio`：

```bash
PLATFORMIO_BUILD_DIR=.pio/build-ci pio run -d path/to/project
```

这条与 CubeMX、PlatformIO、模板本身无关，是**运行环境的删除保护**导致的。

## 文档索引

| 文档 | 什么时候看 |
|---|---|
| [`SKILL.md`](SKILL.md) | 让 Agent 按标准流程作业时的操作面（含八步流程、提交模板） |
| [`references/capability-boundary.md`](references/capability-boundary.md) | 想搞清楚「为什么不能配串口」、四层能力/权限模型 |
| [`references/verify-contract.md`](references/verify-contract.md) | 要消费 `verify.json`，或自己实现一个核验器 |
| [`references/regen-exit-codes.md`](references/regen-exit-codes.md) | `regen.sh` 退出码、`KO` 判据、脏 `.ioc` 语义 |
| [`references/diff-evidence.md`](references/diff-evidence.md) | 判断一次改动是否越界、如何区分噪音与真改动 |
| [`references/pitfalls.md`](references/pitfalls.md) | 踩坑速查（D1–D9 / H-1–H-6 / P1–P4） |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | 想知道某个设计为什么是这样（含被推翻的旧结论） |
| [`docs/TASKBOARD.md`](docs/TASKBOARD.md) | 进度与各任务证据链接 |

## 仓库结构

```
SKILL.md              Agent 操作面
references/           五个手册页（本仓自有内容）
scripts/
  verify_generation.py    G1 核验器（7 项，标准库）
  regen.sh                备份 → 生成 → 核验 → 失败回滚
  ioc_backup.py           .ioc 备份/还原（sha256 凭据）
  ioc_field.py            .ioc 单键读写（保留 CRLF，原子写）
tests/                74 个 pytest 用例
docs/                 决策记录、任务看板、实测报告与原始日志
.github/workflows/    CI（pytest 矩阵 + 脚本静态检查；不含 CubeMX 端到端）
```

## 项目状态

- **Phase 1 已完成**：核验器 1.2.0（7 项）、`regen.sh`、74 个单测、S1/S2/S3 三个场景实测
- **Phase 2 挂起**：实板烧录验证（L5）需要接板后继续
- **Phase 3 进行中**：CI 与文档收口

CI 覆盖的是「脚本与核验器的逻辑没退化」，**不覆盖**「某个 `.ioc` 改对了」——CubeMX 是 Windows GUI 应用且需交互接受许可，无法在 GitHub Actions 上运行。端到端证据来自本地实测，见 `docs/reports/`。

## License

[MIT](LICENSE) © 2026 LeonhardtHUST
