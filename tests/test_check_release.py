# -*- coding: utf-8 -*-
"""`tools/check_release.py` 的判据回归。

两批内容
--------
**① 判据①「五处机器可验」**（0.7.4 / D 组，D35 §35.7）

0.7.4 把版本轴从「四处」扩到「五处」：新增 `package-lock.json` 的根 `version` 与
`packages[""].version`。扩判据的价值全在**能抓到真漂移**：

> 手改 `package.json.version` 却忘了跑 `npm install --package-lock-only`
> ⇒ lock 停在旧版本，`npm ci` 与发布产物都以 lock 为准，而旧判据（四处）**完全看不见**。

正例/负例都围绕"lock 与 manifest 不同值"：**正例必须 PASS，负例必须 FAIL 到点名
package-lock**，只断言"rc≠0"是不够的（那样任何无关错误都能让用例变绿）。

**② `--network` 的 npm 失败必须判红**（0.8.0 / Q0，F-1）

发布后核证（`--network`）的意义是确认远端真的对齐了；旧实现在 npm 调用失败/超时时
降级 WARN、**rc 仍 0**，于是网络一抖就"绿"——等于把"没核证"读成"核证通过"。
现在：失败 → FAIL；带一次重试；不带 `--network` 的发布前门禁**根本不查 npm**（F-5）。

⚠️ 网络路径的用例**用假 `npm` 桩**（`PATH` 前置一个必失败的 shim），不依赖真网络；
真 registry 的成功路径只在发版时人工跑 `--network` 覆盖。
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
CHECK_RELEASE = REPO_ROOT / "tools" / "check_release.py"

#: 目标版本取自 `package.json`（不写死数字：升版不会让本文件变红）。
CURRENT_VERSION = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))["version"]

#: 判据①② 与台账项读到的文件（副本要齐，否则会因"读不到"而不是"要测的那件事"变红）。
COPY_FILES = (
    "package.json",
    "package-lock.json",
    "SKILL.md",
    "README.md",
    "docs/releases/README.md",
)


# ── 工具 ────────────────────────────────────────────────────────────────────


def _load_module():
    """按路径加载 `check_release.py`（`tools/` 不是包）。

    ⚠️ 必须先注册进 `sys.modules`：该模块有 ``@dataclass``，dataclasses 解析注解时要按
    ``cls.__module__`` 回查 `sys.modules`，不注册会得到一条与本次改动无关的
    ``AttributeError``。
    """
    spec = importlib.util.spec_from_file_location("_tools_check_release_for_tests", CHECK_RELEASE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_repo_copy(dest: Path) -> Path:
    """拷一份最小仓到 ``dest``（判据只读这几个文件）。"""
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "docs" / "releases").mkdir(parents=True, exist_ok=True)
    for rel in COPY_FILES:
        shutil.copyfile(REPO_ROOT / rel, dest / rel)
    for note in sorted((REPO_ROOT / "docs" / "releases").glob("*.md")):
        shutil.copyfile(note, dest / "docs" / "releases" / note.name)
    return dest


def _run_check(repo: Path) -> subprocess.CompletedProcess[str]:
    """跑 `check_release.py --repo-root <repo> --tag v<当前版本>`（不碰网络、不读真 tag）。"""
    return subprocess.run(
        [
            sys.executable,
            str(CHECK_RELEASE),
            "--repo-root", str(repo),
            "--tag", f"v{CURRENT_VERSION}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
        cwd=str(REPO_ROOT),
    )


def _rewrite_lock_root(repo: Path, value: str) -> None:
    """把副本 lock 的**根** `version` 改成 ``value``（`packages[""]` 保持原样）。"""
    path = repo / "package-lock.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = value
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ── parse_lock_versions() 单元 ───────────────────────────────────────────────


def test_parse_lock_versions_reads_both_places() -> None:
    """正例：真仓 lock 的根两处都等于 `package.json.version`。"""
    module = _load_module()

    parsed = module.parse_lock_versions(REPO_ROOT)

    assert parsed["root"] == CURRENT_VERSION
    assert parsed["package"] == CURRENT_VERSION


def test_parse_lock_versions_reports_two_different_places(tmp_path: Path) -> None:
    """两处不同值时**原样返回**（判定交给判据①，函数本身不做裁决）。"""
    module = _load_module()
    repo = tmp_path / "repo-diff"
    repo.mkdir()
    (repo / "package-lock.json").write_text(
        json.dumps({"version": "9.9.9", "packages": {"": {"version": "8.8.8"}}}),
        encoding="utf-8",
    )

    parsed = module.parse_lock_versions(repo)

    assert parsed == {"root": "9.9.9", "package": "8.8.8"}


def test_parse_lock_versions_rejects_bad_json(tmp_path: Path) -> None:
    """坏 JSON：给**可读** ``ValueError``（调用方转 FAIL），不抛 ``JSONDecodeError`` 上去。"""
    module = _load_module()
    repo = tmp_path / "repo-bad"
    repo.mkdir()
    (repo / "package-lock.json").write_text("{ not json", encoding="utf-8")

    with pytest.raises(ValueError) as caught:
        module.parse_lock_versions(repo)

    assert "不是合法 JSON" in str(caught.value)


def test_parse_lock_versions_rejects_missing_packages_section(tmp_path: Path) -> None:
    """缺 `packages[""]`：点名缺哪一段，不当成"没有版本号"静默放过。"""
    module = _load_module()
    repo = tmp_path / "repo-nopkg"
    repo.mkdir()
    (repo / "package-lock.json").write_text(json.dumps({"version": "0.7.3", "packages": {}}), encoding="utf-8")

    with pytest.raises(ValueError) as caught:
        module.parse_lock_versions(repo)

    assert 'packages[""]' in str(caught.value)


def test_parse_lock_versions_allows_absent_version_fields(tmp_path: Path) -> None:
    """两处 version 字段缺失：返回 ``None``（不猜），由判据判红。"""
    module = _load_module()
    repo = tmp_path / "repo-nover"
    repo.mkdir()
    (repo / "package-lock.json").write_text(json.dumps({"packages": {"": {}}}), encoding="utf-8")

    parsed = module.parse_lock_versions(repo)

    assert parsed == {"root": None, "package": None}


# ── 判据① 端到端（正例 / 负例都必须**点名** lock）────────────────────────────


def test_five_places_same_value_passes(tmp_path: Path) -> None:
    """正例：五处同值 ⇒ 判据① PASS、rc=0。"""
    repo = _make_repo_copy(tmp_path / "repo-ok")

    proc = _run_check(repo)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "判据① 版本轴同值" in proc.stdout
    assert "与五处一致" in proc.stdout
    assert '[PASS] package-lock.json 根 version' in proc.stdout
    assert '[PASS] package-lock.json packages[""].version' in proc.stdout


def test_lock_root_mismatch_fails_criterion_one(tmp_path: Path) -> None:
    """负例（本批核心）：lock 根 = `9.9.9`、manifest 仍当前版本 ⇒ 判据① FAIL 且点名 lock。"""
    repo = _make_repo_copy(tmp_path / "repo-lock-drift")
    _rewrite_lock_root(repo, "9.9.9")

    proc = _run_check(repo)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "判据① 版本轴同值" in proc.stdout
    assert "package-lock.json 根=9.9.9" in proc.stdout, proc.stdout
    # 未涉及的第二处仍 pass（证明只报真正不一致的那一处，不连坐）
    assert '[PASS] package-lock.json packages[""].version' in proc.stdout


def test_lock_package_section_mismatch_fails_criterion_one(tmp_path: Path) -> None:
    """负例：`packages[""].version` 单独漂移（根对）⇒ 同样判红并点名该处。"""
    repo = _make_repo_copy(tmp_path / "repo-pkg-drift")
    path = repo / "package-lock.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["packages"][""]["version"] = "7.7.7"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    proc = _run_check(repo)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert 'package-lock.json packages[""]=7.7.7' in proc.stdout, proc.stdout


def test_lock_missing_section_is_readable_failure(tmp_path: Path) -> None:
    """lock 结构坏了：rc=1 + 可读中文错误，**不崩**（无 traceback）。"""
    repo = _make_repo_copy(tmp_path / "repo-lock-broken")
    (repo / "package-lock.json").write_text(json.dumps({"version": "0.7.3", "packages": {}}), encoding="utf-8")

    proc = _run_check(repo)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    combined = proc.stdout + proc.stderr
    assert "Traceback (most recent call last)" not in combined
    assert '[FAIL] package-lock.json 版本轴' in proc.stdout
    assert 'packages[""]' in proc.stdout


# ── ② `--network`：npm 失败必须判红（0.8.0 Q0 / F-1）──────────────────────────


def _make_failing_npm_stub(dest: Path, marker: Path) -> Path:
    """造一个**必失败**的 `npm` 假桩目录，并返回该目录（用于前置到 `PATH`）。

    两个平台各写一份可执行：

    - POSIX：`npm`（`#!/bin/sh`，`chmod 755`）；
    - Windows：`npm.cmd`（`subprocess` 走 `CreateProcess`，**无扩展名的脚本找不到**，
      这是本仓 `node --test <目录>` 那个坑的同族问题）。

    桩被调用时先写 ``marker``（"到底有没有真的去调 npm"也要能断言），再退 1。

    Args:
        dest: 放桩的目录。
        marker: 每次被调用都会写这个文件。

    Returns:
        ``dest``。
    """
    dest.mkdir(parents=True, exist_ok=True)
    posix = dest / "npm"
    posix.write_text(
        f"#!/bin/sh\n: > '{marker.as_posix()}'\necho 'npm-stub: registry unreachable' >&2\nexit 1\n",
        encoding="utf-8",
    )
    posix.chmod(0o755)
    (dest / "npm.cmd").write_text(
        "@echo off\r\n"
        f'type nul > "{marker}"\r\n'
        "echo npm-stub: registry unreachable 1>&2\r\n"
        "exit /b 1\r\n",
        encoding="utf-8",
    )
    return dest


def _make_failing_npm_stub(dest: Path, marker: Path) -> Path:
    """造一个**必失败**的 `npm` 假桩，返回它的**完整路径**（配合 `CUBEONE_NPM` 使用）。

    ⚠️ **为什么用 `CUBEONE_NPM` 而不是把桩目录前置到 `PATH`**（第一版这么写过，失败了）：
    Windows 上 `CreateProcess` 对**无扩展名**的命令只补 `.exe`、**不按 `PATHEXT` 逐个试**，
    所以 `PATH` 里更靠前的 `npm.cmd` 桩**拦不住**真实的 `npm.exe` —— 桩被静默跳过、
    真 npm 被调用，用例就"绿得毫无意义"（本机实测：断言到 `latest=0.7.4` 才发现）。
    指到具体可执行文件的路径，两个平台都确定无歧义。

    桩被调用时先写 ``marker``（"到底有没有真的去调 npm"也要能断言），再退 1。

    Args:
        dest: 放桩的目录。
        marker: 每次被调用都会写这个文件。

    Returns:
        桩的可执行文件路径。
    """
    dest.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        stub = dest / "npm-stub.cmd"
        stub.write_text(
            "@echo off\r\n"
            f'type nul > "{marker}"\r\n'
            "echo npm-stub: registry unreachable 1>&2\r\n"
            "exit /b 1\r\n",
            encoding="utf-8",
        )
        return stub
    stub = dest / "npm-stub"
    stub.write_text(
        f"#!/bin/sh\n: > '{marker.as_posix()}'\necho 'npm-stub: registry unreachable' >&2\nexit 1\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


def _run_check_with_npm_stub(
    repo: Path,
    *,
    network: bool,
    stub: Path,
) -> subprocess.CompletedProcess[str]:
    """用假 npm（`CUBEONE_NPM` 指向桩）跑 `check_release.py`。"""
    env = {**os.environ, "CUBEONE_NPM": str(stub)}
    argv = [
        sys.executable,
        str(CHECK_RELEASE),
        "--repo-root", str(repo),
        "--tag", f"v{CURRENT_VERSION}",
    ]
    if network:
        argv.append("--network")
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
        check=False,
        cwd=str(REPO_ROOT),
        env=env,
    )


def test_network_npm_failure_is_red(tmp_path: Path) -> None:
    """**F-1 的核心断言**：`--network` + npm 必失败 ⇒ **rc≠0**，且只红在 npm 这一条。

    旧行为是"降级 WARN、rc 仍 0"，那等于网络一抖就把"没核证"读成"核证通过"。
    """
    repo = _make_repo_copy(tmp_path / "repo-net-fail")
    marker = tmp_path / "npm-called.marker"
    stub = _make_failing_npm_stub(tmp_path / "bin-fail", marker)

    proc = _run_check_with_npm_stub(repo, network=True, stub=stub)
    out = proc.stdout

    assert proc.returncode == 1, out + proc.stderr
    assert "[FAIL] npm dist-tags" in out, out
    assert "未查到 ≠ 没问题" in out, out
    # 真的调了 npm（否则这条"红"可能来自别的原因）
    assert marker.is_file(), "假 npm 桩没被调用——那这条用例并没验到网络失败路径"
    # 只有 npm 一条红：台账/正文/版本轴都不该被牵连（工作区干净在副本上无法判定 → WARN）
    assert [line for line in out.splitlines() if "[FAIL]" in line] == [
        line for line in out.splitlines() if "[FAIL] npm dist-tags" in line
    ], out


def test_without_network_npm_is_not_invoked(tmp_path: Path) -> None:
    """发布前门禁（不带 `--network`）**根本不查 npm**：既不会红、也不会因网络变慢（F-5 分级不变）。"""
    repo = _make_repo_copy(tmp_path / "repo-no-net")
    marker = tmp_path / "npm-called-no-net.marker"
    stub = _make_failing_npm_stub(tmp_path / "bin-fail-2", marker)

    proc = _run_check_with_npm_stub(repo, network=False, stub=stub)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "npm dist-tags" not in proc.stdout, proc.stdout
    assert not marker.exists(), "发布前门禁不该调用 npm（F-5：目标版本尚未发布时 latest 必然不等）"


def test_npm_dist_tags_retries_once_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """重试逻辑：第一次失败、第二次成功 ⇒ 返回 dist-tags（不判红），并说明"第 2 次才成功"。"""
    module = _load_module()
    calls: list[tuple] = []

    class _Result:
        def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            return _Result(1, "", "npm-stub: registry unreachable")
        return _Result(0, '{"latest": "0.7.4"}')

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    tags, note = module.npm_dist_tags(REPO_ROOT)

    assert tags == {"latest": "0.7.4"}
    assert len(calls) == 2, f"应该恰好重试一次，实际调用 {len(calls)} 次"
    assert "第 2 次" in note


def test_npm_dist_tags_returns_none_after_two_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    """两次都超时 ⇒ 返回 ``None``（由调用方在 `--network` 下判红），文案点明 2/2 次。"""
    module = _load_module()
    calls: list[tuple] = []

    def fake_run(*args, **kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired(cmd="npm", timeout=kwargs.get("timeout", 60))

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    tags, message = module.npm_dist_tags(REPO_ROOT)

    assert tags is None
    assert len(calls) == 2
    assert "超时" in message and "2/2" in message, message


# ── ③ 空输出必须走重试并归因到"输出为空"（0.8.0 Q2b / F-1）──────────────────


def _make_silent_npm_stub(dest: Path, counter: Path) -> Path:
    """造一个**成功退出但零输出**的 npm 桩，返回其完整路径。

    每次被调用往 ``counter`` 追加一行（用来断言"确实重试了"）。零输出是关键：
    真实世界里 npm 在 half-open 连接 / 被信号打断时会**什么都没打印就退 0**，
    旧实现 `json.loads(stdout or "{}")` 把这种情况当成"合法空对象"。
    """
    dest.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        stub = dest / "npm-silent.cmd"
        stub.write_text(
            "@echo off\r\n"
            f'echo .>> "{counter}"\r\n'
            "exit /b 0\r\n",
            encoding="utf-8",
        )
        return stub
    stub = dest / "npm-silent"
    stub.write_text(
        f"#!/bin/sh\necho . >> '{counter.as_posix()}'\nexit 0\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


def test_network_silent_npm_output_is_red_and_retried(tmp_path: Path) -> None:
    """`--network` + npm **零输出** ⇒ rc≠0、文案含「输出为空」、且**确实重试了一次**。

    修复前：空输出被 `json.loads(stdout or "{}")` 当成 `{}` ⇒ 不重试、rc=0，并通过
    「远端 latest=None ≠ 目标 0.7.4」把责任推给 registry —— 归因完全是错的。
    """
    repo = _make_repo_copy(tmp_path / "repo-silent")
    counter = tmp_path / "npm-calls.txt"
    stub = _make_silent_npm_stub(tmp_path / "bin-silent", counter)

    proc = _run_check_with_npm_stub(repo, network=True, stub=stub)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "[FAIL] npm dist-tags" in proc.stdout, proc.stdout
    assert "输出为空" in proc.stdout, proc.stdout
    assert "latest=None" not in proc.stdout, "空输出不该被归因成「registry 返回奇怪 dist-tags」"
    calls = [line for line in counter.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(calls) == 2, f"空输出必须走一次重试（共 2 次），实际 {len(calls)} 次"


def test_npm_dist_tags_retries_when_first_output_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """第一次「零输出但退出 0」、第二次正常 ⇒ 返回 dist-tags（rc 不红），并说明第 2 次才成功。"""
    module = _load_module()
    calls: list[tuple] = []

    class _Result:
        def __init__(self, returncode: int, stdout: str) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    def fake_run(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            return _Result(0, "")  # 成功退出但什么也没输出
        return _Result(0, '{"latest": "0.8.0"}')

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    tags, note = module.npm_dist_tags(REPO_ROOT)

    assert tags == {"latest": "0.8.0"}
    assert len(calls) == 2, f"应重试一次，实际 {len(calls)} 次"
    assert "第 2 次" in note
