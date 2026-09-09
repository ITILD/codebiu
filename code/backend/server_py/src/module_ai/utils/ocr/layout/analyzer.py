import time
from pathlib import Path

import numpy as np

from .utils import (
    LoadImage,
    OrtInferSession,
    YOLOv8PostProcess,
    YOLOv8PreProcess,
    # get_logger,
)
import logging
logger = logging.getLogger(__name__)
# ROOT_URL = "https://github.com/RapidAI/RapidLayout/releases/download/v0.0.0/"
# KEY_TO_MODEL_URL = {
#     "pp_layout_cdla": f"{ROOT_URL}/layout_cdla.onnx",
#     "pp_layout_publaynet": f"{ROOT_URL}/layout_publaynet.onnx",
#     "pp_layout_table": f"{ROOT_URL}/layout_table.onnx",
#     "yolov8n_layout_paper": f"{ROOT_URL}/yolov8n_layout_paper.onnx",
#     "yolov8n_layout_report": f"{ROOT_URL}/yolov8n_layout_report.onnx",
#     "yolov8n_layout_publaynet": f"{ROOT_URL}/yolov8n_layout_publaynet.onnx",
#     "yolov8n_layout_general6": f"{ROOT_URL}/yolov8n_layout_general6.onnx",
# }


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
            raise ValueError(f"iou_thres {conf_thres} is outside of range [0, 1]")

        config = {
            "model_path": model_path,
            "use_cuda": use_cuda,
            "use_dml": use_dml,
        }
        self.session = OrtInferSession(config)
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
