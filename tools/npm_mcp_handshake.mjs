#!/usr/bin/env node
// npm 包（cubeone-mcp MCP server）的工具通道冒烟自检。
//
// 与 tools/mcp_smoke.py（针对 vscode-cube-mcp）同思路：不满足于协议握手，
// 要真的 tools/call 并判返回。覆盖：
//   T1 协议握手（initialize）
//   T2 tools/list = 3 个工具
//   T3 resources/list ≥ 1 且可读（SKILL.md）
//   T4 ioc_field get（只读，真实 .ioc）
//   T5 ioc_backup list（只读）
//   T6 verify_generation（真实日志 + 真实工程，期望 verdict=pass）
//   T7 写策略：read_only 下 ioc_field set → isError 且文本含"策略拦截"
//   T8 dry-run 放行：CUBEONE_POLICY=full + dry_run=true → exit=0
//   T9 路径白名单：CUBEONE_ALLOWED_ROOTS 外的路径 → isError 且含"越界"
//   T10 中文可读：Python 侧中文报错到 MCP 返回文本里必须是正常汉字（R-B2 的 PYTHONIOENCODING）
//   T11 fail-closed：**不设** roots 也不设逃生门 → 调用被拒且文案含 CUBEONE_ALLOWED_ROOTS（R-C1）
//
// ⚠️ 0.7.0 起默认 fail-closed（未设白名单拒绝路径参数）。所以凡是要真正跑通调用的用例
//    （T4/T5/T6/T7/T8/T10）都必须**显式**给 CUBEONE_ALLOWED_ROOTS —— 它们验的是别的事
//    （只读查询 / 策略门禁 / 中文编码），不该被"没配白名单"顺手拦掉而变成假红。
//    这**不是**为了让冒烟变绿去放水：T9（界外拦截）与 T11（无白名单被拒）反过来守默认值。
//
// 运行：node tools/npm_mcp_handshake.mjs
// 证据：docs/logs/phase1/npm-mcp/handshake.log（同内容落盘）

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { writeFileSync, mkdirSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const BIN = path.join(ROOT, "bin", "cubeone-mcp.mjs");
const G474 = path.join(ROOT, "testbeds", "_verifier-regen", "g474");
const LOG_PATH = path.join(ROOT, "docs", "logs", "phase1", "regen-success", "cubemx-generate.log");
const EVIDENCE_DIR = path.join(ROOT, "docs", "logs", "phase1", "npm-mcp");

const logLines = [];
function log(line = "") {
  logLines.push(line);
  console.log(line);
}

/**
 * 合并宿主 env 后起客户端。
 * 值传 `undefined` 表示**删除**该变量（空串 ≠ 删除：T11 要模拟"完全没配"的用户）。
 * SDK 对 undefined 值的处理随版本而变，所以在 JS 侧先删干净，不把 `KEY=undefined` 传下去。
 */
function makeClient(env = {}) {
  const merged = { ...process.env };
  for (const [key, value] of Object.entries(env)) {
    if (value === undefined) delete merged[key];
    else merged[key] = value;
  }
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [BIN],
    env: merged,
  });
  const c = new Client({ name: "cubeone-mcp-handshake", version: "0.0.0" }, { timeout: 90_000 });
  return { c, transport };
}

async function withClient(env, fn) {
  const { c, transport } = makeClient(env);
  await c.connect(transport);
  try {
    return await fn(c);
  } finally {
    await c.close();
  }
}

function textOf(res) {
  return (res.content || []).map((c) => (c.type === "text" ? c.text : "")).join("\n");
}

let pass = 0;
let fail = 0;
function check(id, ok, detail) {
  if (ok) {
    pass += 1;
    log(`[PASS] ${id}${detail ? ` — ${detail}` : ""}`);
  } else {
    fail += 1;
    log(`[FAIL] ${id}${detail ? ` — ${detail}` : ""}`);
  }
}

async function main() {
  // ── 素材定位 ──
  let iocPath = null;
  for (const dir of [G474, path.join(ROOT, "testbeds", "stm32-g474-template")]) {
    try {
      const hit = readdirSync(dir).find((f) => f.endsWith(".ioc"));
      if (hit) {
        iocPath = path.join(dir, hit);
        break;
      }
    } catch {
      /* 目录不存在则跳过 */
    }
  }
  log(`# ioc=${iocPath}`);
  log(`# g474=${G474}`);
  log(`# log=${LOG_PATH}`);
  log("");

  // T1 + T2 + T3
  // 白名单显式给仓库根：T1/T2/T3 是协议面，T4/T5/T6/T7/T10 用的是仓内素材，
  // 0.7.0 默认 fail-closed 之下不给 roots 会让它们全部变成"越界/未配白名单"的假红。
  await withClient({ CUBEONE_ALLOWED_ROOTS: ROOT }, async (c) => {
    const ver = c.getServerVersion();
    check("T1 握手", Boolean(ver?.name), `server=${ver?.name} v${ver?.version}`);

    const tools = await c.listTools();
    const names = tools.tools.map((t) => t.name).sort();
    check(
      "T2 tools/list",
      names.length === 3 && names.join() === "ioc_backup,ioc_field,verify_generation",
      names.join(", "),
    );

    const resources = await c.listResources();
    check(
      "T3 resources/list",
      resources.resources.length >= 1 && resources.resources.some((r) => r.uri === "cubeone://docs/SKILL.md"),
      `${resources.resources.length} 个资源`,
    );

    const skill = await c.readResource({ uri: "cubeone://docs/SKILL.md" });
    check("T3b 读 SKILL.md", (skill.contents?.[0]?.text || "").length > 1000, "text/markdown");

    // T4 ioc_field get（只读）
    if (iocPath) {
      const get = await c.callTool({
        name: "ioc_field",
        arguments: { ioc: iocPath, action: "get", key: "MxCube.Version" },
      });
      check(
        "T4 ioc_field get",
        !get.isError && textOf(get).includes("exit=0") && get.structuredContent?.value !== undefined,
        `value=${get.structuredContent?.value}`,
      );
    } else {
      check("T4 ioc_field get", false, "找不到 .ioc 素材");
    }

    // T5 ioc_backup list（只读）
    const ls = await c.callTool({
      name: "ioc_backup",
      arguments: { project: G474, action: "list" },
    });
    check("T5 ioc_backup list", !ls.isError && textOf(ls).includes("exit=0"), "");

    // T6 verify_generation（真实素材）
    const verify = await c.callTool({
      name: "verify_generation",
      arguments: {
        log: LOG_PATH,
        main_c: path.join(G474, "Core", "Src", "main.c"),
        mxproject: path.join(G474, ".mxproject"),
        expect: "GPIO",
        project_root: G474,
      },
    });
    check(
      "T6 verify_generation",
      !verify.isError && verify.structuredContent?.verdict === "pass",
      `verdict=${verify.structuredContent?.verdict} exit 文本含 exit=${(verify.structuredContent && "0") || "?"}`,
    );

    // T7 写策略：read_only 拒绝 set
    const denied = await c.callTool({
      name: "ioc_field",
      arguments: {
        ioc: iocPath || path.join(G474, "x.ioc"),
        action: "set",
        key: "ProjectManager.AskForMigrate",
        value: "false",
      },
    });
    check(
      "T7 read_only 拒绝 set",
      denied.isError === true && textOf(denied).includes("策略拦截"),
      textOf(denied).split("\n")[0],
    );

    // T10 中文可读（R-B2）：不加 PYTHONIOENCODING 时，中文 Windows 上 Python 以 cp936
    // 写管道、JS 按 utf8 解码 → "指向的文件不存在" 变成乱码；本项就是这条的守卫。
    // 只看 structuredContent 是老冒烟的盲区：那里是 JSON（脚本自己按 utf8 写的），
    // 永远不乱，乱的是 stdout/stderr 文本 —— 所以必须断言**文本**。
    const zh = await c.callTool({
      name: "verify_generation",
      arguments: {
        log: path.join(ROOT, "no-such-dir", "no-such.log"),
        main_c: path.join(G474, "Core", "Src", "main.c"),
        mxproject: path.join(G474, ".mxproject"),
        expect: "GPIO",
      },
    });
    const zhText = textOf(zh);
    const zhLine = zhText.split("\n").find((l) => l.includes("[input-error]")) || "";
    check(
      "T10 中文报错可读",
      zh.isError === true && zhLine.includes("指向的文件不存在") && !zhText.includes("\uFFFD"),
      zhLine.trim().slice(0, 90) || zhText.split("\n")[0],
    );
  });

  // T8 dry-run 放行（full 策略 + dry_run）
  if (iocPath) {
    // 同样显式给 roots：本项验的是"策略 full + dry_run 放行"，不是白名单默认值。
    await withClient({ CUBEONE_POLICY: "full", CUBEONE_ALLOWED_ROOTS: ROOT }, async (c) => {
      const dry = await c.callTool({
        name: "ioc_field",
        arguments: {
          ioc: iocPath,
          action: "set",
          key: "ProjectManager.AskForMigrate",
          value: "false",
          dry_run: true,
        },
      });
      check("T8 full+dry_run 放行", !dry.isError && textOf(dry).includes("exit=0"), "");
    });

    // T9 白名单拦截
    await withClient({ CUBEONE_ALLOWED_ROOTS: ROOT }, async (c) => {
      const blocked = await c.callTool({
        name: "ioc_field",
        arguments: { ioc: "C:\\Windows\\win.ini", action: "get", key: "x" },
      });
      check(
        "T9 白名单拦截",
        blocked.isError === true && textOf(blocked).includes("越界"),
        textOf(blocked).split("\n")[0],
      );
    });
  }

  // T11 fail-closed（R-C1）：完全不配白名单、也不开逃生门 → 调用必须被拒，
  // 且文案点名 CUBEONE_ALLOWED_ROOTS —— 只说"越界"会让人去改路径，
  // 而真实原因是"没配白名单"，方向一错就要反复绕。
  // 注意这里用 undefined 真删变量（空串不算"没配"）。REQUIRE_ROOTS 一起删：
  // 它会让进程启动即退出，那时 T11 会退化成"连不上"而不是"调用被拒"，失去测点。
  await withClient(
    {
      CUBEONE_ALLOWED_ROOTS: undefined,
      CUBEONE_ALLOW_NO_ROOTS: undefined,
      CUBEONE_REQUIRE_ROOTS: undefined,
    },
    async (c) => {
      const noRoots = await c.callTool({
        name: "ioc_field",
        arguments: { ioc: iocPath || path.join(G474, "x.ioc"), action: "get", key: "MxCube.Version" },
      });
      const noRootsText = textOf(noRoots);
      check(
        "T11 无白名单默认拒绝",
        noRoots.isError === true && noRootsText.includes("CUBEONE_ALLOWED_ROOTS"),
        noRootsText.split("\n")[0],
      );
    },
  );

  log("");
  log(`VERDICT: ${fail === 0 ? "HANDSHAKE SMOKE PASS" : "HANDSHAKE SMOKE FAIL"} (pass=${pass} fail=${fail})`);
  return fail === 0 ? 0 : 1;
}

try {
  const code = await main();
  mkdirSync(EVIDENCE_DIR, { recursive: true });
  writeFileSync(path.join(EVIDENCE_DIR, "handshake.log"), logLines.join("\n") + "\n", "utf8");
  process.exit(code);
} catch (err) {
  log(`[FATAL] ${err?.stack || err}`);
  log("VERDICT: HANDSHAKE SMOKE FAIL (exception)");
  try {
    mkdirSync(EVIDENCE_DIR, { recursive: true });
    writeFileSync(path.join(EVIDENCE_DIR, "handshake.log"), logLines.join("\n") + "\n", "utf8");
  } catch {
    /* 忽略落盘失败 */
  }
  process.exit(1);
}
