"""OCR 服务门面: 识别/分段/版面分析统一入口

模型加载策略: 全部引擎(识别流水线/版面分析)惰性加载并缓存,
首次调用对应方法时才加载模型, 保证未配置 ocr 的环境导入本服务不报错。
"""
from functools import lru_cache

from module_ai.utils.ocr.layout import RapidLayout
from module_ai.utils.ocr.pipeline import detect_recognize
from module_ai.utils.ocr.segment.parser_multi_para import MultiPara

from module_ai.config.ocr import get_layout_model_path

# 排版分段引擎(纯算法, 不加载模型)
segment_engine = MultiPara()


@lru_cache(maxsize=1)
def get_layout_engine() -> RapidLayout:
    """获取版面分析引擎(惰性加载, 全局缓存)"""
    return RapidLayout(model_path=get_layout_model_path())

class OcrService:
    def recognize(self,image_cv: any, detect: bool, classify: bool, lang: str, inpaint=False):
        """执行文字识别(OCR)处理，支持多语言识别、文本检测和分类

        Args:
            image_cv (Any): 输入图像，支持OpenCV格式(numpy.ndarray)或文件路径(str)
            detect (bool): 是否启用文本检测(定位文字区域)
            classify (bool): 是否启用文本分类(识别文本类型如标题/正文)
            lang (str): 目标语言代码(如'en'/'zh')，支持多语言混合识别
            inpaint (bool, optional): 是否启用图像去除检测位置，默认False
        """
        # 开始识别 ocr ja true true
        result = detect_recognize(
            image_cv, lang=lang, detect=detect, classify=classify, inpaint=inpaint
        )
        results = result["results"]
        # 循环修改results中的每个元素
        for i in range(len(results)):
            resultOne = results[i]
            resultOne["box"] = resultOne["box"].tolist()
            # numpy.float32转float
            resultOne["score"] = float(resultOne["score"])
        return result
    def segment_layout(self,image_cv: any, detect: bool, classify: bool, lang: str, inpaint=False):
        """执行文字识别/分栏分段"""
        result = self.recognize(image_cv, detect, classify, lang, inpaint=inpaint)
        results = result["results"]
        if len(results) > 0:
            result["results"] = segment_engine.run(results)
        return result

    def layout(self,image_cv: any):
        """版面分析"""
        boxes, scores, class_names, elapse = get_layout_engine().check(image_cv)
        return boxes, scores, class_names, elapse


    async def recognize_all(self,image_cv: any, detect: bool, classify: bool, lang: str, inpaint=False):
        """执行文字识别/分栏分段/版面分析"""
        # 1 文字识别+分栏分段
        result = self.segment_layout(image_cv, detect, classify, lang, inpaint=inpaint)
        boxes, scores, class_names, elapse = get_layout_engine().check(image_cv)
        layout = []
        i = 0
        for class_name in class_names:
            # 如果是图片、表格或目录，则将bbox添加到结果中
            if (
                class_name == "Title"
                or class_name == "Figure"
                or class_name == "Table"
                or class_name == "Toc"
            ):
                layout.append(boxes[i].tolist())
            i = i + 1
        result["layout"] = layout
        return result
