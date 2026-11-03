#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP 工具调用冒烟自检（T0.4）：真实调用工具并把证据落盘。

与 T0.2/T0.3 的「协议级握手」不同，本脚本不满足于 ``initialize`` + ``tools/list``，
而是**真的发起 tools/call**，验证工具能返回结果，从而证明「调用通道」可用。

复现方式（必须用这个解释器，它带有 ``mcp`` SDK）::

    "C:/Users/Leon/AppData/Roaming/uv/tools/vscode-cube-mcp/Scripts/python.exe" tools/mcp_smoke.py

本机系统 Python 未安装 ``mcp`` 包，直接 ``python tools/mcp_smoke.py`` 会 ImportError。
不要为此向系统 Python ``pip install`` 任何东西。

两种运行模式（日志里都会记下 ``script_sha256``，便于把日志归因到某个确切的脚本版本）::

    # 正向：正常冒烟，应 exit=0 且末行 VERDICT: SMOKE PASS
    ... python.exe tools/mcp_smoke.py

    # 负向对照：故意把 vscode-cube-mcp 的命令指向不存在的路径，
    # 用来证明脚本真的会判 FAIL 并以 exit=1 退出（不是恒 PASS）。
    ... python.exe tools/mcp_smoke.py --negative-control

正向日志写到 ``docs/logs/phase0/mcp-smoke.log``，
负向日志写到 ``docs/logs/phase0/mcp-smoke-negative.log``。

覆盖的两个 server：

A. ``vscode-cube-mcp``（``C:\\Users\\Leon\\.local\\bin\\vscode-cube-mcp.exe``）
     - ``cubemx_help``  必须成功
     - ``cubemx_load``  必须成功，且**必须证明只读**（调用前后 .ioc 的 sha256 不变）

B. ``platformio.mcp``（``uvx platformio.mcp``，``build_only`` 策略）
     - ``pio_system_info``  必须成功
     - ``pio_list_devices`` 允许「没有设备」的空结果，但调用本身必须成功返回

硬性约定：

1. 绝不修改 testbed。``cubemx_load`` 声称只读，脚本自行用 sha256 前后比对来证明；
   一旦不一致，判定 FAIL 并以非零码退出。若 ``cubemx_load`` 根本没执行（前置条件
   缺失或会话中断），只报「未执行，无法比对」，**不会**伪造成「一致」。
2. 任一必需调用失败/未执行 → 退出码 1；四个必需调用全部成功 → 0。
   摘要里的分母恒为“必需调用数”，不会因为漏测而变小。
3. 单个调用有超时；超时按规定判 FAIL，但**继续执行**后续项，最后统一判定。
4. 不依赖 cwd：仓库根由 ``Path(__file__).resolve().parent.parent`` 定位。

日志行式风格 ``OK <项> : <值>`` / ``FAIL <项> : <原因>`` / ``SKIP <项> : <原因>``，
末行为 ``VERDICT: SMOKE PASS`` 或 ``VERDICT: SMOKE FAIL``。
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata as importlib_metadata
import json
import os
import shutil
import sys
import time
import traceback
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Sequence

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# --------------------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------------------

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
SCRIPT_PATH: Final[Path] = Path(__file__).resolve()
LOG_DIR: Final[Path] = REPO_ROOT / "docs" / "logs" / "phase0"
LOG_FILE_POSITIVE: Final[Path] = LOG_DIR / "mcp-smoke.log"
LOG_FILE_NEGATIVE: Final[Path] = LOG_DIR / "mcp-smoke-negative.log"

#: 单个 tools/call 的超时（秒）。实测 ``cubemx_load`` 约 20~26s、``pio_system_info`` 约 3s，
#: 120s 余量充分；若换到明显更慢的机器上出现超时，直接调大这个常量即可。
#: 注意 server 侧 ``ST_CUBEMX_TIMEOUT=300`` 是 CubeMX 自身单次执行的预算，与本处无关。
DEFAULT_CALL_TIMEOUT_S: Final[float] = 120.0

#: initialize / tools/list 握手的超时（秒）。
INIT_TIMEOUT_S: Final[float] = 120.0

#: 返回内容写入日志时的预览长度上限。
PREVIEW_LIMIT: Final[int] = 200

#: 优先使用的 testbed .ioc；不存在时回退到 testbeds/ 下任意 .ioc。
PREFERRED_IOC: Final[Path] = (
    REPO_ROOT / "testbeds" / "stm32-g474-template" / "stm32-g474-template.ioc"
)

CUBE_SERVER_NAME: Final[str] = "vscode-cube-mcp"
PIO_SERVER_NAME: Final[str] = "platformio.mcp"

#: 本轮冒烟必须成功返回的工具全集（顺序即调用顺序、也是摘要行的顺序）。
REQUIRED_CALLS: Final[tuple[str, ...]] = (
    "cubemx_help",
    "cubemx_load",
    "pio_system_info",
    "pio_list_devices",
)

#: 必需调用的条数：摘要行的**分母恒为它**，漏测时比值只会变差、不会变好。
REQUIRED_CALL_COUNT: Final[int] = len(REQUIRED_CALLS)

#: vscode-cube-mcp 的启动命令（绝对路径，避免 PATH 歧义）。
CUBE_COMMAND: Final[Path] = Path.home() / ".local" / "bin" / "vscode-cube-mcp.exe"

#: 负向对照模式下故意使用的、必定不存在的命令。
NEGATIVE_CUBE_COMMAND: Final[Path] = Path(r"C:/definitely/not/here/vscode-cube-mcp.exe")

CUBE_ENV: Final[dict[str, str]] = {
    "ST_CUBEMX_EXE": r"C:\ST\STM32CubeMX\STM32CubeMX.exe",
    "ST_CUBEMX_ALLOWED_ROOTS": r"D:\Projects;C:\Users\Leon\WorkBuddy",
    "ST_CUBEMX_TIMEOUT": "300",
}

PIO_ENV: Final[dict[str, str]] = {
    "PLATFORMIO_MCP_POLICY": "build_only",
    "PLATFORMIO_MCP_PIO": r"C:\Users\Leon\.platformio\penv\Scripts\pio.exe",
}

#: uvx 的常见落点，PATH 里找不到时用它们兜底。
UVX_FALLBACKS: Final[tuple[Path, ...]] = (
    Path.home() / ".local" / "bin" / "uvx.exe",
    Path.home() / ".cargo" / "bin" / "uvx.exe",
    Path.home() / "AppData" / "Roaming" / "uv" / "bin" / "uvx.exe",
)

#: 日志条目名所在的列宽（按终端显示宽度算，中日韩字符占 2 列）。
LOG_LABEL_WIDTH: Final[int] = 22

#: 负向对照模式的命令行开关。
NEGATIVE_CONTROL_FLAG: Final[str] = "--negative-control"


# --------------------------------------------------------------------------------------
# 运行选项
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SmokeOptions:
    """本轮运行的开关与派生路径。

    Attributes:
        negative_control: 负向对照模式。为 True 时故意把 vscode-cube-mcp 的命令指向
            不存在的路径，用来证明脚本真的会判 FAIL 并以非零码退出。
    """

    negative_control: bool = False

    @property
    def cube_command(self) -> Path:
        """本轮的 vscode-cube-mcp 启动命令。

        Returns:
            正向模式返回真实路径；负向模式返回一个必定不存在的路径。
        """
        return NEGATIVE_CUBE_COMMAND if self.negative_control else CUBE_COMMAND

    @property
    def log_file(self) -> Path:
        """本轮的日志落盘路径。

        Returns:
            正向写 ``mcp-smoke.log``，负向写 ``mcp-smoke-negative.log``。
        """
        return LOG_FILE_NEGATIVE if self.negative_control else LOG_FILE_POSITIVE


# --------------------------------------------------------------------------------------
# 数据结构
# --------------------------------------------------------------------------------------

@dataclass
class CallRecord:
    """单次 tools/call 的观测结果。

    Attributes:
        server: server 名称。
        tool: 工具名。
        ok: 调用是否判定为通过。
        duration_ms: 调用耗时（毫秒）；超时或异常时为已等待的毫秒数。
        is_error: server 返回的 ``isError`` 标志；未拿到返回时为 None。
        text: 返回的完整文本（用于语义判断）。
        preview: ``text`` 压平换行后的前 ``PREVIEW_LIMIT`` 个字符（用于写日志）。
        chars: ``text`` 的总字符数。
        timeout_s: 本次调用使用的超时（秒）。
        note: 附加说明（如「已枚举到设备列表」）。
    """

    server: str
    tool: str
    ok: bool
    duration_ms: int
    is_error: bool | None = None
    text: str = ""
    preview: str = ""
    chars: int = 0
    timeout_s: float = DEFAULT_CALL_TIMEOUT_S
    note: str = ""


@dataclass
class SmokeReport:
    """整个冒烟过程累积的证据。

    Attributes:
        lines: 按顺序落盘的正文行。
        records: 所有已发生的调用（含失败的）。
        called: 工具名 -> 调用记录，供摘要行判定「跑过没有」。
        skipped: 工具名 -> 未执行原因，供摘要行输出 SKIP。
        failures: 失败项清单；非空即整体 FAIL。
    """

    lines: list[str] = field(default_factory=list)
    records: list[CallRecord] = field(default_factory=list)
    called: dict[str, CallRecord] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def ok(self, label: str, value: str) -> None:
        """写入一条 OK 行。

        Args:
            label: 条目名。
            value: 条目值。
        """
        self.lines.append(format_line("OK", label, value))

    def fail(self, label: str, reason: str) -> None:
        """写入一条 FAIL 行并登记失败。

        Args:
            label: 条目名。
            reason: 失败原因。
        """
        self.lines.append(format_line("FAIL", label, reason))
        self.failures.append(f"{label}: {reason}")

    def skip(self, label: str, reason: str) -> None:
        """写入一条 SKIP 行并登记「该调用未执行」。

        与 FAIL 的区别：SKIP 表示这一项压根没跑（前置条件不满足），既不是通过也不是
        失败；整体判据仍会因为它不满足「必需调用全部成功」而 FAIL。

        Args:
            label: 工具名或条目名。
            reason: 未执行的原因。
        """
        self.lines.append(format_line("SKIP", label, reason))
        self.skipped[label] = reason

    def note(self, label: str, text: str) -> None:
        """写入一条 INFO 行（不计入失败）。

        Args:
            label: 条目名。
            text: 说明文本。
        """
        self.lines.append(format_line("INFO", label, text))

    def raw(self, text: str = "") -> None:
        """写入一行原文（用于分隔符、注释、预览缩进）。

        Args:
            text: 要写入的整行文本，默认空行。
        """
        self.lines.append(text)

    def add_call(self, record: CallRecord) -> None:
        """登记一次调用并按结果写入日志。

        Args:
            record: 调用观测结果。
        """
        self.records.append(record)
        self.called[record.tool] = record
        detail = (
            f"{record.duration_ms}ms | isError={record.is_error} | "
            f"chars={record.chars} | timeout={record.timeout_s:.0f}s"
        )
        if record.note:
            detail = f"{detail} | {record.note}"
        if record.ok:
            self.ok(record.tool, detail)
        else:
            self.fail(record.tool, record.note or "调用失败")
            self.lines[-1] = f"{self.lines[-1]} [{detail}]"
        if record.preview:
            self.lines.append(f"     preview: {record.preview}")


# --------------------------------------------------------------------------------------
# 格式化与文件工具
# --------------------------------------------------------------------------------------

def display_width(text: str) -> int:
    """计算字符串在等宽终端里的显示宽度。

    Args:
        text: 任意字符串。

    Returns:
        显示列数，中日韩全角字符按 2 列计。
    """
    width = 0
    for char in text:
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def pad_label(label: str, width: int = LOG_LABEL_WIDTH) -> str:
    """把条目名补齐到指定显示宽度，使日志各列对齐。

    Args:
        label: 条目名。
        width: 目标显示宽度。

    Returns:
        右侧补空格到 ``width`` 列的字符串。
    """
    return label + " " * max(0, width - display_width(label))


def format_line(prefix: str, label: str, value: str) -> str:
    """按 ``<前缀> <条目名> : <值>`` 的行式风格拼一行日志。

    Args:
        prefix: ``OK`` / ``FAIL`` / ``SKIP`` / ``INFO``。
        label: 条目名。
        value: 条目值或原因。

    Returns:
        拼好的单行文本。
    """
    return f"{prefix.ljust(4)} {pad_label(label)} : {value}"


def format_entry(command: str, args: Sequence[str], env: dict[str, str]) -> str:
    """把 server 启动配置渲染成一行 JSON（与 handshake 日志的 ``entry`` 行同构）。

    Args:
        command: 可执行文件路径。
        args: 启动参数。
        env: 追加的环境变量。

    Returns:
        紧凑的单行 JSON 字符串。
    """
    return json.dumps(
        {"command": command, "args": list(args), "env": env},
        ensure_ascii=False,
    )


def sha256_file(path: Path) -> str:
    """计算文件的 sha256 十六进制摘要。

    Args:
        path: 目标文件路径。

    Returns:
        小写十六进制摘要字符串。
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def flatten(text: str) -> str:
    """把多行文本压平成单行，便于写进行式日志。

    Args:
        text: 原始文本。

    Returns:
        换行、制表符与连续空白全部折叠成单个空格的单行文本。
    """
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())


def truncate(text: str, limit: int = PREVIEW_LIMIT) -> str:
    """截断文本到指定长度。

    Args:
        text: 原始文本。
        limit: 最大保留字符数。

    Returns:
        长度不超过 ``limit`` 的字符串，超长时以 ``…`` 收尾。
    """
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def extract_text(result: Any) -> str:
    """从 ``CallToolResult`` 中抽取文本内容。

    Args:
        result: SDK 返回的调用结果对象。

    Returns:
        拼接后的文本；非文本块用 ``str()`` 兜底。
    """
    pieces: list[str] = []
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        pieces.append(text if isinstance(text, str) else str(block))
    if not pieces:
        structured = getattr(result, "structured_content", None)
        if structured is not None:
            pieces.append(str(structured))
    return "\n".join(pieces)


def resolve_uvx() -> str | None:
    """定位 uvx 可执行文件。

    Returns:
        uvx 的绝对路径；找不到时返回 None。
    """
    found = shutil.which("uvx")
    if found:
        return found
    for candidate in UVX_FALLBACKS:
        if candidate.is_file():
            return str(candidate)
    return None


def pick_ioc() -> Path | None:
    """挑选一个用于 ``cubemx_load`` 的 .ioc 文件。

    Returns:
        优先返回 ``testbeds/stm32-g474-template/stm32-g474-template.ioc``；
        不存在时返回 ``testbeds/`` 下按路径排序的第一个 .ioc；都没有则返回 None。
    """
    if PREFERRED_IOC.is_file():
        return PREFERRED_IOC
    candidates = sorted((REPO_ROOT / "testbeds").rglob("*.ioc"))
    return candidates[0] if candidates else None


# --------------------------------------------------------------------------------------
# 单次调用
# --------------------------------------------------------------------------------------

async def invoke(
    session: ClientSession,
    server: str,
    tool: str,
    arguments: dict[str, Any] | None = None,
) -> CallRecord:
    """执行一次 tools/call 并记录观测结果。

    Args:
        session: 已 initialize 的客户端会话。
        server: server 名称，用于日志。
        tool: 工具名。
        arguments: 工具入参，默认为空字典。

    Returns:
        调用观测结果；超时与异常都会被捕获成 ``ok=False`` 的记录，不抛出。
    """
    timeout_s = DEFAULT_CALL_TIMEOUT_S
    started = time.perf_counter()
    try:
        result = await session.call_tool(
            tool,
            arguments if arguments is not None else {},
            read_timeout_seconds=timeout_s,
        )
    except TimeoutError:
        elapsed = int((time.perf_counter() - started) * 1000)
        return CallRecord(
            server=server,
            tool=tool,
            ok=False,
            duration_ms=elapsed,
            timeout_s=timeout_s,
            note=f"调用超时（>{timeout_s:.0f}s）",
        )
    except Exception as exc:  # noqa: BLE001 - 冒烟脚本需要把任何异常落盘而不是崩掉
        elapsed = int((time.perf_counter() - started) * 1000)
        return CallRecord(
            server=server,
            tool=tool,
            ok=False,
            duration_ms=elapsed,
            timeout_s=timeout_s,
            note=f"异常 {type(exc).__name__}: {truncate(flatten(str(exc)), 160)}",
        )

    elapsed = int((time.perf_counter() - started) * 1000)
    text = extract_text(result)
    is_error = bool(getattr(result, "is_error", False))
    return CallRecord(
        server=server,
        tool=tool,
        ok=not is_error,
        duration_ms=elapsed,
        is_error=is_error,
        text=text,
        preview=truncate(flatten(text)),
        chars=len(text),
        timeout_s=timeout_s,
        note="" if not is_error else "server 返回 isError=True",
    )


# --------------------------------------------------------------------------------------
# A. vscode-cube-mcp
# --------------------------------------------------------------------------------------

def report_ioc_readonly(
    report: SmokeReport,
    ioc: Path | None,
    hash_before: str | None,
) -> None:
    """比对 .ioc 的 sha256，为 ``cubemx_load`` 的「只读」声明出证。

    只有在 ``cubemx_load`` 确实执行过时，才会给出「一致」的结论。未执行时明确写
    「未执行，无法比对」——两个哈希相同并不构成只读证据，不能拿来冒名顶替。

    Args:
        report: 冒烟报告。
        ioc: 目标 .ioc；为 None 表示压根没找到文件。
        hash_before: 调用前的 sha256；为 None 表示没算过。
    """
    if ioc is None or hash_before is None:
        report.skip("ioc_readonly", "找不到 .ioc，无从比对")
        return

    hash_after = sha256_file(ioc)
    report.ok("ioc_sha256_after", hash_after)

    if "cubemx_load" not in report.called:
        report.skip(
            "ioc_readonly",
            "cubemx_load 未执行，无法比对"
            f"（before={hash_before[:16]}… after={hash_after[:16]}…，"
            "两者相同不构成只读证据）",
        )
    elif hash_after == hash_before:
        report.ok("ioc_readonly", "sha256 前后一致，文件未被修改")
    else:
        report.fail(
            "ioc_readonly",
            f"sha256 变化 {hash_before} -> {hash_after}，cubemx_load 改动了 .ioc",
        )


async def smoke_cube(report: SmokeReport, options: SmokeOptions) -> None:
    """对 vscode-cube-mcp 执行只读冒烟。

    调用顺序：``cubemx_help`` → ``cubemx_load``。``cubemx_load`` 前后对目标 .ioc
    计算 sha256 并比对，以自证「只读」。前置条件不满足时，两个工具都记 SKIP。

    Args:
        report: 冒烟报告，结果追加其中。
        options: 运行选项（决定用真实命令还是负向对照的假命令）。
    """
    report.raw()
    report.raw(f"--- A. {CUBE_SERVER_NAME} ---")

    cube_command = options.cube_command
    ioc = pick_ioc()
    hash_before = sha256_file(ioc) if ioc is not None else None

    # ioc 与命令是两条独立的前置事实，无论哪条不满足都要如实记下来。
    if ioc is not None and hash_before is not None:
        report.ok("ioc", str(ioc))
        report.ok("ioc_sha256_before", hash_before)
    else:
        report.fail("ioc", "testbeds/ 下找不到任何 .ioc")

    blocker: str | None = None
    if not cube_command.is_file():
        report.fail("command", f"找不到可执行文件 {cube_command}")
        blocker = f"前置 vscode-cube-mcp 命令不存在（{cube_command.name}），未执行"
    elif ioc is None:
        blocker = "前置 .ioc 缺失，未执行"
    else:
        report.ok("entry", format_entry(str(cube_command), [], CUBE_ENV))

    if blocker is not None:
        report.skip("cubemx_help", blocker)
        report.skip("cubemx_load", blocker)
        report_ioc_readonly(report, ioc, hash_before)
        return

    parameters = StdioServerParameters(
        command=str(cube_command),
        args=[],
        env=dict(CUBE_ENV),
        cwd=str(REPO_ROOT),
    )

    try:
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=INIT_TIMEOUT_S)
                tools = await asyncio.wait_for(session.list_tools(), timeout=INIT_TIMEOUT_S)
                report.ok("tools_count", str(len(tools.tools)))

                report.add_call(
                    await invoke(session, CUBE_SERVER_NAME, "cubemx_help", {"topic": ""})
                )
                report.add_call(
                    await invoke(session, CUBE_SERVER_NAME, "cubemx_load", {"ioc": str(ioc)})
                )
    except Exception as exc:  # noqa: BLE001 - 启动/握手失败要落盘而不是崩溃
        report.fail(
            "session",
            f"{type(exc).__name__}: {truncate(flatten(str(exc)), 200)}",
        )
    finally:
        report_ioc_readonly(report, ioc, hash_before)


# --------------------------------------------------------------------------------------
# B. platformio.mcp
# --------------------------------------------------------------------------------------

async def smoke_platformio(report: SmokeReport) -> None:
    """对 platformio.mcp 执行只读冒烟。

    调用顺序：``pio_system_info`` → ``pio_list_devices``。后者在「没有设备」时返回
    空结果是正常的，只要调用本身成功就算通过。

    Args:
        report: 冒烟报告，结果追加其中。
    """
    report.raw()
    report.raw(f"--- B. {PIO_SERVER_NAME} ---")

    uvx = resolve_uvx()
    if uvx is None:
        report.fail("command", "PATH 与常见落点都找不到 uvx 可执行文件")
        reason = "前置 uvx 不存在，未执行"
        report.skip("pio_system_info", reason)
        report.skip("pio_list_devices", reason)
        return

    report.ok("entry", format_entry(uvx, ["platformio.mcp"], PIO_ENV))
    pio_exe = Path(PIO_ENV["PLATFORMIO_MCP_PIO"])
    if pio_exe.is_file():
        report.ok("pio_exe", str(pio_exe))
    else:
        report.note("pio_exe", f"{pio_exe} 不存在，交由 server 自行兜底")

    parameters = StdioServerParameters(
        command=uvx,
        args=["platformio.mcp"],
        env=dict(PIO_ENV),
        cwd=str(REPO_ROOT),
    )

    try:
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=INIT_TIMEOUT_S)
                tools = await asyncio.wait_for(session.list_tools(), timeout=INIT_TIMEOUT_S)
                report.ok("tools_count", str(len(tools.tools)))

                report.add_call(
                    await invoke(session, PIO_SERVER_NAME, "pio_system_info")
                )

                devices = await invoke(session, PIO_SERVER_NAME, "pio_list_devices")
                if devices.ok:
                    # 用完整返回文本判「有没有枚举到设备」，不用截断后的 preview。
                    devices.note = (
                        "已枚举到设备" if '"port"' in devices.text
                        else "未枚举到设备，属正常结果（调用本身成功）"
                    )
                report.add_call(devices)
    except Exception as exc:  # noqa: BLE001 - 启动/握手失败要落盘而不是崩溃
        report.fail(
            "session",
            f"{type(exc).__name__}: {truncate(flatten(str(exc)), 200)}",
        )


# --------------------------------------------------------------------------------------
# 判据与渲染
# --------------------------------------------------------------------------------------

def is_pass(report: SmokeReport) -> bool:
    """判定整轮冒烟是否通过。

    四个必需调用必须**全部真的执行过**并且全部成功；``failures`` 非空直接否。
    这里逐项点名检查 ``REQUIRED_CALLS``，而不是比较条数——避免「某个 server 起不来、
    只剩两项调用」时 2/2 被误判成 PASS。

    Args:
        report: 冒烟报告。

    Returns:
        通过返回 True，否则 False。
    """
    if report.failures:
        return False
    return all(
        tool in report.called and report.called[tool].ok for tool in REQUIRED_CALLS
    )


def required_status(report: SmokeReport, tool: str) -> tuple[str, str]:
    """返回某个必需调用的状态前缀与说明。

    Args:
        report: 冒烟报告。
        tool: 工具名。

    Returns:
        ``(前缀, 说明)``，前缀为 ``OK`` / ``FAIL`` / ``SKIP``。
    """
    record = report.called.get(tool)
    if record is None:
        return "SKIP", report.skipped.get(tool, "未执行")
    if record.ok:
        return "OK", "通过"
    return "FAIL", record.note or "调用失败"


def build_header(options: SmokeOptions) -> list[str]:
    """构造日志头部。

    Args:
        options: 运行选项。

    Returns:
        日志头部各行。
    """
    try:
        sdk_version = importlib_metadata.version("mcp")
    except importlib_metadata.PackageNotFoundError:  # pragma: no cover - 环境异常兜底
        sdk_version = "unknown"

    if options.negative_control:
        head = ["===== MCP 工具调用冒烟自检 (T0.4) — 负向对照 ====="]
        head.append(
            "# 本日志来自负向对照运行：故意把 vscode-cube-mcp 的命令指向不存在的路径"
            f"（{NEGATIVE_CUBE_COMMAND}），"
        )
        head.append(
            "# 用于证明脚本真的会判 FAIL 并以 exit=1 退出，而不是恒 PASS。"
        )
    else:
        head = ["===== MCP 工具调用冒烟自检 (T0.4) ====="]

    head.extend(
        [
            f"time     : {datetime.now().isoformat(timespec='seconds')}",
            f"mode     : {'negative-control' if options.negative_control else 'positive'}",
            f"runner   : {sys.executable}",
            f"script   : {SCRIPT_PATH}",
            f"script_sha256 : {sha256_file(SCRIPT_PATH)}",
            f"repo_root: {REPO_ROOT}",
            f"mcp_sdk  : {sdk_version}",
            f"cwd      : {os.getcwd()}",
        ]
    )
    return head


def render(report: SmokeReport, options: SmokeOptions) -> str:
    """把报告渲染成完整日志文本。

    Args:
        report: 冒烟报告。
        options: 运行选项。

    Returns:
        可直接落盘的日志全文，末行为 VERDICT。
    """
    passed = sum(
        1 for tool in REQUIRED_CALLS
        if tool in report.called and report.called[tool].ok
    )
    missing = [
        tool for tool in REQUIRED_CALLS
        if not (tool in report.called and report.called[tool].ok)
    ]

    lines = build_header(options)
    lines.extend(report.lines)

    lines.append("")
    lines.append("--- 汇总 ---")
    # 逐项列出四个必需调用的真实状态：跑过的写 OK/FAIL，没跑的写 SKIP。
    for tool in REQUIRED_CALLS:
        prefix, detail = required_status(report, tool)
        lines.append(format_line(prefix, tool, detail))

    # 分母恒为 REQUIRED_CALL_COUNT：漏测只会让比值变差，不会变小。
    if missing:
        lines.append(
            format_line(
                "FAIL",
                "必需调用通过",
                f"{passed} / {REQUIRED_CALL_COUNT}（缺：{'、'.join(missing)}）",
            )
        )
    else:
        lines.append(
            format_line("OK", "必需调用通过", f"{passed} / {REQUIRED_CALL_COUNT}")
        )

    lines.append(
        format_line(
            "INFO",
            "判据",
            "cubemx_load 必须成功且 .ioc 的 sha256 不变；"
            "pio_list_devices 允许空结果，调用成功即通过",
        )
    )
    for record in report.records:
        lines.append(
            format_line(
                "INFO",
                "耗时",
                f"{record.server}/{record.tool} = {record.duration_ms}ms",
            )
        )
    for failure in report.failures:
        lines.append(format_line("INFO", "失败项", failure))

    lines.append("")
    lines.append(f"VERDICT: {'SMOKE PASS' if is_pass(report) else 'SMOKE FAIL'}")
    return "\n".join(lines) + "\n"


def write_log(path: Path, text: str) -> None:
    """把日志写入指定路径（UTF-8，LF 换行）。

    Args:
        path: 日志文件路径。
        text: 日志全文。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------------------

async def run_smoke(report: SmokeReport, options: SmokeOptions) -> None:
    """依次对两个 server 做冒烟。

    单个 server 失败不影响后续 server，最后统一判定。

    Args:
        report: 冒烟报告。
        options: 运行选项。
    """
    await smoke_cube(report, options)
    await smoke_platformio(report)


def parse_options(argv: Sequence[str]) -> SmokeOptions:
    """解析命令行参数。

    Args:
        argv: 不含程序名的参数列表。

    Returns:
        运行选项。

    Raises:
        ValueError: 出现未知参数时抛出，避免拼错开关却静默按正向跑。
    """
    unknown = [arg for arg in argv if arg != NEGATIVE_CONTROL_FLAG]
    if unknown:
        raise ValueError(
            f"未知参数 {unknown}；只支持 {NEGATIVE_CONTROL_FLAG}"
        )
    return SmokeOptions(negative_control=NEGATIVE_CONTROL_FLAG in argv)


def main(argv: Sequence[str] | None = None) -> int:
    """脚本入口。

    Args:
        argv: 命令行参数（不含程序名）。

    Returns:
        进程退出码：四个必需调用全部成功为 0，否则为 1。
    """
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        options = parse_options(args)
    except ValueError as exc:
        print(f"参数错误: {exc}", file=sys.stderr)
        return 2

    report = SmokeReport()
    try:
        asyncio.run(run_smoke(report, options))
    except Exception as exc:  # noqa: BLE001 - 顶层兜底，保证一定写出 VERDICT
        report.fail(
            "runner",
            f"{type(exc).__name__}: {truncate(flatten(str(exc)), 200)}",
        )
        report.raw()
        report.raw("--- traceback ---")
        for line in traceback.format_exc().splitlines():
            report.raw(f"  {line}")
    finally:
        text = render(report, options)
        write_log(options.log_file, text)
        print(text, end="")
    return 0 if is_pass(report) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
