# 陷阱全表（P / D / H 三个系列）

> 手册页 · owner: `skill-author` · 最后核对：2026-11-03
> `SKILL.md` §5 只放**索引**（症状 → 处置一句话），本页是全文。
>
> **来源分级**：
> - **P 系列** = 本项目 Phase 1 实跑踩到的（✅ 本仓证据）
> - **D 系列** = 模板仓 `TEMPLATE-PLACEHOLDERS.md` §D（📄 上游文档）
> - **H 系列** = 模板仓 `docs/HAL-PITFALLS.md`（📄 上游文档）
>
> ⚠️ 链接注意：`HAL-PITFALLS.md` **只存在于 `template-mcu-STM32F103C8T6` 与
> `template-mcu-STM32H723-series` 两仓，G474 仓没有这个文件**。

---

## P 系列（本项目实跑，优先级最高）

### P1 · `AskForMigrate` 的真相（三元结构，别读成"不构成风险"）

1. **已确定**：`config save`/`saveas` 会整体重写 `.ioc` 并把 `AskForMigrate` 写成 `true`；
   **纯 `project generate` 不改写 `.ioc`、不改变该值**——`regen.sh` 默认路径实测前后
   sha256 逐字节相同（D19）。
2. **未验证**：`true` 状态下 `-q` 是否会阻塞 —— **至今零证据**（`true` 的两个样本之后再没被
   `-q` 加载过），既无正证也无反证。**零证据 ≠ 无风险。**
3. **处置**：**不拦、不改、不注入**。若生成长时间无输出，先查 `MxCube.Version` 是否低于
   本机版本（**排障建议，不是因果结论**）。

> **行为约束（操作纪律）**：`regen.sh` 不修改该值；生成后它为 `true` 属正常，
> **不要在提交前手工复位**。详见 `regen-exit-codes.md` §4。

### P2 · 只改一个 GPIO，`.ioc` 却是 619/106 整文件重写

- **判据**：`.ioc` 的 `MxCube.Version` < 本机 6.18.1 ⇒ 迁移重写（**唯一成因**）。
- **处置**：拆独立 `chore(ioc):` 提交，不与功能改动混在一起（否则违反 `AGENTS.md` §1.4 原子性）；
  版本戳要不要升由用户决定。
- 详见 `diff-evidence.md` §3。

### P3 · 代码里报的 Flash/RAM 与 `pio run` 对不上（实测差 1540 B RAM）

- **判据**：PlatformIO 内置 size **不计算** stack(1024) + heap(512) 预留。
- **处置**：以链接器 `--print-memory-usage` 或 bin 实际字节为准，**并注明口径**。
  不要把两种口径的数字混着报，也不要用旧数字充本次证据。

### P4 · `.mxproject` 干净，换机器却跑不了

- **判据**：绝对路径写死在 `scripts/*.mx`（CubeMX 脚本**不支持变量**，必须硬写，A1）。
- **处置**：指向**本工程根**是**合规**状态，指向别处才是错（`mx_script_abs_path` 三态）。
- 详见 `verify-contract.md` §4.5。

---

## D 系列（工具 / 模板层）

| # | 症状 | 判据 | 处置 |
|---|---|---|---|
| **D1** | `Core/**` 保存后出现与本次无关的整体重排 diff | 编辑器 `editor.formatOnSave: true`，clang-format 保存时重排 | 处理 `Core/**` 时关掉它，或加 `// clang-format off` 保护 |
| **D2** | 只有行尾变化的巨大 diff | `git ls-files --eol` 显示 CRLF/LF 混杂 | 严格按仓库既有策略，**不提交纯行尾变化**；判读法见 `diff-evidence.md` §2 |
| **D3** | 写了参数但 CubeMX 当没看见 | 对应 `<IP>.IPParameters=a,b,c` / `<Pin>.GPIOParameters=...` 白名单里没有这个 key | 两处一起补。实例：`PC13.GPIOParameters=PinState` 才让 `PC13.PinState` 生效 |
| **D4** | 信号名"看起来对"但配置失败 | 少了 `S_` 前缀：PA0 上 TIM2 通道 1 应写 `S_TIM2_CH1_ETR`，写 `TIM2_CH1_ETR` 会失败 | 以 `C:\ST\STM32CubeMX\db\mcu\<型号>.xml` 为准，先查库再写 |
| **D5** | **生成返回成功，外设却没了** | 日志有 `Cannot map signal`；`project generate` 仍返回成功 | 这就是"静默丢弃"，走 G1（`verify-contract.md` §4.1） |
| **D6** | 新克隆仓库 `Drivers/` 只有 `.gitkeep` | 这是**预期**的：HAL/CMSIS/启动文件/链接脚本由 PlatformIO framework 提供 | 不要试图提交 `Drivers/`；注意 git 无法 re-include 被排除目录下的文件 |
| **D7** | 无头生成卡在 `Begin LoadConfig()` 不动 | ⚠️ 与 P1 是同一件事的不同说法 | **以 P1 三元为准**，不要单独按本条的措辞处置 |
| **D8** | G474 日志总有 `Pin5 (VP_RIF_VS_RIF1) cannot be retrieved for this MCU` | CubeMX 6.18.1 的 G4 数据库噪音，即使只配 NVIC/RCC/SYS 也会出现；**不是** `Cannot map` | **忽略**，不要为它删外设。直接调核验器时显式 `--allow-signal VP_RIF_VS_RIF1`（`regen.sh` 已预置） |
| **D9** | 日志报 `FileNotFoundException: <工程目录>\D:\...\syscalls.c`，这两个文件不更新 | 叠加路径问题（CubeMX 已知缺陷），其余文件正常 | 核验器已降为 `warn`、**不判失败**；要更新就从 `STM32Cube_FW_G4_*` 的模板目录复制 |

---

## H 系列（HAL 运行期，来自派生工程真实故障）

> 说明：这些来自 `hust-sti-measure-2026`（频率计）的故障记录，已对照锁定的 HAL 源码审核。
> **升级 HAL 包后必须重新核对**，不能跨版本套用状态机或寄存器副作用。

| # | 症状 | 判据 / 根因 | 处置 |
|---|---|---|---|
| **H-1** | UART 能发不能收（轮询发送正常，接收中断回调从未进入） | `HAL_UART_Receive_IT()` 只配置 UART 接收中断源，**不代替 CPU 的 NVIC 配置**；还需要正确的 IRQ handler 调 `HAL_UART_IRQHandler()` | 先在 `.ioc` 里配 USART 的 NVIC 并重新生成，再查 MSP 的优先级与 `HAL_NVIC_EnableIRQ()`、中断文件里的 handler；在 USER CODE 块内显式使能前先看 `HAL_UART_Receive_IT()` 返回值 |
| **H-2** | 计数器已启动，但 `htim.State == HAL_TIM_STATE_READY` 自检失败 | `HAL_TIM_Base_Start()` 检查 READY 后把句柄整体状态置 BUSY；而 `HAL_TIM_IC_Start_DMA()` 检查的是**通道及互补通道**状态，不会仅因整体 BUSY 就返回 `HAL_BUSY` | 分别检查整体状态、通道状态和返回值；`__HAL_TIM_ENABLE()` 只操作 CEN、不维护 HAL 状态，**不是** 通用 Start API 的替代品 |
| **H-3** | 停止一次捕获后，依赖同一计数器的时基逻辑不再前进 | `HAL_TIM_IC_Stop_DMA()` 会关闭捕获通道、DMA 请求并调用 `__HAL_TIM_DISABLE()`；该宏只在 CCER 中所有 CCxE/CCxNE 均关闭时才清 CEN ⇒ "停止 DMA 一定关闭计数器"不成立 | 明确计数器的唯一管理者；在停止路径核对其他使用者并按需恢复计数，或改用独立定时器。周期性补写 CEN 只能作为特定工程的恢复策略 |
| **H-4** | 高频采集偶发 `CC1OF`，而完成的读数正常 | `HAL_TIM_IC_Start_DMA()` 先开捕获通道、再启动 DMA、最后开 TIM DMA 请求；计数器已在跑且外部输入持续时，这个窗口会产生尚未服务的捕获 | 在采集协议层控制输入/触发与启动顺序；定位时记录 SR、DMA 剩余长度和错误状态。清标志只能当"允许丢弃启动段事件"的特定策略，**会掩盖真实覆盖** |
| **H-5** | 时钟/外设初始化失败后，串口一个字都没有 | 模板的 `Error_Handler()` 关中断并停在无限循环；故障可能发生在 UART 初始化之前，关中断后的日志也无法工作 | **保留**模板默认的停机行为。需要容错降级的派生工程必须单独设计并验证降级启动路径、安全输出状态与实际时钟；不要简单把 `Error_Handler` 改成返回 |
| **H-6** | **新增外设没落入生成物，日志还没有 `Cannot map`** | 可能是信号名、IP/Pin 清单、参数白名单或模式表达式不完整；某派生工程曾遇到 TIM4 被丢弃且**没有 `Cannot map`** | 依次核对：加载后写回的 `.ioc` → 生成日志 → `MX_xxx_Init()` 的定义**和**调用 → HAL 模块开关 → MSP 时钟/GPIO/DMA 与 IRQ handler/NVIC。失败时用 GUI 配一遍并比对差异 |

### 为什么 H-6 是 G1 存在的唯一理由

它是"**返回成功但什么都没做**"的静默失败。而 §0.0 的"非 GPIO 无能力"是它存在的**第二个理由**——
在手改 `.ioc` 的路径上，G1 是唯一安全网。
**"日志无错误"只是必要条件之一，不能替代生成物核验。**
