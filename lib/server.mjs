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
//    → 只有 exit 2 / spawn 失败 / 超时 → isError=true；
//      exit 1 是"域内结论"（核验 FAIL、键不存在），isError=false，结论看结构化 JSON。
// 3. stdout 是 JSON-RPC 通道，任何日志只准走 stderr。

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
  const fullArgs = [script, ...args, "--json-out", jsonOut];

  let res;
  res = spawnSync(pythonExe(), fullArgs, {
    encoding: "utf8",
    timeout: 120_000,
    maxBuffer: 16 * 1024 * 1024,
    windowsHide: true,
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

function isExecFailure(res) {
  if (res.error) return true; // ENOENT（python 不存在）/ ETIMEDOUT / EACCES …
  return res.status === null || res.status === 2; // null = 被信号杀死/超时
}

function textResult(text, structured = undefined, isError = false) {
  const out = { content: [{ type: "text", text }] };
  if (structured !== undefined && structured !== null) out.structuredContent = structured;
  if (isError) out.isError = true;
  return out;
}

function envFootnote() {
  const roots = allowedRoots();
  return `—\npolicy=${policy()} | allowed_roots=${roots.length ? roots.join(";") : "未设置(不校验)"}`;
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
    args.push("--ioc", a.ioc, a.action, a.key);
    if (a.action === "set" && a.value !== undefined) args.push(a.value);
    if (a.dry_run) args.push("--dry-run");
  }
  return args;
}

async function callTool(toolName, a) {
  if (!SCRIPTS[toolName]) {
    return textResult(`未知工具：${toolName}`, undefined, true);
  }
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
  const head = `[cubeone-mcp] ${toolName} exit=${res.status}${isExecFailure(res) ? " (执行层失败)" : ""}`;

  if (isExecFailure(res)) {
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
        `python=${pythonExe()} | allowed_roots=${allowedRoots().length || "未设置"}`,
    );
  });
}
