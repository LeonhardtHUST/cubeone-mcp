// cubeone-mcp — Node MCP stdio server（薄封装层）
//
// 设计原则（对齐 SKILL.md）：
// 1. 所有判据都在 Python 脚本里（verify_generation.py / ioc_backup.py / ioc_field.py），
//    本文件只负责：MCP 协议、参数透传、路径白名单、写策略门禁、退出码→isError 映射。
//    绝不在 JS 侧重新实现任何判据（单写者边界）。
// 2. 退出码映射（与脚本约定一致）：
//    - verify_generation: 0=通过(可含 warn) 1=存在 FAIL 2=输入错误
//    - ioc_backup:        0=OK 1=目标不存在 2=输入错误
//    - ioc_field:         0=OK 1=键不存在 2=输入错误
//    → 判据是**白名单制**（isExecFailure），不是黑名单：
//      · exit 0                        → 成功
//      · exit 1 + 落了结构化 JSON      → **域内结论**（核验器的 verdict=FAIL 走这条），isError=false
//      · exit 1 + stderr 含 [<tool>][not-found] → **域内结论**（键/目标不存在），isError=false
//      · exit 1 + stderr 含 Traceback  → 执行层失败（崩溃优先于上面两条：
//        exit 1 只是碰巧等于"域内结论"的码）
//      · exit 1 + 以上都不满足         → 执行层失败（裸 KeyError / ModuleNotFoundError / 语法错）
//      · 其余一切退出码（2 / 9009 / 其它未知码）→ 执行层失败，isError=true
//      · status===null（被信号杀死/超时）或 spawn error → 执行层失败
//    ⚠️ 两类失败的措辞**有意不同**，不要合并：`res.error`（ENOENT / ETIMEDOUT）
//       意味着"根本没起来"，处置是改 `CUBEONE_PYTHON`；而 exit 2 / 9009 / null
//       意味着"起来了但出错"，处置是查参数、环境或 --log 素材。写同一句话会降低可操作性。
//    ⚠️ 为什么不用"只认 exit 2"：WindowsApps 的 python 桩在"未安装"时退 **9009**，
//       旧判据把它当域内结论；裸 exit 1 的 traceback 也会被当成"配置问题"混进正文。
//       F1（审定最重要代码发现）就是这一条。
//    ⚠️ 为什么 `[not-found]` 必须进白名单：ioc_field / ioc_backup 在"键/目标不存在"时
//       **在写 --json-out 之前**就 return 1，structured 必为 null。不认标记的话，
//       "查不到这个键"会被报成"执行层失败"，把使用者推去查 Python 环境。
// 3. stdout 是 JSON-RPC 通道，任何日志只准走 stderr。
// 4. 子进程注入 PYTHONIOENCODING=utf-8：中文 Windows 默认 cp936，脚本的 stderr 中文
//    会以 cp936 编码写入、按 utf8 解码 → 乱码。见 R-B2。
// 5. 路径白名单 **0.7.0 起默认 fail-closed**（R-C1 第二步，BREAKING）：`CUBEONE_ALLOWED_ROOTS`
//    未设置时，任何路径参数一律拒绝（checkPath → reason "no-roots"），并在拒绝文案里给出配置方法。
//    确需旧语义（无限制）的，显式设 `CUBEONE_ALLOW_NO_ROOTS=1`：宽松模式，返回文本会标注。
//    为什么 fail-open 当默认值是错的：默认值**不会自己说话**——用户看到"能跑通"就以为路径被
//    限制住了，实际上 agent 的每一次笔误都能落到任意目录。安全默认值的第一原则是"默认拒绝、
//    显式放行"：只有写下来的放宽才可能被看见、被复核。0.6.x 的"未设 = 不校验"把危险设成了
//    沉默的默认，因此 0.7.0 翻转默认值，把代价转移给"需要放宽的人"（写一行 env）。
//    `CUBEONE_REQUIRE_ROOTS` 因默认已严格而**降级为冗余**：设不设都不改变路径判定，只保留
//    "显式 opt-in 时未配白名单则启动即退出"这一条 fail-fast（见 requireRootsEnabled）；
//    两者同时为真时以 `ALLOW_NO_ROOTS` 为准（显式逃生门优先于显式收紧，不放宽为"互相抵消"）。

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, mkdtempSync, realpathSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const PKG_ROOT = fileURLToPath(new URL("..", import.meta.url));
const SERVER_VERSION = JSON.parse(
  readFileSync(path.join(PKG_ROOT, "package.json"), "utf8"),
).version;

// ── 环境配置 ────────────────────────────────────────────────────────

function pythonExe() {
  const v = (process.env.CUBEONE_PYTHON || "").trim();
  return v || "python";
}

function policy() {
  const v = (process.env.CUBEONE_POLICY || "read_only").trim().toLowerCase();
  return v === "full" ? "full" : "read_only";
}

// 与 vscode-cube-mcp 的 ST_CUBEMX_ALLOWED_ROOTS 同构：os.pathsep 分隔（Windows = ';'）
function allowedRoots() {
  const raw = (process.env.CUBEONE_ALLOWED_ROOTS || "").trim();
  if (!raw) return [];
  return raw
    .split(path.delimiter)
    .map((t) => t.trim())
    .filter(Boolean)
    .map((t) => {
      const abs = path.resolve(t);
      return process.platform === "win32" ? abs.toLowerCase() : abs;
    });
}

// 环境变量真值解析（**唯一实现**，`CUBEONE_REQUIRE_ROOTS` 与 `CUBEONE_ALLOW_NO_ROOTS` 共用）。
//
// 取值契约（**已被 tests/node/server.test.mjs 组7-1 的 10 条断言钉死，改语义先改测试**）：
//   `1` / `true` / `yes` → 开（trim + 小写后比较，故 " YES " 也算开）
//   其余一切（未设 / "" / 空白 / `0` / `false` / 任意其它字符串）→ 关
// 宽窄是有意的：宁可少放宽（要人显式写开），也不要把 `false` / 乱值误读成"开"而静默改变
// 安全姿态。两个 env 共用一份解析逻辑：复制第二份必然有一天会改歪其中一份，而这两条恰好是
// "放宽/收紧"的对偶开关，判据不一致会导致"设了 A 却按 B 生效"这种最难排查的静默降级。
function envTruthy(name) {
  const v = (process.env[name] || "").trim().toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}

// 冗余开关（0.7.0）：默认已 fail-closed，设不设都不改变路径判定。
// 仅保留 fail-fast —— 显式要求"必须有白名单"却配漏了，属配置不自洽，启动即退出比
// "连上了但每个调用都被拒"容易排障（后者要翻每次调用的返回文本才知道原因）。
function requireRootsEnabled() {
  return envTruthy("CUBEONE_REQUIRE_ROOTS");
}

// 显式逃生门（0.7.0）：恢复 0.6.x 的宽松语义（未设 roots = 不校验）。
// 与 requireRootsEnabled() 同时为真时**以本函数为准**：显式放宽优先，不搞"互相抵消"。
function allowNoRoots() {
  return envTruthy("CUBEONE_ALLOW_NO_ROOTS");
}

// 物理路径解析（R-C2）：跟穿 symlink / junction，返回真正的落点。
//
// 为什么需要：只做词法前缀比较时，白名单内的一个 junction（`mklink /J`，Windows 上创建它
// 不需要管理员权限）就能把"界内路径"整体搬到界外——路径字符串看起来完全合法，写下去的却是
// 别处的文件。所以要拿**物理路径**做判据。
//
// 目标不存在时 realpathSync 抛 ENOENT，此时**不是**直接退化成 path.resolve()：那样当父目录
// 本身是 8.3 短名（`C:\Users\LEON~1`）或 junction 时，目标的比较基准形态与 root 的物理形态
// 不一致，界内路径会被误判成越界（假失败）。正确做法是逐级向上找最近存在的祖先，取其物理
// 路径再拼回剩余词法段。
//
// ⚠️ 残余风险（如实记录，不假装已解决）：**不防 TOCTOU**——校验通过之后、真正打开文件之前，
//    链接仍可能被替换。威胁模型是"agent 误操作"（写错目录、跟错 junction），不是"对抗者构造
//    竞态"；后者需要 O_NOFOLLOW 级别的内核支持，超出本薄封装层的职责。
function physical(p) {
  const abs = path.resolve(p);
  try {
    return realpathSync(abs);
  } catch {
    /* 不存在 / 无权限：走下面逐级上溯 */
  }
  const parts = [];
  let cur = abs;
  for (;;) {
    const parent = path.dirname(cur);
    if (cur === parent) return abs; // 到卷根仍失败：纯词法解析，不再上溯
    parts.unshift(path.basename(cur));
    try {
      return path.join(realpathSync(parent), ...parts);
    } catch {
      cur = parent;
    }
  }
}

// 白名单校验：**物理路径**前缀匹配（防 D:\Projects 前缀撞上 D:\ProjectsEvil，必须含分隔符）。
//
// 返回形状（区分四种结局，调用方据此给出不同文案）：
//   { ok:true,  abs }                        —— 放行（roots 命中）
//   { ok:true,  abs, lenient:true, note }    —— 宽松模式放行（roots 空 + CUBEONE_ALLOW_NO_ROOTS）
//   { ok:false, reason:"no-roots", abs }     —— roots 空且未放宽 → **默认拒绝**（0.7.0 语义）
//   { ok:false, abs, roots, physical }       —— 有 roots 但不命中（`physical` 仅供文案对比用）
// `abs` 一律是**词法路径**：用户认自己传的那个路径；物理路径只用于比较与排障打点。
function checkPath(p) {
  const roots = allowedRoots();
  const abs = path.resolve(p);
  if (!roots.length) {
    if (allowNoRoots()) {
      return {
        ok: true,
        abs,
        lenient: true,
        note:
          "CUBEONE_ALLOWED_ROOTS 未设置（宽松模式：CUBEONE_ALLOW_NO_ROOTS 生效），本次未做白名单校验",
      };
    }
    return { ok: false, reason: "no-roots", abs };
  }
  // win32 大小写不敏感：双侧 lowercase 后比较（与 allowedRoots() 的归一口径保持一致）
  const norm = (x) => (process.platform === "win32" ? x.toLowerCase() : x);
  const target = norm(physical(abs));
  for (const r of roots) {
    const root = norm(physical(r));
    if (target === root || target.startsWith(root + path.sep)) return { ok: true, abs };
  }
  // 越界。`physical` 带出去是为了让"词法在界内、物理出界"（symlink/junction 绕出）这种情形
  // 能被文案明确指出来——否则用户会盯着自己传的那个看起来完全合法的路径无从下手。
  return { ok: false, abs, roots, physical: physical(abs) };
}

// ── 工具定义 ────────────────────────────────────────────────────────

const CAPABILITY_NOTE =
  "能力边界：只能可靠核验/读写 .ioc 与生成物；非 GPIO 外设（UART/SPI/TIM/ADC/I2C）的增改没有工具能力，" +
  "必须手改 .ioc 或走 GUI 后再过本核验器（SKILL.md §0.0）。";

const TOOL_DEFS = [
  {
    name: "verify_generation",
    description:
      "G1 生成核验硬关卡（schema /2，7 项检查：log_cannot_map / main_init_present / main_init_called / " +
      "pins_present / mxproject_abs_path / mx_script_abs_path / syscalls_path）。" +
      "退出码语义：0=通过（可含 warn）；1=存在 FAIL（须立即回滚，不要先构建）；2=输入错误（isError=true，别误报成配置问题）。" +
      "保证边界：外设级无条件保证；引脚级仅当传 ioc + expect_pins 才检查（否则 skip，不冒充通过）；参数级不保证。" +
      "🔴 log 必须是 CubeMX 原始 stdout 重定向文件——禁止传任何 MCP 工具返回值（Cannot map 真实行是 INFO 级，" +
      "MCP 返回文本里必然没有，会假阴性且 verdict 仍 PASS）。" +
      "report_md 会写 Markdown 报告文件——read_only 下也允许（属证据输出），路径仍受白名单校验。",
    annotations: { title: "G1 生成核验", readOnlyHint: true, openWorldHint: false },
    inputSchema: {
      type: "object",
      properties: {
        log: { type: "string", description: "CubeMX 原始 stdout 重定向文件路径" },
        main_c: { type: "string", description: "工程 Core/Src/main.c 路径" },
        mxproject: { type: "string", description: "工程 .mxproject 路径" },
        expect: {
          type: "string",
          description:
            "期望存在的外设名，逗号分隔（以改动意图为准，漏写=漏检、多写=假失败）；空串=不查外设（第 2/3 项将 skip）",
        },
        project_root: { type: "string", description: "可选，工程根目录；不传则相关检查 skip" },
        ioc: {
          type: "string",
          description: "可选，.ioc 路径；与 expect_pins 搭配才启用第 4 项引脚级检查",
        },
        expect_pins: {
          type: "array",
          items: { type: "string" },
          description: '引脚级期望，"PIN=SIGNAL"（如 PB0=GPIO_Output），可重复、大小写不敏感',
        },
        allow_signal: {
          type: "array",
          items: { type: "string" },
          description: "Cannot map 白名单：按抽出的信号名精确匹配（非整行子串），如 VP_RIF_VS_RIF1",
        },
        report_md: { type: "string", description: "可选，Markdown 报告输出路径" },
      },
      required: ["log", "main_c", "mxproject", "expect"],
      additionalProperties: false,
    },
    pathArgs: ["log", "main_c", "mxproject", "project_root", "ioc", "report_md"],
  },
  {
    name: "ioc_backup",
    description:
      ".ioc 备份 / 还原 / 清单（SHA-256 凭据）。backup 只新增 .ioc.bak、绝不改 .ioc 本体，read_only 下可用；" +
      "restore 属写操作，CUBEONE_POLICY=read_only 时拒绝。退出码：0=OK；1=目标不存在；" +
      "2=输入错误(isError=true，也包括 restore 前的备份完整性校验失败——此时 .ioc 一个字节都不动)。" +
      "红线：写操作前必须先 backup——它是唯一可靠的回滚锚点，别指望 git checkout。",
    annotations: { title: ".ioc 备份/还原", openWorldHint: false },
    inputSchema: {
      type: "object",
      properties: {
        project: { type: "string", description: "工程根目录（含 .ioc 的目录）" },
        action: {
          type: "string",
          enum: ["backup", "restore", "list"],
          description: "backup=备份(默认)；restore=从 .ioc.bak 还原(写操作)；list=只列出 .ioc 不写盘",
        },
      },
      required: ["project", "action"],
      additionalProperties: false,
    },
    pathArgs: ["project"],
    writeActions: ["restore"],
  },
  {
    name: "ioc_field",
    description:
      ".ioc 键级读/写（ini 键值，如 ProjectManager.AskForMigrate / Mcu.PinsNb）。get 只读；" +
      "set 属写操作——CUBEONE_POLICY=read_only 时仅允许 dry_run=true（只计算不写盘）。" +
      "退出码：0=OK；1=键不存在；2=输入错误(isError=true)。" +
      CAPABILITY_NOTE,
    annotations: { title: ".ioc 键读写", openWorldHint: false },
    inputSchema: {
      type: "object",
      properties: {
        ioc: { type: "string", description: ".ioc 文件路径" },
        action: { type: "string", enum: ["get", "set"] },
        key: { type: "string", description: "键名，如 ProjectManager.AskForMigrate" },
        value: { type: "string", description: "set 时必填；get 时忽略" },
        dry_run: { type: "boolean", description: "true=只计算不写盘（默认 false）" },
      },
      required: ["ioc", "action", "key"],
      additionalProperties: false,
    },
    pathArgs: ["ioc"],
  },
];

// ── Python 执行 ─────────────────────────────────────────────────────

const SCRIPTS = {
  verify_generation: "scripts/verify_generation.py",
  ioc_backup: "scripts/ioc_backup.py",
  ioc_field: "scripts/ioc_field.py",
};

function tail(s, n = 12000) {
  if (!s) return "";
  return s.length <= n ? s : `…(截断，仅保留末 ${n} 字符)\n` + s.slice(-n);
}

// 统一执行：--json-out 走临时文件 → 读回作为 structuredContent
function runPython(toolName, args) {
  const tmpDir = mkdtempSync(path.join(os.tmpdir(), "cubeone-mcp-"));
  const jsonOut = path.join(tmpDir, "out.json");
  const script = path.join(PKG_ROOT, SCRIPTS[toolName]);
  const fullArgs = [script, ...args];

  // `--json-out` 是**选项**，必须落在 `--` 之前，否则 argparse 会把它当位置参数。
  // ioc_field 用 `--` 隔开位置参数（action/key/value），就属于这种情况。
  const term = fullArgs.indexOf("--");
  if (term >= 0) fullArgs.splice(term, 0, "--json-out", jsonOut);
  else fullArgs.push("--json-out", jsonOut);

  let res;
  res = spawnSync(pythonExe(), fullArgs, {
    encoding: "utf8",
    timeout: 120_000,
    maxBuffer: 16 * 1024 * 1024,
    windowsHide: true,
    // 中文 Windows 默认 cp936：不注入时脚本输出的中文会乱码（R-B2）。
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  });

  const readJson = () => {
    try {
      if (!existsSync(jsonOut)) return null;
      const txt = readFileSync(jsonOut, "utf8");
      return txt.trim() ? JSON.parse(txt) : null;
    } catch {
      return null;
    }
  };
  const structured = readJson();
  rmSync(tmpDir, { recursive: true, force: true });

  return { res, structured };
}

// 退出码 → 是否"执行层失败"（白名单制：只有明确认识的成功/域内结论才放行）
//
// `[<tool>][not-found]` 是脚本自己打的固定标记（ioc_field.py:220/234、
// ioc_backup.py:235/251），只在「键 / 目标不存在」时出现，且在写 --json-out **之前**就
// return 1，所以 structured 必为 null。若不认这个标记，"查不到这个键"就会被报成
// "执行层失败"，把使用者推去排查 Python 环境 —— 而真实答案是参数或键写错了。
// 认标记而不是认中文文案：文案会改，标记是脚本的接口约定。
// 用**通用标签**而不是写死 `ioc_field|ioc_backup`：以后新增脚本只要打同样的
// `[<tool>][not-found]` 标记就自动被认，不用回来改这一行。`[not-found]` 这个
// 方括号 token 本身就是脚本侧的接口约定，通配的是工具名，不是"任意文本"。
const NOT_FOUND_RE = /\[[a-z0-9_]+\]\[not-found\]/i;

function isExecFailure(res, structured = null) {
  if (res.error) return true; // ENOENT（python 不存在）/ ETIMEDOUT / EACCES …
  if (res.status === null) return true; // 被信号杀死 / 超时强杀
  if (res.status === 0) return false; // 成功
  if (res.status === 1) {
    const stderr = res.stderr || "";
    // 崩溃优先：exit 1 只是碰巧等于"域内结论"的码，Traceback 说明它其实崩了。
    if (/Traceback \(most recent call last\)/.test(stderr)) return true;
    // 域内结论（标记制）：目标/键不存在 —— 这是答案，不是故障。
    if (NOT_FOUND_RE.test(stderr)) return false;
    // 其余 exit 1："仅当"落了结构化 JSON 才算域内结论（核验器的 verdict=FAIL 走这条）。
    // 裸 exit 1（KeyError、ModuleNotFoundError、语法错）一律执行失败。
    return structured == null;
  }
  return true; // exit 2 与其余一切未知码（含 WindowsApps 桩的 9009）
}

// 文案用：把"为什么判成执行层失败"说清楚。
// 只写"执行层失败"会让人以为环境坏了；把具体判据写出来，排障方向才不会跑偏。
function failureNote(res, structured) {
  if (res.status === 1) {
    if (/Traceback \(most recent call last\)/.test(res.stderr || "")) {
      return " (exit 1 且 stderr 含 Traceback，按执行层失败处理)";
    }
    if (structured == null) return " (exit 1 未落结构化 JSON，按执行层失败处理)";
  }
  return " (执行层失败)";
}

function textResult(text, structured = undefined, isError = false) {
  const out = { content: [{ type: "text", text }] };
  if (structured !== undefined && structured !== null) out.structuredContent = structured;
  if (isError) out.isError = true;
  return out;
}

// W1-2 / A-20：能力边界的**机读**告警。
// 能力层 ≠ 权限层（references/capability-boundary.md:8–10）：命中时只加字段，
// 不拦截写入、不改 changed / isError，也不改 scripts/ioc_field.py 的输出结构。
// `Mcu.IP*` 之类键不以 .Signal 结尾，本来就不会命中；GPIO_* 值属可靠范围，也不告警。
function applyCapabilityWarning(toolName, a, structured) {
  if (
    toolName === "ioc_field" &&
    a?.action === "set" &&
    /\.Signal\s*$/i.test(String(a.key ?? "")) &&
    !/^GPIO/i.test(String(a.value ?? "")) &&
    structured !== null &&
    structured !== undefined &&
    typeof structured === "object"
  ) {
    return {
      ...structured,
      capability_warning: {
        code: "OUT_OF_TOOL_CAPABILITY",
        key: String(a.key),
        message:
          `写入 ${a.key} 超出本工具能力边界（仅可靠处理 GPIO / Mcu.IP* 键值）；` +
          "须手改 .ioc 或走 CubeMX GUI，并强制过 G1 核验（SKILL.md §0.0）。",
      },
    };
  }
  return structured;
}

// 每次调用末尾的环境脚注：必须能读出"这次到底被限制在哪"。
// 三态，措辞一律显式写出后果：
//   有 roots            → 真实白名单
//   无 roots + 放宽      → 宽松模式（0.6.x 语义），点名是哪个 env 生效的
//   无 roots + 未放宽    → 严格模式（默认），说明路径参数会被一律拒绝
// 只说"未设置"是不够的：用户会自己脑补成"用默认白名单"，而实际后果是相反的两种。
function envFootnote() {
  const roots = allowedRoots();
  let rootsText;
  if (roots.length) {
    rootsText = roots.join(";");
  } else if (allowNoRoots()) {
    rootsText = "未设置(宽松模式：本次调用无路径限制，CUBEONE_ALLOW_NO_ROOTS 生效)";
  } else {
    rootsText = "未设置(严格模式：本次调用会拒绝所有路径参数，配置见 README 安全节)";
  }
  return `—\npolicy=${policy()} | allowed_roots=${rootsText}`;
}

// ── 参数校验（inputSchema 的必填 / 类型 / 取值） ────────────────────
//
// 定位：**入口校验**，不是判据。它只保证"传进 Python 的东西形状对"，
// 不判断配置对不对（那是核验器的事，单写者边界）。
// 为什么必须有：缺参数时旧实现把 `undefined` 直接拼进命令行，Python 侧报的是
// "文件不存在：undefined" 这类误导消息（U4.4 唯一 FAIL）。

function isPresent(v) {
  return v !== undefined && v !== null;
}

function typeName(v) {
  if (Array.isArray(v)) return "array";
  if (v === null) return "null";
  return typeof v;
}

// 只校验 JSON Schema 里能确定的那几类；number/integer 等本仓未使用，不猜。
const CHECKED_TYPES = new Set(["string", "array", "boolean"]);

function validateArgs(toolName, a) {
  const def = TOOL_DEFS.find((t) => t.name === toolName);
  if (!def) return null; // 未知工具由 callTool 单独处理
  const schema = def.inputSchema || {};
  const props = schema.properties || {};
  const missing = [];
  const badType = [];
  const badEnum = [];
  const hints = [];
  const contractErrors = [];

  // 1) required：**只判存在，不判长度**。expect 的空串是合法值（= 不查外设，第 2/3 项 skip）。
  for (const key of schema.required || []) {
    if (!isPresent(a[key])) missing.push(key);
  }

  // 2) enum：从 schema 读，不硬编码（action 的取值域归 TOOL_DEFS 维护）
  for (const [key, spec] of Object.entries(props)) {
    if (!Array.isArray(spec?.enum) || spec.enum.length === 0) continue;
    const v = a[key];
    if (!isPresent(v)) continue;
    if (!spec.enum.includes(v)) {
      badEnum.push(`${key} 应为 ${spec.enum.join(" / ")} 之一（实际：${JSON.stringify(v)}）`);
    }
  }

  // 3) 类型抽查（array 必须用 Array.isArray，typeof [] === "object"）
  for (const [key, spec] of Object.entries(props)) {
    if (!CHECKED_TYPES.has(spec?.type)) continue;
    const v = a[key];
    if (!isPresent(v)) continue;
    const ok = spec.type === "array" ? Array.isArray(v) : typeof v === spec.type;
    if (!ok) badType.push(`${key} 应为 ${spec.type}（实际：${typeName(v)}）`);
  }

  // 4) 条件必填：ioc_field 的 value 不在 required 数组里（get 时不需要），
  //    但 action=set 时必须给。空串 "" 合法 —— 所以判存在，不判真值。
  if (toolName === "ioc_field" && a.action === "set" && !isPresent(a.value)) {
    missing.push("value");
    hints.push('ioc_field action=set 必须给 value（空串 "" 是合法值，表示写成空）');
  }

  // 4b) 内容注入护栏（W1-1 / A-21）：key / value 含 CR / LF 一律拒绝。
  //     `buildArgs()` 用 argv 把 value 原样传给 ioc_field.py，带换行就能在 .ioc 里
  //     凭空写出任意键值行；scripts/ioc_field.py 的入口还有第二层拒绝（CLI 直调也挡）。
  //     错误文案与 CLI 侧点名同一组参数，便于排障。
  if (toolName === "ioc_field") {
    for (const field of ["key", "value"]) {
      const v = a[field];
      if (typeof v === "string" && /[\r\n]/.test(v)) {
        contractErrors.push(
          `[cubeone-mcp][参数错误] ${field} 含换行符（CR / LF），拒绝写入：避免 .ioc 内容注入`,
        );
      }
    }
  }

  // 5) 未知键拒绝（W0-5）：落地 inputSchema.additionalProperties=false。
  //    三个 schema 都写了 additionalProperties:false，旧实现却只遍历 props，从未拒绝
  //    props 之外的键 —— 手滑写成 projectRoot 会静默传到 Python 侧变成"文件不存在"。
  //    文案必须列出合法键名；常见 camelCase 追加「是否想写 snake_case？」提示。
  const unknown = Object.keys(a || {}).filter(
    (key) => !Object.prototype.hasOwnProperty.call(props, key),
  );
  if (unknown.length) {
    const legal = Object.keys(props).join(" / ");
    const described = unknown.map((key) => {
      const snake = key.replace(/([a-z0-9])([A-Z])/g, "$1_$2").toLowerCase();
      return Object.prototype.hasOwnProperty.call(props, snake)
        ? `${key} ⇒ 是否想写 ${snake}？`
        : key;
    });
    contractErrors.push(
      `[cubeone-mcp][参数错误] 未知参数：${described.join("、")}；` +
        `合法参数：${legal}（见 tools/list 的 inputSchema）`,
    );
  }

  // 6) 参数联动（W0-1）：verify_generation 的 expect_pins 与 ioc 必须同时提供。
  //    CLI 侧 main() 输入校验对同一组合退 2；这里提前给可机读错误，避免无谓 spawn。
  if (toolName === "verify_generation") {
    const hasPins = Array.isArray(a.expect_pins)
      ? a.expect_pins.length > 0
      : isPresent(a.expect_pins);
    if (hasPins && !isPresent(a.ioc)) {
      contractErrors.push(
        "[cubeone-mcp][参数错误] expect_pins 与 ioc 必须同时提供：给了 expect_pins 但缺 ioc，" +
          "引脚级检查无法进行（否则核验器会退 2）",
      );
    }
  }

  if (
    missing.length === 0 &&
    badType.length === 0 &&
    badEnum.length === 0 &&
    contractErrors.length === 0
  ) return null;

  const lines = [
    missing.length
      ? `[cubeone-mcp][参数错误] 缺少必填参数：${missing.join(" / ")}（见 tools/list 的 inputSchema）`
      : "[cubeone-mcp][参数错误] 参数校验未通过",
  ];
  if (badType.length) lines.push(`参数类型错误：${badType.join("；")}`);
  if (badEnum.length) lines.push(`参数取值非法：${badEnum.join("；")}`);
  for (const h of hints) lines.push(h);
  lines.push(...contractErrors);
  // 只回显参数名与类型，绝不回显 undefined —— 那句 "文件不存在：undefined" 就是本项要消灭的。
  return textResult(lines.join("\n"), undefined, true);
}

// ── 工具调用门禁 + 分发 ─────────────────────────────────────────────

function gateArgs(toolName, a) {
  const def = TOOL_DEFS.find((t) => t.name === toolName);

  // 1) 路径白名单。**两类失败必须分开说**（0.7.0）：
  //    · no-roots：配置缺失 —— 处置是"去配白名单"（或显式放宽），与"路径选错"完全无关；
  //    · 越界    ：配置在、路径不在界内 —— 处置是"换路径"或"扩白名单"。
  //    合成一句话会让用户去查错方向：明明没配白名单，却去改路径。
  for (const key of def.pathArgs || []) {
    const v = a[key];
    if (typeof v !== "string" || !v.trim()) continue;
    const chk = checkPath(v);
    if (chk.ok) continue;

    if (chk.reason === "no-roots") {
      return textResult(
        `[cubeone-mcp][策略拦截] 未配置 CUBEONE_ALLOWED_ROOTS，0.7.0 起默认拒绝所有路径参数。\n` +
          `被拒参数：${key}=${v}（解析为 ${chk.abs}）\n` +
          `原因：没有白名单就没有判据——0.6.x 的"未设即放行"等于让"这次到底被限制在哪"不可见，` +
          `而 agent 的笔误能落到任意目录，故默认翻转为 fail-closed。\n` +
          `配置方法（二选一，改完重启 MCP 客户端）：\n` +
          `  1) 在注册条目的 env 里加白名单，多个用系统分隔符（Windows 用 ';'，POSIX 用 ':'）：\n` +
          `       "CUBEONE_ALLOWED_ROOTS": "D:\\\\Projects;C:\\\\Users\\\\you\\\\WorkBuddy"\n` +
          `  2) 确需无限制则显式设 "CUBEONE_ALLOW_NO_ROOTS": "1"（宽松模式，不建议；` +
          `返回文本会标注 allowed_roots=未设置(宽松模式…)）`,
        undefined,
        true,
      );
    }

    // 词法路径看似在界内、物理落点却在界外 → symlink/junction 绕出，必须把物理路径打出来
    const samePath = (x, y) =>
      process.platform === "win32" ? x.toLowerCase() === y.toLowerCase() : x === y;
    const physicalNote =
      chk.physical && !samePath(chk.physical, chk.abs)
        ? `\n物理路径：${chk.physical}（词法路径看似在界内，但符号链接 / junction 指向界外）`
        : "";
    return textResult(
      `[cubeone-mcp][越界] 参数 ${key}=${v} 不在 CUBEONE_ALLOWED_ROOTS 内。\n` +
        `解析为：${chk.abs}${physicalNote}\n白名单：${chk.roots.join(";")}\n` +
        `如确需访问该目录，更新注册条目 env.CUBEONE_ALLOWED_ROOTS（';' 分隔）并重启客户端。` +
        `（确无限制需求可显式设 CUBEONE_ALLOW_NO_ROOTS=1，宽松模式，不建议）`,
      undefined,
      true,
    );
  }

  // 2) 写策略
  if (def.writeActions?.includes(a.action) && policy() !== "full") {
    return textResult(
      `[cubeone-mcp][策略拦截] 当前 CUBEONE_POLICY=read_only，拒绝写操作（${toolName} action=${a.action}）。\n` +
        `升级方法：把注册条目 env 的 CUBEONE_POLICY 改为 "full" 并重启 MCP 客户端；升级动作建议先征得用户同意。`,
      undefined,
      true,
    );
  }
  if (toolName === "ioc_field" && a.action === "set" && !a.dry_run && policy() !== "full") {
    return textResult(
      `[cubeone-mcp][策略拦截] CUBEONE_POLICY=read_only 下 ioc_field set 仅允许 dry_run=true。` +
        `如需真实写盘，把 env.CUBEONE_POLICY 改为 "full" 并重启客户端。`,
      undefined,
      true,
    );
  }

  return null; // 放行
}

function buildArgs(toolName, a) {
  const args = [];
  if (toolName === "verify_generation") {
    args.push("--log", a.log, "--main-c", a.main_c, "--mxproject", a.mxproject, "--expect", a.expect);
    if (a.project_root) args.push("--project-root", a.project_root);
    if (a.ioc) args.push("--ioc", a.ioc);
    for (const p of a.expect_pins || []) args.push("--expect-pins", String(p));
    for (const s of a.allow_signal || []) args.push("--allow-signal", String(s));
    if (a.report_md) args.push("--report-md", a.report_md);
  } else if (toolName === "ioc_backup") {
    args.push("--project", a.project);
    if (a.action === "restore") args.push("--restore");
    if (a.action === "list") args.push("--list");
  } else if (toolName === "ioc_field") {
    // 选项一律前置，`--` 之后只放位置参数：
    // 否则 value 以 `-`/`--` 开头会被 argparse 当选项（`-h` 假成功打印 help、
    // `--dry-run` 静默改写盘语义），属静默错误行为，比报错危险得多。
    if (a.action === "set" && a.dry_run) args.push("--dry-run");
    args.push("--ioc", a.ioc, "--");
    args.push(a.action, a.key);
    if (a.action === "set" && a.value !== undefined) args.push(a.value);
  }
  return args;
}

async function callTool(toolName, a) {
  // 客户端可能传 null（合法 JSON-RPC 里 arguments 可缺省），归一成空对象，
  // 否则后面的 a[key] 会抛 TypeError 变成"内部错误"，掩盖真正原因。
  a ??= {};
  if (!SCRIPTS[toolName]) {
    const available = TOOL_DEFS.map((t) => t.name).join(" / ");
    return textResult(`未知工具：${toolName}。可用：${available}`, undefined, true);
  }
  // 入口校验必须在门禁之前：参数形状不对时，"越界/策略拦截"这类消息只会误导。
  const invalid = validateArgs(toolName, a);
  if (invalid) return invalid;

  const gated = gateArgs(toolName, a);
  if (gated) return gated;

  const { res, structured } = runPython(toolName, buildArgs(toolName, a));

  if (res.error) {
    const code = res.error.code || res.error.message;
    return textResult(
      `[cubeone-mcp][执行失败] 无法启动 Python (${code})：pythonExe=${pythonExe()}\n` +
        `处置：把注册条目 env.CUBEONE_PYTHON 指向一个 Python 3.11+ 的 python.exe 绝对路径，重启客户端。` +
        `本包三个脚本均为纯标准库，无需 pip install。`,
      undefined,
      true,
    );
  }

  const stdout = res.stdout || "";
  const stderr = res.stderr || "";
  const failed = isExecFailure(res, structured);
  const head = `[cubeone-mcp] ${toolName} exit=${res.status}${failed ? failureNote(res, structured) : ""}`;

  if (failed) {
    return textResult(
      `${head}\n--- stdout ---\n${tail(stdout)}\n--- stderr ---\n${tail(stderr)}\n${envFootnote()}`,
      undefined,
      true,
    );
  }

  let body = `${head}\n--- stdout ---\n${tail(stdout)}`;
  if (stderr.trim()) body += `\n--- stderr ---\n${tail(stderr)}`;
  if (structured) body += `\n--- 结构化结论见 structuredContent（verdict / checks / summary.notes）---`;
  body += `\n${envFootnote()}`;
  // W1-2：能力边界告警只挂在 structuredContent 上（域内结论落了 JSON 才注入），
  // 绝不在这里翻 isError 或拦截写入。
  return textResult(body, applyCapabilityWarning(toolName, a, structured));
}

// ── 资源（把 SKILL.md 与 references/ 暴露给客户端） ─────────────────

const RESOURCE_FILES = [];
{
  const skill = path.join(PKG_ROOT, "SKILL.md");
  if (existsSync(skill)) {
    RESOURCE_FILES.push({ uri: "cubeone://docs/SKILL.md", name: "SKILL.md", file: skill });
  }
  const refDir = path.join(PKG_ROOT, "references");
  if (existsSync(refDir)) {
    for (const f of readdirSync(refDir).filter((f) => f.endsWith(".md")).sort()) {
      RESOURCE_FILES.push({
        uri: `cubeone://docs/references/${f}`,
        name: `references/${f}`,
        file: path.join(refDir, f),
      });
    }
  }
}

// ── server 装配 ─────────────────────────────────────────────────────

export function main() {
  // 0.7.0：默认已是 fail-closed，因此这里只在**显式** CUBEONE_REQUIRE_ROOTS=1 时做 fail-fast。
  // 放在装配 server **之前** —— 配置不自洽时不该先把协议通道拉起来，否则客户端看到的是
  // "连上了但每个调用都被拒"，比直接退出更难排障。
  // CUBEONE_ALLOW_NO_ROOTS 优先：两者同时为真时走宽松模式，不退出（显式逃生门压过显式收紧）。
  if (requireRootsEnabled() && !allowNoRoots() && allowedRoots().length === 0) {
    console.error(
      "[cubeone-mcp][配置错误] CUBEONE_REQUIRE_ROOTS 已启用，但 CUBEONE_ALLOWED_ROOTS 未设置。\n" +
        "0.7.0 起未设白名单本身就是严格模式（路径参数一律拒绝），本开关只用于提前失败。\n" +
        "配置方法（二选一）：\n" +
        "  1) 在 MCP 注册条目的 env 里加白名单，多个用系统分隔符（Windows 用 ';'，POSIX 用 ':'）：\n" +
        '       "CUBEONE_ALLOWED_ROOTS": "D:\\\\Projects;C:\\\\Users\\\\you\\\\WorkBuddy"\n' +
        "  2) 明确要无限制：删掉 CUBEONE_REQUIRE_ROOTS，并显式设 \"CUBEONE_ALLOW_NO_ROOTS\": \"1\"\n" +
        "     （宽松模式，本次调用无路径限制；不建议，返回文本会标注）。",
    );
    process.exit(1);
  }

  const server = new Server(
    { name: "cubeone-mcp", version: SERVER_VERSION },
    { capabilities: { tools: {}, resources: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOL_DEFS }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: a = {} } = request.params;
    try {
      return await callTool(name, a);
    } catch (err) {
      return textResult(`[cubeone-mcp][内部错误] ${err?.stack || err}`, undefined, true);
    }
  });

  server.setRequestHandler(ListResourcesRequestSchema, async () => ({
    resources: RESOURCE_FILES.map((r) => ({
      uri: r.uri,
      name: r.name,
      mimeType: "text/markdown",
    })),
  }));

  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const entry = RESOURCE_FILES.find((r) => r.uri === request.params.uri);
    if (!entry) {
      throw new Error(`未知资源：${request.params.uri}`);
    }
    return {
      contents: [
        { uri: entry.uri, name: entry.name, mimeType: "text/markdown", text: readFileSync(entry.file, "utf8") },
      ],
    };
  });

  const transport = new StdioServerTransport();
  return server.connect(transport).then(() => {
    // 启动横幅反映**三态**（与 envFootnote 同口径）：运维第一眼就要能分辨
    // "有白名单" / "严格但没配（等于全拒）" / "宽松模式"——后两者都不能误读成"正常"。
    const roots = allowedRoots();
    const rootsText = roots.length
      ? roots.join(";")
      : allowNoRoots()
        ? "未设置(宽松模式：本次调用无路径限制)"
        : "未设置(严格模式：所有路径参数将被拒绝)";
    console.error(
      `[cubeone-mcp] stdio server v${SERVER_VERSION} 启动 | policy=${policy()} | ` +
        `python=${pythonExe()} | allowed_roots=${rootsText}`,
    );
  });
}

// ── 测试可见面（R-D1） ──────────────────────────────────────────────
// 只做导出，不改协议行为：bin/cubeone-mcp.mjs 仍然只调 main()。
// 这些函数都是纯函数（policy / allowedRoots 读 process.env，测试里临时改环境变量即可）。
// 不导出的话，"安全门禁在 JS 侧却零测试"（F4）就没法补 —— 测不了的东西等于没有门禁。
export {
  isExecFailure,
  checkPath,
  buildArgs,
  validateArgs,
  applyCapabilityWarning,
  policy,
  allowedRoots,
  requireRootsEnabled,
  allowNoRoots,
  physical,
  TOOL_DEFS,
};
