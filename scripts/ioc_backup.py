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
import contextlib
import hashlib
import json
import os
import shutil
import socket
import sys
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

__version__ = "1.1.0"

SCHEMA = "platform32.ioc_backup/1"

EXIT_OK = 0
EXIT_NOT_FOUND = 1
EXIT_INPUT_ERROR = 2

# ── 并发写锁（0.8.0 / Q3）────────────────────────────────────────────
# 与 `scripts/ioc_field.py` 里那份**同款、各持一份**（本仓惯例：这几个脚本必须能单独拷走就用，
# 不引入共享模块）。两个工具对**同一工程目录**用**同一个锁文件** ⇒ 天然互斥。
# `--list` 是只读，**不加锁**（不写盘的命令不该被别人的写操作排队挡住）。
LOCK_FILENAME = ".cubeone-lock"
LOCK_STALE_SECONDS = 300.0  # 持锁进程崩溃后，锁超过 5 分钟视为陈旧
LOCK_POLL_INTERVAL = 0.1
LOCK_DEFAULT_TIMEOUT = 10.0
TOOL_NAME = "ioc_backup"


class LockTimeout(RuntimeError):
    """在超时预算内没能拿到锁（→ 退 2：属"环境/输入错误"，不是"域内结论"）。"""

    def __init__(self, lock_path: str, timeout: float) -> None:
        super().__init__(f"无法在 {timeout:g}s 内获取锁：{lock_path}")
        self.lock_path = lock_path
        self.timeout = timeout


def _reclaim_stale_lock(lock_path: str) -> bool:
    """锁文件 mtime 超过 ``LOCK_STALE_SECONDS`` 时回收它。

    用 ``os.replace`` 先改名到 ``.stale.<ts>`` 再删：两个进程同时判定"陈旧"时，
    **只有 rename 成功的那一个**会去删，另一个拿到 ``FileNotFoundError`` 静默放过。
    直接 ``unlink`` 会让两边都以为"我回收了"，且可能与真正持有者互相踩。

    Returns:
        ``True`` = 本次**确实回收了**一把陈旧锁（调用方应立刻重试，不要先看 deadline）；
        ``False`` = 没回收（锁很新 / 已被别人回收 / 持有者刚释放）。
    """
    try:
        if time.time() - os.path.getmtime(lock_path) <= LOCK_STALE_SECONDS:
            return False
    except OSError:
        return False
    stale_path = f"{lock_path}.stale.{int(time.time())}"
    try:
        os.replace(lock_path, stale_path)
    except OSError:
        return False  # 别人先回收了 / 持有者刚释放：都不是错误
    with contextlib.suppress(OSError):
        os.unlink(stale_path)
    return True


@contextlib.contextmanager
def acquire_ioc_lock(
    lock_dir: str | os.PathLike[str],
    timeout: float = LOCK_DEFAULT_TIMEOUT,
) -> Iterator[str]:
    """对工程目录加排他锁（锁文件 ``<dir>/.cubeone-lock``）。

    Args:
        lock_dir: 锁文件所在目录（``--project`` 目录）。
        timeout: 最长等待秒数；``0`` 表示只尝试一次、立即超时。

    Yields:
        锁文件路径。

    Raises:
        LockTimeout: 超时仍拿不到锁。
        OSError: 锁文件无法创建（权限 / 目录不存在），由调用方按输入错误处理。
    """
    lock_path = os.path.join(os.fspath(lock_dir), LOCK_FILENAME)
    deadline = time.monotonic() + max(timeout, 0.0)
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            # F-2（0.8.1 A2）：**回收成功就无条件再试一次**，先别看 deadline。
            # 否则 `--lock-timeout 0` 会死在"刚判明持有者已死（回收了）→ 立刻按超时报错，
            # 还告诉用户『另一进程正在改同一工程』"——与我们刚得到的结论自相矛盾。
            # 重试一次是安全的：陈旧锁已被移走，下一轮大概率直接 O_EXCL 成功；
            # 若此刻真有人抢到，会再次进这里，而那时 mtime 是新的 ⇒ 回收返回 False ⇒ 走 deadline。
            if _reclaim_stale_lock(lock_path):
                continue
            if time.monotonic() >= deadline:
                raise LockTimeout(lock_path, max(timeout, 0.0)) from None
            time.sleep(LOCK_POLL_INTERVAL)
            continue
        try:
            os.write(
                fd,
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "host": socket.gethostname(),
                        "tool": TOOL_NAME,
                        "ts": time.time(),
                    },
                    ensure_ascii=False,
                ).encode("utf-8"),
            )
        finally:
            os.close(fd)
        break
    try:
        yield lock_path
    finally:
        with contextlib.suppress(OSError):
            os.unlink(lock_path)

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
            "      2 还可能是**并发锁超时**（`[ioc_backup][lock-timeout]`：另一进程正在改同一工程）\n"
            "示例：python scripts/ioc_backup.py --project firmware --json-out backup.json"
        ),
    )
    parser.add_argument("--project", required=True, help="工程根目录（含 .ioc 的目录）")
    parser.add_argument("--restore", action="store_true", help="从 .ioc.bak 还原 .ioc")
    parser.add_argument("--list", action="store_true", dest="list_only", help="只列出 .ioc，不写盘")
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=LOCK_DEFAULT_TIMEOUT,
        dest="lock_timeout",
        help=(
            "获取并发写锁的最长等待秒数（默认 10；0=不等待、只尝试一次）。"
            "锁超时退 2；--list 只读、不加锁"
        ),
    )
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


def _harden_console_streams() -> None:
    """按输出目标加固 stdout/stderr，杜绝"控制台编码不够就崩"。

    为什么需要（2026-11-04，Windows CI 两次抓到，两版修法）：
    - **第一次**：Windows 英文环境控制台编码是 **cp1252**，打印 ``→`` / 中文抛
      ``UnicodeEncodeError``，脚本直接以 1 退出——用户看到的是"工具坏了"。
    - **第二次**：只把 errors 换成 backslashreplace 是**半对**。管道（非 TTY）的编码若也被污染成
      cp1252，中文会整体退化成 ``\\u7f3a`` 这类转义：**不崩，但读不了**——而下游（MCP 封装层、
      测试断言、日志检索）要的恰恰是中文原文。

    所以按目标分流（**管道要可解析，控制台要可阅读**；两者要求不同编码，不能一条规则通吃）：
    - **管道 / 重定向**（非 TTY，最常见：``regen.sh`` 重定向到日志、MCP 封装层抓管道）：
      **强制 UTF-8**。这是机器消费的路径，UTF-8 是唯一不产生歧义的编码；封装层本来就按
      UTF-8 解码，写别的编码反而会乱码。
    - **交互式控制台**（TTY）：**保留控制台自身编码**（中文 Windows = cp936，中文正常），
      只把错误处理器换成 backslashreplace —— 该编码表示不了的字符（如 cp1252 遇到 ``→``）
      转义成 ``\\u2192``，而不是抛 ``UnicodeEncodeError`` 崩掉。

    ⚠️ **TTY 那一支没有自动回归**（造 TTY 夹具的复杂度远超收益）：改动本函数后请**手动**在
    中文 Windows 控制台（cp936）与一个英文/ASCII 语言环境各跑一次，确认中文正常、``→`` 不崩。
    管道那一支由 ``tests/test_console_encoding.py`` 覆盖。

    三个脚本各自持有一份（``ioc_backup`` / ``ioc_field`` / ``verify_generation``）：这三个
    文件必须能**单独拷走就用**，不引入共享模块。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.isatty():
                stream.reconfigure(errors="backslashreplace")
            else:
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):
            # 非 TextIOWrapper（被重定向到自定义对象 / pytest capsys）或极旧版本：跳过即可，
            # 跳过的后果只是回到原行为，不会更糟。
            pass


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 入口。

    Returns:
        退出码：0 / 1 / 2。
    """
    _harden_console_streams()
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
            # 0.8.0 / Q3：还原是写操作 ⇒ 加锁；`--list` 只读不加锁。
            with acquire_ioc_lock(project_dir, args.lock_timeout):
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
            with acquire_ioc_lock(project_dir, args.lock_timeout):
                records = backup_project(project_dir)
            for record in records:
                print(
                    f"backed up {record.ioc} → {record.backup} "
                    f"({record.bytes} bytes, sha256={record.sha256[:12]}…)"
                )
    except LockTimeout as error:
        # rc=2 与"输入错误"同码：都是"没跑成"，不是"跑完的结论是失败"。
        print(
            f"[ioc_backup][lock-timeout] 无法在 {error.timeout:g}s 内获取锁：{error.lock_path}"
            "（另一进程正在改同一工程？用 --lock-timeout 调大等待）",
            file=sys.stderr,
        )
        return EXIT_INPUT_ERROR
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
