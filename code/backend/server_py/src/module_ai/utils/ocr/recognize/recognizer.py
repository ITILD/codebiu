"""CRNN 文本识别器: 将文本图批量识别为文字"""
import json

import numpy as np

from module_ai.utils.ocr.common import resize_norm_img
from module_ai.utils.ocr.runtime import OrtInferSession
from .ctc_decode import CTCLabelDecode


class TextRecognizer:
    """文本识别器类，使用ONNX模型进行OCR识别"""
    
    def __init__(self, path, config):
        """
        初始化文本识别器
        
        Args:
            path: ONNX模型文件路径
            config: 配置参数
        """
        self.rec_batch_num = config.get("rec_batch_num", 1)  # 批处理大小
        session_instance = OrtInferSession(path)
        self.session = session_instance.session  # ONNX推理会话

        # 获取模型元数据
        metamap = session_instance.session.get_modelmeta().custom_metadata_map

        # 从模型元数据中加载字符字典
        chars = metamap["dictionary"].splitlines()
        # 字符集
        self.postprocess_op = CTCLabelDecode(chars)  # 创建CTC解码器
        self.rec_image_shape = json.loads(metamap["shape"])  # 图像输入形状
        self.input_name = session_instance.get_input_name()  # 模型输入名称

    def __call__(self, img_list: list[np.ndarray]):
        """
        执行文本识别
        
        Args:
            img_list: 图像列表，每个图像为numpy数组
            
        Returns:
            识别结果列表，每个元素包含识别文本和置信度
        """
        if isinstance(img_list, np.ndarray):
            img_list = [img_list]  # 如果是单个图像，转换为列表

        # 计算所有文本条的宽高比
        width_list = [img.shape[1] / float(img.shape[0]) for img in img_list]

        # 按宽高比排序，可以加速识别过程
        indices = np.argsort(np.array(width_list))

        img_num = len(img_list)
        rec_res = [["", 0.0]] * img_num  # 初始化结果列表

        batch_num = self.rec_batch_num
        # 分批处理图像
        for beg_img_no in range(0, img_num, batch_num):
            end_img_no = min(img_num, beg_img_no + batch_num)
            max_wh_ratio = 0
            # 计算当前批次的最大宽高比
            for ino in range(beg_img_no, end_img_no):
                h, w = img_list[indices[ino]].shape[0:2]
                wh_ratio = w * 1.0 / h
                max_wh_ratio = max(max_wh_ratio, wh_ratio)

            norm_img_batch = []
            # 对当前批次图像进行归一化处理
            for ino in range(beg_img_no, end_img_no):
                img_c, img_h, img_w = self.rec_image_shape
                # 根据最大宽高比动态计算新宽度(基准高度32像素)解决文本行长度不一致的问题
                img_w = int((32 * max_wh_ratio))
                # 强制固定高度，用于批量处理和标准OCR模型
                norm_img = resize_norm_img(img_list[indices[ino]], img_w, img_h, img_c)
                norm_img_batch.append(norm_img[np.newaxis, :])
            norm_img_batch = np.concatenate(norm_img_batch).astype(np.float32)

            # 执行ONNX模型推理
            onnx_inputs = {self.input_name: norm_img_batch}
            preds = self.session.run(None, onnx_inputs)[0]
            rec_result = self.postprocess_op(preds)  # 对预测结果进行CTC解码

            # 将结果存储到正确的位置
            for rno in range(len(rec_result)):
                rec_res[indices[beg_img_no + rno]] = rec_result[rno]
        return rec_res
