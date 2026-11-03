#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""版本轴与发布收口校验（C2.3）：把「四个地方写的版本号是否同值」交给机器比。

为什么需要
----------
`README.md`「三个版本号，别混」把发布轴规则定成：`git tag` = `package.json` = `SKILL.md`
frontmatter = README 表里那两处，**必须同值同步**（D33 §33.2）。这条规则以前靠人肉对四行——
而"人肉对四行"在 0.6.2 / 0.7.0 两次发版里都出现过同一类失误的前兆：改了三处、忘了第四处，
直到有人翻 README 才发现。凡是"必须同时成立的多处一致"，都该有台机器来比。

判据（任一不满足即 ``exit 1``）
-------------------------------
1. **版本轴一致**：最新 tag（去掉 ``v``）== ``package.json`` 的 ``version`` ==
   ``SKILL.md`` frontmatter 的 ``version`` == README「三个版本号」表里的两处值。
   ``SKILL.md`` 正文状态行（``> 状态：vX.Y.Z``）**不一致只警告**：它是叙述，不是契约，
   卡死它会让"顺手补一句状态"变成必须同步 bump 的负担。
2. **发布正文存在**：``docs/releases/`` 下有名字含该版本号的 ``.md``（发布正文入库是
   0.6.2 起的约定——正文只存在于 GitHub 页面等于没归档）。
3. **未发版改动提醒**：``master`` 领先该 tag 的提交数 > 0 时**只打印提醒，不算失败**。
   那是"改了但还没发版"的正常状态，把它判红等于逼人每次 push 都发版。

可选判据（需网络）
------------------
``--network`` 额外查 npm ``dist-tags``（``npm view``，带超时）。**失败/不匹配都只 warning**：
发布顺序本来就是 tag → Release → npm，脚本在打完 tag 立刻跑时 npm 还没更新属正常；
网络不通更是环境问题。判成红会让这条判据在 CI 里失去信息量。

用法
----
::
    python tools/check_release.py                  # 校验当前仓（发布前手动跑）
    python tools/check_release.py --network        # 额外查 npm dist-tags
    python tools/check_release.py --tag v0.9.9     # 预演/自测：指定要比对的 tag，跳过 git
    python tools/check_release.py --repo-root X    # 校验副本（自测坏样本用）

设计约束
--------
- **纯标准库、零依赖**（与 `check_taskboard.py` 同一约束：CI 的 lint job 只装 pytest）。
- **只读**：本脚本不改任何文件，也不执行任何写操作（不 add / 不 commit / 不打 tag）。
- **不猜**：读不到版本号就报错并指名是哪一处，不做"取第一个数字"这类猜测——
  猜对了没人知道，猜错了会给出一个看起来通过的假结论。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]

#: 允许的版本号形态（三段式）。核验器轴 `1.2.0` 也是三段式，所以匹配后还要按"出处"区分。
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")

#: 反引号 token（README 表里的值都是行内代码）。
BACKTICK_RE = re.compile(r"`([^`]+)`")

#: SKILL.md 正文状态行：`> 状态：v0.7.1（…）`
SKILL_STATUS_RE = re.compile(r"状态：v(\d+\.\d+\.\d+)")

#: 发布正文文件名里的版本号（`2026-11-04-v0.7.1.md`）。边界要卡住：
#: 否则 `0.7.1` 会匹配到 `0.7.10.md`——一个只在"真有 0.7.10"时才暴露的静默错误。
def release_file_pattern(version: str) -> re.Pattern[str]:
    """返回匹配"名字含该版本号"的发布正文文件名正则。"""
    return re.compile(rf"(?:^|[-_])v?{re.escape(version)}\.md$")


@dataclass
class Finding:
    """一条判定结果。

    Attributes:
        kind: ``PASS`` / ``FAIL`` / ``WARN``。
        where: 判据位置（人读的短标签）。
        detail: 具体事实（含实际值与期望值）。
    """

    kind: str
    where: str
    detail: str


def read_text(path: Path) -> str:
    """按 UTF-8 读文本；失败时抛 ``OSError``（由调用方转成 FAIL）。"""
    return path.read_text(encoding="utf-8")


def run_git(root: Path, args: Sequence[str]) -> tuple[int, str]:
    """跑一条 git 命令。

    Args:
        root: 仓库根。
        args: 传给 git 的参数（不含 ``-C``）。

    Returns:
        ``(returncode, stdout)``；git 不可用时返回 ``(-1, "")``。
    """
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return -1, ""
    return completed.returncode, completed.stdout


def latest_tag(root: Path) -> str | None:
    """取最新 tag（``git tag --sort=-v:refname`` 的第一行）。"""
    code, out = run_git(root, ["tag", "--sort=-v:refname"])
    if code != 0:
        return None
    for line in out.splitlines():
        if line.strip():
            return line.strip()
    return None


def commits_ahead(root: Path, tag: str) -> int | None:
    """统计 ``HEAD`` 领先某 tag 的提交数。"""
    code, out = run_git(root, ["rev-list", "--count", f"{tag}..HEAD"])
    if code != 0:
        return None
    try:
        return int(out.strip())
    except ValueError:
        return None


def parse_package_version(root: Path) -> str:
    """从 ``package.json`` 取 ``version``（用正则而非 ``json.loads``：

    本仓 `package.json` 是纯 JSON，两者等价；但坏样本测试里可能出现被 sed 改坏的
    文件，正则能给出"这一行是什么"，比 JSONDecodeError 的报错更好定位。
    """
    text = read_text(root / "package.json")
    match = re.search(r'"version"\s*:\s*"([^"]+)"', text)
    if not match:
        raise ValueError("package.json 里找不到 version 字段")
    return match.group(1).strip()


def parse_skill_version(root: Path) -> tuple[str, str | None]:
    """取 ``SKILL.md`` 的 frontmatter ``version`` 与正文状态行版本号。

    Returns:
        ``(frontmatter_version, status_line_version_or_None)``。

    Raises:
        ValueError: frontmatter 里没有 ``version`` 行。
    """
    text = read_text(root / "SKILL.md")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md 第一行不是 frontmatter 起始的 ---")
    frontmatter: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        frontmatter.append(line)
    else:
        raise ValueError("SKILL.md frontmatter 没有闭合的 ---")
    for line in frontmatter:
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip(), _status_line_version(text)
    raise ValueError("SKILL.md frontmatter 里没有 version 行")


def _status_line_version(text: str) -> str | None:
    """从正文里抓 ``> 状态：vX.Y.Z`` 的版本号。"""
    match = SKILL_STATUS_RE.search(text)
    return match.group(1) if match else None


def _version_in_cell(cell: str) -> str | None:
    """从 README 表格单元格里取版本号（优先取行内代码里的那个）。"""
    for token in BACKTICK_RE.findall(cell):
        hit = VERSION_RE.search(token)
        if hit:
            return hit.group(0)
    hit = VERSION_RE.search(cell)
    return hit.group(0) if hit else None


def parse_readme_versions(root: Path) -> dict[str, str | None]:
    """取 README「三个版本号」表里的两处发布轴值。

    Returns:
        ``{"tag": 值或 None, "skill": 值或 None}``。

    只认**行首单元格**带标签的两行，不按行号取：表可能被重排、也可能多出别的版本轴行
    （核验器那行 `verify_generation.py --version` 就是干扰项，且**故意不参与**本判据）。
    """
    text = read_text(root / "README.md")
    found: dict[str, str | None] = {"tag": None, "skill": None}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        label = cells[0]
        value = _version_in_cell(cells[2])
        if "仓库发布标签" in label and found["tag"] is None:
            found["tag"] = value
        elif "SKILL.md" in label and "version" in label and found["skill"] is None:
            found["skill"] = value
    return found


def find_release_note(root: Path, version: str) -> Path | None:
    """在 ``docs/releases/`` 下找该版本号的发布正文。"""
    releases = root / "docs" / "releases"
    if not releases.is_dir():
        return None
    pattern = release_file_pattern(version)
    for candidate in sorted(releases.glob("*.md")):
        if pattern.search(candidate.name):
            return candidate
    return None


def npm_dist_tags(root: Path, timeout: float = 20.0) -> tuple[dict[str, str] | None, str]:
    """查 npm 的 ``dist-tags``（``--network`` 才调用）。

    Args:
        root: 仓库根（在仓内跑，便于继承 `.npmrc`）。
        timeout: 超时秒数；npm 卡住不该把发布流程一起卡住。

    Returns:
        ``(dist_tags 或 None, 说明)``。任何失败都只返回说明，由调用方降级为 WARN。
    """
    try:
        completed = subprocess.run(
            ["npm", "view", "cubeone-mcp", "dist-tags", "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(root),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"npm 调用失败（{type(error).__name__}）"
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip().splitlines()
        tail = stderr[-1] if stderr else f"退出码 {completed.returncode}"
        return None, f"npm view 失败：{tail}"
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return None, "npm view 输出不是合法 JSON"
    if not isinstance(payload, dict):
        return None, "npm view 输出不是对象"
    return {str(k): str(v) for k, v in payload.items()}, "ok"


def check(
    root: Path,
    tag_override: str | None,
    network: bool,
) -> tuple[list[Finding], list[Finding]]:
    """跑全部判据。

    Args:
        root: 仓库根。
        tag_override: 非空时用它代替 `git tag`（自测/预演用）。
        network: 是否额外查 npm dist-tags。

    Returns:
        ``(findings, extras)``：``findings`` 参与退出码（PASS/FAIL），
        ``extras`` 只打印（WARN / 提醒）。
    """
    findings: list[Finding] = []
    extras: list[Finding] = []

    # ── 取各处版本号 ──
    values: dict[str, str | None] = {"package": None, "skill": None, "readme_tag": None, "readme_skill": None}

    try:
        values["package"] = parse_package_version(root)
        findings.append(Finding("PASS", "package.json version", values["package"]))
    except (OSError, ValueError) as error:
        findings.append(Finding("FAIL", "package.json version", str(error)))

    status_version: str | None = None
    try:
        skill_version, status_version = parse_skill_version(root)
        values["skill"] = skill_version
        findings.append(Finding("PASS", "SKILL.md frontmatter version", skill_version))
    except (OSError, ValueError) as error:
        findings.append(Finding("FAIL", "SKILL.md frontmatter version", str(error)))

    try:
        readme = parse_readme_versions(root)
        values["readme_tag"] = readme["tag"]
        values["readme_skill"] = readme["skill"]
        for label, key in (("README 仓库发布标签", "readme_tag"), ("README SKILL.md version", "readme_skill")):
            value = values[key]
            if value is None:
                findings.append(Finding("FAIL", label, "没读到版本号（表格结构或标签变了）"))
            else:
                findings.append(Finding("PASS", label, value))
    except OSError as error:
        findings.append(Finding("FAIL", "README 版本表", str(error)))

    # ── 判据 1：最新 tag == 三处 ──
    tag = tag_override
    if tag is None:
        tag = latest_tag(root)
        if tag is None:
            findings.append(Finding("FAIL", "最新 tag", "读不到任何 tag（git 不可用或仓内无 tag）——无法判定"))
        else:
            findings.append(Finding("PASS", "最新 tag", tag))
    else:
        findings.append(Finding("PASS", "最新 tag", f"{tag}（--tag 显式指定）"))

    if tag is not None:
        tag_version = tag[1:] if tag.startswith("v") else tag
        mismatched = [
            (label, value)
            for label, value in (
                ("package.json", values["package"]),
                ("SKILL.md frontmatter", values["skill"]),
                ("README 仓库发布标签", values["readme_tag"]),
                ("README SKILL.md version", values["readme_skill"]),
            )
            if value is not None and value != tag_version
        ]
        if mismatched:
            detail = "；".join(f"{label}={value}" for label, value in mismatched)
            findings.append(
                Finding(
                    "FAIL",
                    "判据① 版本轴同值",
                    f"最新 tag={tag_version}，但 {detail}",
                )
            )
        else:
            findings.append(Finding("PASS", "判据① 版本轴同值", f"tag={tag_version} 与四处一致"))

        # 正文状态行：只警告（见模块 docstring 的理由）
        if status_version is not None and status_version != tag_version:
            extras.append(
                Finding(
                    "WARN",
                    "SKILL.md 正文状态行",
                    f"v{status_version} ≠ tag {tag_version}（叙述行，不判红；顺手对齐一下更省事）",
                )
            )

    # ── 判据 2：发布正文存在 ──
    # 用 tag 的版本号去找（判据① 已保证它与三处同值时才有意义；不同值时两个判据一起红，
    # 这是有意的：错的地方都列出来，别让人修一处跑一次）。
    target_version = None
    if tag is not None:
        target_version = tag[1:] if tag.startswith("v") else tag
    elif values["package"]:
        target_version = values["package"]
    if target_version is None:
        findings.append(Finding("FAIL", "判据② 发布正文", "无法确定要比对的版本号"))
    else:
        note = find_release_note(root, target_version)
        if note is None:
            findings.append(
                Finding("FAIL", "判据② 发布正文", f"docs/releases/ 下没有含 {target_version} 的 .md")
            )
        else:
            findings.append(Finding("PASS", "判据② 发布正文", str(note.relative_to(root))))

    # ── 判据 3：未发版改动（只提醒） ──
    if tag is not None and tag_override is None:
        ahead = commits_ahead(root, tag)
        if ahead is None:
            extras.append(Finding("WARN", "判据③ 未发版改动", "读不到 HEAD 与该 tag 的关系（git 不可用）"))
        elif ahead > 0:
            extras.append(
                Finding(
                    "WARN",
                    "判据③ 未发版改动",
                    f"HEAD 领先 {tag} 共 {ahead} 个提交——正常状态（有改动未发版），下次发版记得收口",
                )
            )
        else:
            extras.append(Finding("PASS", "判据③ 未发版改动", f"HEAD 与 {tag} 同点"))

    # ── 可选判据：npm dist-tags ──
    if network:
        tags, message = npm_dist_tags(root)
        if tags is None:
            extras.append(Finding("WARN", "npm dist-tags", f"{message}（网络失败只警告，不判红）"))
        elif target_version is None:
            extras.append(Finding("WARN", "npm dist-tags", f"无法确定目标版本；远端 latest={tags.get('latest')}"))
        elif tags.get("latest") == target_version:
            extras.append(Finding("PASS", "npm dist-tags", f"latest={target_version}"))
        else:
            extras.append(
                Finding(
                    "WARN",
                    "npm dist-tags",
                    f"远端 latest={tags.get('latest')} ≠ 目标 {target_version}"
                    "（发布顺序是 tag → Release → npm，打完 tag 立刻跑时属正常；只警告）",
                )
            )

    return findings, extras


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 入口。

    Returns:
        退出码：``0`` 全部判据通过；``1`` 存在不一致或无法判定。
    """
    parser = argparse.ArgumentParser(
        prog="check_release.py",
        description="校验版本轴（tag / package.json / SKILL.md / README）与发布正文是否收口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="退出码：0=通过 1=不一致或无法判定。示例：python tools/check_release.py --network",
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="仓库根（默认脚本所在仓）")
    parser.add_argument("--tag", default=None, help="显式指定要比对的 tag（自测/预演用，跳过 git）")
    parser.add_argument("--network", action="store_true", help="额外查 npm dist-tags（失败只警告）")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = Path(args.repo_root).resolve()
    print(f"[check_release] 仓根：{root}")
    if not (root / "package.json").is_file():
        print(f"[check_release][error] 不是仓根（找不到 package.json）：{root}", file=sys.stderr)
        return 1

    findings, extras = check(root, args.tag, args.network)

    print("\n== 判据 ==")
    for item in findings:
        print(f"  [{item.kind}] {item.where} — {item.detail}")
    print("\n== 提醒（不参与退出码）==")
    if extras:
        for item in extras:
            print(f"  [{item.kind}] {item.where} — {item.detail}")
    else:
        print("  （无）")

    failures = [item for item in findings if item.kind == "FAIL"]
    print("\n== 汇总 ==")
    if failures:
        print(f"✗ {len(failures)} 条判据不满足：")
        for item in failures:
            print(f"  - {item.where}：{item.detail}")
        print("\n[check_release] FAIL —— 版本轴或发布正文没收口；四处必须同值，正文必须入库。")
        return 1
    print("✓ 版本轴同值、发布正文在位、无阻塞项。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
