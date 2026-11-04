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
// ── 素材（C1.2，2026-11-04）───────────────────────────────────────────────────
// 有的用例需要"真实工程的素材"，而素材来源分两类：
//   ① `testbeds/`（本机克隆的模板工程，**被 .gitignore 忽略**）—— CI 上不存在；
//   ② `tests/fixtures/e2e/`（入库的极小样本，只有一只 `board.ioc`）—— CI 上有。
// 素材缺失时**不能判红**（那会把"这台机器没有 testbeds"误报成"工具坏了"），
// 但**更不能静默跳过**——所以引入第三个计数 `skip`：`[SKIP]` 行写清缺什么、为什么缺，
// 汇总行 `pass=/fail=/skip=` 三数并列，缺素材的项一眼可见，绝不会被读成"通过"。
//
// 两种模式：
//   node tools/npm_mcp_handshake.mjs                      # 宽松：缺素材记 SKIP，退出码只看 fail
//   node tools/npm_mcp_handshake.mjs --require-materials   # 严格：SKIP 即失败（本地/发版前用它）
//   node tools/npm_mcp_handshake.mjs --ci                  # CI：等同宽松 + 不落盘证据文件
//
// 运行：node tools/npm_mcp_handshake.mjs [--require-materials] [--ci]
// 证据：docs/logs/phase1/npm-mcp/handshake.log（同内容落盘；`--ci` 下不写）

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { writeFileSync, appendFileSync, mkdirSync, readdirSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// ── 编码与管道（B-5 / 0.7.4）───────────────────────────────────────────────
// 本文件所有落盘都是显式 "utf8"（`writeStepSummary()` 的 appendFileSync、末尾的 writeFileSync）。
// Node 对 stdout/stderr 也一律写 **UTF-8 字节**、**不按控制台代码页转码**，所以 Python 侧那个
// `UnicodeEncodeError` 的失败模式在这里不存在：cp1252 / cp936 控制台上最坏是**显示**乱码，
// 进程不会崩，日志文件里的字节仍是 UTF-8（`tests/test_tools_encoding.py` 用 `LANG=C` +
// `PYTHONIOENCODING=cp1252` 跑本脚本断言这一点）。
// 真正会崩的是**管道被下游提前关闭**（如 `node tools/npm_mcp_handshake.mjs | head -5`）：
// EPIPE 会变成未捕获异常 ⇒ 冒烟以"崩溃"结束，而不是给出 PASS/FAIL —— 那比失败更误导。
// 所以这里只吞 EPIPE；其它写错误也不往外抛（结论已在 logLines 里，落盘路径会再试一次）。
for (const stream of [process.stdout, process.stderr]) {
  stream.on("error", (error) => {
    if (error?.code !== "EPIPE") return;
  });
}

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const BIN = path.join(ROOT, "bin", "cubeone-mcp.mjs");

// 素材目录候选：先 testbeds（真实工程，含 .mxproject / main.c），再入库的 fixtures。
// 顺序即优先级：本机有 testbeds 时用真实素材（T6 也能跑），CI 上自然落到 fixtures。
const MATERIAL_DIRS = [
  path.join(ROOT, "testbeds", "_verifier-regen", "g474"),
  path.join(ROOT, "testbeds", "stm32-g474-template"),
  path.join(ROOT, "tests", "fixtures", "e2e"),
];
const LOG_PATH = path.join(ROOT, "docs", "logs", "phase1", "regen-success", "cubemx-generate.log");
const EVIDENCE_DIR = path.join(ROOT, "docs", "logs", "phase1", "npm-mcp");

// ── 开关 ──
const argv = process.argv.slice(2);
const KNOWN_FLAGS = new Set(["--require-materials", "--ci"]);
for (const flag of argv) {
  if (!KNOWN_FLAGS.has(flag)) {
    console.error(`[usage] 未知参数：${flag}（支持 --require-materials / --ci）`);
    process.exit(2);
  }
}
const requireMaterials = argv.includes("--require-materials");
const ciMode = argv.includes("--ci");

const logLines = [];
function log(line = "") {
  logLines.push(line);
  console.log(line);
}

/**
 * `--ci` 下把汇总写进 GitHub Job Summary（A-24 / F-6）。
 *
 * 只改**呈现**，不改判定：SKIP 仍然不翻 FAIL、不造假素材、退出码仍只看 fail。
 * 目的是让 `pass=11 skip=1` 不会被读成"12 项全测过"——Summary 里逐条列出 skippedIds。
 * 用 appendFileSync 而不是 writeFileSync：同一个 job 里别的步骤可能已经写过 Summary。
 * CI 没给 GITHUB_STEP_SUMMARY（本地模拟 --ci）时安静跳过，不影响退出码。
 */
function writeStepSummary() {
  if (!ciMode) return;
  const target = process.env.GITHUB_STEP_SUMMARY;
  if (!target) return;
  const conclusion = fail === 0 ? "PASS" : "FAIL";
  const lines = [
    "### MCP 工具通道冒烟（handshake）",
    "",
    `- 结论：**${conclusion}** ｜ pass=${pass} fail=${fail} skip=${skip}`,
    skip > 0
      ? `- ⚠️ 有 ${skip} 项 SKIPPED（未验证，**不代表通过**；缺素材不造假，见 F-6）`
      : "- 无 SKIPPED 项",
    "",
    "#### SKIPPED 明细",
    "",
  ];
  if (skippedIds.length) {
    for (const id of skippedIds) lines.push(`- ${id}`);
  } else {
    lines.push("- （无）");
  }
  lines.push("", "> SKIP 是有意取舍：`--require-materials` 严格模式下 SKIP 即失败。");
  try {
    appendFileSync(target, lines.join("\n") + "\n", "utf8");
  } catch (error) {
    console.error(`[handshake] 写 GITHUB_STEP_SUMMARY 失败（不影响退出码）：${error?.message || error}`);
  }
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
let skip = 0;
const skippedIds = [];

function check(id, ok, detail) {
  if (ok) {
    pass += 1;
    log(`[PASS] ${id}${detail ? ` — ${detail}` : ""}`);
  } else {
    fail += 1;
    log(`[FAIL] ${id}${detail ? ` — ${detail}` : ""}`);
  }
}

/**
 * 记录一条"因为缺素材而没验"的项。
 *
 * 默认记 SKIP 并计数（不入 fail）；`--require-materials` 下**转为 FAIL** —— 发版前
 * 必须在本机把 12 项全跑过，缺素材就是没验，不能带着 SKIP 发版。
 */
function skipCheck(id, detail) {
  if (requireMaterials) {
    check(id, false, `${detail}（--require-materials 下 SKIP 即失败）`);
    return;
  }
  skip += 1;
  skippedIds.push(id);
  log(`[SKIP] ${id} — ${detail}`);
}

/** 在候选目录里找第一只 `.ioc`；返回 `{ iocPath, projectDir }`。 */
function locateIoc() {
  for (const dir of MATERIAL_DIRS) {
    try {
      const hit = readdirSync(dir).find((f) => f.endsWith(".ioc"));
      if (hit) return { iocPath: path.join(dir, hit), projectDir: dir };
    } catch {
      /* 目录不存在则试下一个候选 */
    }
  }
  return { iocPath: null, projectDir: null };
}

/**
 * T6 需要的"三者自洽"素材：原始日志 + `main.c` + `.mxproject`。
 *
 * **为什么要三者齐全才跑**：`verify_generation` 的判据之一是 `.mxproject` 里不得出现
 * 盘符绝对路径，另几项要从 `main.c` 抓 `MX_*_Init` 定义/调用。手工拼一套"看起来像"的
 * 假素材极容易拼出 `verdict=pass` 的**假绿**（例如日志为空 → `log_cannot_map` 只给 warn）。
 * 所以 T6 宁可 SKIP 也不造假素材——这是**有意的取舍**，不是偷懒。
 */
function verifyMaterialsOf(projectDir) {
  if (!projectDir) return null;
  const mainC = path.join(projectDir, "Core", "Src", "main.c");
  const mxproject = path.join(projectDir, ".mxproject");
  if (!existsSync(LOG_PATH) || !existsSync(mainC) || !existsSync(mxproject)) return null;
  return { mainC, mxproject };
}

/**
 * T9 用的"界外路径"。
 *
 * ⚠️ 不能写死 `C:\Windows\win.ini`：在 Linux 上 `path.resolve("C:\\Windows\\win.ini")`
 * 会变成 `<仓库根>/C:\Windows\win.ini`，**落在白名单内**，T9 于是会因为"文件不存在"
 * 而不是"越界"失败——一个只在 Windows 上成立的用例，进了 CI 就是假红。
 * 统一取"仓库根的上一级 + 一个不存在的名字"，两平台都必然在界外。
 */
function outsidePath() {
  return path.join(path.dirname(ROOT), "__cubeone_outside_probe__.ioc");
}

async function main() {
  log(`# mode=${ciMode ? "ci" : "local"}${requireMaterials ? " require-materials" : ""}`);
  const { iocPath, projectDir } = locateIoc();
  const verifyMaterials = verifyMaterialsOf(projectDir);
  log(`# ioc=${iocPath}`);
  log(`# project=${projectDir}`);
  log(`# log=${LOG_PATH}`);
  log(`# verify-materials=${verifyMaterials ? "ok" : "缺（T6 记 SKIP）"}`);
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
      skipCheck("T4 ioc_field get", `缺 .ioc 素材（候选：${MATERIAL_DIRS.map((d) => path.relative(ROOT, d)).join(" / ")}）`);
    }

    // T5 ioc_backup list（只读）
    if (projectDir) {
      const ls = await c.callTool({
        name: "ioc_backup",
        arguments: { project: projectDir, action: "list" },
      });
      check("T5 ioc_backup list", !ls.isError && textOf(ls).includes("exit=0"), path.relative(ROOT, projectDir));
    } else {
      skipCheck("T5 ioc_backup list", "缺工程目录素材（需一个含 *.ioc 的目录）");
    }

    // T6 verify_generation（真实素材，三者自洽；缺则不造假素材，见 verifyMaterialsOf 注释）
    if (verifyMaterials) {
      const verify = await c.callTool({
        name: "verify_generation",
        arguments: {
          log: LOG_PATH,
          main_c: verifyMaterials.mainC,
          mxproject: verifyMaterials.mxproject,
          expect: "GPIO",
          project_root: projectDir,
        },
      });
      check(
        "T6 verify_generation",
        !verify.isError && verify.structuredContent?.verdict === "pass",
        `verdict=${verify.structuredContent?.verdict}`,
      );
    } else {
      skipCheck(
        "T6 verify_generation",
        "缺素材（需 CubeMX 原始日志 + 真实工程的 main.c/.mxproject；不造假素材以免拼出 verdict=pass 的假绿）",
      );
    }

    // T7 写策略：read_only 拒绝 set
    const denied = await c.callTool({
      name: "ioc_field",
      arguments: {
        ioc: iocPath || path.join(projectDir || ROOT, "x.ioc"),
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
    // 输入校验按 --log → --main-c → --mxproject 的顺序，`--log` 不存在就先报，
    // 所以另两个参数随便给（本项验的是编码，不是文件存在性）。
    const zh = await c.callTool({
      name: "verify_generation",
      arguments: {
        log: path.join(ROOT, "no-such-dir", "no-such.log"),
        main_c: path.join(projectDir || ROOT, "Core", "Src", "main.c"),
        mxproject: path.join(projectDir || ROOT, ".mxproject"),
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
  } else {
    skipCheck("T8 full+dry_run 放行", "缺 .ioc 素材（dry_run 也要真实文件）");
  }

  // T9 白名单拦截（界外路径见 outsidePath() 注释）
  await withClient({ CUBEONE_ALLOWED_ROOTS: ROOT }, async (c) => {
    const blocked = await c.callTool({
      name: "ioc_field",
      arguments: { ioc: outsidePath(), action: "get", key: "x" },
    });
    check(
      "T9 白名单拦截",
      blocked.isError === true && textOf(blocked).includes("越界"),
      textOf(blocked).split("\n")[0],
    );
  });

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
        arguments: {
          ioc: iocPath || path.join(projectDir || ROOT, "x.ioc"),
          action: "get",
          key: "MxCube.Version",
        },
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
  if (skip > 0) {
    // 单独一行点名，避免"skip 数"被读成"通过的另一种写法"
    log(`SKIPPED (未验证，不代表通过)：${skippedIds.join(", ")} —— 缺素材，本机跑 --require-materials 可补齐`);
  }
  const verdictText = fail === 0 ? "HANDSHAKE SMOKE PASS" : "HANDSHAKE SMOKE FAIL";
  // A-24：headline 显式带 (skip=N)，别让 PASS 被读成"全测过"；不翻 FAIL、不改 rc。
  const skipNote = skip > 0 ? ` (skip=${skip}，SKIPPED 未验证、不代表通过)` : "";
  log(`VERDICT: ${verdictText}${skipNote} (pass=${pass} fail=${fail} skip=${skip})`);
  writeStepSummary();
  return fail === 0 ? 0 : 1;
}

try {
  const code = await main();
  if (!ciMode) {
    mkdirSync(EVIDENCE_DIR, { recursive: true });
    writeFileSync(path.join(EVIDENCE_DIR, "handshake.log"), logLines.join("\n") + "\n", "utf8");
  }
  process.exit(code);
} catch (err) {
  log(`[FATAL] ${err?.stack || err}`);
  log("VERDICT: HANDSHAKE SMOKE FAIL (exception)");
  try {
    if (!ciMode) {
      mkdirSync(EVIDENCE_DIR, { recursive: true });
      writeFileSync(path.join(EVIDENCE_DIR, "handshake.log"), logLines.join("\n") + "\n", "utf8");
    }
  } catch {
    /* 忽略落盘失败 */
  }
  process.exit(1);
}
