# -*- coding: utf-8 -*-
"""`tools/check_release.py` 判据① 的**五处机器可验**回归（0.7.4 / D 组，D35 §35.7）。

为什么单独一个文件
------------------
0.7.4 把版本轴从「四处」扩到「五处」：新增 `package-lock.json` 的根 `version` 与
`packages[""].version`。扩判据的价值全在**能抓到真漂移**：

> 手改 `package.json.version` 却忘了跑 `npm install --package-lock-only`
> ⇒ lock 停在旧版本，`npm ci` 与发布产物都以 lock 为准，而旧判据（四处）**完全看不见**。

所以本文件的正例/负例都围绕"lock 与 manifest 不同值"：**正例必须 PASS，负例必须 FAIL 到
点名 package-lock**，只断言"rc≠0"是不够的（那样任何无关错误都能让用例变绿）。

⚠️ 本文件只测判据①与 `parse_lock_versions()`，不测 npm 网络路径（`--network` 的
dist-tags 需要真网络，不在 CI 跑）。
"""

from __future__ import annotations

import importlib.util
import json
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
