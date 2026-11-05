# 发布台账（releases/）

> **一页看清"每个版本改了什么、证据齐不齐"。**
> 收口判据来自 [`../DECISIONS.md`](../DECISIONS.md) **D33**：`tag` + `GitHub Release 正文` + `npm 发布`
> + `看板回填`，**四证缺一视为发布未收口**。流程与命令见 **D35 §35.6**（机器查 vs 人工核边界）。
> **发布前门禁**（`publish.yml`）跑 `python tools/check_release.py`（**不带 `--network`**）：
> 只校验本地版本轴 / tag / 正文 / 工作区；目标版本尚未发布时 `latest` 必然不等于
> `package.json.version`，把 dist-tags 当发布前门禁会把正常发版自己卡死（F-5）。
> **发布后核证**才跑 `--network`（显式带官方 registry `https://registry.npmjs.org/`）：
> 远端 `dist-tags.latest` 与目标版本不一致即判红。

> **发版证据口径 · 只认 CI 的 LF pack（硬纪律，0.7.4 起）**
> **包内容证据（files 数 / 体积 / tarball 清单）一律取自 CI 的 LF checkout**。
> 本机 `npm pack` 会把**工作区行尾**打进 tarball：`.gitattributes` 要求 index 存 LF，而工作区可能有
> 21 个文件仍是 CRLF（`git ls-files --eol | grep -c 'w/crlf'` 实测 = **21**），于是本机尺寸偏大
> （0.7.3 实测 `138.1 kB` vs CI/registry `137.6 kB`）。
> ⇒ **本机 `npm pack` 的尺寸只能作参考，不得写进发版正文或本表当作包体积证据**；
> 唯一例外是先确认 `w/crlf` 计数为 0。陷阱与自检命令见 [`../README.md`](../README.md) **§2.1 第 5 条**
> （**`git status` 干净 ≠ 工作区逐字节等于 index**）。
>
> 📌 **`w/crlf` 的计数本身也不是证据**（0.8.0 Q0 补正）：它随文档写盘实时变动——0.7.4 发版时实测 20，
> 之后同一批文档被重写一遍就变成 21。所以**不要把某个具体数字写进正文当判据**（0.7.4 正文里那个
> `20` 已不可复现，属**已发布正文，按约定不追改**）。判据只有一条：**本机 pack 一律不作证据，
> 证据只认 CI 的 LF pack**；`w/crlf` 只用来回答"我这台机器现在要不要先清一遍再拿本机数字参考"。
>
> 📌 **发 Release 正文必须取 HEAD 的 blob（LF），不要直接喂工作区文件**（0.8.0 发版后由 QA 实测补正）
>
> `gh release create --notes-file docs/releases/<date>-vX.Y.Z.md` 读的是**工作区文件**。而本仓的工作区
> `.md` 可能是 **CRLF**（`.gitattributes` 只强制 index 存 LF，工作区行尾不受约束）：0.8.0 就是这样——
> 工作区 182 行 ⇒ **182 个 CR**、body 13916 B；`git show HEAD:docs/releases/2026-11-05-v0.8.0.md`
> 的 blob 是 **13734 B、CR=0**。**去 CR 后内容零差异，但逐字节不相等**；而 0.7.3 / 0.7.4 的 body 都是
> CR=0、与 blob 逐字节相等 ⇒ 0.8.0 在"逐字一致"这条性质上**退步了**（已发布正文按约定不追改，
> 只在此处立纪律）。
>
> - **做法（二选一，都行）**：① `git show HEAD:<path> > "$(mktemp)"` 导出 LF 内容，再把 `--notes-file`
>   指向那个临时文件；② 发版前先把工作区该文件重检出为 LF（`git checkout -- <path>`，前提是工作区干净），
>   再用它。
> - **判据（D35 §35.6 人工核第 2 项的正确读法）**：Release 正文应与 **`git show HEAD:<path>` 的 blob**
>   逐字一致，而**不是**"与工作区文件一致"。工作区带 CRLF 时，这两者本来就不相等。
> - **为什么较真**：从 CI 或干净 clone 复核的人只会看到 182 字节差（还带着 182 个不可见 CR），
>   很容易误判成"正文被事后改过"；更糟的是，下一次**真正**的正文改动会更容易被"反正也差 182 字节"
>   糊过去——证据链一旦容忍"小差"，就再也说不清哪次是真的。
> - **自检一行**：`gh release view vX.Y.Z --json body --jq .body | tr -d '\r' | cmp -s - <(git show HEAD:docs/releases/<file>.md) && echo 一致`（`tr -d '\r'` 只是让"仅行尾不同"也能看出来；要判定**逐字节**一致就把 `tr` 去掉）。

---

## 1. 版本 × 内容 × 四证

| 版本 | 日期 | 一句话内容 | tag | Release 正文 | npm | 正文文件 |
|---|---|---|---|---|---|---|
| **v0.1.0** | 2026-11-03 | 首版（当时仓名 `platform32-mcp`）：Phase 1 收口——G1 核验器 + `regen.sh` + S1/S2/S3 三场景实测 + SKILL 初版；README 定下 L0–L5 | ✅ `v0.1.0` | ✅（正文 71 行，含 L0–L5 表） | ❌（npm 通道自 0.6.0 才有） | —（正文在 GitHub；入库约定自 0.6.2 起） |
| **v0.1.1** | 2026-11-03 | 冒烟判据升级：`ok = not isError` → `(not isError) and not text_failed`。修正"`isError=False` + `[FAIL …]` 被判成 PASS"的假绿（实测：`.ioc` 为垃圾内容时 CubeMX 弹模态框被超时强杀，正好落在这个形态） | ✅ `v0.1.1` | ✅ | ❌ | —（同上） |
| **0.6.0** | 2026-11-03 | **npm 工具通道首发**（MCP）：`bin/cubeone-mcp.mjs` + `lib/server.mjs` 包起三个脚本，3 个工具可被任何 MCP 客户端拉起 | ❌ **无 tag** | ❌ **无 Release** | ✅ `cubeone-mcp@0.6.0` | — |
| **v0.6.1** | 2026-11-03 | 首个带 npm 通道的**正规发布**：Trusted Publisher（OIDC）流水线启用；仓库更名 `platform32-mcp` → `cubeone-mcp`、`main` → `master`（D32） | ✅ `v0.6.1` | ✅ **事后补发**（2026-11-03 22:0x） | ✅ `0.6.1` | [`2026-11-03-v0.6.1-backfill.md`](2026-11-03-v0.6.1-backfill.md)（补发说明 + 内容） |
| **v0.6.2** | 2026-11-03 | M1 接缝修复：退出码白名单化、入参 `inputSchema` 校验、`PYTHONIOENCODING=utf-8`、`--` 分隔、Node 单测基建（32 例） | ✅ `v0.6.2`（`b8f1857`） | ✅ | ✅ `0.6.2`（`14:04:53Z`，Trusted Publisher，17 files / 82.1 kB） | [`2026-11-03-v0.6.2.md`](2026-11-03-v0.6.2.md) |
| **v0.7.0** | 2026-11-03 | **BREAKING**：路径白名单默认 fail-closed（未设 `CUBEONE_ALLOWED_ROOTS` = 拒绝所有路径参数）+ `realpath` 防 junction 绕出 + `.ioc` 还原原子化与完整性摘要 | ✅ `v0.7.0`（`64a9a01`） | ✅ | ✅ `0.7.0` | [`2026-11-03-v0.7.0.md`](2026-11-03-v0.7.0.md) |
| **v0.7.1** | 2026-11-04 | **无行为变更**：注册指南修正并随包下发（补 0.7.0 默认拒绝 + 新增「注册后自检」）；带出 M3 的 `ioc_field` **1.1.0**（get 区分多行歧义/键不存在） | ✅ `v0.7.1`（`5ecc0b7`） | ✅ | ✅ `0.7.1`（18 files / 99.0 kB，含两本指南） | [`2026-11-04-v0.7.1.md`](2026-11-04-v0.7.1.md) |
| **v0.7.2** | 2026-11-04 | **补丁版，无新增能力**：两处**用户可见缺陷**修复——① CLI 在 cp1252/cp936 控制台打印 `→` 抛 `UnicodeEncodeError` 退出 1（改为按输出目标分流：非 TTY 强制 UTF-8 / TTY 保留编码 + `backslashreplace`）；② 核验器对 `ProjectManager.CoupleFile=true` 工程**假失败**（`--project-root` 下改扫 `Core/Src/*.c`，行号换算回原文件；无 project-root 时降 warn + `notes`）。同批工程化：Windows CI / lock 入库 + `npm ci` / 覆盖率底线 36 / `check_release.py` / D35 SOP / 贡献者文档 | [`v0.7.2`](https://github.com/LeonhardtHUST/cubeone-mcp/releases/tag/v0.7.2) | [`v0.7.2`](https://github.com/LeonhardtHUST/cubeone-mcp/releases/tag/v0.7.2) | `0.7.2`（latest） | [`2026-11-04-v0.7.2.md`](2026-11-04-v0.7.2.md) |
| **v0.7.3** | 2026-11-04 | **补丁版，无新增能力，但有一处 BREAKING behavior**：审定整改 W0–W6（10 个 commit）——① **堵 G1 四类假绿**（漏 `--ioc` / 错 `--project-root` / 日志含整行 `KO` / 任意文本或空文件当 `--log`）：证据不成立统一 **rc=2 且不落 `--json-out`/`--report-md`**，整行 `KO` 复用 `log_cannot_map` 判 **fail（rc=1）**；② `.ioc` **双层拒绝换行注入**（MCP `validateArgs` + `ioc_field` `_reject_newlines`，rc=2 且一字节不动）+ `capability_warning` 机读字段；③ `regen.sh` **退出码归一 / 缺参不死循环 / dry-run 不写盘**；④ 发布门禁**分级**（`--network` 才判红，发布前不卡死）+ `publish.yml` tag 一致性与幂等补发路径；⑤ 操作面与状态真源归位、N 处随包可达性补齐。**判据/契约零改动**：仍 7 项 / schema `/2`，无第 8 个 check id | [`v0.7.3`](https://github.com/LeonhardtHUST/cubeone-mcp/releases/tag/v0.7.3) | [`v0.7.3`](https://github.com/LeonhardtHUST/cubeone-mcp/releases/tag/v0.7.3) | `0.7.3`（latest，20 files / 137.6 kB，Trusted Publisher + provenance） | [`2026-11-04-v0.7.3.md`](2026-11-04-v0.7.3.md) |
| **v0.7.4** | 2026-11-04 | **收尾补丁版：无 BREAKING、无新增能力**（工具清单 / 能力边界 / `CUBEONE_*` 语义 / 核验器 `1.2.0` 全部不变）——① **包体积双口径澄清**：0.7.3 正文的 `138.1 kB` 是**本机 CRLF** pack、台账/registry 的 `137.6 kB` 是 **CI LF** pack，去 CR 后逐字节相等，**不追改已发布正文**；② **CRLF 硬纪律**：发版证据只认 CI 的 LF pack（陷阱：`git status` 干净 ≠ 工作区逐字节等于 index，本机实测 20 个 `w/crlf`）；③ `KO` 正则大小写敏感**复测提示**（判据本体未改）；④ `tools/*` **编码加固**（`check_release` / `check_taskboard` / `npm_mcp_handshake` 统一 UTF-8 + 控制台/管道分流 + EPIPE 守卫）；⑤ 版本轴 **四处 → 五处**（`check_release.py` 判据① 扩到 `package-lock.json` 根两处，D35 §35.7）；⑥ B-10 杂项（三证→四证、弱断言加强 2 处、文档索引修正） | [`v0.7.4`](https://github.com/LeonhardtHUST/cubeone-mcp/releases/tag/v0.7.4) | [`v0.7.4`](https://github.com/LeonhardtHUST/cubeone-mcp/releases/tag/v0.7.4) | `0.7.4`（latest，20 files / **138.1 kB**，CI LF 口径，Trusted Publisher + provenance） | [`2026-11-04-v0.7.4.md`](2026-11-04-v0.7.4.md) |
| **v0.8.0** | 2026-11-05 | **minor：MCP 输出侧契约增强，输入契约与 7 项判据零改动**——① 三工具补 `outputSchema`（**新增可选字段**，旧客户端忽略不报错；`inputSchema` 的 required/enum/additionalProperties **一字未改**；`checks[].id` enum 只把 F-1 契约显式化，判定真源仍是 `verify_documents()`）；② `structuredContent` 加 **64 KiB 上限**（超限头尾保留 + 字段级裁剪 + `_meta` 告警，**未超限完全不注入 `_meta`**，与 0.7.x 逐字节一致）；③ `tail()` 改**头尾保留**（首行 `verdict` 不再被截掉）；④ `ioc_field` / `ioc_backup` 加**并发文件锁** `.cubeone-lock`（`--lock-timeout` 默认 10s、超时 **rc=2 且 `.ioc` 一字不动**、`--list`/`get`/`--dry-run` 不加锁、Windows 走 `CreateFileW(CREATE_NEW)`；**只覆盖进程级互斥，`regen.sh` 跨步骤并发仍不在范围**）；⑤ Q2b 两个小修（npm 空输出归因、`tail()` 上界失效） | [`v0.8.0`](https://github.com/LeonhardtHUST/cubeone-mcp/releases/tag/v0.8.0) | [`v0.8.0`](https://github.com/LeonhardtHUST/cubeone-mcp/releases/tag/v0.8.0) | `0.8.0`（latest，20 files / **146.3 kB**，CI LF 口径，Trusted Publisher + provenance） | [`2026-11-05-v0.8.0.md`](2026-11-05-v0.8.0.md) |

> **`0.6.0` 那一行三个 ❌ 是事实，不是漏记**：当时 npm 化是计划外的（D33 §33.1 已把它追溯认定为正式交付物形态），
> tag 与 Release 都没做，`0.6.1` 才补上正规流程。**不要把 0.6.0 读成"发过但忘了记账"**——它是"发了但没有收口"，
> 这正是 D33 把收口判据从"打了 tag"升级成"四证齐全"的直接原因。
>
> **`v0.1.0` / `v0.1.1` 的 tag 名是 `platform32-mcp v0.1.0/0.1.1`**（改名前打的），
> 正文只存在于 GitHub Release 页面——入库约定（正文进 `docs/releases/`）是 0.6.2 才立的，
> **不回补**：补写等于伪造当时的证据形态，只在此处注明出处。

## 2. npm 包内容（`npm pack --dry-run` 实测）

| 版本 | files | 大小 | 备注 |
|---|---|---|---|
| 0.6.2 | 17 | 82.1 kB | `files` 只带 `bin/ lib/ scripts/*.py SKILL.md references/` |
| 0.7.0 | 17 | — | 同上（**包里那本指南讲的是两个外部 server，与本包无关**——交付缺口，见 0.7.1） |
| 0.7.1 | **18** | **99.0 kB** | 新增 `docs/guides/npm-publish-and-codebuddy.md`（本包真正的注册指南），`mcp-registration.md` 同时保留作双通道背景 |
| 0.7.2 | 18 | — | 未记大小（发版时未回填本表，此处只补 files 数） |
| 0.7.3 | **20** | **137.6 kB** | 新增 `docs/guides/gate-2.0-checklist.md` 与 `docs/guides/testbeds-board-map.md`（W4-3：接板日必备的两本此前**不在包里**） |
| 0.7.4 | **20** | **138.1 kB**（**CI LF**，publish run `41855861594` 实测） | 只改 `SKILL.md` / `references/regen-exit-codes.md` 文本，**files 数不变**；本机 CRLF pack 实测 `138.7 kB`，按本版新纪律**不作为证据**（见页首「发版证据口径」+ 0.7.4 正文 ①②） |
| 0.8.0 | **20** | **146.3 kB**（**CI LF**，publish run `41958627679` 实测） | 新增 `outputSchema`（`lib/server.mjs` 增约 300 行）与文件锁；`files` 清单仍为 `bin/ lib/ scripts/*.py SKILL.md references/ docs/guides/`，**files 数不变** |

> 📏 **包体积双口径（v0.7.3，A① 澄清）**：上表 `137.6 kB` 是 **CI 的 LF pack**，也就是 registry 上
> 真正发布的那个 tarball；`docs/releases/2026-11-04-v0.7.3.md` 里写的 `138.1 kB` 是**发版当时本机
> `npm pack` 的 CRLF pack**（工作区有 21 个文件 `w/crlf`、index 是 LF，所以 `git status` 仍显示干净——
> 见 [`../README.md`](../README.md) §2.1 第 5 条）。**两者内容一致**：去掉 CR 之后，包内文件与
> registry tarball **逐字节相等**，差异只有行尾字节与由此产生的体积差。
> **不追改已发布正文**：改它会破坏「Release 正文与入库文件逐字一致」这条证据（D35 §35.6 人工核第 2 项），
> 所以该口径只在本表与 **0.7.4 及后续正文**里澄清。

## 3. 怎么追加一行（发版后必做）

按 [`../DECISIONS.md`](../DECISIONS.md) **D35** 的 9 步流水线，在第 7 步"看板回填"时**顺手**把本页加一行：

1. 新建正文 `docs/releases/<日期>-vX.Y.Z.md`（结构照上一版：BREAKING 与否 → 改了什么 → 验证等级表 → 已知限制）；
2. 本表加一行：日期、一句话内容、**四证**（tag sha / Release 正文 / npm 版本与 files / 看板回填）、正文链接；
3. **发布后核证**：`python tools/check_release.py --network` → **rc=0**（版本轴同值 + 正文存在 +
   官方 registry 的 npm `latest` 对齐 + 台账回填 + 工作区干净）；发布前门禁跑不带 `--network` 的版本；
4. `python tools/check_taskboard.py` → **rc=0**（批次行回填后看板才能变绿）。

> ⚠️ 顺序不能反：**先建正文、再发 Release、最后补 npm**；`release` 事件的 workflow 取自 **tag 点**，
> 改过 `publish.yml` 的批次要让修复先落进将要打 tag 的那个 commit（D35 §35.3 坑①）。
