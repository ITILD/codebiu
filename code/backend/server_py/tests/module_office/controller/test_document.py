# -*- coding: utf-8 -*-
"""module_office 文档解析/分块接口标准测试
覆盖: /office/document-parse/get-markdown-by-file, /office/document-parse/split-code

说明:
- app.py 目前未导入 module_office.config.server(/office 未挂载, 属集成缺陷, 已在报告说明),
  测试内按模块设计方式显式 import 触发挂载与路由注册
- md/txt/py/java 解析均走本地解析器(docling SimplePipeline / ast), 不依赖外部解析服务与 LLM,
  可真实调用; PDF/OCR 等需要下载模型的路径不在本测试范围
"""

import time
import uuid

import httpx

from common.config.path import DIR_TEMP

# 显式触发 /office 子应用挂载与控制器路由注册(生产入口 app.py 缺少对应导入)
import module_office.config.server  # noqa: F401
import module_office.controller.document_parse  # noqa: F401

PARSE_BASE = "/office/document-parse"

# 用于 split-code 的 Python 样例(含模块级代码/函数/类+方法)
PY_SOURCE = '''"""模块文档字符串"""

MODULE_CONST = 1


def calc_sum(a: int, b: int) -> int:
    """计算两数之和"""
    return a + b


class CalcService:
    """计算服务"""

    def multiply(self, a: int, b: int) -> int:
        """计算两数之积"""
        return a * b
'''

# 用于 split-code 的 Java 样例(含类型上下文/字段/方法)
JAVA_SOURCE = '''package com.example;

public class Calculator {
    private int base = 10;

    public int add(int a, int b) {
        return a + b + this.base;
    }
}
'''


def _suffix() -> str:
    """生成时间戳+随机唯一后缀, 避免临时文件相互覆盖"""
    return f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


async def test_get_markdown_by_file_md(client: httpx.AsyncClient):
    """上传 .md 文件解析为 markdown: 200 且返回内容包含上传文本"""
    suffix = _suffix()
    filename = f"parse_in_{suffix}.md"
    text = f"# 接口测试标题_{suffix}\n\n这是接口测试的正文段落 {suffix}。\n"
    try:
        resp = await client.post(
            f"{PARSE_BASE}/get-markdown-by-file",
            files={"file": (filename, text.encode("utf-8"), "text/markdown")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body, str), f"应返回 markdown 字符串: {body!r}"
        assert f"接口测试标题_{suffix}" in body, f"标题应保留在解析结果中: {body}"
        assert suffix in body
    finally:
        # 端点会把上传文件与解析结果写入临时目录, 测试后清理
        (DIR_TEMP / filename).unlink(missing_ok=True)
        (DIR_TEMP / f"parse_in_{suffix}.md").unlink(missing_ok=True)


async def test_get_markdown_by_file_txt(client: httpx.AsyncClient):
    """上传 .txt 文件解析为 markdown: 200 且正文内容保留"""
    suffix = _suffix()
    filename = f"parse_in_{suffix}.txt"
    text = f"纯文本解析测试内容 {suffix}。第二行内容。\n"
    try:
        resp = await client.post(
            f"{PARSE_BASE}/get-markdown-by-file",
            files={"file": (filename, text.encode("utf-8"), "text/plain")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body, str), f"应返回 markdown 字符串: {body!r}"
        assert suffix in body, f"正文应保留在解析结果中: {body}"
    finally:
        # 清理输入临时文件(.txt)与解析输出文件(.md)
        (DIR_TEMP / filename).unlink(missing_ok=True)
        (DIR_TEMP / f"parse_in_{suffix}.md").unlink(missing_ok=True)


async def test_get_markdown_by_file_unsupported_type(client: httpx.AsyncClient):
    """上传不支持的文件类型应 400(服务层 ValueError 映射)"""
    suffix = _suffix()
    resp = await client.post(
        f"{PARSE_BASE}/get-markdown-by-file",
        files={"file": (f"binary_{suffix}.xyz", b"\x00\x01not-a-doc", "application/octet-stream")},
    )
    assert resp.status_code == 400, resp.text
    assert "不支持的文件类型" in resp.json()["detail"], resp.text


async def test_get_markdown_by_file_missing_file(client: httpx.AsyncClient):
    """缺少 file 表单字段应 422"""
    resp = await client.post(f"{PARSE_BASE}/get-markdown-by-file")
    assert resp.status_code == 422, resp.text


async def test_split_code_python(client: httpx.AsyncClient):
    """上传 .py 文件: 按语义拆分出函数/类方法, 元数据回填原始文件名"""
    suffix = _suffix()
    filename = f"parser_{suffix}.py"
    resp = await client.post(
        f"{PARSE_BASE}/split-code",
        files={"file": (filename, PY_SOURCE.encode("utf-8"), "text/x-python")},
    )
    assert resp.status_code == 200, resp.text
    chunks = resp.json()
    assert isinstance(chunks, list) and chunks, "应返回非空分块列表"

    # 函数与类方法均被拆出
    symbols = {c["metadata"]["symbol_name"] for c in chunks}
    assert "calc_sum" in symbols, f"应拆出模块级函数: {symbols}"
    assert "multiply" in symbols, f"应拆出类方法: {symbols}"

    # 分块结构与元数据
    for chunk in chunks:
        assert chunk["content_type"] == "code"
        assert chunk["metadata"]["language"] == "python"
        assert chunk["metadata"]["source"] == filename, "应回填上传时的原始文件名"


async def test_split_code_java(client: httpx.AsyncClient):
    """上传 .java 文件: 拆分出类型上下文与方法"""
    suffix = _suffix()
    filename = f"Calculator_{suffix}.java"
    resp = await client.post(
        f"{PARSE_BASE}/split-code",
        files={"file": (filename, JAVA_SOURCE.encode("utf-8"), "text/x-java-source")},
    )
    assert resp.status_code == 200, resp.text
    chunks = resp.json()
    assert isinstance(chunks, list) and chunks, "应返回非空分块列表"
    assert all(c["metadata"]["language"] == "java" for c in chunks)
    symbols = {c["metadata"]["symbol_name"] for c in chunks}
    assert "add" in symbols, f"应拆出方法 add: {symbols}"
    assert "Calculator" in symbols, f"应拆出类型上下文: {symbols}"


async def test_split_code_python_syntax_fallback(client: httpx.AsyncClient):
    """语法不完整的 .py: 返回单个全文 fallback 块而非报错"""
    suffix = _suffix()
    filename = f"broken_{suffix}.py"
    broken = f"def broken_{suffix}(:\n    pass\n"
    resp = await client.post(
        f"{PARSE_BASE}/split-code",
        files={"file": (filename, broken.encode("utf-8"), "text/x-python")},
    )
    assert resp.status_code == 200, resp.text
    chunks = resp.json()
    assert len(chunks) == 1, f"语法错误应返回单个 fallback 块: {chunks}"
    assert chunks[0]["metadata"]["parse_mode"] == "fallback", chunks
    assert f"broken_{suffix}" in chunks[0]["content"], "fallback 块应保留全文"


async def test_split_code_python_empty(client: httpx.AsyncClient):
    """上传空的 .py 文件: 200 且返回空分块列表"""
    suffix = _suffix()
    resp = await client.post(
        f"{PARSE_BASE}/split-code",
        files={"file": (f"empty_{suffix}.py", b"", "text/x-python")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == [], "空文件应返回空列表"


async def test_split_code_unsupported_suffix(client: httpx.AsyncClient):
    """上传非 .py/.java 文件应 400(仅支持代码文件)"""
    suffix = _suffix()
    resp = await client.post(
        f"{PARSE_BASE}/split-code",
        files={"file": (f"note_{suffix}.txt", "普通文本".encode("utf-8"), "text/plain")},
    )
    assert resp.status_code == 400, resp.text
    assert "仅支持" in resp.json()["detail"], resp.text


async def test_split_code_missing_file(client: httpx.AsyncClient):
    """缺少 file 表单字段应 422"""
    resp = await client.post(f"{PARSE_BASE}/split-code")
    assert resp.status_code == 422, resp.text
