# -*- coding: utf-8 -*-
"""多文件（per-peripheral 文件布局）判据的回归用例（F1，2026-11-04）。

缺陷本体（C3.1 预演在真实 NUEDC 工程上实测）
--------------------------------------------
CubeMX 的 ``ProjectManager.CoupleFile=true``（"Generate peripheral initialization as a pair
of '.c/.h' files"）会把每个外设的 ``MX_<P>_Init`` 生成到**独立文件**（``Core/Src/gpio.c``
/ ``tim.c`` …），``main.c`` 里只剩调用。核验器原先只读 ``--main-c`` 一个文件，于是把
"定义在别的文件里"误判成"外设被静默丢弃"——**假失败**：配置完全正确却被判红。

四条用例各自守一件事
--------------------
1. 多文件（给 ``--project-root``）→ 三项全 pass，且报出的定义位置**指向真实文件**；
2. 单文件（不给 ``--project-root``）→ **行为与修复前完全一致**（仍 fail），
   证明"修好一个"没有顺手放宽默认严格度；
3. ``CoupleFile=true`` 且没给 ``--project-root`` → 降 ``warn`` 并写进 ``notes``
   （这一种情形我们确实看不见，判 fail 就是冤枉）；
4. ``CoupleFile=false`` 且没给 ``--project-root`` → **不降级**（保持严格）。
   第 3、4 条配对，防止"降级条件"被写成"缺 project-root 就一律 warn"。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import verify_generation as vg

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: ``main.c``：只有调用，没有定义（per-peripheral 布局的典型形态）。
MAIN_C = """#include "main.h"

void SystemClock_Config(void);

int main(void)
{
  HAL_Init();
  SystemClock_Config();
  MX_GPIO_Init();
  while (1)
  {
  }
}
"""

#: ``gpio.c``：定义与 GPIO 时钟使能都在这里（这正是原核验器看不到的地方）。
GPIO_C = """#include "main.h"

void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};

  __HAL_RCC_GPIOC_CLK_ENABLE();

  GPIO_InitStruct.Pin = GPIO_PIN_13;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
}
"""

#: 干净的生成日志（无 ``Cannot map``）。
LOG = """[INFO] CodeEngine:321 - Generated code: Core/Src/main.c
[INFO] CodeEngine:321 - Generated code: Core/Src/gpio.c
"""

#: 无盘符绝对路径的 ``.mxproject``（否则 ``mxproject_abs_path`` 会红，干扰本组断言）。
MXPROJECT = """<?xml version="1.0" encoding="UTF-8"?>
<Project>
  <File Version="6"/>
</Project>
"""


def build_project(tmp_path: Path, couple_file: bool) -> Path:
    """造一个 per-peripheral 布局的最小工程（``Core/Src/main.c`` + ``gpio.c`` + `.ioc`）。

    Args:
        tmp_path: pytest 的临时目录。
        couple_file: 写进 ``.ioc`` 的 ``ProjectManager.CoupleFile`` 取值。

    Returns:
        工程根目录。
    """
    root = tmp_path / "proj"
    src = root / "Core" / "Src"
    src.mkdir(parents=True)
    (src / "main.c").write_text(MAIN_C, encoding="utf-8", newline="\n")
    (src / "gpio.c").write_text(GPIO_C, encoding="utf-8", newline="\n")
    (root / ".mxproject").write_text(MXPROJECT, encoding="utf-8", newline="\n")
    (root / "board.ioc").write_text(
        "Mcu.CPN=STM32G474VET6\n"
        "PC13.GPIOParameters=PinState\n"
        "PC13.PinState=GPIO_PIN_RESET\n"
        "PC13.Signal=GPIO_Output\n"
        f"ProjectManager.CoupleFile={'true' if couple_file else 'false'}\n"
        "ProjectManager.ProjectName=fake-board\n",
        encoding="utf-8",
        newline="\n",
    )
    return root


def project_ioc(couple_file: bool) -> str:
    """构造 ``.ioc`` 文本（只需要 ``CoupleFile`` 与引脚声明）。"""
    return (
        "Mcu.CPN=STM32G474VET6\n"
        "PC13.GPIOParameters=PinState\n"
        "PC13.PinState=GPIO_PIN_RESET\n"
        "PC13.Signal=GPIO_Output\n"
        f"ProjectManager.CoupleFile={'true' if couple_file else 'false'}\n"
        "ProjectManager.ProjectName=fake-board\n"
    )


def run_verify(*, project_root: Path | None, main_c_text: str, couple_file: bool) -> dict[str, object]:
    """跑一次完整核验（直接调 ``verify_documents``，便于断言报告结构）。

    Args:
        project_root: 工程根；``None`` 表示不传 ``--project-root``。
        main_c_text: ``main.c`` 全文。
        couple_file: 写进 ``.ioc`` 的 ``CoupleFile`` 取值。

    Returns:
        报告字典。
    """
    return vg.verify_documents(
        log_text=LOG,
        main_c_text=main_c_text,
        mxproject_text=MXPROJECT,
        expect=["GPIO"],
        project_root=str(project_root) if project_root is not None else None,
        ioc_text=project_ioc(couple_file),
        expect_pins=[("PC13", "GPIO_Output")],
    )


def check_by_id(report: dict[str, object], check_id: str) -> dict[str, object]:
    """从报告中取出某条检查的 dict。"""
    checks = report["checks"]
    assert isinstance(checks, list)
    for item in checks:
        assert isinstance(item, dict)
        if item["id"] == check_id:
            return item
    raise AssertionError(f"报告里没有 {check_id}")


def notes_of(report: dict[str, object]) -> list[str]:
    """取 ``summary.notes``。"""
    summary = report["summary"]
    assert isinstance(summary, dict)
    notes = summary["notes"]
    assert isinstance(notes, list)
    return [str(item) for item in notes]


def test_multifile_layout_finds_definitions_in_peripheral_file(tmp_path: Path) -> None:
    """给了 ``--project-root`` → 三项全 pass，且定义位置指向 ``Core/Src/gpio.c``。"""
    root = build_project(tmp_path, couple_file=True)
    report = run_verify(
        project_root=root,
        main_c_text=(root / "Core" / "Src" / "main.c").read_text(encoding="utf-8"),
        couple_file=True,
    )

    assert report["verdict"] == "pass", notes_of(report)
    present = check_by_id(report, vg.CHECK_MAIN_INIT_PRESENT)
    assert present["status"] == "pass"
    assert "Core/Src/gpio.c" in str(present["detail"]), present["detail"]

    called = check_by_id(report, vg.CHECK_MAIN_INIT_CALLED)
    assert called["status"] == "pass", called["detail"]

    pins = check_by_id(report, vg.CHECK_PINS_PRESENT)
    assert pins["status"] == "pass", pins["detail"]


def test_single_file_mode_keeps_strict_behavior(tmp_path: Path) -> None:
    """不给 ``--project-root`` → 与修复前一致：仍判 fail（**没有**顺手放宽默认）。"""
    root = build_project(tmp_path, couple_file=False)
    report = run_verify(
        project_root=None,
        main_c_text=(root / "Core" / "Src" / "main.c").read_text(encoding="utf-8"),
        couple_file=False,
    )

    assert report["verdict"] == "fail"
    assert check_by_id(report, vg.CHECK_MAIN_INIT_PRESENT)["status"] == "fail"
    assert check_by_id(report, vg.CHECK_PINS_PRESENT)["status"] == "fail"


def test_couple_file_without_project_root_downgrades_to_warn() -> None:
    """``CoupleFile=true`` + 无 ``--project-root`` → 降 warn，并在 notes 里点名原因。"""
    report = run_verify(project_root=None, main_c_text=MAIN_C, couple_file=True)

    present = check_by_id(report, vg.CHECK_MAIN_INIT_PRESENT)
    pins = check_by_id(report, vg.CHECK_PINS_PRESENT)
    assert present["status"] == "warn", present["detail"]
    assert pins["status"] == "warn", pins["detail"]
    # 降级理由必须同时出现在 detail 与 notes：只在 detail 里等于"看一眼就过去了"
    assert "CoupleFile=true" in str(present["detail"])
    joined = "\n".join(notes_of(report))
    assert "CoupleFile=true" in joined
    assert vg.CHECK_MAIN_INIT_PRESENT in joined
    assert vg.CHECK_PINS_PRESENT in joined
    # 降级后不该再有 fail，否则 warn 就没有意义
    assert report["verdict"] == "pass"


def test_couple_file_false_without_project_root_stays_strict() -> None:
    """``CoupleFile=false`` + 无 ``--project-root`` → **不降级**（否则等于废掉这两项）。"""
    report = run_verify(project_root=None, main_c_text=MAIN_C, couple_file=False)

    assert check_by_id(report, vg.CHECK_MAIN_INIT_PRESENT)["status"] == "fail"
    assert check_by_id(report, vg.CHECK_PINS_PRESENT)["status"] == "fail"
    assert report["verdict"] == "fail"


def test_ioc_couple_file_reader() -> None:
    """``ioc_uses_per_peripheral_files``：读得到 true/false，读不到时返回 None（不猜）。"""
    assert vg.ioc_uses_per_peripheral_files("ProjectManager.CoupleFile=true\n") is True
    assert vg.ioc_uses_per_peripheral_files("ProjectManager.CoupleFile=FALSE\n") is False
    assert vg.ioc_uses_per_peripheral_files("Mcu.CPN=STM32G474VET6\n") is None
    assert vg.ioc_uses_per_peripheral_files(None) is None


@pytest.mark.parametrize("couple_file", [True, False])
def test_origin_locator_maps_to_real_file_and_line(tmp_path: Path, couple_file: bool) -> None:
    """定义位置的行号必须换算回**原文件**，不能是拼接文本里的假行号。"""
    root = build_project(tmp_path, couple_file=couple_file)
    combined, origin_of, labels = vg.build_source_text(
        str(root), (root / "Core" / "Src" / "main.c").read_text(encoding="utf-8")
    )
    assert "Core/Src/gpio.c" in labels
    definitions = vg.collect_init_definitions(combined)
    offset = definitions["MX_GPIO_Init"][0]
    label, line = origin_of(offset)
    assert label == "Core/Src/gpio.c"
    # GPIO_C 里 `void MX_GPIO_Init(void)` 在第 3 行
    assert line == 3, (label, line)


# ---------------------------------------------------------------------------
# W0-2 / A-14：CLI 层「工程根选错」负样本（2026-11-04）
# ---------------------------------------------------------------------------
def test_cli_rejects_project_root_without_sources(tmp_path: Path) -> None:
    """给了 ``--project-root`` 但 ``Core/Src/*.c`` 为空 ⇒ rc=2、不落 JSON。

    ⚠️ 本文件其余用例**直调** ``verify_documents(log_text=LOG)``，那是纯函数、
    不走 ``main()``，所以 W0 的输入/形态校验对它们零影响 —— 正是 F-1
    「形态校验绝不下移进 verify_documents()」要保护的场景。这一条特意走 CLI
    验证入口层守卫。
    """
    root = tmp_path / "wrong-root"
    (root / "Core" / "Src").mkdir(parents=True)
    json_out = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "verify_generation.py"),
            "--log", str(FIXTURES / "log_clean.txt"),
            "--main-c", str(FIXTURES / "main_g474_template.c"),
            "--mxproject", str(FIXTURES / "mxproject_relative.txt"),
            "--expect", "GPIO",
            "--project-root", str(root),
            "--json-out", str(json_out),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert result.returncode == vg.EXIT_INPUT_ERROR, result.stdout + result.stderr
    assert "工程根可能选错" in result.stderr
    assert not json_out.exists(), "rc=2 不得落 JSON 报告"
