# -*- coding: utf-8 -*-
"""``scripts/regen.sh`` 的**生成前**行为（不跑 CubeMX，秒级）。

重点验证 lead 定的那条结构性判断：``ProjectManager.AskForMigrate=true`` 的危害
发生在**生成时**（``-q`` 会卡在迁移对话框直到超时），所以它必须是 ``regen.sh``
的**前置硬拦**（退出码 2），而不是生成后才跑的 check —— 等核验器看到它，人已经
白等了。这里断言两件事：**退出码 2** 且 **CubeMX 根本没被调用**（无生成日志）。

另外两个用例覆盖同一层的其它拒绝路径：``.ioc`` 脏工作区、环境缺失。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REGEN = REPO_ROOT / "scripts" / "regen.sh"

IOC_TEMPLATE = """#MicroXplorer Configuration settings - do not modify
Mcu.CPN=STM32G474VET6
Mcu.IP0=NVIC
Mcu.IP1=RCC
Mcu.IP2=SYS
Mcu.IPNb=3
Mcu.Pin0=PC13
Mcu.PinsNb=1
MxCube.Version={version}
PC13.GPIOParameters=PinState
PC13.PinState=GPIO_PIN_SET
PC13.Signal=GPIO_Output
ProjectManager.AskForMigrate={migrate}
ProjectManager.ProjectName=fake-board
"""


def find_bash() -> str | None:
    """找一个可用的 bash（Git Bash）。找不到就跳过这些用例。"""
    candidate = shutil.which("bash")
    if candidate:
        return candidate
    guesses = [
        Path(r"C:\Program Files\Git\bin\bash.exe"),
        Path(r"C:\Program Files (x86)\Git\bin\bash.exe"),
    ]
    guesses.extend(sorted(Path.home().glob(".workbuddy/binaries/PortableGit/versions/*/bin/bash.exe")))
    for guess in guesses:
        if guess.is_file():
            return str(guess)
    return None


BASH = find_bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="没有可用的 bash（Git Bash）")


def make_project(tmp_path: Path, *, migrate: str = "true", version: str = "6.18.1") -> Path:
    """造一个足以通过前置检查的最小工程（.ioc + main.c + .mxproject + .mx）。"""
    project = tmp_path / "fake-board"
    (project / "Core" / "Src").mkdir(parents=True)
    (project / "scripts").mkdir(parents=True)
    (project / "fake-board.ioc").write_text(
        IOC_TEMPLATE.format(migrate=migrate, version=version), encoding="utf-8"
    )
    (project / "Core" / "Src" / "main.c").write_text(
        "int main(void)\n{\n  MX_GPIO_Init();\n  while (1) {}\n}\n", encoding="utf-8"
    )
    (project / ".mxproject").write_text(
        "[PreviousUsedMakefileFiles]\nSourceFiles=Core\\Src\\main.c;\n", encoding="utf-8"
    )
    (project / "scripts" / "cubemx-generate.mx").write_text(
        "config load fake-board.ioc\nSetStructure Advanced\nproject generate\nexit\n",
        encoding="utf-8",
    )
    return project


def run_regen(project: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """跑 regen.sh（PYTHON 指向当前解释器，避免 PATH 差异）。"""
    assert BASH is not None
    return subprocess.run(
        [BASH, str(REGEN), str(project), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
        timeout=timeout,
        check=False,
        env={**__import__("os").environ, "PYTHON": sys.executable},
    )


def test_ask_for_migrate_blocks_before_generation(tmp_path: Path) -> None:
    """``AskForMigrate=true`` → 退出码 2，且**没有**产生 CubeMX 生成日志。

    这是"防白等 300 秒"的关键：脚本必须在调用 CubeMX 之前就退出。
    """
    project = make_project(tmp_path, migrate="true")
    out_dir = tmp_path / "evidence"

    result = run_regen(project, "-o", str(out_dir))

    assert result.returncode == 2, result.stdout + result.stderr
    combined = result.stdout + result.stderr
    assert "AskForMigrate" in combined
    assert "前置检查未通过" in combined
    # 关键断言：CubeMX 压根没被调用 → 不可能有生成日志
    assert not (out_dir / "cubemx-generate.log").exists()
    # 也不该有任何备份动作（前置检查在备份之前）
    assert not (project / "fake-board.ioc.bak").exists()


def test_ask_for_migrate_passes_when_false(tmp_path: Path) -> None:
    """``AskForMigrate=false`` 时前置通过，失败点是环境（这里故意给不存在的 CubeMX）。"""
    project = make_project(tmp_path, migrate="false")
    out_dir = tmp_path / "evidence"

    result = run_regen(
        project,
        "-o",
        str(out_dir),
        "--java",
        sys.executable,  # 存在即可，本用例不会真的执行
        "--cube",
        str(tmp_path / "no-such-STM32CubeMX.exe"),
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 2, combined
    assert "找不到 CubeMX" in combined
    assert "AskForMigrate" not in combined  # 前置已放行
    assert (out_dir / "ioc-backup.json").is_file()  # 说明确实进到了备份步骤


def test_dirty_ioc_refused_with_next_step_hint(tmp_path: Path) -> None:
    """``.ioc`` 脏且没带 ``--allow-dirty-ioc`` → 退出码 2，并直接给出下一步命令。"""
    git = shutil.which("git")
    if git is None:
        pytest.skip("没有 git，跳过脏工作区用例")

    project = make_project(tmp_path, migrate="false")
    subprocess.run([git, "init", "-q"], cwd=project, check=True, timeout=60)
    subprocess.run([git, "add", "."], cwd=project, check=True, timeout=60)
    subprocess.run(
        [git, "-c", "user.email=t@example.com", "-c", "user.name=tester", "commit", "-qm", "init"],
        cwd=project,
        check=True,
        timeout=60,
    )
    # 模拟"刚用 CLI set 改完 .ioc"
    ioc = project / "fake-board.ioc"
    ioc.write_text(ioc.read_text(encoding="utf-8") + "PA0.Signal=GPIO_Output\n", encoding="utf-8")

    result = run_regen(project, "-o", str(tmp_path / "evidence"))
    combined = result.stdout + result.stderr

    assert result.returncode == 2, combined
    assert "--allow-dirty-ioc" in combined
    assert "拒绝在 .ioc 脏的工作区生成" in combined


def test_version_stamp_mismatch_warns_only(tmp_path: Path) -> None:
    """版本戳与锁定版本不一致 → 只告警（P2 提交卫生），不改变前置结论。"""
    project = make_project(tmp_path, migrate="false", version="6.17.0")
    out_dir = tmp_path / "evidence"

    result = run_regen(
        project,
        "-o",
        str(out_dir),
        "--java",
        sys.executable,
        "--cube",
        str(tmp_path / "no-such-STM32CubeMX.exe"),
    )
    combined = result.stdout + result.stderr

    assert "6.17.0" in combined
    assert "锁定版本 6.18.1" in combined
    # 仍然是因为环境缺失而失败（不是被版本戳拦下）
    assert result.returncode == 2
    assert "找不到 CubeMX" in combined


def test_effective_allowlist_is_announced(tmp_path: Path) -> None:
    """生效白名单必须打印出来（两个入口默认值不同，不打印就会出现两种结论）。"""
    project = make_project(tmp_path, migrate="false")

    result = run_regen(project, "-o", str(tmp_path / "evidence"), "--dry-run")
    combined = result.stdout + result.stderr

    assert result.returncode == 0, combined
    assert "生效 allowlist：VP_RIF_VS_RIF1" in combined
    # dry-run 不该落任何证据文件
    assert not (tmp_path / "evidence" / "verify.json").exists()
