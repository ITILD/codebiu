"""文本识别(recognize)子包: CRNN 将文本图批量识别为文字"""
from .ctc_decode import CTCLabelDecode
from .recognizer import TextRecognizer

__all__ = ["TextRecognizer", "CTCLabelDecode"]
