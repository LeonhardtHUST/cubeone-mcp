# -*- coding: utf-8 -*-
"""``scripts/verify_generation.py``（G1 生成核验器）单测。

覆盖矩阵（对应 T1.2 DoD "≥5 例 + 正/负样本"）：

======================================  ==========================================
用例                                     覆盖点
======================================  ==========================================
``test_positive_g474_template``          正样本：G474 模板真实 main.c + 干净日志 → pass
``test_h6_missing_s_prefix_*``           负样本 A：去 ``S_`` 前缀 → Cannot map → fail
``test_missing_ip_parameters_*``         负样本 B：白名单缺失 → 外设无 Init → fail
``test_tim4_silently_dropped``           负样本 C：TIM4 被静默丢弃（H-6）→ fail
``test_vp_rif_noise_allowlisted``        D8 噪音白名单 → warn 且 verdict 仍 pass
``test_vp_rif_without_allowlist_fails``  未开白名单时不得被默认放过
``test_mxproject_abs_path_*``            ``.mxproject`` 盘符绝对路径 → fail
``test_mx_script_*``                     ``.mx`` 脚本绝对路径三态（自指/指别处/占位符）
``test_syscalls_overlay_warning_only``   D9 叠加路径 → 仅 warning，不阻塞
``test_blocking_field_semantics``        ``blocking`` 是"检查性质"，不随 status 漂移
``test_main_init_call_commented``        注释掉的调用不算"被调用"
``test_dead_definition_in_comment``      注释里的定义不算"有定义"
``test_usart2_resolves_uart_suffix``     ``USART2`` → ``MX_USART2_UART_Init`` 容错
``test_input_error_*``                   退出码 2 语义
======================================  ==========================================
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import verify_generation as vg

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify_generation.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

LOG_CLEAN = FIXTURES / "log_clean.txt"
LOG_CANNOT_MAP = FIXTURES / "log_cannot_map_missing_s_prefix.txt"
LOG_VP_RIF = FIXTURES / "log_vp_rif_cannot_map.txt"
LOG_SYSCALLS = FIXTURES / "log_syscalls_overlay.txt"

MAIN_G474 = FIXTURES / "main_g474_template.c"
MAIN_MULTI = FIXTURES / "main_multi_periph.c"
MAIN_MISSING_TIM4 = FIXTURES / "main_missing_tim4.c"
MAIN_TIM4_COMMENTED = FIXTURES / "main_tim4_call_commented.c"

MXP_RELATIVE = FIXTURES / "mxproject_relative.txt"
MXP_ABS = FIXTURES / "mxproject_abs_path.txt"


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------
def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """以子进程方式跑真实 CLI（校验退出码与落盘 JSON，而不是只测内部函数）。"""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(item) for item in args]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
        timeout=120,
        check=False,
    )


def run_verify(
    tmp_path: Path,
    *,
    log: Path = LOG_CLEAN,
    main_c: Path = MAIN_G474,
    mxproject: Path = MXP_RELATIVE,
    expect: str = "GPIO",
    project_root: Path | None = None,
    extra: tuple[str, ...] = (),
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    """跑一次 CLI 并返回 (进程结果, JSON 报告)。"""
    json_out = tmp_path / "report.json"
    args: list[str] = [
        "--log",
        str(log),
        "--main-c",
        str(main_c),
        "--mxproject",
        str(mxproject),
        "--expect",
        expect,
        "--json-out",
        str(json_out),
    ]
    if project_root is not None:
        args.extend(["--project-root", str(project_root)])
    args.extend(extra)
    result = run_cli(*args)
    assert json_out.is_file(), f"CLI 未生成 JSON 报告：{result.stderr}"
    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert isinstance(report, dict)
    return result, report


def check_of(report: dict[str, object], check_id: str) -> dict[str, object]:
    """从报告里取出指定 id 的检查项。"""
    checks = report["checks"]
    assert isinstance(checks, list)
    for item in checks:
        if item["id"] == check_id:
            return item
    raise AssertionError(f"报告里缺少检查项 {check_id}")


def statuses(report: dict[str, object]) -> dict[str, str]:
    """把所有检查项压成 ``{id: status}``。"""
    checks = report["checks"]
    assert isinstance(checks, list)
    return {str(item["id"]): str(item["status"]) for item in checks}


# ---------------------------------------------------------------------------
# 1. 正样本
# ---------------------------------------------------------------------------
def test_positive_g474_template(tmp_path: Path) -> None:
    """G474 模板真实 main.c + 干净日志 + 相对路径 .mxproject → 全通过。"""
    result, report = run_verify(tmp_path, expect="GPIO")

    assert result.returncode == vg.EXIT_PASS, result.stdout + result.stderr
    assert report["schema"] == vg.SCHEMA
    assert report["verdict"] == "pass"
    assert [item["id"] for item in report["checks"]] == list(vg.CHECK_ORDER)
    assert statuses(report) == {
        vg.CHECK_LOG_CANNOT_MAP: "pass",
        vg.CHECK_MAIN_INIT_PRESENT: "pass",
        vg.CHECK_MAIN_INIT_CALLED: "pass",
        vg.CHECK_MXPROJECT_ABS_PATH: "pass",
        # 未传 --project-root → .mx 扫描 skip（向后兼容，不报 fail）
        vg.CHECK_MX_SCRIPT_ABS_PATH: "skip",
        vg.CHECK_SYSCALLS_PATH: "pass",
    }
    summary = report["summary"]
    assert isinstance(summary, dict)
    assert summary["errors"] == 0
    assert summary["warnings"] == 0
    assert summary["checked_peripherals"] == ["GPIO"]
    # skip 的原因必须写进 summary.notes，不能只躺在 check detail 里
    assert any("project-root" in str(note) for note in summary["notes"])

    # detail 必须写清实际匹配到的符号名（下游文档/S1 场景要靠它写证据）。
    present = check_of(report, vg.CHECK_MAIN_INIT_PRESENT)
    assert "MX_GPIO_Init" in str(present["detail"])
    # 三份输入的路径都要出现在报告里，便于证据链回溯。
    inputs = report["inputs"]
    assert isinstance(inputs, dict)
    assert inputs["log"].endswith("log_clean.txt")
    assert inputs["main_c"].endswith("main_g474_template.c")
    assert inputs["mxproject"].endswith("mxproject_relative.txt")
    assert inputs["project_root"] is None
    assert inputs["effective_allow_signals"] == []


def test_positive_multi_peripheral(tmp_path: Path) -> None:
    """多外设正样本：GPIO + TIM4 + USART2 全部定义且调用 → pass。"""
    result, report = run_verify(
        tmp_path, main_c=MAIN_MULTI, expect="GPIO,TIM4,USART2"
    )
    assert result.returncode == vg.EXIT_PASS, result.stdout + result.stderr
    assert report["verdict"] == "pass"
    assert check_of(report, vg.CHECK_MAIN_INIT_PRESENT)["status"] == "pass"
    assert check_of(report, vg.CHECK_MAIN_INIT_CALLED)["status"] == "pass"


# ---------------------------------------------------------------------------
# 2. 负样本 A：H-6 复现（信号名去 S_ 前缀 → Cannot map）
# ---------------------------------------------------------------------------
def test_h6_missing_s_prefix_fails_cannot_map(tmp_path: Path) -> None:
    """去掉 ``S_`` 前缀后 CubeMX 只留 Cannot map，必须判 fail（D4/D5/H-6）。"""
    result, report = run_verify(
        tmp_path, log=LOG_CANNOT_MAP, main_c=MAIN_MULTI, expect="GPIO,TIM4,USART2"
    )

    assert result.returncode == vg.EXIT_FAIL, result.stdout + result.stderr
    assert report["verdict"] == "fail"
    cannot_map = check_of(report, vg.CHECK_LOG_CANNOT_MAP)
    assert cannot_map["status"] == "fail"
    assert cannot_map["blocking"] is True
    detail = str(cannot_map["detail"])
    assert "TIM4_CH1" in detail
    assert "L4" in detail or "L" in detail  # 报了行号
    summary = report["summary"]
    assert isinstance(summary, dict)
    assert summary["errors"] >= 1


# ---------------------------------------------------------------------------
# 3. 负样本 B：漏写 IPParameters 白名单 → 外设没有 Init（日志干净也抓得到）
# ---------------------------------------------------------------------------
def test_missing_ip_parameters_whitelist_fails(tmp_path: Path) -> None:
    """日志干净但 main.c 里没有 TIM4 的 Init → main_init_present 必须 fail。

    这是"参数没进 ``TIM4.IPParameters`` 白名单，CubeMX 静默忽略"的可观测后果
    （D3/D5）：日志无 Cannot map，只有生成物能证明配置没生效。
    """
    result, report = run_verify(
        tmp_path, main_c=MAIN_MISSING_TIM4, expect="GPIO,TIM4,USART2"
    )

    assert result.returncode == vg.EXIT_FAIL, result.stdout + result.stderr
    assert report["verdict"] == "fail"
    assert check_of(report, vg.CHECK_LOG_CANNOT_MAP)["status"] == "pass"
    present = check_of(report, vg.CHECK_MAIN_INIT_PRESENT)
    assert present["status"] == "fail"
    detail = str(present["detail"])
    assert "TIM4" in detail
    assert "MX_GPIO_Init" in detail  # 已满足的那部分也要写出来，方便定位
    # 没有定义的外设不参与"是否被调用"，避免同一个根因报两条 fail。
    assert check_of(report, vg.CHECK_MAIN_INIT_CALLED)["status"] == "pass"


# ---------------------------------------------------------------------------
# 4. 负样本 C：TIM4 被静默丢弃（H-6）
# ---------------------------------------------------------------------------
def test_tim4_silently_dropped(tmp_path: Path) -> None:
    """期望清单含 TIM4，但真实 G474 main.c 里没有任何 TIM4 痕迹 → fail。"""
    result, report = run_verify(tmp_path, main_c=MAIN_G474, expect="TIM4")

    assert result.returncode == vg.EXIT_FAIL, result.stdout + result.stderr
    assert report["verdict"] == "fail"
    present = check_of(report, vg.CHECK_MAIN_INIT_PRESENT)
    assert present["status"] == "fail"
    assert "TIM4" in str(present["detail"])
    # 一个外设都没有定义时，"是否被调用"无从核验 → skip（而不是再报一条 fail）。
    called = check_of(report, vg.CHECK_MAIN_INIT_CALLED)
    assert called["status"] == "skip"
    # blocking 描述的是"该检查失败时是否阻塞"，与本次 status 无关（skip 也是 True）。
    assert called["blocking"] is True


# ---------------------------------------------------------------------------
# 5. D8 噪音白名单：warn 且 verdict 仍为 pass
# ---------------------------------------------------------------------------
def test_vp_rif_noise_allowlisted(tmp_path: Path) -> None:
    """``Cannot map "VP_RIF_VS_RIF1"`` 命中 --allow-signal → warn，verdict 仍 pass。"""
    result, report = run_verify(
        tmp_path,
        log=LOG_VP_RIF,
        main_c=MAIN_MULTI,
        expect="GPIO",
        extra=("--allow-signal", "VP_RIF_VS_RIF1"),
    )

    assert result.returncode == vg.EXIT_PASS, result.stdout + result.stderr
    assert report["verdict"] == "pass"
    cannot_map = check_of(report, vg.CHECK_LOG_CANNOT_MAP)
    assert cannot_map["status"] == "warn"
    assert cannot_map["blocking"] is True
    assert "VP_RIF_VS_RIF1" in str(cannot_map["detail"])
    summary = report["summary"]
    assert isinstance(summary, dict)
    assert summary["errors"] == 0
    assert summary["warnings"] == 1


def test_vp_rif_without_allowlist_fails(tmp_path: Path) -> None:
    """不给白名单时，同样的噪音必须判 fail —— 核验器不默认放过任何 Cannot map。"""
    result, report = run_verify(
        tmp_path, log=LOG_VP_RIF, main_c=MAIN_MULTI, expect="GPIO"
    )
    assert result.returncode == vg.EXIT_FAIL, result.stdout + result.stderr
    assert check_of(report, vg.CHECK_LOG_CANNOT_MAP)["status"] == "fail"


# ---------------------------------------------------------------------------
# 6. .mxproject 盘符绝对路径
# ---------------------------------------------------------------------------
def test_mxproject_abs_path_fails(tmp_path: Path) -> None:
    """``.mxproject`` 含 ``D:\\...`` → fail（换机即坏，TOOLING §3.2）。"""
    result, report = run_verify(tmp_path, mxproject=MXP_ABS, expect="GPIO")

    assert result.returncode == vg.EXIT_FAIL, result.stdout + result.stderr
    assert report["verdict"] == "fail"
    abs_check = check_of(report, vg.CHECK_MXPROJECT_ABS_PATH)
    assert abs_check["status"] == "fail"
    assert "D:" in str(abs_check["detail"])


def test_mxproject_relative_paths_pass() -> None:
    """相对路径的 .mxproject 不得误报（``http://`` 这类伪盘符必须放过）。"""
    clean = vg.check_mxproject_abs_path(
        "ProjectUrl=http://example.com/x\nHeaderPath=Core\\Inc;\n"
    )
    assert clean.status == "pass"
    mixed = vg.check_mxproject_abs_path("HeaderPath=D:\\Projects\\fw\\Core\\Inc;\n")
    assert mixed.status == "fail"


# ---------------------------------------------------------------------------
# 6b. CubeMX 脚本（`.mx`）里的绝对路径：三态判据，不是"有盘符就 fail"
# ---------------------------------------------------------------------------
def make_fake_project(root: Path, mx_body: str, *, script_name: str = "cubemx-init.mx") -> Path:
    """在临时目录里造一个最小工程骨架 + 一份 .mx 脚本。"""
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / script_name).write_text(mx_body, encoding="utf-8")
    return root


def test_mx_script_absolute_path_pointing_to_self_passes(tmp_path: Path) -> None:
    """指向本工程的绝对路径**是合规的**（模板 A1：CubeMX 脚本不支持变量）。"""
    project = make_fake_project(
        tmp_path / "board",
        f"load STM32G474VETx\nproject path {tmp_path / 'board'}\nproject generate\nexit\n",
    )
    result, report = run_verify(tmp_path, project_root=project)

    check = check_of(report, vg.CHECK_MX_SCRIPT_ABS_PATH)
    assert check["status"] == "pass", check["detail"]
    assert check["blocking"] is True
    assert result.returncode == vg.EXIT_PASS
    assert "指向本工程" in str(check["detail"])


def test_mx_script_absolute_path_pointing_elsewhere_fails(tmp_path: Path) -> None:
    """指向**别的工程**才是缺陷：生成会写进另一处，克隆到新机器必踩。"""
    project = make_fake_project(
        tmp_path / "board",
        "# 从裸 MCU 建工程（A1）\nproject path D:\\Projects\\GitHub\\other-board\nproject generate\nexit\n",
    )
    result, report = run_verify(tmp_path, project_root=project)

    check = check_of(report, vg.CHECK_MX_SCRIPT_ABS_PATH)
    assert check["status"] == "fail"
    assert check["blocking"] is True
    assert result.returncode == vg.EXIT_FAIL
    detail = str(check["detail"])
    assert "other-board" in detail
    assert "cubemx-init.mx:2:" in detail  # 报相对路径 + 行号
    assert "in_comment=false" in detail


def test_mx_script_placeholder_warns_not_fails(tmp_path: Path) -> None:
    """``__PROJECT_DIR__`` 未替换 = 脚本没配好 → warn（不阻塞，A1 的占位形态）。"""
    project = make_fake_project(
        tmp_path / "board",
        "load STM32G474VETx\nproject path __PROJECT_DIR__\nproject generate\nexit\n",
    )
    result, report = run_verify(tmp_path, project_root=project)

    check = check_of(report, vg.CHECK_MX_SCRIPT_ABS_PATH)
    assert check["status"] == "warn"
    assert result.returncode == vg.EXIT_PASS
    detail = str(check["detail"])
    assert "占位符" in detail
    assert "__PROJECT_DIR__" in detail


def test_mx_script_comment_hit_is_marked_as_comment(tmp_path: Path) -> None:
    """写在注释里的绝对路径照样报出来，但标 ``in_comment=true`` 供人判断。"""
    project = make_fake_project(
        tmp_path / "board",
        "# project path D:\\Projects\\GitHub\\other-board\nproject generate\nexit\n",
    )
    _, report = run_verify(tmp_path, project_root=project)

    check = check_of(report, vg.CHECK_MX_SCRIPT_ABS_PATH)
    assert check["status"] == "fail"
    assert "in_comment=true" in str(check["detail"])


def test_mx_script_without_any_script_is_skip(tmp_path: Path) -> None:
    """传了 --project-root 但工程里没有 .mx → skip（本项不适用，不是 fail）。"""
    project = tmp_path / "no-scripts"
    project.mkdir()
    _, report = run_verify(tmp_path, project_root=project)

    check = check_of(report, vg.CHECK_MX_SCRIPT_ABS_PATH)
    assert check["status"] == "skip"
    assert check["blocking"] is True


def test_mx_script_relative_ioc_is_not_flagged(tmp_path: Path) -> None:
    """``config load <相对 .ioc>``（cubemx-generate.mx 的正常形态）不得误报。"""
    project = make_fake_project(
        tmp_path / "board",
        "config load stm32-g474-template.ioc\nSetStructure Advanced\nproject generate\nexit\n",
        script_name="cubemx-generate.mx",
    )
    _, report = run_verify(tmp_path, project_root=project)
    assert check_of(report, vg.CHECK_MX_SCRIPT_ABS_PATH)["status"] == "pass"


def test_project_root_missing_is_input_error(tmp_path: Path) -> None:
    """``--project-root`` 指向不存在的目录 → 退出码 2（输入错误，不是配置问题）。"""
    result = run_cli(
        "--log",
        str(LOG_CLEAN),
        "--main-c",
        str(MAIN_G474),
        "--mxproject",
        str(MXP_RELATIVE),
        "--expect",
        "GPIO",
        "--project-root",
        str(tmp_path / "nope"),
    )
    assert result.returncode == vg.EXIT_INPUT_ERROR
    assert "input-error" in result.stderr


# ---------------------------------------------------------------------------
# 6c. blocking 字段语义（旧 `level` 字段会让全 pass 的报告看起来"有错"）
# ---------------------------------------------------------------------------
def test_blocking_field_semantics(tmp_path: Path) -> None:
    """``blocking`` 描述"该检查失败时是否阻塞"，不随本次 status 漂移。"""
    _, report = run_verify(tmp_path, expect="GPIO")
    checks = report["checks"]
    assert isinstance(checks, list)
    flags = {str(item["id"]): item["blocking"] for item in checks}
    assert flags == {
        vg.CHECK_LOG_CANNOT_MAP: True,
        vg.CHECK_MAIN_INIT_PRESENT: True,
        vg.CHECK_MAIN_INIT_CALLED: True,
        vg.CHECK_MXPROJECT_ABS_PATH: True,
        vg.CHECK_MX_SCRIPT_ABS_PATH: True,
        vg.CHECK_SYSCALLS_PATH: False,
    }
    # 全 pass/skip 的报告里不许出现任何像"有错"的字段（level 已删除）
    for item in checks:
        assert "level" not in item
        assert item["status"] in {"pass", "skip"}


# ---------------------------------------------------------------------------
# 7. D9：syscalls/sysmem 叠加路径仅 warning
# ---------------------------------------------------------------------------
def test_syscalls_overlay_warning_only(tmp_path: Path) -> None:
    """``syscalls.c`` / ``sysmem.c`` 叠加路径 → warn，verdict 不受影响。"""
    result, report = run_verify(
        tmp_path, log=LOG_SYSCALLS, main_c=MAIN_MULTI, expect="GPIO"
    )

    assert result.returncode == vg.EXIT_PASS, result.stdout + result.stderr
    assert report["verdict"] == "pass"
    syscalls = check_of(report, vg.CHECK_SYSCALLS_PATH)
    assert syscalls["status"] == "warn"
    # 唯一的非阻塞检查：失败/告警都不挡交付（D9）
    assert syscalls["blocking"] is False
    detail = str(syscalls["detail"])
    assert "syscalls.c" in detail and "sysmem.c" in detail
    assert "D9" in detail
    summary = report["summary"]
    assert isinstance(summary, dict)
    assert summary["warnings"] == 1


# ---------------------------------------------------------------------------
# 8/9. 注释陷阱
# ---------------------------------------------------------------------------
def test_main_init_call_commented_out_fails(tmp_path: Path) -> None:
    """``MX_TIM4_Init`` 有定义但调用被注释 → main_init_called 必须 fail。"""
    result, report = run_verify(
        tmp_path, main_c=MAIN_TIM4_COMMENTED, expect="GPIO,TIM4,USART2"
    )

    assert result.returncode == vg.EXIT_FAIL, result.stdout + result.stderr
    assert check_of(report, vg.CHECK_MAIN_INIT_PRESENT)["status"] == "pass"
    called = check_of(report, vg.CHECK_MAIN_INIT_CALLED)
    assert called["status"] == "fail"
    detail = str(called["detail"])
    assert "MX_TIM4_Init" in detail
    assert "main()" in detail


def test_dead_definition_in_comment_not_counted(tmp_path: Path) -> None:
    """只出现在注释里的 ``MX_ADC1_Init`` 不算定义 → main_init_present fail。"""
    result, report = run_verify(
        tmp_path, main_c=MAIN_TIM4_COMMENTED, expect="ADC1"
    )
    assert result.returncode == vg.EXIT_FAIL, result.stdout + result.stderr
    present = check_of(report, vg.CHECK_MAIN_INIT_PRESENT)
    assert present["status"] == "fail"
    assert "ADC1" in str(present["detail"])


# ---------------------------------------------------------------------------
# 10. 符号名容错
# ---------------------------------------------------------------------------
def test_usart2_resolves_uart_suffix(tmp_path: Path) -> None:
    """``--expect USART2`` 要能匹配 ``MX_USART2_UART_Init``（CubeMX 会加功能后缀）。"""
    _, report = run_verify(tmp_path, main_c=MAIN_MULTI, expect="gpio, tim4 ,USART2")
    present = check_of(report, vg.CHECK_MAIN_INIT_PRESENT)
    assert present["status"] == "pass"
    detail = str(present["detail"])
    assert "MX_USART2_UART_Init" in detail
    assert "suffix:UART" in detail
    summary = report["summary"]
    assert isinstance(summary, dict)
    assert summary["checked_peripherals"] == ["GPIO", "TIM4", "USART2"]


def test_parse_expect_normalizes() -> None:
    """``--expect`` 解析：逗号/分号/空白分隔、去重、转大写。"""
    assert vg.parse_expect(" gpio , tim4;;usart2 ") == ["GPIO", "TIM4", "USART2"]
    assert vg.parse_expect("GPIO,GPIO") == ["GPIO"]
    assert vg.parse_expect("") == []
    assert vg.parse_expect(None) == []


def test_parse_allow_signals_repeatable() -> None:
    """``--allow-signal`` 可重复且可逗号分隔，保留原始大小写。"""
    assert vg.parse_allow_signals(["VP_RIF_VS_RIF1"]) == ["VP_RIF_VS_RIF1"]
    assert vg.parse_allow_signals(["A,B", "C"]) == ["A", "B", "C"]
    assert vg.parse_allow_signals(None) == []


# ---------------------------------------------------------------------------
# 11. 空输入 / skip 语义
# ---------------------------------------------------------------------------
def test_empty_expect_skips_peripheral_checks(tmp_path: Path) -> None:
    """``--expect ""`` → 外设类检查 skip，其余照常，verdict pass。"""
    result, report = run_verify(tmp_path, expect="")
    assert result.returncode == vg.EXIT_PASS, result.stdout + result.stderr
    assert report["verdict"] == "pass"
    assert check_of(report, vg.CHECK_MAIN_INIT_PRESENT)["status"] == "skip"
    assert check_of(report, vg.CHECK_MAIN_INIT_CALLED)["status"] == "skip"
    summary = report["summary"]
    assert isinstance(summary, dict)
    assert summary["checked_peripherals"] == []


def test_empty_log_warns_not_passes(tmp_path: Path) -> None:
    """空日志不能当成"没错误"——必须 warn 提示生成可能没跑。"""
    empty_log = tmp_path / "empty.log"
    empty_log.write_text("", encoding="utf-8")
    result, report = run_verify(tmp_path, log=empty_log, expect="GPIO")
    assert result.returncode == vg.EXIT_PASS
    cannot_map = check_of(report, vg.CHECK_LOG_CANNOT_MAP)
    assert cannot_map["status"] == "warn"
    assert "空" in str(cannot_map["detail"])


# ---------------------------------------------------------------------------
# 12. 退出码 2：输入/IO 错误
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("missing", ["--log", "--main-c", "--mxproject"])
def test_input_error_missing_file(tmp_path: Path, missing: str) -> None:
    """任一输入文件不存在 → 退出码 2（与"核验不通过"的 1 区分）。"""
    paths = {
        "--log": LOG_CLEAN,
        "--main-c": MAIN_G474,
        "--mxproject": MXP_RELATIVE,
    }
    args: list[str] = []
    for flag, value in paths.items():
        args.extend([flag, str(tmp_path / "does-not-exist") if flag == missing else str(value)])
    args.extend(["--expect", "GPIO"])

    result = run_cli(*args)
    assert result.returncode == vg.EXIT_INPUT_ERROR, result.stdout + result.stderr
    assert "input-error" in result.stderr


def test_missing_required_argument_exits_2() -> None:
    """缺必需参数时 argparse 自身返回 2，与契约一致。"""
    result = run_cli("--log", str(LOG_CLEAN))
    assert result.returncode == vg.EXIT_INPUT_ERROR


# ---------------------------------------------------------------------------
# 13. Markdown 报告
# ---------------------------------------------------------------------------
def test_markdown_report_written(tmp_path: Path) -> None:
    """``--report-md`` 要产出含全部 5 个 check id 的表格。"""
    md_path = tmp_path / "nested" / "verify.md"
    result = run_cli(
        "--log",
        str(LOG_CANNOT_MAP),
        "--main-c",
        str(MAIN_MULTI),
        "--mxproject",
        str(MXP_RELATIVE),
        "--expect",
        "GPIO,TIM4",
        "--report-md",
        str(md_path),
    )
    assert result.returncode == vg.EXIT_FAIL
    assert md_path.is_file()
    text = md_path.read_text(encoding="utf-8")
    assert "| `log_cannot_map`" in text
    for check_id in vg.CHECK_ORDER:
        assert check_id in text
    assert "失败时阻塞" in text
    assert "FAIL" in text


# ---------------------------------------------------------------------------
# 14. 纯函数级：注释剥离保留行号
# ---------------------------------------------------------------------------
def test_strip_c_comments_preserves_line_numbers() -> None:
    """注释/字符串剥离后行号不变，且注释里的符号不可见。"""
    source = (
        "/* MX_ADC1_Init(void)\n"
        "{\n"
        "} */\n"
        "static void MX_TIM4_Init(void)\n"
        "{\n"
        "  printf(\"MX_ADC1_Init\");\n"
        "}\n"
    )
    stripped = vg.strip_c_comments(source)
    assert stripped.count("\n") == source.count("\n")
    defs = vg.collect_init_definitions(stripped)
    assert "MX_TIM4_Init" in defs
    assert "MX_ADC1_Init" not in defs
    assert vg.line_of(stripped, defs["MX_TIM4_Init"][0]) == 4


def test_resolve_init_symbol_variants() -> None:
    """符号解析：精确 / 后缀 / 模糊 / 缺失 / 有歧义。"""
    defined = [
        "MX_GPIO_Init",
        "MX_USART2_UART_Init",
        "MX_TIM4_Init",
        "MX_USB_Device_Init",
    ]
    assert vg.resolve_init_symbol("GPIO", defined) == ("MX_GPIO_Init", "exact")
    assert vg.resolve_init_symbol("USART2", defined) == ("MX_USART2_UART_Init", "suffix:UART")
    assert vg.resolve_init_symbol("usb", defined) == ("MX_USB_Device_Init", "suffix:Device")
    assert vg.resolve_init_symbol("TIM4", defined) == ("MX_TIM4_Init", "exact")
    assert vg.resolve_init_symbol("TIM3", defined)[0] is None
    # expect TIM 不应误匹配 TIM4（否则"少配一个定时器"会漏报）
    assert vg.resolve_init_symbol("TIM", defined)[0] is None
