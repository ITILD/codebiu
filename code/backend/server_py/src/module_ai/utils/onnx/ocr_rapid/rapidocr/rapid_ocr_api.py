import copy

import cv2
import numpy as np

from functools import lru_cache
from module_ai.config.ocr import conf_ocr_models,conf_ocr_ort
from module_ai.utils.onnx.ocr_rapid.text_inpaint.simple_cv import simple_inpaint
from module_ai.utils.onnx.ocr_rapid.utils import Ticker
from .classify import TextClassifier
from .detect import TextDetector
from .recognize import TextRecognizer


def get_rotate_crop_image(img, points, params_retry=None):
    """根据box定义, 从图像中截取相应的部分, 通过透视变换转换为标准长方形图像"""
    # 新参数检测
    if params_retry:
        img_crop_height = int(
            max(
                np.linalg.norm(points[0] - points[3]),
                np.linalg.norm(points[1] - points[2]),
            )
        )
        # 0.045
        # 0.02
        # 0.1
        #  0.01
        # x方向倍数
        tempAddX = img_crop_height * params_retry[0]
        tempAddY = img_crop_height * params_retry[1]
        paddingX = int(img_crop_height * params_retry[2])
        paddingY = int(img_crop_height * params_retry[3])
        points[0][0] = points[0][0] - tempAddX + img_crop_height * 0.02
        points[0][1] = points[0][1] - tempAddY
        points[1][0] = points[1][0] + tempAddX + img_crop_height * 0.04
        points[1][1] = points[1][1] - tempAddY
        points[2][0] = points[2][0] + tempAddX + img_crop_height * 0.04
        points[2][1] = points[2][1] + tempAddY
        points[3][0] = points[3][0] - tempAddX + img_crop_height * 0.02
        points[3][1] = points[3][1] + tempAddY
        points = np.float32(points)

    img_crop_width = int(
        max(
            np.linalg.norm(points[0] - points[1]),
            np.linalg.norm(points[2] - points[3]),
        )
    )
    img_crop_height = int(
        max(
            np.linalg.norm(points[0] - points[3]),
            np.linalg.norm(points[1] - points[2]),
        )
    )
    pts_std = np.float32(
        [
            [0, 0],
            [img_crop_width, 0],
            [img_crop_width, img_crop_height],
            [0, img_crop_height],
        ]
    )
    # 最终检测单句
    transform = cv2.getPerspectiveTransform(points, pts_std)
    dst_img = cv2.warpPerspective(
        img,
        transform,
        (img_crop_width, img_crop_height),
        borderMode=cv2.BORDER_REPLICATE,
        flags=cv2.INTER_CUBIC,
    )

    # 弹窗展示dst_img图片
    if params_retry:
        dst_img = cv2.copyMakeBorder(
            dst_img,
            paddingY,
            paddingY,
            paddingX,
            paddingX,
            cv2.BORDER_CONSTANT,
            value=(255, 255, 255),
        )
    # debug
    # cv2.imshow('Image1', img)
    # 过程图片
    # cv2.imshow('Image', dst_img)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    dst_img_height, dst_img_width = dst_img.shape[:2]
    # 将竖向的文字方向转为横向, 仅当 高>1.5*宽 时进行转换
    if dst_img_height * 1.0 / dst_img_width >= 1.5:
        dst_img = np.rot90(dst_img)
    return dst_img


@lru_cache(maxsize=None)
def load_onnx_model(step, name):
    model_config = conf_ocr_models[step][name]
    model_class = {
        "detect": TextDetector,
        "classify": TextClassifier,
        "recognize": TextRecognizer,
    }[step]
    return model_class(model_config["path"], model_config.get("config"))


class RapidOCR:
    def __init__(self, config):
        super(RapidOCR).__init__()
        self.config = config
        self.text_score = config["config"]["text_score"]
        self.min_height = config["config"]["min_height"]

        models = config["models"]
        self.text_detector = load_onnx_model("detect", models["detect"])
        self.text_recognizer = load_onnx_model("recognize", models["recognize"])
        self.text_cls = load_onnx_model("classify", models["classify"])
        # [xadd, yadd, xpadd,ypadd]
        self.text_recognizer_params = [
            [-0.25, -0.2, 0.02, 0.02],
            [0.1, 0.05, 0.02, 0.02],
            [0.0, 0.05, 0.1, 0.1],
        ]
        # shi用参数标记
        self.text_recognizer_params_index = 0

    def __call__(self, img: np.ndarray, detect=True, classify=True, inpaint=False):
        background = None
        self.text_recognizer_params_index = 0
        ticker = Ticker()
        h, w = img.shape[:2]
        if not detect or h < self.min_height:
            dt_boxes, img_crop_list = self.get_boxes_img_without_det(img, h, w)
            ticker.tick("detect")
        else:
            dt_boxes = self.text_detector(img)
            ticker.tick("detect")
            if dt_boxes is None or len(dt_boxes) < 1:
                return [], ticker.maps
            # if conf["global"]["verbose"]:
            #     print(f"boxes num: {len(dt_boxes)}")

            dt_boxes = self.sorted_boxes(dt_boxes)
            img_crop_list = self.get_crop_img_list(img, dt_boxes)
            ticker.tick("post-detect")

        if classify:
            # 进行子图像角度修正
            img_crop_list, _ = self.text_cls(img_crop_list)
            ticker.tick("classify")
            if conf_ocr_ort["verbose"]:
                print(f"cls num: {len(img_crop_list)}")
        # 2
        recog_result = self.text_recognizer(img_crop_list)
        # 新参数识别start
        self.retry_text_recognizer(
            img,
            dt_boxes,
            recog_result,
        )
        self.text_recognizer_params_index = 0
        # end
        ticker.tick("recognize")
        results, boxs_ok = self.filter_boxes_rec_by_score(dt_boxes, recog_result)

        # 去除文字返回背景
        # 深拷贝img
        img_bg = copy.deepcopy(img)
        if inpaint:
            background = simple_inpaint(img_bg, boxs_ok)
            # image = cv2.imencode(".jpg", background)[1]
            # background = str(base64.b64encode(image))[2:-1]
            # 转base64
            # background = base64.b64encode(background).decode()

        ticker.tick("post-recognize")
        return results, ticker.maps, background

    def get_boxes_img_without_det(self, img, h, w):
        x0, y0, x1, y1 = 0, 0, w, h
        dt_boxes = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
        dt_boxes = dt_boxes[np.newaxis, ...]
        img_crop_list = [img]
        return dt_boxes, img_crop_list

    def get_crop_img_list(self, img, dt_boxes):
        img_crop_list = []
        for box in dt_boxes:
            tmp_box = copy.deepcopy(box)
            img_crop = get_rotate_crop_image(img, tmp_box)
            img_crop_list.append(img_crop)
        return img_crop_list

    @staticmethod
    def sorted_boxes(dt_boxes):
        """对文本框检测结果进行排序, 调整为从上到下、从左到右

        args:
            dt_boxes(array): detected text boxes with shape [4, 2]
        return:
            sorted boxes(array) with shape [4, 2]
        """

        class AlignBox:
            def __init__(self, data) -> None:
                self.data = data
                self.x = data[0][0]
                self.y = data[0][1]

            def __lt__(self, other: "AlignBox"):
                dy = self.y - other.y
                # y差距小于10, 视为相等, 根据x排序
                if abs(dy) < 10:
                    return self.x < other.x
                # 否则根据y排序
                return dy < 0

        align_boxes = sorted([AlignBox(b) for b in dt_boxes])
        return [b.data for b in align_boxes]

    def filter_boxes_rec_by_score(self, dt_boxes, rec_res):
        results = []
        boxs = []
        for box, rec_reuslt in zip(dt_boxes, rec_res):
            text, score = rec_reuslt
            if score >= self.text_score:
                results.append({"box": box, "text": text, "score": score})
                boxs.append(box)
        return results, boxs

    def retry_text_recognizer(self, img, dt_boxes, recog_result):
        # 如果置信度低于0.95，则重新设置多组参数识别
        retryIndexArr = []
        # 所有重检测图像 text_recognizer_params数*imgs数
        retryImgsArr = []
        # 循环recog_result 置信度不合格的添加到retryArrDict
        for i, result in enumerate(recog_result):
            if result[1] <= 0.97:
                retryIndexArr.append(i)
        retryIndexArrLen = len(retryIndexArr)
        # 置信度都合格返回
        if len(retryIndexArr) == 0:
            return
        else:
            # 循环多参数,放入同一批次检测第二遍  参数*置信度不足图像
            for params_retry in self.text_recognizer_params:
                for index in retryIndexArr:
                    tmp_box = copy.deepcopy(dt_boxes[index])
                    img_crop = get_rotate_crop_image(img, tmp_box, params_retry)
                    retryImgsArr.append(img_crop)
            # 方向改正
            img_crop_list_new, _ = self.text_cls(retryImgsArr)
            # 字符检测
            recog_result_new = self.text_recognizer(img_crop_list_new)
            # 检测结果比较取置信度最高值
            for i, result in enumerate(recog_result_new):
                recog_result_new_this = recog_result_new[i]
                index = i % retryIndexArrLen
                recog_result_old_this = recog_result[retryIndexArr[index]]
                # 如果新识别的置信度比旧的高，则替换
                if recog_result_new_this[1] > recog_result_old_this[1]:
                    recog_result[retryIndexArr[index]] = recog_result_new_this
