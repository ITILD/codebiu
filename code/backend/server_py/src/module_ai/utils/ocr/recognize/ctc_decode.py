"""CTC 标签解码: 将识别模型的预测索引序列解码为文本"""
import numpy as np


class CTCLabelDecode:
    """CTC 解码器 - 在文本索引序列和文本字符串之间转换

    :param characters: 模型字典字符列表(来自 onnx 模型元数据)
    """

    def __init__(self, characters: list[str]):
        self.characters = characters
        self.characters.append(" ")  # 追加空格字符
        # 前置 CTC 空白符(blank)
        dict_character = ["blank"] + self.characters
        self.character = dict_character

        self.dict = {char: i for i, char in enumerate(dict_character)}

    def __call__(self, preds: np.ndarray, label=None):
        """解码批量预测结果

        :param preds: 模型输出 (batch, seq_len, num_classes)
        :return: [(文本, 平均置信度), ...]
        """
        preds_idx = preds.argmax(axis=2)  # 每个位置概率最大的字符索引
        preds_prob = preds.max(axis=2)  # 对应概率值
        text = self.decode(preds_idx, preds_prob, is_remove_duplicate=True)
        if label is None:
            return text
        return text, self.decode(label)

    def get_ignored_tokens(self) -> list[int]:
        """需要忽略的 token(CTC 空白符索引)"""
        return [0]

    def decode(self, text_index, text_prob=None, is_remove_duplicate=False) -> list[tuple]:
        """将索引序列转换为文本和置信度

        :param text_index: 索引数组 (batch, seq_len)
        :param text_prob: 对应概率数组(可选)
        :param is_remove_duplicate: 是否移除相邻重复字符(预测时)
        """
        result_list = []
        ignored_tokens = self.get_ignored_tokens()
        batch_size = len(text_index)
        for batch_idx in range(batch_size):
            char_list = []  # 字符
            conf_list = []  # 置信度
            for idx in range(len(text_index[batch_idx])):
                if text_index[batch_idx][idx] in ignored_tokens:
                    continue  # 跳过空白符
                if is_remove_duplicate and idx > 0 and text_index[batch_idx][idx - 1] == text_index[batch_idx][idx]:
                    continue  # 移除重复字符
                char_list.append(self.character[int(text_index[batch_idx][idx])])
                if text_prob is not None:
                    conf_list.append(text_prob[batch_idx][idx])
                else:
                    conf_list.append(1)
            # 平均置信度, 空序列时为 0
            score = float(np.mean(conf_list)) if conf_list else 0
            result_list.append(("".join(char_list), score))
        return result_list
