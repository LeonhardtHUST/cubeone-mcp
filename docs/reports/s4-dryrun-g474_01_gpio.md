# S4 预演（无板）：`NUEDC_2027/G474/G474_01_gpio` 前四段实跑

> 产出时间：2026-11-04 · Owner：`software-engineer` · 批次：**C3.1**（完备计划 §5）
> 对象：`D:/Projects/GitHub/NUEDC_2027/G474/G474_01_gpio` → 副本 `testbeds/nuedc/G474_01_gpio`
> **原仓只读**：改前/改后 `Project.ioc` 的 sha256 均为 `9705d211…b47b`（`docs/logs/phase4/00-original-sha256.txt`）；
> 全部操作只发生在副本里（`testbeds/` 被 `.gitignore:9` 忽略）。
> 本机：Windows 11 · CubeMX **6.18.1**（工程原为 6.18.0）· PlatformIO Core 6.2.0 · Python 3.13.14

## 0. 结论（先看这一段）

| 段 | 做了吗 | 结果 | L 等级 |
|---|---|---|---|
| ① 备份 + 改配置（普通 GPIO） | ✅ | 改 `PC13.PinState`：`GPIO_PIN_SET` → `GPIO_PIN_RESET`，`.ioc` diff **1 行** | L2（单键写 + 回读一致） |
| ② CubeMX 真生成 | ✅ | 退出码 0、**无 KO**、耗时 **62 s**（另一次 58 s）；生成物只动了 **2 个文件** | L3 |
| ③ 生成核验（G1，7 项） | ✅ | **修复前 `verdict=FAIL`（errors=2，全是核验器结构性误判）→ 修复后 `verdict=PASS`（errors=0），`main_init_present` 命中 `Core/Src/gpio.c:L42`** | **L4**（重新生成 + `verify.json` verdict/各 status，见 §2.3.1） |
| ④ 构建（`pio run`） | ✅（补了实验脚手架后） | **SUCCESS**：`FLASH 5104 B / 512 KB（0.97%）`、`RAM 1664 B / 128 KB（1.27%）` | L3 |

**整体 L 等级：L4（生成 + 核验链）+ L3（构建），无 L5。** 依据与边界：
- L4 的证据是 `verify.json` 的 `verdict` 与七项 `status`（§2.3.1 复跑结果），不是"跑过就算"；
- **⚠️ 参数级仍在盲区**：`PC13.PinState` 这类参数改动，七项核验一条都看不见（`pins_present` 只保证
  `.Signal` + 端口时钟使能）。本次靠 **A/B 生成对照**（`gpio.c` 里 `HAL_GPIO_WritePin(... GPIO_PIN_SET)`
  → `... GPIO_PIN_RESET`）才证到"值真的落地"——这段证据属 L2 人工核对，**不计入 L4**；
- **烧录 / 串口（L5）未做** —— 无硬件，Phase 2 挂起（D7）。

三个发现（这是本次预演的主要产出，比"跑通"更有用；**F1/F3 已于同日修复**）：

- **F1（重要，已修）核验器在「每外设一对 `.c/.h`」工程上误判为"外设被静默丢弃"** —— 不是配置错，是 `main_init_present` / `pins_present` 只扫 `--main-c` 造成的**假失败**。本工程 `ProjectManager.CoupleFile=true`，`MX_GPIO_Init` 定义在 `Core/Src/gpio.c:42`，`main.c:90` 只有调用。修复见 §2.3.1。
- **F2（重要）重新生成会静默改掉时钟参数** —— 原 `main.c:130` 的 `PLLN=100` 与 `.ioc` 的 `RCC.PLLN=85` **本来就不一致**；生成把 `main.c` 拉回 85。按 PLL 公式推算，原值对应 SYSCLK **200 MHz**（HSE 24M / PLLM 6 = 4 MHz 输入 × 100 / PLLP 2），**超出 G474 上限 170 MHz**，`HAL_RCC_ClockConfig` 大概率失败进 `Error_Handler`。**7 项核验一条都看不见这件事**（参数级失明已在保证边界声明里）——只记账，不改核验器。
- **F3（已改文档）`AskForMigrate` 会被 `project generate` 写回 `true`** —— 既有文档（`references/pitfalls.md` P1 / `regen.sh` 用法注）写的是"纯 generate 不写回"。实测：置 `false` → `project generate` → 读回 **`true`**（`docs/logs/phase4/12-askformigrate-probe.log`）。而版本戳更旧 + 该标志为 `true` 时，无 GUI 的 `-q` 生成**会挂住直到超时**（首次尝试 300 s 超时，`02-first-generate.log` 停在 `Begin LoadConfig()`）。P1 已按实测改写（含旧判断留档）。

---

## 1. 实验设置

| 项 | 值 |
|---|---|
| 源工程 | `D:/Projects/GitHub/NUEDC_2027/G474/G474_01_gpio`（MCU `STM32G474VET6`，**MDK-ARM/Keil** 工程） |
| 副本 | `testbeds/nuedc/G474_01_gpio`（`cp -r` 全量，6.3 MB） |
| 副本基线哈希 | `9705d211a0f1…b47b`（与原仓一致 ⇒ 拷贝无损） |
| 原工程固有问题 | `.ioc` 版本戳 `6.18.0 / DB.6.0.180`（本机 6.18.1 / DB.6.0.181）、`AskForMigrate=true`、**无 `platformio.ini`、无 GCC 链接脚本**、**无 `.mxproject`**（从未在本机生成过） |

**新增的实验脚手架（声明为"预演用"，不是原工程文件）**：

- `testbeds/nuedc/G474_01_gpio/scripts/cubemx-generate.mx`（三行：`config load` → `project generate` → `exit`）
- `testbeds/nuedc/G474_01_gpio/platformio.ini` + `boards/`（从 `testbeds/_verifier-regen/g474/` 派生，**去掉 `-Werror`、把 `BSP/Src` 纳入编译**；文件头写明了这两处放宽与结论边界）

---

## 2. 四段逐段

### 2.1 ① 备份与改配置

```bash
python scripts/ioc_backup.py --project testbeds/nuedc/G474_01_gpio          # → .ioc.bak + .bak.sha256（R-C3 sidecar）
python scripts/ioc_field.py --ioc <副本>/Project.ioc set PC13.PinState GPIO_PIN_RESET
```

- 选这个改动的原因：**在能力边界内**（普通 GPIO 的电平），且是"参数级"改动 —— 正好用来暴露"核验器看得见外设、看不见参数"这条边界。
- `.ioc` 只变 1 行（`66c66`），回读确认为 `GPIO_PIN_RESET`（`docs/logs/phase4/06-change.log`）。

### 2.2 ② CubeMX 真生成

```bash
bash scripts/regen.sh testbeds/nuedc/G474_01_gpio -e GPIO \
     -o docs/logs/phase4/09-final --expect-pins PC13=GPIO_Output
```

| 项 | 实测 |
|---|---|
| 退出码 / KO | `0` / **无 KO**（`grep -cE '^\s*KO\s*$'` = 0） |
| 耗时 | **62 s**（`07-regen`）· 58 s（对照轮）· 9.34 s（纯构建不算） |
| 生成物变动 | 仅 `Core/Src/gpio.c`、`Core/Src/main.c`（`diff -rq` 原仓 vs 副本，`13-diff-scope.log`）；`Drivers/`、`MDK-ARM/` **零改动** |
| `.ioc` 变动（基线 → 现在） | **3 行**：`MxCube.Version 6.18.0→6.18.1`、`MxDb.Version DB.6.0.180→DB.6.0.181`、`PC13.PinState SET→RESET` |

> **P2 的对照样本**：这一次迁移只有 2 行版本戳变化，**没有**出现"改一个 GPIO 却 619/106 重写"那种大 diff —— 因为工程本来就只差一个补丁号。P2 说的 619/106 是 `6.17.0→6.18.1` 跨小版本的量级，**不是阈值**，本条可作为"小版本迁移的对照锚点"。

**生成前后 `AskForMigrate` 的行为（F3 的证据链）**：

| 时刻 | `MxCube.Version` | `AskForMigrate` | `-q` 生成 | 证据 |
|---|---|---|---|---|
| 初始 | 6.18.0 | `true` | **挂住 300 s 超时**（停在 `Begin LoadConfig()`） | `02-first-generate.log`（RC=124） |
| 置 `false` 后 | 6.18.0 | `false` | 成功 62 s，同时**自动迁移**版本戳到 6.18.1 | `04-first-generate-retry.log` |
| 迁移后再测 | 6.18.1 | `false` | 成功 58 s，**但 `AskForMigrate` 被写回 `true`** | `12-askformigrate-probe.log` |

**含义**：只要 `.ioc` 的版本戳低于本机、且 `AskForMigrate` 为 `true`，无 GUI 的批处理生成就会**挂死**。
`regen.sh` 的"不拦不改"策略在这一步帮不上忙 —— 因为**它自己也不会改这个键**，而 CubeMX 会把 `true` 写回去。
接板日若要拿旧工程生成，**必须先把 `AskForMigrate` 置 `false` 再跑**（`docs/guides/gate-2.0-checklist.md` 已列为前置项）。

### 2.3 ③ 生成核验（G1，7 项）

```
[platform32] 生成核验 verdict=FAIL errors=2 warnings=0 expect=GPIO
  [pass] log_cannot_map       无 'Cannot map' 命中（另有 4 条 OptionalMessage_ERROR 属已知噪音 D8）
  [fail] main_init_present    1/1 个期望外设没有 MX_..._Init 定义 → 配置未生效或被静默丢弃：GPIO(missing)
  [skip] main_init_called     没有任何已定义的初始化函数可供核对
  [fail] pins_present         1/1 个期望引脚没有真正生效：PC13: .ioc 写了 GPIO_Output，但 main.c 里没有
                              __HAL_RCC_GPIOC_CLK_ENABLE()
  [pass] mxproject_abs_path   无盘符绝对路径
  [pass] mx_script_abs_path   扫描 1 个 .mx，0 处指向别处的绝对路径
  [pass] syscalls_path        无叠加路径异常
```

`regen.sh` 据此 `rc=1` 并**从备份回滚** `.ioc` / `.mxproject`（`Core/` 按约定不回滚），行为与设计一致。

#### F1：这两条 fail 是**核验器的结构性误判**，不是配置错

| 核验器说 | 实际 |
|---|---|
| `main_init_present`：GPIO 没有 `MX_GPIO_Init` **定义** | 定义在 **`Core/Src/gpio.c:42`**，声明在 `Core/Inc/gpio.h:39`，`main.c:90` 只有调用 |
| `pins_present`：`main.c` 里没有 `__HAL_RCC_GPIOC_CLK_ENABLE()` | 在 **`gpio.c:48`** |

**根因**：本工程 `ProjectManager.CoupleFile=true`（"Generate peripheral initialization as a pair of '.c/.h' files"），
CubeMX 把每个外设的 `MX_*_Init` 生成到**独立 `.c`**（`gpio.c` / `tim.c`），`main.c` 只保留调用。
而核验器的 `main_init_present` / `pins_present` **只读 `--main-c` 这一个文件**（`verify_generation.py:556` 起），
于是把"定义在别的文件里"误判成"外设被静默丢弃"。

**这是假失败（false positive），严重程度高于漏报**：它会让一条**完全正确的生成结果**被判红，
使用者要么误以为配置错了去反复改 `.ioc`，要么干脆开始不信核验器。

**核验器看到的部分是对的**：`log_cannot_map` / `mxproject_abs_path` / `mx_script_abs_path` / `syscalls_path` 全 pass，
说明"生成日志干净、路径可复现"这几层没问题。

**建议处置（**已于同日实施**，见 §2.3.1）**：

1. 最小修复：`--main-c` 之外增 `--extra-src`（可重复），或当 `main.c` 里只有调用没有定义时，
   在 `Core/Src/*.c` 里找定义；找到则 pass 并在 detail 里写明"定义在 gpio.c:42"。**← 采用这条**
2. 保守修复（不改行为，只改口径）：检测到 `.ioc` 的 `CoupleFile=true` 时，
   把这两项降为 `warn` + `notes` 说明"本项目使用 per-peripheral 文件，定义不在 main.c，本项不适用"。
   **← 作为"没给 `--project-root` 时的兜底"一并实现**

### 2.3.1 修复后复跑：`verdict=FAIL` → **`verdict=PASS`**

修复内容（`scripts/verify_generation.py`，同日提交）：给了 `--project-root` 时，定义类判据
（`main_init_present` / `pins_present`，以及 `main_init_called` 的定义来源）扫描
`Core/Src/*.c`（含 `main.c`）并拼接判断，报出的位置经 `origin_of()` **换算回原文件行号**；
没给 `--project-root` 且 `.ioc` 的 `CoupleFile=true` 时，这两项由 `fail` **降 `warn`** 并把理由写进
`summary.notes`（**仅此一种情形**）。`regen.sh` 本来就带 `--project-root`，主路径自动获益。

**复跑命令**（与本报告 §5 一致，只是显式补 `--project-root` 与 `--ioc`）：

```bash
python scripts/verify_generation.py \
  --log docs/logs/phase4/12-askformigrate-probe.log \
  --main-c  testbeds/nuedc/G474_01_gpio/Core/Src/main.c \
  --mxproject testbeds/nuedc/G474_01_gpio/.mxproject \
  --project-root testbeds/nuedc/G474_01_gpio \
  --ioc testbeds/nuedc/G474_01_gpio/Project.ioc \
  --expect GPIO --expect-pins PC13=GPIO_Output
```

**复跑结果**：

```
[platform32] 生成核验 verdict=PASS errors=0 warnings=0 expect=GPIO
  [pass] log_cannot_map      无 'Cannot map' 命中（另有 4 条 OptionalMessage_ERROR 属已知噪音 D8）
  [pass] main_init_present   全部 1 个期望外设都有初始化函数定义：
                             GPIO → MX_GPIO_Init（exact，定义 Core/Src/gpio.c:L42）   ← 修复前是 fail
  [pass] main_init_called    全部 1 个初始化函数都在 main() 内被调用：GPIO → MX_GPIO_Init（调用 L90）
  [pass] pins_present        全部 1 个期望引脚都在 .ioc 与生成物中对上：
                             PC13.Signal=GPIO_Output + __HAL_RCC_GPIOC_CLK_ENABLE()   ← 修复前是 fail
  [pass] mxproject_abs_path  无盘符绝对路径
  [pass] mx_script_abs_path  扫描 1 个 .mx，0 处指向别处的绝对路径
  [pass] syscalls_path       无叠加路径异常
```

| | 修复前 | 修复后 |
|---|---|---|
| `verdict` | **FAIL**（errors=2） | **PASS**（errors=0） |
| `main_init_present` | fail：`GPIO(missing)` | pass：`定义 Core/Src/gpio.c:L42` |
| `pins_present` | fail：`main.c 里没有 __HAL_RCC_GPIOC_CLK_ENABLE()` | pass：`.Signal + __HAL_RCC_GPIOC_CLK_ENABLE()` |

**回归（不能修好一个弄坏一个）**：原 `testbeds/_verifier-regen/g474` 复跑仍
`verdict=PASS errors=0 warnings=1`（那 1 条是 S1 一直存在的 `mx_script_abs_path` 占位符 warn，
**条数=1 属预期**）。新用例 `tests/test_verify_multifile.py`（7 项）固定住四条语义：
多文件 pass · 单文件**仍 fail** · `CoupleFile=true` 降 warn · `CoupleFile=false` **不降级**。
契约同步：`references/verify-contract.md` §4.2/§4.3/§4.4。

> **这条修复的意义不在"变绿"**：修复前那个 FAIL 会让使用者以为自己的配置错了（实际全对），
> 于是去改 `.ioc`、去怀疑 CubeMX —— **假失败的成本比漏报更高**。修的是扫描范围，不是判据强度。

### 2.4 ④ 构建

```
[env:genericSTM32G474VE]  Building in release mode
Memory region         Used Size  Region Size  %age Used
             RAM:        1664 B       128 KB      1.27%
           FLASH:        5104 B       512 KB      0.97%
========================= [SUCCESS] Took 9.34 seconds =========================
```

| 口径 | Flash | RAM | 说明 |
|---|---|---|---|
| **链接器 `--print-memory-usage`（对外报数用这个）** | **5104 B（0.97%）** | **1664 B（1.27%）** | 含 `.data/.bss` + `StackSize 0x400` + `HeapSize 0x200` |
| PIO 自带 `size` | 4624 B | 124 B | **不计** stack/heap 预留 ⇒ 明显偏小（**P3 现场实例**） |

用 `-Wl,--print-memory-usage` 与 PIO `size` 的差值 `1664-124 = 1540 B ≈ 0x604`，与 `.ioc` 里
`StackSize=0x400 + HeapSize=0x200 = 0x600` 基本吻合（差额 4 B 为对齐）。

**构建前必须先补脚手架**：直接 `pio run -d <副本>` 会 `NotPlatformIOProjectError`
（`10-pio-build.log`）——本工程是 **Keil 工程**，没有 `platformio.ini`、也没有 GCC 链接脚本。
本次从同 MCU 的模板派生了一份（声明见 §1），**首编译报 `bsp.h: No such file or directory`**（`10b-pio-build-with-ini.log`），
因为 `main.c` `#include "bsp.h"` 而 BSP 在 `BSP/Inc`；调整 `src_dir`/`include_dir`/`build_src_filter` 后成功。

---

## 3. F2 详述：重新生成改掉了时钟参数（核验器看不见）

`Core/Src/main.c` 与原仓相比**只有一行**不同：

```diff
-  RCC_OscInitStruct.PLL.PLLN = 100;
+  RCC_OscInitStruct.PLL.PLLN = 85;
```

而 `.ioc` 里 `RCC.PLLN=85` 且**基线就是这样**（`docs/logs/phase4/00-baseline-Project.ioc.bak:157`），
即：**原工程的 `main.c` 与它自己的 `.ioc` 本来就不一致** —— 要么有人手改过 `main.c`，要么改了 `.ioc` 后没重新生成。

按工程内的时钟参数推算（HSE `24 MHz` / `PLLM=DIV6` → VCO 输入 `4 MHz`，`PLLP=DIV2`）：

| PLLN | VCO 输出 | SYSCLK | 判定 |
|---|---|---|---|
| **100（原 main.c）** | 400 MHz | **200 MHz** | **超 G474 上限 170 MHz** ⇒ `HAL_RCC_ClockConfig` 大概率失败 → `Error_Handler()` |
| **85（.ioc / 生成物）** | 340 MHz | **170 MHz** | 与 `.ioc` 声明一致（`RCC.SYSCLKFreq_VALUE=170000000`） |

**这正是"生成后必须 diff、不能只看 verdict"的现场证据**：

- 7 项核验里**没有一项**会看 `main.c` 的时钟参数 —— 这是 V2 known limitation（参数级失明），不是 bug；
- 如果没有 `diff`，这次"修复了一个超频配置"会被完全忽略；反过来，如果生成把好配置改坏了，也一样静默；
- 结论写进接板清单：**生成前后各存一次 `Core/` 的 diff，逐条解释，解释不了的不许烧板**。

---

## 4. 没做 / 不能做的部分

| 项 | 状态 | 原因 |
|---|---|---|
| 烧录（`pio run -t upload` / ST-Link） | **未做** | 无硬件（D7）；且本工程构建通道是本次补的脚手架，未经真机验证 |
| 串口 / boot log | **未做** | 同上；且本工程 `UART` 未启用（`.ioc` 无 USART 外设，见 `Mcu.IP*`） |
| Keil 工程可编译性 | **未验证** | 本次只验证 GCC/PlatformIO 侧；`MDK-ARM/` 未动也未编译 |
| `BSP/` 代码正确性 | **未验证** | 只保证"能编过"，不保证行为；`-Werror` 已在实验脚手架里关掉 |

---

## 5. 复现步骤

```bash
# 0) 副本（原仓只读）
cp -r "/d/Projects/GitHub/NUEDC_2027/G474/G474_01_gpio" testbeds/nuedc/G474_01_gpio
cd testbeds/nuedc/G474_01_gpio && printf 'config load Project.ioc\nproject generate\nexit\n' > scripts/cubemx-generate.mx

# 1) 关掉迁移弹窗（**必须**，否则 -q 会挂死；见 §2.2）
python ../../scripts/ioc_field.py --ioc Project.ioc set ProjectManager.AskForMigrate false

# 2) 首次生成（产出 .mxproject 与 main.c；regen.sh 的前置检查需要它们）
"/c/ST/STM32CubeMX/jre/bin/java.exe" -jar "/c/ST/STM32CubeMX/STM32CubeMX.exe" -q scripts/cubemx-generate.mx

# 3) 备份 + 改配置 + 生成 + 核验（本批主命令）
cd ../.. && python scripts/ioc_backup.py --project testbeds/nuedc/G474_01_gpio
python scripts/ioc_field.py --ioc testbeds/nuedc/G474_01_gpio/Project.ioc set PC13.PinState GPIO_PIN_RESET
bash scripts/regen.sh testbeds/nuedc/G474_01_gpio -e GPIO \
     -o docs/logs/phase4/09-final --expect-pins PC13=GPIO_Output

# 4) 构建（需先有 platformio.ini + boards/，见 §1）
"/c/Users/Leon/.platformio/penv/Scripts/pio.exe" run -d testbeds/nuedc/G474_01_gpio
```

预期：② 成功、③ **`verdict=PASS`**（F1 修复后；修复前是 FAIL + 两条假失败，见 §2.3.1）、④ SUCCESS。
⚠️ 第 3 步的 `regen.sh` 自带 `--project-root`，第 4 步的 `pio run` 需要先把 §1 的 `platformio.ini`/`boards/` 放好。

---

## 6. 证据文件

| 内容 | 路径（`docs/logs/` 按约定 gitignored，仅本地） |
|---|---|
| 原仓 / 副本基线哈希 | `phase4/00-original-sha256.txt`、`phase4/00-baseline-sha256.txt`、`phase4/00-baseline-Project.ioc.bak` |
| 备份（含 sidecar 摘要） | `phase4/01-backup.log`、`phase4/01-backup.json` |
| 首次生成（挂住 300 s） | `phase4/02-first-generate.log`（RC=124，停在 `Begin LoadConfig()`） |
| 关迁移开关 | `phase4/03-askformigrate-off.log` |
| 迁移 + 首次成功生成 | `phase4/04-first-generate-retry.log`（62 s）、`phase4/04-post-migrate-Project.ioc` |
| 改配置 | `phase4/06-change.log`、`phase4/06-change.json` |
| 生成 + 核验（第一轮 / 终轮） | `phase4/07-regen/`、`phase4/09-final/`（各含 `cubemx-generate.log`、`verify.json`、`verify.md`、`ioc-backup.json`） |
| A/B 对照（PinState SET vs RESET） | `phase4/08-gpio-SET.c`、`phase4/08-gpio-RESET.c`、`phase4/08-regen-SET.log` |
| 构建（失败 → 成功） | `phase4/10-pio-build.log`（`NotPlatformIOProjectError`）、`phase4/10b-pio-build-with-ini.log`（缺 `bsp.h`）、`phase4/11-pio-build-final.log`（SUCCESS） |
| `AskForMigrate` 写回探针 | `phase4/12-askformigrate-probe.log` |
| diff 范围（原仓 vs 副本、基线 vs 现在） | `phase4/13-diff-scope.log`、`phase4/14-core-diff.log` |
