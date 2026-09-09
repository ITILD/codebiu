"""OCR 公共工具: 图像裁剪/归一化/可视化/计时"""
import copy
import json
import math
import time

import cv2
import numpy as np


def resize_norm_img(img: np.ndarray, img_w: int, img_h: int, img_c: int) -> np.ndarray:
    """图像预处理归一化: 保持宽高比缩放 + 像素归一化[-1,1] + HWC->CHW + 右侧填充

    :param img: 输入图像 (h, w, c)
    :param img_w/img_h/img_c: 目标宽/高/通道数(网络输入要求)
    :return: (img_c, img_h, img_w) float32
    """
    h, w = img.shape[:2]
    ratio = w / float(h)
    # 按目标高度等比缩放, 超宽时截断到目标宽度
    resized_w = img_w if math.ceil(img_h * ratio) > img_w else int(math.ceil(img_h * ratio))
    resized_image = cv2.resize(img, (resized_w, img_h))
    resized_image = resized_image.astype("float32")
    # HWC -> CHW, 归一化 [0,1] -> [-1,1]
    resized_image = resized_image.transpose((2, 0, 1)) / 255
    resized_image -= 0.5
    resized_image /= 0.5
    padding_im = np.zeros((img_c, img_h, img_w), dtype=np.float32)
    padding_im[:, :, :resized_w] = resized_image
    return padding_im


def get_rotate_crop_image(img: np.ndarray, points, params_retry=None) -> np.ndarray:
    """根据文本框四点定义, 通过透视变换从原图中截取标准长方形文本图

    :param img: 原图
    :param points: 四点文本框 [4, 2]
    :param params_retry: 重试扩展参数 [x倍数, y倍数, x边距, y边距], 用于低置信度区域的扩展裁剪
    :return: 裁剪后的文本图(竖排文本自动转横排)
    """
    points = np.array(points, dtype=np.float32, copy=True)
    # 重试模式: 按文本框高度比例向四周扩展, 提高识别容错
    if params_retry:
        crop_height = int(
            max(
                np.linalg.norm(points[0] - points[3]),
                np.linalg.norm(points[1] - points[2]),
            )
        )
        add_x = crop_height * params_retry[0]
        add_y = crop_height * params_retry[1]
        pad_x = int(crop_height * params_retry[2])
        pad_y = int(crop_height * params_retry[3])
        points[0] += [-add_x + crop_height * 0.02, -add_y]
        points[1] += [add_x + crop_height * 0.04, -add_y]
        points[2] += [add_x + crop_height * 0.04, add_y]
        points[3] += [-add_x + crop_height * 0.02, add_y]

    crop_width = int(
        max(
            np.linalg.norm(points[0] - points[1]),
            np.linalg.norm(points[2] - points[3]),
        )
    )
    crop_height = int(
        max(
            np.linalg.norm(points[0] - points[3]),
            np.linalg.norm(points[1] - points[2]),
        )
    )
    pts_std = np.float32(
        [[0, 0], [crop_width, 0], [crop_width, crop_height], [0, crop_height]]
    )
    transform = cv2.getPerspectiveTransform(points, pts_std)
    dst_img = cv2.warpPerspective(
        img,
        transform,
        (crop_width, crop_height),
        borderMode=cv2.BORDER_REPLICATE,
        flags=cv2.INTER_CUBIC,
    )
    # 重试模式: 扩展区域用白边补齐
    if params_retry:
        dst_img = cv2.copyMakeBorder(
            dst_img, pad_y, pad_y, pad_x, pad_x,
            cv2.BORDER_CONSTANT, value=(255, 255, 255),
        )

    dst_height, dst_width = dst_img.shape[:2]
    # 高>1.5*宽 时视为竖排文本, 旋转为横排
    if dst_height * 1.0 / dst_width >= 1.5:
        dst_img = np.rot90(dst_img)
    return dst_img


def check_and_read_gif(img_path) -> np.ndarray | None:
    """GIF 图像读取: 取第一帧转为 BGR 数组; 非 GIF 返回 None"""
    if str(img_path).lower().endswith(".gif"):
        gif = cv2.VideoCapture(str(img_path))
        ret, frame = gif.read()
        if not ret:
            return None
        if len(frame.shape) == 2 or frame.shape[-1] == 1:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        return frame[:, :, ::-1]
    return None


def draw_text_det_res(dt_boxes, raw_im: np.ndarray) -> np.ndarray:
    """在原图上绘制检测框(调试可视化用)"""
    src_im = copy.deepcopy(raw_im)
    for i, box in enumerate(dt_boxes):
        box = np.array(box).astype(np.int32).reshape(-1, 2)
        cv2.polylines(src_im, [box], True, color=(0, 0, 255), thickness=1)
        cv2.putText(
            src_im, str(i),
            (int(box[0][0]), int(box[0][1])),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2,
        )
    return src_im


class Ticker:
    """流水线分步计时器: tick 记录各阶段耗时, reset=False 时累计"""

    def __init__(self, reset: bool = True) -> None:
        self.ts = time.perf_counter()
        self.reset = reset
        self.maps: dict[str, float] = {}

    def tick(self, name: str, reset: bool | None = None) -> float:
        ts = time.perf_counter()
        if reset is None:
            reset = self.reset
        dt = ts - self.ts
        if reset:
            self.ts = ts
        self.maps[name] = dt
        return dt


def tojson(obj, **kws) -> str:
    """JSON 序列化, 自动处理 numpy 数组"""
    return json.dumps(obj, default=lambda o: o.tolist() if hasattr(o, "tolist") else o,
                      ensure_ascii=False, **kws)
