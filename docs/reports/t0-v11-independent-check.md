# T0 · v1.1 独立复核（GATE-1.1 第三方第二双眼睛）

> 产出时间：2026-11-03 · owner：`env-agent`（**独立执行，未参考 verifier-dev / lead 的报告正文**）· 验证等级：**L2**（实跑测试 + 实跑核验器 + 构造 fixture）
> 复核对象：`verify_generation.py` v1.1 + `regen.sh` + `ioc_field.py` + `tests/`
> 结论：**四项全部与 lead 声称一致；无一项不一致。** 另附 3 条独立发现，其中 1 条闭环了此前的悬置问题。

---

## 0. 基线与环境（先钉死冻结点）

```text
$ git log --oneline -1
31fd1ee docs(reports): 清除无证据来源的 (a2) 转述并同步契约      # ✅ 与 lead 给的 FROZEN 一致

$ git status --porcelain scripts/ tests/
（无输出）                                                        # ✅ 工作区干净

$ python -V
Python 3.13.14
$ python -m pytest --version
pytest 9.2.0
```

关键文件 mtime（确认跑的时候文件已稳定，避免抓在写入中间）：
`scripts/verify_generation.py` 12:57:58 · `scripts/regen.sh` 12:39:00 · `scripts/ioc_field.py` 12:08:09

---

## 1) pytest —— ✅ PASS

```text
$ python -m pytest tests/ -q
........................................................................ [ 97%]
..                                                                       [100%]
74 passed in 73.29s (0:01:13)
```

**判定：`74 passed`，0 failed，与 lead 声称的数字一致。** 耗时 73.29s（本机 Python 3.13.14 / pytest 9.2.0）。

---

## 2) `.mx` 六态 fixture —— ✅ 6/6 全部符合期望

**方法**：我自己新建临时目录（`tempfile.mkdtemp`），**未触碰任何 testbed**。每个 case 目录下建 `scripts/gen.mx`，用 `--project-root <该 case 目录>` 各跑一次，从 stdout 抓 `mx_script_abs_path` 那一行（原始输出，未经改写）。

### 2.1 原始输出

```text
################ case 1：占位符未替换      期望 warn
.mx: project path __PROJECT_DIR__
verdict=PASS errors=0 warnings=1
[warn] mx_script_abs_path   1 处占位符未替换（脚本未配置，直接跑会失败）：scripts/gen.mx:1: __PROJECT_DIR__（in_comment=false） ← project path __PROJECT_DIR__。扫描 1 个 .mx 脚本，0 处绝对路径指向本工程

################ case 2：真实绝对路径（自指）    期望 pass
.mx: project path C:\Users\Leon\AppData\Local\Temp\p32v11b-xxxx\c2-realpath
verdict=PASS errors=0 warnings=0
[pass] mx_script_abs_path   扫描 1 个 .mx 脚本，1 处绝对路径指向本工程，无指向别处的绝对路径（CubeMX 脚本不支持变量，A1 的绝对路径属合规）

################ case 3：指向别处    期望 fail
.mx: project path D:\Projects\GitHub\HUSTRadio\stm32-digital-clock
verdict=FAIL errors=1 warnings=0
[fail] mx_script_abs_path   1 处 .mx 绝对路径**指向别的工程** → 生成会写进另一处，克隆到新机器必踩（模板 A1）。扫描 1 个 .mx 脚本，0 处绝对路径指向本工程。命中：scripts/gen.mx:1: project path D:\Projects\GitHub\HUSTRadio\stm32-digital-clock（in_comment=false）

################ case 4：大小写混排 + 正斜杠（自指）    期望 pass
.mx: project path c:/users/leon/appdata/local/temp/p32v11b-xxxx/c4-mixedcase-fwdslash
verdict=PASS errors=0 warnings=0
[pass] mx_script_abs_path   扫描 1 个 .mx 脚本，1 处绝对路径指向本工程，无指向别处的绝对路径

################ case 5：含 ../ 归一化（自指）    期望 pass
.mx: project path c:/users/leon/appdata/local/temp/p32v11c-xxxx/c5-dotdot/../c5-dotdot
verdict=PASS errors=0 warnings=0
[pass] mx_script_abs_path   扫描 1 个 .mx 脚本，1 处绝对路径指向本工程，无指向别处的绝对路径

################ case 5b：更深一层 + ./ + 尾部斜杠（自指）    期望 pass
.mx: project path c:/users/leon/appdata/local/temp/p32v11c-xxxx/sub/c5b-x/../c5b-x/./
verdict=PASS errors=0 warnings=0
[pass] mx_script_abs_path   扫描 1 个 .mx 脚本，1 处绝对路径指向本工程，无指向别处的绝对路径

################ case 6：指向上级目录    期望 warn
.mx: project path C:\Users\Leon\AppData\Local\Temp\p32v11b-xxxx
verdict=PASS errors=0 warnings=1
[warn] mx_script_abs_path   1 处指向本工程的上级目录（需配合 project name 才落对目录，请人工确认）：scripts/gen.mx:1: ... → 指向上级目录 C:\Users\Leon\AppData\Local\Temp\p32v11b-xxxx
```

### 2.2 判定

| # | 场景 | 期望 | 实得 | 判定 |
|---|---|---|---|---|
| 1 | 占位符 `__PROJECT_DIR__` | warn | **warn** | ✅ |
| 2 | 真实绝对路径（自指） | pass | **pass** | ✅ |
| 3 | 指向别处（`D:\...\stm32-digital-clock`） | fail | **fail** | ✅ |
| 4 | 大小写混排 + 正斜杠（自指） | pass | **pass** | ✅ |
| 5 | 含 `../` 归一化（自指） | pass | **pass** | ✅ |
| 5b | 更深 `../` + `./` + 尾部斜杠（自指） | pass | **pass** | ✅ |
| 6 | 指向上级目录 | warn | **warn** | ✅ |

**六态全绿**。你重点担心的两条都成立：`casefold` + 斜杠统一有效（case 4），`normpath` 生效（case 5 / 5b）。第四态方向也**没写反**（case 6 是 warn 而非 fail；case 3 是 fail 而非被误判成上文目录）。

> **诚实记录一个我自己的失误**：case 5 首版我把 `.mx` 写进了 `c5-dotdot/`，内容却引用了 `c4-mixedcase-fwdslash/../c4-...`（复制粘贴时错用了 c4 的路径），实得 `fail`。**那是我的 fixture 构造错误，不是核验器缺陷**——它按设计正确地判定"指向别处"。修正构造（改为引用自身）后判 `pass`。先记在这里，避免这条被误传成 bug。

---

## 3) `pins_present` 反向 + 正向对照 —— ✅ 反向红、正向绿

### 3.1 反向（不存在的引脚，硬门槛）

```text
$ python scripts/verify_generation.py \
    --log docs/logs/phase1/s1-regen/cubemx-generate.log \
    --main-c testbeds/template-mcu-STM32G474-series/Core/Src/main.c \
    --mxproject testbeds/template-mcu-STM32G474-series/.mxproject \
    --ioc testbeds/template-mcu-STM32G474-series/stm32-g474-template.ioc \
    --project-root testbeds/template-mcu-STM32G474-series \
    --expect GPIO --expect-pins PC999=GPIO_Output

[platform32] 生成核验 verdict=FAIL errors=1 warnings=1 expect=GPIO
  [pass] log_cannot_map       生成日志无 'Cannot map' 命中
  [pass] main_init_present    全部 1 个期望外设都有初始化函数定义：GPIO → MX_GPIO_Init（exact，定义 L152）
  [pass] main_init_called     全部 1 个初始化函数都在 main() 内被调用：GPIO → MX_GPIO_Init（调用 L88）
  [fail] pins_present         1/1 个期望引脚没有真正生效：PC999: .ioc 里没有 PC999.Signal（期望 GPIO_Output）
  [pass] mxproject_abs_path   '.mxproject' 无盘符绝对路径（换机可复现）
  [warn] mx_script_abs_path   1 处占位符未替换（脚本未配置…）：scripts/cubemx-init.mx:5: __PROJECT_DIR__
  [pass] syscalls_path        生成日志无 syscalls.c / sysmem.c 叠加路径异常

rc=1
```

**判定：✅ `pins_present` = fail，rc=1，报错精确到"`.ioc` 里没有 PC999.Signal"。第 7 项确实起作用。**

### 3.2 正向对照（**必须补做**，否则"永远 fail 的 check"也能骗过反向测试）

```text
# PB0（基线已有）
[platform32] 生成核验 verdict=PASS errors=0 warnings=1 expect=GPIO
  [pass] pins_present         全部 1 个期望引脚都在 .ioc 与生成物中对上：PB0.Signal=GPIO_Output + __HAL_RCC_GPIOB_CLK_ENABLE()
rc=0

# PC13（基线已有）
[pass] pins_present         全部 1 个期望引脚都在 .ioc 与生成物中对上：PC13.Signal=GPIO_Output + __HAL_RCC_GPIOC_CLK_ENABLE()
rc=0

# 混合：PB0 存在 + PC999 不存在（应只报 PC999）
[platform32] 生成核验 verdict=FAIL errors=1 warnings=1 expect=GPIO
[fail] pins_present         1/2 个期望引脚没有真正生效：PC999: .ioc 里没有 PC999.Signal（期望 GPIO_Output）。已生效：PB0.Signal=GPIO_Output + __HAL_RCC_GPIOB_CLK_ENABLE()
rc=1

# 期望值写错：PB0 期望成 GPIO_Input（验证比对方向不是恒真）
[platform32] 生成核验 verdict=FAIL errors=1 warnings=1 expect=GPIO
[fail] pins_present         1/1 个期望引脚没有真正生效：PB0: .ioc 里 PB0.Signal=GPIO_Output（期望 GPIO_Input）
rc=1
```

**判定：✅ 正向 pass（PB0 / PC13）、混合只报缺失项、期望值写错也能红 —— 说明它不是"恒 fail"也不是"恒 pass"。**
额外加分：它同时校验了 `.ioc` 的 `Signal` **和**生成物的 `__HAL_RCC_GPIOx_CLK_ENABLE()`，即"配置层 + 生成物层"双向印证，比只查 `.ioc` 强。

---

## 4) `--allow-signal` 行为回归 —— ✅ 三态全部符合，短词漏洞已堵

日志：`docs/logs/phase1/s3b-regen/cubemx-generate.log`，其中确有 1 条真实命中（原文见 §5.1）。

```text
################ 4a) --allow-signal VP_TIM4_VS_ClockSourceINT（精确信号名）
[platform32] 生成核验 verdict=PASS errors=0 warnings=1 expect=GPIO
  [warn] log_cannot_map       命中 1 条 'Cannot map'，全部命中 --allow-signal 白名单（VP_TIM4_VS_ClockSourceINT@L321），按已知噪音降级为 warning
rc=0

################ 4b) 不带 --allow-signal
[platform32] 生成核验 verdict=FAIL errors=1 warnings=0 expect=GPIO
  [fail] log_cannot_map       命中 1 条 'Cannot map'，其中 1 条不在白名单 → 外设会被静默丢弃（D5/H-6）。L321: VP_TIM4_VS_ClockSourceINT
rc=1

################ 4c) --allow-signal signal（短词）
[platform32] 生成核验 verdict=FAIL errors=1 warnings=0 expect=GPIO
  [fail] log_cannot_map       命中 1 条 'Cannot map'，其中 1 条不在白名单 → 外设会被静默丢弃（D5/H-6）。L321: VP_TIM4_VS_ClockSourceINT
rc=1
```

| 调用 | 期望 | 实得 | 判定 |
|---|---|---|---|
| `--allow-signal VP_TIM4_VS_ClockSourceINT` | warn / PASS / rc=0 | warn / PASS / **rc=0** | ✅ |
| 不带 `--allow-signal` | fail / rc=1 | fail / **rc=1** | ✅ |
| `--allow-signal signal`（短词） | fail / rc=1 | fail / **rc=1** | ✅ |

**判定：✅ 你重点验的第 3 条（短词不得放行）成立 —— 用 `signal` 这个词关不掉 D5 守卫，白名单必须是精确信号名。**

---

## 5. 独立发现（3 条，均非缺陷）

### 5.1 ⭐ `Cannot map` 的真实级别是 `[INFO]` + 时间戳前缀 —— 此前悬置项就此闭环

`docs/logs/phase1/s3b-regen/cubemx-generate.log:321` 原文：

```text
2026-11-03 12:33:47,866 [INFO] ImportTextPane:234 - (OptionalMessage_ERROR) Cannot map signal (VP_TIM4_VS_ClockSourceINT) on pin (VP_TIM4_VS_ClockSourceINT)
```

⇒ **`Cannot map` 走的是 `[INFO]`，且带 `YYYY-MM-DD HH:MM:SS,mmm` 前缀** → 精确命中 `vscode-cube-mcp` 的 `NOISE_RE` 第一条分支 → **MCP 通道必然把它整行删掉**。

这把我此前标为"未实测"的那条**变成已证实**：**G1 必须读原始日志，不能消费 MCP 返回文本**，否则负路径会被上游过滤掉、造成假阴性。`verify_generation.py` 当前正是读原始日志（`--log` 直接吃 CubeMX 的 stdout 重定向文件），处置正确。

同时印证：`s1-regen` 日志（正常路径）**无** `Cannot map` 命中，`s3b-regen` 日志**有** 1 条 —— 核验器的判定与日志真实内容对得上，不是恒绿。

### 5.2 真实 G474 基线在 `mx_script_abs_path` 上**恒为 warn**（设计预期，但需写进文档）

第 3 项那次真实基线运行的输出里：

```text
[warn] mx_script_abs_path   1 处占位符未替换（脚本未配置，直接跑会失败）：scripts/cubemx-init.mx:5: __PROJECT_DIR__（in_comment=false）
```

`testbeds/template-mcu-STM32G474-series/scripts/cubemx-init.mx:5` 就是 `project path __PROJECT_DIR__`（模板 A1 的占位符约定）。所以**任何照模板建的真实工程，只要保留 `cubemx-init.mx`，`mx_script_abs_path` 就永远是 warn**，`verdict` 会一直是 `PASS (warnings=1)`。

不是缺陷（占位符确实"未配置、直接跑会失败"），但**SKILL.md 应写明"warn ≠ 坏"**，否则使用者会以为自己的工程有问题；或者明确要求"首建完成后把 `cubemx-init.mx` 的占位符替换掉/删掉"，让 warn 消掉。

### 5.3 `--expect-pins` 未传时是 `skip` 而非静默 pass

```text
[skip] pins_present         未提供 --expect-pins，跳过引脚级检查（v1.1 的外设级保证不含引脚增量）
```

措辞明确、不冒充通过，这点写得好。

---

## 6. 与 lead 声称的差异：**无**

| lead 的说法 | 我的独立结果 |
|---|---|
| `31fd1ee` 已推送、`scripts/ tests/` 干净 | ✅ 一致 |
| pytest `74 passed` | ✅ `74 passed in 73.29s` |
| 六态期望（含 `../` 归一化、上级目录 warn） | ✅ 6/6 一致 |
| `--expect-pins PC999=...` 应 fail | ✅ fail，rc=1 |
| `--allow-signal` 三态（含短词必须仍 fail） | ✅ 三态一致 |

**唯一"不一致"是我自己 case 5 首版 fixture 写错了路径**（详见 §2.2 诚实记录），修正后与期望一致，与核验器无关。

---

## 7. 未覆盖 / 边界（如实标注）

| # | 项 | 说明 |
|---|---|---|
| 1 | MCP 客户端内的工具调用 | 全程走 CLI 等价通道（D12）。MCP 通道只做了协议级握手，未在客户端内调用工具 |
| 2 | `pins_present` 对"`.ioc` 有 Signal 但生成物缺 `__HAL_RCC_*_CLK_ENABLE`" 的组合态 | 未单独构造该组合（只验了"`.ioc` 缺失"与"全对上"两端）。若该组合存在，应报 fail —— 建议 verifier-dev 补一条单测 |
| 3 | `regen.sh` 的真实生成路径 | 本次未跑真生成（只跑核验器与 fixture）；`regen.sh` 的回滚不完整问题已在另一份报告提出（`t0-regen-sh-review.md`），本次不重复 |
| 4 | `--allow-signal` 对 `OptionalMessage_ERROR` 类噪音的处理 | 只验了 `Cannot map` 路径，未验"仅白名单信号命中但 generate 失败"的组合 |

---

## 8. 签署

**四项全过，六态全绿，短词漏洞已堵，第 7 项反向可红。** 我这一票：**GATE-1.1 从我的角度可以过**（前提是 lead 与 `skill-author` 只读清单的结论一致）。
报告未 commit（按 lead 指示，工作区归 `skill-author` 管理，避免抢索引）。
