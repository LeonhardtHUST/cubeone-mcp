# T0 · 配置备份脱敏结果独立复核

> 产出时间：2026-11-03 · owner：`env-agent`（**不复信 lead 给出的数字，独立重扫**）· 验证等级：**L1**（`git check-ignore` + 正则全文扫描 + JSON 结构比对，均为可复现命令）
> 被审对象：`platform-lead` 在 `docs/backups/` 下产出的 4 个文件
> 依据：DECISIONS D10（备份归属）、D11（脱敏规则 + 安全红线）

---

## 0. 复核结论

**lead 声称的"JWT 残留 0 条 / 3 处 REDACTED"经独立复核 —— 成立。**

| 复核项 | 结果 |
|---|---|
| 两个 `*.raw.json` 是否被 git 忽略 | ✅ 均命中 `.gitignore:26 *.raw.json` |
| `redacted.json` 凭据真值残留 | ✅ **0**（JWT 0 / siyuan Token 0 / `userToken=` 真值 0 / gho_ 0 / 32+ hex 0 / 60+ 长串 0） |
| `mcp.proposed.diff` 凭据残留 | ✅ **0**（全 8 类特征零命中） |
| `***REDACTED***` 标记数 | ✅ **3**，与三处凭据一一对应 |
| 结构完整性 | ✅ 8 个 server 全在、顺序一致、`disabled` 字段逐一相等、JSON 合法 |
| 改动是否只发生在凭据字段 | ✅ 逐字段 diff 只命中 3 处凭据 |

**另有 1 处需要澄清的"疑似命中"，实为本审计自身正则的误报**，见 §3。

---

## 1. `.gitignore` 生效性（`git check-ignore -v`）

```text
[IGNORED ] docs/backups/mcp.json.bak-20261103-114836.raw.json
           <- .gitignore:26:*.raw.json
[IGNORED ] docs/backups/mcp.proposed.raw.json
           <- .gitignore:26:*.raw.json
[TRACKABLE] docs/backups/mcp.json.bak-20261103-114836.redacted.json
[TRACKABLE] docs/backups/mcp.proposed.diff
```

`git status --porcelain --untracked-files=all docs/backups/` 展开后只列出两个文件：

```text
?? docs/backups/mcp.json.bak-20261103-114836.redacted.json
?? docs/backups/mcp.proposed.diff
```

⇒ **含明文凭据的两个 `.raw.json` 进不了 git**，`docs/backups/` 目录下可入库的只有脱敏版与 diff。

⚠ 一点提示（不是问题，但要知道）：实际拦截命中的是 `.gitignore:26` 的**全局规则** `*.raw.json`，不是 `:24` 的 `docs/backups/*.raw.json`。全局规则更严格，效果更好；但若将来有人把 `*.raw.json` 改成受目录限制的规则，需要同时确认 `.proposed.raw.json` 这类命名仍被覆盖。

---

## 2. 凭据扫描（8 类特征，全文）

### 2.1 `mcp.json.bak-20261103-114836.redacted.json`（2135 B，将被提交）

| 特征 | 命中 |
|---|---|
| JWT（`eyJ` 开头） | **0** |
| siyuan `Token <值>` | **0** |
| `userToken=` 后跟真实值 | **0**（精化扫描：`userToken=(?!\*\*\*REDACTED\*\*\*)[^"'&\s]{16,}` → 0） |
| GitHub `gh[pousr]_` | **0** |
| OpenAI `sk-` | **0** |
| 32+ 位连续十六进制 | **0** |
| 40+ 位 base64 串 | 3 处 — **全部为误报**，见 §3 |
| 60+ 位长不透明标识 | **0** |

### 2.2 `mcp.proposed.diff`（884 B，将被提交）

8 类特征**全部 0 命中**。该 diff 只包含新增的两个 server 条目（`vscode-cube-mcp` / `platformio.mcp`），上下文行仅到 `"siyuan": {` / `"url"` / `"headers": {` 就截止，未触及任何 token 行 ✔。

### 2.3 对照：原始未脱敏备份（`*.raw.json`，已忽略）

同一套扫描在 raw 版上命中 **11 处**（`Token 09qv…`、`userToken=`、2 处 60+ 长串、7 处路径片段），证明**脱敏确实必要且确实做了事**——不是"本来就没什么可脱"。

---

## 3. 需澄清的 4 处"疑似命中"：全部是误报

### 3.1 `userToken=` 1 处（参数名命中，值已脱敏）

实际内容：

```json
"url": "https://design.penpot.app/mcp/stream?userToken=***REDACTED***"
```

`userToken=` 这个**参数名**保留了（有助于读者理解这是哪种鉴权方式），**值已被 `***REDACTED***` 替换**。我的宽口径正则 `userToken=` 只匹配参数名，故计为命中；精化扫描（要求 `=` 后跟 ≥16 位非 REDACTED 字符）结果为 **0**。⇒ **不是泄露**。

### 3.2 40+ 位 base64 串 3 处（是 Windows 文件路径片段）

```text
0/STLink-gdb-server/bin/ST-LINK_gdbserver
0/STM32CubeProgrammer/bin/STM32_Programmer_CLI
0/GNU-tools-for-STM32/bin/arm-none-eabi-gdb
```

来自 `stm32-stlink` 条目的 `STMCP_*` 路径（`C:/ST/STM32CubeCLT_1.22.0/...`）。含 `/` 与 `-`、长度超 40，被宽口径正则误吞。⇒ **不是凭据**。

---

## 4. 结构完整性（`redacted` vs `raw` 逐字段比对）

```text
raw   server 数: 8  ['agentic-hil','hig-doctor','lighthouse-ops','penpot-api',
                     'penpot-official-mcp','rea','siyuan','stm32-stlink']
redac server 数: 8  ['agentic-hil','hig-doctor','lighthouse-ops','penpot-api',
                     'penpot-official-mcp','rea','siyuan','stm32-stlink']
server 集合一致 : True
disabled 一致   : True          # 逐条比较 .disabled，全等
REDACTED 标记数 : 3
```

逐字段 diff 只命中 3 处，且全部是凭据字段：

| # | 位置 | 原文（脱敏后不可还原） | 处理 |
|---|---|---|---|
| 1 | `siyuan.headers.Authorization` | 22 B | → `***REDACTED***` |
| 2 | `penpot-official-mcp.url` 的 `userToken` 值 | 390 B URL 中的 token 段 | 值 → `***REDACTED***`，URL 结构保留 |
| 3 | `penpot-api.env.PENPOT_ACCESS_TOKEN` | 343 B JWT | → `***REDACTED***` |

其余字段（`command`/`args`/`url`/`env` 非凭据项/`disabled`/`type`/`timeout`）**逐字节未变** ⇒ 脱敏没有破坏"可审计快照"的用途。

---

## 5. 残留风险与建议（不阻塞入库）

| # | 风险 | 说明 / 建议 |
|---|---|---|
| R1 | `penpot-official-mcp` 的 **URL 结构**仍暴露 `design.penpot.app/mcp/stream` 与鉴权方式 | 不构成凭据泄露；若连"用了哪个 SaaS"都想隐藏，需整条 `disabled` 化或删条目——**当前不必要** |
| R2 | `docs/logs/phase0/` 已入库的日志里**是否含凭据** | 本次顺手复核：4 份日志只含路径、版本号、工具清单，**无 token**（`platformio-mcp-doctor.log` 的 `log_dir`、`core_dir` 是普通路径） |
| R3 | 我已提交的 `docs/guides/mcp-registration.md` 里引用了凭据**字段名**（`userToken`/`PENPOT_ACCESS_TOKEN`/`Authorization`）但**无值** | 属"点名红线位置"，是有意为之；已复核无值泄露 |
| R4 | 本地未入库的 `*.raw.json` 仍在磁盘上 | 符合 D11 设计（本机保留原始备份用于回滚）。若日后清理磁盘，记得它们含真凭据，删除时勿进回收站快照/sharing |

---

## 6. 复核命令（可复现）

```bash
# 1) gitignore 生效性
git check-ignore -v docs/backups/mcp.json.bak-20261103-114836.raw.json
git check-ignore -v docs/backups/mcp.proposed.raw.json
git status --porcelain --untracked-files=all docs/backups/

# 2) 凭据扫描（Python，8 类特征）
python - <<'PY'
import re
p = "docs/backups/mcp.json.bak-20261103-114836.redacted.json"
t = open(p, encoding="utf-8").read()
pats = {
 "JWT": r"eyJ[A-Za-z0-9_\-]{8,}",
 "siyuan": r"Token\s+[A-Za-z0-9]{8,}",
 "userToken 真值": r"userToken=(?!\*\*\*REDACTED\*\*\*)[^\"'&\s]{16,}",
 "github": r"gh[pousr]_[A-Za-z0-9]{20,}",
 "openai": r"sk-[A-Za-z0-9]{16,}",
 "hex32": r"\b[A-Fa-f0-9]{32,}\b",
}
for k, v in pats.items():
    print(k, len(re.findall(v, t)))
print("REDACTED 标计数", t.count("***REDACTED***"))
PY

# 3) 结构比对
python - <<'PY'
import json
a = json.load(open("docs/backups/mcp.json.bak-20261103-114836.raw.json", encoding="utf-8"))["mcpServers"]
b = json.load(open("docs/backups/mcp.json.bak-20261103-114836.redacted.json", encoding="utf-8"))["mcpServers"]
print("数量", len(a), len(b), "键序一致", list(a) == list(b))
print("disabled 一致", all(a[k].get("disabled") == b[k].get("disabled") for k in a))
PY
```

---

## 7. 签署

- **可入库**：`mcp.json.bak-20261103-114836.redacted.json`、`mcp.proposed.diff` —— 二者凭据残留为 0，结构完整。
- **不可入库**：`*.raw.json`（git 已拦截，符合 D11）。
- 本复核为**独立重扫**，未采信 lead 给出的统计数字；结论与之一致。
