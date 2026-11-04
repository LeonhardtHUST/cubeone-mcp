# 发布台账（releases/）

> **一页看清"每个版本改了什么、证据齐不齐"。**
> 收口判据来自 [`../DECISIONS.md`](../DECISIONS.md) **D33**：`tag` + `GitHub Release 正文` + `npm 发布`
> + `看板回填`，**四证缺一视为发布未收口**。流程与命令见 **D35**。
> 机器校验：`python tools/check_release.py --network`（版本轴同值 + 正文存在 + 远端 dist-tags）。

---

## 1. 版本 × 内容 × 三证

| 版本 | 日期 | 一句话内容 | tag | Release 正文 | npm | 正文文件 |
|---|---|---|---|---|---|---|
| **v0.1.0** | 2026-11-03 | 首版（当时仓名 `platform32-mcp`）：Phase 1 收口——G1 核验器 + `regen.sh` + S1/S2/S3 三场景实测 + SKILL 初版；README 定下 L0–L5 | ✅ `v0.1.0` | ✅（正文 71 行，含 L0–L5 表） | ❌（npm 通道自 0.6.0 才有） | —（正文在 GitHub；入库约定自 0.6.2 起） |
| **v0.1.1** | 2026-11-03 | 冒烟判据升级：`ok = not isError` → `(not isError) and not text_failed`。修正"`isError=False` + `[FAIL …]` 被判成 PASS"的假绿（实测：`.ioc` 为垃圾内容时 CubeMX 弹模态框被超时强杀，正好落在这个形态） | ✅ `v0.1.1` | ✅ | ❌ | —（同上） |
| **0.6.0** | 2026-11-03 | **npm 工具通道首发**（MCP）：`bin/cubeone-mcp.mjs` + `lib/server.mjs` 包起三个脚本，3 个工具可被任何 MCP 客户端拉起 | ❌ **无 tag** | ❌ **无 Release** | ✅ `cubeone-mcp@0.6.0` | — |
| **v0.6.1** | 2026-11-03 | 首个带 npm 通道的**正规发布**：Trusted Publisher（OIDC）流水线启用；仓库更名 `platform32-mcp` → `cubeone-mcp`、`main` → `master`（D32） | ✅ `v0.6.1` | ✅ **事后补发**（2026-11-03 22:0x） | ✅ `0.6.1` | [`2026-11-03-v0.6.1-backfill.md`](2026-11-03-v0.6.1-backfill.md)（补发说明 + 内容） |
| **v0.6.2** | 2026-11-03 | M1 接缝修复：退出码白名单化、入参 `inputSchema` 校验、`PYTHONIOENCODING=utf-8`、`--` 分隔、Node 单测基建（32 例） | ✅ `v0.6.2`（`b8f1857`） | ✅ | ✅ `0.6.2`（`14:04:53Z`，Trusted Publisher，17 files / 82.1 kB） | [`2026-11-03-v0.6.2.md`](2026-11-03-v0.6.2.md) |
| **v0.7.0** | 2026-11-03 | **BREAKING**：路径白名单默认 fail-closed（未设 `CUBEONE_ALLOWED_ROOTS` = 拒绝所有路径参数）+ `realpath` 防 junction 绕出 + `.ioc` 还原原子化与完整性摘要 | ✅ `v0.7.0`（`64a9a01`） | ✅ | ✅ `0.7.0` | [`2026-11-03-v0.7.0.md`](2026-11-03-v0.7.0.md) |
| **v0.7.1** | 2026-11-04 | **无行为变更**：注册指南修正并随包下发（补 0.7.0 默认拒绝 + 新增「注册后自检」）；带出 M3 的 `ioc_field` **1.1.0**（get 区分多行歧义/键不存在） | ✅ `v0.7.1`（`5ecc0b7`） | ✅ | ✅ `0.7.1`（18 files / 99.0 kB，含两本指南） | [`2026-11-04-v0.7.1.md`](2026-11-04-v0.7.1.md) |
| **v0.7.2** | 2026-11-04 | **补丁版，无新增能力**：两处**用户可见缺陷**修复——① CLI 在 cp1252/cp936 控制台打印 `→` 抛 `UnicodeEncodeError` 退出 1（改为按输出目标分流：非 TTY 强制 UTF-8 / TTY 保留编码 + `backslashreplace`）；② 核验器对 `ProjectManager.CoupleFile=true` 工程**假失败**（`--project-root` 下改扫 `Core/Src/*.c`，行号换算回原文件；无 project-root 时降 warn + `notes`）。同批工程化：Windows CI / lock 入库 + `npm ci` / 覆盖率底线 36 / `check_release.py` / D35 SOP / 贡献者文档 | 待发布 | 待发布 | 待发布 | [`2026-11-04-v0.7.2.md`](2026-11-04-v0.7.2.md) |

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

## 3. 怎么追加一行（发版后必做）

按 [`../DECISIONS.md`](../DECISIONS.md) **D35** 的 9 步流水线，在第 7 步"看板回填"时**顺手**把本页加一行：

1. 新建正文 `docs/releases/<日期>-vX.Y.Z.md`（结构照上一版：BREAKING 与否 → 改了什么 → 验证等级表 → 已知限制）；
2. 本表加一行：日期、一句话内容、三证（tag sha / Release / npm 版本与 files）、正文链接；
3. `python tools/check_release.py --network` → **rc=0**（版本轴同值 + 正文存在 + npm `latest` 对齐）；
4. `python tools/check_taskboard.py` → **rc=0**（批次行回填后看板才能变绿）。

> ⚠️ 顺序不能反：**先建正文、再发 Release、最后补 npm**；`release` 事件的 workflow 取自 **tag 点**，
> 改过 `publish.yml` 的批次要让修复先落进将要打 tag 的那个 commit（D35 §35.3 坑①）。
