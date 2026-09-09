"""DBNet 文本检测后处理: 概率图 -> 二值化 -> 轮廓提取 -> 文本框"""
import cv2
import numpy as np
from pyclipper import PyclipperOffset, JT_ROUND, ET_CLOSEDPOLYGON
from shapely.geometry import Polygon


class DBPostProcess:
    """Differentiable Binarization (DB) 检测后处理

    :param thresh: 二值化阈值
    :param box_thresh: 文本框得分阈值
    :param max_candidates: 最大候选轮廓数
    :param unclip_ratio: 文本框外扩比例
    :param use_dilation: 是否对二值图做膨胀
    """

    def __init__(
        self,
        thresh: float = 0.3,
        box_thresh: float = 0.7,
        max_candidates: int = 9999,
        unclip_ratio: float = 2.0,
        use_dilation: bool = False,
    ):
        self.thresh = thresh
        self.box_thresh = box_thresh
        self.max_candidates = max_candidates
        self.unclip_ratio = unclip_ratio
        self.min_size = 3
        self.dilation_kernel = np.array([[1, 1], [1, 1]]) if use_dilation else None

    def __call__(self, pred: np.ndarray, shape_list: np.ndarray) -> list[dict]:
        """概率图批处理后处理

        :param pred: 模型概率输出 (batch, 1, H, W)
        :param shape_list: 每个样本的 (src_h, src_w, ratio_h, ratio_w)
        :return: [{"points": 文本框数组}, ...]
        """
        pred = pred[:, 0, :, :]
        segmentation = pred > self.thresh

        boxes_batch = []
        for batch_index in range(pred.shape[0]):
            src_h, src_w, _, _ = shape_list[batch_index]
            if self.dilation_kernel is not None:
                mask = cv2.dilate(
                    np.array(segmentation[batch_index]).astype(np.uint8),
                    self.dilation_kernel,
                )
            else:
                mask = segmentation[batch_index]
            boxes, _ = self.boxes_from_bitmap(pred[batch_index], mask, src_w, src_h)
            boxes_batch.append({"points": boxes})
        return boxes_batch

    def boxes_from_bitmap(self, pred, bitmap, dest_width, dest_height):
        """从二值图提取文本框并映射回原图坐标"""
        bitmap = bitmap
        height, width = bitmap.shape

        outs = cv2.findContours(
            (bitmap * 255).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
        )
        if len(outs) == 3:
            contours = outs[1]
        else:
            contours = outs[0]

        num_contours = min(len(contours), self.max_candidates)

        boxes = []
        scores = []
        for index in range(num_contours):
            contour = contours[index]
            points, sside = self.get_mini_boxes(contour)
            if sside < self.min_size:
                continue
            points = np.array(points)
            score = self.box_score_fast(pred, points.reshape(-1, 2))
            if self.box_thresh > score:
                continue

            box = self.unclip(points).reshape(-1, 1, 2)
            box, sside = self.get_mini_boxes(box)
            if sside < self.min_size + 2:
                continue
            box = np.array(box)

            box[:, 0] = np.clip(np.round(box[:, 0] / width * dest_width), 0, dest_width)
            box[:, 1] = np.clip(np.round(box[:, 1] / height * dest_height), 0, dest_height)
            boxes.append(box.astype(np.int16))
            scores.append(score)
        return np.array(boxes, dtype=np.int16), scores

    def unclip(self, box):
        """按 unclip_ratio 外扩文本框多边形"""
        distance = Polygon(box).area * self.unclip_ratio / Polygon(box).length
        offset = PyclipperOffset()
        offset.AddPath(box, JT_ROUND, ET_CLOSEDPOLYGON)
        return np.array(offset.Execute(distance))

    def get_mini_boxes(self, contour):
        """最小面积外接矩形 -> 按顺时针排列的四个顶点"""
        bounding_box = cv2.minAreaRect(contour)
        points = sorted(list(cv2.boxPoints(bounding_box)), key=lambda x: x[0])

        index_1, index_2, index_3, index_4 = 0, 1, 2, 3
        if points[1][1] > points[0][1]:
            index_1, index_4 = 0, 1
        else:
            index_1, index_4 = 1, 0
        if points[3][1] > points[2][1]:
            index_2, index_3 = 2, 3
        else:
            index_2, index_3 = 3, 2

        box = [points[index_1], points[index_2], points[index_3], points[index_4]]
        return box, min(bounding_box[1])

    def box_score_fast(self, bitmap, box):
        """计算文本框区域内的平均得分"""
        h, w = bitmap.shape[:2]
        box = box.copy()
        xmin = np.clip(np.floor(box[:, 0].min()).astype(int), 0, w - 1)
        xmax = np.clip(np.ceil(box[:, 0].max()).astype(int), 0, w - 1)
        ymin = np.clip(np.floor(box[:, 1].min()).astype(int), 0, h - 1)
        ymax = np.clip(np.ceil(box[:, 1].max()).astype(int), 0, h - 1)

        mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
        box[:, 0] = box[:, 0] - xmin
        box[:, 1] = box[:, 1] - ymin
        cv2.fillPoly(mask, box.reshape(1, -1, 2).astype(np.int32), 1)
        return cv2.mean(bitmap[ymin: ymax + 1, xmin: xmax + 1], mask)[0]
