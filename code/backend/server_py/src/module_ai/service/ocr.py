from module_ai.utils.onnx.ocr_rapid.rapidocr.main import detect_recognize

from module_ai.utils.onnx.ocr_rapid.rapid_layout import RapidLayout
from module_ai.utils.onnx.ocr_rapid.tbpu.parser_multi_para import MultiPara

from module_ai.config.ocr import path_lout_model

tupu_use = MultiPara()
layout_engine = RapidLayout(model_path=path_lout_model)

class OcrService:
    def ocr(self,image_cv: any, detect: bool, classify: bool, lang: str, inpaint=False):
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
    def ocr_tupu(self,image_cv: any, detect: bool, classify: bool, lang: str, inpaint=False):
        """执行文字识别/分栏分段"""
        result = self.ocr(image_cv, detect, classify, lang, inpaint=inpaint)
        results = result["results"]
        if len(results) > 0:
            result["results"] = tupu_use.run(results)
        return result

    def layout(self,image_cv: any):
        """版面分析"""
        boxes, scores, class_names, elapse = layout_engine.check(image_cv)
        return boxes, scores, class_names, elapse


    async def ocr_all(self,image_cv: any, detect: bool, classify: bool, lang: str, inpaint=False):
        """执行文字识别/分栏分段/版面分析"""
        # 1 ocr_tupu
        result = self.ocr_tupu(image_cv, detect, classify, lang, inpaint=inpaint)
        boxes, scores, class_names, elapse = layout_engine.check(image_cv)
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
