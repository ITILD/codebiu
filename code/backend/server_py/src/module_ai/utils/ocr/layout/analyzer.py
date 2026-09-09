"""版面分析(layout)子包: YOLOv8 检测文档区域类型(标题/图片/表格/目录等)"""
import time
from pathlib import Path

import numpy as np

from module_ai.utils.ocr.runtime import OrtInferSession
from .utils import (
    LoadImage,
    YOLOv8PostProcess,
    YOLOv8PreProcess,
)
import logging
logger = logging.getLogger(__name__)


class RapidLayout:
    def __init__(
        self,
        model_path: str | Path | None = None,
        conf_thres: float = 0.5,
        iou_thres: float = 0.5,
        use_cuda: bool = False,
        use_dml: bool = False,
    ):
        if not self.check_of(conf_thres):
            raise ValueError(f"conf_thres {conf_thres} is outside of range [0, 1]")

        if not self.check_of(iou_thres):
            raise ValueError(f"iou_thres {iou_thres} is outside of range [0, 1]")

        # 会话创建与设备切换统一由 runtime 管理(use_dml 由全局配置决定)
        self.session = OrtInferSession(str(model_path), use_cuda=use_cuda)
        labels = self.session.get_character_list()
        logger.info("%s contains %s", model_path, labels)

        # yolov8
        self.yolov8_input_shape = (640, 640)
        self.yolov8_preprocess = YOLOv8PreProcess(img_size=self.yolov8_input_shape)
        self.yolov8_postprocess = YOLOv8PostProcess(labels, conf_thres, iou_thres)

        self.load_img = LoadImage()

    def check(
        self, img_content: str | np.ndarray | bytes | Path
    ) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None, float]:
        img = self.load_img(img_content)
        ori_img_shape = img.shape[:2]
        # return self.pp_layout(img, ori_img_shape)
        return self.yolov8_layout(img, ori_img_shape)

    def yolov8_layout(self, img: np.ndarray, ori_img_shape: tuple[int, int]):
        s_time = time.time()

        input_tensor = self.yolov8_preprocess(img)
        outputs = self.session(input_tensor)
        boxes, scores, class_names = self.yolov8_postprocess(
            outputs, ori_img_shape, self.yolov8_input_shape
        )
        elapse = time.time() - s_time
        return boxes, scores, class_names, elapse

    @staticmethod
    def check_of(thres: float) -> bool:
        if 0 <= thres <= 1.0:
            return True
        return False
