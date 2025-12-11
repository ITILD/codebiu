import copy
import json
import cv2
import numpy as np
from common.utils.media.FileFormat import resize_norm_img
from module_ai.utils.onnx.ocr_rapid.utils import OrtInferSession


class ClsPostProcess:
    """
    文本方向分类后处理类 - 用于将分类模型的输出转换为文本标签
    在文本方向分类任务中，将预测结果转换为可读的标签
    """

    def __init__(self, label_list):
        """
        初始化分类后处理类
        
        Args:
            label_list: 标签列表，包含所有可能的分类标签
        """
        super(ClsPostProcess, self).__init__()
        self.label_list = label_list

    def __call__(self, preds, label=None):
        """
        执行分类结果后处理
        
        Args:
            preds: 模型预测结果，形状为 [batch_size, num_classes]
            label: 真实标签(可选)
            
        Returns:
            如果只提供了预测结果，则返回解码后的预测结果列表，每个元素为(标签, 置信度)
            如果同时提供了预测结果和真实标签，则返回(预测结果列表, 真实标签列表)
        """
        # 获取每个样本概率最大的类别索引
        pred_idxs = preds.argmax(axis=1)
        # 将索引转换为对应的标签和置信度
        decode_out = [
            (self.label_list[idx], preds[i, idx]) for i, idx in enumerate(pred_idxs)
        ]
        # 如果没有提供真实标签，只返回预测结果
        if label is None:
            return decode_out

        # 如果提供了真实标签，也将其转换为标签列表格式
        label = [(self.label_list[idx], 1.0) for idx in label]
        return decode_out, label


class TextClassifier:
    """
    文本方向分类器 - 用于检测OCR文本图像的方向，并根据需要进行旋转校正
    使用ONNX模型实现文本方向分类
    """
    
    def __init__(self, path, config):
        """
        初始化文本分类器
        
        Args:
            path: ONNX模型文件路径
            config: 配置参数字典，包含batch_size和score_thresh等参数
        """
        self.cls_batch_num = config["batch_size"]  # 批处理大小
        self.cls_thresh = config["score_thresh"]  # 分类阈值，用于确定是否旋转图像

        # 创建ONNX推理会话
        session_instance = OrtInferSession(path)
        self.session = session_instance.session
        # 获取模型元数据
        metamap = self.session.get_modelmeta().custom_metadata_map

        # 从元数据中获取图像输入形状
        self.cls_image_shape = json.loads(metamap["shape"])

        # 从元数据中获取标签列表并初始化后处理器
        labels = json.loads(metamap["labels"])
        self.postprocess_op = ClsPostProcess(labels)
        # 获取模型输入名称
        self.input_name = session_instance.get_input_name()

    def __call__(self, img_list: list[np.ndarray]):
        """
        执行文本方向分类和校正
        
        Args:
            img_list: 图像列表，每个图像为numpy数组
            
        Returns:
            tuple: (校正后的图像列表, 分类结果列表)
            分类结果列表中每个元素为[标签, 置信度]格式
        """
        # 如果输入是单个图像，转换为列表
        if isinstance(img_list, np.ndarray):
            img_list = [img_list]

        # 深拷贝图像列表，避免修改原图
        img_list = copy.deepcopy(img_list)

        # 计算所有文本区域的宽高比
        width_list = [img.shape[1] / float(img.shape[0]) for img in img_list]

        # 按宽高比排序，可以加速分类过程
        indices = np.argsort(np.array(width_list))

        img_num = len(img_list)
        # 初始化分类结果列表
        cls_res = [["", 0.0]] * img_num
        batch_num = self.cls_batch_num
        
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
                img_c, img_h, img_w = self.cls_image_shape
                # 调整图像大小并归一化
                norm_img = resize_norm_img(img_list[indices[ino]], img_w, img_h, img_c)
                norm_img = norm_img[np.newaxis, :]  # 增加批次维度
                norm_img_batch.append(norm_img)
            
            # 合并成批次输入格式
            norm_img_batch = np.concatenate(norm_img_batch).astype(np.float32)

            # 执行ONNX模型推理
            onnx_inputs = {self.input_name: norm_img_batch}
            prob_out = self.session.run(None, onnx_inputs)[0]
            # 后处理分类结果
            cls_result = self.postprocess_op(prob_out)

            # 处理分类结果并进行图像旋转(如果需要)
            for rno in range(len(cls_result)):
                label, score = cls_result[rno]
                # 保存分类结果到对应位置
                cls_res[indices[beg_img_no + rno]] = [label, score]
                # 如果分类为180度且置信度高于阈值，则旋转图像
                if label == "180" and score > self.cls_thresh:
                    img_list[indices[beg_img_no + rno]] = cv2.rotate(
                        img_list[indices[beg_img_no + rno]], 1  # 1表示旋转180度
                    )
        
        # 返回校正后的图像列表和分类结果
        return img_list, cls_res
