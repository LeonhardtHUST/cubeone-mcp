// cubeone-mcp — Node 层最小单测（R-D1）
//
// 0.7.0 基线（M2 安全加固，行为变更版）：**未设白名单默认拒绝**（fail-closed，R-C1），
// 只有显式设 CUBEONE_ALLOW_NO_ROOTS=1 才回到 0.6.x 的宽松语义；白名单比较改用物理路径（R-C2）。
//
// 覆盖 6 组门禁逻辑 + 1 组环境派生（合计 37 例）：
//   组1 isExecFailure  退出码矩阵 11 例（R-B1，含 [not-found] 例外白名单正反两面）
//   组2 checkPath      路径白名单 9 例（前缀撞车 / `..` 越界 / win32 大小写 /
//                      roots 未设 fail-closed 三例（R-C1）/ 物理路径两例（R-C2））
//   组3 buildArgs      参数组装 5 例（R-B4 的 `--` 分隔）
//   组4 validateArgs   入口校验 5 例（R-B3，缺 required / enum / 类型 / 条件必填）
//   组5 e2e            真实 stdio 1 例（SDK Client，不依赖 Python）
//   组5b e2e fail-closed 1 例（R-C1 的可观察面：无 roots 无逃生门 → 调用被拒）
//   组6 启动期 opt-in  2 例（CUBEONE_REQUIRE_ROOTS=1 的 fail-closed 与不误伤）
//   组7 requireRoots 取值 1 例（'1'/'true'/'yes' 与 '0'/空/乱值的解析边界）
//   附  policy/allowedRoots 2 例（环境派生，顺带守住 env 读取时机）
//
// 运行：node --test tests/node/
// 零新依赖：只用 node:test / node:assert/strict / child_process 与已安装的 @modelcontextprotocol/sdk。

import { test, describe, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, mkdirSync, readdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

import {
  isExecFailure,
  checkPath,
  buildArgs,
  validateArgs,
  policy,
  allowedRoots,
  requireRootsEnabled,
  TOOL_DEFS,
} from "../../lib/server.mjs";

const REPO_ROOT = fileURLToPath(new URL("../../", import.meta.url));
const BIN = path.join(REPO_ROOT, "bin", "cubeone-mcp.mjs");

// ── 测试脚手架 ──────────────────────────────────────────────────────

const TMP = mkdtempSync(path.join(os.tmpdir(), "cubeone-test-"));
after(() => rmSync(TMP, { recursive: true, force: true }));

function tmpDir(name) {
  const dir = path.join(TMP, name);
  mkdirSync(dir, { recursive: true });
  return dir;
}

/**
 * 临时改写环境变量后执行 fn（同步），无论成败都还原，避免用例间互相污染。
 * 值传 undefined 表示删除该变量。
 */
function withEnv(pairs, fn) {
  const saved = new Map();
  for (const [key, value] of Object.entries(pairs)) {
    saved.set(key, process.env[key]);
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  try {
    return fn();
  } finally {
    for (const [key, value] of saved) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

/** 基于 process.env 派生一份子进程 env（值 undefined = 删除该变量）。 */
function childEnv(overrides) {
  const env = { ...process.env };
  for (const [key, value] of Object.entries(overrides)) {
    if (value === undefined) delete env[key];
    else env[key] = value;
  }
  return env;
}

/** 把 roots 数组拼成 CUBEONE_ALLOWED_ROOTS 的值（平台分隔符）。 */
function rootsEnv(...dirs) {
  return dirs.join(path.delimiter);
}

function countFlag(args, flag) {
  return args.filter((a) => a === flag).length;
}

/**
 * validateArgs 的失败返回值取文本。
 * 规格文档给了两种形状（R-B3 计划书写的是 textResult 对象，任务书写的 string），
 * 这里两种都接受，只断言"有可读错误文案"，不做形状绑定；形状一旦定稿可在此收窄。
 */
function errorText(v) {
  if (typeof v === "string") return v;
  if (v && Array.isArray(v.content)) {
    return v.content.map((c) => (typeof c?.text === "string" ? c.text : "")).join("\n");
  }
  return null;
}

// ── 组1 · isExecFailure 退出码矩阵（R-B1，8 例） ───────────────────

describe("组1 isExecFailure 退出码矩阵（R-B1）", () => {
  test("组1-1 status=0 且无结构化 JSON → 不算执行失败", () => {
    assert.equal(isExecFailure({ status: 0, stdout: "ok", stderr: "" }, null), false);
  });

  test("组1-2 status=1 且有结构化 JSON → 域内 FAIL 是结论，不是执行失败", () => {
    const res = { status: 1, stdout: "", stderr: "" };
    assert.equal(isExecFailure(res, { verdict: "fail" }), false);
  });

  test("组1-4 status=1 有 JSON 但 stderr 含 Traceback → 执行失败", () => {
    const res = {
      status: 1,
      stdout: "",
      stderr: 'Traceback (most recent call last):\n  File "verify_generation.py", line 12\nKeyError: x\n',
    };
    assert.equal(isExecFailure(res, { verdict: "pass" }), true);
  });

  test("组1-5 status=2（输入错误）→ 执行失败", () => {
    assert.equal(isExecFailure({ status: 2, stdout: "", stderr: "" }, null), true);
  });

  test("组1-6 status=9009（WindowsApps Python 商店桩）→ 执行失败", () => {
    assert.equal(isExecFailure({ status: 9009, stdout: "", stderr: "" }, null), true);
  });

  test("组1-7 status=null（被信号杀死 / 超时强杀）→ 执行失败", () => {
    assert.equal(isExecFailure({ status: null, stdout: "", stderr: "" }, null), true);
  });

  test("组1-8 res.error 存在（ENOENT）→ 执行失败", () => {
    const res = { error: { code: "ENOENT", message: "spawn python ENOENT" }, status: null };
    assert.equal(isExecFailure(res, null), true);
  });

  // ── 例外白名单：[not-found] 是域内结论，不是崩溃 ──────────────────
  // ioc_field.py:220/234 与 ioc_backup.py:235/251 在「键 / 目标不存在」时**在写 --json-out 之前**
  // 就 return 1，因此 structured 必为 null。若只按「exit 1 + 无 JSON」判死，会把"查不到键"
  // 降级成"执行层失败"，让调用方去查 Python 环境而不是改参数。
  // 唯一可靠判据是脚本自己打的固定标记 `[<tool>][not-found]`——不能靠中文文案或退出码本身。

  test("组1-9 ioc_field 的 [not-found] 是域内结论 → 不算执行失败", () => {
    const res = {
      status: 1,
      stdout: "",
      stderr: "[ioc_field][not-found] ProjectManager.Nope 不存在于 /x/board.ioc\n",
    };
    assert.equal(isExecFailure(res, null), false);
  });

  test("组1-10 exit 1 但无 [not-found] 标记 → 仍是执行失败（白名单不得过宽）", () => {
    // 合并了原 1-3（KeyError 无 traceback）与 1-10 两种真实裸崩溃形态，共用本分支：
    // 一个来自运行期异常，一个来自依赖缺失——两者都必须是 isError=true。
    const keyError = { status: 1, stdout: "", stderr: "KeyError: 'ProjectManager.Nope'\n" };
    const missingModule = {
      status: 1,
      stdout: "",
      stderr: "ModuleNotFoundError: No module named 'x'\n",
    };
    assert.equal(isExecFailure(keyError, null), true);
    assert.equal(isExecFailure(missingModule, null), true);
  });

  test("组1-11 ioc_backup 的 [not-found] 同样按域内结论处理（标记不得只认 ioc_field）", () => {
    const res = {
      status: 1,
      stdout: "",
      stderr: "[ioc_backup][not-found] 目录下没有 .ioc：/x/proj\n",
    };
    assert.equal(isExecFailure(res, null), false);
  });

  test("组1-12 任意工具标签的 [not-found] 都算域内结论（有意为之，非漏网）", () => {
    // 这条**故意**允许通用：`[<tool>][not-found]` 是脚本族的统一标记约定
    // （ioc_field.py:220/234、ioc_backup.py:235/251 同一形态），通配的只是"工具名"这一段，
    // 不是任意文本——`stderr` 里必须出现完整的 `[标签][not-found]` 结构才命中。
    // 为什么不怕被滥用：真崩溃在前面两道闸就已判死——
    //   ① res.error / status===null（ENOENT、超时、被信号杀）；
    //   ② status===1 时 Traceback 判定**优先于**标记判定（顺序见 isExecFailure 实现）；
    // 所以要靠这条"蒙混"成域内结论，得先绕开崩溃检测、再伪造出脚本的固定标记，
    // 代价远高于收益。若将来收窄成显式工具名，本用例的期望要反转为 true。
    const res = { status: 1, stdout: "", stderr: "[some_future_tool][not-found] 目标不存在\n" };
    assert.equal(isExecFailure(res, null), false);
  });
});

// ── 组2 · checkPath 路径白名单（9 例） ─────────────────────────────
//
// 0.7.0：默认 fail-closed，逃生门需显式（R-C1）。
// 「未设 roots」不再是"不校验"的暗示性提示，而是**明确拒绝**；想回到宽松语义必须
// 显式设 CUBEONE_ALLOW_NO_ROOTS=1 —— 这样"忘了配白名单"就不会悄悄变成"全盘可写"。

describe("组2 checkPath 路径白名单", () => {
  // 全部用临时目录构造，不依赖本机 D:\Projects 实际结构
  const proj = tmpDir("proj");
  const target = path.join(proj, "Core", "Src", "main.c");

  test("组2-1 白名单内路径 → 放行且 abs 为绝对路径", () => {
    withEnv({ CUBEONE_ALLOWED_ROOTS: rootsEnv(proj) }, () => {
      const chk = checkPath(target);
      assert.equal(chk.ok, true);
      assert.equal(chk.abs, path.resolve(target));
      assert.equal(path.isAbsolute(chk.abs), true);
    });
  });

  test("组2-2 前缀撞车（Projects vs ProjectsEvil）→ 拒绝", () => {
    const projects = tmpDir("Projects");
    const evil = path.join(TMP, "ProjectsEvil", "x.ioc"); // 前缀相同，但不是子目录
    withEnv({ CUBEONE_ALLOWED_ROOTS: rootsEnv(projects) }, () => {
      const chk = checkPath(evil);
      assert.equal(chk.ok, false, "前缀撞车必须拒绝：D:\\Projects 不得放行 D:\\ProjectsEvil");
      assert.equal(chk.abs, path.resolve(evil));
    });
  });

  test("组2-3 `..` 越界 → 拒绝", () => {
    const a = tmpDir("a");
    const escape = path.join(a, "..", "b", "x.ioc");
    withEnv({ CUBEONE_ALLOWED_ROOTS: rootsEnv(a) }, () => {
      const chk = checkPath(escape);
      assert.equal(chk.ok, false);
      assert.equal(chk.abs, path.resolve(TMP, "b", "x.ioc"), "abs 应是 resolve 后的真实落点");
    });
  });

  test(
    "组2-4 win32 大小写归一 → roots 小写 + 目标大写仍放行",
    { skip: process.platform !== "win32" && "大小写归一仅 win32 适用" },
    () => {
      const lower = path.join(TMP, "caseroot");
      const upper = path.join(TMP, "CASEROOT", "board.ioc");
      withEnv({ CUBEONE_ALLOWED_ROOTS: rootsEnv(lower) }, () => {
        const chk = checkPath(upper);
        assert.equal(chk.ok, true, `${upper} 应命中白名单 ${lower}（win32 不区分大小写）`);
      });
    },
  );

  // ── roots 未设：0.7.0 fail-closed 三态（R-C1） ────────────────────
  //
  // 三例合起来钉住一张完整的真值表，缺一条就会留下"半开"的缝：
  //   5a 都不设 → 拒绝（默认安全）
  //   5b 显式逃生门 → 放行且必须说明后果（宽松不能静默）
  //   5c 逃生门取值解析 → 只有真值才开，乱值不得当开

  test("组2-5a roots 未设 + 无逃生门 → 拒绝，且 reason 可机读为 no-roots", () => {
    withEnv({ CUBEONE_ALLOWED_ROOTS: undefined, CUBEONE_ALLOW_NO_ROOTS: undefined }, () => {
      const chk = checkPath(target);
      assert.equal(chk.ok, false, "0.7.0 默认 fail-closed：未设白名单必须拒绝路径参数");
      assert.equal(
        chk.reason,
        "no-roots",
        `调用方要能区分"没配白名单"与"配了但越界"，reason 必须是 "no-roots"，实际 ${JSON.stringify(chk.reason)}`,
      );
      assert.equal(chk.abs, path.resolve(target), "被拒时仍应回显解析后的绝对路径，便于排障");
      assert.equal(allowedRoots().length, 0);
    });
  });

  test("组2-5b roots 未设 + CUBEONE_ALLOW_NO_ROOTS=1 → 放行且 note 标注宽松模式", () => {
    withEnv({ CUBEONE_ALLOWED_ROOTS: undefined, CUBEONE_ALLOW_NO_ROOTS: "1" }, () => {
      const chk = checkPath(target);
      assert.equal(chk.ok, true, "逃生门开启后应恢复 0.6.x 的宽松语义");
      assert.ok(
        typeof chk.note === "string" && chk.note.length > 0,
        "宽松模式必须在 note 里说清后果，不允许静默放行",
      );
      assert.ok(
        /宽松|ALLOW_NO_ROOTS/.test(chk.note),
        `note 应标注宽松模式或点名逃生门变量，实际：${chk.note}`,
      );
    });
  });

  test("组2-5c 逃生门取值解析：'true'/' yes ' 同 5b；'0'/'false'/'whatever' 同 5a", () => {
    for (const value of ["true", " yes "]) {
      withEnv({ CUBEONE_ALLOWED_ROOTS: undefined, CUBEONE_ALLOW_NO_ROOTS: value }, () => {
        assert.equal(
          checkPath(target).ok,
          true,
          `CUBEONE_ALLOW_NO_ROOTS=${JSON.stringify(value)} 应视为开启（trim + 小写后比较）`,
        );
      });
    }
    for (const value of ["0", "false", "whatever"]) {
      withEnv({ CUBEONE_ALLOWED_ROOTS: undefined, CUBEONE_ALLOW_NO_ROOTS: value }, () => {
        const chk = checkPath(target);
        assert.equal(
          chk.ok,
          false,
          `CUBEONE_ALLOW_NO_ROOTS=${JSON.stringify(value)} 不是开启值，必须仍然 fail-closed（宁可少开，不可乱开）`,
        );
        assert.equal(chk.reason, "no-roots");
      });
    }
  });

  // ── R-C2：白名单必须比较物理路径，否则目录链接可绕出 ──────────────
  //
  // ⚠️ 前提：链接的**目标文件要真实存在**。realpathSync 只能解析存在的路径；
  // 目标不存在时实现会退化为词法 resolve（见 2-7），那种情况下链接绕出本来就不可见——
  // 那是"写操作目标常常还不存在"的取舍，不是漏检。所以 2-6 预先在界外建好 x.ioc。

  test("组2-6 界内链接指向界外 → 拒绝（R-C2 物理路径）", (t) => {
    const inside = tmpDir("rp-inside");
    const outside = tmpDir("rp-outside");
    const linkPath = path.join(inside, "link");
    const outsideFile = path.join(outside, "x.ioc");
    writeFileSync(outsideFile, "# 界外文件\n", "utf8");

    try {
      // win32 用 junction（不需要管理员/开发者模式）；POSIX 用 "dir"。
      symlinkSync(outside, linkPath, process.platform === "win32" ? "junction" : "dir");
    } catch (err) {
      // 建不了链接（EPERM/EACCES/ENOTSUP…）说明是环境限制，跳过比判红诚实
      t.skip(`无法创建目录链接（${err?.code || err?.message}），跳过本项：${err?.message || err}`);
      return;
    }

    const escaped = path.join(linkPath, "x.ioc");
    if (!existsSync(escaped)) {
      t.skip(`链接未生效（${escaped} 读不到），跳过本项`);
      return;
    }

    withEnv({ CUBEONE_ALLOWED_ROOTS: rootsEnv(inside), CUBEONE_ALLOW_NO_ROOTS: undefined }, () => {
      const chk = checkPath(escaped);
      assert.equal(
        chk.ok,
        false,
        `经界内链接绕到界外必须拒绝：${escaped} 物理落点是 ${outsideFile}，不在白名单 ${inside} 内`,
      );
    });
  });

  test("组2-7 白名单内不存在的路径 → 不因 realpath 失败而误拒", () => {
    const root = tmpDir("rp-missing");
    const ghost = path.join(root, "not", "yet", "board.ioc");
    withEnv({ CUBEONE_ALLOWED_ROOTS: rootsEnv(root), CUBEONE_ALLOW_NO_ROOTS: undefined }, () => {
      const chk = checkPath(ghost);
      assert.equal(
        chk.ok,
        true,
        "写操作的目标文件常常尚不存在；realpath 失败必须退化为词法 resolve，不能反过来拒绝",
      );
      // abs 的精确形态由组2-1 钉（那里目标同样是未创建路径），这里只要求是个绝对路径，
      // 免得把"abs 改取物理路径"这种实现选择误判成 bug。
      assert.equal(typeof chk.abs, "string");
      assert.equal(path.isAbsolute(chk.abs), true);
    });
  });
});

// ── 组3 · buildArgs 参数组装（R-B4，5 例） ─────────────────────────

describe("组3 buildArgs 参数组装（R-B4）", () => {
  const IOC = path.join(TMP, "board.ioc");

  test("组3-1 ioc_field get：`--` 在 --ioc 的值之后，action/key 在 `--` 之后，无 --dry-run", () => {
    const args = buildArgs("ioc_field", { ioc: IOC, action: "get", key: "Mcu.PinsNb" });
    const sep = args.indexOf("--");
    const iocVal = args.indexOf(IOC);

    assert.notEqual(sep, -1, `必须含 \`--\` 分隔符，实际 args=${JSON.stringify(args)}`);
    assert.ok(sep > iocVal, "`--` 必须排在 --ioc 的取值之后");
    assert.ok(args.indexOf("get") > sep, "action 必须在 `--` 之后");
    assert.ok(args.indexOf("Mcu.PinsNb") > sep, "key 必须在 `--` 之后");
    assert.equal(args.includes("--dry-run"), false, "get 不应带 --dry-run");
    assert.deepEqual(args, ["--ioc", IOC, "--", "get", "Mcu.PinsNb"]);
  });

  test("组3-2 ioc_field set value=\"-h\"：`-h` 落在 `--` 之后，不会被 argparse 当选项", () => {
    const args = buildArgs("ioc_field", {
      ioc: IOC,
      action: "set",
      key: "Mcu.Name",
      value: "-h",
    });
    const sep = args.indexOf("--");
    assert.notEqual(sep, -1);
    assert.ok(sep < args.indexOf("-h"), "`-h` 必须在 `--` 之后，否则会打印 help 假成功");
    assert.deepEqual(args, ["--ioc", IOC, "--", "set", "Mcu.Name", "-h"]);
  });

  test("组3-3 ioc_field set value=\"--dry-run\"：字面值在 `--` 之后，真选项在 `--` 之前", () => {
    const args = buildArgs("ioc_field", {
      ioc: IOC,
      action: "set",
      key: "Mcu.Name",
      value: "--dry-run",
      dry_run: true,
    });
    const sep = args.indexOf("--");
    const first = args.indexOf("--dry-run"); // 真选项
    const last = args.lastIndexOf("--dry-run"); // 字面值

    assert.notEqual(sep, -1);
    assert.ok(first < sep, `真 --dry-run 选项必须在 \`--\` 之前，实际 args=${JSON.stringify(args)}`);
    assert.ok(last > sep, "value 字面量 --dry-run 必须在 `--` 之后，否则会静默改写盘语义");
  });

  test("组3-4 ioc_field set + dry_run=true：--dry-run 排在 `--` 之前", () => {
    const args = buildArgs("ioc_field", {
      ioc: IOC,
      action: "set",
      key: "Mcu.Name",
      value: "STM32G474RETx",
      dry_run: true,
    });
    const sep = args.indexOf("--");
    const dryRun = args.indexOf("--dry-run");
    assert.notEqual(dryRun, -1, "dry_run=true 必须带 --dry-run");
    assert.ok(dryRun < sep, "选项必须在 `--` 之前");
    assert.equal(args[sep + 1], "set");
  });

  test("组3-5 verify_generation 数组型参数逐个透传，expect 空串不丢参数", () => {
    const args = buildArgs("verify_generation", {
      log: path.join(TMP, "gen.log"),
      main_c: path.join(TMP, "Core", "Src", "main.c"),
      mxproject: path.join(TMP, ".mxproject"),
      expect: "",
      expect_pins: ["PB0=GPIO_Output", "PC13=GPIO_Output"],
      allow_signal: ["VP_RIF_VS_RIF1", "VP_RIF_VS_RIF2"],
    });

    assert.equal(countFlag(args, "--expect-pins"), 2, `pins 应两组，实际 args=${JSON.stringify(args)}`);
    assert.equal(args[args.indexOf("--expect-pins") + 1], "PB0=GPIO_Output");
    assert.equal(args[args.lastIndexOf("--expect-pins") + 1], "PC13=GPIO_Output");

    assert.equal(countFlag(args, "--allow-signal"), 2);
    assert.equal(args[args.indexOf("--allow-signal") + 1], "VP_RIF_VS_RIF1");

    const expectIdx = args.indexOf("--expect");
    assert.notEqual(expectIdx, -1, "--expect 必须存在");
    assert.equal(args[expectIdx + 1], "", "expect 为空串时必须原样透传空串，不能丢参数");
  });
});

// ── 组4 · validateArgs 入口校验（R-B3，5 例） ──────────────────────

describe("组4 validateArgs 入口校验（R-B3）", () => {
  const VERIFY_FULL = {
    log: path.join(TMP, "gen.log"),
    main_c: path.join(TMP, "Core", "Src", "main.c"),
    mxproject: path.join(TMP, ".mxproject"),
    expect: "GPIO",
  };

  test("组4-1 verify_generation 传 {} → 非 null，点名四个缺参，且不含字面量 undefined", () => {
    const err = validateArgs("verify_generation", {});
    assert.notEqual(err, null);
    assert.notEqual(err, undefined);
    const text = errorText(err);
    assert.equal(typeof text, "string", "失败必须带可读错误文案");
    for (const field of ["log", "main_c", "mxproject", "expect"]) {
      assert.ok(text.includes(field), `错误文案应点名缺失字段 ${field}，实际：${text}`);
    }
    assert.equal(text.includes("undefined"), false, `不得把 undefined 透传给用户，实际：${text}`);
  });

  test("组4-2 expect 为空串是合法值 → 通过（null）", () => {
    const v = validateArgs("verify_generation", { ...VERIFY_FULL, expect: "" });
    assert.equal(v, null, `expect="" 应放行，实际返回：${JSON.stringify(v)}`);
  });

  test("组4-3 ioc_backup action=\"destroy\" 越界 enum → 非 null 且文案点名 action", () => {
    const err = validateArgs("ioc_backup", { project: TMP, action: "destroy" });
    assert.notEqual(err, null);
    const text = errorText(err);
    assert.ok(text.includes("action"), `错误文案应点名 action，实际：${text}`);
    assert.ok(
      /action|取值|enum/i.test(text),
      `错误文案应说明取值非法，实际：${text}`,
    );
  });

  test("组4-4 类型错误：expect_pins 传字符串 → 非 null 且点名 expect_pins（dry_run 同理）", () => {
    const badArray = validateArgs("verify_generation", {
      ...VERIFY_FULL,
      expect_pins: "PB0=GPIO_Output", // 应为 array
    });
    assert.notEqual(badArray, null);
    const textArray = errorText(badArray);
    assert.ok(textArray.includes("expect_pins"), `错误文案应点名 expect_pins，实际：${textArray}`);

    const badBool = validateArgs("ioc_field", {
      ioc: path.join(TMP, "board.ioc"),
      action: "get",
      key: "Mcu.Name",
      dry_run: "yes", // 应为 boolean
    });
    assert.notEqual(badBool, null);
    assert.ok(errorText(badBool).includes("dry_run"), "错误文案应点名 dry_run");
  });

  test("组4-5 ioc_field set 缺 value → 非 null 且点名 value；value 为空串 → 通过", () => {
    const ioc = path.join(TMP, "board.ioc");
    const missing = validateArgs("ioc_field", { ioc, action: "set", key: "Mcu.Name" });
    assert.notEqual(missing, null, "action=set 不给 value 必须被拒");
    assert.ok(errorText(missing).includes("value"), `错误文案应点名 value，实际：${errorText(missing)}`);

    const emptyOk = validateArgs("ioc_field", { ioc, action: "set", key: "Mcu.Name", value: "" });
    assert.equal(emptyOk, null, `value="" 是合法写入值，应放行，实际：${JSON.stringify(emptyOk)}`);
  });

  // W0-5 / A-8②：三个 schema 都写了 additionalProperties:false，旧实现却从不落地。
  test("组4-6 未知键拒绝：projectRoot ⇒ 列出合法键名并提示应写 project_root", () => {
    const err = validateArgs("verify_generation", { ...VERIFY_FULL, projectRoot: TMP });
    assert.notEqual(err, null, "未知键必须被拒（否则静默传到 Python 变成文件不存在）");
    const text = errorText(err);
    assert.ok(text.includes("projectRoot"), `文案应点名未知键，实际：${text}`);
    assert.ok(text.includes("project_root"), `文案应给出正确键名，实际：${text}`);
    assert.ok(text.includes("inputSchema"), `文案应指向 inputSchema，实际：${text}`);
    assert.equal(err.isError, true, "未知键必须是 isError=true 的可机读错误");

    // 正确拼写仍放行，别把规则做成"一律拒绝额外键"的误伤
    const ok = validateArgs("verify_generation", { ...VERIFY_FULL, project_root: TMP });
    assert.equal(ok, null, `project_root 是合法键，应放行，实际：${JSON.stringify(ok)}`);
  });

  // W0-1 / A-11：CLI 侧对同一组合退 2，MCP 侧提前给可机读错误、避免无谓 spawn。
  test("组4-7 expect_pins 与 ioc 联动：给了 pins 缺 ioc 被拒，补齐后放行", () => {
    const err = validateArgs("verify_generation", {
      ...VERIFY_FULL,
      expect_pins: ["PC13=GPIO_Output"],
    });
    assert.notEqual(err, null, "expect_pins 有而 ioc 无必须被拒");
    const text = errorText(err);
    assert.ok(text.includes("expect_pins") && text.includes("ioc"), `文案应点名两个参数，实际：${text}`);
    assert.equal(err.isError, true);

    const ok = validateArgs("verify_generation", {
      ...VERIFY_FULL,
      expect_pins: ["PC13=GPIO_Output"],
      ioc: path.join(TMP, "board.ioc"),
    });
    assert.equal(ok, null, `两者齐备应放行，实际：${JSON.stringify(ok)}`);
  });
});

// ── 组5 · e2e 真实 stdio（1 例，不依赖 Python） ────────────────────
//
// 本用例刻意留空 CUBEONE_ALLOWED_ROOTS 也不开逃生门：它验的是「参数校验发生在
// 门禁之前」——空参数必须报"缺 log"，而不是先报"越界"。这条顺序是 0.6.x 既有的
// 有意设计（参数形状不对时，越界/策略文案只会误导），0.7.0 的 fail-closed 不该改变它。

describe("组5 e2e 真实 stdio（SDK Client）", () => {
  test("组5-1 initialize → tools/list 3 工具且 required 非空 → 空参数调用报参数错误", async (t) => {
    const transport = new StdioClientTransport({
      command: process.execPath,
      args: [BIN],
      env: {
        ...process.env,
        CUBEONE_POLICY: "read_only",
        CUBEONE_ALLOWED_ROOTS: "", // 显式清空，避免继承宿主环境导致越界拦截干扰本用例
      },
      stderr: "pipe",
    });
    const client = new Client({ name: "cubeone-node-test", version: "0.0.0" }, { timeout: 60_000 });

    await client.connect(transport);
    t.after(async () => {
      await client.close();
    });

    // T1 tools/list：3 个工具，required 均非空，且与 TOOL_DEFS 同名同数
    const { tools } = await client.listTools();
    assert.equal(tools.length, 3, `工具数应为 3，实际 ${tools.length}`);
    assert.deepEqual(
      tools.map((x) => x.name).sort(),
      TOOL_DEFS.map((x) => x.name).sort(),
      "tools/list 与 TOOL_DEFS 必须一致",
    );
    for (const tool of tools) {
      const required = tool.inputSchema?.required;
      assert.ok(Array.isArray(required) && required.length > 0, `${tool.name} 的 required 不应为空`);
    }

    // T2 空参数 → validateArgs 前置拦截，走不到 spawn Python
    const res = await client.callTool({ name: "verify_generation", arguments: {} });
    assert.equal(res.isError, true, "空参数调用必须 isError=true");
    const text = (res.content || [])
      .filter((c) => c.type === "text")
      .map((c) => c.text)
      .join("\n");
    assert.equal(text.includes("undefined"), false, `错误文案不得含 undefined，实际：${text}`);
    assert.ok(text.includes("log"), `错误文案应点名缺失字段 log，实际：${text}`);
  });
});

// ── 组5b · e2e fail-closed 可观察面（R-C1，1 例） ──────────────────
//
// 组2 测的是 checkPath 的**返回对象**；这一组测**用户真的看到什么**。
// 两者必须分别钉：返回对象对了但 gateArgs 把 roots 拼成空串，用户看到的是
// "白名单：" 后面什么都没有 —— 比不提示还糟（会让人以为工具坏了）。
//
// 本组只依赖"起得来 + 调用被拒"，不需要 Python（门禁在 spawn 之前），
// 所以它同时是"默认 fail-closed 不会把 server 卡死在启动阶段"的守卫。

/** 在 testbeds 下找一份真实 `.ioc`；找不到返回 null（调用方跳过，不判红）。 */
function findRealIoc() {
  const candidates = [
    path.join(REPO_ROOT, "testbeds", "_verifier-regen", "g474"),
    path.join(REPO_ROOT, "testbeds", "stm32-g474-template"),
  ];
  for (const dir of candidates) {
    if (!existsSync(dir)) continue;
    const hit = readdirSync(dir).find((f) => f.endsWith(".ioc"));
    if (hit) return path.join(dir, hit);
  }
  return null;
}

describe("组5b e2e fail-closed（无白名单被拒，R-C1）", () => {
  test("组5b-1 不设 roots 也不设逃生门 → ioc_field get 被拒且文案点名两个变量", async (t) => {
    const ioc = findRealIoc();
    if (!ioc) {
      t.skip("testbeds 下找不到真实 .ioc 素材，跳过本项");
      return;
    }

    const transport = new StdioClientTransport({
      command: process.execPath,
      args: [BIN],
      // 三个变量都真正删除（空串不等于删除：合法的空 roots 与"没配"必须走同一分支，
      // 但这里要模拟的是**完全没配**的用户，删掉才是真实场景）。
      // REQUIRE_ROOTS 一并删掉：它会让进程启动即退出，那样本用例会变成"连不上"而不是
      // "连上了但调用被拒"——测的就不是默认行为了。
      env: childEnv({
        CUBEONE_ALLOWED_ROOTS: undefined,
        CUBEONE_ALLOW_NO_ROOTS: undefined,
        CUBEONE_REQUIRE_ROOTS: undefined,
      }),
      stderr: "pipe",
    });
    const client = new Client({ name: "cubeone-node-test-noroots", version: "0.0.0" }, { timeout: 60_000 });

    await client.connect(transport);
    t.after(async () => {
      await client.close();
    });

    const res = await client.callTool({
      name: "ioc_field",
      arguments: { ioc, action: "get", key: "MxCube.Version" },
    });
    assert.equal(res.isError, true, `未配白名单时必须拒绝，实际放行了 ${ioc}`);

    const text = (res.content || [])
      .filter((c) => c.type === "text")
      .map((c) => c.text)
      .join("\n");
    assert.ok(
      text.includes("CUBEONE_ALLOWED_ROOTS"),
      `文案必须告诉用户配哪个变量（否则会去改路径），实际：${text}`,
    );
    assert.ok(
      text.includes("CUBEONE_ALLOW_NO_ROOTS"),
      `文案必须给出逃生门，否则从 0.6.x 升上来的用户只有"报错"没有"出路"，实际：${text}`,
    );
    assert.equal(text.includes("undefined"), false, `文案不得透出 undefined，实际：${text}`);
  });
});

// ── 组6 · 启动期 opt-in 严格模式（CUBEONE_REQUIRE_ROOTS=1，2 例） ──
//
// 0.6.2 的白名单是 fail-open（未配 roots = 不校验），危险在于**连提示都不给**。
// 这一组守两件事：
//   6-1 显式 opt-in 后，没配 roots 必须**拒绝启动**并说明怎么配（fail-closed 不得静默）；
//   6-2 opt-in 不能误伤正常配置（配了 roots 就必须照常起得来）。
// 注意区分两种"拒绝"：本组是**启动期**拒绝（进程退出，严格模式 opt-in 才有）；
// 0.7.0 的默认 fail-closed 是**调用期**拒绝（进程照常起，路径参数被拒）——
// 后者由组5-1（能起来）与组5b（起得来但调用被拒）共同兜住。

describe("组6 启动期 opt-in 严格模式（CUBEONE_REQUIRE_ROOTS=1）", () => {
  test("组6-1 未配 roots + REQUIRE_ROOTS=1 → 拒绝启动，并在 stderr 说明怎么配", async (t) => {
    const child = spawn(process.execPath, [BIN], {
      cwd: REPO_ROOT,
      // 关键：把 CUBEONE_ALLOWED_ROOTS 从继承环境里真正删掉（空串不等于删除，不可用于本用例）
      env: childEnv({ CUBEONE_ALLOWED_ROOTS: undefined, CUBEONE_REQUIRE_ROOTS: "1" }),
      stdio: ["pipe", "pipe", "pipe"],
    });
    t.after(() => {
      try {
        child.kill();
      } catch {
        /* 已退出 */
      }
    });

    let stderr = "";
    let stdout = "";
    child.stderr.setEncoding("utf8");
    child.stdout.setEncoding("utf8");
    child.stderr.on("data", (d) => (stderr += d));
    child.stdout.on("data", (d) => (stdout += d));

    const outcome = await new Promise((resolve) => {
      const timer = setTimeout(() => {
        child.kill();
        resolve({ timedOut: true, stderr, stdout });
      }, 10_000);
      child.on("exit", (code, signal) => {
        clearTimeout(timer);
        resolve({ code, signal, stderr, stdout });
      });
      child.on("error", (err) => {
        clearTimeout(timer);
        resolve({ error: err, stderr, stdout });
      });
    });

    assert.equal(outcome.timedOut, undefined, `进程 10s 内未退出——极可能是静默启动了：stderr=${outcome.stderr}`);
    assert.equal(outcome.error, undefined, `子进程启动失败：${outcome.error && outcome.error.message}`);
    // 退出码非 0 是硬要求；具体值按实现（1 或 2 都合法），这里只钉"非 0"，
    // 免得把"用 2 表示配置错误"这种合理选择判成 bug。
    assert.notEqual(outcome.code, 0, `必须拒绝启动，实际 exitCode=${outcome.code}；stderr=${outcome.stderr}`);
    assert.equal(typeof outcome.code, "number", `应是正常退出而非被信号杀死，signal=${outcome.signal}`);
    assert.ok(
      /CUBEONE_ALLOWED_ROOTS/.test(outcome.stderr),
      `拒绝启动时必须告诉用户配哪个变量，实际 stderr=${JSON.stringify(outcome.stderr)}`,
    );
    // 交互面卫生：拒绝启动的提示绝不能跑到 stdout（stdout 是 JSON-RPC 通道）
    assert.equal(
      /CUBEONE_ALLOWED_ROOTS/.test(outcome.stdout),
      false,
      `提示不得写进 stdout（会污染 JSON-RPC），实际 stdout=${JSON.stringify(outcome.stdout)}`,
    );
  });

  test("组6-2 配了 roots + REQUIRE_ROOTS=1 → 正常启动并可用（opt-in 不误伤）", async (t) => {
    const roots = tmpDir("require-roots-ok");
    const transport = new StdioClientTransport({
      command: process.execPath,
      args: [BIN],
      env: childEnv({
        CUBEONE_ALLOWED_ROOTS: roots,
        CUBEONE_REQUIRE_ROOTS: "1",
        CUBEONE_POLICY: "read_only",
      }),
      stderr: "pipe",
    });
    const client = new Client({ name: "cubeone-node-test-ro", version: "0.0.0" }, { timeout: 60_000 });

    await client.connect(transport);
    t.after(async () => {
      await client.close();
    });

    const { tools } = await client.listTools();
    assert.equal(tools.length, 3, `配了 roots 时应正常暴露 3 个工具，实际 ${tools.length}`);
    assert.deepEqual(
      tools.map((x) => x.name).sort(),
      ["ioc_backup", "ioc_field", "verify_generation"],
    );
  });
});

// ── 组7 · requireRootsEnabled 取值解析（R-C1 第一步，1 例） ────────
//
// 组6 只走 env="1" 这一条端到端路径，解析器的宽窄没被钉住：
// 若有人把它"简化"成 v === "1"，文档承诺的 'true'/'yes' 会静默失效——
// 表现是"设了 CUBEONE_REQUIRE_ROOTS=true 却仍然 fail-open"，属于最难排查的那类静默降级。
// 这里只测纯函数（不 spawn），避免 process.exit(1) 带走 test runner。

describe("组7 requireRootsEnabled 取值解析", () => {
  test("组7-1 '1'/'true'/'yes'（大小写、空白容忍）→ true；'0'/空/未设/乱值 → false", () => {
    const cases = [
      [undefined, false, "未设"],
      ["", false, "空串"],
      ["   ", false, "纯空白"],
      ["0", false, "0 视为关闭"],
      ["false", false, "false"],
      ["whatever", false, "乱值不得当开启"],
      ["1", true, "1"],
      ["true", true, "true"],
      ["TRUE", true, "大写"],
      [" yes ", true, "小写带空白"],
    ];
    for (const [value, expected, label] of cases) {
      withEnv({ CUBEONE_REQUIRE_ROOTS: value }, () => {
        assert.equal(
          requireRootsEnabled(),
          expected,
          `CUBEONE_REQUIRE_ROOTS=${JSON.stringify(value)}（${label}）应得 ${expected}`,
        );
      });
    }
  });
});

// ── 附 · 环境派生配置（2 例） ─────────────────────────────────────

describe("附 policy / allowedRoots 环境派生", () => {
  test("附-1 policy：默认 read_only，仅 full（大小写/空白容忍）才升级", () => {
    withEnv({ CUBEONE_POLICY: undefined }, () => assert.equal(policy(), "read_only"));
    withEnv({ CUBEONE_POLICY: "  FULL  " }, () => assert.equal(policy(), "full"));
    withEnv({ CUBEONE_POLICY: "whatever" }, () => assert.equal(policy(), "read_only"));
    withEnv({ CUBEONE_POLICY: "full" }, () => assert.equal(policy(), "full"));
  });

  test("附-2 allowedRoots：按 path.delimiter 切分、去空白、绝对化；未设 → []", () => {
    const r1 = tmpDir("r1");
    const r2 = tmpDir("r2");
    // win32 上 allowedRoots 会小写归一（与 checkPath 的 norm 对齐），期望值随之归一
    const norm = (p) => (process.platform === "win32" ? path.resolve(p).toLowerCase() : path.resolve(p));
    withEnv({ CUBEONE_ALLOWED_ROOTS: ` ${r1} ${path.delimiter} ${r2} ${path.delimiter}` }, () => {
      assert.deepEqual(allowedRoots(), [norm(r1), norm(r2)]);
    });
    withEnv({ CUBEONE_ALLOWED_ROOTS: undefined }, () => assert.deepEqual(allowedRoots(), []));
  });
});
