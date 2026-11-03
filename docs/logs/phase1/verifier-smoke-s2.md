# 交叉验证：核验器 v1 在真实非模板工程上的冒烟（正/负样本）

- 执行者：scenario-tester
- 时间：2026-11-03 12:02 (+0800)
- 被验对象：`scripts/verify_generation.py`（verifier-dev，T1.2 产出）
- 被测工程：`testbeds/stm32-digital-clock`（**真实用户工程**，非模板：STM32F1 系列、`Core/` 结构、`test/` 目录、含未提交工作树）
- 性质：**只读冒烟**。未修改 `scripts/`、`tests/` 任何文件（单写者原则）；输出写临时目录，未污染仓库
- 目的：在 GATE-1.1 之前独立确认核验器**不会对已知良好工程误报**，且**失败路径确实会 FAIL**

> ⚠️ **边界声明**：本冒烟**不是 T1.6/T1.8（S1/S3）的正式证据**。原因：本仓未跑过 CubeMX 生成，没有真实生成日志，`log_cannot_map` / `syscalls_path` 两项用的是合成日志，**只验证了代码路径，未验证真实 CubeMX 输出特征**。正式负路径证据须在 S3 用真实 `.ioc` 注入 + 真实生成日志产出。

---

## 1. 正样本：已知良好工程应 PASS 且 0 误报

```bash
python scripts/verify_generation.py \
  --log /tmp/s2-synth.log \
  --main-c testbeds/stm32-digital-clock/Core/Src/main.c \
  --mxproject testbeds/stm32-digital-clock/.mxproject \
  --expect GPIO,SPI1 \
  --json-out /tmp/s2-verify.json
```

输出：

```
[platform32] 生成核验 verdict=PASS errors=0 warnings=0 expect=GPIO,SPI1
  [pass] log_cannot_map       生成日志无 'Cannot map' 命中
  [pass] main_init_present    全部 2 个期望外设都有初始化函数定义：
                              GPIO → MX_GPIO_Init（exact，定义 L199）；
                              SPI1 → MX_SPI1_Init（exact，定义 L161）
  [pass] main_init_called     全部 2 个初始化函数都在 main() 内被调用：
                              GPIO → MX_GPIO_Init（调用 L92）；
                              SPI1 → MX_SPI1_Init（调用 L93）
  [pass] mxproject_abs_path   '.mxproject' 无盘符绝对路径（换机可复现）
  [pass] syscalls_path        生成日志无 syscalls.c / sysmem.c 叠加路径异常
```

JSON 报告：`verdict: pass`，`errors: None`，`warnings: None`，退出码 **0**。

**结论：0 误报。** 这是对核验器泛化能力的一次独立确认 —— 它此前只在 G474 模板（`Core/` + STM32G4 命名）上验过，本次在 **STM32F1 系列、不同 HAL 命名（`stm32f1xx_*`）、不同目录习惯**的工程上依然正确识别 `MX_GPIO_Init` / `MX_SPI1_Init` 的定义行号与调用行号。

## 2. 负样本：期望外设不存在时必须 FAIL 并给出原因

```bash
python scripts/verify_generation.py ... --expect GPIO,SPI1,USART2
```

输出：

```
[platform32] 生成核验 verdict=FAIL errors=1 warnings=0 expect=GPIO,SPI1,USART2
  [pass] log_cannot_map       生成日志无 'Cannot map' 命中
  [fail] main_init_present    1/3 个期望外设没有 MX_..._Init 定义 →
                              配置未生效或被静默丢弃（D5/H-6）：USART2(missing)。
                              已满足：GPIO → MX_GPIO_Init（exact，定义 L199）；
                              SPI1 → MX_SPI1_Init（exact，定义 L161）
  [pass] main_init_called     全部 2 个初始化函数都在 main() 内被调用：…；
                              另有 1 个外设无定义、未参与本项：USART2
  [pass] mxproject_abs_path   '.mxproject' 无盘符绝对路径（换机可复现）
  [pass] syscalls_path        生成日志无 syscalls.c / sysmem.c 叠加路径异常
```

退出码 **1**。

**结论：失败路径正确。** 诊断信息质量好 —— 不只说"缺 USART2"，还点名了根因关联（`D5/H-6`：参数白名单 / 静默丢弃），并列出"已满足的 2 个"作为对照，可直接粘进 bug 报告。

## 3. 退出码约定（`--help` 声明 vs 实测）

| 场景 | 声明 | 实测 | 结论 |
|---|---|---|---|
| 正样本 | `0` = 通过（可含 warning） | **0** | ✅ |
| 负样本（fail 级） | `1` = 存在 fail 级问题 | **1** | ✅ |
| 坏输入（`--log` 不存在） | `2` = 输入/IO/参数错误 | **2** | ✅ |

三条约定全部落实。**这一项对 CI 最重要** —— `regen.sh` / Actions 靠退出码判定，若 fail 却返回 0，整条流水线会假绿。

## 4. 冒烟中顺带确认的两个非问题（避免后续被当成 bug 报）

1. `--json-out` / `--report-md` 传 `/tmp/xxx.json` 时，Python 在 Windows 上把它解析成 `C:\Users\Leon\AppData\Local\Temp\xxx.json`（MSYS 路径未翻译），**属正常**，报告实际落盘成功，不是缺陷。
2. `--main-c` 指向的工程若某外设"无定义"，`main_init_called` 会**跳过**该外设并注明"未参与本项"，而不是二次报错 —— 设计合理（避免一个根因产生两条 fail），不构成漏报。

> 勘误留痕：本次首轮用 `python ... | tail -20; echo $?` 取退出码，拿到的是 `tail` 的 0 而非 python 的 1，误以为"FAIL 却 exit 0"。改为不经管道直取后确认退出码正确。记录此事以免其他成员复现同一测量错误。

---

## 5. 遗留（不在本冒烟范围）

| 项 | 说明 |
|---|---|
| `log_cannot_map` 的真实特征 | 未被验证（用合成日志）。真实 CubeMX 日志里 `Cannot map` 的行格式、是否带引号、是否多行，须在 S3 用真日志确认 |
| `syscalls_path` 的真实特征 | 同上 |
| `.mx` 脚本盘符绝对路径 | 核验器**未覆盖**（已单独报 verifier-dev）：本仓 `scripts/cubemx-init.mx` 写死 `project path D:\Projects\GitHub\HUSTRadio\stm32-digital-clock`，而 `.mxproject` 干净 → 核验器全 PASS，属真实漏检 |

---

**验证等级声明**：L1（静态冒烟，只读调用被测脚本 + 人工判读输出）。未涉构建、未涉硬件。
