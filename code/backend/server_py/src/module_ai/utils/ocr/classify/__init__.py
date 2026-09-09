"""方向分类(classify)子包: 判断文本图方向并旋转校正(0/180 度)"""
from .classifier import ClsPostProcess, TextClassifier

__all__ = ["TextClassifier", "ClsPostProcess"]
