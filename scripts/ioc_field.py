#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cubeone-mcp · ``.ioc`` 单键读写工具（供 ``regen.sh`` 做字段复位）。

为什么单独做一个工具
--------------------
``ProjectManager.AskForMigrate`` 是 CubeMX 的**弹窗开关**，不是配置项：模板提交
为 ``false``，但 CubeMX 每次生成都会把它写回 ``true``（``docs/TOOLING-cubemx.md``
§3.3、模板 ``TEMPLATE-PLACEHOLDERS.md`` D7）。留着 ``true`` 会让**下一次**无头生成
卡在迁移对话框直到超时，所以在生成成功后必须把它复位。

复位要求"只改这一行、其它字节不动"（``.ioc`` 是唯一事实来源，行尾可能是 CRLF），
用 ``sed`` 之类容易把文件写坏，所以单独给一个精确到行的最小工具：

* 只做 ``key=value`` 的单行替换，**不新增/删除任何行**；
* 保留原行尾（CRLF/LF）与文件末尾是否有换行；
* 原子写（同目录临时文件 + ``os.replace``）；
* 值已经是目标值时不写盘（保持 mtime，避免无意义 diff）。

用法
----
::

    python scripts/ioc_field.py --ioc board.ioc get ProjectManager.AskForMigrate
    python scripts/ioc_field.py --ioc board.ioc set ProjectManager.AskForMigrate false
    python scripts/ioc_field.py --ioc board.ioc set MxCube.Version 6.18.1 --dry-run

退出码：``0`` 读到/写成；``1`` 没有结论可给（键不存在 **或** 同名键多行歧义——两者报文不同，
前者提示核对键名、后者附出全部行号）；``2`` 参数/IO 错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from typing import Sequence

__version__ = "1.1.0"

SCHEMA = "platform32.ioc_field/1"

EXIT_OK = 0
EXIT_KEY_MISSING = 1
EXIT_INPUT_ERROR = 2


def read_preserving_newlines(path: str | os.PathLike[str]) -> str:
    """读文本并**原样保留**行尾（``newline=""`` + ``surrogateescape``）。

    Args:
        path: 文件路径。

    Returns:
        未做任何行尾归一化的文本。

    Raises:
        OSError: 文件不可读。
    """
    with open(path, "r", encoding="utf-8", errors="surrogateescape", newline="") as handle:
        return handle.read()


def write_preserving_newlines(path: str | os.PathLike[str], text: str) -> None:
    """原子写入（同目录临时文件 + ``os.replace``），不改动行尾。

    Args:
        path: 目标路径。
        text: 要写入的完整文本。

    Raises:
        OSError: 写入失败。
    """
    target = os.path.abspath(os.fspath(path))
    parent = os.path.dirname(target) or "."
    handle, temp_path = tempfile.mkstemp(prefix=".ioc_field.", suffix=".tmp", dir=parent)
    os.close(handle)
    try:
        with open(temp_path, "w", encoding="utf-8", errors="surrogateescape", newline="") as stream:
            stream.write(text)
        os.replace(temp_path, target)
    except OSError:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def find_key_lines(lines: Sequence[str], key: str) -> list[int]:
    """返回 ``key=`` 所在行下标（``lines`` 需保留行尾）。

    Args:
        lines: ``text.splitlines(keepends=True)`` 的结果。
        key: 形如 ``ProjectManager.AskForMigrate`` 的键。

    Returns:
        命中行的下标列表（0 起）；通常只有一个。
    """
    prefix = f"{key}="
    return [index for index, line in enumerate(lines) if line.startswith(prefix)]


def split_line_ending(line: str) -> tuple[str, str]:
    """把一行拆成 ``(内容, 行尾)``，行尾可能是 ``\\r\\n`` / ``\\n`` / 空串。"""
    for ending in ("\r\n", "\n"):
        if line.endswith(ending):
            return line[: -len(ending)], ending
    return line, ""


def _reject_newlines(key: str, value: str | None = None) -> None:
    """拒绝 ``key`` / ``value`` 里的回车 / 换行符，防 ``.ioc`` 内容注入（W1-1 / A-21）。

    ``set_value()`` 会把值原样拼进 ``lines[index] = f"{key}={value}{ending}"``；
    只要 ``value`` 带换行，就能在 ``.ioc`` 里凭空写出任意键值行。护栏分两层：
    MCP 侧 ``lib/server.mjs`` 的 ``validateArgs()`` 提前给可机读错误；本函数是
    CLI 侧兜底 —— 直接跑脚本、或经 ``regen.sh`` 调用，同样生效。

    Args:
        key: 键名。
        value: ``set`` 时的新值；``get`` 时传 ``None``。

    Raises:
        ValueError: 任一参数含 CR（回车）或 LF（换行）。``main()`` 统一退 2。
    """
    for label, text in (("key", key), ("value", value)):
        if text is not None and ("\r" in text or "\n" in text):
            raise ValueError(
                f"{label} 含换行符（CR / LF），拒绝写入：避免 .ioc 内容注入"
            )


def get_value(path: str | os.PathLike[str], key: str) -> tuple[str | None, int]:
    """读取单键的值。

    三种情形**必须给出三种不同的话**（否则人拿到的是同一条消息，得自己去翻文件）：

    * 命中一行      → ``(值, 行号)``
    * 一行都没有    → ``(None, 0)``（调用方报「不存在」）
    * 命中多行      → 抛 ``KeyError``，报文里带**全部行号**：这是"同名键多行"的歧义，
      与"不存在"是两件事——前者说明 ``.ioc`` 被手工改出了重复键（CubeMX 自己不会写重复键），
      后者说明键名写错。把两者合成一句"不存在"，会让人去改键名，而真正该做的是去修那个 ``.ioc``。

    Args:
        path: ``.ioc`` 路径。
        key: 键名。

    Returns:
        ``(值 或 None, 命中行号 1 起)``；未命中时行号为 0。

    Raises:
        KeyError: 同名键出现多行（报文含行号列表）。
        ValueError: ``key`` 含 CR / LF（内容注入护栏，W1-1）。
    """
    _reject_newlines(key)
    text = read_preserving_newlines(path)
    lines = text.splitlines(keepends=True)
    hits = find_key_lines(lines, key)
    if not hits:
        return None, 0
    if len(hits) > 1:
        line_list = ", ".join(str(index + 1) for index in hits)
        raise KeyError(
            f"{key} 在 {path} 出现 {len(hits)} 次（第 {line_list} 行）：同名键多行歧义，get 不做猜测"
        )
    content, _ending = split_line_ending(lines[hits[0]])
    return content.split("=", 1)[1] if "=" in content else "", hits[0] + 1


def set_value(
    path: str | os.PathLike[str], key: str, value: str, *, dry_run: bool = False
) -> dict[str, object]:
    """把单键的值改写成 ``value``（只动这一行）。

    Args:
        path: ``.ioc`` 路径。
        key: 键名。
        value: 新值（原样写入，不加引号）。
        dry_run: 只计算不写盘。

    Returns:
        结果摘要：``{"key","before","after","line","changed","dry_run"}``。

    Raises:
        KeyError: 键不存在或存在多行同名键。
        ValueError: ``key`` / ``value`` 含 CR / LF（内容注入护栏，W1-1）。
        OSError: 读写失败。
    """
    _reject_newlines(key, value)
    text = read_preserving_newlines(path)
    lines = text.splitlines(keepends=True)
    hits = find_key_lines(lines, key)
    if len(hits) == 0:
        raise KeyError(f"{key} 不存在于 {path}")
    if len(hits) > 1:
        raise KeyError(f"{key} 出现了 {len(hits)} 次（第 {', '.join(str(i + 1) for i in hits)} 行），拒绝猜测")
    index = hits[0]
    content, ending = split_line_ending(lines[index])
    before = content.split("=", 1)[1] if "=" in content else ""
    changed = before != value
    if changed:
        lines[index] = f"{key}={value}{ending}"
        if not dry_run:
            write_preserving_newlines(path, "".join(lines))
    return {
        "key": key,
        "before": before,
        "after": value,
        "line": index + 1,
        "changed": changed,
        "dry_run": dry_run,
    }


def build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器。"""
    parser = argparse.ArgumentParser(
        prog="ioc_field.py",
        description=".ioc 单键读写（保留 CRLF/LF 与文件末尾换行，原子写）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "退出码：0=成功 1=键不存在 或 同名键多行歧义（报文会区分：后者附全部行号） 2=参数/IO 错误\n"
            "示例：python scripts/ioc_field.py --ioc board.ioc set "
            "ProjectManager.AskForMigrate false"
        ),
    )
    parser.add_argument("--ioc", required=True, help=".ioc 文件路径")
    parser.add_argument(
        "action", choices=("get", "set"), help="get=读单键，set=改单键"
    )
    parser.add_argument("key", help="键名，如 ProjectManager.AskForMigrate")
    parser.add_argument("value", nargs="?", default=None, help="set 时的新值")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run", help="只计算不写盘")
    parser.add_argument("--json-out", default=None, dest="json_out", help="结构化 JSON 输出路径")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__} (schema {SCHEMA})"
    )
    return parser


def _harden_console_streams() -> None:
    """按输出目标加固 stdout/stderr，杜绝"控制台编码不够就崩"。

    为什么需要（2026-11-04，Windows CI 两次抓到，两版修法）：
    - **第一次**：Windows 英文环境控制台编码是 **cp1252**，打印 ``→`` / 中文抛
      ``UnicodeEncodeError``，脚本直接以 1 退出——用户看到的是"工具坏了"。
    - **第二次**：只把 errors 换成 backslashreplace 是**半对**。管道（非 TTY）的编码若也被污染成
      cp1252，中文会整体退化成 ``\\u7f3a`` 这类转义：**不崩，但读不了**——而下游要的恰恰是中文原文。

    所以按目标分流（**管道要可解析，控制台要可阅读**；两者要求不同编码，不能一条规则通吃）：
    - **管道 / 重定向**（非 TTY）：**强制 UTF-8**。机器消费的路径，UTF-8 是唯一不产生歧义的编码；
      封装层本来就按 UTF-8 解码，写别的编码反而会乱码。
    - **交互式控制台**（TTY）：**保留控制台自身编码**（中文 Windows = cp936，中文正常），只把
      错误处理器换成 backslashreplace —— 该编码表示不了的字符（如 cp1252 遇到 ``→``）转义成
      ``\\u2192``，而不是抛 ``UnicodeEncodeError`` 崩掉。

    ⚠️ **TTY 那一支没有自动回归**：改动本函数后请**手动**在中文 Windows 控制台（cp936）与
    英文/ASCII 语言环境各跑一次。管道那一支由 ``tests/test_console_encoding.py`` 覆盖。

    三个脚本各自持有一份（这三个文件必须能单独拷走就用，不引入共享模块）。
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
        退出码：0 / 1 / 2。
    """
    _harden_console_streams()
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not os.path.isfile(args.ioc):
        print(f"[ioc_field][input-error] .ioc 不存在：{args.ioc}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    if args.action == "set" and args.value is None:
        print("[ioc_field][input-error] set 需要提供新值", file=sys.stderr)
        return EXIT_INPUT_ERROR

    payload: dict[str, object]
    try:
        if args.action == "get":
            # ⚠️ 标记必须仍是 `[<tool>][not-found]`：`lib/server.mjs` 的 isExecFailure 把它
            # 当"域内结论"白名单（exit 1 + 无 JSON 也算答案，不报执行层失败）。多行歧义另起一个
            # 标记词（如 `[ambiguous]`）会让那次调用被报成"执行层失败"，把使用者推去查 Python。
            # ⇒ 区分靠**报文**（带行号 + 歧义字样），不靠标记；退出码同样是 1（"没有结论可给"）。
            value, lineno = get_value(args.ioc, args.key)
            if value is None:
                print(
                    f"[ioc_field][not-found] {args.key} 不存在于 {args.ioc}（键名核对："
                    f"区分大小写，完整键名形如 ProjectManager.AskForMigrate）",
                    file=sys.stderr,
                )
                return EXIT_KEY_MISSING
            print(value)
            payload = {"ioc": os.path.abspath(args.ioc), "action": "get", "key": args.key,
                       "value": value, "line": lineno}
        else:
            result = set_value(args.ioc, args.key, str(args.value), dry_run=args.dry_run)
            payload = {"ioc": os.path.abspath(args.ioc), "action": "set", **result}
            state = "dry-run" if args.dry_run else ("changed" if result["changed"] else "unchanged")
            print(
                f"[ioc_field] {args.key}: {result['before']} → {result['after']} "
                f"（L{result['line']}, {state}）"
            )
    except ValueError as error:
        # W1-1：key / value 含换行的注入尝试 → 输入错误（rc=2），.ioc 一个字节都不动。
        print(f"[ioc_field][input-error] {error}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except KeyError as error:
        # `str(KeyError("x"))` 会带上引号（`'x'`）——直接用 args[0] 去掉那层噪音，
        # 否则 stderr 里会出现 `[ioc_field][not-found] 'Mcu.Name 出现 2 次…'` 这种难读形态。
        message = error.args[0] if error.args else str(error)
        print(f"[ioc_field][not-found] {message}", file=sys.stderr)
        return EXIT_KEY_MISSING
    except OSError as error:
        print(f"[ioc_field][input-error] {error}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    payload["schema"] = SCHEMA
    payload["tool"] = {"name": "ioc_field.py", "version": __version__}
    if args.json_out:
        try:
            parent = os.path.dirname(os.path.abspath(args.json_out))
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(args.json_out, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except OSError as error:
            print(f"[ioc_field][input-error] 写 JSON 失败：{error}", file=sys.stderr)
            return EXIT_INPUT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
