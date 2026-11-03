#!/usr/bin/env node
// vpx 冷启动冒烟：模拟 codebuddy 注册条目的真实拉起方式。
//   command = vpx, args = ["cubeone-mcp"]（vite+ 的包执行器，自动从 registry 拉包）
// 验证：协议握手 → tools/list → 真实工具调用（ioc_field get）。
// 首次运行 vpx 会下载包与依赖（本机默认 registry=npmmirror），需数秒到数十秒。
//
// 运行：node tools/npm_vpx_coldstart.mjs
// 证据：docs/logs/phase1/npm-mcp/vpx-coldstart.log

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const VPX = process.env.VPX_EXE || "C:\\Users\\Leon\\.vite-plus\\bin\\vpx.exe";
const EVIDENCE_DIR = path.join(ROOT, "docs", "logs", "phase1", "npm-mcp");

const lines = [];
function log(s = "") {
  lines.push(s);
  console.log(s);
}

// 从 bash/MSYS 环境启动时，继承的 PATH 是 POSIX 格式（/c/...:...），
// vpx 这类原生 exe 解析不了 → 显式换成 Windows 格式并前置 npm 所在目录。
// （真实 MCP 客户端是原生进程，PATH 本来就是 Windows 格式，无需这层修正。）
const WIN_PATH = [
  "C:\\Users\\Leon\\.vite-plus\\bin",
  "C:\\Users\\Leon\\.workbuddy\\binaries\\node\\versions\\22.22.2-6",
  "C:\\Windows\\System32",
  process.env.PATH || "",
].join(";");

const transport = new StdioClientTransport({
  command: VPX,
  args: ["cubeone-mcp"],
  env: { ...process.env, PATH: WIN_PATH },
});
const client = new Client({ name: "vpx-coldstart", version: "0.0.0" }, { timeout: 180_000 });

try {
  log(`# vpx = ${VPX}`);
  log("# 拉起 vpx cubeone-mcp（首次含下载，耐心等）…");
  await client.connect(transport);

  const ver = client.getServerVersion();
  log(`[PASS] 握手 server=${ver?.name} v${ver?.version}`);

  const tools = await client.listTools();
  log(`[PASS] tools/list ${tools.tools.length} 个：${tools.tools.map((t) => t.name).join(", ")}`);

  const r = await client.callTool({
    name: "ioc_field",
    arguments: {
      ioc: path.join(ROOT, "testbeds", "_verifier-regen", "g474", "stm32-g474-template.ioc"),
      action: "get",
      key: "MxCube.Version",
    },
  });
  const val = r.structuredContent?.value;
  log(`${val === "6.18.1" ? "[PASS]" : "[FAIL]"} ioc_field get → MxCube.Version=${val}`);

  log("");
  log(`VERDICT: ${val === "6.18.1" && tools.tools.length === 3 ? "VPX COLDSTART PASS" : "VPX COLDSTART FAIL"}`);
  process.exitCode = val === "6.18.1" && tools.tools.length === 3 ? 0 : 1;
} catch (err) {
  log(`[FATAL] ${err?.stack || err}`);
  log("VERDICT: VPX COLDSTART FAIL (exception)");
  process.exitCode = 1;
} finally {
  try {
    await client.close();
  } catch {
    /* ignore */
  }
  mkdirSync(EVIDENCE_DIR, { recursive: true });
  writeFileSync(path.join(EVIDENCE_DIR, "vpx-coldstart.log"), lines.join("\n") + "\n", "utf8");
}
