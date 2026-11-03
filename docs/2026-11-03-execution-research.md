# platform32-mcp 执行前调研报告

> 生成时间：2026-11-03 · 生成者：计划 Agent
> 用途：交给执行 Agent 作为《STM32 全链路自动化平台 MCP》立项报告的**执行前调研结论**。
> 调研方式：全部结论基于**本机实测**（文件系统、命令行探测、doctor 运行）与外部仓库/官方文档核对；无法实测的项已标注 `[待验证]`。
> 原始立项报告：`D:\Users\Leon\Downloads\Edge\deep-research-report (16).md`（下称"原报告"）

---

## 0. 一页结论（执行 Agent 必读）

1. **本机已具备全链路的全部工具与 70% 现成软件资产**，不需要从零写 `.ioc` 解析器、烧录器或 PlatformIO 封装。真正要做的是**编排层**：把已有的 3 个 MCP 服务（`vscode-cube-mcp`、`stm32-stlink-mcp`、`platformio.mcp`）与模板仓的验证规范组装成 WorkBuddy Skill + 少量自研校验脚本。
2. **原报告有 3 处关键技术错误必须纠正**（见 §1），否则执行 Agent 会走弯路：`.ioc` 不是 XML、CubeMX 出错是静默非致命的、报告所列第三方方案大半已被本机模板文档明确否决。
3. **本机当前没有接 ST-Link 探针和开发板**（2026-11-03 实测 probes 为空、串口全为蓝牙虚拟口），所有 L5 级（实板）里程碑必须标注"需接板"。
4. 验证靶子现成：3 个 `template-mcu-*` 模板仓 + `NUEDC_2027/G474` 的 10 个渐进式工程 + `stm32-digital-clock`，覆盖 F1/G4 两个已装固件包系列。
5. 建议执行顺序：**先打通"改 .ioc → 生成 → 核验 → pio run 构建"无硬件闭环**（全部可当日验收），再做烧录/串口（需接板），CI 与 CMake 流放最后。

---

## 1. 对原报告的事实性纠正（重要）

原报告可作为蓝图，但以下内容与实测不符，执行时以本节为准：

| # | 原报告说法 | 实测事实 | 对执行的影响 |
|---|-----------|---------|------------|
| C1 | "建议使用 XML 解析（`xml.etree`）修改 `.ioc`" | **`.ioc` 是 Java properties 风格的 `key=value` 纯文本**，不是 XML。XML 只用于 CubeMX 的器件数据库（`C:\ST\STM32CubeMX\db\mcu\*.xml`） | 不要写 XML 解析器。改 `.ioc` 有两条安全路径：① CubeMX CLI 的 `set mode`/`set pin`/`set gpio`/`set ip` 命令（官方支持，`cubemx_configure` 已封装）；② 文本编辑但必须同步参数白名单（见 C2） |
| C2 | 未提及 | **CubeMX 对 `.ioc` 错误是静默非致命的**：信号名写错只在日志留一行 `Cannot map signal`，生成仍返回"成功"，外设被静默丢弃。参数必须写进 `<IP>.IPParameters` / `<Pin>.GPIOParameters` 白名单才生效 | 任何 `.ioc` 改动后**必须**做两项核验：① 生成日志无 `Cannot map`；② 生成的 `Core/Src/main.c` 有对应 `MX_xxx_Init()`。这必须成为 MCP 工具链的强制步骤（详见 §4 Gap-G1） |
| C3 | 工具调研表推荐 stm32pio、STM32Cube-MCP 等 | 本机模板文档（`template-mcu-*/docs/TOOLING-cubemx.md` §5）已明确否决：`stm32pio`（2021 起不维护，且会重建 PIO 工程与现有 `platformio.ini` 冲突）、`stm32cubemx-mcp`（走 CubeIDE，与需求不符）、`STM32Cube-MCP`（GUI 自动化为主，超出需求） | **不要安装这三个方案**。配置环节用已装的 `vscode-cube-mcp`，烧录用本机 `stmcp` |
| C4 | "CubeMX CLI 检测命令可校验约束" | CLI 没有独立的"detect/check"命令；约束校验由生成动作本身隐式完成（且如 C2 所述会静默吞错） | 校验逻辑必须自建（生成物核验），不能指望 CLI 返回值 |
| C5 | 流程图里"构建失败→回滚/修复" | 回滚的正确粒度是 **git**（生成前 commit 干净点），不是"自动修复" | 自动改配置前确保工作区干净 + `.ioc.bak` 备份；失败路径 = `git checkout` 恢复，不做智能修复 |
| C6 | 未区分 CubeMX 版本 | 本机同时装有 **CubeMX 6.18.1**（模板实测基线）和 **STM32CubeMX2 1.1.1**（新大版本）。CubeMX2 的 `-q` CLI 基本兼容但有编码坑（脚本须 UTF-8 无 BOM、路径避中文），且 `.ioc` 写回格式有差异 | MVP 锁定 **6.18.1**（与三个模板仓的实测结论一致）；CubeMX2 作为 Phase 3 的适配项 `[待验证]` |

---

## 2. 本机环境清单（2026-11-03 实测）

### 2.1 ST 官方工具（`C:\ST\`）

| 工具 | 版本 | 路径 | 状态 |
|---|---|---|---|
| STM32CubeMX | 6.18.1（DB.6.0.181） | `C:\ST\STM32CubeMX\STM32CubeMX.exe`（自带 JRE：`C:\ST\STM32CubeMX\jre\bin\java.exe`） | ✅ 模板仓实测基线 |
| STM32CubeMX2 | 1.1.1 | `C:\ST\STM32CubeMX2_1.1.1\` | ⚠️ 已装未验证，MVP 不用 |
| STM32CubeCLT | 1.22.0 | `C:\ST\STM32CubeCLT_1.22.0\` | ✅ 含 ST-LINK_gdbserver 7.14.0、STM32_Programmer_CLI 2.23.0、arm-none-eabi-gdb 15.2.90、GNU-tools-for-STM32 14.3.rel1、**CMake、Make、Ninja、st-arm-clang** |
| STM32CubeIDE | 2.2.0 | `C:\ST\STM32CubeIDE_2.2.0\` | ✅ 已装（headless build 备选） |

- CubeMX 固件包仓库（`C:\Users\Leon\STM32Cube\Repository\`）：**FW_F1 V1.8.7、FW_G4 V1.6.3 已装**；**无 H7**（H723 模板要跑生成需先装 FW_H7）。
- CubeMX 无头调用方式（已在模板仓验证）：
  ```powershell
  & "C:\ST\STM32CubeMX\jre\bin\java.exe" -jar "C:\ST\STM32CubeMX\STM32CubeMX.exe" -q "<script.mx>"
  ```
  单次生成耗时约 1 分钟（JVM 启动 + CMSIS 拷贝），**超时阈值别低于 240s**。

### 2.2 构建/通用工具

| 工具 | 版本 | 路径 |
|---|---|---|
| PlatformIO Core | 6.2.0 | `C:\Users\Leon\.platformio\penv\Scripts\pio.exe`（不在 PATH） |
| ststm32 平台包 | 20.0.0 | `~\.platformio\packages\`（framework-stm32cubef1@1.8.7、framework-stm32cubeg4@1.6.3、toolchain-gccarmnoneeabi@1.70201.0、tool-openocd@3.1200.7、tool-ldscripts-ststm32@0.3.0、tool-cmake、tool-ninja、tool-cppcheck） |
| CMake | 4.3.1 | 系统 PATH |
| Python / uv | 3.13.14 / 已装 | uv 管 MCP 工具（`uv tool list`） |
| Node | 22.22.2 | WorkBuddy 内置 + 系统 |
| 主机 GCC | MinGW 15.2.0 | 跑模板 `test/` 主机回归用 |

### 2.3 硬件现状

- **ST-Link 探针：未连接**（`stmcp doctor` 实测 probes 为空）。
- **串口：只有蓝牙虚拟串口**（COM16–23，BTHENUM），无 USB CDC。
- ⇒ 凡涉及烧录/实板的验收项当前**无法执行**，需接板后进行。可用板（从仓库推断）：Penguins-G474（G474VET6）、X Pulse（G474，NUEDC 2027 训练板）、STM32F103C8T6 蓝色药丸（stm32-digital-clock）。

### 2.4 环境变量现状（与模板文档不一致，执行时注意）

模板文档声称用户级已设 `ST_CUBEMX_EXE` / `ST_CUBEMX_ALLOWED_ROOTS` / `ST_CUBEMX_TIMEOUT`，但本次实测**用户级注册表未查到**（reg 被安全策略拦截，经 PowerShell `GetEnvironmentVariable('...','User')` 探测为空）。
⇒ 注册 MCP server 时**必须把这三个变量写进 server 配置的 `env` 块**，不要依赖系统环境变量。同理 `STMCP_*` 三个路径变量按 `mcp.json` 现有 `stm32-stlink` 条目内联。

---

## 3. 可复用资产清单

### 3.1 本机已装 MCP 服务（核对过源码/文档）

| 服务 | 形态 | 工具集 | 覆盖原报告的环节 | 状态 |
|---|---|---|---|---|
| **stm32-stlink-mcp**（`stmcp`） | TypeScript，`C:\Users\Leon\.workbuddy\mcp-servers\stmcp\`（src+dist+tests，MCP SDK 1.30） | 17 工具：`list_probes`、`debug_connect/disconnect/status`、`flash_standalone`、`flash_load_in_session`、`debug_run/halt/reset/step`、`breakpoint_*`、`memory_read/write`、`register_*`、`read_fault_registers`、`evaluate_expression`；`doctor` 自检 | 烧录 + 调试 + 寄存器/故障诊断（原报告"构建/烧录 Skill""验证 Skill"的硬件侧） | ✅ 完整可用，doctor 通过；`mcp.json` 有条目但 **disabled** |
| **vscode-cube-mcp** | Python（uv tool v0.4.2，h666zhang，PyPI，MIT），`C:\Users\Leon\.local\bin\vscode-cube-mcp.exe` | ~20 工具：`cubemx_help`、`cubemx_load`（只读回读）、`cubemx_configure`（set 命令序列+备份写回）、`cubemx_generate`、`cubemx_new_project`、`cubemx_remove_peripheral`、`cubemx_add_source`、`cubemx_export_pinout`、`cubemx_script`（逃生通道） | `.ioc` 读取/修改/代码生成（原报告"配置编辑 Skill"） | ✅ 已装；**未注册**进 `~/.workbuddy/mcp.json` |
| **platformio.mcp**（powerdragonfire） | Python，`uvx platformio.mcp`（PyPI 0.2.0，2026-09 活跃，MIT） | 40 工具：`pio_build`（解析错误→file:line）、`pio_flash_and_verify`、`pio_monitor_start/read/write/capture`、`pio_test`、`pio_size_report`、`pio_decode_backtrace`、`pio_port_diagnose`、`pio_pkg_*`、`pio_deps_check`；策略变量 `PLATFORMIO_MCP_POLICY=full/build_only/read_only` | PlatformIO 构建 + 串口 + 测试 + 尺寸/错误分析（原报告"PlatformIO Skill"） | ⬜ 未装；一行 `uvx` 可装 `[待验证]` |

> stmcp 的 README 还指出了 RTT 路线（`strtt-mcp`，共享 ST-LINK Server 免抢占）——L5 实时日志若需要再加，MVP 不做。

### 3.2 本机参考仓库（`D:\Projects\GitHub\`）

| 仓库 | 用途 | 关键文件 |
|---|---|---|
| `template-mcu-STM32F103C8T6` / `-STM32G474-series` / `-STM32H723-series` | **平台要服务的工程范式**（CubeMX+PlatformIO+VS Code），也是流程验收靶子；三者结构一致（`AGENTS.md`、`TEMPLATE-PLACEHOLDERS.md`、`.ioc`、`platformio.ini`、`scripts/cubemx-*.mx`、`boards/`） | `AGENTS.md`（L0–L5 验证等级、提交规范、12 条硬约束）；`docs/TOOLING-cubemx.md`（**本机 CLI 实测大全，§1–§5**）；`docs/HAL-PITFALLS.md`（6 个真实故障案例 H-1~H-6，验证 Skill 的测试灵感来源）；`TEMPLATE-PLACEHOLDERS.md`（占位符 A1–A4、陷阱 D1–D9） |
| `NUEDC_2027/G474/` | 10 个渐进式实战工程（`G474_00_empty` → `G474_10_dds_ad9959`：gpio/lcd/uart/adc×3/dac×2/dds），**多外设变更场景的黄金测试集** | `README.md` |
| `HUSTRadio/stm32-digital-clock/` | F103 实际项目（`.ioc` + `.ioc.bak` 备份惯例） | — |
| `hust-sti-measure-2026` | HAL-PITFALLS 的故障来源工程（频率计） | — |
| `esp-sdr/` | **CMake 流的本地参照**（ESP-IDF CMake，多 target sdkconfig 矩阵）；非 STM32，仅借架构 | `CMakeLists.txt`、`firmware-targets.json` |
| `leonskill-easyeda-*` | 用户自己的 Skill 仓**结构惯例**：`SKILL.md` + `scripts/` + `tests/` + `references/` + `research/` + `skill-dependencies.json` | platform32-mcp 产出的 Skill 应沿用此结构 |

三个模板仓 remote 均在 `github.com/LeonhardtHUST/...`；`platform32-mcp` 本身**只有 Initial commit、无 remote**。

### 3.3 官方/外部事实（已核对）

- **CubeMX CLI 官方命令表**（dev.st.com，6.18.1 版文档）：`load`、`loadboard`、`config load/save/saveas/saveext`、`project name/path/toolchain/compiler/generate`、`generate code`（只生成代码不出工程）、`SetStructure`、`SetCopyLibrary`、`setDriver`、**`set mode` / `set pin` / `set gpio` / `set ip` / `set pinreservation`**、`csv pinout`、`swmgr install/remove`（可无头装固件包！）、`pack enable/validate`、`script`、`exit`。交互/脚本/静默三模式：`-i` / `-s` / `-q`。
- platformio.mcp 详情见 §3.1；其策略层（`build_only`/`read_only`）正好实现原报告的"权限模型"。
- 原报告未提到但重要：`swmgr install stm32cube_h7_...` 可以**无头安装固件包**——补 FW_H7 不需要开 GUI `[待验证]`。

---

## 4. Gap 分析：真正要自建的东西

原报告把大量篇幅放在"整合已有工具"上，实测后真正的缺口只有以下几项：

| Gap | 描述 | 建议归属 | 优先级 |
|---|---|---|---|
| **G1 生成核验器** | `.ioc` 改动后强制核验：① 日志扫描 `Cannot map` / 相关 `OptionalMessage_ERROR`（容忍 G474 已知的 `VP_RIF_VS_RIF1` 噪音，见模板 D8）；② `Core/Src/main.c` 存在对应 `MX_xxx_Init()`；③ `.mxproject` 无盘符绝对路径（模板实测 §3.2）。现有任何 MCP 都不做这件事 | platform32-mcp 自研脚本（Python），作为 Skill 流水线的**必经关卡** | P0 |
| **G2 编排 Skill** | 把"改配置→生成→核验→构建→（烧录）→（串口验证）"串成带 L0–L5 验证等级声明的流程，并输出符合模板 `AGENTS.md` 提交规范的 commit。现有三个 MCP 各管一段，没人管整体 | platform32-mcp 主交付物：WorkBuddy Skill（沿用 leonskill 结构）+ 编排脚本 | P0 |
| **G3 MCP 注册与安全配置** | `~/.workbuddy/mcp.json` 目前只有 disabled 的 `stm32-stlink`。需新增 `vscode-cube-mcp`（env 内联 `ST_CUBEMX_*`，`ALLOWED_ROOTS=D:\Projects;...`）与 `platformio.mcp`，并启用 `stm32-stlink`；策略默认 `build_only`（烧录需显式升档） | 配置文件改动 + 各 server 的 env 白名单 | P0 |
| **G4 H723 模板跑通前置** | 无 FW_H7 → H723 模板无法生成/构建。先 `swmgr install` 装 FW_H7，且 PlatformIO 首次构建要联网拉 framework-stm32cubeh7 | 一次性环境操作 | P1 |
| **G5 CMake 流** | 模板范式是 PlatformIO 单流（CubeMX 生成 `Core/`，HAL/链接脚本/启动文件由 PIO framework 提供，见 AGENTS.md §2.4–2.5）。原报告的"双流同步"是伪需求（用户实际工程全部是 PIO 流）。CLT 自带 CMake/Ninja 可作后备 | **降级为 Phase 3 选做**；MVP 不做 | P2 |
| **G6 CI 示例** | GitHub Actions：matrix 只跑 `pio run`（离线可用已装包）；CubeMX 生成步骤在 CI 中涉及 ST 专有软件许可与 JVM 镜像，**MVP 不进 CI**，CI 仅做构建+主机回归（模板 §3 的 gcc 命令） | workflow 模板文件 | P2 |
| **G7 HIL/串口验证** | 接板后才可做。串口读已有 platformio.mcp 的 `pio_monitor_*`；功耗测试（STLINK_PWR）**砍掉不做**（无设备） | 需接板 | P1 |

---

## 5. 推荐架构

```
┌─────────────────────────── WorkBuddy / MCP 客户端 ───────────────────────────┐
│                                                                              │
│  platform32-mcp Skill（自建，G2）                                             │
│  ├─ SKILL.md：流程编排知识（L0–L5、提交规范、模板约束、陷阱清单 D1–D9/H-1–H-6） │
│  ├─ scripts/：verify_generation.py（G1）、regen.sh、ioc_backup.py             │
│  └─ tests/ + references/（引用三个模板仓文档，不复制内容）                     │
│                                                                              │
│  ┌─────────────── MCP servers（~/.workbuddy/mcp.json 注册）──────────────┐   │
│  │ vscode-cube-mcp   → .ioc 读/改/生成（CubeMX -q 封装，路径白名单）        │   │
│  │ platformio.mcp    → 构建/串口/测试/尺寸/错误解析（policy=build_only）    │   │
│  │ stm32-stlink-mcp  → 烧录/调试/寄存器（现有 stmcp，按需启用）             │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

关键决策：
1. **platform32-mcp 仓 = Skill + 编排脚本 + 文档**，不是又一个 MCP server。三个领域 server 已存在，再造轮子违背模板文档的否决结论。
2. **`.ioc` 修改首选 `cubemx_configure`（CLI `set` 命令）**，不做文本注入；手改仅限小改动且必须过 G1 核验。任何修改前自动 `git status` 检查 + `.ioc.bak` 备份。
3. **生成后必须**：`git diff` 报告给用户（哪些 USER CODE 区之外的东西被动了）+ G1 核验器结果。
4. 权限三层：MCP server env 白名单（路径）→ `PLATFORMIO_MCP_POLICY`（动作档位）→ Skill 层 L 等级声明（不达标不许提交）。

---

## 6. 分阶段执行计划（含验收标准）

### Phase 0：装配（0.5 天，全部 L1 可验）
1. 在 `~/.workbuddy/mcp.json` 注册 `vscode-cube-mcp`（env 内联 `ST_CUBEMX_EXE=C:\ST\STM32CubeMX\STM32CubeMX.exe`、`ST_CUBEMX_ALLOWED_ROOTS=D:\Projects;C:\Users\Leon\WorkBuddy`、`ST_CUBEMX_TIMEOUT=300`）与 `platformio.mcp`（`PLATFORMIO_MCP_POLICY=build_only`、`PLATFORMIO_MCP_PIO=C:\Users\Leon\.platformio\penv\Scripts\pio.exe`）；`stm32-stlink` 保持 disabled（接板日再开）。
2. `uvx platformio.mcp doctor` 验证。
- ✅ 验收：三个 server 在客户端可见，`cubemx_help`、`pio_system_info` 返回正常。

### Phase 1：MVP 无硬件闭环（2–3 天）
1. 建 platform32-mcp 骨架（leonskill 结构：SKILL.md/scripts/tests/references）。
2. 写 G1 `verify_generation.py`：输入 = 生成日志 + `main.c` + `.mxproject`；输出 = 结构化核验报告（pass/fail + 差异）。用 `template-mcu-STM32G474-series` 的已知噪音（D8）做负样本测试。
3. SKILL.md 编排流程：`cubemx_load`（审计）→ 改前 `git status`/备份 → `cubemx_configure`/`cubemx_generate` → G1 核验 → `pio_build`（解析错误 file:line）→ `git diff` 汇报 → 按模板规范生成 commit 文案。
4. 实战验收（无硬件，全部可当日完成）：
   - 在 `template-mcu-STM32G474-series` 副本上：把 PC13 之外再加一个 GPIO 输出（或改 `PinState`），全流程跑通至 `pio run` 成功。
   - 在 `stm32-digital-clock` 上：只读审计 `cubemx_load` + `pio_build`。
   - 负路径：故意写错信号名（去掉 `S_` 前缀），确认 G1 能抓住静默丢弃。
- ✅ 验收：3 个场景全过；G1 核验器有单测。

### Phase 2：烧录与串口（接板后 1–2 天）
1. 接板（Penguins-G474 或 X Pulse），开 `stm32-stlink`，`list_probes` 确认。
2. 流程扩展：构建 → `flash_standalone`（或 platformio.mcp `pio_flash_and_verify`）→ `pio_monitor_capture` 看 boot log → L5 声明。
3. 用 `NUEDC_2027/G474/G474_01_gpio`～`G474_03_uart` 做端到端样例（改一个外设配置→生成→烧录→串口验证）。
4. 顺手装 FW_H7（`swmgr install` 或 GUI），让 H723 模板可跑 `pio run`。
- ✅ 验收：至少 1 个 NUEDC 工程完成"改 .ioc→生成→核验→构建→烧录→串口输出符合预期"全链，提交信息含 L5 证据。

### Phase 3：CI 与收尾（1–2 天，可并行）
1. GitHub Actions workflow 模板：checkout → `pio run` matrix（G474/F103）→ 主机 gcc 回归（模板 §3 命令）→ 上传固件产物。**CubeMX 不进 CI**（许可+镜像成本，写入文档说明原因）。
2. 文档：README（架构图+三 server 职责）、SKILL.md 定稿、把 TOOLING/HAL-PITFALLS 的结论以引用方式链入。
3. 选做：CubeMX 2.1.1 适配评估、CMake 流（CLT CMake）评估、strtt RTT。
- ✅ 验收：CI 在模板仓 fork 上绿；文档齐。

---

## 7. 风险与对策

| 风险 | 等级 | 对策 |
|---|---|---|
| CubeMX 静默吞配置错误（C2/D5/H-6） | 高 | G1 强制核验 = 流程硬关卡；负路径测试进 Skill 的 tests |
| 生成覆盖用户代码 | 高 | 只信 USER CODE 区约定；生成前 `git status` 干净检查 + 备份 + `git diff` 汇报；绝不 `--force` |
| `AskForMigrate` 被写回 true 导致无头卡死（D7） | 中 | 生成前脚本检查该字段；卡住时的排障步骤写入 SKILL.md |
| `syscalls.c`/`sysmem.c` 叠加路径不更新（§3.4/D9） | 低 | 已知限量；核验器忽略这两个文件的"未更新" |
| CubeMX 升级/写回 `.ioc` 产生噪音 diff（D2） | 中 | `.gitattributes` 已管行尾；提交规范禁止混合行尾提交 |
| platformio.mcp 是早期项目（2026-09 起，星少） | 中 | 仅用其稳定面（build/monitor/test）；失败路径回退到直接 `pio` CLI（脚本里保留双通道） |
| CubeMX2 迁移引入不兼容 | 低 | MVP 锁 6.18.1；升级走模板仓的"生成+构建双验证"流程 |
| 端口被占/权限（串口） | 低 | platformio.mcp 的 `pio_port_diagnose` 已分类处理 |
| H7 模板无固件包 | 低 | `swmgr install` 无头安装；仍失败则 GUI 装 |

---

## 8. 遗留决策点（建议执行 Agent 开工前用 AskUserQuestion 与用户确认）

1. **CubeMX 版本锁 6.18.1？**（推荐是；模板基线。CubeMX2 留 Phase 3 评估）
2. **platformio.mcp 用外部包还是 Skill 直调 pio CLI？**（推荐：先装外部包做主力，CLI 做回退；它带错误解析与策略层，值）
3. **CMake 流是否砍出 MVP？**（推荐砍；用户实际工程全是 PIO 流）
4. **FW_H7 现在装还是接板时装？**（推荐 Phase 2 顺手装）
5. **platform32-mcp 的 GitHub remote**：现在建 `LeonhardtHUST/platform32-mcp` 还是先本地？（用户对模板仓都有 remote，建议尽早建）
6. **烧录探针默认 ST-Link？**（模板默认 stlink/SWD；X Pulse 板是否同探针 `[待验证]`）

---

## 9. 附：关键路径速查

```
CubeMX exe        C:\ST\STM32CubeMX\STM32CubeMX.exe
CubeMX JRE        C:\ST\STM32CubeMX\jre\bin\java.exe
CubeMX 器件库     C:\ST\STM32CubeMX\db\mcu\
FW 仓库           C:\Users\Leon\STM32Cube\Repository\（F1 V1.8.7 / G4 V1.6.3）
pio               C:\Users\Leon\.platformio\penv\Scripts\pio.exe
PIO 包目录        C:\Users\Leon\.platformio\packages\
stmcp             C:\Users\Leon\.workbuddy\mcp-servers\stmcp\（node dist/index.js serve | doctor）
vscode-cube-mcp   C:\Users\Leon\.local\bin\vscode-cube-mcp.exe（uv tool）
MCP 注册表        C:\Users\Leon\.workbuddy\mcp.json
gdbserver         C:\ST\STM32CubeCLT_1.22.0\STLink-gdb-server\bin\ST-LINK_gdbserver.exe
Programmer CLI    C:\ST\STM32CubeCLT_1.22.0\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe
arm-gdb           C:\ST\STM32CubeCLT_1.22.0\GNU-tools-for-STM32\bin\arm-none-eabi-gdb.exe
模板仓            D:\Projects\GitHub\template-mcu-{STM32F103C8T6,STM32G474-series,STM32H723-series}
测试靶            D:\Projects\GitHub\NUEDC_2027\G474\（G474_00~10）、D:\Projects\GitHub\HUSTRadio\stm32-digital-clock
本报告            D:\Projects\GitHub\platform32-mcp\docs\2026-11-03-execution-research.md
```
