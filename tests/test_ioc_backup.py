# -*- coding: utf-8 -*-
"""``scripts/ioc_backup.py`` 单测：``.ioc`` → ``.ioc.bak`` 备份与还原。

覆盖：备份生成 + sha256 一致、``--list`` 不写盘、``--restore`` 回滚内容、
``--json-out`` 结构、无 ``.ioc`` 时退出码 1。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import ioc_backup as ib

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ioc_backup.py"

FAKE_IOC = """#MicroXplorer Configuration settings - do not modify
Mcu.CPN=STM32G474VET6
Mcu.Name=STM32G474V(B-C-E)Tx
Mcu.PinsNb=5
Mcu.Pin0=PC13
PC13.GPIOParameters=PinState
PC13.PinState=GPIO_PIN_SET
PC13.Signal=GPIO_Output
ProjectManager.ProjectName=fake-board
ProjectManager.AskForMigrate=true
"""


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
def fake_project(tmp_path: Path) -> Path:
    """建一个含单个 ``.ioc`` 的假工程目录。"""
    project = tmp_path / "fake-board"
    project.mkdir()
    (project / "fake-board.ioc").write_text(FAKE_IOC, encoding="utf-8")
    (project / "Core").mkdir()
    return project


def test_backup_creates_bak(fake_project: Path) -> None:
    """备份要生成 ``<name>.ioc.bak``，字节与 sha256 与原文件一致。"""
    result = run_cli("--project", str(fake_project))
    assert result.returncode == ib.EXIT_OK, result.stdout + result.stderr

    ioc = fake_project / "fake-board.ioc"
    bak = fake_project / "fake-board.ioc.bak"
    assert bak.is_file()
    assert bak.read_bytes() == ioc.read_bytes()
    assert ib.sha256_of(bak) == ib.sha256_of(ioc)
    assert "backed up" in result.stdout


def test_backup_json_payload(fake_project: Path, tmp_path: Path) -> None:
    """``--json-out`` 结构可被 regen.sh / Skill 消费。"""
    json_out = tmp_path / "out" / "backup.json"
    result = run_cli("--project", str(fake_project), "--json-out", str(json_out))
    assert result.returncode == ib.EXIT_OK, result.stdout + result.stderr

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["schema"] == ib.SCHEMA
    assert payload["action"] == "backup"
    assert Path(payload["project"]).as_posix().endswith("fake-board")
    files = payload["files"]
    assert len(files) == 1
    assert files[0]["ioc"].endswith("fake-board.ioc")
    assert files[0]["backup"].endswith("fake-board.ioc.bak")
    assert files[0]["bytes"] > 0
    assert len(files[0]["sha256"]) == 64


def test_list_does_not_write(fake_project: Path) -> None:
    """``--list`` 只读：不得产生 ``.ioc.bak``。"""
    result = run_cli("--project", str(fake_project), "--list")
    assert result.returncode == ib.EXIT_OK, result.stdout + result.stderr
    assert not (fake_project / "fake-board.ioc.bak").exists()
    assert "fake-board.ioc" in result.stdout


def test_restore_roundtrip(fake_project: Path) -> None:
    """备份 → 篡改 → 还原，内容必须回到备份时状态（模拟生成失败回滚）。"""
    assert run_cli("--project", str(fake_project)).returncode == ib.EXIT_OK
    ioc = fake_project / "fake-board.ioc"

    ioc.write_text("ProjectManager.AskForMigrate=true\n# 生成把我改坏了\n", encoding="utf-8")
    assert ioc.read_text(encoding="utf-8") != FAKE_IOC

    result = run_cli("--project", str(fake_project), "--restore")
    assert result.returncode == ib.EXIT_OK, result.stdout + result.stderr
    assert ioc.read_text(encoding="utf-8") == FAKE_IOC
    assert "restored" in result.stdout


def test_restore_without_bak_returns_1(fake_project: Path) -> None:
    """没有任何 ``.ioc.bak`` 时还原要返回 1 并提示改用 git。"""
    result = run_cli("--project", str(fake_project), "--restore")
    assert result.returncode == ib.EXIT_NOT_FOUND
    assert "git checkout" in result.stderr


def test_no_ioc_returns_1(tmp_path: Path) -> None:
    """目录里没有 ``.ioc`` → 退出码 1（不是 2，代表"找不到目标"）。"""
    empty = tmp_path / "empty"
    empty.mkdir()
    result = run_cli("--project", str(empty))
    assert result.returncode == ib.EXIT_NOT_FOUND
    assert "not-found" in result.stderr


def test_missing_project_dir_returns_2(tmp_path: Path) -> None:
    """工程目录不存在 → 退出码 2（参数/IO 错误）。"""
    result = run_cli("--project", str(tmp_path / "nope"))
    assert result.returncode == ib.EXIT_INPUT_ERROR
    assert "input-error" in result.stderr


def test_find_ioc_ignores_backup(fake_project: Path) -> None:
    """``find_ioc_files`` 只认 ``*.ioc``，不把 ``*.ioc.bak`` 当成新工程。"""
    assert run_cli("--project", str(fake_project)).returncode == ib.EXIT_OK
    found = [path.name for path in ib.find_ioc_files(fake_project)]
    assert found == ["fake-board.ioc"]
