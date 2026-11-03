#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cubeone-mcp · ``.ioc`` 备份 / 还原工具。

为什么需要
----------
``.ioc`` 是 STM32 工程的**唯一事实来源**（模板 ``AGENTS.md`` §2.1）。CubeMX 生成
会原地重写它（还会把 ``ProjectManager.AskForMigrate`` 写回 ``true``，见 D7），一旦
生成后核验不通过，必须能立刻回到"生成前"的状态。

回滚的本义是 **git**（调研报告 C5：回滚粒度是 git，不是"智能修复"）。本工具是
git 之外的**第二道保险**：工程还没进版本库、或者 ``.ioc`` 处于未提交改动时，仍能
拿一份带 sha256 的快照回滚。

用法
----
::

    python scripts/ioc_backup.py --project <工程目录>              # 备份 *.ioc → *.ioc.bak
    python scripts/ioc_backup.py --project <工程目录> --list         # 只列出将备份的 .ioc
    python scripts/ioc_backup.py --project <工程目录> --restore      # 从 *.ioc.bak 还原
    python scripts/ioc_backup.py --project <工程目录> --json-out r.json

退出码：``0`` 成功；``1`` 未找到 ``.ioc``（或还原时缺 ``.ioc.bak``）；``2`` 参数/IO 错误
（**还原前的备份完整性校验失败也返回 ``2``**）。

命名约定沿用模板：``<name>.ioc.bak``（已被模板 ``.gitignore`` 的 ``*.ioc.bak`` 规则
忽略，不会污染 ``git status``）。

完整性凭据（R-C3）
------------------
备份成功后额外落一份旁路摘要 ``<name>.ioc.bak.sha256``（64 位 hex + 换行），同样走
"临时文件 + ``os.replace``"原子写。还原前先重算 ``.bak`` 的 sha256 与之比对：

- **不一致** → 拒绝还原（stderr 打 ``[ioc_backup][integrity]``，退出码 ``2``），``.ioc``
  **一个字节都不动**——"备份已被篡改 / 部分写入"时还原等于用坏数据覆盖好数据，比不还原
  危险得多；
- **旁路摘要不存在** → 视为旧版备份，允许还原，但在 stdout 打 ``[warn]`` 说明跳过了校验；
- **摘要文件本身格式非法**（不是 64 位 hex）→ 按"不可信"处理，同样拒绝还原。

为什么摘要独立成旁路文件而不是写进 ``--json-out``：``--json-out`` 是可选的，随时会被覆盖
或丢掉，而完整性校验必须在**每次**还原时都做得到；旁路文件与 ``.bak`` 同目录、同生命周期，
删 ``.bak`` 时它自然一起被清理（``*.ioc.bak.sha256`` 也不会被 ``find_ioc_files`` 当成工程）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

__version__ = "1.1.0"

SCHEMA = "platform32.ioc_backup/1"

EXIT_OK = 0
EXIT_NOT_FOUND = 1
EXIT_INPUT_ERROR = 2

#: 备份后缀（模板惯例，见 ``template-mcu-*/AGENTS.md`` 与 ``.gitignore``）。
BACKUP_SUFFIX = ".bak"

#: 完整性摘要旁路文件后缀：``<name>.ioc.bak`` → ``<name>.ioc.bak.sha256``。
SIDECAR_SUFFIX = ".sha256"

#: sha256 十六进制摘要的固定长度（用于判定旁路文件内容是否可信）。
SHA256_HEX_LEN = 64


class BackupIntegrityError(Exception):
    """``.ioc.bak`` 的 sha256 与旁路摘要不一致（疑似篡改或部分写入）。

    设计成异常而不是返回布尔：还原路径上"校验没通过"必须**中断**整个还原，
    不能靠调用方每处都记得判返回值（漏判一次就是拿坏备份覆盖好文件）。

    Attributes:
        backup: 出问题的 ``.ioc.bak`` 路径。
        expected: 旁路摘要里记录的 sha256（不可信时为其原文）。
        actual: 重新计算得到的 ``.ioc.bak`` sha256。
    """

    def __init__(self, backup: str | os.PathLike[str], expected: str, actual: str) -> None:
        self.backup = str(backup)
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"备份疑似被篡改或部分写入：{self.backup} 期望 {expected} 实际 {actual}"
        )


@dataclass(frozen=True)
class FileRecord:
    """单个 ``.ioc`` 的备份/还原记录。"""

    ioc: str
    backup: str
    bytes: int
    sha256: str

    def to_dict(self) -> dict[str, object]:
        """序列化为 JSON 片段。"""
        return {
            "ioc": self.ioc,
            "backup": self.backup,
            "bytes": self.bytes,
            "sha256": self.sha256,
        }


def sha256_of(path: str | os.PathLike[str]) -> str:
    """计算文件的 SHA-256 十六进制摘要。"""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_ioc_files(project_dir: str | os.PathLike[str]) -> list[Path]:
    """列出工程目录顶层的 ``*.ioc``（不递归，排除 ``*.ioc.bak``）。

    Args:
        project_dir: 工程根目录。

    Returns:
        按名称排序的 ``.ioc`` 路径列表。
    """
    root = Path(project_dir)
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.glob("*.ioc")
        if path.is_file() and not path.name.endswith(BACKUP_SUFFIX)
    )


def backup_path_of(ioc_path: Path) -> Path:
    """返回某个 ``.ioc`` 对应的备份路径（``name.ioc`` → ``name.ioc.bak``）。"""
    return ioc_path.with_name(ioc_path.name + BACKUP_SUFFIX)


def sidecar_path_of(backup_path: str | os.PathLike[str]) -> Path:
    """返回备份对应的完整性摘要旁路路径（``name.ioc.bak`` → ``name.ioc.bak.sha256``）。"""
    return Path(str(backup_path) + SIDECAR_SUFFIX)


def atomic_write_text(target: str | os.PathLike[str], text: str) -> None:
    """原子写文本文件（同目录临时文件 + ``os.replace``）。

    Args:
        target: 目标路径（父目录必须已存在）。
        text: 待写入内容（UTF-8，``\\n`` 换行）。

    Raises:
        OSError: 写入或替换失败（临时文件会被清理，目标文件保持原状）。
    """
    target_path = Path(target)
    handle, temp_name = tempfile.mkstemp(
        prefix=target_path.name + ".", suffix=".tmp", dir=str(target_path.parent)
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temp_name, target_path)
    except OSError:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def read_sidecar_digest(backup_path: str | os.PathLike[str]) -> str | None:
    """读取备份的旁路摘要。

    Args:
        backup_path: ``.ioc.bak`` 路径。

    Returns:
        摘要原文（已 strip）；旁路文件不存在时返回 ``None``（旧版备份）。

    Raises:
        OSError: 旁路文件存在但读不了（权限/IO）。
    """
    sidecar = sidecar_path_of(backup_path)
    if not sidecar.is_file():
        return None
    return sidecar.read_text(encoding="utf-8").strip()


def verify_backup_integrity(backup_path: str | os.PathLike[str]) -> str | None:
    """核对 ``.ioc.bak`` 与旁路摘要是否一致。

    Args:
        backup_path: ``.ioc.bak`` 路径。

    Returns:
        缺失摘要（旧版备份）时返回 ``None``，校验通过时返回实际 sha256。

    Raises:
        BackupIntegrityError: 摘要不一致或摘要格式非法（不可信）。
        OSError: 读取失败。
    """
    expected = read_sidecar_digest(backup_path)
    if expected is None:
        return None  # 旧版备份：交由调用方打印警告后放行
    actual = sha256_of(backup_path)
    # 格式非法（长度不对 / 非 hex）一律按"不可信"处理：宁可拒还原，也不要拿一个
    # 看不懂的摘要当"校验通过"——那正是 fail-open 的老毛病。
    normalized = expected.lower()
    trusted = len(normalized) == SHA256_HEX_LEN and all(
        char in "0123456789abcdef" for char in normalized
    )
    if not trusted or normalized != actual:
        raise BackupIntegrityError(backup_path, expected, actual)
    return actual


def backup_project(project_dir: str | os.PathLike[str]) -> list[FileRecord]:
    """把工程顶层每个 ``.ioc`` 复制为 ``<name>.ioc.bak``，并落一份完整性摘要旁路。

    采用"临时文件 + ``os.replace``"的原子写法，避免中途失败留下半份备份。
    ``.bak`` 落盘后立即计算 sha256，写入 ``<name>.ioc.bak.sha256``（同样原子写）——
    顺序必须是"先 ``.bak`` 再摘要"：摘要描述的是已经落盘的字节，反过来会描述一个
    只存在于临时文件里的中间态。

    Args:
        project_dir: 工程根目录。

    Returns:
        备份记录列表；未找到 ``.ioc`` 时返回空列表。

    Raises:
        OSError: 复制/写摘要失败（权限/磁盘）。
    """
    records: list[FileRecord] = []
    for ioc_path in find_ioc_files(project_dir):
        target = backup_path_of(ioc_path)
        handle, temp_name = tempfile.mkstemp(
            prefix=target.name + ".", suffix=".tmp", dir=str(target.parent)
        )
        os.close(handle)
        try:
            shutil.copy2(ioc_path, temp_name)
            os.replace(temp_name, target)
        except OSError:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
            raise
        digest = sha256_of(target)
        # 旁路摘要：64 位 hex + 换行（便于 cat/比较，也便于 grep 工具消费）。
        atomic_write_text(sidecar_path_of(target), digest + "\n")
        records.append(
            FileRecord(
                ioc=str(ioc_path),
                backup=str(target),
                bytes=target.stat().st_size,
                sha256=digest,
            )
        )
    return records


def restore_project(project_dir: str | os.PathLike[str]) -> list[FileRecord]:
    """从 ``<name>.ioc.bak`` 还原 ``.ioc``（还原前核对备份完整性，还原本身原子）。

    两阶段执行，顺序不可交换：

    1. **先全量校验**（不写盘）：逐个读旁路摘要并重算 ``.bak`` 的 sha256。任何一份不合格
       就抛 :class:`BackupIntegrityError`，此时**一个 ``.ioc`` 都没被动过**——不会出现
       "前两个工程被还原、第三个是坏备份"的半途状态。
    2. **再逐个原子替换**：同目录 ``mkstemp`` → ``copy2`` → ``os.replace``，与 backup 对称。
       中途失败最多留一个 ``.tmp`` 临时文件，不会留下半份 ``.ioc``（词法层面不可见的
       半写文件会被 CubeMX 读成损坏工程，比报错难查得多）。

    旧版备份（无旁路摘要）允许还原，但会在 stdout 打 ``[warn]`` 说明跳过了校验。

    Args:
        project_dir: 工程根目录。

    Returns:
        还原记录列表；没有任何 ``.ioc.bak`` 时返回空列表。

    Raises:
        BackupIntegrityError: 某份 ``.ioc.bak`` 与旁路摘要不一致（拒绝还原，``.ioc`` 未改动）。
        OSError: 复制/读摘要失败。
    """
    pending: list[tuple[Path, Path]] = []
    for ioc_path in find_ioc_files(project_dir):
        source = backup_path_of(ioc_path)
        if not source.is_file():
            continue
        if verify_backup_integrity(source) is None:
            # 旧版备份：放行但必须说出来。静默跳过校验等于让"完整性保障"变成薛定谔的。
            print(
                f"[ioc_backup][warn] 缺少完整性摘要（旧版备份），已跳过校验：{source}",
                file=sys.stdout,
            )
        pending.append((source, ioc_path))

    records: list[FileRecord] = []
    for source, ioc_path in pending:
        handle, temp_name = tempfile.mkstemp(
            prefix=ioc_path.name + ".", suffix=".tmp", dir=str(ioc_path.parent)
        )
        os.close(handle)
        try:
            shutil.copy2(source, temp_name)
            os.replace(temp_name, ioc_path)
        except OSError:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
            raise
        records.append(
            FileRecord(
                ioc=str(ioc_path),
                backup=str(source),
                bytes=ioc_path.stat().st_size,
                sha256=sha256_of(ioc_path),
            )
        )
    return records


def build_payload(action: str, project_dir: str, records: Sequence[FileRecord]) -> dict[str, object]:
    """构造结构化输出（供 regen.sh / Skill / CI 消费）。"""
    return {
        "schema": SCHEMA,
        "action": action,
        "project": os.path.abspath(project_dir),
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "files": [record.to_dict() for record in records],
        "tool": {"name": "ioc_backup.py", "version": __version__},
    }


def build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器。"""
    parser = argparse.ArgumentParser(
        prog="ioc_backup.py",
        description="工程 .ioc 的备份 / 还原（<name>.ioc → <name>.ioc.bak）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "退出码：0=成功 1=未找到 .ioc（或还原时缺 .bak） 2=参数/IO 错误\n"
            "      注意：2 也可能表示**还原前的备份完整性校验失败**（.bak 的 sha256 与\n"
            "      <name>.ioc.bak.sha256 不一致，疑似篡改或部分写入；此时 .ioc 未被改动）\n"
            "示例：python scripts/ioc_backup.py --project firmware --json-out backup.json"
        ),
    )
    parser.add_argument("--project", required=True, help="工程根目录（含 .ioc 的目录）")
    parser.add_argument("--restore", action="store_true", help="从 .ioc.bak 还原 .ioc")
    parser.add_argument("--list", action="store_true", dest="list_only", help="只列出 .ioc，不写盘")
    parser.add_argument("--json-out", default=None, dest="json_out", help="结构化 JSON 输出路径")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__} (schema {SCHEMA})"
    )
    return parser


def _write_json(path: str, payload: dict[str, object]) -> None:
    """写 JSON 报告（自动建父目录）。"""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 入口。

    Returns:
        退出码：0 / 1 / 2。
    """
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    project_dir = args.project
    if not os.path.isdir(project_dir):
        print(f"[ioc_backup][input-error] 工程目录不存在：{project_dir}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    iocs = find_ioc_files(project_dir)
    if not iocs:
        print(f"[ioc_backup][not-found] 目录下没有 .ioc：{project_dir}", file=sys.stderr)
        return EXIT_NOT_FOUND

    action = "list"
    records: list[FileRecord] = []

    try:
        if args.list_only:
            action = "list"
            for ioc_path in iocs:
                print(f"{ioc_path}\t{ioc_path.stat().st_size} bytes")
        elif args.restore:
            action = "restore"
            records = restore_project(project_dir)
            if not records:
                print(
                    "[ioc_backup][not-found] 没有任何 .ioc.bak 可还原；"
                    "回滚请改用 git checkout -- <工程>/*.ioc",
                    file=sys.stderr,
                )
                return EXIT_NOT_FOUND
            for record in records:
                print(f"restored {record.ioc} ← {record.backup} ({record.bytes} bytes)")
        else:
            action = "backup"
            records = backup_project(project_dir)
            for record in records:
                print(
                    f"backed up {record.ioc} → {record.backup} "
                    f"({record.bytes} bytes, sha256={record.sha256[:12]}…)"
                )
    except BackupIntegrityError as error:
        # 必须在 OSError 之前：这不是"IO 出错"，而是"备份不可信"——处置完全不同
        # （重新备份 / 找回正确快照 vs. 查权限和磁盘）。.ioc 此时一个字节都没动。
        print(
            f"[ioc_backup][integrity] {error}",
            file=sys.stderr,
        )
        return EXIT_INPUT_ERROR
    except OSError as error:
        print(f"[ioc_backup][input-error] {action} 失败：{error}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    if args.json_out:
        try:
            _write_json(args.json_out, build_payload(action, project_dir, records))
        except OSError as error:
            print(f"[ioc_backup][input-error] 写 JSON 失败：{error}", file=sys.stderr)
            return EXIT_INPUT_ERROR
        print(f"[ioc_backup] JSON 报告：{os.path.abspath(args.json_out)}")

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
