#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP 工具调用冒烟自检（T0.4）：真实调用工具并把证据落盘。

与 T0.2/T0.3 的「协议级握手」不同，本脚本不满足于 ``initialize`` + ``tools/list``，
而是**真的发起 tools/call**，验证工具能返回结果，从而证明「调用通道」可用。

复现方式（必须用这个解释器，它带有 ``mcp`` SDK）::

    "C:/Users/Leon/AppData/Roaming/uv/tools/vscode-cube-mcp/Scripts/python.exe" tools/mcp_smoke.py

本机系统 Python 未安装 ``mcp`` 包，直接 ``python tools/mcp_smoke.py`` 会 ImportError。
不要为此向系统 Python ``pip install`` 任何东西。

三种运行模式（日志里都会记下 ``script_sha256``，便于把日志归因到某个确切的脚本版本）::

    # 正向：正常冒烟，应 exit=0 且末行 VERDICT: SMOKE PASS
    ... python.exe tools/mcp_smoke.py

    # 负向对照：故意把 vscode-cube-mcp 的命令指向不存在的路径，
    # 用来证明脚本真的会判 FAIL 并以 exit=1 退出（不是恒 PASS）。
    # 注意：这条路径在 tools/call 之前就因「命令不存在」而 SKIP，
    # 因此**不会**触达 ``ok = not is_error`` 判据。
    ... python.exe tools/mcp_smoke.py --negative-control

    # 负向错误响应：cube server 正常启动（命令存在、能握手），
    # 让 cubemx_load **真的被调用**并失败，覆盖三条失败路径：
    #   [越界]     .ioc 在临时目录、不存在      → 白名单拒绝      → isError=True
    #   [缺失]     .ioc 在白名单内、不存在      → ".ioc 文件不存在" → isError=True
    #   [执行失败] .ioc 在白名单内但内容是垃圾   → "[FAIL exit=None]…" → isError=False
    ... python.exe tools/mcp_smoke.py --negative-error

三种模式的日志分别写到::

    docs/logs/phase0/mcp-smoke.log            # 正向
    docs/logs/phase0/mcp-smoke-negative.log   # 负向对照（命令不存在）
    docs/logs/phase0/mcp-smoke-error.log      # 负向错误响应（isError 分支）

第三份日志的存在意义：``--negative-control`` 证明的是「前置不满足时脚本会判 FAIL」，
而不是「调用发出了、server 返回错误、脚本判 FAIL」。后者由 ``--negative-error`` 覆盖，
它是唯一真正把返回侧判据跑过的模式。

**判据（重要）**：通过与否 = ``(not isError) and (返回文本不是失败形态)``。
只看 ``isError`` 是不够的——``vscode-cube-mcp`` 的工具在**执行失败**时并不抛异常，
而是正常返回 ``"[FAIL exit=N]\\n…"`` 字符串，``isError`` 仍是 False。
本脚本把这类响应判为 FAIL，判据与 server 自己的
``ok = returncode == 0 and not any(line.strip() == "KO" ...)`` 对齐。
详细形态见 :func:`detect_text_failure`。

实测记录（2026-11-03，`--negative-error` 三个子情形）::

    [越界]     isError=True   文本 "Error executing tool cubemx_load"
    [缺失]     isError=True   文本 "Error executing tool cubemx_load"
    [执行失败] isError=False  文本 "[FAIL exit=None]\\nTIMEOUT: CubeMX 子进程超过 25s
                              被终止(已强杀进程树)"
       ↑ 这一行就是「返回值说成功、实际失败」：只看 isError 会判通过（假绿）

为什么 [执行失败] 需要 ``ST_CUBEMX_TIMEOUT=25``：垃圾 ``.ioc`` 会触发 CubeMX 的
**模态对话框** ``Load Project — Not a valid ioc file — [OK]``，无头 ``-q`` 进程挂在
对话框上等人点 OK，直到超时才被强杀。原 300s 会让整轮冒烟卡 5 分钟且客户端先超时；
压到 25s 既快又稳定，返回形态与「CubeMX 非零退出」完全相同（都以 ``[FAIL`` 开头）。

三个子情形的 ``.ioc`` 落点（这条安排本身就是证据）：

* [越界]、[缺失] 都不需要创建文件，只把路径交给 server；
* [执行失败] 的垃圾 ``.ioc`` 落在 ``ST_CUBEMX_ALLOWED_ROOTS`` **之内**（
  :data:`BAD_IOC_DIR`，仓库之外、``testbeds/`` 之外），这样才能通过白名单守门、
  真把路径交给 CubeMX；运行期创建、``finally`` 删除，创建前用
  :func:`is_within_testbeds` 自查，落进 testbeds 直接判 FAIL。


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
   失败判据是 ``(not isError) and (返回文本不是失败形态)``——返回值说成功、
   实际失败的那种响应会被判 FAIL。
   ``--negative-error`` 模式下 exit=1 是**预期结果**（判据不因此放宽或反转，
   仍走同一套判定，只是把两条失败路径真的跑了一遍）。
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
import tempfile
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
LOG_FILE_NEGATIVE_ERROR: Final[Path] = LOG_DIR / "mcp-smoke-error.log"

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

#: vscode-cube-mcp 的启动命令（绝对路径，避免 PATH 歧义）。
CUBE_COMMAND: Final[Path] = Path.home() / ".local" / "bin" / "vscode-cube-mcp.exe"

#: 负向对照模式下故意使用的、必定不存在的命令。
NEGATIVE_CUBE_COMMAND: Final[Path] = Path(r"C:/definitely/not/here/vscode-cube-mcp.exe")

#: testbed 根目录。凡是「假路径」都必须落在它之外，避免污染 testbeds 全树零写入的结论。
TESTBEDS_ROOT: Final[Path] = REPO_ROOT / "testbeds"

#: 负向错误响应模式下的子情形 A：路径越界 + 不存在。
#:
#: 落点取系统临时目录（Windows 通常是 ``%LOCALAPPDATA%\\Temp``），**一定**在
#: ``testbeds/`` 之外，也**一定**不在 ``ST_CUBEMX_ALLOWED_ROOTS`` 里，因此会被
#: server 的 ``_check_path`` 直接拒绝。这里只是拼一个字符串路径交给 server，
#: 脚本自身不会创建它，因此对磁盘零写入。
NEGATIVE_ERROR_IOC: Final[Path] = Path(tempfile.gettempdir()) / "no-such-project.ioc"

#: 垃圾 .ioc 的内容：三行废话，CubeMX 无法解析。
NEGATIVE_ERROR_BAD_IOC_BODY: Final[str] = (
    "This is NOT a valid STM32CubeMX project file.\n"
    "garbage line 2: %%% @@@ ###\n"
    "garbage line 3: not a single key=value pair\n"
)

#: 负向错误响应模式下写进日志的返回文本预览长度（团队要求前 500 字）。
TEXT_PREVIEW_LIMIT: Final[int] = 500

CUBE_ENV: Final[dict[str, str]] = {
    "ST_CUBEMX_EXE": r"C:\ST\STM32CubeMX\STM32CubeMX.exe",
    "ST_CUBEMX_ALLOWED_ROOTS": r"D:\Projects;C:\Users\Leon\WorkBuddy",
    "ST_CUBEMX_TIMEOUT": "300",
}

#: 子情形 B/C 的工作目录：**必须落在 ``ST_CUBEMX_ALLOWED_ROOTS`` 之内**，否则会被
#: ``_check_path`` 先拦成「路径越界」，测不到「文件缺失」与「执行失败」两条路径。
#:
#: 取白名单的第一项（``D:\Projects``）下的一个专用临时目录，因此它在仓库之外
#: （不会污染 git 状态）也在 ``testbeds/`` 之外。运行期创建、``finally`` 中删除。
BAD_IOC_DIR: Final[Path] = (
    Path(CUBE_ENV["ST_CUBEMX_ALLOWED_ROOTS"].split(";")[0]) / ".mcp-smoke-tmp"
)

#: 子情形 B：在白名单内、但**不存在**的 .ioc（测「文件缺失」而非「越界」）。
NEGATIVE_ERROR_MISSING_IOC: Final[Path] = BAD_IOC_DIR / "no-such-project.ioc"

#: 子情形 C：在白名单内、**存在且后缀 .ioc、但内容是垃圾**的 .ioc（测「执行失败」）。
NEGATIVE_ERROR_BAD_IOC: Final[Path] = BAD_IOC_DIR / "bad-project.ioc"

#: 负向错误响应模式下给 CubeMX 子进程的预算（秒）。
#:
#: 垃圾 .ioc 会让 CubeMX 弹出模态对话框 ``Not a valid ioc file``，无头进程挂在对话框上
#: 等人点 OK，直到 ``ST_CUBEMX_TIMEOUT`` 才被强杀（实测原 300s 根本等不到，客户端先超时）。
#: 压到 25s：既让 server 自己的 ``subprocess.TimeoutExpired -> ok=False`` 分支产出
#: ``[FAIL exit=None]``（``isError`` 仍是 False），又不必真等 5 分钟。
NEGATIVE_ERROR_CUBEMX_TIMEOUT: Final[str] = "25"

#: 三个子情形标签（同时作为摘要行的条目名，自解释，免去在汇总里回查 header）。
CASE_OUT_OF_ROOT: Final[str] = "cubemx_load[越界]"
CASE_MISSING_IOC: Final[str] = "cubemx_load[缺失]"
CASE_BAD_IOC: Final[str] = "cubemx_load[执行失败]"

#: 负向错误响应的三个子情形（顺序即调用顺序、也是摘要行的顺序）。
ERROR_CASES: Final[tuple[str, ...]] = (
    CASE_OUT_OF_ROOT,
    CASE_MISSING_IOC,
    CASE_BAD_IOC,
)

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

#: 负向错误响应模式的命令行开关（让 tools/call 真的失败，触达 ``isError`` 分支）。
NEGATIVE_ERROR_FLAG: Final[str] = "--negative-error"

#: 全部已支持的开关；参数解析与提示文案都以它为准。
SUPPORTED_FLAGS: Final[tuple[str, ...]] = (NEGATIVE_CONTROL_FLAG, NEGATIVE_ERROR_FLAG)


# --------------------------------------------------------------------------------------
# 运行选项
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SmokeOptions:
    """本轮运行的开关与派生路径。

    Attributes:
        negative_control: 负向对照模式。为 True 时故意把 vscode-cube-mcp 的命令指向
            不存在的路径，用来证明脚本真的会判 FAIL 并以非零码退出。
        negative_error: 负向错误响应模式。为 True 时 cube server 正常启动、正常握手，
            但 ``cubemx_load`` 的 ``.ioc`` 指向一个故意不存在的路径，使工具**真的被
            调用**，从而触达 server 返回 ``isError=True`` 的分支——这是唯一真正验证
            ``ok = not is_error`` 这条判据的模式。
    """

    negative_control: bool = False
    negative_error: bool = False

    @property
    def mode(self) -> str:
        """本轮模式名（写进日志 header 的 ``mode:`` 行）。

        Returns:
            ``positive`` / ``negative-control`` / ``negative-error`` 三者之一。
        """
        if self.negative_error:
            return "negative-error"
        if self.negative_control:
            return "negative-control"
        return "positive"

    @property
    def cube_command(self) -> Path:
        """本轮的 vscode-cube-mcp 启动命令。

        Returns:
            负向对照模式返回一个必定不存在的路径；其余模式（正向、负向错误响应）
            返回真实路径——负向错误响应模式要求 server 能正常启动。
        """
        return NEGATIVE_CUBE_COMMAND if self.negative_control else CUBE_COMMAND

    @property
    def log_file(self) -> Path:
        """本轮的日志落盘路径。

        Returns:
            正向写 ``mcp-smoke.log``，负向对照写 ``mcp-smoke-negative.log``，
            负向错误响应写 ``mcp-smoke-error.log``（三份互不覆盖）。
        """
        if self.negative_error:
            return LOG_FILE_NEGATIVE_ERROR
        return LOG_FILE_NEGATIVE if self.negative_control else LOG_FILE_POSITIVE

    @property
    def ioc(self) -> Path | None:
        """本轮交给 ``cubemx_load`` 的 ``.ioc`` 路径。

        Returns:
            负向错误响应模式返回 ``NEGATIVE_ERROR_IOC``（不存在的临时路径）；
            其余模式返回 ``pick_ioc()`` 的结果（可能为 None）。
        """
        return NEGATIVE_ERROR_IOC if self.negative_error else pick_ioc()

    @property
    def cube_env(self) -> dict[str, str]:
        """本轮 cube server 的环境变量。

        Returns:
            ``CUBE_ENV`` 的副本。负向错误响应模式只调整 ``ST_CUBEMX_TIMEOUT``
            （25s），**不动** ``ST_CUBEMX_ALLOWED_ROOTS``——子情形 B/C 用的假 ``.ioc``
            本来就放在白名单内（见 :data:`BAD_IOC_DIR`），不需要放宽白名单，
            因此「路径越界」这条分支也保持原样可测。日志里的 ``entry`` 行会原样
            打印环境，可复核。
        """
        env = dict(CUBE_ENV)
        if self.negative_error:
            env["ST_CUBEMX_TIMEOUT"] = NEGATIVE_ERROR_CUBEMX_TIMEOUT
        return env


# --------------------------------------------------------------------------------------
# 数据结构
# --------------------------------------------------------------------------------------

@dataclass
class CallRecord:
    """单次 tools/call 的观测结果。

    Attributes:
        server: server 名称。
        tool: 工具名。
        ok: 调用是否判定为通过（``isError`` 为 False **且**返回文本不是失败形态）。
        duration_ms: 调用耗时（毫秒）；超时或异常时为已等待的毫秒数。
        is_error: server 返回的 ``isError`` 标志；未拿到返回时为 None。
        text: 返回的完整文本（用于语义判断）。
        preview: ``text`` 压平换行后的前 ``PREVIEW_LIMIT`` 个字符（用于写日志）。
        chars: ``text`` 的总字符数。
        timeout_s: 本次调用使用的超时（秒）。
        note: 附加说明（如「已枚举到设备列表」）。
        text_failed: 返回文本是否命中失败形态（``[FAIL`` 前缀或独立 ``KO`` 行）。
        text_reason: ``text_failed`` 为 True 时的判定依据说明。
        log_label: 登记时使用的条目名（默认与 ``tool`` 相同，负向错误响应模式下为
            ``cubemx_load[A]`` / ``cubemx_load[B]``）。
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
    text_failed: bool = False
    text_reason: str = ""
    log_label: str = ""


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

    def add_call(self, record: CallRecord, label: str | None = None) -> None:
        """登记一次调用并按结果写入日志。

        Args:
            record: 调用观测结果。
            label: 可选的登记名/日志条目名。默认用工具名；负向错误响应模式下同一个
                工具会跑多个子情形，用 ``cubemx_load[A]`` / ``cubemx_load[B]`` 区分，
                避免后一次覆盖前一次的记录。
        """
        key = label or record.tool
        record.log_label = key
        self.records.append(record)
        self.called[key] = record
        detail = (
            f"{record.duration_ms}ms | isError={record.is_error} | "
            f"text_fail={record.text_failed} | "
            f"chars={record.chars} | timeout={record.timeout_s:.0f}s"
        )
        if record.note:
            detail = f"{detail} | {record.note}"
        if record.ok:
            self.ok(key, detail)
        else:
            self.fail(key, record.note or "调用失败")
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

def detect_text_failure(raw_text: str) -> tuple[bool, str]:
    """按 server 自己的失败形态判断返回文本是否为失败。

    ``vscode-cube-mcp`` 的写/读工具在**执行失败**时并不抛异常，而是正常返回::

        f"[{'OK' if r['ok'] else 'FAIL'} exit={r['exit_code']}]\\n{r['output']}"

    此时 ``isError`` 仍是 False。只看 ``isError`` 会把这种失败判成通过——即
    「返回值说成功、实际失败」，所以必须叠加文本侧判据。两种失败形态与 server 侧
    ``ok = proc.returncode == 0 and not any(line.strip() == "KO" ...)`` 对齐：

    1. 文本（去前导空白后）以 ``[FAIL`` 开头；
    2. 存在**整行等于** ``KO`` 的行（注意是整行，不是子串——与 server 判定口径一致）。

    Args:
        raw_text: token 级抽取后的**原始**返回文本（**不要**先压平，压平会消灭换行，
            使整行 ``KO`` 判据永久失效）。

    Returns:
        ``(是否失败, 依据说明)``；未命中失败形态时返回 ``(False, "")``。
    """
    stripped = raw_text.lstrip()
    if stripped.startswith("[FAIL"):
        first_line = stripped.splitlines()[0] if stripped.splitlines() else ""
        return True, f"返回文本以 [FAIL 开头（{truncate(flatten(first_line), 80)}）"
    ko_lines = [line for line in raw_text.splitlines() if line.strip() == "KO"]
    if ko_lines:
        return True, f"返回文本含 {len(ko_lines)} 行独立 KO（server 自身的失败标记）"
    return False, ""


async def invoke(
    session: ClientSession,
    server: str,
    tool: str,
    arguments: dict[str, Any] | None = None,
) -> CallRecord:
    """执行一次 tools/call 并记录观测结果。

    判定判据：``ok = (not isError) and (返回文本不是失败形态)``。只看 ``isError``
    不够——server 在执行失败时返回的是 ``[FAIL exit=N]`` 这样的正常字符串，
    ``isError`` 依然是 False。

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
    # 文本侧判据：isError 为 False 不代表执行成功（见 detect_text_failure 的说明）。
    text_failed, text_reason = detect_text_failure(text)
    if is_error:
        note = "server 返回 isError=True"
    elif text_failed:
        note = f"isError=False 但返回文本判失败：{text_reason}"
    else:
        note = ""
    return CallRecord(
        server=server,
        tool=tool,
        ok=(not is_error) and not text_failed,
        duration_ms=elapsed,
        is_error=is_error,
        text=text,
        preview=truncate(flatten(text)),
        chars=len(text),
        timeout_s=timeout_s,
        note=note,
        text_failed=text_failed,
        text_reason=text_reason,
    )


# --------------------------------------------------------------------------------------
# A. vscode-cube-mcp
# --------------------------------------------------------------------------------------

def is_within_testbeds(path: Path) -> bool:
    """判断路径是否落在 ``testbeds/`` 之内。

    用于给「假路径不许进 testbeds」这条红线做自证：负向错误响应模式用的
    ``.ioc`` 路径必须落在 testbeds 之外，否则会破坏「testbeds 全树零写入」的结论。

    Args:
        path: 待判断路径（允许不存在）。

    Returns:
        落在 testbeds 之内返回 True，否则 False。
    """
    try:
        path.resolve().relative_to(TESTBEDS_ROOT.resolve())
    except ValueError:
        return False
    return True


def report_ioc_readonly(
    report: SmokeReport,
    ioc: Path | None,
    hash_before: str | None,
    absent_reason: str = "找不到 .ioc，无从比对",
) -> None:
    """比对 .ioc 的 sha256，为 ``cubemx_load`` 的「只读」声明出证。

    只有在 ``cubemx_load`` 确实执行过时，才会给出「一致」的结论。未执行时明确写
    「未执行，无法比对」——两个哈希相同并不构成只读证据，不能拿来冒名顶替。

    Args:
        report: 冒烟报告。
        ioc: 目标 .ioc；为 None 表示压根没找到文件。
        hash_before: 调用前的 sha256；为 None 表示没算过。
        absent_reason: 缺少可比对哈希时写入 SKIP 的原因说明。
    """
    if ioc is None or hash_before is None:
        report.skip("ioc_readonly", absent_reason)
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


def report_fake_ioc_guard(report: SmokeReport, ioc: Path) -> None:
    """为负向错误响应模式下的假 .ioc 路径出具前置自证。

    Args:
        report: 冒烟报告。
        ioc: 故意不存在的 .ioc 路径。
    """
    inside_testbeds = is_within_testbeds(ioc)
    report.note(
        "ioc_fake_path",
        f"{ioc} | exists={ioc.exists()}（期望 False） | "
        f"in_testbeds={inside_testbeds}（期望 False）",
    )
    if ioc.exists():
        report.fail(
            "ioc_fake_path",
            f"假路径 {ioc} 竟然已存在，本用例不成立（server 可能真的读到文件）",
        )
    if inside_testbeds:
        report.fail(
            "ioc_fake_path",
            f"假路径 {ioc} 落在 testbeds/ 之内，违反「testbeds 零写入」红线",
        )


def report_error_branch(report: SmokeReport) -> None:
    """为「``ok = (not isError) and (文本不是失败形态)`` 判据是否真的被跑到」出证。

    三个子情形各自一条证据行，外加返回文本前 ``TEXT_PREVIEW_LIMIT`` 字。任一子情形
    未执行时如实写"未执行"，不拿别条的结果冒名顶替。

    Args:
        report: 冒烟报告。
    """
    for label in ERROR_CASES:
        record = report.called.get(label)
        if record is None:
            report.note(
                "error_branch",
                f"{label} 未执行，该子情形未触达（判据在这一支上仍属未验证）",
            )
            continue
        report.note(
            "error_branch",
            f"{label} 真的发出了 tools/call：isError={record.is_error} | "
            f"text_failed={record.text_failed} | "
            f"判据 (not is_error) and not text_failed 得 ok={record.ok}",
        )
        report.note(
            "raw[:500]",
            f"{label} = {truncate(flatten(record.text), TEXT_PREVIEW_LIMIT)}",
        )


def write_bad_ioc(path: Path) -> None:
    """写一个「存在、后缀 .ioc、内容是垃圾」的文件。

    该文件用于子情形 C：让 server 的 ``_ioc_path`` 通过（在白名单内、存在、是 .ioc），
    从而真的把路径交给 CubeMX，触发「执行失败」那条路径。

    Args:
        path: 目标路径，调用方必须保证它在 ``testbeds/`` 之外。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(NEGATIVE_ERROR_BAD_IOC_BODY, encoding="utf-8", newline="\n")


def remove_bad_ioc_dir(attempts: int = 180, delay_s: float = 0.5) -> bool:
    """删除 :data:`BAD_IOC_DIR` 及其内容，失败时退避重试。

    **为什么需要重试，而且要等这么久**：子情形 C 的 CubeMX 是被 ``ST_CUBEMX_TIMEOUT``
    强杀的，挂着模态对话框的进程在被 kill 之后仍继续持有 ``.ioc`` 的句柄。实测
    （2026-11-03，``ST_CUBEMX_TIMEOUT=25``）：``tools/call`` 返回后 **36.4s** 才第一次
    ``unlink`` 成功，期间连续 55 次 ``OSError``。因此这里给到 90s 的退避窗口
    （180 × 0.5s），成功即返回，不留固定开销——文件没被占用时第一次就过。

    只删本脚本自己建的那个专用目录，绝不递归删其它路径。

    Args:
        attempts: 最多尝试次数。
        delay_s: 每次失败后的等待秒数。

    Returns:
        目录最终已不存在（含本就不存在）返回 True，否则 False。
    """
    for attempt in range(1, attempts + 1):
        for path in (NEGATIVE_ERROR_BAD_IOC, NEGATIVE_ERROR_MISSING_IOC):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass  # 被刚强杀的 CubeMX 占用，靠下一轮重试
        try:
            BAD_IOC_DIR.rmdir()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            if attempt < attempts:
                time.sleep(delay_s)
    return False


def sweep_bad_ioc(report: SmokeReport, label: str) -> None:
    """清理 :data:`BAD_IOC_DIR` 并把结果如实写进日志（不隐瞒耗时）。

    Args:
        report: 冒烟报告。
        label: 日志条目名（开头清扫用 ``bad_ioc_preswept``，结尾清运用
            ``bad_ioc_cleaned``）。
    """
    started = time.perf_counter()
    cleaned = remove_bad_ioc_dir()
    elapsed = time.perf_counter() - started
    bad_exists = NEGATIVE_ERROR_BAD_IOC.exists()
    detail = (
        f"{BAD_IOC_DIR}（bad exists={bad_exists}，dir exists={BAD_IOC_DIR.exists()}，"
        f"等待 {elapsed:.1f}s）"
    )
    if cleaned and not bad_exists:
        report.ok(label, f"已删除 {detail}")
    else:
        report.fail(
            label,
            f"清理失败，残留 {BAD_IOC_DIR}，需手工删除。{detail}",
        )


async def run_negative_error_cases(report: SmokeReport, session: ClientSession) -> None:
    """在同一个会话里依次跑负向错误响应的三个子情形。

    * ``cubemx_load[越界]``：``.ioc`` 指向系统临时目录下**不存在**的路径
      → server 在 ``_check_path`` 按白名单拒绝 → ``isError=True``。
    * ``cubemx_load[缺失]``：``.ioc`` 在白名单内但**不存在**
      → server 在 ``_ioc_path`` 抛 ``.ioc 文件不存在`` → ``isError=True``。
    * ``cubemx_load[执行失败]``：``.ioc`` 在白名单内、存在、后缀 ``.ioc``，但内容是垃圾
      → CubeMX 弹模态对话框挂住 → 被 ``ST_CUBEMX_TIMEOUT`` 强杀 → server 正常返回
      ``[FAIL exit=None]…``，``isError=False``。
      这一支正是「返回值说成功、实际失败」的现场：只看 ``isError`` 会假通过。

    Args:
        report: 冒烟报告，结果追加其中。
        session: 已 initialize 的客户端会话。
    """
    report.raw()
    report.raw("--- A-1. [越界] .ioc 在临时目录、不存在 → 期望 isError=True ---")
    report.add_call(
        await invoke(
            session, CUBE_SERVER_NAME, "cubemx_load", {"ioc": str(NEGATIVE_ERROR_IOC)}
        ),
        label=CASE_OUT_OF_ROOT,
    )

    report.raw()
    report.raw("--- A-2. [缺失] .ioc 在白名单内、不存在 → 期望 isError=True ---")
    report.note(
        "missing_ioc",
        f"{NEGATIVE_ERROR_MISSING_IOC} | exists={NEGATIVE_ERROR_MISSING_IOC.exists()}"
        "（期望 False） | in_testbeds="
        f"{is_within_testbeds(NEGATIVE_ERROR_MISSING_IOC)}（期望 False）",
    )
    report.add_call(
        await invoke(
            session,
            CUBE_SERVER_NAME,
            "cubemx_load",
            {"ioc": str(NEGATIVE_ERROR_MISSING_IOC)},
        ),
        label=CASE_MISSING_IOC,
    )

    report.raw()
    report.raw("--- A-3. [执行失败] .ioc 在白名单内、存在、内容是垃圾 → 期望 isError=False ---")
    inside_testbeds = is_within_testbeds(NEGATIVE_ERROR_BAD_IOC)
    report.note(
        "bad_ioc",
        f"{NEGATIVE_ERROR_BAD_IOC} | in_testbeds={inside_testbeds}（期望 False） | "
        f"{len(NEGATIVE_ERROR_BAD_IOC_BODY)} 字节垃圾内容",
    )
    if inside_testbeds:
        report.fail(
            "bad_ioc",
            "垃圾 .ioc 落在 testbeds/ 之内，违反「testbeds 零写入」红线，该子情形不执行",
        )
        return
    if BAD_IOC_DIR.exists():
        # 上一轮残留（例如被强杀的 CubeMX 当时还占着句柄）：先清掉再写，保持目录干净。
        report.note("bad_ioc_preexisting", f"{BAD_IOC_DIR} 已存在，先清扫上一轮残留")
        sweep_bad_ioc(report, "bad_ioc_preswept")
    try:
        write_bad_ioc(NEGATIVE_ERROR_BAD_IOC)
        report.ok("bad_ioc_written", f"{NEGATIVE_ERROR_BAD_IOC.stat().st_size} 字节")
        report.add_call(
            await invoke(
                session, CUBE_SERVER_NAME, "cubemx_load", {"ioc": str(NEGATIVE_ERROR_BAD_IOC)}
            ),
            label=CASE_BAD_IOC,
        )
    finally:
        sweep_bad_ioc(report, "bad_ioc_cleaned")


async def smoke_cube(report: SmokeReport, options: SmokeOptions) -> None:
    """对 vscode-cube-mcp 执行只读冒烟。

    调用顺序：``cubemx_help`` → ``cubemx_load``。``cubemx_load`` 前后对目标 .ioc
    计算 sha256 并比对，以自证「只读」。前置条件不满足时，两个工具都记 SKIP。

    负向错误响应模式（``options.negative_error``）下，命令与握手一切正常，只有
    ``cubemx_load`` 的 ``.ioc`` 换成三类坏输入，让工具真的被调用：
    [越界]（临时目录、不存在 → 白名单拒绝 → ``isError=True``）、
    [缺失]（白名单内、不存在 → ``.ioc 文件不存在`` → ``isError=True``）、
    [执行失败]（白名单内、存在但内容是垃圾 → 正常返回 ``[FAIL …]``、``isError=False``）。
    该模式下没有「调用前哈希」可算，只读比对如实记 SKIP。环境另见
    :attr:`SmokeOptions.cube_env`。

    Args:
        report: 冒烟报告，结果追加其中。
        options: 运行选项（决定用真实命令还是负向对照的假命令、用真 .ioc 还是坏 .ioc）。
    """
    report.raw()
    report.raw(f"--- A. {CUBE_SERVER_NAME} ---")

    cube_command = options.cube_command
    ioc = options.ioc
    # 假路径（负向错误响应模式）不存在，因此 hash_before 自然为 None，不做只读比对。
    hash_before = sha256_file(ioc) if ioc is not None and ioc.is_file() else None

    if options.negative_error and ioc is not None:
        report_fake_ioc_guard(report, ioc)

    # ioc 与命令是两条独立的前置事实，无论哪条不满足都要如实记下来。
    if ioc is not None and hash_before is not None:
        report.ok("ioc", str(ioc))
        report.ok("ioc_sha256_before", hash_before)
    elif options.negative_error and ioc is not None:
        # 文件不存在正是本用例的输入，不是脚本或环境的缺陷，故记 INFO 而非 FAIL。
        report.note(
            "ioc",
            f"{ioc}（负向错误响应子情形 [越界]：该文件故意不存在，期望 isError=True）",
        )
    else:
        report.fail("ioc", "testbeds/ 下找不到任何 .ioc")

    blocker: str | None = None
    if not cube_command.is_file():
        report.fail("command", f"找不到可执行文件 {cube_command}")
        blocker = f"前置 vscode-cube-mcp 命令不存在（{cube_command.name}），未执行"
    elif ioc is None:
        blocker = "前置 .ioc 缺失，未执行"
    else:
        report.ok("entry", format_entry(str(cube_command), [], options.cube_env))

    if blocker is not None:
        report.skip("cubemx_help", blocker)
        report.skip("cubemx_load", blocker)
        report_ioc_readonly(report, ioc, hash_before)
        return

    parameters = StdioServerParameters(
        command=str(cube_command),
        args=[],
        env=dict(options.cube_env),
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
                if options.negative_error:
                    # 子情形 A（文件不存在）+ 子情形 B（执行失败）都要真的调用一次。
                    await run_negative_error_cases(report, session)
                    report_error_branch(report)
                else:
                    report.add_call(
                        await invoke(
                            session, CUBE_SERVER_NAME, "cubemx_load", {"ioc": str(ioc)}
                        )
                    )
    except Exception as exc:  # noqa: BLE001 - 启动/握手失败要落盘而不是崩溃
        report.fail(
            "session",
            f"{type(exc).__name__}: {truncate(flatten(str(exc)), 200)}",
        )
    finally:
        report_ioc_readonly(
            report,
            ioc,
            hash_before,
            absent_reason=(
                "负向错误响应模式：.ioc 故意不存在，没有调用前哈希可比对"
                if options.negative_error
                else "找不到 .ioc，无从比对"
            ),
        )


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

    if options.negative_error:
        head = ["===== MCP 工具调用冒烟自检 (T0.4) — 负向错误响应 (3 条失败路径) ====="]
        head.append(
            "# cube server 正常启动并握手（9 个工具可枚举），三个子情形都让 cubemx_load 真的被调用："
        )
        head.append(
            f"#   [越界]     .ioc={NEGATIVE_ERROR_IOC}"
            "（临时目录、不存在）→ _check_path 按白名单拒绝 → 期望 isError=True"
        )
        head.append(
            f"#   [缺失]     .ioc={NEGATIVE_ERROR_MISSING_IOC}"
            "（白名单内、不存在）→ _ioc_path 抛「.ioc 文件不存在」→ 期望 isError=True"
        )
        head.append(
            f"#   [执行失败] .ioc={NEGATIVE_ERROR_BAD_IOC}"
            "（白名单内、存在、内容是垃圾）→ CubeMX 弹模态框挂住 → 超时强杀 →"
            " 期望 isError=False 但文本以 [FAIL 开头"
        )
        head.append(
            "# 目的：实测 ok = (not isError) and (文本不是失败形态)。"
            "只看 isError 会把 [执行失败] 判成通过（假绿）。"
        )
        head.append(
            "# 垃圾 .ioc 与其父目录在运行期创建、finally 删除；"
            "环境仅调整 ST_CUBEMX_TIMEOUT="
            f"{NEGATIVE_ERROR_CUBEMX_TIMEOUT}"
            "（让挂在模态框上的 CubeMX 快速被强杀，不必真等 5 分钟），"
            "ALLOWED_ROOTS 保持原样。"
        )
        head.append("# 预期：三条子情形均判 FAIL、末行 VERDICT: SMOKE FAIL、exit=1。")
    elif options.negative_control:
        head = ["===== MCP 工具调用冒烟自检 (T0.4) — 负向对照 ====="]
        head.append(
            "# 本日志来自负向对照运行：故意把 vscode-cube-mcp 的命令指向不存在的路径"
            f"（{NEGATIVE_CUBE_COMMAND}），"
        )
        head.append(
            "# 用于证明脚本真的会判 FAIL 并以 exit=1 退出，而不是恒 PASS。"
        )
        head.append(
            "# 注意：该路径在 tools/call 之前就 SKIP，故本条不覆盖 isError 分支"
            "（那是 --negative-error 的职责）。"
        )
    else:
        head = ["===== MCP 工具调用冒烟自检 (T0.4) ====="]

    head.extend(
        [
            f"time     : {datetime.now().isoformat(timespec='seconds')}",
            f"mode     : {options.mode}",
            f"runner   : {sys.executable}",
            f"script   : {SCRIPT_PATH}",
            f"script_sha256 : {sha256_file(SCRIPT_PATH)}",
            f"repo_root: {REPO_ROOT}",
            f"mcp_sdk  : {sdk_version}",
            f"cwd      : {os.getcwd()}",
        ]
    )
    return head


def summary_entries(options: SmokeOptions) -> tuple[str, ...]:
    """返回摘要行要逐项列出的条目名（顺序即输出顺序）。

    负向错误响应模式下 ``cubemx_load`` 有两个子情形，各自独立占一行，
    避免后一次调用覆盖前一次的记录。

    Args:
        options: 运行选项。

    Returns:
        条目名元组；正向与负向对照模式即 ``REQUIRED_CALLS``。
    """
    if not options.negative_error:
        return REQUIRED_CALLS
    entries: list[str] = []
    for tool in REQUIRED_CALLS:
        if tool == "cubemx_load":
            entries.extend(ERROR_CASES)
        else:
            entries.append(tool)
    return tuple(entries)


def render(report: SmokeReport, options: SmokeOptions) -> str:
    """把报告渲染成完整日志文本。

    Args:
        report: 冒烟报告。
        options: 运行选项。

    Returns:
        可直接落盘的日志全文，末行为 VERDICT。
    """
    entries = summary_entries(options)
    passed = sum(1 for name in entries if name in report.called and report.called[name].ok)
    missing = [
        name for name in entries
        if not (name in report.called and report.called[name].ok)
    ]

    lines = build_header(options)
    lines.extend(report.lines)

    lines.append("")
    lines.append("--- 汇总 ---")
    # 逐项列出必需调用的真实状态：跑过的写 OK/FAIL，没跑的写 SKIP。
    for name in entries:
        prefix, detail = required_status(report, name)
        lines.append(format_line(prefix, name, detail))

    # 分母恒为 entries 长度：漏测只会让比值变差，不会变小。
    if missing:
        lines.append(
            format_line(
                "FAIL",
                "必需调用通过",
                f"{passed} / {len(entries)}（缺：{'、'.join(missing)}）",
            )
        )
    else:
        lines.append(
            format_line("OK", "必需调用通过", f"{passed} / {len(entries)}")
        )

    if options.negative_error:
        lines.append(
            format_line(
                "INFO",
                "预期",
                "负向错误响应模式：三条子情形 [越界]（isError=True）、[缺失]"
                "（isError=True）、[执行失败]（isError=False 但文本 [FAIL…]）"
                "都应判 FAIL，故本轮 VERDICT 应为 SMOKE FAIL、exit=1",
            )
        )
    lines.append(
        format_line(
            "INFO",
            "判据",
            "ok = (not isError) and not 文本失败形态"
            "（文本以 [FAIL 开头，或存在整行 KO）；"
            "cubemx_load 另需 .ioc 的 sha256 不变；"
            "pio_list_devices 允许空结果，调用成功即通过",
        )
    )
    for record in report.records:
        lines.append(
            format_line(
                "INFO",
                "耗时",
                f"{record.server}/{record.log_label or record.tool} = {record.duration_ms}ms",
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
        ValueError: 出现未知参数，或同时指定两个互斥的负向开关时抛出，
            避免拼错开关却静默按正向跑。
    """
    supported = " / ".join(SUPPORTED_FLAGS)
    unknown = [arg for arg in argv if arg not in SUPPORTED_FLAGS]
    if unknown:
        raise ValueError(f"未知参数 {unknown}；只支持 {supported}")

    negative_control = NEGATIVE_CONTROL_FLAG in argv
    negative_error = NEGATIVE_ERROR_FLAG in argv
    if negative_control and negative_error:
        raise ValueError(
            f"{NEGATIVE_CONTROL_FLAG} 与 {NEGATIVE_ERROR_FLAG} 互斥，"
            "一次只能跑一种负向模式"
        )
    return SmokeOptions(
        negative_control=negative_control,
        negative_error=negative_error,
    )


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
