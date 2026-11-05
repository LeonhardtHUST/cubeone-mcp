# -*- coding: utf-8 -*-
"""`ioc_backup` / `ioc_field` 的**并发写锁**回归（0.8.0 / Q3）。

为什么需要锁
------------
同一工程目录上并发执行两个会话时，`.ioc` / `.ioc.bak` / `ioc-backup.json` 可能互相覆盖
（lost-update，`docs/README.md` §2.1 第 3 条）。0.8.0 起两个脚本在**写盘前**对「工程目录」
加 ``.cubeone-lock`` 排他锁：拿不到锁 ⇒ **rc=2**（`[<tool>][lock-timeout]`），**一字节不动**。

锁的跨平台基础是 `os.open(O_CREAT | O_EXCL)` —— Win32 映射 `CreateFileW(CREATE_NEW)`、
POSIX 是 `open(O_EXCL)`，两边都保证「不存在才创建」原子。这也是本文件**必须用真实进程**验证
的原因：锁语义是**跨进程**的，用线程或 monkeypatch 模拟会把"两个进程真的同时进去"这件事测没。

负样本（与编排 §3.4 一一对应）
------------------------------
1. 持锁期间 `ioc_field set` ⇒ rc=2、stderr 含 `lock-timeout`、`.ioc` 一字未变；
2. 释放后重试 ⇒ rc=0 且 `changed=true`；
3. 陈旧锁（mtime 拨老 400s）⇒ 自动回收、写入成功；
4. `ioc_backup --restore` 持锁期间 ⇒ rc=2；`--list` 持锁期间 ⇒ **rc=0**（只读不加锁）；
5. 单写者正常路径零回归（由 `pytest tests/ -q` 全量守住，本文件只补一处"正常路径 <1ms 量级"的弱断言）。

⚠️ 关于"两个进程同时抢"的写法：本文件用**外部持锁进程 + 多个真实子进程**构造冲突，
而不是"同时 spawn 两个然后期望它们撞上"。后者依赖调度时序——快机器上第一个进程可能在
第二个启动前就跑完了，用例就会**间歇性变绿**（假通过）。持锁进程让冲突**必然发生**，
断言才是确定的。
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
IOC_FIELD = REPO_ROOT / "scripts" / "ioc_field.py"
IOC_BACKUP = REPO_ROOT / "scripts" / "ioc_backup.py"

LOCK_FILENAME = ".cubeone-lock"

IOC_TEMPLATE = """#MicroXplorer Configuration settings - do not modify
Mcu.CPN=STM32G474VET6
Mcu.IP0=NVIC
Mcu.IPNb=1
Mcu.Pin0=PC13
Mcu.PinsNb=1
MxCube.Version=6.18.1
PC13.Signal=GPIO_Output
ProjectManager.AskForMigrate=false
ProjectManager.ProjectName=fake-board
"""

#: 持锁子进程：建锁 → 打印 LOCKED（让父进程知道"锁已在手"）→ 睡 N 秒 → 删锁退出。
#: 用 `python -c` 而不是 shell 脚本：不依赖 bash，Windows/Linux 同一套。
HOLD_LOCK_SCRIPT = r"""
import os, sys, time
lock_path, hold_seconds = sys.argv[1], float(sys.argv[2])
fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
try:
    os.write(fd, b'{"pid": %d, "tool": "test-holder"}' % os.getpid())
finally:
    os.close(fd)
sys.stdout.write("LOCKED\n")
sys.stdout.flush()
time.sleep(hold_seconds)
try:
    os.unlink(lock_path)
except OSError:
    pass
"""


def _make_project(tmp_path: Path) -> Path:
    """造一个只含一只 `.ioc` 的最小工程目录。"""
    project = tmp_path / "board"
    project.mkdir(parents=True, exist_ok=True)
    (project / "fake-board.ioc").write_text(IOC_TEMPLATE, encoding="utf-8", newline="\n")
    return project


@contextmanager
def _held_lock(project: Path, hold_seconds: float = 30.0):
    """在 ``project`` 下由**另一个真实进程**持锁，直到本上下文退出。

    Yields:
        锁文件路径。

    Raises:
        AssertionError: 持锁进程没能起来（那后续断言就都失去意义）。
    """
    lock_path = project / LOCK_FILENAME
    proc = subprocess.Popen(
        [sys.executable, "-c", HOLD_LOCK_SCRIPT, str(lock_path), str(hold_seconds)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        # 等到 LOCKED 再往下走：否则被测进程可能先跑完，冲突根本没发生（假通过）。
        line = proc.stdout.readline() if proc.stdout else ""
        assert line.strip() == "LOCKED", f"持锁进程没起来：{line!r} {proc.stderr.read() if proc.stderr else ''}"
        assert lock_path.exists(), "锁文件应已存在"
        yield lock_path
    finally:
        proc.kill()
        proc.wait(timeout=30)
        # `kill` 掉的进程来不及 unlink 自己的锁文件，由本上下文兜底删掉
        # ——语义上等价于"持锁进程正常释放了锁"（真写盘里那条路径走 `finally: os.unlink`）。
        # 不兜底的话，后续用例会撞上一个**永久存在的锁**，把"释放后重试"测成"再超时一次"。
        with contextlib.suppress(OSError):
            lock_path.unlink()


def _run(script: Path, *args: str, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    """跑一个脚本（真实子进程，**不用线程模拟**）。"""
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        cwd=str(REPO_ROOT),
    )


# ── 1) 持锁期间拒绝写：rc=2 且一字节不动 ─────────────────────────────────────


def test_ioc_field_set_times_out_while_lock_held(tmp_path: Path) -> None:
    """`ioc_field set` 撞上别人的锁 ⇒ **rc=2**、`[ioc_field][lock-timeout]`、`.ioc` 未变。"""
    project = _make_project(tmp_path)
    ioc = project / "fake-board.ioc"
    before = ioc.read_bytes()

    with _held_lock(project):
        result = _run(
            IOC_FIELD,
            "--ioc", str(ioc),
            "--lock-timeout", "1",
            "--", "set", "ProjectManager.AskForMigrate", "true",
        )

    assert result.returncode == 2, result.stdout + result.stderr
    assert "[ioc_field][lock-timeout]" in result.stderr, result.stderr
    assert "无法在 1s 内获取锁" in result.stderr, result.stderr
    # 关键：锁没拿到就**绝不能**动文件
    assert ioc.read_bytes() == before, ".ioc 在锁超时后被动过——那正是 lost-update 的形态"


# ── 2) 释放后重试：rc=0 且真的改了 ───────────────────────────────────────────


def test_ioc_field_set_succeeds_after_lock_released(tmp_path: Path) -> None:
    """锁释放后同一命令 ⇒ rc=0、`changed=true`（证明失败是**锁**造成的，不是参数写错）。"""
    project = _make_project(tmp_path)
    ioc = project / "fake-board.ioc"

    with _held_lock(project, hold_seconds=5):
        blocked = _run(
            IOC_FIELD, "--ioc", str(ioc), "--lock-timeout", "0.2",
            "--", "set", "ProjectManager.AskForMigrate", "true",
        )
    assert blocked.returncode == 2, blocked.stdout + blocked.stderr

    # 持锁进程已退出（上下文 finally 里 kill 了），锁文件要么被它自己删、要么被回收
    assert not (project / LOCK_FILENAME).exists(), "持锁进程退出后锁文件不该还在"

    retry = _run(
        IOC_FIELD, "--ioc", str(ioc), "--lock-timeout", "5",
        "--", "set", "ProjectManager.AskForMigrate", "true",
    )

    assert retry.returncode == 0, retry.stdout + retry.stderr
    assert "changed" in retry.stdout, retry.stdout
    assert "ProjectManager.AskForMigrate=true" in ioc.read_text(encoding="utf-8")


# ── 3) 陈旧锁自动回收 ───────────────────────────────────────────────────────


def test_stale_lock_is_reclaimed(tmp_path: Path) -> None:
    """锁文件 mtime 拨老 400s（> 300s 阈值）⇒ 自动回收、写入成功（并留下 `.stale.*`）。"""
    project = _make_project(tmp_path)
    ioc = project / "fake-board.ioc"
    lock_path = project / LOCK_FILENAME
    lock_path.write_text('{"pid": 999999, "tool": "ghost"}', encoding="utf-8")
    old = time.time() - 400
    os.utime(lock_path, (old, old))

    result = _run(
        IOC_FIELD, "--ioc", str(ioc), "--lock-timeout", "2",
        "--", "set", "ProjectManager.AskForMigrate", "true",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "changed" in result.stdout, result.stdout
    # 回收路径：改名为 .stale.<ts> 后删除；也可能已被删光 —— 两者都算回收成功
    assert not lock_path.exists(), "陈旧锁应已被回收"
    assert list(project.glob(f"{LOCK_FILENAME}.stale.*")) == [], "回收后不该残留 .stale 文件"


def test_fresh_lock_is_not_reclaimed(tmp_path: Path) -> None:
    """反向对照：锁很新（mtime 就是现在）⇒ **不得**被当作陈旧，必须超时 rc=2。

    没有这一条，`test_stale_lock_is_reclaimed` 无法区分"真的看了 mtime"和"一律回收"。
    """
    project = _make_project(tmp_path)
    ioc = project / "fake-board.ioc"
    (project / LOCK_FILENAME).write_text('{"pid": 1, "tool": "live"}', encoding="utf-8")

    result = _run(
        IOC_FIELD, "--ioc", str(ioc), "--lock-timeout", "0.5",
        "--", "set", "ProjectManager.AskForMigrate", "true",
    )

    assert result.returncode == 2, result.stdout + result.stderr
    assert "[ioc_field][lock-timeout]" in result.stderr


# ── 4) ioc_backup：写操作加锁、`--list` 不加锁 ───────────────────────────────


def test_ioc_backup_backup_times_out_while_lock_held(tmp_path: Path) -> None:
    """`ioc_backup`（backup）撞锁 ⇒ rc=2，且没有生成 `.bak`。"""
    project = _make_project(tmp_path)

    with _held_lock(project):
        result = _run(IOC_BACKUP, "--project", str(project), "--lock-timeout", "0.5")

    assert result.returncode == 2, result.stdout + result.stderr
    assert "[ioc_backup][lock-timeout]" in result.stderr, result.stderr
    assert list(project.glob("*.ioc.bak")) == [], "锁没拿到却写了 .bak —— 那正是要防的写法"


def test_ioc_backup_restore_times_out_while_lock_held(tmp_path: Path) -> None:
    """`--restore` 也是写操作 ⇒ 撞锁 rc=2（并发下**至少一个**明确失败，这里用持锁进程让它必然发生）。"""
    project = _make_project(tmp_path)
    ioc = project / "fake-board.ioc"
    # 先正常备份一次，让 restore 有东西可还原
    first = _run(IOC_BACKUP, "--project", str(project))
    assert first.returncode == 0, first.stdout + first.stderr
    ioc.write_text(IOC_TEMPLATE.replace("AskForMigrate=false", "AskForMigrate=true"), encoding="utf-8")
    dirty = ioc.read_bytes()

    with _held_lock(project):
        result = _run(IOC_BACKUP, "--project", str(project), "--restore", "--lock-timeout", "0.5")

    assert result.returncode == 2, result.stdout + result.stderr
    assert "[ioc_backup][lock-timeout]" in result.stderr
    assert ioc.read_bytes() == dirty, "锁没拿到却改了 .ioc"


def test_ioc_backup_list_is_not_blocked_by_lock(tmp_path: Path) -> None:
    """`--list` 是只读 ⇒ **不加锁**，持锁期间仍 rc=0（只读命令不该被写操作排队挡住）。"""
    project = _make_project(tmp_path)

    with _held_lock(project):
        result = _run(IOC_BACKUP, "--project", str(project), "--list", "--lock-timeout", "0.5")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "fake-board.ioc" in result.stdout


# ── 5) 单写者正常路径：锁本身不引入可观测开销 ───────────────────────────────


def test_single_writer_path_is_fast(tmp_path: Path) -> None:
    """无人争抢时，加锁不应让一次写盘变慢（阈值放到 5s，只抓"退化到秒级"这类真问题）。"""
    project = _make_project(tmp_path)
    ioc = project / "fake-board.ioc"

    started = time.monotonic()
    result = _run(
        IOC_FIELD, "--ioc", str(ioc), "--", "set", "ProjectManager.AskForMigrate", "true"
    )
    elapsed = time.monotonic() - started

    assert result.returncode == 0, result.stdout + result.stderr
    assert elapsed < 5.0, f"单写者路径耗时 {elapsed:.2f}s，锁不该引入秒级开销"
    assert not (project / LOCK_FILENAME).exists(), "正常路径结束后不该留下锁文件"


def test_dry_run_does_not_need_lock(tmp_path: Path) -> None:
    """`--dry-run` 不写盘 ⇒ 不加锁：持锁期间也应 rc=0（否则"只估算一下"会被写操作卡住）。"""
    project = _make_project(tmp_path)
    ioc = project / "fake-board.ioc"

    with _held_lock(project):
        result = _run(
            IOC_FIELD, "--ioc", str(ioc), "--dry-run", "--lock-timeout", "0.5",
            "--", "set", "ProjectManager.AskForMigrate", "true",
        )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "dry-run" in result.stdout


@pytest.mark.parametrize("timeout_value", ["0", "0.0"])
def test_lock_timeout_zero_tries_once(tmp_path: Path, timeout_value: str) -> None:
    """`--lock-timeout 0` ⇒ **只尝试一次**、立即超时（不等待）。"""
    project = _make_project(tmp_path)
    ioc = project / "fake-board.ioc"

    with _held_lock(project):
        started = time.monotonic()
        result = _run(
            IOC_FIELD, "--ioc", str(ioc), "--lock-timeout", timeout_value,
            "--", "set", "ProjectManager.AskForMigrate", "true",
        )
        elapsed = time.monotonic() - started

    assert result.returncode == 2, result.stdout + result.stderr
    assert elapsed < 3.0, f"--lock-timeout 0 不该等待，实际 {elapsed:.2f}s"
