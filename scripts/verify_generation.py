#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""platform32-mcp · G1 生成核验器（CubeMX 静默丢弃检测）。

背景
----
STM32CubeMX 对 ``.ioc`` 的错误是**静默非致命**的：

* 信号名写错（例如该写 ``S_TIM4_CH1`` 却写成 ``TIM4_CH1``）只在生成日志里留下
  一行 ``(OptionalMessage_ERROR) Cannot map signal ...``，``project generate``
  依然返回"成功"，外设被静默丢弃（模板 ``TEMPLATE-PLACEHOLDERS.md`` D4/D5，
  ``docs/HAL-PITFALLS.md`` H-6）；
* 外设/引脚参数没写进 ``<IP>.IPParameters`` / ``<Pin>.GPIOParameters`` 白名单，
  同样被忽略（D3）；
* ``.mxproject`` 里出现盘符绝对路径（``D:\\Projects\\...``）会让工程换机即坏
  （``docs/TOOLING-cubemx.md`` §3.2）；
* ``syscalls.c`` / ``sysmem.c`` 会被写成叠加路径而不再更新（§3.4 / D9），
  这是 CubeMX 的已知缺陷，**不阻塞**交付。

因此"生成成功"不等于"配置生效"。本脚本是 Skill 流水线的**强制关卡**：
拿生成日志 + ``Core/Src/main.c`` + ``.mxproject`` 三份产物做交叉核验，输出
结构化报告（JSON / Markdown），并给出可直接用于 CI 判断的退出码。

检查项（id 固定，下游按 id 消费）
---------------------------------
============================  ================================================
``log_cannot_map``            生成日志无 ``Cannot map``；命中 ``--allow-signal``
                              白名单的行降级为 ``warn``（G474 的
                              ``VP_RIF_VS_RIF1`` 是 D8 已知噪音）
``main_init_present``         每个期望外设都能在 ``main.c`` 里找到
                              ``MX_<PERIPH>[_<FUNC>]_Init`` 的**函数定义**
``main_init_called``          这些 ``MX_..._Init`` 在 ``main()`` 函数体内**被调用**
                              （注释掉的调用不算）
``mxproject_abs_path``        ``.mxproject`` 里没有盘符绝对路径
``syscalls_path``             ``syscalls.c`` / ``sysmem.c`` 叠加路径告警，**单独**
                              降级为 ``warning``（D9，不阻塞）
============================  ================================================

CLI 契约
--------
::

    python scripts/verify_generation.py \\
        --log <cubeMX生成日志> \\
        --main-c <工程/Core/Src/main.c> \\
        --mxproject <工程/.mxproject> \\
        --expect <外设名逗号分隔, 如 GPIO,TIM4,USART2> \\
        [--allow-signal VP_RIF_VS_RIF1] \\
        [--json-out <输出路径>] \\
        [--report-md <输出路径>]

退出码：``0`` 全部通过（可含 warning）；``1`` 存在 fail 级问题；``2`` 输入/IO/参数错误。

只依赖 Python 标准库，方便被 MCP/Skill/CI 直接调用。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

__version__ = "1.0.0"

#: 报告 schema 版本号；结构变更时必须递增（下游 T1.4 文档与 S1 场景按此消费）。
SCHEMA = "platform32.verify_generation/1"

#: 退出码。
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_INPUT_ERROR = 2

# ---- 检查项 id（固定，不得改名）------------------------------------------
CHECK_LOG_CANNOT_MAP = "log_cannot_map"
CHECK_MAIN_INIT_PRESENT = "main_init_present"
CHECK_MAIN_INIT_CALLED = "main_init_called"
CHECK_MXPROJECT_ABS_PATH = "mxproject_abs_path"
CHECK_SYSCALLS_PATH = "syscalls_path"

#: 输出顺序（便于人读与快照比对）。
CHECK_ORDER: tuple[str, ...] = (
    CHECK_LOG_CANNOT_MAP,
    CHECK_MAIN_INIT_PRESENT,
    CHECK_MAIN_INIT_CALLED,
    CHECK_MXPROJECT_ABS_PATH,
    CHECK_SYSCALLS_PATH,
)

STATUS_PASS = "pass"
STATUS_WARN = "warn"
STATUS_FAIL = "fail"
STATUS_SKIP = "skip"

#: CubeMX 生成的初始化函数后缀（``MX_<PERIPH>_<FUNC>_Init``）。
#: 例：``--expect USART2`` → ``MX_USART2_UART_Init``；``--expect USB`` →
#: ``MX_USB_Device_Init``。大小写不敏感匹配。
FUNCTION_SUFFIXES: tuple[str, ...] = (
    "UART",
    "USART",
    "LPUART",
    "TIM",
    "SPI",
    "I2C",
    "ADC",
    "DAC",
    "CAN",
    "Device",
    "Host",
    "SD",
    "ETH",
    "SAI",
    "I2S",
    "RTC",
    "FLASH",
    "USB",
    "COMP",
    "OPAMP",
    "CRC",
    "RNG",
    "HCD",
)

#: 疑似编码顺序（CubeMX 日志含中文提示时可能是 GBK/GB18030）。
_TEXT_ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8", "gb18030", "cp936", "latin-1")

#: ``Cannot map`` 判定（CubeMX 原文 ``Cannot map signal ...``，大小写不敏感）。
_CANNOT_MAP_RE = re.compile(r"cannot\s+map", re.IGNORECASE)
#: CubeMX 的 ``OptionalMessage_ERROR`` 前缀（仅作参考信息，不参与判定，见 D8）。
_OPTIONAL_ERROR_RE = re.compile(r"OptionalMessage_ERROR", re.IGNORECASE)
#: 从 Cannot map 行里抽取信号名（CubeMX 多数情况下不加引号）。
_QUOTED_SIGNAL_RE = re.compile(r"[\"'`]([A-Za-z0-9_./\\-]+)[\"'`]")
_BARE_SIGNAL_RE = re.compile(r"cannot\s+map\s+(?:signal\s+)?([A-Za-z0-9_]+)", re.IGNORECASE)
#: 盘符绝对路径（``D:\`` / ``C:/``）。用反向断言挡掉 ``http://``、``file:///``。
_DRIVE_PATH_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
#: D9：这两个 newlib 桩文件会被写成叠加路径。
_SYSCALLS_NAMES: tuple[str, ...] = ("syscalls.c", "sysmem.c")
#: D9 的症状关键字（CubeMX 报 FileNotFoundException + 拒绝访问）。
_SYSCALLS_HINTS: tuple[str, ...] = (
    "filenotfoundexception",
    "ioexception",
    "exception",
    "拒绝访问",
    "access is denied",
    "cannot find",
    "no such file",
)

#: ``MX_xxx_Init`` 声明/定义：第三组 ``{`` = 定义，``;`` = 原型或调用。
_INIT_DECL_RE = re.compile(r"\b(MX_[A-Za-z0-9_]+_Init)\s*\(([^;{}]*)\)\s*([;{])")
#: ``int main(void)`` 形式（CubeMX 固定生成，容忍空白与注释残留）。
_MAIN_DECL_RE = re.compile(r"\bint\s+main\s*\(([^;{)]*)\)\s*\{")


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CheckResult:
    """单条检查结果。

    Attributes:
        check_id: 固定的检查项 id（见 ``CHECK_ORDER``）。
        status: ``pass`` / ``warn`` / ``fail`` / ``skip``。
        detail: 人可读的中文说明，必须包含判定依据（行号、符号名等）。
    """

    check_id: str
    status: str
    detail: str

    @property
    def level(self) -> str:
        """问题严重度：``warning`` 表示不阻塞交付，``error`` 表示阻塞。"""
        return "warning" if self.status in (STATUS_WARN, STATUS_SKIP) else "error"

    def to_dict(self) -> dict[str, str]:
        """序列化为 JSON 片段。"""
        return {
            "id": self.check_id,
            "status": self.status,
            "level": self.level,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# 读文件 / 文本工具
# ---------------------------------------------------------------------------
def read_text(path: str | os.PathLike[str]) -> str:
    """按候选编码读取文本文件。

    Args:
        path: 文件路径。

    Returns:
        解码后的文本（换行原样保留，CRLF 也保留）。

    Raises:
        OSError: 文件不存在或不可读。
    """
    with open(path, "rb") as handle:
        raw = handle.read()
    for encoding in _TEXT_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def strip_c_comments(text: str) -> str:
    """把 C 源码里的注释与字符串内容替换为空格，**保留换行**。

    这样处理后行号与原文件一一对应，可以直接用于报行号；同时避免把注释掉的
    ``MX_TIM4_Init();`` 误判成"被调用"、把 ``/* MX_xxx_Init(void) */``
    误判成"有定义"。

    Args:
        text: 原始 C 源码。

    Returns:
        与输入等长（近似）的文本，注释/字符串内容被空格填充，换行不动。
    """
    out: list[str] = []
    index = 0
    length = len(text)
    state = "code"
    while index < length:
        char = text[index]
        nxt = text[index + 1] if index + 1 < length else ""
        if state == "code":
            if char == "/" and nxt == "/":
                state = "line_comment"
                out.append("  ")
                index += 2
                continue
            if char == "/" and nxt == "*":
                state = "block_comment"
                out.append("  ")
                index += 2
                continue
            if char == '"':
                state = "string"
                out.append('"')
                index += 1
                continue
            if char == "'":
                state = "char"
                out.append("'")
                index += 1
                continue
            out.append(char)
            index += 1
            continue
        # 以下为注释/字符串内部
        if char == "\n":
            out.append("\n")
            if state == "line_comment":
                state = "code"
            index += 1
            continue
        if state == "line_comment":
            out.append(" ")
            index += 1
            continue
        if state == "block_comment":
            if char == "*" and nxt == "/":
                state = "code"
                out.append("  ")
                index += 2
                continue
            out.append(" ")
            index += 1
            continue
        # string / char
        if char == "\\":
            out.append("  ")
            index += 2
            continue
        terminator = '"' if state == "string" else "'"
        if char == terminator:
            state = "code"
            out.append(terminator)
            index += 1
            continue
        out.append(" ")
        index += 1
    return "".join(out)


def line_of(text: str, index: int) -> int:
    """返回字符下标所在的行号（1 起）。"""
    if index <= 0:
        return 1
    return text.count("\n", 0, index) + 1


def _truncate(text: str, limit: int = 200) -> str:
    """截断长文本，保持单行可读。"""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def extract_signal_name(line: str) -> str | None:
    """从 ``Cannot map`` 行里抽取被丢弃的信号名。

    CubeMX 有时给信号名加引号（``Cannot map signal "X"``），有时不加
    （``Cannot map signal X on pin PA0``），两种都要能抽出来。

    Args:
        line: 日志行。

    Returns:
        信号名，抽不到时返回 ``None``。
    """
    quoted = _QUOTED_SIGNAL_RE.search(line)
    if quoted is not None:
        return quoted.group(1)
    bare = _BARE_SIGNAL_RE.search(line)
    if bare is not None:
        return bare.group(1)
    return None


def _describe_blocking_hit(lineno: int, line: str) -> str:
    """把一条阻塞命中渲染成 ``L12: SIGNAL ← 原文`` 形式。"""
    signal = extract_signal_name(line)
    prefix = f"{signal} ← " if signal else ""
    return f"L{lineno}: {prefix}{_truncate(line, 160)}"


# ---------------------------------------------------------------------------
# main.c 解析
# ---------------------------------------------------------------------------
def collect_init_definitions(code: str) -> dict[str, list[int]]:
    """收集 ``main.c`` 里所有 ``MX_xxx_Init`` **函数定义**的下标。

    Args:
        code: 已过 :func:`strip_c_comments` 的源码。

    Returns:
        符号名 -> 定义处字符下标列表（原型声明 ``;`` 不计入）。
    """
    definitions: dict[str, list[int]] = {}
    for match in _INIT_DECL_RE.finditer(code):
        if match.group(3) != "{":
            continue
        definitions.setdefault(match.group(1), []).append(match.start())
    return definitions


def find_main_body(code: str) -> tuple[int, int] | None:
    """定位 ``main()`` 函数体在大括号之间的区间。

    Args:
        code: 已过 :func:`strip_c_comments` 的源码。

    Returns:
        ``(body_start, body_end)`` 字符下标；找不到 ``main`` 时返回 ``None``。
    """
    match = _MAIN_DECL_RE.search(code)
    if match is None:
        return None
    body_start = match.end() - 1  # 指向 '{'
    depth = 0
    for index in range(body_start, len(code)):
        char = code[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return body_start, index + 1
    return None


def resolve_init_symbol(periph: str, defined_symbols: Iterable[str]) -> tuple[str | None, str]:
    """把 ``--expect`` 里的外设名解析成 ``main.c`` 里实际存在的初始化符号。

    匹配优先级（全部大小写不敏感）：

    1. 精确 ``MX_<PERIPH>_Init``；
    2. 带功能后缀 ``MX_<PERIPH>_<FUNC>_Init``（``FUNCTION_SUFFIXES``，
       如 ``USART2`` → ``MX_USART2_UART_Init``）；
    3. 兜底：``MX_<PERIPH>_<TOKEN>_Init`` 形式且**唯一**命中时接受（模糊匹配）。

    Args:
        periph: 期望外设名，如 ``GPIO`` / ``TIM4`` / ``USART2``。
        defined_symbols: ``main.c`` 里已定义的符号集合。

    Returns:
        ``(符号名或 None, 匹配方式说明)``。
    """
    name = (periph or "").strip()
    if not name:
        return None, "empty"
    lowered = {symbol.lower(): symbol for symbol in defined_symbols}
    exact_key = f"mx_{name.lower()}_init"
    if exact_key in lowered:
        return lowered[exact_key], "exact"
    for suffix in FUNCTION_SUFFIXES:
        key = f"mx_{name.lower()}_{suffix.lower()}_init"
        if key in lowered:
            return lowered[key], f"suffix:{suffix}"
    fuzzy_re = re.compile(
        r"MX_" + re.escape(name) + r"_[A-Za-z0-9]+_Init", re.IGNORECASE
    )
    candidates = sorted(
        symbol
        for key, symbol in lowered.items()
        if key.startswith(f"mx_{name.lower()}_") and fuzzy_re.fullmatch(symbol)
    )
    if len(candidates) == 1:
        return candidates[0], "fuzzy"
    if len(candidates) > 1:
        return None, "ambiguous:" + "/".join(candidates)
    return None, "missing"


# ---------------------------------------------------------------------------
# 各检查项
# ---------------------------------------------------------------------------
def check_log_cannot_map(log_text: str, allow_signals: Sequence[str]) -> CheckResult:
    """检查生成日志里是否出现 ``Cannot map``（外设被静默丢弃的**根因证据**）。

    Args:
        log_text: CubeMX 生成日志全文。
        allow_signals: 允许降级为 warning 的信号名（``--allow-signal``）。

    Returns:
        检查结果：无命中 → ``pass``；命中但全部在白名单 → ``warn``；否则 ``fail``。
    """
    allow = [item.strip() for item in allow_signals if item and item.strip()]
    allow_lower = [(item, item.lower()) for item in allow]
    hits: list[tuple[int, str]] = []
    optional_errors = 0
    for lineno, line in enumerate(log_text.splitlines(), 1):
        if _OPTIONAL_ERROR_RE.search(line):
            optional_errors += 1
        if _CANNOT_MAP_RE.search(line):
            hits.append((lineno, line.strip()))

    if not log_text.strip():
        return CheckResult(
            CHECK_LOG_CANNOT_MAP,
            STATUS_WARN,
            "生成日志为空，无法确认生成是否真的跑过；请确认 --log 指向本次生成的日志",
        )

    if not hits:
        detail = "生成日志无 'Cannot map' 命中"
        if optional_errors:
            detail += (
                f"（另有 {optional_errors} 条 OptionalMessage_ERROR，属 CubeMX 已知噪音，"
                "如 G474 的 VP_RIF_VS_RIF1 见模板 D8，不计入判定）"
            )
        return CheckResult(CHECK_LOG_CANNOT_MAP, STATUS_PASS, detail)

    allowed_hits: list[tuple[int, str, str]] = []
    blocking: list[tuple[int, str]] = []
    for lineno, line in hits:
        lowered_line = line.lower()
        matched = next((orig for orig, low in allow_lower if low in lowered_line), None)
        if matched:
            allowed_hits.append((lineno, line, matched))
        else:
            blocking.append((lineno, line))

    samples = "；".join(
        _describe_blocking_hit(lineno, line) for lineno, line in blocking[:3]
    )
    if blocking:
        detail = (
            f"命中 {len(hits)} 条 'Cannot map'，其中 {len(blocking)} 条不在白名单 → "
            f"外设会被静默丢弃（D5/H-6）。{samples}"
        )
        if allowed_hits:
            detail += f"；已白名单放行 {len(allowed_hits)} 条"
        return CheckResult(CHECK_LOG_CANNOT_MAP, STATUS_FAIL, detail)

    allowed_desc = "、".join(
        f"{sig}@L{lineno}" for lineno, _line, sig in allowed_hits[:5]
    )
    return CheckResult(
        CHECK_LOG_CANNOT_MAP,
        STATUS_WARN,
        f"命中 {len(hits)} 条 'Cannot map'，全部命中 --allow-signal 白名单（{allowed_desc}），"
        "按已知噪音降级为 warning",
    )


def check_main_init_present(
    code: str, definitions: dict[str, list[int]], expect: Sequence[str]
) -> tuple[CheckResult, dict[str, dict[str, str | int]]]:
    """检查期望外设是否都有对应的 ``MX_..._Init`` **定义**。

    Args:
        code: 已过 :func:`strip_c_comments` 的 ``main.c`` 源码（用于取行号）。
        definitions: :func:`collect_init_definitions` 的返回值。
        expect: 期望外设清单。

    Returns:
        ``(检查结果, 解析明细)``。明细键为外设名，值含 ``symbol`` / ``match`` / ``line``。
    """
    if not expect:
        return (
            CheckResult(
                CHECK_MAIN_INIT_PRESENT,
                STATUS_SKIP,
                "--expect 为空，未指定期望外设，跳过初始化函数存在性检查",
            ),
            {},
        )

    resolved: dict[str, dict[str, str | int]] = {}
    missing: list[str] = []
    for periph in expect:
        symbol, kind = resolve_init_symbol(periph, definitions.keys())
        if symbol is None:
            missing.append(f"{periph}({kind})")
            continue
        resolved[periph] = {
            "symbol": symbol,
            "match": kind,
            "line": line_of(code, definitions[symbol][0]),
        }

    satisfied = "；".join(
        f"{periph} → {info['symbol']}（{info['match']}，定义 L{info['line']}）"
        for periph, info in resolved.items()
    )
    if missing:
        detail = (
            f"{len(missing)}/{len(expect)} 个期望外设没有 MX_..._Init 定义 → 配置未生效或被静默丢弃"
            f"（D5/H-6）：{'、'.join(missing)}"
        )
        if satisfied:
            detail += f"。已满足：{satisfied}"
        return CheckResult(CHECK_MAIN_INIT_PRESENT, STATUS_FAIL, detail), resolved

    return (
        CheckResult(
            CHECK_MAIN_INIT_PRESENT,
            STATUS_PASS,
            f"全部 {len(expect)} 个期望外设都有初始化函数定义：{satisfied}",
        ),
        resolved,
    )


def check_main_init_called(
    code: str, resolved: dict[str, dict[str, str | int]], expect: Sequence[str]
) -> CheckResult:
    """检查已定义的 ``MX_..._Init`` 是否在 ``main()`` 函数体内真的被调用。

    典型漏配：函数有定义但 ``main()`` 里没有调用（漏改 ``.ioc`` 的代码生成项），
    或者调用被注释掉。注释已由 :func:`strip_c_comments` 清空，不会误判。

    Args:
        code: 已过 :func:`strip_c_comments` 的 ``main.c`` 源码。
        resolved: :func:`check_main_init_present` 产出的解析明细。
        expect: 期望外设清单（仅用于说明"哪些外设没定义、未参与本项"）。

    Returns:
        检查结果。
    """
    if not expect:
        return CheckResult(
            CHECK_MAIN_INIT_CALLED,
            STATUS_SKIP,
            "--expect 为空，跳过 main() 调用检查",
        )
    if not resolved:
        return CheckResult(
            CHECK_MAIN_INIT_CALLED,
            STATUS_SKIP,
            "没有任何已定义的初始化函数可供核对（缺失原因见 main_init_present）",
        )

    body = find_main_body(code)
    if body is None:
        return CheckResult(
            CHECK_MAIN_INIT_CALLED,
            STATUS_FAIL,
            "main.c 里找不到 int main(void) 函数体，无法确认初始化函数是否被调用",
        )
    body_start, body_end = body
    body_text = code[body_start:body_end]

    called: list[str] = []
    not_called: list[str] = []
    for periph, info in resolved.items():
        symbol = str(info["symbol"])
        match = re.search(r"\b" + re.escape(symbol) + r"\s*\(", body_text)
        if match is None:
            not_called.append(f"{periph} → {symbol}（定义 L{info['line']}，main() 内无调用）")
            continue
        call_line = line_of(code, body_start + match.start())
        called.append(f"{periph} → {symbol}（调用 L{call_line}）")

    undefined = [periph for periph in expect if periph not in resolved]
    suffix_note = ""
    if undefined:
        suffix_note = f"；另有 {len(undefined)} 个外设无定义、未参与本项：{'、'.join(undefined)}"

    if not_called:
        detail = (
            f"{len(not_called)}/{len(resolved)} 个已定义的初始化函数没有在 main() 内被调用 → "
            f"外设初始化不会执行：{'；'.join(not_called)}"
        )
        if called:
            detail += f"。已正确调用：{'；'.join(called)}"
        return CheckResult(
            CHECK_MAIN_INIT_CALLED, STATUS_FAIL, detail + suffix_note
        )

    return CheckResult(
        CHECK_MAIN_INIT_CALLED,
        STATUS_PASS,
        f"全部 {len(called)} 个初始化函数都在 main() 内被调用：{'；'.join(called)}{suffix_note}",
    )


def check_mxproject_abs_path(mxproject_text: str) -> CheckResult:
    """检查 ``.mxproject`` 是否含盘符绝对路径（换机即坏，模板 TOOLING §3.2）。

    Args:
        mxproject_text: ``.mxproject`` 全文。

    Returns:
        检查结果：有盘符路径 → ``fail``；否则 ``pass``。
    """
    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(mxproject_text.splitlines(), 1):
        if _DRIVE_PATH_RE.search(line):
            hits.append((lineno, line.strip()))
    if not hits:
        return CheckResult(
            CHECK_MXPROJECT_ABS_PATH,
            STATUS_PASS,
            "'.mxproject' 无盘符绝对路径（换机可复现）",
        )
    samples = "；".join(
        f"L{lineno}: {_truncate(_mask_line(line), 160)}" for lineno, line in hits[:3]
    )
    return CheckResult(
        CHECK_MXPROJECT_ABS_PATH,
        STATUS_FAIL,
        f"'.mxproject' 含 {len(hits)} 处盘符绝对路径 → 换机/换盘符即失效，"
        f"应在工程根目录用 config load + project generate 原地重生成（TOOLING §3.2）。{samples}",
    )


def _mask_line(line: str) -> str:
    """把行内 ``key=value`` 的 value 截短，避免报告被超长文件清单淹没。"""
    if "=" not in line:
        return line
    key, _sep, value = line.partition("=")
    if len(value) <= 120:
        return line
    return f"{key}={value[:117]}…"


def check_syscalls_path(log_text: str) -> CheckResult:
    """检查 ``syscalls.c`` / ``sysmem.c`` 叠加路径告警（D9）。

    这两份文件是标准 newlib 桩，CubeMX 会把它写成
    ``<工程目录>\\D:\\...\\Core\\Src\\syscalls.c`` 并因此不更新内容。属已知缺陷，
    按约定**只降级为 warning**，不阻塞交付。

    Args:
        log_text: CubeMX 生成日志全文。

    Returns:
        检查结果：命中 → ``warn``；未命中 → ``pass``。
    """
    hits: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(log_text.splitlines(), 1):
        lowered = line.lower()
        name = next((item for item in _SYSCALLS_NAMES if item in lowered), None)
        if name is None:
            continue
        if not any(hint in lowered for hint in _SYSCALLS_HINTS):
            continue
        hits.append((lineno, name, line.strip()))
    if not hits:
        return CheckResult(
            CHECK_SYSCALLS_PATH,
            STATUS_PASS,
            "生成日志无 syscalls.c / sysmem.c 叠加路径异常",
        )
    names = "、".join(sorted({name for _lineno, name, _line in hits}))
    samples = "；".join(
        f"L{lineno}: {_truncate(line, 160)}" for lineno, _name, line in hits[:2]
    )
    return CheckResult(
        CHECK_SYSCALLS_PATH,
        STATUS_WARN,
        f"命中 {len(hits)} 条叠加路径异常（{names}），这两个 newlib 桩本次未更新；"
        f"属 CubeMX 已知缺陷 D9，不阻塞交付（需要更新时从 FW 包模板目录复制）。{samples}",
    )


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
def parse_expect(raw: str | Sequence[str] | None) -> list[str]:
    """解析 ``--expect``：支持逗号/分号/空白分隔，去重并统一大写。

    Args:
        raw: 原始字符串（``"GPIO,TIM4,USART2"``）或已拆分的序列。

    Returns:
        外设名列表（保持首次出现顺序）。
    """
    if raw is None:
        return []
    chunks: list[str] = []
    if isinstance(raw, str):
        chunks = re.split(r"[,;\s]+", raw)
    else:
        for item in raw:
            chunks.extend(re.split(r"[,;\s]+", str(item)))
    result: list[str] = []
    for chunk in chunks:
        name = chunk.strip().upper()
        if name and name not in result:
            result.append(name)
    return result


def parse_allow_signals(raw: Sequence[str] | None) -> list[str]:
    """解析 ``--allow-signal``（可重复、可逗号分隔），保留原始大小写。"""
    if not raw:
        return []
    result: list[str] = []
    for item in raw:
        for chunk in re.split(r"[,;\s]+", str(item)):
            name = chunk.strip()
            if name and name not in result:
                result.append(name)
    return result


def verify_documents(
    *,
    log_text: str,
    main_c_text: str,
    mxproject_text: str,
    expect: Sequence[str],
    allow_signals: Sequence[str] = (),
    inputs: dict[str, str] | None = None,
) -> dict[str, object]:
    """对已读入内存的三份产物执行全部检查，返回报告字典。

    纯函数（不碰文件系统），便于单测与在其他进程内复用。

    Args:
        log_text: CubeMX 生成日志全文。
        main_c_text: ``Core/Src/main.c`` 全文。
        mxproject_text: ``.mxproject`` 全文。
        expect: 期望外设清单（已规范化，如 ``["GPIO", "TIM4"]``）。
        allow_signals: 允许降级为 warning 的信号名。
        inputs: 报告 ``inputs`` 字段（路径），缺省为空字符串。

    Returns:
        符合 :data:`SCHEMA` 的报告字典。
    """
    code = strip_c_comments(main_c_text)
    definitions = collect_init_definitions(code)

    log_result = check_log_cannot_map(log_text, allow_signals)
    present_result, resolved = check_main_init_present(code, definitions, expect)
    called_result = check_main_init_called(code, resolved, expect)
    mxproject_result = check_mxproject_abs_path(mxproject_text)
    syscalls_result = check_syscalls_path(log_text)

    by_id = {
        item.check_id: item
        for item in (
            log_result,
            present_result,
            called_result,
            mxproject_result,
            syscalls_result,
        )
    }
    checks = [by_id[check_id] for check_id in CHECK_ORDER]

    errors = sum(1 for item in checks if item.status == STATUS_FAIL)
    warnings = sum(1 for item in checks if item.status == STATUS_WARN)
    report: dict[str, object] = {
        "schema": SCHEMA,
        "verdict": "fail" if errors else "pass",
        "checks": [item.to_dict() for item in checks],
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "checked_peripherals": list(expect),
        },
        "inputs": dict(inputs or {"log": "", "main_c": "", "mxproject": ""}),
        "expect": list(expect),
        "allow_signals": list(allow_signals),
        "tool": {"name": "verify_generation.py", "version": __version__},
    }
    return report


def render_markdown(report: dict[str, object]) -> str:
    """把报告渲染成便于贴进证据文档的 Markdown 表格。

    Args:
        report: :func:`verify_documents` 的返回值。

    Returns:
        Markdown 文本（以换行结尾）。
    """
    summary = report.get("summary", {})
    inputs = report.get("inputs", {})
    assert isinstance(summary, dict) and isinstance(inputs, dict)
    checked = summary.get("checked_peripherals") or []
    verdict = str(report.get("verdict", "fail")).upper()
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    lines: list[str] = [
        "# 生成核验报告（G1）",
        "",
        f"- **verdict**：`{verdict}`",
        f"- **errors / warnings**：{summary.get('errors', 0)} / {summary.get('warnings', 0)}",
        f"- **期望外设**：{', '.join(str(item) for item in checked) or '（未指定）'}",
        f"- **schema**：`{report.get('schema', SCHEMA)}`",
        f"- **生成时间**：{timestamp}",
        f"- **生成日志**：`{inputs.get('log', '')}`",
        f"- **main.c**：`{inputs.get('main_c', '')}`",
        f"- **.mxproject**：`{inputs.get('mxproject', '')}`",
        "",
        "| 检查项 | 结果 | 级别 | 说明 |",
        "|---|---|---|---|",
    ]
    checks = report.get("checks", [])
    assert isinstance(checks, list)
    for item in checks:
        assert isinstance(item, dict)
        detail = str(item.get("detail", "")).replace("|", "\\|")
        lines.append(
            f"| `{item.get('id', '')}` | {item.get('status', '')} | {item.get('level', '')} | {detail} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_console(report: dict[str, object]) -> str:
    """渲染终端摘要（stdout 输出，便于人和 agent 直接读）。"""
    summary = report.get("summary", {})
    assert isinstance(summary, dict)
    verdict = str(report.get("verdict", "fail"))
    header = (
        f"[platform32] 生成核验 verdict={verdict.upper()} "
        f"errors={summary.get('errors', 0)} warnings={summary.get('warnings', 0)} "
        f"expect={','.join(str(item) for item in summary.get('checked_peripherals') or []) or '-'}"
    )
    rows = [header]
    checks = report.get("checks", [])
    assert isinstance(checks, list)
    for item in checks:
        assert isinstance(item, dict)
        rows.append(
            f"  [{str(item.get('status', '')).ljust(4)}] {str(item.get('id', '')).ljust(20)} "
            f"{item.get('detail', '')}"
        )
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器（参数名是对外契约，勿改）。"""
    parser = argparse.ArgumentParser(
        prog="verify_generation.py",
        description=(
            "G1 生成核验器：核对 CubeMX 生成日志 / main.c / .mxproject，"
            "抓住被静默丢弃的外设与不可复现的工程路径。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "退出码：0=通过（可含 warning） 1=存在 fail 级问题 2=输入/IO/参数错误\n"
            "示例：python scripts/verify_generation.py --log build/cubemx.log "
            "--main-c firmware/Core/Src/main.c --mxproject firmware/.mxproject "
            "--expect GPIO,TIM4,USART2 --allow-signal VP_RIF_VS_RIF1 --json-out report.json"
        ),
    )
    parser.add_argument("--log", required=True, help="CubeMX 生成日志路径")
    parser.add_argument("--main-c", required=True, dest="main_c", help="工程 Core/Src/main.c 路径")
    parser.add_argument("--mxproject", required=True, help="工程 .mxproject 路径")
    parser.add_argument(
        "--expect",
        required=True,
        help="期望外设清单，逗号分隔（如 GPIO,TIM4,USART2）；空串表示不检查外设",
    )
    parser.add_argument(
        "--allow-signal",
        action="append",
        default=None,
        dest="allow_signal",
        help=(
            "允许把 Cannot map 降级为 warning 的信号名（可重复、可逗号分隔）。"
            "G474 最小工程的 VP_RIF_VS_RIF1 属 D8 已知噪音"
        ),
    )
    parser.add_argument("--json-out", default=None, dest="json_out", help="结构化 JSON 报告输出路径")
    parser.add_argument("--report-md", default=None, dest="report_md", help="Markdown 报告输出路径")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__} (schema {SCHEMA})"
    )
    return parser


def _write_text(path: str, content: str) -> None:
    """写文本文件（自动建父目录，UTF-8 + LF）。"""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 入口。

    Args:
        argv: 参数列表（缺省取 ``sys.argv[1:]``）。

    Returns:
        退出码：0 / 1 / 2。
    """
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    expect = parse_expect(args.expect)
    allow_signals = parse_allow_signals(args.allow_signal)
    inputs = {
        "log": os.path.abspath(args.log),
        "main_c": os.path.abspath(args.main_c),
        "mxproject": os.path.abspath(args.mxproject),
    }

    # 输入校验一律走退出码 2（与"核验不通过"的 1 区分开）。
    for label, path in (("--log", args.log), ("--main-c", args.main_c), ("--mxproject", args.mxproject)):
        if not os.path.isfile(path):
            print(f"[platform32][input-error] {label} 指向的文件不存在：{path}", file=sys.stderr)
            return EXIT_INPUT_ERROR
    try:
        log_text = read_text(args.log)
        main_c_text = read_text(args.main_c)
        mxproject_text = read_text(args.mxproject)
    except OSError as error:
        print(f"[platform32][input-error] 读取输入失败：{error}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    report = verify_documents(
        log_text=log_text,
        main_c_text=main_c_text,
        mxproject_text=mxproject_text,
        expect=expect,
        allow_signals=allow_signals,
        inputs=inputs,
    )

    try:
        if args.json_out:
            _write_text(
                args.json_out,
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            )
        if args.report_md:
            _write_text(args.report_md, render_markdown(report))
    except OSError as error:
        print(f"[platform32][input-error] 写报告失败：{error}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    print(render_console(report))
    if args.json_out:
        print(f"[platform32] JSON 报告：{os.path.abspath(args.json_out)}")
    if args.report_md:
        print(f"[platform32] Markdown 报告：{os.path.abspath(args.report_md)}")

    return EXIT_FAIL if report.get("verdict") == "fail" else EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
