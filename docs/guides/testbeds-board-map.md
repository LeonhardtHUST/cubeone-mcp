# testbeds ↔ 实板对照表（选工程 / 首烧前必查）

> **一句话**：`testbeds/` 里"同是 STM32G474"的工程**不是**同一块板。烧之前先在这页查
> "这个 testbed 面向哪块板"，再去 [`gate-2.0-checklist.md`](gate-2.0-checklist.md) §1 逐项对引脚。
>
> 来源：2026-11-04 接板首日 **F4**，见
> [`docs/reports/phase2-bringup-2026-11-04.md`](../reports/phase2-bringup-2026-11-04.md) §4、§5。
>
> ⚠️ **本页是唯一随仓库分发的对照真源**：`/testbeds/` 被 `.gitignore:9` 整个忽略
> （`git check-ignore -v testbeds/README.md` 可验），写在 testbed 目录里的说明只在做实验的这台机器上存在，
> **clone 之后看不到**。所以"面向哪块板"这条事实必须写在 `docs/` 里。

---

## 1. 为什么会需要这一页（F4 现场）

接板首日先烧了 C3 无板预演的产物 `testbeds/nuedc/G474_01_gpio`：

| 环节 | 结果 |
|---|---|
| 烧录 | `Verified OK`，探针无报错 |
| 寄存器回读 | `GPIOC MODER = 0x57FFFF00`、`ODR = 0x0000C000` —— **配置确实落到了硬件** |
| 人眼观察 | **板上什么也没发生** |

原因不是工具没生效，而是**工程与板不匹配**：该工程把 RGB 接在 **PC13/PC14/PC15**（NUEDC 原板），
而手上的实板是 **X-Pulse**，RGB 在 **PC0/PC1/PC2** 且**共阳低电平点亮**，**PC13 只引到扩展排针、根本没有 LED**。
两块的 MCU 都是 `STM32G474VETx`，`.ioc` 里 `Mcu.Name` 都是 `STM32G474V(B-C-E)Tx` ——
**"同 MCU / 同封装 / 同 HAL 包"三条都成立，仍然不能互相烧**。

> 这类失败最伤人的地方：所有软件侧判据都是绿的，只有"人眼看不到"这一条是红的，
> 极容易被误判成「工具没写入 / 探针坏了 / 固件没跑」而开始错误的排查。

---

## 2. 对照表

### 2.1 绑定了实板的工程（**只有这两个可作为首烧目标**）

| testbed | 面向板卡 | MCU | 板载 LED 接线 | 有效电平 | 已达成等级 | 首烧适用范围 |
|---|---|---|---|---|---|---|
| `testbeds/nuedc/G474_01_gpio` | **NUEDC_2027 原板**（副本来源 `D:/Projects/GitHub/NUEDC_2027/G474/G474_01_gpio`，见 [`s4-dryrun-g474_01_gpio.md`](../reports/s4-dryrun-g474_01_gpio.md)） | `STM32G474VETx`（LQFP100），`ProjectManager.CoupleFile=true` | `LED_R/G/B = PC13/PC14/PC15`（`Core/Inc/main.h:60–65`） | ⚠️ **本仓未取证**：LED 极性以 NUEDC 原板原理图为准，不要从 `.ioc` 猜。本副本 `Core/Src/gpio.c:53–56` 的**初始电平**是 R=`GPIO_PIN_RESET`、G/B=`GPIO_PIN_SET` | 无板预演 L3（构建）；在 X-Pulse 上误烧过一次（F4） | **仅 NUEDC 原板**。烧到 X-Pulse = "成功但没现象" |
| `testbeds/xpulse-min` | **X-Pulse / Penguins-G474** | `STM32G474VET6`（LQFP100） | RGB 是**同一颗三色灯**的三个阴极：`PC0=蓝 / PC1=绿 / PC2=红`（`Core/Inc/xpulse.h`，**注意是 B/G/R 顺序**） | **共阳接 3V3、经 RN1 2 kΩ 限流 → 低电平点亮**（`XP_LED_ON = GPIO_PIN_RESET`）；`XP_LED_OFF = GPIO_PIN_SET`。**PC13 只到 P2/P3 排针，无 LED** | **L5**（改配置 → 生成 → G1 PASS → 构建 → 烧录 → 寄存器回读 → 目视，全链） | **X-Pulse 唯一推荐首烧目标** |

X-Pulse 当前验证态（`phase2-bringup-2026-11-04.md` §3.6）：

```text
.ioc        PC2.Signal=GPIO_Output（Mcu.Pin1，Mcu.PinsNb 4→5）
main.c      HAL_GPIO_WritePin(GPIOC, LED_RED_Pin|GPIO_PIN_2, GPIO_PIN_RESET)
GPIOC MODER 0xF7FFFFDF  → PC2 = 01（推挽输出）
GPIOC ODR   0x00000000  → bit2 = 0（PC2 低电平）
PC          0x08000D08  → 程序在 Flash 中运行
目视        红灯亮、绿/蓝灭
```

> `LED_RED_Pin` 是模板 `.ioc` 留下的 **PC13 占位配置**，本次没删；它不接 LED，
> 因此与 PC2 一起拉低不会造成可见冲突，但读代码时别把它当成板载灯。

### 2.2 通用模板 / 一次性副本（**不绑定实板，不得当首烧目标**）

| testbed（组） | 实际是什么 | 面向板卡 | 能否烧实板 |
|---|---|---|---|
| `template-mcu-STM32G474-series/`、`template-mcu-STM32F103C8T6/`、`template-mcu-STM32H723-series/` | 三个**官方最小模板**的本地克隆（T1.5），用于生成链 / 核验器的基线 | 无（通用模板，按 MCU 系列组织） | ❌ 默认 PC13 闪灯是模板占位，不代表任何实板接线 |
| `stm32-digital-clock/` | **真实用户工程副本**（STM32F103C8T6，S2 只读审计对象，见 [`t1.7-s2-audit-stm32-digital-clock.md`](../reports/t1.7-s2-audit-stm32-digital-clock.md)） | 该用户工程自己的板（电工基地招新题目），**未在本仓登记原理图** | ❌ 板卡信息不全，不做首烧 |
| `_s1-dryrun/`、`_s1-run/`、`_s3-probe/`、`_s3b/`、`_s3b2/`、`_verifier-regen/` | 各批次的一次性**丢弃副本**（S1 干跑 / S3 负路径 / 核验器回归 / TIM4 探测） | 无 | ❌ 用完即弃，状态可能被故意写坏 |
| `stm32-g474-template/` | 仅剩单个 `.ioc` 的残留目录 | 无 | ❌ |
| `xpulse-min/` 之外的 `*_g474` 变体 | 见 §2.1 之外的全部 G474 工程 | 无 | ❌ |

#### ⚠️ 2.3 一个会放大 F4 的坑：模板 README 里写着"面向 Penguins-G474"

三份 G474 系列模板及其所有干跑副本的 `README.md` 都写着：

> 默认面向 **Penguins-G474** 开发板（STM32G474VET6 …），默认 HSI 16 MHz、**PC13 闪灯**。

而 X-Pulse 的板级头文件 `Core/Inc/xpulse.h` 明确写着 **PC13 只到扩展排针、没有 LED**，
板载 RGB 在 PC0/PC1/PC2。**这两句话不能同时为真**：要么模板的"默认面向"是沿用旧板的描述，
要么该 README 指的是另一版硬件。

**裁定**：板级事实以**板级头文件 / 原理图**为准，不以模板 README、也不以 `.ioc` 的 `GPIO_Label` 为准。
因此即便看到"面向 Penguins-G474"字样，**也不要把这些模板直接烧到手上的 X-Pulse 板** ——
要用就用 §2.1 里已经按实板改过引脚、且跑通过 L5 的 `testbeds/xpulse-min`。

---

## 3. 选工程的顺序（接板日照这个走）

1. **先定板**：看丝印 / 板级头文件（X-Pulse：`Core/Inc/xpulse.h`），写下"板上 LED 在哪几个脚、什么电平亮"。
2. **再查本页 §2.1**：找"面向该板"的 testbed。查不到 = **没有可烧目标**，先建副本并按实板改引脚，
   不要从"同 MCU"里挑一个凑合。
3. **逐项对引脚与有效电平**：走 [`gate-2.0-checklist.md`](gate-2.0-checklist.md) §1 的那一行检查；
   灯的引脚、有效电平、按键、串口四项都要对上。
4. **然后才进流程**：`regen.sh` → G1 核验 → `pio run` → GATE-2.1 安全确认 → 烧录 → 回读 + 目视。

> 反过来的顺序（先挑工程、再看板）正是 F4 的成因：C3 预演选 NUEDC 工程时**没有实板**，
> 那个选择本身没错；错在接板日把"已有产物"当成了"默认首烧目标"，没有重新核对板卡。

---

## 4. 维护约定

- **新增 testbed 必须在本页登记**，至少写清「面向哪块板 / 能否作为首烧目标 / LED 引脚与有效电平」；
  一次性副本也要登记成组，别让它看起来像可烧工程。
- **板级事实的唯一来源是板级头文件（如 `xpulse.h`）与原理图**。`.ioc` 只说明"这个工程怎么配的"，
  **不说明"板上接了什么"** —— 把 `.ioc` 里的 `GPIO_Label=LED_R` 当成板级证据，就是 F4 的思维错误。
- 换板 / 改接线后，同步改本页 §2.1 与 `gate-2.0-checklist.md` §1。
- 本页是**标注文档**，不改 `docs/TASKBOARD.md` 的任务表与 §4 快照（新增一行任务会让机器校验失配）。
- 本机 `testbeds/README.md` 是一份便利指针（被 `.gitignore` 忽略，仅本机可见），**不得当作真源引用**。

---

## 5. 证据与上游

| 事实 | 出处 |
|---|---|
| F4 误烧、引脚不匹配、X-Pulse 引脚映射 | [`docs/reports/phase2-bringup-2026-11-04.md`](../reports/phase2-bringup-2026-11-04.md) §3.1 / §4 / §5 |
| L5 回读与目视双判据 | 同上 §3.6 |
| NUEDC 副本来源与 C3 预演四段 | [`docs/reports/s4-dryrun-g474_01_gpio.md`](../reports/s4-dryrun-g474_01_gpio.md) |
| 接板日"引脚与实板对得上"检查 | [`docs/guides/gate-2.0-checklist.md`](gate-2.0-checklist.md) §1 |
| X-Pulse 板级引脚映射（原仓） | `D:/Projects/GitHub/template-mcu-minimal-STM32G474VET6-XPulse/Core/Inc/xpulse.h`（原仓只读） |
| `testbeds/` 被整体忽略 | `.gitignore:9`（`/testbeds/`）；`CONTRIBUTING.md` §目录归属 |
