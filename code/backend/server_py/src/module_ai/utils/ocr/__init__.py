"""OCR 工具包: 按子任务划分的检测/分类/识别/版面/分段/修复工具包

子包职责:
    - detect:    文本检测(DBNet), 定位文本行区域
    - classify:  文本方向分类(0/180 度旋转校正)
    - recognize: 文本识别(CRNN + CTC 解码)
    - layout:    版面分析(YOLOv8, 标题/图片/表格/目录区域)
    - segment:   排版分段解析(多栏/单栏/段落合并)
    - inpaint:   文字消除修复
    - pipeline:  端到端流水线编排(检测->分类->识别->重试)
设备切换(CPU/GPU)统一由 runtime.OrtInferSession 管理, 配置见 conf_ocr_ort。
"""
from module_ai.utils.ocr.classify import TextClassifier
from module_ai.utils.ocr.detect import TextDetector
from module_ai.utils.ocr.layout import RapidLayout
from module_ai.utils.ocr.pipeline import RapidOCR, detect_recognize, get_ocr_pipeline, load_onnx_model
from module_ai.utils.ocr.recognize import TextRecognizer
from module_ai.utils.ocr.runtime import OrtInferSession, build_providers
from module_ai.utils.ocr.segment import getParser

__all__ = [
    "TextDetector", "TextClassifier", "TextRecognizer", "RapidLayout",
    "RapidOCR", "detect_recognize", "get_ocr_pipeline", "load_onnx_model",
    "OrtInferSession", "build_providers", "getParser",
]
