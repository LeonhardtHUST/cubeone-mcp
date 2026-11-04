# cubeone-mcp

让 AI Agent 安全地驱动 **STM32CubeMX** 改 `.ioc` 配置、生成代码，并判断「改的东西到底有没有真的进生成物」。

> **想改这个仓库？** 先看 [`CONTRIBUTING.md`](CONTRIBUTING.md)（三层测试怎么跑 / 提交规范 / 单写者原则 / 依赖边界）；
> **不确定该看哪页文档？** 看 [`docs/README.md`](docs/README.md)（一页索引）。
> 只想**用**它的话，读下面的能力边界 + [`SKILL.md`](SKILL.md) 就够了。

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

## MCP 工具通道（`npx` / `vpx`）

本仓库同时发布为 npm 包 [`cubeone-mcp`](https://www.npmjs.com/package/cubeone-mcp)：
一个 Node 版 stdio MCP server，把三个 Python 脚本（G1 核验 / `.ioc` 备份 / 键读写）暴露为 MCP 工具，
内置路径白名单（`CUBEONE_ALLOWED_ROOTS`）与写策略门禁（`CUBEONE_POLICY`，默认 `read_only`）。

```jsonc
// 任意 MCP 客户端的 mcpServers 片段（CodeBuddy / Claude Desktop 风格）
"cubeone-mcp": {
  "command": "vpx",            // 或 "npx"
  "args": ["cubeone-mcp"],
  "env": {
    "CUBEONE_POLICY": "read_only",
    "CUBEONE_ALLOWED_ROOTS": "D:\\Projects"
  }
}
```

工具清单、退出码判据、发布与注册细节见 [`docs/guides/npm-publish-and-codebuddy.md`](docs/guides/npm-publish-and-codebuddy.md)。
能力边界对 MCP 通道同样适用：**非 GPIO 外设的增改依旧没有工具能力**，核验器仍是唯一安全网。

### 安全默认值（0.7.0 起）：`CUBEONE_ALLOWED_ROOTS` 未设置 = **拒绝所有路径参数**

> **BREAKING（0.7.0）**：默认值从"未设 = 不校验"翻转为 **fail-closed**。升级后如果没配白名单，
> 每次带路径参数的调用都会返回 `[cubeone-mcp][策略拦截] 未配置 CUBEONE_ALLOWED_ROOTS…` 并拒绝执行。
> 这是**有意**的破坏：迁移只需在注册条目里加一行 env（见下）。

| 情形 | 实际行为 |
|---|---|
| 设了 `CUBEONE_ALLOWED_ROOTS` | 路径参数不在白名单内 → 拒绝（返回「越界」，并给出解析后的物理路径） |
| **未设** `CUBEONE_ALLOWED_ROOTS` | ✅ **默认拒绝**所有路径参数，文案给出配置方法 + 逃生门 |
| 未设 + `CUBEONE_ALLOW_NO_ROOTS=1` | ⚠️ **宽松模式**：不校验，可访问任意路径。返回文本回显 `allowed_roots=未设置(宽松模式：本次调用无路径限制，CUBEONE_ALLOW_NO_ROOTS 生效)` |

**迁移方法**（二选一，改完重启 MCP 客户端）：

```jsonc
// 推荐：配白名单（Windows 用 ';' 分隔多个目录，POSIX 用 ':'）
"cubeone-mcp": {
  "command": "vpx",
  "args": ["cubeone-mcp"],
  "env": {
    "CUBEONE_POLICY": "read_only",
    "CUBEONE_ALLOWED_ROOTS": "D:\\Projects;C:\\Users\\you\\WorkBuddy"
  }
}
```

```jsonc
// 不推荐：显式退回 0.6.x 的宽松语义（确实需要访问任意路径时）
"env": { "CUBEONE_ALLOW_NO_ROOTS": "1" }
```

**为什么把 fail-open 当默认值是错的**：默认值不会自己说话——用户看到"能跑通"就以为路径被限制住了，
实际上 agent 的每一次笔误（写错工程目录、跟错 junction）都能落到任意位置，而**它全程处于无保护状态
却不自知**。安全默认值的第一原则是"默认拒绝、显式放行"：只有写下来的放宽才可能被看见、被复核。
0.7.0 因此把代价从"所有人静默无保护"换成"需要放宽的人写一行 env"。

白名单比较的是**物理路径**（`realpath`）：白名单目录内的 symlink / junction（Windows `mklink /J`
不需要管理员权限）指向界外时同样会被拒绝，拒绝文案会把物理落点打出来。
⚠️ 残余风险：不防 TOCTOU（校验通过后、打开文件前链接被替换）——威胁模型是 agent 误操作，不是对抗者。

`CUBEONE_REQUIRE_ROOTS=1` 仍然可用，但 0.7.0 起**降级为冗余**（默认已严格）：设不设都不改变路径判定，
只额外提供"启动即退出"的 fail-fast。它与 `CUBEONE_ALLOW_NO_ROOTS` 同时为真时**以后者为准**（显式放宽优先）。

## 快速开始

依赖：**Python 3.11+**（CI 仅覆盖 3.11 / 3.13，更早版本未验证；脚本全为标准库）、**STM32CubeMX 6.18.1**、**PlatformIO Core**（仅构建/烧录需要）。

```bash
# 1. 跑单元测试，确认脚本本身没问题
python -m pytest tests/ -q          # 期望：全绿（基准 2026-11-04：127 passed；数字随提交增长，以当次输出为准）

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
| **L5** 实板 | 烧录 + 独立判据 + 观察现象（LED / 寄存器回读 / 目视）；**首板 L5 已达成（2026-11-04）**，见 `docs/reports/phase2-bringup-2026-11-04.md`；串口段仍未实测 |

> 定义沿用模板仓 `AGENTS.md` §3，不另立一套。

已完成的场景实测（数字均可在 `docs/reports/` 找到出处）：

| 场景 | 内容 | 结果 | 等级 |
|---|---|---|---|
| S1 | G474 模板新增一个 GPIO 输出（PB0） | 7 项 pass；构建 **12.06 s** / 0 告警；**Flash 3 744 → 3 792 B（+48）**、RAM 1 584 B 不变；实质改动仅 `main.c` + `.ioc`，`USER CODE` 块零触碰 | L4 + L3 |
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

**pytest 的临时目录也会被安全软件拦住**：`python -m pytest tests/` 默认把每个用例的临时根堆在
系统 `%TEMP%\pytest-of-<user>\` 下，跑得多了会累积上千个目录；某些安全软件/agent 沙箱的**批量删除
保护**会在 pytest 清理旧临时根时拦截（表现为 `PermissionError`、`[SAFE_DELETE_*]` 之类的钩子消息，
或干脆挂起等确认）。规避方式是每轮换一个干净目录，跑完不清理也无所谓：

```bash
python -m pytest tests/ -q --basetemp="$TEMP/pytest-run-$(date +%s)"
```

`--basetemp` 给的是一个**本次专用**的临时根，pytest 不再去动历史那堆目录。CI 上不需要（runner 是一次性的）。

## 文档索引

| 文档 | 什么时候看 |
|---|---|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 要改这个仓库时：三层测试、提交规范、单写者原则、依赖边界 |
| [`docs/README.md`](docs/README.md) | **不确定看哪页时先看这里**（计划 / 决策 / 看板 / 报告 / 发布台账 / 指南 一页索引） |
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
tests/                Python 单测（基准 2026-11-04：`pytest tests/ -q` → 127 passed）+ fixtures/ 与 node/ 下的 Node 层单测（41 passed）
tools/
  mcp_smoke.py          MCP 通道冒烟（真实调用 4 次 / 4 个场景，含负向对照；本包 tools/list 为 3 个工具）
  npm_mcp_handshake.mjs npm 包工具通道冒烟（12 项；缺素材的项如实记 SKIP，不冒充通过）
  check_taskboard.py    看板一致性校验（快照 / 证据路径 / 发布记账）
  check_release.py      版本轴与发布收口校验（tag ↔ package.json ↔ SKILL.md ↔ README）
docs/                 决策记录、任务看板、发布正文（releases/）、实测报告与原始日志
.github/workflows/    CI（pytest × 覆盖率底线 + Node 三档 + Windows 真机 job + 脚本检查；不含 CubeMX 端到端）
```

> **依赖边界（重要，别读反）**：`scripts/` 下的三个 Python 脚本是**纯标准库、运行时零第三方依赖**——
> 只装了 Python 3.11+ 就能跑，不需要 `pip install` 任何东西。`pytest` / `pytest-cov` 属**测试工具链**，
> 只在跑测试时需要，**不算运行时依赖**；`package.json` 的唯一运行时依赖是
> `@modelcontextprotocol/sdk`（精确版本，lock 已入库）。

## 项目状态

- **Phase 1 已完成**：核验器（7 项）、`regen.sh`、Python/Node 单测、S1/S2/S3 三个场景实测（测试数字基准见上文「仓库结构」与「快速开始」）
- **Phase 2 已达成 L5（2026-11-04）**：烧录（`Verified OK`）、寄存器回读、目视一致，全链证据见 `docs/reports/phase2-bringup-2026-11-04.md`；**串口段与 `pio device monitor` 仍未实测**（本工程未启用 USART）
- **Phase 3 已完成**：CI 全绿（`pytest` 3.11 / 3.13 双矩阵 + `Node` 18/20/22 三档 + **Windows 真机 job**）

CI 覆盖的是「脚本与核验器的逻辑没退化」，**不覆盖**「某个 `.ioc` 改对了」——CubeMX 是 Windows GUI 应用且需交互接受许可，无法在 GitHub Actions 上运行。端到端证据来自本地实测，见 `docs/reports/`。

**覆盖率口径**（基准 2026-11-04，`pytest --cov=scripts tests/ -q`）：Python 侧 `--cov=scripts` 实测 **37%**，CI 底线 **36%**（基线 -1pp，只防回退、不追指标）。
这个数字**低估**了真实覆盖面——多数用例是用子进程调脚本的，子进程内的执行不计入 coverage，
所以不要拿它当"覆盖率只有 37%"读。Node 侧覆盖率只在 Node 22 档输出、**暂不设门槛**。

### 三个版本号，别混

本仓同时存在三个版本轴，它们不是一回事：

| 版本 | 指什么 | 当前值 |
|---|---|---|
| **仓库发布标签** | 对外发布的整体快照 | `v0.7.2`（本次发布后） |
| `SKILL.md` 的 `version` | Agent 操作面的文档迭代号 | `0.7.2` |
| `verify_generation.py --version` | 核验器实现 + JSON schema | `1.2.0`（schema `/2`） |

**发布轴规则**：前两轴与 `package.json` 的 `version` 必须**同值同步**——`git tag` = `package.json` = `SKILL.md` frontmatter（如 `v0.7.2` / `0.7.2` / `0.7.2`）；核验器那一轴**故意独立**（它是判据契约号，与包版本解耦）。每次打 tag 必须同时有 **GitHub Release + npm 发布 + 看板回填**，三者缺一视为发布未收口。规则出处与理由见 [`docs/DECISIONS.md`](docs/DECISIONS.md) **D33**。

引用时请写明是哪一轴：说「核验器 1.2.0」比说「0.6.2」有用得多，因为前者决定了 `verify.json` 的形状。

## License

[MIT](LICENSE) © 2026 LeonhardtHUST
