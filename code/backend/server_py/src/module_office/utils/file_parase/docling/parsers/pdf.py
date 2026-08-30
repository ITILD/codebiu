"""PDF 解析器(docling 引擎)。

自动检测 PDF 文本层：文本型走 ``do_ocr=False``(~5s，跳过冗余 OCR)，
扫描件/图片型走 ``do_ocr=True``(完整 OCR)。调用方无需关心 PDF 子类型。
"""
import logging
from pathlib import Path

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.document import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from common.config.path import DIR_MODEL
from module_office.utils.file_parase.docling.base import DoclingBaseParser

logger = logging.getLogger(__name__)

class PDFParser(DoclingBaseParser):
    """PDF 解析器(docling 引擎)。

    支持通过 ocr_llm 进行 OCR 识别(扫描件/图片型 PDF)。解析时按 PDF 文本层
    自动选择 converter：文本型跳过 OCR，扫描件走完整 OCR，两类 converter 各自
    懒加载并复用，避免重复加载模型。

    Converter 在**类级别**缓存(``_shared_converter_text`` / ``_shared_converter_ocr``),
    跨所有 PDFParser 实例复用; ``ocr_llm`` 仍 per-request(仅用于图片内容提取)。
    """

    # 类级 converter 缓存: 文本型/扫描件各一份, 跨实例复用避免重复加载模型
    _shared_converter_text: DocumentConverter | None = None
    _shared_converter_ocr: DocumentConverter | None = None

    def _get_converter(self, file: Path) -> DocumentConverter:
        """按 PDF 文本层选择 converter，复用类级缓存避免重复加载模型。

        文本型 PDF(有文本层)走 ``do_ocr=False`` 跳过冗余 OCR；
        扫描件(无文本层)走 ``do_ocr=True`` 完整 OCR。
        """
        if self._has_text_layer(file):
            if PDFParser._shared_converter_text is None:
                PDFParser._shared_converter_text = self._make_converter(do_ocr=False)
            return PDFParser._shared_converter_text
        if PDFParser._shared_converter_ocr is None:
            PDFParser._shared_converter_ocr = self._make_converter(do_ocr=True)
        return PDFParser._shared_converter_ocr

    @staticmethod
    def _build_pdf_pipeline_options(do_ocr: bool = True) -> PdfPipelineOptions:
        """构造 PDF pipeline 选项，强制使用本地预置模型避免联网下载。

        docling 的 ``artifacts_path`` 为 pipeline 级参数，会同时作用于
        layout / table structure / OCR 三个阶段，因此需在 ``DIR_MODEL`` 下
        预置以下目录(目录名须与 repo_id 的 ``/`` 替换为 ``--`` 一致):

        * ``docling-project--docling-layout-heron/``  布局模型(RTDetrV2)
        * ``docling-project--docling-models/``        TableFormer 表格结构模型
        * ``RapidOcr/``                               RapidOCR 检测/分类/识别 onnx

        任一目录缺失时回退到 docling 默认行为(联网下载或 HF 缓存)。
        """
        logger.info("构造 PDF pipeline 选项")
        pipeline_options = PdfPipelineOptions()
        pipeline_options.artifacts_path = str(DIR_MODEL)
        # 启用 GPU: 同时加速 layout(RT-DETR, transformers 引擎)与 RapidOCR。
        # docling 据 accelerator_options.device 推导 use_cuda 并下发到各引擎。
        pipeline_options.accelerator_options = AcceleratorOptions(
            device=AcceleratorDevice.CUDA
        )
        # RapidOCR 优先 torch 后端(.pth)走 CUDA；缺 pth 时回退 onnxruntime(.onnx, CPU)。
        # PP-OCRv6 medium 是中文可用最大档(server 不支持中文)；cls 沿用 v4 mobile。
        rapid_dir = DIR_MODEL / "RapidOcr"
        det_pth = rapid_dir / "PP-OCRv6_det_medium.pth"
        rec_pth = rapid_dir / "PP-OCRv6_rec_medium.pth"
        cls_pth = rapid_dir / "ch_ptocr_mobile_v2.0_cls_mobile.pth"
        keys_txt = rapid_dir / "ppocrv6_dict.txt"
        if det_pth.exists() and rec_pth.exists() and cls_pth.exists():
            pipeline_options.ocr_options = RapidOcrOptions(
                backend="torch",
                det_model_path=str(det_pth),
                cls_model_path=str(cls_pth),
                rec_model_path=str(rec_pth),
                rec_keys_path=str(keys_txt) if keys_txt.exists() else None,
            )
        else:
            logger.warning("PP-OCRv6 pth模型缺失，回退到 onnxruntime")
            det_onnx = rapid_dir / "PP-OCRv6_det_medium.onnx"
            rec_onnx = rapid_dir / "PP-OCRv6_rec_medium.onnx"
            if det_onnx.exists() and rec_onnx.exists():
                pipeline_options.ocr_options = RapidOcrOptions(
                    det_model_path=str(det_onnx),
                    rec_model_path=str(rec_onnx),
                )
        pipeline_options.do_ocr = do_ocr
        # 提取文档内嵌图片(figures/charts/photos)为单独图像，供 _save_picture 保存。
        # 默认 False 时 PictureItem.get_image() 返回 None，图片无法落盘。
        pipeline_options.generate_picture_images = True
        return pipeline_options

    def _make_converter(self, do_ocr: bool) -> DocumentConverter:
        """按 do_ocr 开关构造 DocumentConverter(含本地模型与 GPU 配置)。"""
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=self._build_pdf_pipeline_options(do_ocr=do_ocr)
                )
            }
        )

    @staticmethod
    def _has_text_layer(file: Path) -> bool:
        """检测 PDF 是否有可用文本层(平均每页字符数超阈值)。

        扫描件文本层为空或极少;文本型 PDF 每页通常有数十至数百字符。
        """
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(str(file))
        try:
            total = sum(
                len(page.get_textpage().get_text_range().strip()) for page in doc
            )
            return total / max(len(doc), 1) > 50
        finally:
            doc.close()
