"""RAG 文档解析双引擎测试(本地 docling / 外部 mineru)。

覆盖层次:
- 单元层(必跑, 零外部依赖):
  * ParserFactory 双引擎路由(mineru 不支持的格式回退 docling)
  * docling 线程化回归: convert 在专用线程执行且解析期间事件循环不被阻塞
    (对应"上传/解析卡死其他请求"修复的回归测试)
  * MinerU 结果 zip 解包契约(content_list.json/images 落盘)与条目→Chunk 映射
  * LocalMinerUClient HTTP 契约(zip 成功 / 非 zip 错误体 / 5xx)
- 集成层(环境就绪才跑, 否则 skip):
  * docling 真实解析: 需预置模型(DIR_MODEL 或 HF 缓存), 避免 CI 联网下载数百 MB
  * mineru 远程真实解析(mineru.net): 需配置 token 且网络可达, 完整链路
    上传→轮询→下载 zip→解包转 Chunk, 全程约 30~90s
  * mineru 本地 docker 真实解析: mode=local 且 local_base_url 可达
"""

import asyncio
import json
import shutil
import threading
import time
import zipfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from common.config.path import DIR_MODEL, DIR_TEMP
from module_office.utils.file_parase.docling.parsers import MarkdownParser, PDFParser
from module_office.utils.file_parase.factory import ParserFactory
from module_office.utils.file_parase.do.chunk import ContentType
from module_office.utils.file_parase.mineru.client import (
    LocalMinerUClient,
    MinerUError,
)
from module_office.utils.file_parase.mineru.config import load_config
from module_office.utils.file_parase.mineru.parser import MinerUParser

# ==================== 测试素材 ====================

# 文本层长度需超过 PDFParser._has_text_layer 阈值(每页 >50 字符)以确保走文本型分支
_PDF_TEXT = "RAG document parse integration test. This paragraph provides enough text layer characters for pdfium detection. Hello docling and mineru."


def _build_pdf_bytes(text: str) -> bytes:
    """构造单页文本型 PDF(手写最小结构, 无外部生成库依赖)。"""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for idx, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{idx} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(xref_pos).encode() + b"\n%%EOF\n"
    )
    return bytes(out)


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """生成并自验证的最小文本型 PDF。"""
    import pypdfium2 as pdfium

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(_build_pdf_bytes(_PDF_TEXT))
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        text = doc[0].get_textpage().get_text_range()
        assert "RAG document parse" in text, "手写 PDF 文本层无效, pdfium 读不到文本"
    finally:
        doc.close()
    return pdf_path


def _build_mineru_zip(stem: str) -> bytes:
    """构造 MinerU 结果 zip({stem}/content_list.json + full.md + images/...)。"""
    content_list = [
        {"type": "text", "text": "系统架构总览", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "本文档用于验证解析链路。", "page_idx": 0},
        {
            "type": "table",
            "table_body": "<table><tr><th>引擎</th><th>部署</th></tr>"
            "<tr><td>docling</td><td>本地 GPU</td></tr></table>",
            "page_idx": 0,
        },
        {
            "type": "image",
            "img_path": "images/fig1.jpg",
            "img_caption": ["图1 系统架构"],
            "page_idx": 1,
        },
    ]
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{stem}/content_list.json", json.dumps(content_list, ensure_ascii=False))
        zf.writestr(f"{stem}/full.md", "# 系统架构总览\n\n本文档用于验证解析链路。")
        zf.writestr(f"{stem}/images/fig1.jpg", b"\xff\xd8\xff\xe0FAKEJPEGDATA")
    return buf.getvalue()


# ==================== 单元层: 工厂路由 ====================


def test_factory_engine_routing(sample_pdf: Path):
    """双引擎路由: 按后缀与 engine 选择解析器, mineru 不支持格式回退 docling。"""
    # PDF 双引擎均可
    assert isinstance(
        ParserFactory.create(Path("a.pdf"), engine="docling"), PDFParser
    )
    assert isinstance(
        ParserFactory.create(Path("a.pdf"), engine="mineru"), MinerUParser
    )
    # mineru 不支持纯文本 → 回退 docling 注册表
    assert isinstance(
        ParserFactory.create(Path("a.md"), engine="mineru"), MarkdownParser
    )
    # docling 引擎自身支持
    assert isinstance(
        ParserFactory.create(Path("a.md"), engine="docling"), MarkdownParser
    )
    # 未注册后缀 / 未知引擎报错
    with pytest.raises(ValueError, match="不支持的文件类型"):
        ParserFactory.create(Path("a.xyz"), engine="docling")
    with pytest.raises(ValueError, match="不支持的解析引擎"):
        ParserFactory.create(Path("a.pdf"), engine="unknown")


# ==================== 单元层: docling 线程化回归 ====================


async def test_docling_convert_runs_off_event_loop(
    sample_pdf: Path, monkeypatch
):
    """convert 必须在专用单线程执行且不阻塞事件循环。

    回归背景: convert 曾直接在事件循环上同步执行, 解析期间同进程所有请求
    被卡死。断言三点:
    1. convert 在 docling-parse 前缀的专用线程上执行;
    2. convert 线程 sleep(模拟推理)期间, 事件循环仍能正常调度其他协程;
    3. 解析结果 Chunk 正常产出。
    """
    from docling_core.types.doc import DocItemLabel, DoclingDocument

    doc = DoclingDocument(name="mock")
    doc.add_text(label=DocItemLabel.TEXT, text="docling 线程化回归测试内容")

    entered = threading.Event()
    thread_names: list[str] = []

    class _FakeConverter:
        def convert(self, file):
            thread_names.append(threading.current_thread().name)
            entered.set()
            time.sleep(0.3)  # 模拟推理耗时: 期间事件循环必须仍可调度
            return SimpleNamespace(document=doc)

    monkeypatch.setattr(
        PDFParser, "_get_converter", lambda self, file: _FakeConverter()
    )

    parser = PDFParser(ocr_llm=None)
    task = asyncio.create_task(parser.extract(sample_pdf))

    # 等 convert 进入线程(最多 2s)
    deadline = time.monotonic() + 2.0
    while not entered.is_set():
        assert time.monotonic() < deadline, "convert 未在 2s 内进入专用线程"
        await asyncio.sleep(0.01)

    # convert 线程 sleep(0.3) 期间, 事件循环的 50ms 协程必须在 0.25s 内完成
    # (若 convert 阻塞事件循环, 此 await 会拖到 convert 结束才返回 → 断言失败)
    t0 = time.monotonic()
    await asyncio.sleep(0.05)
    assert time.monotonic() - t0 < 0.25, "convert 期间事件循环被阻塞"

    chunks = await asyncio.wait_for(task, timeout=5)
    assert thread_names and thread_names[0].startswith("docling-parse"), (
        f"convert 应在 docling-parse 专用线程执行, 实际: {thread_names}"
    )
    assert any(
        c.content_type == ContentType.TEXT and "线程化回归" in c.content
        for c in chunks
    ), f"应产出含 mock 文本的 TEXT chunk: {[(c.content_type, c.content) for c in chunks]}"


# ==================== 单元层: MinerU 结果契约 ====================


async def test_mineru_unpack_and_chunk_mapping():
    """结果 zip 解包契约: content_list/images 落盘 + 条目→Chunk 类型映射。"""
    stem = f"mineru_test_{time.strftime('%H%M%S')}_{threading.get_ident()}"
    try:
        parser = MinerUParser(ocr_llm=None)
        zip_bytes = _build_mineru_zip(stem)

        content_list, images = parser._unpack(zip_bytes, stem)
        assert [item["type"] for item in content_list] == [
            "text", "text", "table", "image",
        ]
        # images 双键映射(相对键 + 文件名), 本地已落盘
        assert "fig1.jpg" in images and Path(images["fig1.jpg"]).exists()

        chunks = []
        for item in content_list:
            chunks.extend(await parser._item_to_chunks(item, images))
        types = [c.content_type for c in chunks]
        # 标题→TITLE / 正文→TEXT / 表格→TABLE / 图片→IMAGE + IMAGE_CONTENT(caption)
        assert types == [
            ContentType.TITLE,
            ContentType.TEXT,
            ContentType.TABLE,
            ContentType.IMAGE,
            ContentType.IMAGE_CONTENT,
        ], f"条目映射类型不符: {types}"
        # page_idx(0-based) → 页码(1-based)
        assert chunks[0].position.page == 1
        assert chunks[3].position.page == 2
        # 标题级别透传
        assert chunks[0].position.heading_level == 1
        # 表格转紧凑 markdown
        assert "| 引擎 | 部署 |" in chunks[2].content
        # 图片说明作为 IMAGE_CONTENT
        assert "系统架构" in chunks[4].content
    finally:
        shutil.rmtree(DIR_TEMP / stem, ignore_errors=True)


async def test_mineru_local_client_http_contracts(monkeypatch, tmp_path: Path):
    """LocalMinerUClient HTTP 契约: zip 成功 / 非 zip 错误体 / 5xx → MinerUError。"""
    from module_office.utils.file_parase.mineru.client import MinerUConfig

    cfg = MinerUConfig(
        mode="local",
        local_base_url="http://mineru-test",
        local_endpoint="/file_parse",
        timeout=5,
    )
    client = LocalMinerUClient(cfg)
    fake_file = tmp_path / "doc.pdf"
    fake_file.write_bytes(_build_pdf_bytes(_PDF_TEXT))
    zip_bytes = _build_mineru_zip("contract")

    # 单次 patch + 可切换 handler: 若多次 patch 工厂, 后续工厂会捕获上一次
    # 已被替换的 AsyncClient, 导致 transport 被旧 handler 覆盖
    real_client = httpx.AsyncClient
    handler_box: dict = {}

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda request: handler_box["fn"](request)
        )
        return real_client(*args, **kwargs)

    monkeypatch.setattr(
        "module_office.utils.file_parase.mineru.client.httpx.AsyncClient", factory
    )

    # 1. 正常 zip 流
    handler_box["fn"] = lambda request: httpx.Response(200, content=zip_bytes)
    assert await client.parse(fake_file) == zip_bytes

    # 2. 200 但非 zip(参数/版本错误的 JSON 体)
    handler_box["fn"] = lambda request: httpx.Response(
        200, json={"code": 1, "msg": "bad param"}
    )
    with pytest.raises(MinerUError, match="非 zip"):
        await client.parse(fake_file)

    # 3. 服务端 5xx
    handler_box["fn"] = lambda request: httpx.Response(500, text="boom")
    with pytest.raises(MinerUError, match=r"500"):
        await client.parse(fake_file)


# ==================== 集成层: 环境就绪才真跑 ====================


def _docling_models_ready() -> bool:
    """docling 模型预置检测(DIR_MODEL artifacts 目录或 HF 缓存)。"""
    if (DIR_MODEL / "docling-project--docling-layout-heron").exists():
        return True
    hf_hub = Path.home() / ".cache" / "huggingface" / "hub"
    return hf_hub.exists() and any(hf_hub.glob("models--*docling*"))


@pytest.mark.skipif(
    not _docling_models_ready(),
    reason="docling 本地模型未预置(DIR_MODEL/docling-project--* 或 HF 缓存), "
    "跳过真实解析避免测试期间联网下载数百 MB 模型; 预置后自动启用",
)
async def test_docling_real_parse_pdf(sample_pdf: Path):
    """[集成] 本地 docling 真实解析文本型 PDF(含模型加载与 GPU 推理)。"""
    parser = ParserFactory.create(sample_pdf, engine="docling")
    assert isinstance(parser, PDFParser)
    chunks = await asyncio.wait_for(parser.extract(sample_pdf), timeout=300)
    assert chunks, "docling 解析结果为空"
    assert any(
        c.content_type == ContentType.TEXT and "RAG document parse" in c.content
        for c in chunks
    ), f"应识别出 PDF 文本层内容: {[(c.content_type, c.content[:40]) for c in chunks[:5]]}"
    assert all(c.position.page >= 1 for c in chunks)


async def test_mineru_remote_real_parse_pdf(sample_pdf: Path):
    """[集成] 外部 mineru.net 远程真实解析: 上传→轮询→下载 zip→解包转 Chunk。"""
    cfg = load_config()
    if cfg.mode != "remote" or not cfg.token:
        pytest.skip("mineru 未配置远程模式 token(config.seed.yaml/CODEBIU_MINERU__TOKEN)")
    try:
        async with httpx.AsyncClient(timeout=5) as probe:
            await probe.get("https://mineru.net")
    except httpx.HTTPError:
        pytest.skip("mineru.net 网络不可达")

    parser = ParserFactory.create(sample_pdf, engine="mineru")
    assert isinstance(parser, MinerUParser)
    chunks = await asyncio.wait_for(parser.extract(sample_pdf), timeout=600)
    assert chunks, "mineru 远程解析结果为空"
    assert any(
        c.content_type in (ContentType.TEXT, ContentType.TITLE)
        and "RAG document parse" in c.content
        for c in chunks
    ), f"应识别出 PDF 文本内容: {[(c.content_type, c.content[:40]) for c in chunks[:5]]}"
    # 解包产物清理(DIR_TEMP/<stem>)
    shutil.rmtree(DIR_TEMP / sample_pdf.stem, ignore_errors=True)


async def test_mineru_local_real_parse_pdf(sample_pdf: Path):
    """[集成] 本地 docker mineru-api 真实解析(mode=local 且服务可达)。"""
    cfg = load_config()
    if cfg.mode != "local":
        pytest.skip(f"mineru 模式为 {cfg.mode}(未启用本地 docker mineru-api)")
    try:
        async with httpx.AsyncClient(timeout=3) as probe:
            await probe.get(cfg.local_base_url)
    except httpx.HTTPError:
        pytest.skip(f"本地 mineru 服务不可达: {cfg.local_base_url}")

    parser = ParserFactory.create(sample_pdf, engine="mineru")
    chunks = await asyncio.wait_for(parser.extract(sample_pdf), timeout=600)
    assert chunks and any(
        c.content_type in (ContentType.TEXT, ContentType.TITLE) for c in chunks
    )
    shutil.rmtree(DIR_TEMP / sample_pdf.stem, ignore_errors=True)
