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
| D5-a | `cubeone-mcp` 仓库可见性 | **Public** | 用户选定；`gh` 已登录 `LeonhardtHUST`，scopes 含 `repo`/`workflow`，git 走 ssh |
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

- **背景**：lead 在 GATE-0 向用户出示 diff 请求授权写入 `C:\Users\Leon\.workbuddy\mcp.json`，用户明确否决并界定项目范围：**"我在让你开发 cubeone-mcp，不是让你帮我装 mcp+skills 能力工具链。"**
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
  > `cubeone-mcp` 能**可靠代做**的是**普通 GPIO 级改动**（新增/改模式/改上下拉）。
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

### D31 · MCP 工具失败时 `isError` 为 `False`——"返回值说成功、实际失败"第三例（实测）

#### 31.1 实测证据（lead 直连 MCP server 探针，非转述）

构造：在 `ALLOWED_ROOTS` 内放一个**存在、后缀 `.ioc`、内容为垃圾**的文件，`ST_CUBEMX_TIMEOUT=25`，调用 `cubemx_load`。

```
elapsed_s     = 26.2 s          ← 被 25s 超时杀掉，说明期间一直卡着
isError       = False           ← 注意
text          = "[FAIL exit=None]\nTIMEOUT: CubeMX 子进程超过 25s 被终止(已强杀进程树)"
failed_by_text= True
judge_ok      = False           ← 仅当判据含文本检查时才为 False
```

⇒ **`ok = not is_error` 会把一次彻底失败的调用判成"通过"。** 这是本项目抓到的第三例同型缺陷：
1. `set ip parameters` 回 `OK` 但 `.ioc` 一字未改（D25）
2. `git status` 报 8 个改动、实际 2 个（D22）
3. **本条：`isError=False` 但工具没成功**

#### 31.2 根因：CubeMX 对无效 `.ioc` 弹**模态对话框**

用户提供的截图显示：加载垃圾 `.ioc` 时 CubeMX 弹出 `Load Project — Not a valid ioc file — [OK]`。

- 无头 `-q` 跑到这里**不会返回**，而是挂在对话框上等人点 OK
- 直到 `ST_CUBEMX_TIMEOUT` 把进程树强杀 → `_run_script` 得 `exit_code=None`、`ok=False`
- 但 server 仍**以正常字符串返回** `"[FAIL exit=None]…"`，**不置 `isError`**

#### 31.3 决策

1. **`tools/mcp_smoke.py` 的判据必须改**：`ok = (not is_error) and not failed_by_text`，其中
   `failed_by_text = text.lstrip().startswith("[FAIL") or any(ln.strip() == "KO" for ln in text.splitlines())`。
   - `startswith("[FAIL")` 不用子串：成功是 `[OK exit=0]`
   - `KO` 只认**整行等于**（与 server 内部判据一致）
2. **任何消费 MCP 返回值的一方都不能只看 `isError`**。这条要写进 `references/capability-boundary.md` 与 `pitfalls.md`：**MCP 层的 `isError` 只覆盖参数校验类失败，不覆盖工具执行失败。**
3. 无效 `.ioc` 会导致 25–300s 阻塞，排障时先想到"是不是弹了对话框"，别当成"生成慢"。

#### 31.4 影响面（重要）
`cubemx_load` / `cubemx_configure` / `cubemx_generate` 失败时都走同一条 `return f"[{'OK' if r['ok'] else 'FAIL'} exit=…]"` 路径，**都不置 `isError`**。所以"看 isError 判成败"这个直觉在 vscode-cube-mcp 上整体不成立，不只是 `cubemx_load`。

### D32 · 项目更名为 `cubeone-mcp`，主分支 `main` → `master`

#### 32.1 变更
- 仓库名：`platform32-mcp` → **`cubeone-mcp`**
- 主分支：`main` → **`master`**（远端默认分支同步切换，旧 `main` 删除）
- CI 触发条件同步改为 `branches: [master]`

#### 32.2 `docs/logs/` 与 `docs/reports/` 一并改写（推翻本条的初版判断）
初版判断是"证据保持原样，因为它是某次运行的快照"。**这个判断被推翻了**，理由：

> 证据存在的目的是**将来能查**。如果它指向的路径在改名后已不存在、仓库名也已作废，那它就从"证据"退化成"化石"——留着旧名反而让人无法定位产物，等于亲手让证据 stale。

所以：`docs/logs/`、`docs/reports/`、`.workbuddy/memory/` 里的旧名**全部机械改写**（67 个文件 / 446 处）。

改写不破坏任何已声明的指纹：
- 文档引用的是**脚本**哈希（`4fb474e9…`、`43e0641c…`）与 **`.ioc`** 哈希（`f57b1d33…`），不是日志文件自身的哈希
- 运行事实（耗时、`isError`、`VERDICT`、sha256 前后值）**一字未动**，只改路径与仓库名

需要追溯"当时到底叫什么"时，看 `a8c1621` 之前的 git 历史即可——**变更记录在版本库里，不该靠正文里的化石来保存**。

#### 32.3 影响
- 旧的 GitHub 地址会重定向到新仓库名（GitHub 自动行为），已有的 `git remote` 需手动更新（本仓已改为 HTTPS + `gh` 凭据）
- **本地克隆目录名仍是 `platform32-mcp`**：改名时被运行中的 IDE 占用（`Device or resource busy` / `item is in use`），Bash 与 PowerShell 两种方式均失败。需**关闭工作区后**手动执行：
  ```
  cd D:\Projects\GitHub
  mv platform32-mcp cubeone-mcp
  ```
  在改名完成前，证据里出现的 `D:\Projects\GitHub\cubeone-mcp\...` 是**按新名书写**的目标路径，本机尚未存在；换机克隆时按新名落地即自然一致
- 两个 release 的**标题与正文**已同步改为 `cubeone-mcp v0.1.x`（tag 名不变，tag 与仓库名无关）

---

## 后续决策追加区

> 每个新决策按 `D12`、`D13`… 递增追加，写清"决策 / 理由 / 影响 / 谁确认 / 何时"。

### D33 · 追溯认定 npm 工具通道为正式交付物形态，并固定版本轴治理

> 来源：修复计划 `docs/2026-11-03-remediation-plan.md` §1 R-G1（对应 `.workbuddy/audit/2026-11-03-审定报告.md` 的发现①，最高危项）

#### 33.1 追溯授权：产物先于授权存在，本条目补的是授权与记录

**写入时实测到的既有事实**（不是计划、不是意图）：

| 事实 | 证据 |
|---|---|
| `bin/cubeone-mcp.mjs`（stdio MCP 入口）+ `lib/server.mjs`（工具封装）已在库 | 入库 commit `3b99c27 feat(mcp): 新增 Node MCP server 薄封装三脚本，发布 npm 包 0.6.0` |
| `.github/workflows/publish.yml`（Trusted Publisher OIDC 发布流）已在库 | 入库 commit `78bfea9 ci(npm): Trusted Publisher OIDC 发布工作流` |
| npm 上 `cubeone-mcp` 已发布 **0.6.0、0.6.1** 两个正式版 | `npm view cubeone-mcp versions` → `["0.0.0-stage","0.6.0","0.6.1"]` |
| `package.json` 与 `SKILL.md` frontmatter 均为 `0.6.1`；tag 有 `v0.1.0`/`v0.1.1`/`v0.6.1` | 工作区实测 |

⇒ 这是**事后追认**：通道已经对外可用，本条不是"批准一件待做的事"，而是**认定一件已做的事**。

**必须同时记下的流程缺陷**：npm 化与 MCP 封装落地时**没有开任何用户决策门，`DECISIONS.md` 里也没有对应条目**。调研报告的结论是「本项目不是又一个 MCP server」，而推翻这个结论的动作没留下任何决策痕迹。

- **这是流程缺陷，不是技术缺陷。** 兼与 `D12` 张力：`D12` 把「不替用户装工具链」界定为项目范围约束，而「把 MCP server 发布到 npm」恰好擦这条边——越过它却一次都没问用户，是执行纪律问题，不是产物质量问题。
- 措辞上不写"经评估后决定"：形态从 `3b99c27` 起就是既成事实，缺的只是一张纸，把它写成"决策"是美化。

**追认理由（三条，均可核验）**：

1. **产物架构评级 A**（交付审定报告）。分层清楚：`bin/` 只做协议、`lib/` 只做封装、三个 Python 脚本保持零依赖。
2. **动态测评 94.1%**（同上）。工具面在真实调用下可用，不是只能 handshake。
3. **给 MCP 注册提供标准通道**：`npx`/`vpx` 一条命令即可被任意 MCP 客户端拉起。这是「Skill + 脚本 + 文档」形态**做不到**的分发能力——撤掉它等于收回已发出去且能用的通道，净收益为负。

**结论（方案 a）**：npm / MCP 工具通道**认定为正式交付物形态**，与「Skill + 脚本 + 文档」**并列**，不再算实验分支、不再算"顺手做的"。
**未被采纳的方案 b**（判定范围失控、冻结 npm 线、README 标 unmaintained、回归纯 Skill 形态）：会让已经 `npx cubeone-mcp` 用起来的人失去通道，且不能挽回任何已发生的成本。

#### 33.2 版本轴治理规则（随本条固化）

**单轴对外**：`git tag` = `package.json` = `SKILL.md` frontmatter，三处必须同值（例：`v0.6.2` / `0.6.2` / `0.6.2`）。
**例外：`verify_generation.py --version` 保持独立 1.x 轴**（判据契约演进，与包版本解耦）。

- 为什么核验器不并入单轴：它那个号是**契约号**（决定 `verify.json` 是 `schema /2` 还是别的形状），消费者靠它判断报告怎么解析。绑到包版本上，会让"只改了 README"也暗示契约变了。
- 代价要写明：单轴治理压掉的是"包内的三个号"（tag / `package.json` / frontmatter），对外仍是**两个实质版本轴**——**包版本**与**核验器契约号**。README「三个版本号，别混」那张表照旧维护，它列的是三个**位置**，不是三个轴；引用版本时必须写明是哪一轴。

**发布收口定义（硬规则）**：每次 tag 必须**同时**具备

1. **GitHub Release**（正文含验证等级汇总表）
2. **npm 发布**（Trusted Publisher 自动）
3. **看板回填**（`docs/TASKBOARD.md` 记录 tag / release / npm 三证）

**三者缺一 = 发布未收口**，不算完成。把"看板回填"写进规则而不是当习惯，是因为它现在是可机器校验的（M3 的 `tools/check_taskboard.py`，见 R-E1），不靠自觉。

#### 33.3 元规则：此后任何形态 / 技术栈 / 发布渠道变更必须先开 GATE

- **覆盖**：交付物形态（Skill / MCP server / CLI / 库）、技术栈（Node / Python / 其他）、发布渠道（npm / PyPI / GitHub Release / 其他）。**无论多小**。
- **流程**：先开 GATE（用户确认）→ 落一条 `DECISIONS` → 才允许合入。**缺一不得合入。**
- **本条是判例不是特例**：D33 自身之所以只能"追溯"，正是因为前两步没走。下一个想动形态的人，看这一条就知道成本在哪。
- 更宽的治理元规则（角色入册协议、L 等级降级须批准、节奏条款）归 M3 的 **D34**，本条只锁"形态变更必须开 GATE"这一根。

#### 33.4 `v0.6.1` 的发布缺口与处置

- **缺口（实测）**：`v0.6.1` 有 tag、npm 有 `0.6.1`，但 **GitHub Release 不存在**（`gh release list` 只有 `cubeone-mcp v0.1.1` / `cubeone-mcp v0.1.0`）。按 33.2 的判据，`v0.6.1` 属于**未收口**。
- **处置**：**随 0.6.2 发版一并补发 `v0.6.1` 的 release notes**——内容为该 tag 的变更摘要 + 验证等级声明，**独立成一条 release，不与 0.6.2 的正文合并**。补发完成前，`v0.6.1` 一直记为"未收口"。
- **为什么不立刻单独补**：单发一条没有新产物的 release 只增加噪音；0.6.2 是紧接的下一版（M1 批次），一次操作把两条线的账平掉更省事，且不会漏。
- 回填口径：M1 收口时 `TASKBOARD` 的 T3.5 行要同时挂出 `v0.6.1` 的 release 链接。

**33.4.1 补发结果与一次假红（2026-11-03 22:07 实测，如实记录）**

- **已完成**：`v0.6.1` Release 正文补发完毕（`gh release create v0.6.1`，正文入库 `docs/releases/2026-11-03-v0.6.1-backfill.md`）。至此 `v0.6.1` 三证齐全（tag `8f99fb0` / Release / npm `2026-11-03T12:08:52Z`）。
- **代价：`Publish npm` run `41650583470` 失败（红）。** 原因不是产物问题，而是**`release` 事件的 workflow 取自 tag 点，不是默认分支**：
  - 该 run 的 `head_sha = 8f99fb0`（`v0.6.1` tag 点），跑的是 **tag 上的旧 `publish.yml`**；
  - 旧版幂等检查是 `::error` + `exit 1`，于是「版本已存在」直接判红；
  - 本轮在默认分支新加的"跳过发布 + warning"守卫（commit `f830b55`）**对已有 tag 不生效**。
- **为什么不删掉这条 Release 换回绿灯**：删了等于把"未收口"还原回去，为了一条可解释的红灯而牺牲账目完整，方向反了。**红灯保留，原因写在这里**，并同时给出不再复发的机制（见下条）。
- **可推广的教训**：**tag 冻结的是 workflow 语义本身，不止代码**。任何对发布流水线的治理修复（守卫、跳过、权限），
  **都无法追溯影响旧 tag 的补发**。所以：① 治理修复必须在"下一次发版之前"落地（本轮 `f830b55` 早于 `v0.6.2` 吗？——晚于，但 0.6.2 是**正常发布**不触发幂等分支，故不受影响）；② 历史补发前先确认 tag 点上的 workflow 是否支持幂等跳过，否则预期一次假红。
- **对后续的约束**：`v0.6.2` 及以后的 tag 都带新守卫，补发同类正文不会再红；**若再次出现旧 tag 补发需求，先在本文件记一条"预期假红"再动手**。

#### 33.5 影响

- `README.md`「三个版本号，别混」表对齐 0.6.2 并引用本条（R-A3，本轮已做）。
- `SKILL.md` frontmatter 的 `0.6.2` bump 归 **M1 批次**；本轮 M0 只改文档，**不动 `SKILL.md`**（避免与 M1 的 bump 抢同一行）。
- `tools/check_taskboard.py`（M3 / R-E1）必须实现一致性规则：**`git tag` 含 `v0.6.x` 时 T3.5 不得为「待开始」**——防重复发布。
- 自 0.6.2 起，"发版完成"的判据从"打了 tag"升级为"**三证齐全 + 看板回填**"。

#### 33.6 谁确认 / 何时

- **确认人**：用户 **Leon**
- **时间**：**2026-11-03 21:13**（本地时间）
- **方式**：**会话内口头确认**，在方案 a / 方案 b 之间选定 **方案 a**（追溯认定）。未走 `AskUserQuestion` 表单——本条属修复计划 §1 的用户决策门 R-G1，用户在计划评审时直接裁定。
- **记录人**：`software-engineer`（M0 批次执行者），据用户裁定落盘。

### D34 · 形态演进与治理元规则（角色入册 / L 等级降级 / 节奏）

> 来源：修复计划 `docs/2026-11-03-remediation-plan.md` §4 R-E2（对应审定报告异议 1/4/5）
> 关系：D33 §33.3 管「形态变更必须先开 GATE」这一根；本条目管**其余治理面**（角色、等级、节奏、模板）。

#### 34.1 为什么要单独立一条"元规则"

M0–M2 三轮执行暴露出一个共同形态：**规则本身没被写下来，只活在当时那个人的记忆里**。
具体表现（都可核验，不是推测）：

| 事实 | 触发的问题 |
|---|---|
| `software-engineer` / `software-qa-engineer` / `release-engineer` 三个计划外角色实际在干活，但角色表里没有 | 审定异议 2：分不清谁有权改哪个文件 |
| T0.4 的判据在做完冒烟之后被升级（`ok = not isError` → `ok = (not isError) and not text_failed`），DoD 的 L 等级也随之变化，无人批准 | 审定异议 4：等级是"证据强度"，随手改等于自己给自己发证 |
| 计划预估 2–3 天的批次，实际半天内推进完 M0+M1 并继续往下做 | 审定异议 5：**进度超前时的默认动作是什么，没有规定** |

单条规则（如"要开 GATE"）解决不了这三件事，因为它们问的是**流程本身的元规则**。所以集中成一条。

#### 34.2 五条元规则（可执行，不是口号）

**(1) 形态变更元规则**
任何改变**交付物形态 / 技术栈 / 发布渠道**的演进，无论多小，先开 GATE（用户确认）+ 落 `DECISIONS`，
**缺一不得合入**。与 D33 §33.3 同源，本条不重复其判例，只强调适用范围不因"改动小"而收窄。

**(2) 角色入册协议**
- **计划外角色**：出场即登记，写进 `docs/TASKBOARD.md` §0.4.1，必须含**授权人**与**授权范围（可写哪些路径）**。
  不写范围的登记等于没登记——下次换人时无法判断他能不能改那个文件。
- **计划角色表**改**双列**（出场 / 未出场 + 原因）：未出场不等于漏排班，必须写清"为什么没他"（如 `hil-agent`
  专属任务全在 Phase 2，而本会话无硬件）。

**(3) L 等级降级须批准**
DoD 声明的 L 等级**下调**必须：lead 批准 + `DECISIONS` 条目 + 看板标注「原 Lx → 实 Ly」。
- 为什么只约束"降级"：升级（做了更多验证）不需要批准，降级是**放宽对证据的要求**，性质不同。
- 为什么必须写"原 Lx"：只写"实 Ly"等于抹掉历史，读者无法判断这条任务是"本来只要 L1"还是"本来要 L4 没做到"。
- 现存实例：M1 的 R-B2（`PYTHONIOENCODING`）在本机**造不出 cp936 分支**，属"验证对象不可达"，
  已在 TASKBOARD M1 行如实标注，不是降级而是**声明边界**——两者要分清。

**(4) 节奏条款**
进度超前时，**时间盈余默认归属"提前交付 + 加强验证"**（多跑一轮回归、补测试、补文档），
**不是**默认扩范围。要扩围（多做一项原本不在计划里的事）必须显式授权并留决策记录。
- 理由：审定异议 5 的根源是"趁快多做点"这一善意冲动——它让范围在没有授权的情况下膨胀，
  而膨胀后的东西没人验证过（M1 期间的 npm 化就是这样落地的，见 D33 §33.1 的流程缺陷记录）。
- 判据要可操作：**新增一件计划外的事**之前，先回答"它属于加强验证，还是扩范围？"
  后者就去开 GATE，不要自我批准。

**(5) 模板化**
后续 Phase 计划文档以此为准；**不回改**已交付的 `docs/2026-11-03-remediation-plan.md`，
需要时**追加勘误链接**而不是改原文。
- 理由（与 D32 §32.2 同一原理）：已交付的计划是某个时间点的判断快照，改写它会让"当时的判断"消失；
  勘误要能被看出是"后来补的"。

#### 34.3 影响

- `docs/TASKBOARD.md` §0.4 已成为角色登记的唯一落点（3 个计划外角色 + 8 个计划角色双列）。
- 本条的 (1)(2) 已可机器校验一半：`tools/check_taskboard.py` 校验快照/证据/发布三组一致性，
  但**角色入册与 L 等级降级仍靠人**——脚本读不出"这个人有没有授权"。如实记下这个边界，不假装全覆盖。
- 与 D33 §33.2 的关系：D33 管发布收口（tag/release/npm/看板四证），本条管**过程纪律**；两者不重叠。

#### 34.4 谁确认 / 何时

- **确认人**：用户 **Leon**（通过在计划评审时通过 `docs/2026-11-03-remediation-plan.md` §4 R-E2 授权落盘）
- **时间**：**2026-11-03**（计划通过时间；本条落盘于 M3 批次）
- **方式**：计划文档授权，**未逐条过目本条正文**——本条属治理机制，不改变交付物形态，故未单独开 GATE（依 34.2(1) 的适用范围）。
- **记录人**：`software-engineer`（M3 批次执行者）。

### D35 · 发布流程 SOP：把两次实跑固化成一条流水线

> 来源：完备计划 `docs/2026-11-04-engineering-completeness-plan.md` §4 C2.4
> 关系：D33 定**规则**（三证 + 版本轴同值 + 收口判据），本条定**动作顺序**——按 D33 做但没有顺序，仍会在"先打 tag 还是先补看板"上反复试错。

#### 35.1 为什么需要 SOP：0.6.2 与 0.7.0 的两次实跑并不同构

两次发版都成功了，但**顺序是每次现场推出来的**：

| 版本 | 差异点 | 代价 |
|---|---|---|
| `0.6.2` | 先把 npm 发出去、再补 GitHub Release 正文入库 | 正文有一段时间只存在于 GitHub 页面（`docs/releases/` 里是事后补的） |
| `0.7.0` | 先打 tag、再走 CI OIDC 发布；期间**push 被平台策略拦下一次** | 一度出现"tag 在本地、Release 与 npm 两证未产出"的中间态，看板只能记「进行中」 |

结论：**顺序不是风格问题，它决定了"中间态"长什么样**。把顺序写死，中间态就只有一个已知形态，
看板该记什么、别人接手该从哪一步续，都不需要现场推理。

#### 35.2 发布流水线（照抄执行，勿跳步）

| # | 步骤 | 命令 / 动作 | 产出证据 |
|---|---|---|---|
| 0 | **确认版本轴三处同值** | `node -p "require('./package.json').version"` + `grep -m1 '^version:' SKILL.md` + README 表两处 | 三条输出一致 |
| 1 | **本地四项自验** | `python -m pytest tests/ -q --basetemp=<干净目录>`（含覆盖率底线）· `node --test tests/node/*.test.mjs` · `node tools/npm_mcp_handshake.mjs --require-materials` · `npm pack --dry-run \| grep -E "guides/"` | 全绿 + 清单里指南在位 |
| 2 | **CI 全绿**（含 Windows job） | 等 `CI` workflow 全绿——**job 数以 `.github/workflows/ci.yml` 为准，当前 7 个**（`pytest×2`（3.11/3.13）/ `node×3`（18/20/22）/ `windows` / `脚本检查`）；**加删 job 时同批改本行**，否则这里又会变成一个对不上的旧数字 | run 链接 + 逐 job 结论 |
| 3 | **GATE-3.1 证据包** | 向用户出示：CI run + 本地自验 + 变更摘要（`git log --oneline <上tag>..HEAD`）+ 已知限制 + **BREAKING 与否** | 用户明确放行 |
| 4 | **打 tag** | `git tag -a vX.Y.Z -m "…"` → `git push origin vX.Y.Z`（若 push 被策略拦下：**停手报告，不自行重试**） | `git tag -l` 含新 tag |
| 5 | **GitHub Release** | 正文取自 `docs/releases/<日期>-vX.Y.Z.md`（**先入库，再发 Release**） | Release 页面 + 正文入库 commit |
| 6 | **npm 发布** | Trusted Publisher（`publish.yml`）或人工 `npm publish --registry "https://registry.npmjs.org/"`；发完确认 `dist-tags.latest` | `npm view cubeone-mcp dist-tags` |
| 7 | **看板回填**（**当场做**） | 该批次行 → 「已完成」+ 三证链接进证据列；§4 快照同步 | 见 35.3 坑② |
| 8 | **两道机器校验** | `python tools/check_taskboard.py` → `rc=0`；`python tools/check_release.py --network` → `rc=0` | 两条输出 |
| 9 | **npmmirror 同步**（可选，国内可见性） | `curl -X PUT https://registry.npmmirror.com/cubeone-mcp/sync` | 秒同步 |

**顺序里唯一不能交换的两对**：

- **4 必须在 5、6 之前**：Release 与 npm 都以 tag 为锚（`release` 事件的 workflow 取自 tag 点，见坑①）。
- **7 必须在 8 之前**：看板没回填时 `check_taskboard.py` 的判据③ 会红（tag 已存在而 T3.5/批次行未记账）。

#### 35.3 两个已踩的坑（别再踩）

**① `release` 事件的 workflow 取自 tag 点，不是取自默认分支的最新提交**

GitHub 在 `release` 事件里用的是**该 tag 指向的那个 commit** 上的 workflow 文件。所以：
tag 打得早、workflow 修得晚，发布时跑的就是**旧版** workflow。

- 实例：`v0.6.1` 补发 Release 时触发 `Publish npm` run `41650583470` 失败——tag 点 `8f99fb0`
  早于幂等守卫提交 `f830b55`，旧版 `::error` 判红。
- **处置**：保留红灯不删（删了等于抹掉历史），把根因记账。详见 **D33 §33.4.1**。
- **可操作推论**：**改过 `publish.yml` 的批次，必须让 workflow 修复先落进将要打 tag 的那个 commit**，
  否则 tag 一点下去就注定跑旧逻辑。

**② 发布后看板回填必须当场做，否则 `check_taskboard.py` 会红**

`tools/check_taskboard.py` 的判据③：`git tag` 里存在 `v0.6.*` / `v0.7.*` 时，`T3.5` 不得为「待开始」
（防"tag 打了但看板没记账"）。于是**发版是唯一会主动制造红灯的动作**：
tag 落地的瞬间，看板就从绿变红，直到批次行回填完成。

- 正确姿势：tag / Release / npm 三证拿到后，**同一次会话内**就回填看板并跑一遍脚本；
  不要"发完先去干别的"。中间态若确实要留（如 push 被拦），该行按 D33 §33.2 记「进行中」，
  **不得提前写「已完成」**。
- 反例形态：把 `check_taskboard.py` 从 CI 里摘掉来"解决"红灯——那是把温度计砸了。

#### 35.4 与 D33 / D34 的关系

- **D33** 管"什么算收口"（三证 + 版本轴同值 + 看板回填）；本条管"按什么顺序做"。
- **D34 §34.2(4)** 管"节奏"（时间盈余优先加强验证、不默认扩范围）；本条是它的下游：
  SOP 让"发版"这件事本身不再消耗判断力，盈余才能真的用在验证上。
- **机器化落点**：`tools/check_release.py`（C2.3）把步骤 0 与步骤 8 的一半交给机器；
  `tools/check_taskboard.py`（M3）管步骤 7 的另一半。两者都**只校验、不改写**。

#### 35.5 谁确认 / 何时

- **确认人**：用户 **Leon**（完备计划 §4 C2.4 授权"发布 SOP 成文"，随 C2 批次落盘）
- **时间**：**2026-11-04**
- **方式**：计划文档授权；本条不改变交付物形态、只固化已发生的两次实跑顺序，故未单独开 GATE（依 D34 §34.2(1)）。
- **记录人**：`software-engineer`（C2 批次执行者）。

#### 35.6 机器查 vs 人工核边界（A-22 / F-5，2026-11-04 追加）

D33 定「四证齐全」、35.2 定动作顺序，但**哪些能交给机器、哪些必须人核**此前没写清，
导致 `check_release.py` 只比本地版本轴、`--network` 的 dist-tags 不一致又只降级 WARN，
GATE-3.1 实质上全靠人。本条把边界钉死（**在 D35 内追加，不新增 D37**）。

**机器可查（`check_release.py --network`，发布后核证；不满足即 `rc≠0`）**

| 项 | 判据 | 落点 |
|---|---|---|
| 版本轴 | `tag` = `package.json` = `SKILL.md` frontmatter = README 两处，四处同值 | 判据① |
| tag | 最新 tag 可读且去掉 `v` 后等于目标版本 | `latest_tag()` |
| 发布正文 | `docs/releases/` 下有含该版本号的 `.md` | 判据② |
| npm `dist-tags` | **官方 registry**（`--registry "https://registry.npmjs.org/"`）的 `latest` == 目标版本 | `--network` 分支 |
| 台账回填 | `docs/releases/README.md` 表格里有该版本的台账行 | `ledger_has_version()` |
| 工作区 | `git status --porcelain` 为空 | `worktree_clean()` |

**机器可查（`check_taskboard.py`）**：任务表 ↔ §4 快照、证据路径存在性、当前版本 tag 存在时
T3.5 不得「待开始」。

**人工核（脚本读不到，写进 GATE-3.1 证据包由用户/维护者核对）**

1. **CI success**：run 链接 + 逐 job 结论（脚本本地无 CI 上下文，不能靠 `GITHUB_ACTIONS` 猜）。
2. **GitHub Release 正文内容**：页面正文与 `docs/releases/<date>-vX.Y.Z.md` 是否逐字一致。
3. **npm 页面可见性**：包页 `latest` 标签、tarball 内容（`npm pack --dry-run` 清单）。
4. **用户明确放行**：GATE-3.1 不能因为「CI 绿了」自动打 tag（D-5 / §5.1(5)）。
5. **BREAKING behavior 与迁移提示**是否写进发布正文（0.7.3 补丁版要求）。

**为什么发布前门禁跑不带 `--network`（F-5）**：目标版本尚未发布时，`latest` 必然不等于
`package.json.version`；把 dist-tags 一致当发布前门禁，正常发版会被自己卡死。
因此 `publish.yml` 门禁只跑 `check_taskboard.py` + `check_release.py`（**不带 `--network`**）+
`tag == package.json.version`；`--network` 的 dist-tags 判红**只用于发布后核证**。
同理，不带 `--network` 时新增的台账/工作区项一律进 `extras`（WARN），
保证"长期未发版 + 工作区有改动"的日常状态仍 `rc=0`，不制造恒定红灯。

**两条合法路径不因本条收紧**（F-5）：`workflow_dispatch` 仍是正常发布入口；
D33 补发历史 Release 依赖的 `::warning` 幂等跳过分支保留。

#### 35.7 版本轴五处与 `package-lock` 机器校验（2026-11-04 追加，0.7.4 D 组）

**结论**：发布轴自本批起是**五处**（此前口径为「三处 / 四处」）：

| # | 位置 | 谁在消费它 |
|---|---|---|
| 1 | `package.json` → `version` | npm 包版本、`npm publish` 的版本来源 |
| 2 | `package-lock.json` → 根 `version` | `npm ci` 的锁根 |
| 3 | `package-lock.json` → `packages[""].version` | lockfileVersion 2/3 的包根记录 |
| 4 | `SKILL.md` → frontmatter `version` | Agent 操作面的文档迭代号 |
| 5 | `README.md` → 「三个版本号」表两处 | 人读的对外快照（两处同值视为一处轴） |
| — | `git tag` `vX.Y.Z` | 发布锚点（与上面五处比对，但**不算**"五处"之一） |
| — | `verify_generation.py --version`（`1.2.0`） | 判据契约轴，**故意独立**（D33 §33.2），**不并入** |

**为什么把 2/3 纳入**：`npm install` 会自动把 lock 根同步成 `package.json.version`，
所以漂移只有一个来源——**手改了 `package.json.version` 却没跑 `npm install --package-lock-only`**。
这种漂移在旧的「四处」口径下**完全看不见**（四处都还是新版本，只有 lock 停在旧值），
而 `npm ci` 与发布产物**都以 lock 为准**；等它暴露时通常已经是 CI 红或 registry 上出现旧版本。
「五处」如果只是句口号、没有机器比对，就等于把这条规则又交回人手。

**实现落点**：`tools/check_release.py` 的 `parse_lock_versions()` + 判据①。
`parse_lock_versions()` 对**坏 JSON / 顶层不是对象 / 缺 `packages[""]`** 抛 `ValueError`，
由 `check()` 转成 `[FAIL] package-lock.json 版本轴` —— **不猜、不静默降级**；
`version` 字段缺失时返回 `None`，由判据① 判红（同样不猜）。

**判据① 的预期 FAIL 形态（与 §35.2 step0 一致，只是明细多两行）**：

```
[FAIL] 判据① 版本轴同值 — 最新 tag=0.7.3，但 package-lock.json 根=0.7.4；package-lock.json packages[""]=0.7.4
```

- **打 tag 之前**：五处已是新版本、最新 tag 还是旧版本 ⇒ FAIL。**这是预期的**，
  它证明的正是"版本号改了、tag 还没打"这个真实状态（与 §35.2 的说明同义）。
- **打 tag 之后**：`tag` 与五处同值 ⇒ PASS。
- 显式 `--tag v0.7.2`（历史版本）会因 lock=当前版本判红 —— **这也是正确的**：
  当前工作区确实不是 0.7.2。
- `check_release.py` **不挂 CI**（F-5），所以扩判据不影响 CI 绿。

**自测（可复核，不留"纸面通过"）**：`tests/test_check_release.py` —— ① 五处同值 ⇒ PASS（rc=0）；
② 副本把 lock **根** `version` 改 `9.9.9` ⇒ 判据① FAIL 且明细**点名** `package-lock.json 根=9.9.9`；
③ 只改 `packages[""].version` ⇒ 同样判红且点名该处；④ 缺 `packages[""]` ⇒ rc=1、可读中文错误、
无 traceback。**负例断言的是"点名到哪一处"，不是"rc≠0"**——只断言 rc 的用例，任何无关错误都能让它变绿。

**与 §35.2 / §35.6 的关系（遵循「更正只追加勘误」）**：§35.2 **step0 原文**与 §35.6 表格里写的
「三处 / 四处同值」**不改**（它们记录的是当时的判据）；**自本条起读作「五处」**，以本条为准。
`README.md` 的「三个版本号，别混」表同步补了 lock 两处的说明。

**谁确认 / 何时**：用户 **Leon** 在 0.7.4 增量 PRD 的 Q2 中裁决「版本轴统一为五处、判据① 扩到
`package-lock.json` 根两处」；**2026-11-04** 由 `software-engineer`（P4 批次）落盘，属 D34 §34.2(1)
的"实现位移按追加勘误处理"，不新开 GATE。

#### 35.8 §35.6 第 2 项「正文逐字一致」的锚点：**回填 commit 的 blob**（2026-11-05 追加，0.8.1 A1 后裁定）

**锚点定义**（唯一合法基准）：

> Release 正文应与 **该版本 `docs/releases/<file>.md` 的最后一次提交（= 回填 commit）的 blob** 逐字节一致，
> 核证命令形如 `git show <回填sha>:docs/releases/<file>.md`。
>
> **不是** `vX.Y.Z^{}` 的 tag 点 blob；**不是**裸 `HEAD`（HEAD 随未来提交漂移，锚点会自己跑掉）；
> **更不是**工作区文件（工作区可能是 CRLF，见 §35.6 的 CRLF 纪律）。

各版本锚点 sha 记在 `docs/releases/README.md` §1 台账的「正文」列：
`v0.7.3` = `327866c`（**无回填**，tag blob 即锚点）/ `v0.7.4` = `8f7d819` / `v0.8.0` = `aa8d1ed` / `v0.8.1` = `7837a45`。

**为什么是回填 commit（三条依据，缺一不可）**：

1. **实测体积只能在 publish 之后取得**：`npm notice package size` 与 files 数来自 publish run 日志，而 publish 由
   `release` 事件触发、**必然晚于 tag**。所以正文只能"先不带体积 → 发布后回填"。
   锚 tag ⇒ 等于要求正文**不写**实测体积或**靠猜**，与「包体积只认 CI LF pack」这条纪律直接冲突
   （靠猜就是 0.7.3 正文那个 `138.1 kB` 的老问题）。
2. **tag 锚点会让三版立刻变红，且唯一修法自我矛盾**：按 tag 锚点实测差值为
   0.7.4 **28 B** / 0.8.0 **101 B** / 0.8.1 **47 B**（差值全部来自回填进去的体积与 run 号）。
   要让它变绿只能**追改已发布正文**，而 0.7.3 起已确立"已发布正文不追改"（§35.7 与 `releases/README.md`）。
   ⇒ tag 锚点与"不追改"互相冲突。
3. **回填 commit 锚点四版 4/4 成立、零回溯**：0.7.3 / 0.7.4 / 0.8.0 / 0.8.1 的 body 都能用
   `git show <回填sha>:` 一次核过（含 0.8.0 那次行尾修正后的 13734 B）。

**人工核提示（能一眼看出"哪里该有差"）**：把 tag 点 blob 与锚点 blob 做 diff，**差异只应出现在
「包内容 / CI run」这类回填行**上；若差异出现在正文叙述、兼容性结论、已知限制等段落，说明有人
**事后改过正文**，那就是真问题，不只是锚点口径。

**本批不做的部分**：把"tag blob 与锚点 blob 的 diff 只允许落在包内容/CI 行"做成机器白名单校验
（`tools/check_release.py`）——排在后续代码批次，判据设计已记在此处。§35.2 step0 原文不改，按 D34 §34.2(1)
"实现位移按追加勘误处理"。

**谁确认 / 何时**：用户 **Leon** 批准批次 A 后，QA 独立核实并裁定锚点；**2026-11-05** 由
`software-engineer` 落盘（纯文档 commit，不改代码、不改任何已发布正文）。

---

### D36 · R1 批次三项裁决：`AskForMigrate` 告警策略 / 不做时钟参数判据 / 核验器 2.0 维持不排期

**背景**：P1 批次（2026-11-04）把 `references/pitfalls.md` P1 按实测重写——`project generate`
**会**写回 `AskForMigrate=true`，而 `true` **且**工程版本戳更旧时 `-q` 无头生成会**挂死**
（实测 300 s 超时、`RC=124`、日志停在 `Begin LoadConfig()`；置 `false` 后同一脚本 62 s 成功）。
由此暴露一个**体验级缺陷**：用户看到的是"程序卡住 5 分钟然后超时"，完全不知道是自己工程的设置问题。
P1 文末当时留了一条"待批准项"（是否改成"发现该键为 `true` 就退 `2`"）。本轮 R1 就此收口，
并同批裁掉另外两项长期悬空的候选改动。

#### 36.1 ① `AskForMigrate=true` **不**改成"拒跑退 2"，改为「前置告警 + opt-in 开关 + 定向诊断」

**决定**：

1. `scripts/regen.sh` 在调用 CubeMX**之前**读 `.ioc` 的 `ProjectManager.AskForMigrate`，
   为 `true` 时**分两级输出**（`false` / 读不到 → 什么都不打）：
   - **版本戳落后于锁定基线 → `[regen][warn]`（4 行）**：因果一句 + 可直接复制执行的置 `false`
     命令（含真实绝对路径）+ GUI 迁移的替代路径 + 指向 P1。
   - **版本戳一致 → 一行 `[regen]` info**：说明该键为 true 是生成后的**稳态**，但若你机器上的
     CubeMX 版本高于工程版本戳仍可能挂起，处置见 P1。
   全程**不改值、不拦跑**。
2. 新增 **opt-in** 开关 `--fail-fast-on-migrate`：只要该键为 `true` 就**退 `2`**（不依赖上面的
   版本戳判断——CI 要的是"宁可退 2 也不要挂住"，而不是"少说一句"），默认关闭。
3. 生成**超时**（`RC=124`）后做**定向诊断**：检查 CubeMX 日志**末行附近**是否停在 `Begin LoadConfig()`
   ——命中才输出"这不是你的工程坏了" + 迁移对话框解释 + **两条处置**（置 `false` 重跑 / GUI 打开一次
   让迁移完成）+ 指向 P1；未命中就**只报超时**，并明确写出"不能归因"。

**两个被否决的极端（记录留档，别再重开）**：
- **只在该键为 true 且版本戳落后时才输出、否则完全静默**：否决。`EXPECTED_CUBEMX_VERSION` 是锁定
  基线**常量**，**不是**"你机器上装了哪个版本"的探测结果——在"工程戳 6.18.1、本机装的却是 6.19.0"
  这种错配上会给出**反向结论**（判"不落后"→ 静默 → 正好漏掉会挂死的那一例）。
  **用错的判据换来的安静，比吵闹更危险。**
- **一律 `warn`（不分级）**：否决。该键在每次 `project generate` 后都会被写回 `true`（P1-1），
  一律 warn 等于**每一次 regen 都刷 4 行黄字**；用户三两次后就学会无视 `[regen][warn]`——
  **警告一旦常态化就等于没有警告**（旧文案"无实测卡死证据，仅作提示"正是这样被忽略的）。
- **采用的分级**：可疑（版本戳落后）→ `warn` 响亮且带修法；不确定（版本戳一致）→ 一行 `info`
  低调但不沉默。两个错误都不犯，代价是"不确定档只说一句"，而这正是它应得的分量。

**理由**：脚本在不启动 CubeMX 的前提下**无法可靠知道当前安装的是哪个版本**，因此判不出
"版本戳是否更旧"（`EXPECTED_CUBEMX_VERSION` 是锁定基线**常量**，不是探测结果）。只凭
`AskForMigrate=true` 拒跑，会把「同版本、能正常生成」的合法工程一并拦下——
**误拦的代价高于一次 5 分钟挂起**。把判断权留在人手里（给告警 + 可复制的修法），
需要"宁可退 2 也不要挂住"的场景再显式开开关。

**代价**：

- 默认路径下**仍可能挂 300 s**——告警是"看得见"，不是"拦得住"；CI 若不开开关就仍会等满超时。
- **告警会接近常态化**：`project generate` 会把该键**写回 `true`**（P1-1），所以生成过的工程几乎
  每次 regen 都会命中这条告警。**这是本条决策明确接受的代价**——告警文案自带"如何确认 / 如何关掉 /
  关掉只是本次有效"，仍比静默通过更接近事实。**但若实测证明噪音压过收益（例如告警被批量忽略），
  修法是把 `--fail-fast-on-migrate` 提为默认，或改用可靠的本机版本探测——不是偷偷叠加版本戳判据。**
- 「定向诊断」只覆盖**一种**日志形态；未命中时只能给方向，不能给结论（这是有意的，见下）。
- 告警基于 `.ioc` 快照；生成过程会把该键写回 `true`，所以"上次生成后是 false"不构成任何保证。

**什么情况下重新考虑**：

- 出现**可靠、零副作用**的"当前安装版本"探测（例如 CubeMX CLI 提供 `--version` 且不需 GUI）——
  那时"版本戳更旧 + 该键 true"成为**可判定**条件，才谈得上默认拒跑。
- 实测出现"同版本 + `true` 也挂死"（推翻 36.1 的前提）——那判据不再需要版本，直接退 `2` 就成立。
- 若 CI 场景里"挂满超时"的代价被证明高于误拦（例如批量跑 50 个工程），可把
  `--fail-fast-on-migrate` 提为默认开启（属行为变更，需单独批准）。

#### 36.2 ② **不做**「时钟参数判据」（核验器不新增时钟/参数级检查）

**决定**：核验器 v1.x **不增加** RCC/PLL 参数级判据（`PLLN`/`PLLM`/`HCLK` 之类），
F2（重新生成静默把 `PLLN 100→85`、SYSCLK 推算 200→170 MHz）**只作为已知限制记录**，
防线放在"生成前后 diff + 接板清单"。

**理由**：

- **期望值无可信来源**：`.ioc` 里的 `RCC.PLLN` 是"被生成器改过之后的值"，工程里没有第二处独立声明
  期望值。拿它做判据，等于**拿生成结果和自己比**——只能证明"文件里写了什么"，证明不了"本该是什么"。
- **半吊子判据比没有判据更糟**：一个只覆盖 3 个字段的参数判据会让人以为"时钟已被核验"，
  从而**停止逐条解释 diff**——而此时其余 20 个参数仍在静默变化。**假安全网比没有网更危险**
  （同 D22 立 `pins_present` 的理由的反面：那项能立，是因为期望值是**外部输入**）。
- 时钟错误的**真实后果是实板行为**（不启动、跑飞、波特率不对），最终只能由 L5 接板确认；
  一个静态判据既不能替代它，还会削弱"必须接板"这条纪律。

**代价**：PLLN 类静默改动仍然只有 `git diff` 一条发现路径；不主动 diff 的人**看不到**。
（F2 的教训已写入 `docs/guides/gate-2.0-checklist.md` 与 `references/diff-evidence.md` 三级确认。）

**什么情况下重新考虑**：

- 出现**可信的期望值来源**：如工程里存在与 `.ioc` 独立的时钟声明（`clock-plan.md`、测试断言、
  上游 spec），或用户明确给出"目标 SYSCLK"作为输入参数——那时判据有外部锚点，可以立。
- 或者把判据**降级为"变更提示"**而非 pass/fail（只报"本次生成改了这些时钟字段"，不判对错）——
  那是另一个形态，需单独立项。

#### 36.3 ③ 核验器 **2.0 维持不排期**

**决定**：核验器 2.0（schema `/3` 破坏性重构：扁平化 `inputs.*`、合并 check id、引入
`severity` 分级）**不排期、不预留占位**。触发条件是**被动**的：真实出现 schema `/3` 需求，
或现有顶层字段造成实际误用。

**理由**：1.x 的 7 项判据 + `schema /2` 至今**没有一次**因版本不符或字段语义不清导致的下游阻塞；
`inputs.*` 收口（v1.2）、`blocking` 取代 `level`（D17）、`pins_present`（D22）都是**按需**加进去的。
为"结构性更干净"而预先重构，是在没有失败案例时先付迁移成本——**下游（`regen.sh`、`lib/server.mjs`、
`tools/npm_mcp_handshake.mjs`）全都要跟改**，而收益无法验证。

**代价**：`schema /2` 的字段冗余（`inputs` 嵌套 vs 顶层 `summary`）会继续存在；
读 JSON 的人仍需按 `references/verify-contract.md` 的说明取参，不能"一眼看懂"。
弃用字段口径已统一为"v1.x 保留兼容、**v2.0 移除**"（D34），**若 2.0 永不落地，
"v2.0 移除"就是一张空头支票**——故本条同时确立：**兜底按"保留兼容"执行，移除只在 2.0 真做时发生**。

**什么情况下重新考虑**（满足任一即触发立项）：

1. 出现真实的 `schema /3` 需求方（下游工具或用户明确要求 `/3` 语义）；
2. 现有**顶层字段**造成实际误用（例如有人从顶层读了本该在 `inputs` 里的值，导致错误结论）——
   有实例即立项，无实例不立项；
3. 7 项判据的**保证边界**需要重划（例如非 GPIO 能力开放后，判据粒度必须变）。

#### 36.4 与 D19 / D22 / D34 的关系

- **D19**（`AskForMigrate` 裁决：不硬拦、不复位、单独出现不告警）被 **36.1 部分修订**：
  「不复位、不硬拦」不变；「单独出现不告警」**作废**——现在单独出现就告警（正是为了避免那 5 分钟的
  无解释挂起）。**条款被修订，不删历史**，故 D19 原文保留。
- **D22**（`pins_present` 立项理由）是 36.2 的**正面参照**：能立判据的前提是"期望值来自外部输入"。
- **D34 §34.2(1)**（形态变更元规则）要求"能力增减须有实例"；36.2 / 36.3 的"不做"正是该规则的执行结果。

#### 36.5 谁确认 / 何时

- **确认人**：用户 **Leon**（R1 批次开工前逐条裁定，负责人转达）
- **时间**：**2026-11-04**
- **方式**：批次任务书直接给定结论与理由（三项同批裁决）；本条只做记录，未单独开 GATE
  （依 D34 §34.2(1)：36.1 属体验层行为增量且有实测支撑，36.2 / 36.3 是"不做"）。
- **记录人**：`software-engineer`（R1 批次执行者）。
