import json
import numpy as np
from common.utils.media.FileFormat import resize_norm_img
from module_ai.utils.onnx.ocr_rapid.utils import OrtInferSession


class CTCLabelDecode:
    """CTC标签解码器 - 在文本标签和文本索引之间进行转换"""

    def __init__(self, characters: list[str]):
        """
        初始化CTC标签解码器
        
        Args:
            characters: 字符列表，包含所有可能的字符
        """
        super(CTCLabelDecode, self).__init__()

        self.characters = characters
        self.characters.append(" ")  # 添加空格字符

        dict_character = self.add_special_char(self.characters)
        self.character = dict_character

        self.dict = {}
        for i, char in enumerate(dict_character):
            self.dict[char] = i

    def __call__(self, preds, label=None):
        """
        调用函数，执行CTC解码
        
        Args:
            preds: 模型预测结果
            label: 真实标签(可选)
            
        Returns:
            解码后的文本结果，如果提供了标签则返回预测结果和真实标签
        """
        preds_idx = preds.argmax(axis=2)  # 获取每个位置概率最大的字符索引
        preds_prob = preds.max(axis=2)    # 获取对应的概率值
        text = self.decode(preds_idx, preds_prob, is_remove_duplicate=True)
        if label is None:
            return text
        label = self.decode(label)
        return text, label

    def add_special_char(self, dict_character):
        """
        添加特殊字符(CTC空白符)
        
        Args:
            dict_character: 原始字符列表
            
        Returns:
            添加了特殊字符后的字符列表
        """
        dict_character = ["blank"] + dict_character  # 添加CTC空白符
        return dict_character

    def get_ignored_tokens(self):
        """
        获取需要忽略的token(CTC空白符)
        
        Returns:
            需要忽略的token索引列表
        """
        return [0]  # CTC空白符的索引

    def decode(self, text_index, text_prob=None, is_remove_duplicate=False):
        """
        将文本索引转换为文本标签
        
        Args:
            text_index: 文本索引数组
            text_prob: 对应的概率数组(可选)
            is_remove_duplicate: 是否移除重复字符(用于预测时)
            
        Returns:
            包含文本和置信度的结果列表
        """

        result_list = []
        ignored_tokens = self.get_ignored_tokens()  # 获取需要忽略的token
        batch_size = len(text_index)
        for batch_idx in range(batch_size):
            char_list = []  # 存储字符
            conf_list = []  # 存储置信度
            for idx in range(len(text_index[batch_idx])):
                if text_index[batch_idx][idx] in ignored_tokens:
                    continue  # 跳过空白符
                if is_remove_duplicate:
                    # 预测时移除重复字符
                    if (
                        idx > 0
                        and text_index[batch_idx][idx - 1] == text_index[batch_idx][idx]
                    ):
                        continue
                # 将索引转换为字符
                char_list.append(self.character[int(text_index[batch_idx][idx])])
                if text_prob is not None:
                    conf_list.append(text_prob[batch_idx][idx])
                else:
                    conf_list.append(1)
            # 计算平均置信度，避免空列表警告
            score = np.mean(conf_list) if conf_list else 0
            text = "".join(char_list)  # 将字符列表拼接成字符串
            result_list.append((text, score))
        return result_list


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
