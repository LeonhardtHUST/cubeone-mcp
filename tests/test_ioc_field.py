# -*- coding: utf-8 -*-
"""``scripts/ioc_field.py`` 单测：``.ioc`` 单键读写。

`regen.sh` 用它把 ``ProjectManager.AskForMigrate`` 复位为 ``false``（D7），所以它的
硬要求是：**只改这一行、保留原行尾、值没变时不写盘**。这三条各一个用例。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import ioc_field as iof

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ioc_field.py"

IOC_BODY = (
    "#MicroXplorer Configuration settings - do not modify\n"
    "Mcu.CPN=STM32G474VET6\n"
    "Mcu.PinsNb=5\n"
    "ProjectManager.AskForMigrate=true\n"
    "ProjectManager.ProjectName=fake-board\n"
)


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """以子进程方式跑真实 CLI。"""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(item) for item in args]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
        timeout=60,
        check=False,
    )


@pytest.fixture()
def ioc_file(tmp_path: Path) -> Path:
    """写一个带 ``AskForMigrate=true`` 的假 `.ioc`（LF 行尾）。"""
    path = tmp_path / "board.ioc"
    path.write_text(IOC_BODY, encoding="utf-8", newline="")
    return path


def test_get_returns_value(ioc_file: Path) -> None:
    """get 打印值并给出行号。"""
    result = run_cli("--ioc", str(ioc_file), "get", "ProjectManager.AskForMigrate")
    assert result.returncode == iof.EXIT_OK, result.stdout + result.stderr
    assert result.stdout.strip() == "true"

    value, lineno = iof.get_value(ioc_file, "ProjectManager.AskForMigrate")
    assert value == "true"
    assert lineno == 4


def test_set_changes_only_that_line(ioc_file: Path) -> None:
    """set 只改目标行，其它行逐字不变。"""
    before_lines = ioc_file.read_text(encoding="utf-8").splitlines()
    result = run_cli(
        "--ioc", str(ioc_file), "set", "ProjectManager.AskForMigrate", "false"
    )
    assert result.returncode == iof.EXIT_OK, result.stdout + result.stderr

    after_lines = ioc_file.read_text(encoding="utf-8").splitlines()
    assert after_lines[3] == "ProjectManager.AskForMigrate=false"
    assert after_lines[:3] == before_lines[:3]
    assert after_lines[4:] == before_lines[4:]


def test_set_preserves_crlf(tmp_path: Path) -> None:
    """CRLF 文件写回后仍是 CRLF（CubeMX 写的是 CRLF，别被我们改成混行尾）。"""
    path = tmp_path / "crlf.ioc"
    path.write_bytes(IOC_BODY.replace("\n", "\r\n").encode("utf-8"))

    result = run_cli("--ioc", str(path), "set", "ProjectManager.AskForMigrate", "false")
    assert result.returncode == iof.EXIT_OK, result.stdout + result.stderr

    raw = path.read_bytes()
    assert b"\r\n" in raw
    assert raw.count(b"\r\n") == IOC_BODY.count("\n")
    assert b"ProjectManager.AskForMigrate=false\r\n" in raw


def test_set_same_value_does_not_write(ioc_file: Path) -> None:
    """值已经是目标值时**不写盘**（避免无意义的 mtime/diff 变化）。"""
    mtime_before = os.stat(ioc_file).st_mtime_ns
    result = run_cli(
        "--ioc", str(ioc_file), "set", "ProjectManager.AskForMigrate", "true"
    )
    assert result.returncode == iof.EXIT_OK
    assert "unchanged" in result.stdout
    assert os.stat(ioc_file).st_mtime_ns == mtime_before

    summary = iof.set_value(ioc_file, "ProjectManager.AskForMigrate", "true")
    assert summary["changed"] is False


def test_set_missing_key_returns_1(ioc_file: Path) -> None:
    """键不存在 → 退出码 1（不新建行，避免污染 .ioc）。"""
    body_before = ioc_file.read_text(encoding="utf-8")
    result = run_cli("--ioc", str(ioc_file), "set", "ProjectManager.Nope", "x")
    assert result.returncode == iof.EXIT_KEY_MISSING
    assert "not-found" in result.stderr
    assert ioc_file.read_text(encoding="utf-8") == body_before

    with pytest.raises(KeyError):
        iof.set_value(ioc_file, "ProjectManager.Nope", "x")


def test_set_duplicate_key_refuses(tmp_path: Path) -> None:
    """同名键出现多行 → 拒绝猜测（退出码 1）。"""
    path = tmp_path / "dup.ioc"
    path.write_text(
        "ProjectManager.AskForMigrate=true\nProjectManager.AskForMigrate=false\n",
        encoding="utf-8",
    )
    result = run_cli("--ioc", str(path), "set", "ProjectManager.AskForMigrate", "false")
    assert result.returncode == iof.EXIT_KEY_MISSING
    assert path.read_text(encoding="utf-8").count("AskForMigrate") == 2


def test_dry_run_does_not_write(ioc_file: Path) -> None:
    """``--dry-run`` 只算不写。"""
    result = run_cli(
        "--ioc", str(ioc_file), "set", "ProjectManager.AskForMigrate", "false", "--dry-run"
    )
    assert result.returncode == iof.EXIT_OK
    assert "dry-run" in result.stdout
    assert "ProjectManager.AskForMigrate=true" in ioc_file.read_text(encoding="utf-8")


def test_json_out_roundtrip(ioc_file: Path, tmp_path: Path) -> None:
    """``--json-out`` 给 regen.sh 留证据：含 before/after/changed/line。"""
    json_out = tmp_path / "field.json"
    result = run_cli(
        "--ioc",
        str(ioc_file),
        "set",
        "ProjectManager.AskForMigrate",
        "false",
        "--json-out",
        str(json_out),
    )
    assert result.returncode == iof.EXIT_OK, result.stdout + result.stderr
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["schema"] == iof.SCHEMA
    assert payload["action"] == "set"
    assert payload["key"] == "ProjectManager.AskForMigrate"
    assert payload["before"] == "true"
    assert payload["after"] == "false"
    assert payload["changed"] is True
    assert payload["line"] == 4


def test_missing_ioc_returns_2(tmp_path: Path) -> None:
    """文件不存在 → 退出码 2。"""
    result = run_cli("--ioc", str(tmp_path / "nope.ioc"), "get", "Mcu.CPN")
    assert result.returncode == iof.EXIT_INPUT_ERROR


# ---------------------------------------------------------------------------
# W1-1 / A-21：.ioc 内容注入双层拒绝 + W1-2 能力层不拦截（2026-11-04）
# ---------------------------------------------------------------------------
INJECTION_VALUES: tuple[str, ...] = (
    "false\r\nPA9.Signal=USART1_TX",   # CRLF 注入
    "false\nPA9.Signal=USART1_TX",     # LF 注入
    "false \r\nPA9.Signal=USART1_TX",  # 尾空格 + CRLF 注入
)


@pytest.mark.parametrize("payload", INJECTION_VALUES, ids=["CRLF", "LF", "尾空格+CRLF"])
def test_set_rejects_newline_in_value(ioc_file: Path, tmp_path: Path, payload: str) -> None:
    """三种变体 ⇒ rc=2、`.ioc` 行数与内容不变、不落 JSON（changed=false 的可观察面）。

    rc=2 不落结构化 JSON，所以 ``changed`` 没有输出；可观察面就是「文件一个字节
    都没动 + 没有 JSON 报告」（见退出码契约：2 = 输入错误，不落盘）。
    """
    before_text = ioc_file.read_text(encoding="utf-8")
    before_lines = before_text.splitlines()
    json_out = tmp_path / "field.json"
    result = run_cli(
        "--ioc", str(ioc_file),
        "set", "ProjectManager.AskForMigrate", payload,
        "--json-out", str(json_out),
    )
    assert result.returncode == iof.EXIT_INPUT_ERROR, result.stdout + result.stderr
    assert "[ioc_field][input-error]" in result.stderr
    assert "换行" in result.stderr
    assert ioc_file.read_text(encoding="utf-8") == before_text
    assert ioc_file.read_text(encoding="utf-8").splitlines() == before_lines
    assert not json_out.exists(), "rc=2 不得落结构化 JSON"


def test_get_rejects_newline_in_key(ioc_file: Path) -> None:
    """get 入口同样拒绝换行（CLI 直调也要挡，不只 MCP 通道）。"""
    result = run_cli("--ioc", str(ioc_file), "get", "Mcu.CPN\nPA9.Signal=USART1_TX")
    assert result.returncode == iof.EXIT_INPUT_ERROR
    assert "换行" in result.stderr


def test_python_entry_points_reject_newlines(ioc_file: Path) -> None:
    """函数入口层：get_value / set_value 直接调用也抛 ValueError，且文件不变。"""
    before = ioc_file.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        iof.get_value(ioc_file, "Mcu.CPN\r\nPA9.Signal=USART1_TX")
    with pytest.raises(ValueError):
        iof.set_value(ioc_file, "Mcu.CPN", "x\nPA9.Signal=USART1_TX")
    with pytest.raises(ValueError):
        iof.set_value(ioc_file, "Mcu.CPN\nPA9.Signal=USART1_TX", "x")
    assert ioc_file.read_text(encoding="utf-8") == before


def test_signal_write_is_not_blocked_by_capability_boundary(tmp_path: Path) -> None:
    """W1-2：能力层 ≠ 权限层 —— ``set PA9.Signal USART1_TX`` 仍成功、只带告警。

    脚本层不拦、不改 ``changed``；告警字段由 ``lib/server.mjs`` 注入
    ``structuredContent``（Node 组 4-9 断言），CLI 输出结构保持纯净。
    """
    path = tmp_path / "signal.ioc"
    path.write_text(IOC_BODY + "PA9.Signal=GPIO_Input\n", encoding="utf-8", newline="\n")
    result = run_cli("--ioc", str(path), "set", "PA9.Signal", "USART1_TX")
    assert result.returncode == iof.EXIT_OK, result.stdout + result.stderr
    after = path.read_text(encoding="utf-8")
    assert "PA9.Signal=USART1_TX" in after
    assert "PA9.Signal=GPIO_Input" not in after
    summary = iof.set_value(path, "PA9.Signal", "USART1_TX")
    assert summary["changed"] is False


# ── 0.8.0 / Q3：并发锁不该在正常路径上留下痕迹 ───────────────────────────────


def test_set_leaves_no_lock_file_behind(tmp_path: Path) -> None:
    """正常写盘结束后**不留锁文件**：锁是"用完即弃"的，残留会毒化下一次调用。"""
    ioc = tmp_path / "board.ioc"
    ioc.write_text("ProjectManager.AskForMigrate=false\n", encoding="utf-8", newline="\n")

    result = iof.main(["--ioc", str(ioc), "--", "set", "ProjectManager.AskForMigrate", "true"])

    assert result == iof.EXIT_OK
    assert not (tmp_path / iof.LOCK_FILENAME).exists()
    assert "ProjectManager.AskForMigrate=true" in ioc.read_text(encoding="utf-8")


def test_get_does_not_create_lock_file(tmp_path: Path) -> None:
    """`get` 是只读 ⇒ **连锁文件都不碰**（只读命令不该在工程目录里留下任何东西）。"""
    ioc = tmp_path / "board.ioc"
    ioc.write_text("ProjectManager.AskForMigrate=false\n", encoding="utf-8", newline="\n")

    result = iof.main(["--ioc", str(ioc), "--", "get", "ProjectManager.AskForMigrate"])

    assert result == iof.EXIT_OK
    assert not (tmp_path / iof.LOCK_FILENAME).exists()
