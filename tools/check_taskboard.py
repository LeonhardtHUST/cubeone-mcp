#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""看板一致性校验（M3 / R-E1）：把「看板写的」与「看板该有的」对上，机械判定。

为什么需要
----------
`docs/TASKBOARD.md` 是唯一状态真源，但它长期靠人手算：审定报告发现②的
「三重失真」（§4 快照写 `7 已完成 / 4 进行中 / 8 待开始`，而任务表实际是 17/0/6/1/1）
就是这么来的。**手算的数字迟早会漂**，而漂了之后没有任何机制能抓住它 —— 除非把
算术搬进脚本。本脚本就是那台机器。

三组判据（任一不满足即 ``exit 1``）
-----------------------------------
1. **快照一致性**
   - 解析任务表（Phase 0–3 四张 + 整改批次表），按段统计六种状态；
   - 解析 §4 快照表，逐段逐状态比对；
   - 每段的「任务数」必须等于该段六种状态之和，`‹Phase 0–3 小计›` 必须等于前四段之和，
     `合计` 必须等于小计 + 批次段 —— **全部由脚本自己求和，不信任手写数字**。
2. **证据路径存在性**
   - 抽取证据列里反引号包裹的仓内相对路径（`docs/` `tests/` `scripts/` `lib/`
     `references/` `tools/` `.github/` 开头），逐个 ``os.path.exists``；
   - ⚠️ **跳过 `docs/logs/` 开头的路径**：该目录被 `.gitignore` 局部忽略，CI 上没有这些
     文件，不跳过会让 CI 恒红。跳过条数**会计数并打印**——静默跳过等于假装检查过；
   - 含通配符（`*` `?` `[`）的条目不算路径（是模式），单独计数；
   - 外部链接、tag 名、commit sha（无 `/` 或不以上述前缀开头）天然被排除。
3. **发布一致性**
   - **当前版本 tag**（`v<package.json.version>`）存在时，`T3.5` 不得为 `待开始`
     （防「tag 打了但看板没记账」，D33 的机读化）；
   - `TAG_RE` 放宽到任意三段式版本 tag（不再钉死 `v0.6/v0.7`），否则 `v0.8.0`
     这类未来的版本 tag 会被静默跳过，判据形同虚设；
   - `git` 不可用 / 无 tag / 当前版本 tag 尚未打出时**不报错**，打印一行 `note` 说明被跳过。

用法
----
::

    python tools/check_taskboard.py              # 校验仓内看板，exit 0 / 1
    python tools/check_taskboard.py --board X.md # 校验副本（自测用：改坏一处 → 必须 exit 1）

设计约束
--------
- **纯标准库、零依赖**（CI 的 lint job 只装了 pytest，不装第三方）。
- **解析容错**：表头可能带全角括号；单元格可能是 `**18**（M1）` 这类富文本 ⇒ 取单元格里
  第一串数字；行标签按前缀匹配。但**状态值不容错**：认不出六种状态之一就判失败并点名行，
  宁可红一次让人来补，也不要让一个写作 `进行中（待发版收口）`/`已完成（三证齐全）` 的
  变体在统计里静默消失。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOARD = REPO_ROOT / "docs" / "TASKBOARD.md"

#: 状态取值（看板 §0.1 的六种，顺序即快照列顺序）。
STATUSES: tuple[str, ...] = ("已完成", "进行中", "挂起", "待开始", "已关闭", "阻塞")

#: 快照列顺序（与看板 §4 表头一致；脚本按表头名字定位列，不依赖这里的位置）。
SNAPSHOT_COLUMNS: tuple[str, ...] = ("任务数",) + STATUSES

#: 分段标签：Phase 0–3 与整改批次表。快照行标签按**前缀**匹配这些标签。
SECTION_LABELS: tuple[str, ...] = (
    "Phase 0",
    "Phase 1",
    "Phase 2",
    "Phase 3",
    "M1 修复批次",
)

#: Phase 0–3 段（小计 = 这四段之和）。
PHASE_LABELS: tuple[str, ...] = ("Phase 0", "Phase 1", "Phase 2", "Phase 3")

#: 批次段（Phase 0–3 之外的整改批次表）。
BATCH_LABEL = "M1 修复批次"

#: 证据列里视为"仓内相对路径"的前缀。
PATH_PREFIXES: tuple[str, ...] = (
    "docs/",
    "tests/",
    "scripts/",
    "lib/",
    "tools/",
    "references/",
    "bin/",
    ".github/",
)

#: 局部被 `.gitignore` 忽略、CI 上不存在的证据目录（必须跳过并计数）。
GITIGNORED_PREFIXES: tuple[str, ...] = ("docs/logs/",)

#: 反引号里出现、但**不是本仓文件**的路径：逐条列明 + 理由。
#:
#: 为什么用显式白名单而不是"父目录存在才算仓内路径"这类启发式：启发式会把真正的缺失
#: 一起放过（父目录存在、文件却没了 —— 恰恰是最常见的失真形态）。
NON_REPO_PATHS: dict[str, str] = {
    "scripts/cubemx-init.mx": "引用被测工程（testbeds 副本）里的 CubeMX 脚本；本仓 scripts/ 下没有 .mx 文件",
}

GLOB_CHARS = ("*", "?", "[", "]")

BACKTICK_RE = re.compile(r"`([^`]+)`")
NUMBER_RE = re.compile(r"(\d+)")
SEPARATOR_RE = re.compile(r"^:?-{2,}:?$")
TAG_RE = re.compile(r"^v\d+\.\d+\.\d+")


@dataclass
class Table:
    """看板里的一个 Markdown 表：标题（最近的 `#` 级标题）+ 表头 + 数据行。"""

    heading: str
    header: list[str]
    rows: list[list[str]]


@dataclass
class Failure:
    """一条失败事实（用于最后汇总并决定退出码）。"""

    where: str
    detail: str


def split_cells(line: str) -> list[str]:
    """把 Markdown 表格行拆成单元格（去掉首尾竖线，逐格 strip）。"""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [cell.strip() for cell in body.split("|")]


def is_separator_row(cells: Sequence[str]) -> bool:
    """判断是否为表头下的 `|---|---|` 分隔行。"""
    return bool(cells) and all(SEPARATOR_RE.match(cell.replace(" ", "")) for cell in cells)


def normalize_text(cell: str) -> str:
    """去掉 Markdown 强调符、行内代码反引号与所有空白，便于前缀匹配。"""
    cleaned = cell.replace("*", "").replace("`", "")
    return re.sub(r"\s+", "", cleaned)


def parse_tables(lines: Sequence[str]) -> list[Table]:
    """从看板正文解析出所有 Markdown 表（含其所属标题）。

    Args:
        lines: 看板文件按行拆分的内容。

    Returns:
        :class:`Table` 列表，顺序与文件中出现顺序一致。
    """
    tables: list[Table] = []
    heading = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            index += 1
            continue
        if line.lstrip().startswith("|") and index + 1 < len(lines):
            header = split_cells(line)
            next_cells = split_cells(lines[index + 1])
            if is_separator_row(next_cells):
                rows: list[list[str]] = []
                cursor = index + 2
                while cursor < len(lines) and lines[cursor].lstrip().startswith("|"):
                    rows.append(split_cells(lines[cursor]))
                    cursor += 1
                tables.append(Table(heading=heading, header=header, rows=rows))
                index = cursor
                continue
        index += 1
    return tables


def column_index(header: Sequence[str], name: str) -> int | None:
    """按表头名定位列下标（支持单元格里带额外说明，如 `状态`、`任务数`）。"""
    for position, cell in enumerate(header):
        if name in normalize_text(cell):
            return position
    return None


def classify_status(cell: str) -> str | None:
    """把状态单元格归一到六种状态之一；认不出返回 ``None``。"""
    text = normalize_text(cell)
    for status in STATUSES:
        if text.startswith(status):
            return status
    return None


def first_number(cell: str) -> int | None:
    """取单元格里第一串数字（`**5**（T0.1–T0.5）` → 5）。"""
    match = NUMBER_RE.search(normalize_text(cell))
    return int(match.group(1)) if match else None


def section_label_of(heading: str) -> str | None:
    """把任务表所属标题映射到分段标签（前缀匹配）。"""
    plain = normalize_text(heading)
    for label in SECTION_LABELS:
        if plain.startswith(normalize_text(label)):
            return label
    return None


def snapshot_label_of(cell: str) -> str | None:
    """把快照表行标签映射到分段标签 / 小计 / 合计；认不出返回 ``None``。"""
    plain = normalize_text(cell)
    if plain.startswith("合计"):
        return "合计"
    if "小计" in plain:
        return "小计"
    for label in SECTION_LABELS:
        if plain.startswith(normalize_text(label)):
            return label
    return None


def count_task_tables(board_text: str) -> tuple[dict[str, dict[str, int]], list[Failure], dict[str, list[str]]]:
    """统计任务表各段六种状态的数量。

    Args:
        board_text: 看板全文。

    Returns:
        ``(counts, failures, row_ids)``：``counts[label][status] = n``；
        ``failures`` 为解析失败项；``row_ids[label]`` 为该段任务 ID 列表。
    """
    counts: dict[str, dict[str, int]] = {label: dict.fromkeys(STATUSES, 0) for label in SECTION_LABELS}
    failures: list[Failure] = []
    row_ids: dict[str, list[str]] = {label: [] for label in SECTION_LABELS}

    for table in parse_tables(board_text.splitlines()):
        id_col = column_index(table.header, "任务ID")
        status_col = column_index(table.header, "状态")
        if id_col is None or status_col is None:
            continue  # 不是任务表（如 GATE 表、§4 快照表）
        label = section_label_of(table.heading)
        if label is None:
            failures.append(
                Failure(
                    where=f"任务表「{table.heading}」",
                    detail="无法归入已知分段（Phase 0–3 / M1 修复批次）：新增批次表请在 SECTION_LABELS 里登记",
                )
            )
            continue
        for row in table.rows:
            if len(row) <= max(id_col, status_col):
                continue  # 空格行 / 残缺行，不计
            task_id = normalize_text(row[id_col])
            if not task_id:
                continue
            status = classify_status(row[status_col])
            row_ids[label].append(task_id)
            if status is None:
                failures.append(
                    Failure(
                        where=f"{label} / {task_id}",
                        detail=f"状态「{row[status_col]}」不在六种取值内（{ ' / '.join(STATUSES) }）",
                    )
                )
                continue
            counts[label][status] += 1
    return counts, failures, row_ids


def parse_snapshot(board_text: str) -> tuple[dict[str, dict[str, int]], list[Failure]]:
    """解析 §4 快照表。

    Args:
        board_text: 看板全文。

    Returns:
        ``(snapshot, failures)``：``snapshot[label][column] = n``（含 `任务数` /
        六种状态 / `小计` / `合计`）。
    """
    snapshot: dict[str, dict[str, int]] = {}
    failures: list[Failure] = []

    for table in parse_tables(board_text.splitlines()):
        if column_index(table.header, "阶段") is None or column_index(table.header, "任务数") is None:
            continue
        if "快照" not in table.heading and "进度" not in table.heading:
            continue
        columns: dict[str, int] = {}
        for name in SNAPSHOT_COLUMNS:
            position = column_index(table.header, name)
            if position is None:
                failures.append(Failure(where="§4 快照表头", detail=f"缺少列「{name}」"))
                continue
            columns[name] = position
        for row in table.rows:
            if not row:
                continue
            label = snapshot_label_of(row[0])
            if label is None:
                if normalize_text(row[0]):
                    failures.append(
                        Failure(where="§4 快照行", detail=f"行标签「{row[0]}」无法识别（既不是分段也不是小计/合计）")
                    )
                continue
            entry: dict[str, int] = {}
            for name, position in columns.items():
                if position >= len(row):
                    entry[name] = 0
                    continue
                number = first_number(row[position])
                if number is None:
                    failures.append(
                        Failure(where=f"§4 快照 / {label} / {name}", detail=f"「{row[position]}」里没有数字")
                    )
                    entry[name] = 0
                    continue
                entry[name] = number
            snapshot[label] = entry
    return snapshot, failures


def check_counts(
    counts: dict[str, dict[str, int]],
    snapshot: dict[str, dict[str, int]],
) -> list[Failure]:
    """判据 1：任务表 ↔ 快照 逐段逐状态比对，并自行校验小计 / 合计。"""
    failures: list[Failure] = []

    for label in SECTION_LABELS:
        if label not in snapshot:
            failures.append(Failure(where=f"§4 快照 / {label}", detail="快照里缺少该分段行"))
            continue
        snapshot_row = snapshot[label]
        table_row = counts[label]
        for status in STATUSES:
            expected = table_row[status]
            written = snapshot_row.get(status, 0)
            if expected != written:
                failures.append(
                    Failure(
                        where=f"§4 快照 / {label} / {status}",
                        detail=f"任务表 {expected} / 快照 {written}",
                    )
                )
        total_written = snapshot_row.get("任务数", 0)
        total_counted = sum(table_row[status] for status in STATUSES)
        if total_written != total_counted:
            failures.append(
                Failure(
                    where=f"§4 快照 / {label} / 任务数",
                    detail=f"任务表 {total_counted} / 快照 {total_written}",
                )
            )
        # 分段行内部自洽：任务数 == 六种状态之和（手写数字最容易在这里漂）
        written_sum = sum(snapshot_row.get(status, 0) for status in STATUSES)
        if written_sum != total_written:
            failures.append(
                Failure(
                    where=f"§4 快照 / {label}",
                    detail=f"任务数写 {total_written}，但该行六种状态之和为 {written_sum}",
                )
            )

    # 小计必须等于 Phase 0–3 之和（脚本自己求和，不信任手写）
    if "小计" not in snapshot:
        failures.append(Failure(where="§4 快照 / 小计", detail="缺少 ‹Phase 0–3 小计› 行"))
    else:
        subtotal_row = snapshot["小计"]
        for column in SNAPSHOT_COLUMNS:
            computed = sum(snapshot.get(label, {}).get(column, 0) for label in PHASE_LABELS)
            written = subtotal_row.get(column, 0)
            if computed != written:
                failures.append(
                    Failure(where=f"§4 快照 / 小计 / {column}", detail=f"自算 {computed} / 快照 {written}")
                )

    # 合计必须等于 小计 + 批次段
    if "合计" not in snapshot:
        failures.append(Failure(where="§4 快照 / 合计", detail="缺少 合计 行"))
    else:
        total_row = snapshot["合计"]
        for column in SNAPSHOT_COLUMNS:
            computed = snapshot.get("小计", {}).get(column, 0) + snapshot.get(BATCH_LABEL, {}).get(column, 0)
            written = total_row.get(column, 0)
            if computed != written:
                failures.append(
                    Failure(where=f"§4 快照 / 合计 / {column}", detail=f"自算 {computed} / 快照 {written}")
                )

    return failures


def collect_evidence_tokens(board_text: str) -> list[tuple[str, str]]:
    """抽取任务表证据列里的反引号路径候选。

    Returns:
        ``[(路径, 所属任务ID), …]``（尚未过滤通配符 / gitignored 目录）。
    """
    tokens: list[tuple[str, str]] = []
    for table in parse_tables(board_text.splitlines()):
        id_col = column_index(table.header, "任务ID")
        if id_col is None:
            continue
        evidence_col = column_index(table.header, "证据")
        if evidence_col is None:
            continue
        for row in table.rows:
            if len(row) <= evidence_col:
                continue
            task_id = normalize_text(row[id_col]) if id_col < len(row) else "?"
            # 证据列之后可能还有列（本节表只有 7 列），一律合并——宁可多查不漏查
            evidence_text = " | ".join(row[evidence_col:])
            for token in BACKTICK_RE.findall(evidence_text):
                tokens.append((token.strip(), task_id))
    return tokens


#: 反引号里的「路径:行号」引用（如 `scripts/cubemx-init.mx:5`）——剥掉行号再判存在性。
LINE_SUFFIX_RE = re.compile(r":\d+(?:[-–]\d+)?$")

#: 反引号里的「路径」结尾可能粘着中文标点 / 括号，需剥掉再判存在性。
TRAILING_PUNCT = "，,。；;、）)》」’'\""


def classify_token(token: str) -> tuple[str, str]:
    """判断一个反引号 token 的处置类别。

    Returns:
        ``(类别, 路径)``：类别为 ``"path"`` / ``"glob"`` / ``"ignored"`` /
        ``"nonrepo"`` / ``"skip"``。
    """
    if not token or token.startswith(("http://", "https://")):
        return "skip", token
    cleaned = token.strip().rstrip(TRAILING_PUNCT).strip()
    # `scripts/cubemx-init.mx:5` 是"路径 + 行号"，不是路径本身：行号不是文件系统的一部分，
    # 不剥掉会把一条真实存在的证据判成缺失（第一版实测踩过：T1.6 的这条被判 missing）。
    cleaned = LINE_SUFFIX_RE.sub("", cleaned)
    if any(char in cleaned for char in GLOB_CHARS):
        return "glob", cleaned
    if not cleaned.startswith(PATH_PREFIXES):
        return "skip", cleaned  # tag 名 / commit sha / 裸文件名
    if cleaned.startswith(GITIGNORED_PREFIXES):
        return "ignored", cleaned
    if cleaned in NON_REPO_PATHS:
        return "nonrepo", cleaned
    return "path", cleaned


def check_evidence(tokens: Iterable[tuple[str, str]]) -> tuple[list[Failure], dict[str, int]]:
    """判据 2：证据路径存在性。"""
    failures: list[Failure] = []
    stats = {"checked": 0, "missing": 0, "ignored": 0, "glob": 0, "skip": 0, "nonrepo": 0, "duplicate": 0}
    seen: set[str] = set()

    for token, task_id in tokens:
        kind, path = classify_token(token)
        if kind != "path":
            stats[kind] += 1
            continue
        if path in seen:
            stats["duplicate"] += 1
            continue
        seen.add(path)
        stats["checked"] += 1
        if not (REPO_ROOT / path).exists():
            stats["missing"] += 1
            failures.append(Failure(where=f"{task_id} 证据列", detail=f"路径不存在：{path}"))
    return failures, stats


def current_package_version() -> str | None:
    """读 ``package.json`` 的 ``version``（判据③的「当前版本」基准）。

    Returns:
        版本号字符串；读不到或没有 ``version`` 字段时返回 ``None``（由调用方跳过判据）。

    ``errors="replace"``（B-5）：`package.json` 若被 GBK/混合字节写过，抛
    ``UnicodeDecodeError`` 只会让判据③ 带着 traceback 崩掉；这里读成带替换字符的文本，
    取不到版本号就走「跳过并打印 note」的既有路径，**不猜、不静默**。
    """
    try:
        text = (REPO_ROOT / "package.json").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(r'"version"\s*:\s*"([^"]+)"', text)
    return match.group(1).strip() if match else None


def git_tags() -> tuple[list[str], str | None]:
    """取仓库 tag 列表。

    Returns:
        ``(tags, note)``：``note`` 非空表示该判据被跳过及原因。
    """
    try:
        completed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "tag", "-l"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:  # git 未安装 / 超时
        return [], f"git 不可用（{error}），跳过发布一致性校验"
    if completed.returncode != 0:
        return [], f"git tag -l 退出码 {completed.returncode}，跳过发布一致性校验"
    tags = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not tags:
        return [], "仓库内没有可读 tag（可能未 fetch tags），该判据无适用对象"
    return tags, None


def statuses_by_id(board_text: str) -> dict[str, str]:
    """抽出 `任务ID → 状态` 映射（发布一致性判据需要单行状态，聚合值不够）。"""
    mapping: dict[str, str] = {}
    for table in parse_tables(board_text.splitlines()):
        id_col = column_index(table.header, "任务ID")
        status_col = column_index(table.header, "状态")
        if id_col is None or status_col is None:
            continue
        for row in table.rows:
            if len(row) <= max(id_col, status_col):
                continue
            task_id = normalize_text(row[id_col])
            status = classify_status(row[status_col])
            if task_id and status is not None:
                mapping[task_id] = status
    return mapping


def publish_failures(mapping: dict[str, str], note_holder: dict[str, str]) -> list[Failure]:
    """判据 3：**当前版本 tag** 存在时，T3.5 不得「待开始」（D33 的机读化）。

    旧实现只做全局代理——"任意 v0.6/v0.7 tag 存在"就检查 T3.5，既会被历史 tag
    永久触发，也会在 v0.8.0 之后因 ``TAG_RE`` 钉死而静默失效。现按
    ``v<package.json.version>`` 精确定位当前版本 tag；没打出时判据无适用对象。

    Args:
        mapping: ``任务ID → 状态``。
        note_holder: 输出参数，写入该判据的说明（含被跳过的原因）。

    Returns:
        失败项列表；判据被跳过时为空。
    """
    tags, note = git_tags()
    note_holder["note"] = note or ""
    if note:
        return []
    published = sorted(tag for tag in tags if TAG_RE.match(tag))
    if not published:
        note_holder["note"] = f"未发现合法版本 tag（共 {len(tags)} 个 tag），该判据无适用对象"
        return []
    version = current_package_version()
    if version is None:
        note_holder["note"] = "读不到 package.json 的 version，该判据无适用对象"
        return []
    expected_tag = f"v{version}"
    if expected_tag not in published:
        note_holder["note"] = (
            f"当前版本 tag {expected_tag} 尚未打出（现有：{', '.join(published)}），该判据无适用对象"
        )
        return []
    status = mapping.get("T3.5")
    if status is None:
        return [Failure(where="Phase 3 / T3.5", detail="任务表里找不到 T3.5，无法做发布一致性校验")]
    note_holder["note"] = f"当前版本 tag：{expected_tag}；T3.5 = {status}"
    if status == "待开始":
        return [
            Failure(
                where="Phase 3 / T3.5",
                detail=(
                    f"当前版本 tag {expected_tag} 已存在，但 T3.5 仍是「待开始」"
                    "—— tag 打了却没记账，属发布未收口（D33 §33.2）"
                ),
            )
        ]
    return []


def render_counts(counts: dict[str, dict[str, int]]) -> str:
    """把统计结果渲染成一行表格文本（供 `--print` 与失败时自证用）。"""
    parts = []
    for label in SECTION_LABELS:
        row = counts[label]
        cells = " / ".join(f"{status} {row[status]}" for status in STATUSES)
        parts.append(f"{label}: {cells}")
    return "\n".join(parts)


def _harden_console_streams() -> None:
    """按输出目标加固 stdout/stderr，杜绝"控制台编码不够就崩"（B-5）。

    与 `scripts/verify_generation.py` / `scripts/ioc_backup.py` / `scripts/ioc_field.py` /
    `tools/check_release.py` 同款分流（**每个脚本各持一份，不引入共享模块**）：

    - **管道 / 重定向（非 TTY）**：强制 UTF-8 —— 输出要被 CI 日志与下游脚本消费；
    - **交互式控制台（TTY）**：保留控制台自身编码，只把 errors 换成 ``backslashreplace``
      （英文 Windows 的 cp1252 打印 ``✓`` / ``✗`` / 中文不再抛 ``UnicodeEncodeError``）。

    ⚠️ TTY 那一支没有自动回归：改动后请**手动**在中文 Windows 控制台跑一次；
    管道那一支由 ``tests/test_tools_encoding.py`` 覆盖。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.isatty():
                stream.reconfigure(errors="backslashreplace")
            else:
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):
            pass


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 入口。

    Returns:
        退出码：``0`` 全部判据通过；``1`` 任一判据失败（或发现解析错误）。
    """
    _harden_console_streams()
    parser = argparse.ArgumentParser(
        prog="check_taskboard.py",
        description="校验 docs/TASKBOARD.md 的快照一致性、证据路径存在性与发布一致性",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "退出码：0=全部通过 1=存在不一致\n"
            "示例：python tools/check_taskboard.py --board /tmp/board-broken.md"
        ),
    )
    parser.add_argument("--board", default=str(DEFAULT_BOARD), help="看板路径（默认仓内 docs/TASKBOARD.md）")
    parser.add_argument(
        "--print-counts", action="store_true", dest="print_counts", help="额外打印任务表统计（自证用）"
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    board_path = Path(args.board)
    print(f"[check_taskboard] 看板：{board_path}")
    print(f"[check_taskboard] 仓根：{REPO_ROOT}")
    if not board_path.is_file():
        print(f"[check_taskboard][error] 看板不存在：{board_path}", file=sys.stderr)
        return 1

    # ⚠️ `errors="replace"`（B-5）是有意的：看板是**人写的文档**，一个坏字节不该让
    # 「快照与任务表是否一致」这个问题失去答案。替换字符会让解析找不到表/状态而**判红**，
    # 比抛 `UnicodeDecodeError` 更接近真相（文件确实读不出那一段）。
    board_text = board_path.read_text(encoding="utf-8", errors="replace")

    # ── 判据 1：快照一致性 ──────────────────────────────────────────
    print("\n== 1) §4 快照 ↔ 任务表 ==")
    counts, count_failures, _row_ids = count_task_tables(board_text)
    snapshot, snapshot_failures = parse_snapshot(board_text)
    if args.print_counts:
        print(render_counts(counts))
    if not snapshot:
        print("[check_taskboard][error] 没有解析到 §4 快照表（表头需含「阶段」与「任务数」）")
        return 1
    for label in SECTION_LABELS:
        row = counts[label]
        counted = sum(row[status] for status in STATUSES)
        print(f"  {label:<14} 任务表 {counted:>2} 条 | " + " / ".join(f"{s} {row[s]}" for s in STATUSES))

    failures: list[Failure] = list(count_failures) + list(snapshot_failures)
    failures += check_counts(counts, snapshot)

    # ── 判据 2：证据路径存在性 ──────────────────────────────────────
    print("\n== 2) 证据路径存在性 ==")
    tokens = collect_evidence_tokens(board_text)
    evidence_failures, stats = check_evidence(tokens)
    print(
        f"  反引号 token {len(tokens)} 个 → 去重后检查 {stats['checked']} 条"
        f"（重复 {stats['duplicate']}）"
    )
    print(
        f"  跳过：docs/logs/ 局部忽略 {stats['ignored']} 条 | 通配符模式 {stats['glob']} 条"
        f" | 非本仓（白名单列明）{stats['nonrepo']} 条"
        f" | 非路径（tag/sha/链接/裸名） {stats['skip']} 条"
    )
    for path, reason in NON_REPO_PATHS.items():
        print(f"    · 非本仓：{path} —— {reason}")
    if stats["missing"]:
        print(f"  缺失 {stats['missing']} 条")
    failures += evidence_failures

    # ── 判据 3：发布一致性 ─────────────────────────────────────────
    print("\n== 3) 发布一致性（当前版本 tag vs T3.5）==")
    mapping = statuses_by_id(board_text)
    note_holder: dict[str, str] = {}
    failures += publish_failures(mapping, note_holder)
    note = note_holder.get("note") or ""
    print(f"  note: {note or '（无）'}")

    # ── 汇总 ───────────────────────────────────────────────────────
    print("\n== 汇总 ==")
    if failures:
        print(f"✗ 发现 {len(failures)} 处不一致：")
        for failure in failures:
            print(f"  - {failure.where}：{failure.detail}")
        print("\n[check_taskboard] FAIL —— 修任务表或修快照，二者必须一致；不许手改数字了事。")
        return 1
    print("✓ 三组判据全部通过：快照与任务表一致、证据路径均存在、发布与看板一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
