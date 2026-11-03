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
// 5. 路径白名单的默认值仍是"未设 = 不校验"（0.6.x 语义，未改）。想强制要求它，
//    设 CUBEONE_REQUIRE_ROOTS=1：未配置白名单则**启动即退出 1**（见 requireRootsEnabled）。
//    0.7.0 才把默认翻转为 fail-closed（R-C1 第二步，届时留 CUBEONE_ALLOW_NO_ROOTS 逃生门）。

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, mkdtempSync, rmSync } from "node:fs";
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

// opt-in 严格模式（R-C1 第一步，0.6.2）：CUBEONE_REQUIRE_ROOTS 为真时，
// 未配置白名单**拒绝启动**，而不是静默地"不校验"。
//
// ⚠️ 这**不改变默认行为**：不设这个 env 就等于 0.6.x 的既有语义（未设 roots = 不校验）。
//    0.7.0 才会把默认翻转为 fail-closed，并通过 CUBEONE_ALLOW_NO_ROOTS=1 留逃生门。
//
// 取值契约（**已被 tests/node/server.test.mjs 组7-1 的 10 条断言钉死，改语义先改测试**）：
//   `1` / `true` / `yes` → 开（trim + 小写后比较，故 " YES " 也算开）
//   其余一切（未设 / "" / 空白 / `0` / `false` / 任意其它字符串）→ 关
// 宽窄是有意的：宁可少拦（要人显式写开），也不要把 `false` 之类误读成"开"而突然拒绝启动。
//    所以本函数是"让人能主动要求严格"，不是"悄悄改默认值"。
function requireRootsEnabled() {
  const v = (process.env.CUBEONE_REQUIRE_ROOTS || "").trim().toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}

// 白名单校验：绝对路径前缀匹配（防 D:\Projects 前缀撞上 D:\ProjectsEvil，必须含分隔符）
function checkPath(p) {
  const roots = allowedRoots();
  const abs = path.resolve(p);
  if (!roots.length) {
    return { ok: true, abs, note: "CUBEONE_ALLOWED_ROOTS 未设置，本次未做白名单校验" };
  }
  const norm = process.platform === "win32" ? abs.toLowerCase() : abs;
  for (const r of roots) {
    if (norm === r || norm.startsWith(r + path.sep)) return { ok: true, abs };
  }
  return { ok: false, abs, roots };
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
      "MCP 返回文本里必然没有，会假阴性且 verdict 仍 PASS）。",
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
      "restore 属写操作，CUBEONE_POLICY=read_only 时拒绝。退出码：0=OK；1=目标不存在；2=输入错误(isError=true)。" +
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

function envFootnote() {
  const roots = allowedRoots();
  // "未设置"必须能读出后果：只说"不校验"等于没提示，用户会以为那是正常状态。
  const rootsText = roots.length
    ? roots.join(";")
    : "未设置(本次调用无路径限制，见 README 安全节)";
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

  if (missing.length === 0 && badType.length === 0 && badEnum.length === 0) return null;

  const lines = [
    missing.length
      ? `[cubeone-mcp][参数错误] 缺少必填参数：${missing.join(" / ")}（见 tools/list 的 inputSchema）`
      : "[cubeone-mcp][参数错误] 参数校验未通过",
  ];
  if (badType.length) lines.push(`参数类型错误：${badType.join("；")}`);
  if (badEnum.length) lines.push(`参数取值非法：${badEnum.join("；")}`);
  for (const h of hints) lines.push(h);
  // 只回显参数名与类型，绝不回显 undefined —— 那句 "文件不存在：undefined" 就是本项要消灭的。
  return textResult(lines.join("\n"), undefined, true);
}

// ── 工具调用门禁 + 分发 ─────────────────────────────────────────────

function gateArgs(toolName, a) {
  const def = TOOL_DEFS.find((t) => t.name === toolName);

  // 1) 路径白名单
  for (const key of def.pathArgs || []) {
    const v = a[key];
    if (typeof v !== "string" || !v.trim()) continue;
    const chk = checkPath(v);
    if (!chk.ok) {
      return textResult(
        `[cubeone-mcp][越界] 参数 ${key}=${v} 不在 CUBEONE_ALLOWED_ROOTS 内。\n` +
          `解析为：${chk.abs}\n白名单：${chk.roots.join(";")}\n` +
          `如确需访问该目录，更新注册条目 env.CUBEONE_ALLOWED_ROOTS（';' 分隔）并重启客户端。`,
        undefined,
        true,
      );
    }
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
  return textResult(body, structured);
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
  // R-C1（0.6.2 第一步）：opt-in 严格模式的启动检查。
  // 放在装配 server **之前** —— 配置不自洽时不该先把协议通道拉起来，否则客户端
  // 看到的是"连上了但每个调用都说不清为什么"，比直接退出更难排障。
  if (requireRootsEnabled() && allowedRoots().length === 0) {
    console.error(
      "[cubeone-mcp][配置错误] CUBEONE_REQUIRE_ROOTS 已启用，但 CUBEONE_ALLOWED_ROOTS 未设置。\n" +
        "未设白名单 = 任何路径参数都不受限制，严格模式因此拒绝启动（不静默降级）。\n" +
        "配置方法（二选一）：\n" +
        "  1) 在 MCP 注册条目的 env 里加白名单，多个用系统分隔符（Windows 用 ';'，POSIX 用 ':'）：\n" +
        '       "CUBEONE_ALLOWED_ROOTS": "D:\\\\Projects;C:\\\\Users\\\\you\\\\WorkBuddy"\n' +
        "  2) 删除 CUBEONE_REQUIRE_ROOTS，恢复 0.6.x 的宽松语义\n" +
        "     （未设白名单 = 不做路径校验，每次调用会在返回文本里回显）。",
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
    console.error(
      `[cubeone-mcp] stdio server v${SERVER_VERSION} 启动 | policy=${policy()} | ` +
        `python=${pythonExe()} | allowed_roots=${allowedRoots().length || "未设置(本次调用无路径限制)"}`,
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
  policy,
  allowedRoots,
  requireRootsEnabled,
  TOOL_DEFS,
};
