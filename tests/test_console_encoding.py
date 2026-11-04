# -*- coding: utf-8 -*-
"""控制台编码加固的回归用例（2026-11-04，Windows CI 首跑抓到的真缺陷）。

缺陷本体
--------
三个脚本的 stdout 里有 ``→`` ``←`` ``·`` ``—`` 与中文。**Windows 英文环境**的控制台编码是
**cp1252**（不是 UTF-8，也没有 ``PYTHONUTF8``），``print()`` 遇到这些字符会抛
``UnicodeEncodeError``，脚本**直接以 1 退出**：

    UnicodeEncodeError: 'charmap' codec can't encode character '\\u2192'

后果不是"显示难看"，而是**CLI 通道（不经 MCP，直接 ``python scripts/xxx.py``）在这类机器上必崩**
——用户看到的是"工具坏了"。MCP 通道没暴露只是因为封装层注入了 ``PYTHONIOENCODING=utf-8``。
本机是 UTF-8 代码页，所以本地永远复现不出来，**这也正是加 Windows CI 的价值**。

修法与用例的对应关系
--------------------
修法是在每个脚本 ``main()`` 开头把 ``stdout``/``stderr`` 的错误处理器改成 ``backslashreplace``
（只换 errors，不换 encoding）。因此本文件不依赖 Windows：用
``PYTHONIOENCODING=ascii`` 把"控制台编码不够"的场景**在任何平台**复现出来。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

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

#: 输出里必然出现 ``→`` 的转义形态。断言它存在有两个作用：
#: ① 证明"字符没被悄悄丢掉"（丢字符也是一种失真）；② 证明加固真的生效了——
#: 若加固缺失，进程会以 1 退出且 stdout 为空，这条断言会连带失败。
ESCAPED_ARROW = "\\u2192"


def ascii_console_env() -> dict[str, str]:
    """构造"控制台只能输出 ASCII"的环境。

    ``PYTHONUTF8=0`` 是必要的：若宿主环境开了 UTF-8 模式，``PYTHONIOENCODING`` 也可能被覆盖，
    那样这个用例会**假绿**（测不到真实场景）。两者一起钉死才等价于英文 Windows 控制台。
    """
    return {**os.environ, "PYTHONIOENCODING": "ascii", "PYTHONUTF8": "0"}


def run_cli_ascii(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    """以 ASCII-only 控制台跑一次真实 CLI。

    Args:
        script: ``scripts/`` 下的脚本文件名。
        *args: 传给脚本的参数。

    Returns:
        ``CompletedProcess``（``text=True``，按 UTF-8 解码——子进程输出此时全是 ASCII）。
    """
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *[str(item) for item in args]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=ascii_console_env(),
        check=False,
    )


def make_project(tmp_path: Path) -> Path:
    """造一个只含一只 ``.ioc`` 的临时工程目录。"""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "board.ioc").write_text(FAKE_IOC, encoding="utf-8", newline="\n")
    return project


def assert_no_traceback(completed: subprocess.CompletedProcess[str]) -> None:
    """断言输出里没有 Python 异常栈（有栈=脚本崩了，退出码再对也不算过）。"""
    assert "Traceback" not in completed.stderr, completed.stderr
    assert "Traceback" not in completed.stdout, completed.stdout
    assert "UnicodeEncodeError" not in completed.stderr, completed.stderr
    assert "UnicodeEncodeError" not in completed.stdout, completed.stdout


def test_ioc_backup_roundtrip_on_ascii_console(tmp_path: Path) -> None:
    """``ioc_backup`` 的备份 + 还原在 ASCII-only 控制台下的往返（原 CI 失败点）。"""
    project = make_project(tmp_path)

    backup = run_cli_ascii("ioc_backup.py", "--project", str(project))
    assert backup.returncode == 0, backup.stderr
    assert_no_traceback(backup)
    assert ESCAPED_ARROW in backup.stdout, backup.stdout
    assert backup.stdout.isascii(), backup.stdout

    listing = run_cli_ascii("ioc_backup.py", "--project", str(project), "--list")
    assert listing.returncode == 0, listing.stderr
    assert_no_traceback(listing)

    restore = run_cli_ascii("ioc_backup.py", "--project", str(project), "--restore")
    assert restore.returncode == 0, restore.stderr
    assert_no_traceback(restore)
    # 还原那一行用的是 `←`，同样必须被转义而不是把进程打死
    assert "\\u2190" in restore.stdout, restore.stdout
    assert restore.stdout.isascii(), restore.stdout


def test_ioc_field_set_on_ascii_console(tmp_path: Path) -> None:
    """``ioc_field set`` 的回显行（``旧值 → 新值``）在 ASCII-only 控制台下不许崩。"""
    project = make_project(tmp_path)
    ioc = project / "board.ioc"

    result = run_cli_ascii(
        "ioc_field.py", "--ioc", str(ioc), "set", "PC13.PinState", "GPIO_PIN_RESET"
    )
    assert result.returncode == 0, result.stderr
    assert_no_traceback(result)
    assert ESCAPED_ARROW in result.stdout, result.stdout
    assert result.stdout.isascii(), result.stdout
    # 写盘效果与编码无关：值必须真的改了
    assert "PC13.PinState=GPIO_PIN_RESET" in ioc.read_text(encoding="utf-8")


def test_verify_generation_error_text_on_ascii_console(tmp_path: Path) -> None:
    """``verify_generation`` 的中文报错（走 stderr）在 ASCII-only 控制台下不许崩。

    这里故意让它走**输入校验失败**分支：它是最容易被 Windows 用户撞到的路径
    （路径写错 / 文件不存在），而且报错文本全是中文。
    """
    project = make_project(tmp_path)
    missing_log = project / "no-such.log"

    result = run_cli_ascii(
        "verify_generation.py",
        "--log", str(missing_log),
        "--main-c", str(project / "Core" / "Src" / "main.c"),
        "--mxproject", str(project / ".mxproject"),
        "--expect", "GPIO",
    )
    # 输入校验失败是"域外错误"，按契约退 2（不是 1，也不是崩溃）
    assert result.returncode == 2, (result.returncode, result.stderr)
    assert_no_traceback(result)
    assert result.stderr.strip(), "报错不能为空——空输出等于把失败藏起来"
    assert result.stderr.isascii(), result.stderr
