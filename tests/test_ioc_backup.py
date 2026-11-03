# -*- coding: utf-8 -*-
"""``scripts/ioc_backup.py`` 单测：``.ioc`` → ``.ioc.bak`` 备份与还原。

覆盖：备份生成 + sha256 一致、``--list`` 不写盘、``--restore`` 回滚内容、
``--json-out`` 结构、无 ``.ioc`` 时退出码 1。

0.7.0 增补（R-C3：restore 原子化 + 完整性核对）：备份额外落一份 sidecar
``<name>.ioc.bak.sha256``；还原前核对它，不一致**拒绝还原并 rc=2**（否则等于把
"被篡改/半份"的备份写回工程，比不还原更危险）；缺 sidecar 只告警不拦（兼容旧备份目录）；
还原走 mkstemp + ``os.replace``，失败不留半份 ``.ioc``。
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

#: 完整性 sidecar 后缀（R-C3）。写死字面量而非引用脚本常量：
#: 后缀是**跨工具契约**（regen.sh / Skill / 用户手查都会用到），不跟着实现改名漂移。
SIDECAR_SUFFIX = ".sha256"

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


def sidecar_of(bak: Path) -> Path:
    """``fake-board.ioc.bak`` → ``fake-board.ioc.bak.sha256``。"""
    return bak.with_name(bak.name + SIDECAR_SUFFIX)


def tmp_leftovers(project: Path) -> list[str]:
    """目录里遗留的临时文件（mkstemp 残留），用于断言"失败不留半份"。"""
    return sorted(path.name for path in project.iterdir() if ".tmp" in path.name)


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
    """``--list`` 只读：不得产生 ``.ioc.bak``，也不得产生完整性 sidecar。"""
    result = run_cli("--project", str(fake_project), "--list")
    assert result.returncode == ib.EXIT_OK, result.stdout + result.stderr
    bak = fake_project / "fake-board.ioc.bak"
    assert not bak.exists()
    assert not sidecar_of(bak).exists(), "--list 是只读动作，连 sidecar 也不该落盘"
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


# ── R-C3：restore 原子化 + 完整性核对（3 例） ─────────────────────────
#
# 为什么这三例要一起看：单看任何一条都能"修好"，合起来才构成闭环——
#   新1 证明"还原确实回到了原件状态，且没留半份临时文件"（原子性）；
#   新2 证明"备份被篡改时宁可不还原"（完整性优先于可用性）；
#   新3 证明"没有摘要的旧备份仍能救急"（不把兼容性做成一刀切拒绝）。


def test_restore_result_sha256_matches_original_and_leaves_no_tmp(fake_project: Path) -> None:
    """还原后 ``.ioc`` 的 sha256 必须等于备份前，且目录里无 ``.tmp`` 残留。

    只比内容不够：``shutil.copy2`` 直接写目标文件，中途失败会留下**半份 .ioc**，
    内容比对能过（因为没跑完），但工程已经坏了。所以要同时钉"摘要相等"与"无临时残留"。
    """
    ioc = fake_project / "fake-board.ioc"
    original_sha = ib.sha256_of(ioc)

    assert run_cli("--project", str(fake_project)).returncode == ib.EXIT_OK
    ioc.write_text("ProjectManager.AskForMigrate=true\n# 生成把我改坏了\n", encoding="utf-8")

    result = run_cli("--project", str(fake_project), "--restore")
    assert result.returncode == ib.EXIT_OK, result.stdout + result.stderr

    assert ib.sha256_of(ioc) == original_sha
    assert ioc.read_text(encoding="utf-8") == FAKE_IOC
    assert tmp_leftovers(fake_project) == [], "还原必须走 mkstemp + os.replace，失败也不得留 .tmp"


def test_restore_rejects_tampered_bak(fake_project: Path) -> None:
    """``.bak`` 被改一个字节（sidecar 不动）→ 拒绝还原、rc=2、``.ioc`` 未被改动。

    这是 R-C3 的核心取舍：**宁可不还原，也不把可疑内容写回工程**。
    用 rc=2（EXIT_INPUT_ERROR）而不是 1：1 的语义是"目标不存在"，这里目标存在但**不可信**，
    混用会让人以为"备份没了，去 git 找"——方向完全错。
    """
    assert run_cli("--project", str(fake_project)).returncode == ib.EXIT_OK
    ioc = fake_project / "fake-board.ioc"
    bak = fake_project / "fake-board.ioc.bak"
    sidecar = sidecar_of(bak)
    assert sidecar.is_file(), f"备份必须落 sidecar {sidecar.name}（R-C3）"

    # 只改最后一个字节，且**不碰** sidecar：模拟"备份被外部改坏/半份写入"
    original_bak = bak.read_bytes()
    bak.write_bytes(original_bak[:-1] + bytes([original_bak[-1] ^ 0xFF]))

    before = ioc.read_bytes()
    result = run_cli("--project", str(fake_project), "--restore")

    assert result.returncode == ib.EXIT_INPUT_ERROR, result.stdout + result.stderr
    assert "integrity" in result.stderr.lower(), f"拒绝理由必须可检索，实际 stderr：{result.stderr}"
    assert ioc.read_bytes() == before, "拒绝还原时 .ioc 必须原样不动（半还原等于损坏）"
    assert tmp_leftovers(fake_project) == []


def test_restore_without_sidecar_warns_but_restores(fake_project: Path) -> None:
    """缺 sidecar → 只告警不拦：stdout 含「缺少完整性摘要」，内容仍被还原。"""
    assert run_cli("--project", str(fake_project)).returncode == ib.EXIT_OK
    ioc = fake_project / "fake-board.ioc"
    bak = fake_project / "fake-board.ioc.bak"
    sidecar = sidecar_of(bak)
    assert sidecar.is_file(), f"备份必须落 sidecar {sidecar.name}（R-C3）"
    sidecar.unlink()

    ioc.write_text("# 生成把我改坏了\n", encoding="utf-8")
    result = run_cli("--project", str(fake_project), "--restore")

    assert result.returncode == ib.EXIT_OK, result.stdout + result.stderr
    assert "缺少完整性摘要" in result.stdout, f"必须在 stdout 告警（stderr 会被判成失败），实际：{result.stdout}"
    assert ioc.read_text(encoding="utf-8") == FAKE_IOC
