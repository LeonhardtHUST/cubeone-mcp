# 决策记录（DECISIONS）

> **owner：`team-lead`（platform-lead）**。本文件是执行期决策的唯一真源，与 `docs/TASKBOARD.md` 配合使用。
> 规则：只追加不删改历史条目；决策被推翻时新增一条并注明推翻哪条。

---

## 一、GATE-D 六项决策（Phase 0 开工前置）

确认时间：**2026-11-03** · 确认方式：`AskUserQuestion`（lead 向用户发起）· 用户结论：**全部采纳推荐值**

| 编号 | 决策 | 用户确认值 | 确认时间 | 影响的下游任务 |
|---|---|---|---|---|
| D1 | CubeMX 版本是否锁 6.18.1 | **是**。MVP 与全部生成流程锁 `C:\ST\STM32CubeMX\STM32CubeMX.exe`（6.18.1 / DB.6.0.181）；CubeMX2 1.1.1 不进 MVP，仅作 T3.4 评估对象 | 2026-11-03 | 全部生成流程、T3.4 |
| D2 | platformio.mcp 是否用外部包 | **是**，装 `platformio.mcp` 作主力；同时保留 `pio` CLI 回退通道，脚本不得只依赖 MCP 一条路 | 2026-11-03 | T0.2、T0.3、Phase 1 构建 |
| D3 | CMake 流是否砍出 MVP | **是，砍出 MVP**。CMake 流降级为 Phase 3 选做评估（T3.4 第 ② 项），MVP 只走 PlatformIO 单流 | 2026-11-03 | T3.4、G5 |
| D4 | FW_H7 何时装 | **推迟到接板日**（Phase 2 顺手装）。本次会话无板，T2.2 一并挂起；H723 模板本次不跑生成/构建 | 2026-11-03 | T2.2、G4 |
| D5 | GitHub remote 是否现在建 | **是，现在建**；可见性 **Public**（与三个 `template-mcu-*` 模板仓一致，便于分享与 Actions 额度） | 2026-11-03 | T1.1、T3.5 |
| D6 | 烧录默认探针 ST-Link/SWD | **是**，默认 ST-Link/SWD；X Pulse 板探针类型待接板日现场确认 | 2026-11-03 | T2.1 |

### 由 GATE-D 连带确认的范围收敛

| 编号 | 决策 | 值 | 理由 |
|---|---|---|---|
| D5-a | `platform32-mcp` 仓库可见性 | **Public** | 用户选定；`gh` 已登录 `LeonhardtHUST`，scopes 含 `repo`/`workflow`，git 走 ssh |
| D7 | 本次会话是否执行 Phase 2（烧录/串口） | **不执行，整体后移** | 用户确认"暂未接板"。T2.1–T2.6 全部挂起至 GATE-2.0 接板日；本次只做 Phase 0 / Phase 1 / Phase 3 中不依赖硬件的部分 |

---

## 二、执行期新增决策（lead 裁决）

### D8 · `docs/logs/` 的入库策略：文本日志入库，二进制产物忽略

- **背景**：T1.1 初版 `.gitignore` 把 `docs/logs/*` 整体忽略（仅留 `.gitkeep`）。但计划 §0.2-2/§5.2 要求"证据一律落盘、路径写进 TASKBOARD"，而 TASKBOARD 是 Public 仓库里的交接真源——若日志不入库，换人/换机后证据链直接断裂，DoD 的"证据落盘"无法被外部核验。
- **决策**：改为"局部忽略"——`docs/logs/` 下的**文本证据**（`.log`/`.txt`/`.json`/`.md`）入库；**二进制与大件产物**（`.elf` `.bin` `.hex` `.map` `.zip`）忽略。
- **理由**：文本日志体积极小（KB 级），是 L0–L5 声明的唯一可核验凭据；二进制产物既大又能由源码重建，无入库价值。
- **影响**：`.gitignore` 第 11–15 行区块改写（owner 见计划 §2.1：`.gitignore` 归 lead）。
- **确认人**：lead（技术裁决，非用户资产，无需 GATE）

### D9 · `template-mcu-STM32F103C8T6` 的 2 处既有脏改动：认定为本项目开工前既有状态

- **事实**：`M .vscode/extensions.json`、`M .vscode/launch.json`。两文件 mtime 均为 **2026-10-15 16:25**，早于本项目首次提交（2026-11-03 11:17）与本次任何操作。
- **决策**：认定为本项目开工前的既有状态，**不是本次执行造成**；本项目所有成员对该仓只做只读操作。
- **例外处理**：`.vscode/` 属编辑器配置、与固件无关，不构成"原仓被误改"（计划 §5.3 风险项）。验收时以"是否有 mtime 晚于 2026-11-03 11:00 的改动"作为判据，而非"是否绝对干净"。
- **影响**：G474 / H723 / NUEDC_2027 三仓基线仍要求 0 脏项。

### D10 · `docs/backups/mcp.json.bak-*` 的归属与入库

- **背景**：T0.2 DoD 要求"改前备份 mcp.json 到仓内 `docs/backups/`"，但该目录由 env-agent 产出，`.gitignore` 归 skill-author，出现双 owner 缝隙（skill-author 已按单写者原则拒绝代提交）。
- **决策**：`docs/backups/` **入库**（是个人配置的可审计快照，且已脱敏：备份仅含 server 定义，含少量既有 token，故**不推送到远端前须复核**）。提交由 `platform-lead` 在 GATE-0 通过后统一执行，避免 env-agent 与 skill-author 各改一半。
- **待办**：备份文件中含现有 MCP 条目的 token（penpot/siyuan/lighthouse）。**入库前必须脱敏**，否则 Public 仓库泄露凭据 → 见 D11。

### D11 · `mcp.json` 备份的脱敏规则（安全红线）

- **事实**：现 `mcp.json` 含 `siyuan` 的 `Authorization: Token ...`、`penpot-official-mcp` 的 `userToken=`、`penpot-api` 的 `PENPOT_ACCESS_TOKEN`。
- **决策**：入库到 Public 仓库的备份**必须**把所有 `token`/`Authorization`/`*_TOKEN` 值替换为 `***REDACTED***`；原始未脱敏备份只留本机 `docs/backups/`（被 `.gitignore` 忽略，另建 `docs/backups/*.raw.json` 规则）。
- **影响**：`.gitignore` 增加 `docs/backups/*.raw.json`；已生成的 `mcp.json.bak-20261103-114836` 需复核是否含明文凭据，含则改名加 `.raw` 后缀后不入库，另出脱敏版。

### D12 · **T0.2 不执行写入**：`mcp.json` 保持原样，注册指引降级为文档交付

- **背景**：lead 在 GATE-0 向用户出示 diff 请求授权写入 `C:\Users\Leon\.workbuddy\mcp.json`，用户明确否决并界定项目范围：**"我在让你开发 platform32-mcp，不是让你帮我装 mcp+skills 能力工具链。"**
- **决策**：`~/.workbuddy/mcp.json` **一个字节都不改**（env-agent 已复核 sha256 与改前一致）。
  - T0.2 的任务性质从"应用配置"改为"**产出一份可复现的注册指引**" → `docs/guides/mcp-registration.md`
  - env-agent 已实测的握手证据（两个 server 能真实拉起、platformio 40 工具 / cube 9 工具）保留，作为指引里的"可复现验证"章节，不再是配置生效的证明
  - T0.4 冒烟测试的证据等级如实标注为 **CLI 通道 / 独立进程握手**，不宣称"MCP 客户端已可用"
- **理由**：本项目的交付物是仓库本体（Skill + 核验脚本 + 文档 + CI），目标读者自己决定是否注册工具链。改用户全局配置既非交付内容，也有跨项目副作用（该文件被 penpot / siyuan / rea / lighthouse-ops 等 8 个项目共用）。
- **影响**：
  - Phase 0 验收口径变更：从"三个 server 在客户端可见"改为"**两个 server 可被独立拉起且工具清单与文档一致**（L1）+ 注册步骤成文"
  - Phase 1 全部场景改走 **CLI 等价通道**（`java -jar STM32CubeMX.exe -q` / `pio.exe`），SKILL.md 必须给出双通道写法，不能只写 MCP 调用
  - T3.5 发布说明中的验证等级汇总表，MCP 工具面一律标 L1（未在客户端实测）
- **确认人**：用户（2026-11-03，GATE-0 问询中直接裁定）

### D13 · `.ioc` 版本戳与锁定版本不一致时，噪音 diff 必须拆独立提交

- **事实**：`stm32-digital-clock` 的 `.ioc` 版本戳为 `6.17.0`（共 5 处），本机 CubeMX 锁 6.18.1（D1）。重新生成会产生 **619 增 / 106 删**的整文件重写，而真实功能改动可能只有 9 增 / 1 删。
- **决策**：① 核验器新增 `ioc_version_stamp`（warning 级）提示版本漂移；② 若必须重生成，**版本归一产生的噪音 diff 必须单独成一个 `chore(ioc):` 提交**，不得与功能改动混提交（AGENTS.md §1.4 原子性硬约束）；③ 写进 SKILL.md 陷阱清单（P2）。
- **影响**：S1/S2 场景的 diff 汇报必须能区分"版本噪音"与"功能改动"。

### D14 · Flash/RAM 数字口径：以链接器为准，不用 PlatformIO 内置 size

- **事实**：`stm32-digital-clock` 实测 PIO 内置 size 报 `RAM 3180 B (3.1%)`，链接器 `--print-memory-usage` 报 `RAM 4720 B (4.6%)`，**差 1540 B** —— 恰为 `.ioc` 的 stack 1024 + heap 512。
- **决策**：本项目所有 L3 证据中的尺寸数字，**一律取链接器 `--print-memory-usage` 或 `.bin` 实际字节**；引用 PIO 内置 size 时必须注明"未计入 stack/heap 预留，不可直接对比"。
- **影响**：T1.6/S1、T3.1 CI 产物说明、SKILL.md §3 判据全部按此口径。

### D15 · `testbeds/` 允许"只读镜像"未提交工作区，但必须可证明保真

- **背景**：`stm32-digital-clock` 原仓 `HEAD` 里的 `.ioc` 是 92 行空壳（`Mcu.IPNb=3`、无 SPI），真实工程只存在于工作区（13 项未提交 + 5 个未跟踪文件）。直接克隆等于审计一个不存在的工程。
- **决策**：允许把工作区状态**镜像**进 testbed（导出 diff → apply → 补未跟踪文件），但必须同时满足：① 原仓 `git status` / `.git/index` mtime / 各文件 SHA256 前后一致；② testbed 与原工作区 **逐文件 SHA256 全等**；③ 镜像动作在报告中显式声明（不得静默）。
- **理由**：这是"保真审计"，不是篡改；且原仓零改动。
- **影响**：S2 报告已按此标注；后续任何 testbed 初始化沿用同一判据。

### D16 · 核验器契约冻结为 **v1.1 = 7 个 check id**，并显式声明保证边界

- **背景**：v1.0.0 只有 5 项；执行期先后发现两类真实漏检，追加后定为 7 项，**并就此冻结**（后续新想法进 v1.2，不进 S1 证据链）。
- **7 项清单**：
  `log_cannot_map` / `main_init_present` / `main_init_called` / `mxproject_abs_path` / `syscalls_path`(blocking=false) / `mx_script_abs_path` / `pins_present`
- **显式否决的三项**（曾提议、未采纳）：
  - `ioc_ask_for_migrate` → 架构位置错误：核验器在**生成之后**才跑，而它的风险发生在生成时。改由 `regen.sh` 只告警（见 D19）。
  - `ioc_version_stamp` → 提交卫生问题，非正确性门。归 SKILL.md 陷阱 P2 + `regen.sh` 一行 warn。
  - 参数级漏配检测（如 `Prescaler` 未进 `IPParameters`）→ **v2 的 Known limitation**，v1 不承诺。
- **保证边界（必须写进文档与 SKILL.md）**：v1.1 保证"**外设级 + （传 `--expect-pins` 时）引脚级**"不漏；**不保证参数级**。使用者不得把"核验 PASS"理解为"参数全对"。
- **理由**：核验器的价值等于"误报率 × 漏报率"的乘积。一项会在合规工程上误报的检查（`mx_script_abs_path` 的初版）会让人整体忽略核验结果，比不加更糟。

### D17 · `level` 字段改名 `blocking: bool`

- **事实**：`level` 由 `status` 派生（`warn`/`skip` → `warning`，其余 → `error`），导致 `status: pass` 的检查也显示 `level: "error"`。实测 `regen-success/verify.json` 中 5 项全 pass、`level` 全为 `error`。
- **决策**：改名 `blocking`（布尔），语义为"该检查失败时是否阻塞"，与本次是否有问题无关。
- **理由**：pre-release、GATE-1.1 未过，改名成本最低；发版后再改属破坏性变更。该缺陷由 `skill-author` 从真实 JSON 产物中发现。

### D18 · 硬禁令：`--log` 只接受 CubeMX 原始 stdout 重定向文件

- **事实**：`vscode-cube-mcp` 的 `NOISE_RE` 会过滤 `INFO`/`WARN`/`DEBUG`/`TRACE` 级别的日志行（`[ERROR]` 保留）。若 `Cannot map signal` 以 `WARN` 形态出现，它在 **MCP 返回文本里根本不存在**。
- **决策**：核验器的 `--log` **禁止**传入任何 MCP 工具返回值；只能传原始 stdout 重定向文件。CLI 通道必须自行重定向。
- **影响**：S3 负路径测试必须记录"日志从哪个通道获得"，否则假阴性能被误判为"核验器漏报"。SKILL.md §0.4 写成硬禁令 + 自检话术。

### D19 · `AskForMigrate` 裁决：不硬拦、不复位、单独出现不告警

- **背景**：一度计划"生成前发现 `AskForMigrate=true` 即退出 2"。被实测推翻：**CubeMX 每次生成后都会把它写回 `true`**，`true` 是生成后的**稳态**。按硬拦实现会让第一次生成成功后的所有后续生成被永久拦死。
- **决策**：单独出现 `true` → 不拦、不告警、不改文件、不文本注入。仅当 `.ioc` 的 `MxCube.Version` < 本机 CubeMX 版本（存在真实迁移需求）时打一条 warn。
- **证据状态**：**⚠️ 封版已撤销，见 D24。** 本条第一版（"生成后稳态"）与第二版（"已封版"）均被证伪。
- ⚠️ **第一版结论错误，已更正**：初稿写"`AskForMigrate=true` 是**生成后**稳态"，依据是"生成过的工程 = true"。这被反例否定 —— `testbeds/_verifier-regen/g474` **生成过两次**（`regen.sh` 的 success/rollback 实跑）却仍是 `false`。
- **正确结论（可直接引用）**：
  > `AskForMigrate=true` 是 **`config save` / `saveas` 之后的稳态**；纯 `project generate` **不改写 `.ioc`、不改变该值**（`regen.sh` 默认路径实测前后 sha256 逐字节相同）。`true` 单独出现不构成风险，不拦不改；真实风险仅当 `.ioc` 由更旧版 CubeMX 生成且需真实迁移时存在，此时仅告警。
- **5 例对照的真实归因**：
  | 观察 | 支持的结论 |
  |---|---|
  | 原仓 + 克隆副本 = `false`（从未跑过） | 模板提交值为 `false` |
  | `_s1-dryrun` 两例 = `true`（走过 `config saveas`） | **`saveas` 会写回 `true`** |
  | `_verifier-regen/g474` = `false`（只走 `project generate`） | **纯 generate 不写回** |
- **为什么措辞必须精确**：按"生成后稳态"写，只用 `regen.sh` 的人会看到 `false`，从而认为本决策是错的、进而怀疑其他决策。**错误结论比没有结论更有害。**
- **对使用者的排障提示（与因果结论分开表述）**：若真遇到 `-q` 长时间无输出且进程有 CPU 占用，先查 `.ioc` 的 `MxCube.Version` 是否低于本机版本；**这是排障建议，不是因果结论**。

### D20 · `regen.sh` 默认允许脏 `.ioc`；回滚只从备份恢复，不走 `git checkout`

- **事实**：`regen.sh` 的定位是"**改完 `.ioc` 之后**备份→生成→核验"，而原默认 `--require-clean` 会让标准路径 100% 撞 `rc=2`。"默认安全"实际等于"默认不可用"。
- **更危险的隐患**：若失败回滚走 `git checkout -- .ioc`，会**直接抹掉用户未提交的编辑**。现有实现从 `ioc_backup.py` 的备份恢复（`regen-rollback` 证据：回滚后 `.ioc` sha256 与生成前完全一致），此路径必须保持。
- **决策**：① 默认允许脏 `.ioc`，`--require-clean` 作为显式严格模式；② 默认路径必须打印 pre-existing 未提交改动清单 + 声明"从备份恢复，不用 git checkout"；③ 失败时额外打印 `git status --porcelain -- Core/` 与 `git checkout -- Core/` 提示，但**不自动回滚 `Core/`**（局部回滚更易看清生成动了什么）。

### D21 · `mx_script_abs_path` 必须是三态判定，不是"有盘符即 fail"

- **背景**：初版定为"`.mx` 含盘符绝对路径 → error"。被 `TEMPLATE-PLACEHOLDERS.md` A1 推翻：**CubeMX 脚本不支持变量，必须硬写绝对路径**，`__PROJECT_DIR__` 是模板有意留的占位符，替换后**本来就该是绝对路径**。按初版实现会在每个配置正确的副本上误报 fail。
- **决策（三态）**：占位符 `__[A-Z_]+__` 未替换 → `warn`；绝对路径归一化后 **== 工程根** → `pass`；**≠ 工程根** → `fail`。归一化含 `realpath` + 斜杠统一 + `casefold`。
- **该检查的真正语义（写进契约）**：不是查"有没有绝对路径"，而是查"**这份脚本在这台机器、这个位置还对不对**"。实证：`stm32-digital-clock/scripts/cubemx-init.mx:27` 写死 `D:\Projects\GitHub\HUSTRadio\...`，原机 pass、克隆到别处即 fail —— 生成会把代码写进另一个工程。

### D22 · `pins_present` 的立项理由：堵"真空 PASS"

- **事实**：在**完全未改动**的 G474 基线上传 `--expect GPIO`，核验器返回 `verdict=PASS / exit 0` —— 因为 `GPIO` 外设模板本来就有（PC13 在用 `MX_GPIO_Init`），而"加一个 PB0"是**已存在外设内部的引脚增量**，5 项外设级检查全部不变红。
- **与 `configure` 返回值叠加形成完美幻觉**：`cubemx_configure` 的 `ok=True` 仅等于 `returncode==0 且无整行 KO`（env-agent 源码实证）；静默失败不产生 `KO` → 返回成功 → 生成无错 → `MX_GPIO_Init` 存在 → **核验 PASS** → 用户以为改动生效，实际什么都没发生。
- **决策**：新增第 7 项 `pins_present`（`--expect-pins PB0=GPIO_Output`，可选，不传则 `skip`）：断言 `.ioc` 中 `<PIN>.Signal` 逐字匹配（大小写不敏感）**且** `main.c` 出现 `__HAL_RCC_<PORT>_CLK_ENABLE()`。
- **定位**：这是**产品级修复**，不是 S1 的场景取证技巧。S1 另需独立的 P1–P5 外部断言作为"这次生成对不对"的场景证据，两者不重复。

### D13 · `.ioc` 噪音 diff 有**两个独立成因**，必须分开归因、分开处理

- **成因 A（版本戳漂移）**：`.ioc` 由旧版 CubeMX 生成（如 `6.17.0`），本机为 6.18.1（D1）。重新生成会连带改写版本戳与大量键。
- **成因 B（`config save/saveas` 整体重写）**：**与版本无关**。只要走了 `config saveas`，CubeMX 就会重写整个 `.ioc`。实测：`scenario-tester` 的 S1 干跑里，8 个 `.ioc` 中只有 `Mcu.Pin1`/`Mcu.Pin2`/`Mcu.Pin5`/`Mcu.PinsNb` **四个键**是 CSP 语义变化，其余全是重排/重写噪音。
- **更正（原 D13 初稿把两者混为一谈，已修正）**：曾把"619 增 / 106 删"记作"版本漂移的产物"，**不准确**。该量级是 `stm32-digital-clock`（成因 A + B 叠加）的具体观测值，**不是阈值、不可跨工程套用**。`scenario-tester` 对此的判断正确。
- **决策**：
  1. 核验器不再单独出 `ioc_version_stamp` 检查（见 D16），版本信息归 `regen.sh` 一行 warn。
  2. **S1/S2/S3 的"diff 只含预期文件"判据必须用 `git diff --numstat -w`，禁止用 `git status`** —— 理由见 D23。
  3. 提交时成因 A 的噪音**必须**拆成独立 `chore(ioc):` 提交（AGENTS.md §1.4 原子性）；成因 B 无法拆分（saveas 不可控），须在提交正文写明"含 saveas 重写噪音"。

### D23 · 所有"文件是否被改动"的判定一律用 `git diff --numstat -w`，禁用 `git status`

- **事实（S1 干跑实测）**：`git status` 报 **8 个 M**，`git diff --numstat` 只有 **2 个非零**；`git ls-files --eol` 显示被报 M 的生成文件是 `w/crlf`。
- **根因**：`.gitattributes` 的 `* text=auto eol=lf` 让行尾在 `diff` 时归一化，但**工作区里 CubeMX 写入的是 CRLF** → `git status` 按 stat 判断为脏，`git diff` 归一化后为空。
- **决策**：本项目所有真伪判定（S1/S2/S3 的 diff 汇报、T1.6 验收、T3.1 CI 检查、`regen.sh` 的脏检测提示）统一使用 **`git diff HEAD --numstat -w`**；`git status` 只作为"有哪些文件被动过"的线索，不得作为证据。
- **⚠️ 基准必须是 `HEAD`（本条初稿的错误，已修正）**：省略基准时 `git diff --numstat -w` 比的是"**工作区 vs 索引**"，不是"工作区 vs HEAD"。S1 流程含 `git add`，一旦暂存，该命令会返回 **0 个文件**，真实改动被自己藏起来 —— 比 `git status` 假失败更危险（**假干净**）。
- **`-w` 的能力边界（必须写进文档）**：`-w` 只忽略**空白差异**（行尾、缩进、行内连续空白）。
  | 噪音成因 | `--numstat -w` 可见 |
  |---|---|
  | CRLF 行尾（本条要滤掉的） | ❌ 不可见（正是目的） |
  | 仅缩进变化 | ❌ **不可见（固有盲区）** |
  | 版本迁移重写（D13 修正后） | ✅ 可见 |
  | 真功能改动 | ✅ 可见 |
  ⇒ 正确表述是"**`numstat -w` 为 0 ⇒ 没有语义改动（可能只有行尾/缩进）**"，**不是"没有改动"**。
- **预置预期（写进 SKILL.md §2 第 7 步）**：按 `* text=auto eol=lf`，工作区是 CRLF、仓库是 LF，因此 `git status` 会**持续把生成文件列成 `M`，直到 `git add` 归一化索引**。⇒ **报 M 的文件数 ≠ 改动文件数**，前者是行尾策略的副作用。S1 使用者第一次看到"改了一个 GPIO，`git status` 报 8 个 M"会误以为 CubeMX 动了 8 个文件。
- **影响**：这是"diff 只含预期文件"这条 DoD 能否成立的前提。用 `git status` 会把 CRLF 噪音当成 6 个意外改动，导致假失败；用 `git diff` 又会把"仅行尾变化"当无变化。**两者单独用都会错。**

### D24 · 因果模型修正：推翻 D13 的「成因 B」与 D19 的「封版」

- **触发**：`env-agent` 对 `testbeds/` 下 6 个 `.ioc` 做了全量取证（含逐文件 mtime 排序），证据链完整可复核。
- **两次错误都源于同一个方法论问题**：把"某次观察到的事实"直接升级成"因果定律"，且没有检查反例。记录在此以免重犯。

#### 24.1 推翻 D19：`AskForMigrate` 是否阻塞 **仍未验证**

| 事实（已取证） | 结论 |
|---|---|
| 原仓 / `_verifier-regen` / 克隆副本 = `false`（只跑过 `project generate`） | **纯 generate 不写回** |
| `_s1-dryrun` 两例 = `true`（跑过 `config saveas`） | **`saveas` 写回 `true`**（原版 CubeMX 行为） |
| **`_s1-dryrun` 从未被 `-q` 加载过**（干跑后再没跑 generate） | **`true` 从未真正进入生成流程** |

⇒ `AskForMigrate=true` 是否会导致 `-q` 阻塞，**本文件第一版说"零证据"也不准确**（见下方更正）。D19 第二版"已封版"的依据（`_verifier-regen` 生成两次仍 `false`）同样不能作为反证——那两次根本没进过 `true` 状态。

- **⚠️ 第三版更正（2026-11-03，最终）**：
  | 观察 | 时间 | 生成时 `.ioc` 的 `AskForMigrate` | 结果 |
  |---|---|---|---|
  | `_s1-dryrun` 干跑（当时 `regen.sh` **无**前置拦截，拦截于 12:10 才加入） | 12:06 | **`true`** | **生成正常完成 48 s，未阻塞** |
  | S1 正式（先 A2 复位为 `false`） | 12:29 | `false` | 43 s 完成（**不能计入本议题**） |
  ⇒ **现有证据：1 例实测，`true` 状态下 `-q` 未阻塞。** 样本量 1，**不足以称"定律"，足以否定"必然阻塞"**。
  ⇒ **决策含义不变**：不拦、不改、不注入。因为「必然阻塞」这个前提已被这 1 例否定，而"为未证实的风险引入默认写操作/硬拦"的代价（永久拦死真实工程、报告与交付错位）依然成立。
  ⇒ **严禁把 S1 正式那次（43 s）当作本议题的证据** —— 它是在复位为 `false` 之后跑的。这一点必须写进报告与文档。

**当前裁决（保守）**：`regen.sh` 保持"只 warn 不中止"（不改 `.ioc` 是对的），但**文案必须写成"该值由 `saveas` 写回、是否阻塞未验证，若生成无输出请先查版本迁移"**，不得写成"不构成风险"。
**补证要求**：S1 必须记录"生成前 / 生成后"两个状态的 `AskForMigrate` 值 —— S1 走的就是 `config saveas` 路径，一次真实生成即可给出正证或反证。

#### 24.2 推翻 D13「成因 B」：整文件重写是**版本迁移**造成的，不是 `saveas`

| 工程 | `.ioc` 版本 | 生成路径 | 实测 diff |
|---|---|---|---|
| G474 模板（6.18.1） | 与锁一致 | `saveas` | `.ioc` **9/6**、`main.c` **11/0**、`.mxproject` **0** |
| `stm32-digital-clock` | 6.17.0 | `saveas` | **619/106** |

⇒ 两者都走了 `saveas`，diff 量差两个数量级。**唯一变量是版本匹配度。** D13 的"成因 B（saveas 整体重写，与版本无关）"**不成立，撤销**。
**修正后的模型**：`.ioc` 噪音**只有一个成因** —— **版本不匹配导致的迁移重写**。与 6.18.1 匹配的工程，`saveas` 只产生小范围语义 diff。

**为什么这条必须纠正**：按"成因 B 与版本无关"写，S1 的"diff 只含预期文件"判据就被自己论证成"永远做不到"——因为每个工程都会被认为必然有整文件重写。判据会因此失去约束力。`env-agent` 这点判断准确。

#### 24.3 `Mcu.PinsNb` 的实际行为（修正 D22 / S1 断言）

实测终态：`Mcu.PinsNb` **5 → 6**，**新增引脚被插入到 `Mcu.Pin1` 位置、原 1–5 整体后移**（`Mcu.Pin5=PB0` 这个断言是错的，已废弃）。

⇒ S1 断言改为**存在性 + 连续性**，不做位序断言：
- `Mcu.PinsNb == 变更前引脚数 + 新增引脚数`
- 存在 `^Mcu\.Pin\d+=<PIN>$` 且 `^<PIN>\.Signal=` 逐字匹配
- `Mcu.Pin1..Mcu.Pin<N>` 序列连续、无重复、无空洞

#### 24.4 两条新增的实测事实（写进契约与 SKILL.md）

- **`set pin` 不会自动补 `GPIOParameters`**（无需补）→ `.ioc` 里不会出现 `<PIN>.PinState=`，而 `main.c` 仍会生成 `HAL_GPIO_WritePin(..., GPIO_PIN_RESET)`（CubeMX 默认）。与 `TEMPLATE-PLACEHOLDERS.md` §3.5 的 PC13 实例一致。**这也解释了为什么 `pins_present` 不能承诺参数生效（D22 的保证边界成立）。**
- **`NoEcho` 行不落磁盘**：`syscalls.c` / `sysmem.c` 的叠加路径异常**只存在于 stdout**，`.ioc` 与源文件里都搜不到 → 只能靠 **stdout 正则**发现。**这是 D18（`--log` 必须用原始 stdout）的第二个独立理由**，比 `NOISE_RE` 那条更硬：即便不走 MCP，任何"只读文件"的核验也会错过它。

### D25 · 🔴 能力边界（最高优先级）：`configure`/CLI 透传通道**只能配普通 GPIO**

- **实测（`scenario-tester` 在丢弃副本上探测 4 种语法，全部记入 `docs/reports/t1.8-s3-prep.md`）**：

| 命令 | 回显 | `.ioc` 变化 | CubeMX 退出码 |
|---|---|---|---|
| `set pin PA0 S_TIM2_CH1_ETR` | **KO** | 无 | 0 |
| `set pin PA0-WKUP S_TIM2_CH1_ETR` | **KO** | 无 | 0 |
| `set ip parameters TIM2 InputCapture PA0-WKUP S_TIM2_CH1_ETR Prescaler 65535` | **OK** | **无变化** | 0 |
| `set pin PA1 USART2_TX` | **KO** | 无 | 0 |
| `set pin PB0 GPIO_Output` | OK | **有变化** | 0 |

- **三条结论**：
  1. **`set pin <PIN> <外设信号>` 一律 `KO`** —— 透传通道**只能配普通 GPIO**，无法新增/改配 UART / SPI / TIM / ADC 等外设。
  2. **`set ip parameters ...` 返回 `OK` 但 `.ioc` 一字未变** —— 这是最危险的形态：**静默空操作**。任何"看返回值判成功"的逻辑都会被骗。根因与 env-agent 的源码结论一致：TIM 伪命令只被 `cubemx_new_project` 调用，纯透传路径无人处理。
  3. **CubeMX 进程退出码恒为 0**，即使回显 `KO` 也返回 0。⇒ **判据只能是回显行 + 生成物，绝不能是退出码或 `ok=True`。**
- **对产品定位的修正（必须体现到 `SKILL.md` §0 / `README`）**：
  > `platform32-mcp` 能**可靠代做**的是**普通 GPIO 级改动**（新增/改模式/改上下拉）。
  > **非 GPIO 外设（UART/SPI/TIM/ADC…）的增改，本工具链不代做** —— 必须走"手改 `.ioc` 文本（含 `Mcu.IP*`/`IPParameters` 白名单/虚拟引脚三类键）+ G1 强制核验"或 GUI。
  > **`G1` 核验器因此不是辅助工具，而是非 GPIO 改动路径上唯一的安全网** —— 这正是本项目的立项理由。
- **为什么必须写进文档而不是只留在报告里**：使用者最可能的第一诉求就是"给我加一路串口"。若不写明，他们会用 `configure` 得到 `OK`、生成无错、核验 PASS（外设级检查对"整段外设缺失"之外静默无感），然后上线一个没有串口的固件。
- **对 S1/S3 的影响**：S1 选 GPIO 是对的（唯一可行路径）；S3 改用**文本编辑 `.ioc`** 注入（更贴 `TEMPLATE-PLACEHOLDERS` D3–D5 的警示主题，也更接近真实用户的失败方式）。

### D26 · 封装事实更正：STM32G474**VE**T6 是 **LQFP100**

- **背景**：lead 在沟通中曾把 Penguins-G474 说成 LQFP64（"VET6 是 64 脚"）。**错的。**
- **事实**：STM32 命名中 `R`=64 / `C`=48 / `V`=100 / `Z`=144。`.ioc` 实测 `Mcu.CPN=STM32G474VET6`、`Mcu.Package=LQFP100`；板级文档引脚列到 `PF0/PF1`（HSE），而 **PF 口只在 100 脚以上封装存在**。
- **影响**：模板目标芯片与 Penguins-G474 **同型号同封装**（G474VET6 / LQFP100）。⇒ **不存在"模板与实板封装不同、需另做板级适配"的问题**，接板日 S4 不必为此走弯路。
- **S1 选 PB0 的理由不变**（避开 PC13/PC15/RCC/PF 等板级特殊功能），但**不是因为封装不同**。该错误说法未写入本文件，仅在此留痕以免复述。

### D27 · S1 场景验收结论（L4 + L3，证据已固定版本）

- **证据版本**：`b5abde7`（lead 已代为 push）。证据目录 `docs/logs/phase1/s1-*`、报告 `docs/reports/t1.6-s1-report.md`。
- **lead 独立复核结果**（不采信成员报告，直接读产物）：

| 判据 | 实测 | 判定 |
|---|---|---|
| `verify.json` | `schema=/2`、`verdict=pass`、`errors=0 warnings=1`、6 项 | ✅ L4 |
| 唯一 warn | `mx_script_abs_path`：`scripts/cubemx-init.mx:5 __PROJECT_DIR__` | ✅ **正是 D21 预期的 1 条** |
| `pio run` | **SUCCESS / 12.06 s / 0 告警** | ✅ L3 |
| FLASH（链接器） | 3744 → **3792 B**（`text 3772 + data 20`），+48 B | ✅ 与干跑预期一致 |
| RAM | 1584 → **1584 B**，±0 | ✅ 与"GPIO 配置是栈上局部"一致 |
| `git diff HEAD --numstat -w` | `Core/Src/main.c 11/0`、`.ioc 8/5`，**仅 2 个文件** | ✅ 无越界 |
| `Mcu.IPNb` | **3（未变）**；`Mcu.PinsNb` 5→6 | ✅ 无越界 |
| `main.c` 实质改动 | 仅 `__HAL_RCC_GPIOB_CLK_ENABLE` + `HAL_GPIO_WritePin` + `HAL_GPIO_Init(GPIOB)` | ✅ 9 行，USER CODE 区未动 |
| `USER CODE` 块 | **0 处被触碰** | ✅ |

- **DoD 降级声明（已写进报告，不得删）**：核验 6 项 + P1–P7 外部断言；**引脚级由场景断言承担，产品路径（`--expect-pins`）计划 v1.2**；**不宣称"产品已覆盖引脚级"**。
- **口径说明（新增，防误引）**：`arm-none-eabi-size` 的 `data/bss` 与链接器 `--print-memory-usage` 的计数口径不同（前者 20/1572，后者合计 1584）。**引用时必须写明口径**，两者不可混用。

### D28 · 全量重建会触发"批量删除保护"，改用独立构建目录规避

- **实测现象**：CubeMX 生成把 `Core/Inc/stm32g4xx_hal_conf.h` 改写成 CRLF → SCons 判定 HAL 全部依赖失效 → 全量重编 → **删除第 50 个旧 `.o` 时触发运行环境的 safe-delete 批量阈值** → 进程挂起等待人工确认（S1 第 1 次构建卡 5m50s 后被 kill）。
- **对照证据**：11:59 基线构建、12:08 干跑构建（两者都是**空 `.pio` 全量构建、零删除**）日志中 `safe-delete` 命中 **0 次**。
- **规避（已验证）**：`PLATFORMIO_BUILD_DIR=.pio/build-s1` 用全新构建目录 → **零删除 → 12.06 s 完成**。属从头全量构建，对 L3 **等价或更强**（排除增量缓存干扰），且不改变 `git diff` 面。
- **决策**：
  1. **不要用 `rm -rf .pio` 清库**；需要干净重建用 `pio run -t clean`，或直接换 `PLATFORMIO_BUILD_DIR`。
  2. 该约束**属于 agent 运行环境的删除保护，不是 CubeMX/PlatformIO/模板的缺陷** —— 写进 SKILL.md 时必须这样归因，否则会误导使用者去改工具链。
  3. 传播面：`hil-agent` 接板日、`ci-agent` 的 Actions 也会遇到同类"改头文件后全量重编"，CI 上无此保护但会重复耗费时间，建议 CI 直接每次全新目录。
- **影响**：SKILL.md §2 第 6 步（构建）必须加这条规避方式；T3.1 CI 设计采用独立构建目录。

### D29 · S3 结果 + `NOISE_RE` 源码实证：D18 从"卫生规则"升级为"正确性红线"

#### 29.1 `NOISE_RE` 的真实定义（lead 直接读源码确认，非转述）

`C:\Users\Leon\AppData\Roaming\uv\tools\vscode-cube-mcp\Lib\site-packages\cubemx_mcp.py:72-77`：
```python
NOISE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[(INFO|WARN|DEBUG|TRACE)\]|"
    r"^(Picked up|log4j[: ]|[A-Z][a-z]{2} \d{2}, \d{4} \d{1,2}:\d{2}:\d{2} (AM|PM)|"
    r"WARNING: Could not open|Configure log4j|Cannot load)",
    re.MULTILINE,
)
```
**关键点：级别集合包含 `INFO`，不包含 `ERROR`。**

#### 29.2 `Cannot map` 的级别实测为 `[INFO]`（S3 唯一真实样本）

`scenario-tester` 在 S3 中用 `.ioc` 文本注入坏信号名，拿到真实样本（**唯一一例，圆括号包裹、无双引号**）：
```
2026-11-03 12:33:47,866 [INFO] ImportTextPane:234 - (OptionalMessage_ERROR) Cannot map signal (VP_TIM4_VS_ClockSourceINT) on pin (VP_TIM4_VS_ClockSourceINT)
```
⚠️ 三个要点：**级别是 `[INFO]`**；**信号名在圆括号内、且原文里含字面量 `signal`**；**不是行首 `Cannot map`**。

> **⚠️ 记录更正（lead 自纠）**：本文件曾出现两条**并不存在**的证据 —— "带双引号的样本 `Cannot map \"S_TIM3_CH1_ETR\" on pin PB4`" 与 "(a2) 脱 `Mcu.PinN` 触发 `IndexOutOfBoundsException`"。经 `scenario-tester` 明确否认，**这两项不是它产出的，也没有对应的实验记录**；是 lead 在转述时误把不同来源/推测混进了事实栏。**已删除，不得再引用。** 教训：lead 汇总时也必须注明每条事实的**产出者与证据路径**，不能只写结论。

#### 29.3 ⇒ 结论：走 MCP 通道会 **100% 假阴性**

把 29.1 与 29.2 相乘：`[INFO]` 行会被 `NOISE_RE` **整行删除** → 从 MCP 返回值里**永远看不到 `Cannot map`** → `log_cannot_map` 恒为 `pass` → 核验假阴性。

**这把 D18 从"文档卫生"升级为正确性红线**：`--log` 只能喂 CubeMX 原始 stdout 重定向文件；喂 MCP 返回值等于主动关闭 D5 守卫。
**同时纠正一处错误判断**：曾有一份报告写"级别是 `[INFO]` 而非 `[WARN]`，所以 `NOISE_RE` 不会吞掉 `Cannot map`" —— **正好相反**，`INFO` 与 `WARN` 同在过滤集合内。该结论已作废。

#### 29.4 S3 的另一个重要结论：D5 / H-6 必须拆成两层

| 层 | 症状 | 日志 | 谁抓得住 |
|---|---|---|---|
| **参数级静默忽略** | 信号进了 `.ioc`，但参数未进白名单 → 参数不生效 | **有 `Cannot map`** | `log_cannot_map` |
| **外设级静默丢弃** | 整个外设未落地 → `MX_xxx_Init` 不存在 | **日志干净** | 只有 `main_init_present` |

⇒ 二者**不可互相替代**。此前把 D5 当成单一失败模式，导致"有了日志检查就够了"的错觉。SKILL.md 的陷阱表必须分两行写。

#### 29.5 `log_cannot_map` 的有效样本数与定位
- 真实样本：**仅 1 例**（S3-A 圆括号形态），已可校准解析。
- 定位：**D5 参数级守卫**，不是高频命中项。S3(a) 已裁决**不做**（样本数 1→2 不改变任何结论）。

#### 29.6 🔴 由真实样本暴露的**核验器真 bug**（必修，优先于冻结）

`scenario-tester` 在核对正则时发现：`detail` 里写 `L321: signal ← …` 不是截断，**是真的把字面量 `signal` 当成了信号名**。

| 输入 | `_QUOTED_SIGNAL_RE` | `_BARE_SIGNAL_RE` |
|---|---|---|
| `Cannot map signal (VP_TIM4_VS_ClockSourceINT) on pin (…)`（真实形态） | `None` | **`'signal'`** ❌ |
| `Cannot map "S_TIM3_CH1_ETR" on pin PB4` | ✅ | `None` |
| `Cannot map signal S_TIM3_CH1_ETR on pin PB4` | `None` | ✅ |

- **根因**：`(?:signal\s+)?` 吃掉 `signal ` 后，`([A-Za-z0-9_]+)` 撞上 `(` 失败 → 正则回溯 → 可选组匹配空 → 捕获到字面量 `signal`。
- **危害（双向）**：
  1. 把已知噪音信号加进 `--allow-signal` → **永远匹配不上** → **假 FAIL**；
  2. 若有人把 `signal` 加进白名单（看着无害）→ **所有圆括号形态被静默放行** → **假 PASS，D5 守卫被绕过**。
- **决策**：冻结前必修。圆括号形态做独立分支，并显式排除字面量 `signal` 作为候选。补三条测试（对应上表三行）。
- **不受影响的结论**：S3(b) 本就应 FAIL（属"错得碰巧对"），S1 日志无 `Cannot map` —— 故 S1/S3 判定不变，但**白名单能力在修复前不可用**。

### D30 · 更正：`--ioc` **必须存在**（我下过一条自相矛盾的删除指令）；保证边界应为三段式

#### 30.1 `--ioc` 的反复：错在 lead，不在实现
- **经过**：v1.1 阶段（尚无 `pins_present`）我判定"7 项里没有消费 `.ioc` 的检查"，下令删除 `--ioc`/`inputs.ioc`；随后又批准新增 `pins_present`——而它**必须读 `.ioc` 的 `<PIN>.Signal`**。两条指令互相矛盾。
- **现状（正确）**：`verify_generation.py --help` 含 `--ioc IOC`，说明为"引脚级检查读 `<PIN>.Signal` 用；配 `--expect-pins`，不传则该项 skip"。
- **记录方式**：D16 的 7 项清单不变；本条目只更正"`--ioc` 不存在"这一错误说法（该说法出自 lead 的冻结版事实表，未写入本文件其他条目）。
- **教训**：**删除一个参数的判据必须是"没有消费者"，而不是"当前没有消费者"**。批准新检查时必须回查它依赖哪些已删参数。

#### 30.2 保证边界改为**三段式**（采纳 `skill-author` 的表述，取代我原来的两段式）
1. **v1.x 无条件下保证**：外设级——`MX_<IP>_Init()` 有定义且被调用，`syscalls` 叠加路径异常可观测。
2. **v1.x 有条件保证**：引脚级——**仅当调用方显式传 `--expect-pins <PIN>=<SIGNAL>`** 时成立；不传则 `skip`，**不冒充通过**。
3. **v1.x 明确不保证**：参数级与 `.ioc` 内部计数/排序自洽（如 `Prescaler` 是否进 `IPParameters`、`Mcu.PinsNb` 是否 +1）——v2 的 Known limitation。

- **理由**：两段式的"引脚级"会让人以为"跑一次就有"，而实际需要声明期望引脚。三段式把"条件"显式化，使用者在报告里就能看出自己拿的是哪一档。

---

## 后续决策追加区

> 每个新决策按 `D12`、`D13`… 递增追加，写清"决策 / 理由 / 影响 / 谁确认 / 何时"。
