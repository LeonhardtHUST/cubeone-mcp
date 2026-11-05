# T2.4 串口靶场就绪与硬件未接证据（2026-11-05）

> **状态：靶场就绪、构建通过（L3）；烧录与串口取证未执行（本机无在线探针）⇒ 任务仍「挂起」。**
> 本文只记录事实与恢复步骤，**不宣布 T2.4 完成**，也不含任何推测性的串口输出。

---

## 1. 靶场与来源

**目标**：为 T2.4（串口链路验证）准备一个**真的会发数据**的工程，且**不动**既有工程原件。

| 项 | 内容 |
|---|---|
| 靶场目录 | `testbeds/xpulse-usart/`（**新建**，`testbeds/` 被外层 `.gitignore` 忽略 ⇒ 工程本体不入库，靠本文复现） |
| 应用来源 | `testbeds/xpulse-min/docs/XPulse/例程/USART/`（X-Pulse 官方 USART 例程）的 `Core/`、`Drivers/`、`USART.ioc` |
| board 定义 | `testbeds/xpulse-min/boards/genericSTM32G474VE.json`（自定义 board，平台内置没有这个 id） |
| 链接脚本 | `testbeds/xpulse-min/STM32G474xx_FLASH.ld` |
| 构建配置 | 照抄 `testbeds/xpulse-min/platformio.ini` 的 env 段 |
| **未改动** | `testbeds/xpulse-min/` 原件、`template-mcu-STM32G474-series`、`template-mcu-STM32H723-series` 一个字节都没动 |

`platformio.ini` 关键项（与 `xpulse-min` 一致）：

```ini
[platformio]
src_dir = Core/Src
include_dir = Core/Inc
boards_dir = boards

[env:genericSTM32G474VE]
platform = ststm32@20.0.0
platform_packages =
  platformio/framework-stm32cubeg4@1.6.3
  platformio/toolchain-gccarmnoneeabi@1.70201.0
  platformio/tool-ldscripts-ststm32@0.3.0
  platformio/tool-openocd@3.1200.7
board = genericSTM32G474VE
framework = stm32cube
board_build.stm32cube.custom_config_header = yes
build_src_filter = +<*> -<system_stm32g4xx.c>
build_src_flags = -std=c11 -Wall -Wextra
upload_protocol = stlink
debug_tool = stlink
monitor_speed = 115200
```

**例程确实会发数据**（这是选它而不是给 `xpulse-min` 加 USART 的原因）：`usart.c` 配 `USART1` 115200；
`main.c` 主循环每 500 ms 调 `HAL_UART_Transmit(&huart1, tx_buf, …)` 并 `printf("X Pulse STM32G474VET6 usart printf test...\r\n")`。

---

## 2. 构建证据（L3）

命令（`pio` 不在 PATH，用绝对路径；**不接管道**，以免 `tail` 把 `pio` 的非零退出码吞成 0）：

```bash
PIO=~/.platformio/penv/Scripts/pio.exe
cd testbeds/xpulse-usart && "$PIO" run
```

```
Compiling .pio/build/genericSTM32G474VE/src/gpio.o
Compiling .pio/build/genericSTM32G474VE/src/main.o
Compiling .pio/build/genericSTM32G474VE/src/stm32g4xx_hal_msp.o
Compiling .pio/build/genericSTM32G474VE/src/stm32g4xx_it.o
Compiling .pio/build/genericSTM32G474VE/src/usart.o
Core/Src/main.c:71:25: warning: unused parameter 'f' [-Wunused-parameter]
Linking .pio/build/genericSTM32G474VE/firmware.elf
RAM:   [          ]   0.3% (used 352 bytes from 131072 bytes)
Flash: [          ]   2.3% (used 12296 bytes from 524288 bytes)
Building .pio/build/genericSTM32G474VE/firmware.bin
========================= [SUCCESS] Took 12.85 seconds =========================
```

| 项 | 值 |
|---|---|
| 退出码 | **0** |
| 结果 | **SUCCESS**，**12.85 s** |
| RAM | **352 B / 128 KB（0.3%）** |
| Flash | **12296 B / 512 KB（2.3%）** |
| 产物 | `firmware.bin` **12784 B**、`firmware.elf` 148796 B |
| 告警 | **1 条**：`unused parameter 'f'`（例程 `fputc` 的 `-Wextra` 提示；本工程未开 `-Werror`，**不阻断**，未改例程代码） |

---

## 3. 硬件探测证据（关键：这是"确实没有"，不是"没去找"）

### 3.1 `pio device list`

**只枚举到 8 个串口，全部是蓝牙虚拟串口**，没有任何 ST-Link / CH340 / CP210x / USB-CDC：

```
COM21  Hardware ID: BTHENUM\{...}  Description: 蓝牙链接上的标准串行 (COM21)
COM20  …                            Description: 蓝牙链接上的标准串行 (COM20)
COM23  …                            Description: 蓝牙链接上的标准串行 (COM23)
COM22  …                            Description: 蓝牙链接上的标准串行 (COM22)
COM17 / COM18 / COM16 / COM19       Description: 蓝牙链接上的标准串行 (COM1x)
```

### 3.2 Windows PnP（排除"pio 枚举漏了"）

设备树里**确实有历史条目**，但**全部不在线**：

```
Status   Class      Name                        InstanceId
Unknown  USBDevice  STM32 STLink                USB\VID_0483&PID_3748\6&247DCA9A&0&1
Unknown  USBDevice  STM32 STLink                USB\VID_0483&PID_3748\6&17C283D&0&1
Unknown  USBDevice  STM32 STLink                USB\VID_0483&PID_3748\7&9863EEB&0&3
Unknown  Ports      USB 串行设备 (COM29)         USB\VID_0483&PID_5740\206D32874B45
Unknown  Ports      USB 串行设备 (COM13)         USB\VID_0483&PID_5740\4987DD6C3634
```

- **`Status = Unknown`** 在 `Get-PnpDevice` 里表示"设备不在场"（ghost 条目，曾插过、现已拔掉）。
- **在线（`Status = OK`）且 `VID_0483` 的设备数 = 0**。
- `.NET` 的 `[System.IO.Ports.SerialPort]::GetPortNames()` 只返回 **COM16–COM23**（与蓝牙串口一致），**不含 COM13 / COM29**。
- 强行打开 `COM29` / `COM13` 均报 `Access to the port 'COMxx' is denied`（端口不存在时的典型表现）。

⇒ **结论：本机没有任何可用的 ST-Link 探针或 USB 串口；板子（或驱动）不在位。**

---

## 4. 结论与未做的事

- **没有在线 ST-Link / COM ⇒ `pio run -t upload` 与 `pio device monitor` 均未执行。**
- `docs/logs/phase2/t2.4-serial-2026-11-05.log` **不存在**；本报告**不含**任何串口输出（也不允许事后手写一份）。
- 因此**没有 L5 证据**：看板 `T2.4` **仍为「挂起」**，等级目标仍是 **L5**，`§4` 快照未动。
- 已确认 `docs/logs/phase2/` **没有被 `.gitignore` 忽略**（`git check-ignore` rc=1）⇒ 板子上线后串口日志**可以入库**。

---

## 5. 恢复步骤（板子插上后照做，不必重建靶场）

1. **确认探针与串口**
   ```bash
   PIO=~/.platformio/penv/Scripts/pio.exe
   "$PIO" device list          # 期望出现 ST-Link 探针与/或 "USB 串行设备 (COMxx) VID_0483&PID_5740"
   ```
2. **烧录**
   ```bash
   cd testbeds/xpulse-usart && "$PIO" run -t upload
   # 期望结尾类似：Verified OK → Resetting Target → SUCCESS
   ```
3. **串口取证**（10–15 s 即够，别让它挂住会话）
   ```bash
   "$PIO" device monitor --baud 115200 --port COMxx    # 抓 10–15 s 后 Ctrl+C
   # 期望看到重复的 "X Pulse STM32G474VET6 usart printf test..." 与 tx_buf 内容
   ```
   把**原始输出**存到 `docs/logs/phase2/t2.4-serial-2026-11-05.log`（该目录**未被忽略**，可入库）。
   若一条都收不到：按"COM 口错 / 波特率错 / 板子没跑起来 / 走的不是这条线"逐项排除，**照实记录**，不要补写。
4. **回填看板**：`T2.4` 挂起 → 已完成、等级 L5，证据列写 upload 输出摘要 + 串口日志摘要（条数/时间戳）+ 日志路径；同批更新 `§4` 快照（Phase 2 已完成 `3→4`、挂起 `3→2`）并跑 `check_taskboard.py`。

## 6. 待用户确认

**X-Pulse 的 `USART1` 走哪条物理通道**：板载 ST-Link 的虚拟串口（VCP），还是外接 USB-TTL 接 PA9/PA10？
现状**无法判定**（无板在场）。这决定 `pio device monitor` 该选哪个 COM 口，也决定是否要额外接线。
