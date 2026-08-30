"""Python/Java 源代码语义解析。

解析器尽量按可检索的语义单元输出 Chunk：
- Python：模块级代码、函数、类上下文、类方法；
- Java：包/导入等模块级代码、类型上下文、方法/构造器；
- 语法不完整时保留全文并标记 fallback，交给后续 CodeChunker 安全切分。
"""

from __future__ import annotations

import ast
import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

from module_office.utils.file_parase.base import BaseParser
from module_office.utils.file_parase.do.chunk import Chunk, ContentType, Position


@dataclass(slots=True)
class _CodeUnit:
    start_line: int
    end_line: int
    content: str
    symbol_type: str
    symbol_name: str
    qualified_name: str
    parse_mode: str = "semantic"


class CodeParser(BaseParser):
    """将 Python/Java 文件解析为语义代码块。"""

    def __init__(self, ocr_llm=None):
        # 与 ParserFactory 的统一构造协议兼容；代码解析不需要 OCR。
        self.ocr_llm = ocr_llm

    async def extract(self, file: Path) -> list[Chunk]:
        source = await asyncio.to_thread(self._read_source, file)
        language = self._language_for(file)

        if language == "python":
            units = self._parse_python(source)
        elif language == "java":
            units = self._parse_java(source)
        else:  # ParserFactory 已做后缀校验，保留防御式检查。
            raise ValueError(f"不支持的代码类型: {file.suffix.lower()}")

        source_name = file.name
        return [
            Chunk(
                content=unit.content,
                content_type=ContentType.CODE,
                position=Position(
                    text_range=[unit.start_line, 0, unit.end_line, 0]
                ),
                metadata={
                    "source": source_name,
                    "language": language,
                    "symbol_type": unit.symbol_type,
                    "symbol_name": unit.symbol_name,
                    "qualified_name": unit.qualified_name,
                    "parse_mode": unit.parse_mode,
                },
            )
            for unit in units
            if unit.content.strip()
        ]

    @staticmethod
    def _read_source(file: Path) -> str:
        raw = file.read_bytes()
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    @staticmethod
    def _language_for(file: Path) -> str:
        suffix = file.suffix.lower()
        if suffix == ".py":
            return "python"
        if suffix == ".java":
            return "java"
        raise ValueError(f"不支持的代码类型: {suffix}")

    def _parse_python(self, source: str) -> list[_CodeUnit]:
        lines = source.splitlines(keepends=True)
        if not source.strip():
            return []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return [self._fallback_unit(source, "python")]

        units: list[_CodeUnit] = []
        cursor = 1
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            start = self._python_node_start(node)
            end = getattr(node, "end_lineno", None) or start
            self._append_module_gap(units, lines, cursor, start - 1, "python")

            if isinstance(node, ast.ClassDef):
                units.extend(self._python_class_units(node, lines))
            else:
                units.append(
                    _CodeUnit(
                        start,
                        end,
                        self._slice_lines(lines, start, end),
                        "function",
                        node.name,
                        node.name,
                    )
                )
            cursor = end + 1

        self._append_module_gap(units, lines, cursor, len(lines), "python")
        if not units:
            return [self._fallback_unit(source, "python", parse_mode="module")]
        return sorted(units, key=lambda item: (item.start_line, item.symbol_type == "method"))

    def _python_class_units(self, node: ast.ClassDef, lines: list[str]) -> list[_CodeUnit]:
        start = self._python_node_start(node)
        end = getattr(node, "end_lineno", None) or start
        methods = [
            child
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if not methods:
            return [
                _CodeUnit(
                    start,
                    end,
                    self._slice_lines(lines, start, end),
                    "class",
                    node.name,
                    node.name,
                )
            ]

        # 类上下文保留装饰器、继承关系、文档字符串和字段，但移除方法体，
        # 避免大型类成为一个无法检索的超长块。
        method_spans = [
            (self._python_node_start(method), getattr(method, "end_lineno", method.lineno))
            for method in methods
        ]
        context_parts: list[str] = []
        context_cursor = start
        for method_start, method_end in method_spans:
            if context_cursor <= method_start - 1:
                context_parts.append(self._slice_lines(lines, context_cursor, method_start - 1))
            context_cursor = method_end + 1
        if context_cursor <= end:
            context_parts.append(self._slice_lines(lines, context_cursor, end))
        context = "".join(context_parts).rstrip()

        results: list[_CodeUnit] = []
        if context.strip():
            results.append(
                _CodeUnit(start, end, context, "class_context", node.name, node.name)
            )

        for method in methods:
            method_start = self._python_node_start(method)
            method_end = getattr(method, "end_lineno", None) or method.lineno
            method_source = self._slice_lines(lines, method_start, method_end).rstrip()
            results.append(
                _CodeUnit(
                    method_start,
                    method_end,
                    method_source,
                    "method",
                    method.name,
                    f"{node.name}.{method.name}",
                )
            )
        return results

    @staticmethod
    def _python_node_start(node: ast.AST) -> int:
        decorators = getattr(node, "decorator_list", [])
        if decorators:
            return min(getattr(item, "lineno", node.lineno) for item in decorators)
        return node.lineno

    def _parse_java(self, source: str) -> list[_CodeUnit]:
        if not source.strip():
            return []
        sanitized = self._sanitize_java(source)
        depths = self._brace_depths(sanitized)
        type_pattern = re.compile(r"\b(class|interface|enum|record)\s+([A-Za-z_$][\w$]*)")
        type_ranges: list[tuple[re.Match[str], int, int]] = []

        for match in type_pattern.finditer(sanitized):
            if depths[match.start()] != 0:
                continue
            open_brace = sanitized.find("{", match.end())
            if open_brace < 0:
                continue
            close_brace = self._matching_brace(sanitized, open_brace)
            if close_brace < 0:
                return [self._fallback_unit(source, "java")]
            type_ranges.append((match, open_brace, close_brace))

        if not type_ranges:
            return [self._fallback_unit(source, "java")]

        units: list[_CodeUnit] = []
        cursor = 0
        for match, open_brace, close_brace in type_ranges:
            type_start = self._line_start(source, match.start())
            self._append_java_gap(units, source, cursor, type_start, "java")
            units.extend(
                self._java_type_units(
                    source,
                    sanitized,
                    type_start,
                    open_brace,
                    close_brace,
                    match.group(1),
                    match.group(2),
                )
            )
            cursor = close_brace + 1
        self._append_java_gap(units, source, cursor, len(source), "java")
        return sorted(units, key=lambda item: (item.start_line, item.symbol_type == "method"))

    def _java_type_units(
        self,
        source: str,
        sanitized: str,
        type_start: int,
        open_brace: int,
        close_brace: int,
        type_kind: str,
        type_name: str,
    ) -> list[_CodeUnit]:
        method_spans = self._java_method_spans(sanitized, open_brace, close_brace)
        start_line = self._line_number(source, type_start)
        end_line = self._line_number(source, close_brace)
        if not method_spans:
            return [
                _CodeUnit(
                    start_line,
                    end_line,
                    source[type_start : close_brace + 1],
                    type_kind,
                    type_name,
                    type_name,
                )
            ]

        results: list[_CodeUnit] = []
        context_parts = [source[type_start : open_brace + 1]]
        context_cursor = open_brace + 1
        for method_start, method_end, method_name in method_spans:
            context_parts.append(source[context_cursor:method_start])
            context_cursor = method_end + 1
            method_source = source[method_start : method_end + 1].strip()
            symbol_type = "constructor" if method_name == type_name else "method"
            results.append(
                _CodeUnit(
                    self._line_number(source, method_start),
                    self._line_number(source, method_end),
                    method_source,
                    symbol_type,
                    method_name,
                    f"{type_name}.{method_name}",
                )
            )
        context_parts.append(source[context_cursor : close_brace + 1])
        context = "".join(context_parts).strip()
        if context:
            results.append(
                _CodeUnit(
                    start_line,
                    end_line,
                    context,
                    f"{type_kind}_context",
                    type_name,
                    type_name,
                )
            )
        return results

    def _java_method_spans(
        self, sanitized: str, open_brace: int, close_brace: int
    ) -> list[tuple[int, int, str]]:
        spans: list[tuple[int, int, str]] = []
        depth = 1
        statement_start = open_brace + 1
        index = open_brace + 1
        control_words = {"if", "for", "while", "switch", "catch", "synchronized", "try", "do"}

        while index < close_brace:
            char = sanitized[index]
            if char == "{" and depth == 1:
                header = sanitized[statement_start:index].strip()
                name_match = re.search(r"([A-Za-z_$][\w$]*)\s*\([^(){};]*\)\s*(?:throws\s+[^{}]+)?$", header)
                name = name_match.group(1) if name_match else ""
                if name and name not in control_words and "=" not in header:
                    method_end = self._matching_brace(sanitized, index)
                    if method_end < 0 or method_end > close_brace:
                        break
                    start = statement_start
                    while start < index and sanitized[start].isspace():
                        start += 1
                    spans.append((start, method_end, name))
                    index = method_end + 1
                    statement_start = index
                    continue
                depth += 1
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 1:
                    statement_start = index + 1
            elif char == ";" and depth == 1:
                statement_start = index + 1
            index += 1
        return spans

    @staticmethod
    def _sanitize_java(source: str) -> str:
        """移除注释/字符串内容但保留长度和换行，便于安全计算大括号。"""
        result = list(source)
        index = 0
        state = "code"
        quote = ""
        while index < len(source):
            char = source[index]
            nxt = source[index + 1] if index + 1 < len(source) else ""
            if state == "code":
                if char == "/" and nxt == "/":
                    result[index] = result[index + 1] = " "
                    index += 2
                    state = "line_comment"
                    continue
                if char == "/" and nxt == "*":
                    result[index] = result[index + 1] = " "
                    index += 2
                    state = "block_comment"
                    continue
                if char in {'"', "'"}:
                    quote = char
                    result[index] = " "
                    state = "string"
            elif state == "line_comment":
                if char == "\n":
                    state = "code"
                else:
                    result[index] = " "
            elif state == "block_comment":
                if char == "*" and nxt == "/":
                    result[index] = result[index + 1] = " "
                    index += 2
                    state = "code"
                    continue
                if char != "\n":
                    result[index] = " "
            elif state == "string":
                if char == "\\":
                    result[index] = " "
                    if index + 1 < len(source) and source[index + 1] != "\n":
                        result[index + 1] = " "
                        index += 2
                        continue
                elif char == quote:
                    result[index] = " "
                    state = "code"
                elif char != "\n":
                    result[index] = " "
            index += 1
        return "".join(result)

    @staticmethod
    def _brace_depths(text: str) -> list[int]:
        depths = [0] * (len(text) + 1)
        depth = 0
        for index, char in enumerate(text):
            depths[index] = depth
            if char == "{":
                depth += 1
            elif char == "}":
                depth = max(0, depth - 1)
        depths[len(text)] = depth
        return depths

    @staticmethod
    def _matching_brace(text: str, open_brace: int) -> int:
        depth = 0
        for index in range(open_brace, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    return index
        return -1

    def _append_module_gap(
        self,
        units: list[_CodeUnit],
        lines: list[str],
        start: int,
        end: int,
        language: str,
    ) -> None:
        if start > end:
            return
        content = self._slice_lines(lines, start, end)
        if content.strip():
            units.append(
                _CodeUnit(start, end, content, "module", "<module>", "<module>")
            )

    def _append_java_gap(
        self,
        units: list[_CodeUnit],
        source: str,
        start: int,
        end: int,
        language: str,
    ) -> None:
        content = source[start:end]
        if content.strip():
            units.append(
                _CodeUnit(
                    self._line_number(source, start),
                    self._line_number(source, max(start, end - 1)),
                    content,
                    "module",
                    "<module>",
                    "<module>",
                )
            )

    @staticmethod
    def _fallback_unit(source: str, language: str, parse_mode: str = "fallback") -> _CodeUnit:
        return _CodeUnit(
            1,
            max(1, len(source.splitlines())),
            source,
            "module",
            "<module>",
            "<module>",
            parse_mode=parse_mode,
        )

    @staticmethod
    def _slice_lines(lines: list[str], start: int, end: int) -> str:
        return "".join(lines[max(0, start - 1) : max(0, end)])

    @staticmethod
    def _line_start(source: str, offset: int) -> int:
        newline = source.rfind("\n", 0, offset)
        return 0 if newline < 0 else newline + 1

    @staticmethod
    def _line_number(source: str, offset: int) -> int:
        return source.count("\n", 0, max(0, offset)) + 1
