# 能力边界（第零层）：这个工具链到底能做什么

> 手册页 · owner: `skill-author` · 上游判据：D25（`docs/DECISIONS.md`）· 最后核对：2026-11-03
> 本页是 `SKILL.md` §0.0 的展开。**SKILL.md 里只放结论，这里是证据。**

## 1. 为什么这一层排在最前

三个 MCP server 提供的是**权限**（路径白名单 + 动作档位），本仓提供的是**流程**（G1 + L 等级）。
但在这两层之下还有一个更硬的东西：**工具链的客观能力上限**。权限层可以放宽，流程层可以加强，
**能力层不会因为你多配一个白名单就长出新能力。**

四层的失败语义完全不同：

| 层 | 内容 | 谁提供 | 失败意味着 | 处置 |
|---|---|---|---|---|
| **第零层 能力层** | 能代做哪些改动 | 工具链客观上限 | **做不了** | 换路径（手改/GUI） |
| 第一层 路径层 | `ST_CUBEMX_ALLOWED_ROOTS` | `vscode-cube-mcp` | 不让做 | 改白名单 |
| 第二层 动作层 | `PLATFORMIO_MCP_POLICY` | `platformio.mcp` | 不让做 | 升档（需 GATE） |
| 第三层 流程层 | G1 核验 + L 等级 | 本仓 | 做错了 | 回滚重做 |

混在一起谈，就会出现"加个 `ALLOWED_ROOTS` 是不是就能配串口了"这种问题。
**不能。白名单只管路径，不管能力。**

## 2. D25 原始探测（4 种 `set` 语法，2026-11-03 实测）

在丢弃副本上跑的，`.ioc` 变化是逐字节比对的：

| 命令 | 回显 | `.ioc` 变化 | 退出码 |
|---|---|---|---|
| `set pin PA0 S_TIM2_CH1_ETR` | **`KO`** | 无 | **0** |
| `set pin PA0-WKUP S_TIM2_CH1_ETR` | **`KO`** | 无 | **0** |
| `set pin PA1 USART2_TX` | **`KO`** | 无 | **0** |
| `set ip parameters TIM2 InputCapture PA0-WKUP S_TIM2_CH1_ETR Prescaler 65535` | **`OK`** | **一字未变** | **0** |
| `set pin PB0 GPIO_Output` | `OK` | **有变化** | 0 |

三条产品级结论：

1. **透传通道只能配普通 GPIO。** `set pin <PIN> <外设信号>` 一律 `KO` —— 无法新增/改配
   UART / SPI / TIM / ADC。
2. **`set ip parameters` 是静默空操作**：`OK` + 退出码 0 + 文件未变。
   **任何"看返回值判成功"的逻辑都会被骗，而且骗得毫无征兆。**
3. **CubeMX 退出码恒为 0**，有 `KO` 也照样 0。⇒ **退出码不可作判据**（见 `diff-evidence.md` 三级确认）。

## 3. 能代做 / 不代做

### 能可靠代做

**普通 GPIO 级改动**：新增引脚、改模式（输入/输出/复用）、改上下拉。
证据：`set pin PB0 GPIO_Output` 被 6.18 接受、逐条回显 `OK`、`.ioc` 确实变化
（`docs/logs/phase1/s1-dryrun-setcube.log`）。

### 不代做（**没有能力，不是"还没实现"**）

**非 GPIO 外设（UART / SPI / TIM / ADC / I2C …）的增改。**
必须走：**手改 `.ioc` 文本 或 GUI → 强制过 G1 → 人工过 H-6 清单**（`SKILL.md` §2 路径 B）。
**没有任何工具能替你确认它生效了。**

## 4. 失败被拦截的层次：三条路线，三个抓法

这一节解释"为什么同一个错误，有时日志报、有时什么都不报"。**它决定了你该用哪个判据。**

| 路线 | 命令层 | 生成日志层 | 谁抓得住 |
|---|---|---|---|
| `set pin` 写非法信号名 | **`KO`** | **根本没走到生成** | `KO` 判据（`regen.sh`）+ 三级确认的 diff |
| **手改 `.ioc`** 写坏信号名 | 无命令层 | **可能出现 `Cannot map`** | `log_cannot_map` |
| 手改 `.ioc` 漏 `IPParameters` 白名单（`set ip parameters` 实测同此路） | 无命令层 | **日志干净，什么都不报** | 只有 `main_init_present`；引脚级另需 `pins_present` + `--expect-pins` |

第三条最危险：**它连 `Cannot map` 都不给**，日志"干净"，生成"成功"，
只有查 `main.c` 有没有 `MX_xxx_Init` 才发现外设没了——这就是 H-6。

## 5. 全绿幻觉链（为什么必须有 G1，且 G1 也不够）

```
configure 返回 ok=True（只等于 returncode==0 且无整行 KO）
        ↓
.ioc 其实一个字没改（或改了但被静默忽略）
        ↓
生成成功（CubeMX 对配置错误是非致命的）
        ↓
MX_GPIO_Init 本来就在（模板的 PC13 在用 GPIO）
        ↓
外设级核验 PASS
        ↓
用户以为改动生效了 —— 实际什么都没发生
```

破这个链需要**三级确认**，缺一不可：

1. 回显逐行是 `OK` 不是 `KO`（**必要不充分**）；
2. `git diff HEAD --numstat -w <工程>/*.ioc` **非 0**（证明真写进去了）；
3. G1 pass 且 `--expect` 覆盖本次全部外设。

**外加**（1.2.0 尤其重要）：核验器**默认只保证外设级**——引脚级增量它看不见，
**必须同时传 `--expect-pins` 与 `--ioc`** 才补上（`pins_present`，见 `verify-contract.md` §4.4）；
即便如此，`.ioc` 内部计数是否自洽仍要按 `diff-evidence.md` §4 的 `Mcu.PinsNb` 三条断言自查。

## 6. 一句话总结

> **G1 核验器不是辅助工具，而是非 GPIO 路径上唯一的安全网。**
> 这也是本项目的立项理由。
