import base64
import math
import cv2
from cv2 import Mat
import numpy as np


# from fastapi import (UploadFile)
def bytes_to_cv2(image_bytes: bytes) -> Mat:
    """将字节流转换为cv2格式"""
    image_np = np.frombuffer(image_bytes, np.uint8)
    image_cv: Mat = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
    return image_cv


def cv2_to_base64(image_cv):
    """将cv2格式转换为base64"""
    image_bytes = image_cv.tobytes()
    # 将字节编码为base64
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    return base64_image


def resize_norm_img(img, img_w, img_h, img_c):
    """
    对输入图像进行缩放、归一化和填充处理，以便符合特定的网络输入要求
    标准化预处理，包括：
    1. 保持宽高比的缩放
    2. 像素值归一化
    3. 通道顺序调整
    4. 边缘填充

    参数：
        img: 输入图像，形状为 (height, width, channels)
        img_w: 目标宽度（网络输入要求）
        img_h: 目标高度（网络输入要求）
        img_c: 目标通道数（网络输入要求）

    返回：
        预处理后的图像，形状为 (channels, height, width)
    """
    h, w = img.shape[:2]
    ratio = w / float(h)
    # 确定缩放后的宽度
    if math.ceil(img_h * ratio) > img_w:
        resized_w = img_w
    else:
        resized_w = int(math.ceil(img_h * ratio))
    resized_image = cv2.resize(img, (resized_w, img_h))
    resized_image = resized_image.astype("float32")
    # 图像从 (height, width, channels) -> (channels, height, width)输入格式(符合pytorch等框架输入
    # 像素值归一化 [0, 1] 。
    resized_image = resized_image.transpose((2, 0, 1)) / 255
    # 像素值归一化 [0, 1] -> [-0.5, 0.5]-> [-1, 1]
    resized_image -= 0.5
    resized_image /= 0.5
    #
    padding_im = np.zeros((img_c, img_h, img_w), dtype=np.float32)
    padding_im[:, :, :resized_w] = resized_image
    return padding_im


# if __name__ == "__main__":
# img_data = base64.b64decode(image_base64)
# 读取图像数据
