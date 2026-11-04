# -*- coding: utf-8 -*-
"""``scripts/regen.sh`` 的**不调真 CubeMX** 行为测试（秒级）。

覆盖 v1.1 定稿后的四条关键语义：

1. **生成判据查 KO**：CubeMX 退出码恒为 0（D25），脚本层回 ``KO`` 也只返回 0
   → 必须靠日志里的整行 ``KO`` 判定"生成阶段失败"，并退出 ``1``（已回滚）。
2. **``AskForMigrate`` 不拦、不改**：``true`` 单独存在是稳态，不告警；只有
   「``.ioc`` 版本低于本机 + ``=true``」才 warn，且**永远不改文件**。
3. **脏 ``.ioc`` 默认放行**（失败从备份恢复，不用 ``git checkout``），
   ``--require-clean`` 才是显式严格模式（退出 2）。
4. **``--dry-run`` 不得宣称通过**。
"""

from __future__ import annotations

import os
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

MAIN_C = """#include "main.h"

static void MX_GPIO_Init(void);

int main(void)
{
  HAL_Init();
  MX_GPIO_Init();
  while (1)
  {
  }
}

static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  __HAL_RCC_GPIOC_CLK_ENABLE();
  GPIO_InitStruct.Pin = GPIO_PIN_13;
  HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
}
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
    guesses.extend(
        sorted(Path.home().glob(".workbuddy/binaries/PortableGit/versions/*/bin/bash.exe"))
    )
    for guess in guesses:
        if guess.is_file():
            return str(guess)
    return None


BASH = find_bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="没有可用的 bash（Git Bash）")


def make_project(tmp_path: Path, *, migrate: str = "false", version: str = "6.18.1") -> Path:
    """造一个足以通过前置检查的最小工程（.ioc + main.c + .mxproject + .mx）。"""
    project = tmp_path / "fake-board"
    (project / "Core" / "Src").mkdir(parents=True)
    (project / "scripts").mkdir(parents=True)
    (project / "fake-board.ioc").write_text(
        IOC_TEMPLATE.format(migrate=migrate, version=version), encoding="utf-8", newline="\n"
    )
    (project / "Core" / "Src" / "main.c").write_text(MAIN_C, encoding="utf-8", newline="\n")
    (project / ".mxproject").write_text(
        "[PreviousUsedMakefileFiles]\nSourceFiles=Core\\Src\\main.c;\n",
        encoding="utf-8",
        newline="\n",
    )
    (project / "scripts" / "cubemx-generate.mx").write_text(
        "config load fake-board.ioc\nSetStructure Advanced\nproject generate\nexit\n",
        encoding="utf-8",
        newline="\n",
    )
    return project


def make_fake_java(tmp_path: Path, body: str) -> Path:
    """造一个假的"java"：把给定内容写到 stdout 后退出 0（模拟 CubeMX 恒返回 0）。"""
    script = tmp_path / "fake-java.sh"
    script.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8", newline="\n")
    os.chmod(script, 0o755)
    return script


def run_regen(project: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """跑 regen.sh（PYTHON 指向当前解释器，避免 PATH 差异）。

    未显式传 ``--java`` / ``--cube`` 时，把 ``ST_CUBEMX_JRE`` / ``ST_CUBEMX_EXE`` 指到存根文件。

    原因：``regen.sh`` 在步骤 2 之前对这两个路径各做一次 ``[ -f … ]`` 存在性检查，
    默认值指向 ``C:/ST/STM32CubeMX/…``；而多数用例只关心"前置检查 / 退出码 / 是否改文件"，
    且用 ``--dry-run`` 压根不执行它们。若不注入存根，这些用例就会依赖"本机是否装了
    CubeMX"——Windows 开发机上是绿的，Linux CI 上直接 ``die 2``（真实事故：CI 5 例全红）。
    测试必须与宿主环境无关。
    """
    assert BASH is not None
    env = {**os.environ, "PYTHON": sys.executable}
    # 强制覆盖（而不是 setdefault）：宿主环境变量能改变测试结果，同样是不可复现的来源。
    for flag, env_key, name in (
        ("--java", "ST_CUBEMX_JRE", "stub-java"),
        ("--cube", "ST_CUBEMX_EXE", "stub-cube"),
    ):
        if flag in args:
            continue
        stub = project.parent / name
        if not stub.exists():
            stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8", newline="\n")
            os.chmod(stub, 0o755)
        env[env_key] = str(stub)
    return subprocess.run(
        [BASH, str(REGEN), str(project), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
        timeout=timeout,
        check=False,
        env=env,
    )


# ---------------------------------------------------------------------------
# 1. 生成判据：退出码 0 但有 KO → 生成阶段失败，退出 1 并回滚
# ---------------------------------------------------------------------------
def test_ko_in_log_fails_generation_with_exit_1(tmp_path: Path) -> None:
    """CubeMX 回 ``KO`` 但退出码 0 → 必须判"生成阶段失败"（退出 1，已回滚）。

    这是 D25 的直接后果：只看 `returncode` 会把这类失败当成功。
    """
    project = make_project(tmp_path)
    out_dir = tmp_path / "evidence"
    cube = tmp_path / "STM32CubeMX.exe"
    cube.write_text("not-a-real-cube", encoding="utf-8")
    fake_java = make_fake_java(
        tmp_path,
        "echo 'set pin PA0 S_TIM2_CH1_ETR'\necho 'KO'\necho 'exit'\n",
    )

    result = run_regen(
        project, "-o", str(out_dir), "--java", str(fake_java), "--cube", str(cube)
    )
    combined = result.stdout + result.stderr

    assert result.returncode == 1, combined
    assert "[regen] 生成阶段失败" in combined
    assert "KO" in combined
    # 生成失败也要留日志证据，并且不能进到核验阶段
    assert (out_dir / "cubemx-generate.log").is_file()
    assert not (out_dir / "verify.json").exists()
    # 回滚：备份存在且 .ioc 内容与生成前一致
    assert (project / "fake-board.ioc.bak").is_file()
    assert (project / "fake-board.ioc").read_text(encoding="utf-8") == (
        IOC_TEMPLATE.format(migrate="false", version="6.18.1")
    )


def test_clean_log_without_ko_proceeds_to_verify(tmp_path: Path) -> None:
    """日志无 KO → 进到核验阶段（这里没生成产物，所以核验必然给非 0，但阶段要对）。"""
    project = make_project(tmp_path)
    out_dir = tmp_path / "evidence"
    cube = tmp_path / "STM32CubeMX.exe"
    cube.write_text("not-a-real-cube", encoding="utf-8")
    fake_java = make_fake_java(tmp_path, "echo 'Code generation finished successfully'\n")

    result = run_regen(
        project, "-o", str(out_dir), "--java", str(fake_java), "--cube", str(cube)
    )
    combined = result.stdout + result.stderr

    # 空日志 → log_cannot_map warn；main.c 里 GPIO 正常 → 核验大概能过，但不管结果，
    # 关键是"生成阶段"通过、进了"核验阶段"。
    assert "生成阶段：退出码 0 且无 KO" in combined
    assert "[regen] 生成阶段失败" not in combined


# ---------------------------------------------------------------------------
# 2. AskForMigrate：只读、不改、条件告警
# ---------------------------------------------------------------------------
def test_ask_for_migrate_true_is_info_only_when_version_matches(tmp_path: Path) -> None:
    """稳态：``=true`` 且版本一致 → **不出 warn**（只有一行 info）、不拦、**不改文件**。

    为什么不是"完全不提"：版本戳比的是**锁定基线常量**，不是对用户机器的探测；
    用户装的 CubeMX 可能高于基线，此时同样会挂。所以这一档降级为 info 而不是静默。
    """
    project = make_project(tmp_path, migrate="true", version="6.18.1")
    before = (project / "fake-board.ioc").read_bytes()

    result = run_regen(project, "-o", str(tmp_path / "evidence"), "--dry-run")
    combined = result.stdout + result.stderr

    assert result.returncode == 0, combined
    warn_lines = [
        ln for ln in combined.splitlines()
        if ln.startswith("[regen][warn]") and "AskForMigrate" in ln
    ]
    assert warn_lines == [], f"版本戳一致时不该出 warn：{warn_lines}"
    assert "AskForMigrate=true（生成后的稳态）" in combined  # info 仍在，不静默
    assert (project / "fake-board.ioc").read_bytes() == before  # 一个字节都没动


def test_ask_for_migrate_true_warns_when_version_is_older(tmp_path: Path) -> None:
    """``=true`` + 旧版本戳 → 出 warn（带修法），仍不拦不改。"""
    project = make_project(tmp_path, migrate="true", version="6.17.0")
    before = (project / "fake-board.ioc").read_bytes()

    result = run_regen(project, "-o", str(tmp_path / "evidence"), "--dry-run")
    combined = result.stdout + result.stderr

    assert result.returncode == 0, combined
    assert "AskForMigrate=true 且版本戳" in combined
    assert "set ProjectManager.AskForMigrate false" in combined  # 可直接复制的修法
    assert (project / "fake-board.ioc").read_bytes() == before


def test_ask_for_migrate_false_never_warns(tmp_path: Path) -> None:
    """``=false`` + 旧版本戳 → 只有版本戳告警，不该提 AskForMigrate。"""
    project = make_project(tmp_path, migrate="false", version="6.17.0")
    result = run_regen(project, "-o", str(tmp_path / "evidence"), "--dry-run")
    combined = result.stdout + result.stderr

    assert result.returncode == 0, combined
    assert "AskForMigrate" not in combined
    assert "锁定版本 6.18.1" in combined


# ---------------------------------------------------------------------------
# 3. 脏 .ioc：默认放行（从备份恢复），--require-clean 才严格
# ---------------------------------------------------------------------------
def _init_git_with_commit(project: Path) -> None:
    """把假工程提交进一个临时 git 仓库（--require-clean 用例需要）。"""
    git = shutil.which("git")
    if git is None:
        pytest.skip("没有 git，跳过脏工作区用例")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "tester",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "tester",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    subprocess.run([git, "init", "-q"], cwd=project, check=True, timeout=60, env=env)
    subprocess.run([git, "add", "-A"], cwd=project, check=True, timeout=60, env=env)
    subprocess.run(
        [git, "commit", "-qm", "init"], cwd=project, check=True, timeout=60, env=env
    )


def test_dirty_ioc_allowed_by_default_and_restores_from_backup(tmp_path: Path) -> None:
    """默认允许脏 .ioc，并明确告知"从备份恢复、不用 git checkout"。"""
    project = make_project(tmp_path)
    _init_git_with_commit(project)
    ioc = project / "fake-board.ioc"
    dirty_body = ioc.read_text(encoding="utf-8") + "PB0.Signal=GPIO_Output\n"
    ioc.write_text(dirty_body, encoding="utf-8", newline="\n")

    result = run_regen(project, "-o", str(tmp_path / "evidence"), "--dry-run")
    combined = result.stdout + result.stderr

    assert result.returncode == 0, combined
    assert "将按现状生成" in combined
    assert "不用 git checkout" in combined
    # 用户未提交的编辑不能被抹掉（dry-run 也不该动 git）
    assert ioc.read_text(encoding="utf-8") == dirty_body


def test_require_clean_refuses_dirty_ioc(tmp_path: Path) -> None:
    """``--require-clean`` + 脏 .ioc → 退出 2（压根没跑）。"""
    project = make_project(tmp_path)
    _init_git_with_commit(project)
    ioc = project / "fake-board.ioc"
    ioc.write_text(
        ioc.read_text(encoding="utf-8") + "PB0.Signal=GPIO_Output\n", encoding="utf-8", newline="\n"
    )

    result = run_regen(project, "-o", str(tmp_path / "evidence"), "--require-clean")
    combined = result.stdout + result.stderr

    assert result.returncode == 2, combined
    assert "--require-clean 命中" in combined
    assert not (tmp_path / "evidence" / "cubemx-generate.log").exists()


def test_removed_flag_is_rejected(tmp_path: Path) -> None:
    """``--allow-dirty-ioc`` 已删除：不做 no-op 别名（那是语义陷阱），直接报未知选项。"""
    project = make_project(tmp_path)
    result = run_regen(project, "--allow-dirty-ioc")
    assert result.returncode == 2
    assert "未知选项" in result.stderr


# ---------------------------------------------------------------------------
# 4. dry-run 不得宣称通过 / 白名单可见
# ---------------------------------------------------------------------------
def test_dry_run_never_claims_pass(tmp_path: Path) -> None:
    """dry-run 没跑生成也没跑核验 → 不得打印"全部通过"。"""
    project = make_project(tmp_path)
    result = run_regen(project, "-o", str(tmp_path / "evidence"), "--dry-run")
    combined = result.stdout + result.stderr

    assert result.returncode == 0, combined
    assert "全部通过" not in combined
    assert "(dry-run) 未执行生成与核验" in combined


def test_effective_allowlist_is_announced(tmp_path: Path) -> None:
    """生效白名单必须打印（两个入口默认值不同，不打印会出现两种结论）。"""
    project = make_project(tmp_path)
    result = run_regen(project, "-o", str(tmp_path / "evidence"), "--dry-run")
    combined = result.stdout + result.stderr
    assert "生效 allowlist：VP_RIF_VS_RIF1" in combined


def test_help_does_not_leak_shell_code(tmp_path: Path) -> None:
    """``--help`` 只打印用法，不得泄漏 `set -uo pipefail` / `export PATH` 之类的代码行。"""
    assert BASH is not None
    result = subprocess.run(
        [BASH, str(REGEN), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
        timeout=60,
        check=False,
    )
    assert result.returncode == 0
    assert "用法" in result.stdout
    assert "set -uo pipefail" not in result.stdout
    assert "export PATH=" not in result.stdout
