# -*- coding: utf-8 -*-
"""``tools/*`` 的编码加固回归（B-5 / 0.7.4，C 组）。

为什么单独一个文件
------------------
`scripts/` 三个脚本的编码加固已有 ``tests/test_console_encoding.py`` 守着（10 例），
但**门禁脚本 `tools/*` 一直没被覆盖**：它们是发版前必跑的四条命令之一，却长期只在
"本机代码页恰好是 UTF-8" 的环境里被执行过。审定报告 §4.7 把它记为 **B-5**。

本文件守四件事：

1. **文档是坏字节也不毁结论**：`check_taskboard.py` 读 GBK 编码的看板、
   `check_release.py` 读坏字节文本时用 ``errors="replace"``，**给结论**而不是抛
   ``UnicodeDecodeError``（判据/门禁的价值在于"回答问题"，不在于"报告文件坏了"）。
2. **管道强制 UTF-8**：``PYTHONIOENCODING=cp1252`` 污染下，非 TTY 输出仍必须是可解析的
   UTF-8 —— 否则 CI 日志与下游脚本拿到的是 ``\\u2713`` 或直接崩。
3. **TTY 分支不参与自动回归**（与 `scripts/` 的口径一致）：cp936 控制台的可读性只能人工核，
   这里只机械验证**分支选择**（`isatty()` 为真时只改 errors、不改 encoding）。
4. **非 UTF-8 环境不崩**：`tools/npm_mcp_handshake.mjs` 在 ``LANG=C`` +
   ``PYTHONIOENCODING=cp1252`` 下仍给出可读的中文错误与稳定退出码（Node 写 UTF-8 字节，
   不按控制台代码页转码 —— 这与 Python 侧的失败模式不同，值得钉住）。

⚠️ 本文件**只验编码与异常处理**，不验任何判据语义；判据的用例在
`tests/test_check_release.py`（P4）与 `tools/check_*.py` 自身的既有覆盖里。
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
CHECK_RELEASE = TOOLS / "check_release.py"
CHECK_TASKBOARD = TOOLS / "check_taskboard.py"
HANDSHAKE = TOOLS / "npm_mcp_handshake.mjs"

#: `node` 可执行（部分环境没有）。
NODE = shutil.which("node")
#: MCP SDK 是否已安装。**`npm_mcp_handshake.mjs` 一开头就 `import @modelcontextprotocol/sdk`**，
#: ESM 的静态 import 在**模块体执行前**求值 ⇒ 没装依赖时连参数校验都到不了，进程直接以
#: `ERR_MODULE_NOT_FOUND` 退 1。
#: ⚠️ CI 的 **pytest job 不跑 `npm ci`**（只有 node job 跑），所以那条 Node 用例在 CI 上
#: **验证对象不可达**——按本仓惯例：**显式 SKIP 并说明原因**，而不是让它变成一条忽红忽绿的
#: 假失败（0.7.4 P3 首次推送就踩了这个：本机 154 passed，CI 三个 pytest/windows job 全红）。
SDK_INSTALLED = (REPO_ROOT / "node_modules" / "@modelcontextprotocol" / "sdk").is_dir()

#: 版本轴五处同值时的目标版本（取自 `package.json`，不写死数字 —— 发版换版本不会让本文件变红）。
CURRENT_VERSION = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))["version"]

#: 读副本所需的文件集（`check_release.py` 的判据①② 与台账项都靠它们）。
#: `package-lock.json` 自 0.7.4 起进判据①（五处机器可验），所以这里一起带上。
COPY_FILES = (
    "package.json",
    "package-lock.json",
    "SKILL.md",
    "README.md",
    "docs/releases/README.md",
)

#: 让 Python 侧与 Node 侧都处在"非 UTF-8 环境"下的 env 覆写。
HOSTILE_ENV = {
    "PYTHONIOENCODING": "cp1252",
    "PYTHONUTF8": "0",
    "LANG": "C",
    "LC_ALL": "C",
}


def _hostile_env() -> dict[str, str]:
    """返回叠加了 ``HOSTILE_ENV`` 的完整环境（保留 PATH 等必需项）。"""
    env = {**os.environ}
    env.update(HOSTILE_ENV)
    return env


def _run(argv: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    """跑一个子进程并**按字节**收输出（编码问题必须在字节层面看，不能先让 Python 猜）。"""
    return subprocess.run(
        argv,
        capture_output=True,
        timeout=180,
        check=False,
        cwd=str(REPO_ROOT),
        env=env,
    )


def _decode(raw: bytes) -> str:
    """按 UTF-8 解码；失败即测试失败（加固的目标就是"输出一定是 UTF-8"）。"""
    return raw.decode("utf-8")


def _assert_no_traceback(proc: subprocess.CompletedProcess[bytes]) -> None:
    """断言两个流里都没有未捕获异常（``traceback`` 才是"崩了"，非零退出不算崩）。"""
    text = _decode(proc.stdout) + _decode(proc.stderr)
    assert "Traceback (most recent call last)" not in text, text
    assert "UnicodeDecodeError" not in text, text
    assert "UnicodeEncodeError" not in text, text


def _make_repo_copy(dest: Path) -> Path:
    """把判据需要的少数几个文件拷进 ``dest``（含非 ASCII 路径时用它）。

    Args:
        dest: 目标目录（可以带中文/空格）。

    Returns:
        ``dest`` 本身，便于链式使用。
    """
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "docs" / "releases").mkdir(parents=True, exist_ok=True)
    for rel in COPY_FILES:
        shutil.copyfile(REPO_ROOT / rel, dest / rel)
    for note in sorted((REPO_ROOT / "docs" / "releases").glob("*.md")):
        shutil.copyfile(note, dest / "docs" / "releases" / note.name)
    return dest


# ── 1) 坏字节不毁结论 ────────────────────────────────────────────────────────


def test_check_taskboard_reads_gbk_board_without_crashing(tmp_path: Path) -> None:
    """GBK 编码的看板：给结论（rc=1，可读中文报错），不抛 ``UnicodeDecodeError``。

    看板是**人写的文档**：中文 Windows 上完全可能是 cp936/GBK 存盘。此时正确答案是
    「这不是一份可解析的看板」，而不是一条编码 traceback。
    """
    board = tmp_path / "board-gbk.md"
    board.write_bytes("# 看板\n\n这一段是 GBK 编码的中文，不是 UTF-8。\n".encode("gbk"))

    proc = _run([sys.executable, str(CHECK_TASKBOARD), "--board", str(board)])

    _assert_no_traceback(proc)
    assert proc.returncode == 1, proc.returncode
    # 该脚本的 `[error]` 走 stdout（既有行为，本批不改）
    stdout = _decode(proc.stdout)
    assert "没有解析到" in stdout, stdout


def test_check_taskboard_replaces_bad_bytes_in_status_cell(tmp_path: Path) -> None:
    """真实看板里一个**状态单元格**被写成 GBK：判据照样跑完，并指名那一行。

    这一条同时证明两件事：① 读文件用了 ``errors="replace"``（替换字符进了报错文案，
    而不是整份文件读取失败）；② 读不出来时**判红并点名行**，不是静默跳过整份看板
    —— 静默跳过等于把"没检查"读成"没问题"。
    """
    raw = (REPO_ROOT / "docs" / "TASKBOARD.md").read_bytes()
    needle = "| 已完成 |".encode("utf-8")
    assert needle in raw, "看板里没有 `| 已完成 |` 形态的状态单元格，本用例需随看板格式调整"
    garbled = b"| " + "已完成".encode("gbk") + b" |"
    board = tmp_path / "board-gbk-status.md"
    board.write_bytes(raw.replace(needle, garbled, 1))

    proc = _run([sys.executable, str(CHECK_TASKBOARD), "--board", str(board)])

    _assert_no_traceback(proc)
    assert proc.returncode == 1, proc.returncode
    stdout = _decode(proc.stdout)
    assert "不在六种取值内" in stdout, stdout
    assert "\ufffd" in stdout, "坏字节没有被替换成 U+FFFD —— errors='replace' 没生效"
    # 快照判据仍然跑完了（不是"读失败就整体放弃"）
    assert "§4 快照 ↔ 任务表" in stdout


def test_check_taskboard_reads_board_with_mixed_bytes(tmp_path: Path) -> None:
    """GBK 坏字节混在**正常看板**里：判据照样跑完，不崩。"""
    source = (REPO_ROOT / "docs" / "TASKBOARD.md").read_bytes()
    board = tmp_path / "board-mixed.md"
    # 在文件头部插一段 GBK 字节（等价于"有人用 cp936 编辑器在表前补了一行中文"）
    board.write_bytes("# 补记：中文备注\n".encode("gbk") + source)

    proc = _run([sys.executable, str(CHECK_TASKBOARD), "--board", str(board)])

    _assert_no_traceback(proc)
    assert proc.returncode in (0, 1), proc.returncode
    # 表在这个文件里是完整的，所以快照判据仍应通过
    assert "§4 快照 ↔ 任务表" in _decode(proc.stdout)


def test_read_text_replaces_invalid_bytes(tmp_path: Path) -> None:
    """`check_release.read_text()` 对坏字节返回替换字符，不抛异常（单元级）。"""
    module = _load_module("check_release", CHECK_RELEASE)
    bad = tmp_path / "bad.md"
    bad.write_bytes("版本号 0.7.3 —— 中文".encode("gbk"))

    text = module.read_text(bad)

    assert "\ufffd" in text
    assert "0.7.3" in text


def test_check_release_tolerates_non_utf8_package_json(tmp_path: Path) -> None:
    """`package.json` 被 GBK 写过：判据给结论（读不到 version ⇒ 判红），不抛异常。"""
    repo = _make_repo_copy(tmp_path / "repo-bad-json")
    (repo / "package.json").write_bytes('{"version": "0.7.3", "note": "中文"}'.encode("gbk"))

    proc = _run(
        [sys.executable, str(CHECK_RELEASE), "--repo-root", str(repo), "--tag", f"v{CURRENT_VERSION}"]
    )

    _assert_no_traceback(proc)
    assert proc.returncode in (0, 1), proc.returncode
    # version 字段本身是 ASCII，仍能读出来 ⇒ 判据① 可判（这里只要求"有结论"）
    assert "判据① 版本轴同值" in _decode(proc.stdout)


# ── 2) 管道强制 UTF-8 ───────────────────────────────────────────────────────


def test_check_release_forces_utf8_on_pipe(tmp_path: Path) -> None:
    """``PYTHONIOENCODING=cp1252`` 下，管道输出仍是 UTF-8（``✓`` 不得变成转义或崩溃）。"""
    repo = _make_repo_copy(tmp_path / "repo-encoding")

    proc = _run(
        [sys.executable, str(CHECK_RELEASE), "--repo-root", str(repo), "--tag", f"v{CURRENT_VERSION}"],
        env=_hostile_env(),
    )

    _assert_no_traceback(proc)
    assert proc.returncode == 0, _decode(proc.stdout) + _decode(proc.stderr)
    stdout = _decode(proc.stdout)  # 硬断言：字节就是 UTF-8
    assert "✓ 版本轴同值" in stdout
    assert "\\u2713" not in stdout, "输出被降级成转义序列（errors=backslashreplace 用错了分支）"


def test_check_taskboard_forces_utf8_on_pipe(tmp_path: Path) -> None:
    """同一分流逻辑在 `check_taskboard.py` 上生效（管道 ⇒ UTF-8）。"""
    proc = _run(
        [sys.executable, str(CHECK_TASKBOARD)],
        env=_hostile_env(),
    )

    _assert_no_traceback(proc)
    stdout = _decode(proc.stdout)
    assert proc.returncode == 0, stdout + _decode(proc.stderr)
    assert "三组判据全部通过" in stdout


def test_harden_console_streams_picks_branch_by_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """TTY / 管道**分支选择**机械验证：TTY 只改 errors，管道同时强制 encoding。

    TTY 的"视觉正确"没有自动回归（本机代码页是 UTF-8，造不出 cp936 分支），
    但"选了哪个分支"可以逐字比对 —— 与 `tests/test_console_encoding.py` 同款做法。
    """

    class _FakeStream:
        def __init__(self, tty: bool) -> None:
            self._tty = tty
            self.calls: list[dict[str, object]] = []

        def isatty(self) -> bool:
            return self._tty

        def reconfigure(self, **kwargs: object) -> None:
            self.calls.append(kwargs)

    for module_name, path in (("check_release", CHECK_RELEASE), ("check_taskboard", CHECK_TASKBOARD)):
        module = _load_module(module_name, path)
        for tty, expected in (
            (True, {"errors": "backslashreplace"}),
            (False, {"encoding": "utf-8", "errors": "backslashreplace"}),
        ):
            fake_out, fake_err = _FakeStream(tty), _FakeStream(tty)
            monkeypatch.setattr(module.sys, "stdout", fake_out, raising=False)
            monkeypatch.setattr(module.sys, "stderr", fake_err, raising=False)
            module._harden_console_streams()
            assert fake_out.calls == [expected], f"{module_name} tty={tty}"
            assert fake_err.calls == [expected], f"{module_name} tty={tty}"


# ── 3) Node 侧非 UTF-8 环境不崩 ─────────────────────────────────────────────


@pytest.mark.skipif(
    NODE is None or not SDK_INSTALLED,
    reason=(
        "缺 node 或未安装 MCP SDK（CI 的 pytest job 不跑 npm ci ⇒ 验证对象不可达；"
        "本仓惯例是显式 SKIP 并说明原因，不是让它假红）"
    ),
)
def test_handshake_reports_readable_error_in_non_utf8_env() -> None:
    """``LANG=C`` + ``PYTHONIOENCODING=cp1252`` 下，未知参数仍给可读中文与稳定 rc=2。

    这一项刻意走**参数校验**路径（不拉 MCP server）：它只回答"Node 在非 UTF-8 环境下
    还能不能正常吐中文"。Node 写的是 UTF-8 字节、不按控制台代码页转码，所以这里
    **解码后必须没有替换字符**（有 ⇒ 说明字节确实被转码污染了）。

    ⚠️ 前置条件是 **SDK 已安装**：本文件以静态 `import` 引入 SDK，ESM 的 import 在模块体
    之前求值，没装依赖时进程退 1（`ERR_MODULE_NOT_FOUND`）而**不是**退 2 ⇒ 断言会变成
    一条与本用例意图无关的假失败。故用 ``skipif`` 把"验证对象不可达"显式说出来。
    """
    proc = _run([NODE or "node", str(HANDSHAKE), "--not-a-flag"], env=_hostile_env())

    _assert_no_traceback(proc)
    assert proc.returncode == 2, proc.returncode
    stderr = _decode(proc.stderr)
    assert "未知参数" in stderr, stderr
    assert "\ufffd" not in stderr, stderr


# ── 工具：按路径加载模块（`tools/` 不是包，也没有 conftest 注入 sys.path）────────


def _load_module(name: str, path: Path):
    """按文件路径加载一个模块（同名缓存会互相顶掉，所以调用方必须给不同的 ``name``）。

    ⚠️ 必须**先注册进 `sys.modules`** 再 `exec_module`：`check_release.py` 里有
    ``@dataclass``，而 dataclasses 解析注解时要按 ``cls.__module__`` 回查
    `sys.modules`；不注册会得到 ``AttributeError: 'NoneType' object has no attribute
    '__dict__'``——一个与本次改动完全无关、却会让人查半天的假失败。
    """
    spec = importlib.util.spec_from_file_location(f"_tools_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
