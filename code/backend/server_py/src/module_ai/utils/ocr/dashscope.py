"""阿里云百炼(DashScope) 在线 OCR 引擎实现

通过 DashScope 多模态接口调用 qwen-vl-ocr 系在线模型识别图片文字,
图片以 base64 Data URL 内联上传, 返回整图纯文本(无坐标框)。

引擎配置来源优先级:
    1. model_config 表(model_type=ocr, server_type=dashscope)的 model/url/api_key/extra 字段
    2. 类内默认值回落(qwen-vl-ocr-latest + 官方接口地址)

extra 可选键:
    - prompt: OCR 指令文本(默认 "Read all the text in this image.")
    - timeout: 请求超时秒数(默认 60)

结果结构与本地 paddle 流水线对齐: {"ts": {...}, "results": [{box, text, score}]}
在线结果 box 为整图矩形坐标列表(score 恒为 1.0), 不参与分段/版面分析。
"""
import base64
import logging
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# DashScope 同步多模态生成接口(OCR)
_DASHSCOPE_OCR_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

# 默认请求超时(秒)
_DEFAULT_TIMEOUT = 60
# 默认 OCR 指令(qwen-vl-ocr 系模型专用提示)
_DEFAULT_PROMPT = "Read all the text in this image."


class DashscopeOCR:
    """阿里云在线 OCR 引擎(qwen-vl-ocr, 整图文本识别)"""

    def __init__(self, conf: dict | None = None):
        """
        :param conf: 动态配置(model_config 映射), 可含:
            - model: 在线模型名(默认 qwen-vl-ocr-latest)
            - url: DashScope OCR 接口地址
            - api_key: 百炼 API Key(必填, 缺失时报错提示)
            - prompt/timeout: 见模块 docstring
        """
        self._conf = conf or {}

    @property
    def _api_key(self) -> str:
        api_key = str(self._conf.get("api_key") or "").strip()
        if not api_key:
            raise RuntimeError("DashScope OCR 缺少 api_key: 请在模型配置中填写百炼 API Key")
        return api_key

    @staticmethod
    def _image_data_uri(image_cv) -> str:
        """cv2 图像编码为 PNG base64 Data URL"""
        ok, buf = cv2.imencode(".png", image_cv)
        if not ok:
            raise RuntimeError("图片编码失败, 无法上传 DashScope OCR")
        b64 = base64.b64encode(buf.tobytes()).decode()
        return f"data:image/png;base64,{b64}"

    @staticmethod
    def _parse_text(result: dict) -> str:
        """解析响应中的识别文本"""
        choices = (result.get("output") or {}).get("choices") or []
        for choice in choices:
            message = choice.get("message") or {}
            content = message.get("content") or []
            for item in content:
                if isinstance(item, dict) and item.get("text"):
                    return str(item["text"]).strip()
                if isinstance(item, str) and item.strip():
                    return item.strip()
            # 兼容 content 为纯字符串的响应
            if isinstance(message.get("content"), str) and message["content"].strip():
                return message["content"].strip()
        return ""

    def recognize(self, image_cv) -> dict:
        """上传图片识别文字, 返回与本地流水线同构的结果

        :param image_cv: cv2 图像(numpy.ndarray)
        :return: {"ts": {"total": 秒}, "results": [{"box", "text", "score"}], "engine": "dashscope"}
        """
        if not isinstance(image_cv, np.ndarray):
            raise RuntimeError("DashScope OCR 仅支持 cv2 图像输入")
        h, w = image_cv.shape[:2]
        payload = {
            "model": str(self._conf.get("model") or "qwen-vl-ocr-latest"),
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": self._image_data_uri(image_cv)},
                            {"text": str(self._conf.get("prompt") or _DEFAULT_PROMPT)},
                        ],
                    },
                ],
            },
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        timeout = float(self._conf.get("timeout") or _DEFAULT_TIMEOUT)
        start = time.time()
        try:
            import httpx

            with httpx.Client(timeout=timeout) as client:
                resp = client.post(str(self._conf.get("url") or _DASHSCOPE_OCR_URL), headers=headers, json=payload)
        except Exception as e:
            raise RuntimeError(f"DashScope OCR 请求失败: {e}") from e
        if resp.status_code >= 400:
            raise RuntimeError(f"DashScope OCR 请求失败({resp.status_code}): {resp.text[:500]}")
        text = self._parse_text(resp.json())
        if not text:
            raise RuntimeError(f"DashScope OCR 未返回识别文本: {resp.text[:500]}")
        # 与本地流水线结果同构: box 为整图矩形(JSON 可序列化列表)
        return {
            "ts": {"total": round(time.time() - start, 3)},
            "results": [{"box": [[0, 0], [w, 0], [w, h], [0, h]], "text": text, "score": 1.0}],
            "engine": "dashscope",
        }
