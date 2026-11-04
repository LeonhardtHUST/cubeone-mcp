# GATE-2.0 接板日清单

> 用途：**接板那天照着从上往下做**，每格都写"怎么验、看到什么算过、不过怎么办"。
> 上游：`docs/TASKBOARD.md` §2 的 **GATE-2.0**（Phase 2 开工）与 **GATE-2.1**（首次烧录前的安全确认）。
> 本清单把 C3.1 预演（[`docs/reports/s4-dryrun-g474_01_gpio.md`](../reports/s4-dryrun-g474_01_gpio.md)）暴露的
> 前置项直接写成了必做步骤——**不照它走，第一次生成就会挂死**（见 §2.1）。

---

## 0. 三条底线（先读）

1. **首烧目标必须是 `testbeds/` 里的副本产物**，不是 `D:\Projects\GitHub\` 下的模板仓 / `NUEDC_2027` 原仓（D9 硬红线）。
2. **GATE-2.1 未过不许上电烧录**：目标板不得串接执行器 / 继电器 / 电机驱动（见 §4）。
3. **没有 `verdict` 与 `diff` 解释就不许烧**：G1 没跑过，或 diff 里有解释不了的改动，一律停手。

---

## 1. 硬件与工具（动手前 5 分钟）

| 检查 | 命令 / 动作 | 期望 |
|---|---|---|
| ST-Link 被系统识别 | PowerShell：`Get-CimInstance Win32_PnPEntity \| ? {$_.DeviceID -match "VID_0483"}` | 有 `STM32 STLink`（`VID:PID 0483:3748` = V2）。**`pio device list` 只列串口、不列调试器**，ST-Link V2 无 VCP，看不见它属正常 |
| 探针型号与固件 | openocd 连一次（见 §1.1）或 `pio system info` | 输出里能看到 `STLINK V2J35S7` 一类固件号与 `Target voltage`；**记下型号** |
| **工程引脚与实板是否对得上**（2026-11-04 实测新增） | 读板级头文件（X-Pulse：`Core/Inc/xpulse.h`）+ 板 README | **灯的引脚、有效电平、按键、串口都必须逐项对上**。X-Pulse：RGB = **PC0/PC1/PC2，共阳 3V3、低电平点亮**；**PC13 只引到排针、无 LED** |
| 目标板 QSPI/供电档位 | 目视 | 板子标注的供电范围与探针 `3.3V` 输出一致；**不要用 5V 直连** |
| 共地 | 目视 + 万用表通断 | 探针 GND 与目标板 GND **导通**；SWD 的 GND/SWDIO/SWCLK/NRST 四线到位 |
| CubeMX 可用 | `"C:\ST\STM32CubeMX\jre\bin\java.exe" -version` | 有版本输出；本仓锁 **6.18.1**（D1） |
| **没有 GUI 实例在跑** | `Get-CimInstance Win32_Process \| ? {$_.Name -like "*java*"}` | 输出为空。GUI 窗口会占共享 workspace，让排查多绕一圈 |

> **探针型号为什么要单独记**：`upload_protocol = stlink` 对 V2/V3 都成立，但 X-Pulse 一类复合探针在
> OpenOCD 下可能需要不同的 interface 配置。记下来写进当天的看板行，下次不用重新猜。

> ⚠️ **"同 MCU" 不构成可烧理由**（2026-11-04 F4 现场教训）：C3 选的首烧目标 `NUEDC/G474_01_gpio`
> 用 PC13/14/15 点灯，而实板 X-Pulse 的灯在 PC0/1/2。烧录成功、寄存器回读也对（`ODR` bit13=0），
> **但人眼什么也看不到**——最容易被误判成"工具没生效"。先对引脚，再选工程。

### 1.1 用 openocd 确认探针与目标（不烧录，5 秒）

```bash
OCD=~/.platformio/packages/tool-openocd/bin/openocd.exe
S=~/.platformio/packages/tool-openocd/openocd/scripts
"$OCD" -s "$S" -f interface/stlink.cfg -c "transport select swd" -f target/stm32g4x.cfg \
  -c "init" -c "mdw 0xE0042000 1" -c "shutdown"
```

期望：`STLINK V2J…`、`Target voltage: 3.2…`、`Cortex-M4`、`Examination succeed`、
`0xe0042000: 20036469`（`DEV_ID 0x469` = G47x/G48x）。

- 报 `Debug adapter doesn't support 'hla_swd' transport` → 用 `-c "transport select swd"`（**不要**用 `hla_swd`）。
- 报 `Error: open failed` 且设备列表里没有 `VID_0483` → **探针物理掉线**（拔线/接触），不是软件问题。

---

## 2. 工程前置（**这一步不做，生成会挂死**）

### 2.1 关掉迁移弹窗开关（C3.1 实测，必做）

```bash
python scripts/ioc_field.py --ioc <工程>/<name>.ioc get ProjectManager.AskForMigrate
# 若为 true 且工程版本戳低于本机 CubeMX（看 MxCube.Version 与 MxDb.Version）：
python scripts/ioc_field.py --ioc <工程>/<name>.ioc set ProjectManager.AskForMigrate false
```

- **为什么必须**：`.ioc` 版本戳 < 本机 CubeMX 且该键为 `true` 时，无 GUI 的 `-q` 生成会**弹模态框并挂住**
  直到超时（实测 300 s 超时，日志停在 `Begin LoadConfig()`）。
- **注意它会被写回**：`project generate` 会把 `AskForMigrate` 写回 `true`（实测），
  所以**每次拿旧工程生成前都要重新确认一次**，别以为设过一次就永久有效。

### 2.2 构建通道（Keil 工程要先补 PlatformIO 脚手架）

```bash
pio run -d <副本>          # 若报 NotPlatformIOProjectError → 该工程没有 platformio.ini（MDK-ARM 工程）
```

补法照 [`docs/reports/s4-dryrun-g474_01_gpio.md`](../reports/s4-dryrun-g474_01_gpio.md) §1：
从同 MCU 的模板派生 `platformio.ini` + `boards/`，并把工程自有 `BSP/Inc`、`BSP/Src` 纳入
（`main.c` 里 `#include "bsp.h"`，不纳入必报 `bsp.h: No such file or directory`）。

### 2.2.1 超时给够（2026-11-04 F5 实测）

| 工程形态 | 单次生成实测 | 建议 `--timeout` |
|---|---|---|
| 精简工程（只有 GPIO + 少量驱动） | **62 s**（C3 的 NUEDC 副本） | 默认 300 s 够 |
| **带全量 `Drivers/` 的模板工程** | **≈2.5 min**（日志 `Time for Copy HAL[0] : 7686mS`） | **480 s** |

- 还要加上 CubeMX **启动阶段**的 CubeFinder 联网查询（网络抖动时明显变慢）——本次就在 300 s 上翻过车，
  但脚本**没有误判成迁移挂死**，而是明确写"不能归因"并自动回滚（见 `phase2-bringup-2026-11-04.md` §4 F6）。
- 提速小技巧：先单独跑一次 `config load`（2 s 就能回 `OK`），第二次启动明显更快。

### 2.3 生成前的基线

```bash
python scripts/ioc_backup.py --project <副本>                    # .ioc.bak + .bak.sha256
cp -r <副本>/Core /tmp/Core-before-$(date +%H%M)                 # 生成前快照，用于 diff
```

### 2.4 改引脚：`set pin` 必须跟 `project generate`

```text
config load <name>.ioc
set pin PC2 GPIO_Output      ← 回显 OK，但此刻 .ioc 还没变（值只在内存里）
project generate             ← 写回 .ioc 的时机在这里
exit
```

**单独 `set pin` + `exit` 不会改 `.ioc`**（2026-11-04 实测：回显 `OK`，`grep PC2` 仍为 0）。
新增引脚插在 `Mcu.Pin1`、原 1–4 顺移、`Mcu.PinsNb +1`——**不要断言固定下标**（D24.3）。

---

## 3. 生成 → 核验 → 构建（三段，逐段卡）

```bash
bash scripts/regen.sh <副本> -e GPIO --expect-pins <PIN>=GPIO_Output -o docs/logs/phase2/<场景>
ls <副本>/../   # 无需操作，仅确认已退回仓库根
pio run -d <副本>
```

| 卡点 | 过 | 不过怎么办 |
|---|---|---|
| `regen.sh` 退出码 | `0` | `1`=跑过了但错了（已回滚）→ 看 `verify.json`；`2`=压根没跑（参数/环境）→ **别翻核验报告**，先修环境 |
| `verdict` | `pass` | `fail` 时逐条看：若**只有** `main_init_present` / `pins_present` 两条红，且工程是"每外设一对 `.c/.h`"（`.ioc` 里 `ProjectManager.CoupleFile=true`），**先确认你传了 `--project-root`**——少了它核验器只能看见 `main.c`，会误判（C3.1 的 F1）。`regen.sh` 自带该参数，裸调 `verify_generation.py` 时要自己补。补上仍红 → 才按真失败处理 |
| 生成日志 | 无整行 `KO` | 有 `KO` → 命令层就失败了，别继续 |
| `Core/` diff | **每一处都能解释** | 见 §3.1——**解释不了的改动不许烧板** |
| `pio run` | `SUCCESS` + Flash/RAM 数字 | 编译错先修；**报数一律用 `--print-memory-usage` 的口径**（PIO 自带 `size` 不计 stack/heap） |

### 3.1 生成物 diff 必须逐条解释（C3.1 F2 现场教训）

预演里 `main.c` 只差一行，但那是 `PLLN 100 → 85` —— 即 **SYSCLK 200 MHz → 170 MHz**：
原工程的 `main.c` 与它自己的 `.ioc` 本来就不一致，照原样烧板大概率进 `Error_Handler`。
**7 项核验一条都看不见这类参数改动**（参数级失明，属已声明的限制）。

```bash
diff -rq /tmp/Core-before-HHMM <副本>/Core        # 哪些文件变了
diff -u /tmp/Core-before-HHMM/main.c <副本>/Core/Src/main.c   # 变了什么
```

- 只允许出现"本次改动导致的差异" + "版本迁移导致的版本戳重写"两类；
- 出现时钟/中断优先级/GPIO 模式等**你没要求过的变化** → 停下，写清现象再决策。

---

## 4. GATE-2.1 安全确认（**上电前逐条口头确认**）

- [ ] 目标板**没有**串接执行器 / 继电器 / 电机 / 加热件（只有 LED / 按键 / 串口座）
- [ ] 目标板供电来自探针或独立稳压源，**与探针共地**
- [ ] SWD 四线接触可靠；板子没有其他主控同时驱动 SWD
- [ ] 已知复位行为：`reset=hard, run=true`（`flash_standalone` 默认）会让程序**立即开始跑**
- [ ] 若板上有外部 flash / EEPROM，确认烧录不会写坏出厂数据
- [ ] 出事时的断电手段就手边（拔 USB / 断电源），不需要找工具

---

## 5. 首次烧录（GATE-2.1 通过后）

```bash
# 方式一：PlatformIO（本批已验证构建，未验证烧录）
"/c/Users/Leon/.platformio/penv/Scripts/pio.exe" run -d <副本> -t upload
# 方式二：MCP 通道（需 CUBEONE_POLICY=full）
#   flash_standalone（reset=hard, run=true）
```

**首烧目标**：C3.1 预演产物（`testbeds/nuedc/G474_01_gpio`，`PC13.PinState=GPIO_PIN_RESET`）。
它的可观测现象最干净：**上电后 LED_R 应为灭**（原配置是亮）——这条就是"固件真的换了"的判据。

| 观察 | 说明 |
|---|---|
| LED_R 灭、LED_G/LED_B 亮 | 与 `gpio.c` 的 `HAL_GPIO_WritePin` 一致 ⇒ 烧录成功且配置生效 |
| 全灭或全亮不变 | 可能没烧进去 / 复位没生效 / 板子 LED 极性相反（先确认硬件极性） |
| 完全不亮且无反应 | 先进 §3.1 的 diff 检查（可能 `HAL_RCC_ClockConfig` 失败进了 `Error_Handler`） |

记录：烧录日志 → `docs/logs/phase2/`；现象（含时间与照片路径）→ 当天的 `docs/reports/`。

---

## 6. 串口验证（**二选一，不要两个都指望**）

| 方案 | 前提 | 做法 | 期望 |
|---|---|---|---|
| **A. boot log（推荐）** | `.ioc` 里已启用某个 USART 且代码里有 `printf` 重定向 | `pio device monitor -b 115200`（或 `pio_monitor_capture`） | 上电后能看到启动打印；**波特率必须与代码一致** |
| **B. 裸 printf（最小）** | 未启用 USART | 先按 §3 生成一个带 USART 的工程——**注意：非 GPIO 外设的增改没有工具能力**，必须手改 `.ioc`/走 GUI 并强制过 G1 | 能打印任意一行字符即算通 |

- **COM 口发现**：`pio device list`；Windows 上也可 `mode`；探针自带的 VCP 与目标板 VCP 是**两个不同的口**，别接错。
- 本预演工程（`G474_01_gpio`）**没有启用任何 USART**（`Mcu.IP*` 只有 NVIC/RCC/SYS/TIM17），
  所以串口段必须换工程或先加外设——这条已知，别在接板日现场才发现。

---

## 7. 收口（当天必须做完）

1. `docs/TASKBOARD.md`：T2.x 行填 L 等级 + 证据路径（`docs/logs/phase2/`、`docs/reports/`）；
2. `python tools/check_taskboard.py` → `rc=0`；
3. 烧录/串口证据按 L5 要求写进报告：**烧录日志 + 现象描述**，缺一条就不是 L5；
4. 本次踩到的新坑写进 `references/pitfalls.md`（P 系列）或本清单，**别只留在对话里**。
