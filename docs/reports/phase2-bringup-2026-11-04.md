# Phase 2 接板首日记录（2026-11-04）

> 目的：记录第一次在**真板**上走「改配置 → 生成 → 核验 → 构建 → 烧录」的记录，包括**没走通的部分**。
> 上游：`docs/guides/gate-2.0-checklist.md`（接板清单）、`docs/reports/s4-dryrun-g474_01_gpio.md`（无板预演）。
> 结论先说：**前三段在真板上走通了，第四段（烧录）因探针掉线未完成；且发现首烧目标选错板**。
> 验证等级：**L4（生成 + 核验在真工程上 PASS）+ L3（构建）**；**L5 未达成**（未在板上看到现象）。按 D34 如实降级，不宣称 L5。

---

## 1. 环境与探测（GATE-2.0 §1）

| 项 | 实测值 | 判据 |
|---|---|---|
| 探针 | `STLINK V2J35S7 (API v2)`，`VID:PID 0483:3748` | ST-Link **V2**（非 V2-1/V3），记入清单 |
| 目标电压 | **3.2387 V**（第二次 3.2355 V） | 3.3V 轨正常；SWD 能通即说明 GND 导通 |
| SWD | `DPIDR 0x2ba01477` → Cortex-M4 r0p1，`Examination succeed` | 四线（GND/SWDIO/SWCLK/NRST）到位 |
| 芯片 ID | `DBGMCU_IDCODE = 0x20036469` → **DEV_ID 0x469** | STM32G47x/G48x，与 `genericSTM32G474VE` 一致 |
| 时钟 | `Unable to match 2000 kHz, using 1800 kHz` | 适配器上限 1.8 MHz，非故障 |

> `pio device list` **只列串口**，不列调试器——ST-Link V2 无 VCP，所以它"看不见"是正常的。
> 判断探针在不在，用 `Win32_PnPEntity` 查 `VID_0483`，或直接用 openocd 连一次。

---

## 2. 第一次烧录：固件进去了，但看不见（发现 F4）

**目标**：C3 预演产物 `testbeds/nuedc/G474_01_gpio`（`firmware.bin` 5104 B）。

```
** Programming Started ** / ** Programming Finished ** / ** Verified OK ** / ** Resetting Target **
```

**寄存器回读**（openocd halt 后读 GPIOC）：

| 寄存器 | 值 | 解读 |
|---|---|---|
| `GPIOC MODER @0x48000800` | `0x57FFFF00` | PC13/14/15 均为 `01`（通用输出） |
| `GPIOC ODR @0x48000814` | `0x0000C000` | bit13=0（R 低）、bit14=1（G 高）、bit15=1（B 高） |
| `Flash[0]` | `SP 0x20020000` / `Reset 0x08001361` | 与烧录时 halt 到的 `pc 0x08001360` 一致 |

⇒ **配置改动确实落到了硬件上**（C3 那次 `PC13.PinState SET→RESET` 在 ODR 里可见）。

**但板上无任何反应。根因（F4）**：这块板子是 **X-Pulse**，其 `Core/Inc/xpulse.h` 与 README 写得很清楚——

- 板载三色灯在 **PC0（蓝）/ PC1（绿）/ PC2（红）**，**共阳接 3V3、低电平点亮**；
- **PC13 只引到 P2/P3 扩展排针，板上没有 LED**。

而 NUEDC 那工程用 PC13/14/15（且按高电平点亮假设）。**"同是 G474" 不等于 "同板"**。

---

## 3. 第二次：按实板引脚重做（前三段真跑通）

**目标**：从 `D:\Projects\GitHub\template-mcu-minimal-STM32G474VET6-XPulse` 复制到 `testbeds/xpulse-min`
（原仓只读，复制前后 `.ioc` md5 一致：`7c6113af…`），再用工具改配置。

### 3.1 改配置

`.mx` 脚本（CubeMX 命令）：
```
config load template-mcu-minimal-STM32G474VET6-XPulse.ioc
set pin PC2 GPIO_Output
project generate
exit
```

`.ioc` 变更：`PC2.Signal=GPIO_Output`、`Mcu.Pin1=PC2`、`Mcu.PinsNb 4 → 5`（新引脚插在 Pin1，原 1–4 顺移，符合 D24.3）。

> `set pin` 回显 **`OK`**；但**只有跟 `project generate` 才会写回 `.ioc`**——单独 `set pin` + `exit` 时 `.ioc` 一字未改（值只在内存里）。这一点值得写进 §2 的注意事项。

### 3.2 生成

`Generated code: …\Core\Src\main.c`、`The Die is : DIE469`。生成物里 PC2 与 PC13 合并在同一 struct：

```c
HAL_GPIO_WritePin(GPIOC, LED_RED_Pin|GPIO_PIN_2, GPIO_PIN_RESET);   /* 初始拉低 */
GPIO_InitStruct.Pin  = LED_RED_Pin|GPIO_PIN_2;
GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
```

本工程 `ProjectManager.CoupleFile=false` ⇒ GPIO 初始化在 **`main.c`**（`MX_GPIO_Init` L149），不在 `gpio.c`。
（这是 C3 那个 F1 的另一面：`CoupleFile=true` 才拆到 `Core/Src/<periph>.c`。）

### 3.3 核验（G1）

```
[platform32] 生成核验 verdict=PASS errors=0 warnings=0 expect=GPIO
  [pass] main_init_present  GPIO → MX_GPIO_Init（exact，定义 Core/Src/main.c:L149）
  [pass] main_init_called   GPIO → MX_GPIO_Init（调用 L88）
  [pass] pins_present       全部期望引脚都在 .ioc 与生成物中对上：PC2.Signal=GPIO_Output + __HAL_RCC_GPIOC_CLK_ENABLE()
  [pass] log_cannot_map / mxproject_abs_path / mx_script_abs_path / syscalls_path
```

### 3.4 构建

```
RAM:   44 bytes / 131072 (0.0%)      Flash: 3168 bytes / 524288 (0.6%)      SUCCESS
```

### 3.5 烧录 → 失败（物理原因）

```
Error: open failed    ** OpenOCD init failed **    *** [upload] Error 1
```

随后查 `Win32_PnPEntity`：**`VID_0483` 设备数 = 0** ⇒ 探针已从 USB 上消失（拔线/接触）。
**不是软件缺陷**；固件已构建好（`firmware.bin` 3168 B），插回探针即可续烧。

---

## 4. 三个发现

### F4（高）首烧目标必须与实板引脚一致

C3 选的首烧目标是 NUEDC 的 G474 工程，其 LED 在 PC13/14/15；实板 X-Pulse 在 PC0/1/2 且**低电平点亮**。
后果：烧录成功、寄存器也对，但**人眼什么也看不到**——最容易被误判成"工具没生效"。

**已在 `gate-2.0-checklist.md` §1 增补检查项**：先用板级头文件（本板 `xpulse.h`）核对 LED/按键/串口引脚，
再决定烧哪份工程；**"同 MCU" 不构成可烧理由**。

### F5（中）300 s 默认超时对"全量驱动工程"偏紧

- C3 的工程生成 **62 s**；本工程 **≈2.5 min**（日志：`Time for Copy HAL[0] : 7686mS`，驱动目录全量拷贝）。
- 加上 CubeMX 启动阶段的 **CubeFinder 联网查询**（本机网络抖动，`Proxy 502` 频发），首次尝试 **300 s 超时**。

⇒ 对带全量 `Drivers/` 的工程，建议 `--timeout 480`；或首次跑时先单独 `config load` 预热一次（第二次启动明显快）。

### F6（低）超时诊断的"不能归因"分支在真机上正确工作

真超时那次的输出：

```
[regen][error] 生成阶段失败：CubeMX 超时（timeout 300s 到点，RC=124）
[regen][warn]  日志尾部未见『停在 Begin LoadConfig()』的痕迹 ⇒ **不能**归因到 AskForMigrate 迁移对话框。
[regen][warn]  这是另一类超时，请按日志最后几行自查：GUI 弹窗 / 首次联网校验 / 磁盘慢 / 杀软扫描 / timeout 过小
[regen][warn] 开始回滚到生成前状态（从备份恢复，不动 git 历史）...
restored … .ioc ← ….ioc.bak
```

即：**没有把"所有超时"都说成迁移挂死**，并且**自动回滚**了 `.ioc` / `.mxproject`。
此前的验证只有假 java 模拟，这次是真超时——D36① 那条"不能归因"文案得到实测支持。

> 另有一条操作性坑：跑无头生成前，**别在同一个 CubeMX 里开着 GUI 窗口**。本次曾有一个 GUI 实例停在
> `hust-sti-training-2019d` 的模板上，虽非本次超时的直接原因，但会让排查多绕一圈（已关）。

---

## 5. 下一步（插回探针即可继续）

1. 查 `VID_0483` 有设备 → `pio run -d testbeds/xpulse-min -t upload`。
2. 烧完读 `GPIOC ODR`：**bit2 应为 0**（PC2 低 → 红灯亮，共阳低电平点亮）。
3. 目视确认：**红灯亮、绿/蓝灭**（`LED_RED_Pin` = PC13 无灯，PC2 = 红）。
4. 若亮 → **L5 达成**（首次在真板上看到"工具改的配置"变成可见现象），把本报告 §3.5 补成成功并更新看板。
5. 之后按 `gate-2.0-checklist.md` §3 继续：串口（本板 USART1=PA9/PA10、USART3=PC10/PC11，**需另配**；本工程未启用任何 USART）。

---

## 6. 复现命令

```bash
# 1) 建副本（原仓只读）
cp -r "D:/Projects/GitHub/template-mcu-minimal-STM32G474VET6-XPulse" testbeds/xpulse-min   # 去掉 .git / node_modules / .pio

# 2) 关迁移弹窗（每次生成前都要确认，project generate 会写回 true）
python scripts/ioc_field.py --ioc testbeds/xpulse-min/*.ioc set ProjectManager.AskForMigrate false

# 3) 生成（首次建议给足超时；.mx 见 §3.1）
bash scripts/regen.sh testbeds/xpulse-min -m testbeds/xpulse-min/scripts/setpin-pc2.mx \
     -e GPIO --expect-pins PC2=GPIO_Output --timeout 480

# 4) 构建 + 烧录
pio run -d testbeds/xpulse-min
pio run -d testbeds/xpulse-min -t upload

# 5) 读回寄存器（可选，做客观判据）
#    GPIOC MODER 0x48000800 / ODR 0x48000814；PC2 应为输出且 ODR bit2 = 0
```
