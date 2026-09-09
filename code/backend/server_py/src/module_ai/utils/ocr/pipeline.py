"""OCR 识别流水线: 检测(detect) -> 方向分类(classify) -> 识别(recognize) -> (可选)文字消除(inpaint)

模型加载策略:
    - onnx 子模型按 (step, name) 全局缓存(lru_cache), 同名配置只加载一次
    - 语言级流水线按语言代码懒加载并缓存; 首次调用 detect_recognize 才加载,
      不再在模块导入时加载全部语言模型
"""
import copy

import numpy as np
from functools import lru_cache

from module_ai.config.ocr import get_ocr_languages, get_ocr_models, get_ocr_ort
from module_ai.utils.ocr.classify import TextClassifier
from module_ai.utils.ocr.common import Ticker, get_rotate_crop_image
from module_ai.utils.ocr.detect import TextDetector
from module_ai.utils.ocr.inpaint.simple_cv import simple_inpaint
from module_ai.utils.ocr.recognize import TextRecognizer

# 低置信度文本的重试裁剪参数组 [x倍数, y倍数, x边距, y边距]
RETRY_PARAMS = [
    [-0.25, -0.2, 0.02, 0.02],
    [0.1, 0.05, 0.02, 0.02],
    [0.0, 0.05, 0.1, 0.1],
]

# 流水线内语言实例缓存 {lang: RapidOCR}
_pipelines: dict[str, "RapidOCR"] = {}


@lru_cache(maxsize=None)
def load_onnx_model(step: str, name: str):
    """按配置节与名称加载 onnx 子模型并全局缓存

    :param step: 模型步骤(detect/classify/recognize)
    :param name: conf_ocr_models[step] 下的模型配置名
    """
    model_config = get_ocr_models()[step][name]
    model_class = {
        "detect": TextDetector,
        "classify": TextClassifier,
        "recognize": TextRecognizer,
    }[step]
    return model_class(model_config["path"], model_config.get("config"))


def get_ocr_pipeline(lang: str = "ch") -> "RapidOCR":
    """按语言获取(懒加载)OCR 流水线实例

    :param lang: 语言代码, 对应 ocr.languages 配置节
    """
    if lang not in _pipelines:
        models = get_ocr_languages()[lang]
        _pipelines[lang] = RapidOCR(models)
    return _pipelines[lang]


def detect_recognize(image, lang: str = "ch", detect: bool = True, classify: bool = True, inpaint: bool = False):
    """执行完整 OCR 识别(原 main.py 门面函数, 懒加载语言模型)

    :return: {"ts": 各阶段耗时, "results": 识别结果, "background": 去文字背景图}
    """
    model = get_ocr_pipeline(lang)
    results, ts, background = model(image, detect=detect, classify=classify, inpaint=inpaint)
    ts["total"] = sum(ts.values())
    return {"ts": ts, "results": results, "background": background}


class RapidOCR:
    """OCR 流水线编排: 组合检测/分类/识别三个子模型完成端到端识别"""

    def __init__(self, config: dict):
        """
        :param config: 语言配置 {"config": {text_score, min_height}, "models": {detect, classify, recognize}}
        """
        self.config = config
        self.text_score = config["config"]["text_score"]
        self.min_height = config["config"]["min_height"]

        models = config["models"]
        self.text_detector = load_onnx_model("detect", models["detect"])
        self.text_recognizer = load_onnx_model("recognize", models["recognize"])
        self.text_cls = load_onnx_model("classify", models["classify"])

    def __call__(self, img: np.ndarray, detect: bool = True, classify: bool = True, inpaint: bool = False):
        """执行端到端识别

        :param img: BGR 图像数组
        :param detect: 是否启用文本检测(否则整图作为单文本行识别)
        :param classify: 是否启用方向分类校正
        :param inpaint: 是否对识别区域做修复, 返回去除文字的背景图
        :return: (results: [{box, text, score}], 耗时字典, 背景图或 None)
        """
        background = None
        ticker = Ticker()
        h, w = img.shape[:2]
        if not detect or h < self.min_height:
            # 整图直接识别(小图/关闭检测)
            dt_boxes, img_crop_list = self.get_boxes_img_without_det(img, h, w)
            ticker.tick("detect")
        else:
            dt_boxes = self.text_detector(img)
            ticker.tick("detect")
            if dt_boxes is None or len(dt_boxes) < 1:
                return [], ticker.maps, None

            dt_boxes = self.sorted_boxes(dt_boxes)
            img_crop_list = self.get_crop_img_list(img, dt_boxes)
            ticker.tick("post-detect")

        if classify:
            # 子图方向校正
            img_crop_list, _ = self.text_cls(img_crop_list)
            ticker.tick("classify")
            if get_ocr_ort().get("verbose", False):
                print(f"cls num: {len(img_crop_list)}")

        # 批量识别 + 低置信度重试
        recog_result = self.text_recognizer(img_crop_list)
        self.retry_text_recognizer(img, dt_boxes, recog_result)
        ticker.tick("recognize")

        results, boxs_ok = self.filter_boxes_rec_by_score(dt_boxes, recog_result)

        if inpaint:
            background = simple_inpaint(copy.deepcopy(img), boxs_ok)
        ticker.tick("post-recognize")
        return results, ticker.maps, background

    @staticmethod
    def get_boxes_img_without_det(img, h, w):
        """不启用检测时, 将整图构造为唯一文本框"""
        dt_boxes = np.array([[0, 0], [w, 0], [w, h], [0, h]])[np.newaxis, ...]
        return dt_boxes, [img]

    @staticmethod
    def get_crop_img_list(img, dt_boxes) -> list[np.ndarray]:
        """按检测框批量裁剪文本子图"""
        return [get_rotate_crop_image(img, copy.deepcopy(box)) for box in dt_boxes]

    @staticmethod
    def sorted_boxes(dt_boxes):
        """对检测结果排序: 从上到下、从左到右

        y 差距小于 10px 视为同一行, 行内按 x 排序
        """

        class AlignBox:
            def __init__(self, data) -> None:
                self.data = data
                self.x = data[0][0]
                self.y = data[0][1]

            def __lt__(self, other: "AlignBox"):
                dy = self.y - other.y
                if abs(dy) < 10:
                    return self.x < other.x
                return dy < 0

        return [b.data for b in sorted(AlignBox(b) for b in dt_boxes)]

    def filter_boxes_rec_by_score(self, dt_boxes, rec_res):
        """按置信度阈值过滤识别结果

        :return: (结果列表 [{box, text, score}], 过滤后的框列表)
        """
        results = []
        boxs = []
        for box, (text, score) in zip(dt_boxes, rec_res):
            if score >= self.text_score:
                results.append({"box": box, "text": text, "score": score})
                boxs.append(box)
        return results, boxs

    def retry_text_recognizer(self, img, dt_boxes, recog_result):
        """低置信度(<0.97)文本图按扩展参数组重新裁剪识别, 保留置信度更高的结果"""
        retry_index = [i for i, result in enumerate(recog_result) if result[1] <= 0.97]
        if not retry_index:
            return
        # 每组重试参数 × 每张低置信度图, 合并为一个批次
        retry_imgs = []
        for params_retry in RETRY_PARAMS:
            for index in retry_index:
                retry_imgs.append(get_rotate_crop_image(img, dt_boxes[index], params_retry))
        # 方向校正后重新识别
        retry_imgs, _ = self.text_cls(retry_imgs)
        new_result = self.text_recognizer(retry_imgs)
        # 逐组比较, 置信度更高则替换
        for i, result in enumerate(new_result):
            index = retry_index[i % len(retry_index)]
            if result[1] > recog_result[index][1]:
                recog_result[index] = result
