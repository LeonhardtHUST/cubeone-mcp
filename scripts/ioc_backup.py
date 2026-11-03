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

退出码：``0`` 成功；``1`` 未找到 ``.ioc``（或还原时缺 ``.ioc.bak``）；``2`` 参数/IO 错误。

命名约定沿用模板：``<name>.ioc.bak``（已被模板 ``.gitignore`` 的 ``*.ioc.bak`` 规则
忽略，不会污染 ``git status``）。
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

__version__ = "1.0.0"

SCHEMA = "platform32.ioc_backup/1"

EXIT_OK = 0
EXIT_NOT_FOUND = 1
EXIT_INPUT_ERROR = 2

#: 备份后缀（模板惯例，见 ``template-mcu-*/AGENTS.md`` 与 ``.gitignore``）。
BACKUP_SUFFIX = ".bak"


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


def backup_project(project_dir: str | os.PathLike[str]) -> list[FileRecord]:
    """把工程顶层每个 ``.ioc`` 复制为 ``<name>.ioc.bak``。

    采用"临时文件 + ``os.replace``"的原子写法，避免中途失败留下半份备份。

    Args:
        project_dir: 工程根目录。

    Returns:
        备份记录列表；未找到 ``.ioc`` 时返回空列表。

    Raises:
        OSError: 复制失败（权限/磁盘）。
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
        records.append(
            FileRecord(
                ioc=str(ioc_path),
                backup=str(target),
                bytes=target.stat().st_size,
                sha256=sha256_of(target),
            )
        )
    return records


def restore_project(project_dir: str | os.PathLike[str]) -> list[FileRecord]:
    """从 ``<name>.ioc.bak`` 还原 ``.ioc``。

    Args:
        project_dir: 工程根目录。

    Returns:
        还原记录列表；没有任何 ``.ioc.bak`` 时返回空列表。

    Raises:
        OSError: 复制失败。
    """
    records: list[FileRecord] = []
    for ioc_path in find_ioc_files(project_dir):
        source = backup_path_of(ioc_path)
        if not source.is_file():
            continue
        shutil.copy2(source, ioc_path)
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
