# -*- coding: utf-8 -*-
"""控制台/管道编码加固的回归用例（2026-11-04，Windows CI 两次抓到后的定稿版）。

两条教训（两版修法，别只记住最后一版）
--------------------------------------
- **第一版（缺加固）**：Windows 英文控制台编码是 cp1252，``print`` 遇到 ``→``/中文抛
  ``UnicodeEncodeError``，脚本 rc=1 —— CI `41682180849`。
- **第二版（只换 errors）**：把 ``errors`` 换成 ``backslashreplace`` 是**半对**：
  管道（非 TTY）的编码若也被污染成 cp1252，中文整体退化成 ``\\u7f3a`` 这类转义——
  **不崩但读不了**，而下游要的恰恰是中文原文。CI 因此再一次红
  （断言 ``"缺少完整性摘要" in stdout`` 失败）。

定稿语义（本文件锁死的就是它）：**管道要可解析，控制台要可阅读**
- **管道/重定向（非 TTY）→ 强制 UTF-8**：机器消费路径，UTF-8 唯一无歧义；
  MCP 封装层本来就按 UTF-8 解码。
- **TTY → 保留控制台自身编码**（中文 Windows = cp936），只换 ``errors``：
  该编码表示不了的字符转义成 ``\\u2192``，而不是崩。

TTY 那一支的覆盖边界
--------------------
真实 TTY 夹具的复杂度远超收益，所以本文件用**行为桩**（假 ``stdout`` 记录 ``reconfigure``
的入参）锁定"分支选择"这一层；**"在真实 cp936 控制台上中文确实正常"仍需人工核对**——
改动 ``_harden_console_streams()`` 后请手动在中文 Windows 控制台跑一次。
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

import ioc_backup as ib

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"

FAKE_IOC = """#MicroXplorer Configuration settings - do not modify
Mcu.CPN=STM32G474VET6
Mcu.PinsNb=2
Mcu.Pin0=PC13
PC13.GPIOParameters=PinState
PC13.PinState=GPIO_PIN_SET
PC13.Signal=GPIO_Output
ProjectManager.ProjectName=fake-board
ProjectManager.AskForMigrate=true
"""

#: 备份输出里的箭头；``restore`` 用 ``←``。
ESCAPED_ARROW = "\\u2192"


def polluted_env(io_encoding: str = "cp1252") -> dict[str, str]:
    """构造"外部把 stdio 编码钉成非 UTF-8"的环境。

    两个变量一起钉死才等价于真实污染：
    - ``PYTHONIOENCODING`` 让 Python 启动时就用该编码；
    - ``PYTHONUTF8=0`` 关掉 UTF-8 模式，否则宿主环境可能把它覆盖回 UTF-8，用例会**假绿**。

    Args:
        io_encoding: 冒充的 stdio 编码（``cp1252`` / ``ascii`` …）。

    Returns:
        可直接传给 ``subprocess.run(env=…)`` 的字典。
    """
    return {**os.environ, "PYTHONIOENCODING": io_encoding, "PYTHONUTF8": "0"}


def run_cli(script: str, *args: str, io_encoding: str = "cp1252") -> subprocess.CompletedProcess[str]:
    """以子进程方式跑真实 CLI，stdout/stderr 走**管道**（非 TTY）。

    父进程按 UTF-8 解码：这正是封装层的做法，也是"管道里应当是 UTF-8"这条契约的验证方式。

    Args:
        script: ``scripts/`` 下的脚本文件名。
        *args: 传给脚本的参数。
        io_encoding: 子进程被污染的 stdio 编码。

    Returns:
        ``CompletedProcess``。
    """
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *[str(item) for item in args]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=polluted_env(io_encoding),
        check=False,
    )


def make_project(tmp_path: Path) -> Path:
    """造一个只含一只 ``.ioc`` 的临时工程目录。"""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "board.ioc").write_text(FAKE_IOC, encoding="utf-8", newline="\n")
    return project


def assert_no_traceback(completed: subprocess.CompletedProcess[str]) -> None:
    """没有 Python 异常栈（有栈=脚本崩了，退出码再对也不算过）。"""
    assert "Traceback" not in completed.stderr, completed.stderr
    assert "Traceback" not in completed.stdout, completed.stdout
    assert "UnicodeEncodeError" not in completed.stderr, completed.stderr
    assert "UnicodeEncodeError" not in completed.stdout, completed.stdout


def test_pipe_output_is_utf8_so_chinese_and_arrows_stay_readable(tmp_path: Path) -> None:
    """管道路径：被污染成 cp1252 也必须输出**可读的 UTF-8**（不是转义）。"""
    project = make_project(tmp_path)

    backup = run_cli("ioc_backup.py", "--project", str(project))
    assert backup.returncode == 0, backup.stderr
    assert_no_traceback(backup)
    # 箭头必须是真字符；退化成 `\u2192` 说明又回到了"只换 errors"的半对修法
    assert "→" in backup.stdout, backup.stdout
    assert ESCAPED_ARROW not in backup.stdout, backup.stdout

    restore = run_cli("ioc_backup.py", "--project", str(project), "--restore")
    assert restore.returncode == 0, restore.stderr
    assert "←" in restore.stdout, restore.stdout


def test_restore_without_sidecar_warns_in_readable_chinese(tmp_path: Path) -> None:
    """**CI 上刚红的那条**：缺 sidecar 的告警是中文，管道路径下必须原样可读。

    复现方式：先备份（生成 ``.ioc.bak`` + ``.bak.sha256``），再删掉 sidecar 模拟旧版备份，
    然后 restore——脚本会打 ``[ioc_backup][warn] 缺少完整性摘要（旧版备份），已跳过校验``。
    第二版修法（只换 errors）在这里会把整句变成 ``\\u7f3a\\u5c11…``，断言因此失败。
    """
    project = make_project(tmp_path)
    assert run_cli("ioc_backup.py", "--project", str(project)).returncode == 0

    (project / "board.ioc.bak.sha256").unlink()
    restore = run_cli("ioc_backup.py", "--project", str(project), "--restore")

    assert restore.returncode == 0, restore.stderr
    assert_no_traceback(restore)
    assert "缺少完整性摘要" in restore.stdout, restore.stdout
    assert "\\u7f3a" not in restore.stdout, restore.stdout


@pytest.mark.parametrize("io_encoding", ["cp1252", "ascii", "cp936"])
def test_pipe_output_ignores_polluted_stdio_encoding(tmp_path: Path, io_encoding: str) -> None:
    """无论外部把 stdio 钉成什么编码，管道路径都必须给出 UTF-8（三种污染各验一次）。"""
    project = make_project(tmp_path)
    backup = run_cli("ioc_backup.py", "--project", str(project), io_encoding=io_encoding)
    assert backup.returncode == 0, backup.stderr
    assert "→" in backup.stdout, (io_encoding, backup.stdout)


def test_ioc_field_echo_is_readable_on_pipe(tmp_path: Path) -> None:
    """``ioc_field set`` 的回显行（``旧值 → 新值``）在管道路径下中文/箭头可读。"""
    project = make_project(tmp_path)
    ioc = project / "board.ioc"

    result = run_cli(
        "ioc_field.py", "--ioc", str(ioc), "set", "PC13.PinState", "GPIO_PIN_RESET"
    )
    assert result.returncode == 0, result.stderr
    assert_no_traceback(result)
    assert "→" in result.stdout, result.stdout
    assert "PC13.PinState=GPIO_PIN_RESET" in ioc.read_text(encoding="utf-8")


def test_verify_generation_error_message_is_readable_on_pipe(tmp_path: Path) -> None:
    """``verify_generation`` 的中文报错（stderr）在管道路径下必须可读。"""
    project = make_project(tmp_path)
    result = run_cli(
        "verify_generation.py",
        "--log", str(project / "no-such.log"),
        "--main-c", str(project / "Core" / "Src" / "main.c"),
        "--mxproject", str(project / ".mxproject"),
        "--expect", "GPIO",
    )
    assert result.returncode == 2, (result.returncode, result.stderr)
    assert_no_traceback(result)
    assert "指向的文件不存在" in result.stderr, result.stderr


class _FakeStream:
    """行为桩：记录 ``reconfigure`` 的入参，用来锁定"TTY vs 管道"的分支选择。

    真实 TTY 造不出来（也不值得造），但**分支条件**是可以机械验证的——
    这一层能防止"有人把 ``isatty()`` 判断写反/删掉"，剩下的"视觉正确"靠人工。
    """

    def __init__(self, is_a_tty: bool) -> None:
        self._is_a_tty = is_a_tty
        self.calls: list[dict[str, str]] = []

    def isatty(self) -> bool:
        """假装是不是终端。"""
        return self._is_a_tty

    def reconfigure(self, **kwargs: str) -> None:
        """记录调用参数。"""
        self.calls.append(dict(kwargs))


class _NoReconfigure:
    """没有 ``reconfigure`` 的对象（模拟 pytest capsys / 自定义重定向）。"""

    def isatty(self) -> bool:
        """按管道处理。"""
        return False


def harden_with(monkeypatch: pytest.MonkeyPatch, stdout_obj: object, stderr_obj: object) -> None:
    """把两个流替换成桩后调用被测函数。"""
    monkeypatch.setattr(sys, "stdout", stdout_obj)
    monkeypatch.setattr(sys, "stderr", stderr_obj)
    ib._harden_console_streams()


def test_tty_branch_keeps_console_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    """TTY 分支：**不换编码**，只换错误处理器（否则中文 Windows 的中文会变成转义）。"""
    out, err = _FakeStream(True), _FakeStream(True)
    harden_with(monkeypatch, out, err)
    assert out.calls == [{"errors": "backslashreplace"}]
    assert err.calls == [{"errors": "backslashreplace"}]


def test_pipe_branch_forces_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    """管道分支：强制 UTF-8 + backslashreplace（机器消费路径必须可解析）。"""
    out, err = _FakeStream(False), _FakeStream(False)
    harden_with(monkeypatch, out, err)
    assert out.calls == [{"encoding": "utf-8", "errors": "backslashreplace"}]
    assert err.calls == [{"encoding": "utf-8", "errors": "backslashreplace"}]


def test_stream_without_reconfigure_is_tolerated(monkeypatch: pytest.MonkeyPatch) -> None:
    """拿不到 ``reconfigure`` 时必须安静跳过（回到原行为，不新增崩溃点）。"""
    real_stdout = io.StringIO()
    harden_with(monkeypatch, _NoReconfigure(), real_stdout)  # 不应抛异常
