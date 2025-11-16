import asyncio
import base64
import math
import cv2
import numpy as np
from common.utils.code.language.lang2lang import Language

from module_ai.dao.translate_prompt import TranslatePrompt
from module_ai.do.translate import Translate
from module_ai.service.ocr import OcrService
from PIL import Image, ImageDraw, ImageFont
from module_ai.service.llm_base import LLMBaseService
from module_ai.do.llm_base import ChatRequest

import logging

logger = logging.getLogger(__name__)

# 常量定义
FONT_COLOR = (0, 0, 0)  # RGB格式
LINE_HEIGHT_RATIO = 1  # 行高倍数
# font_path = "temp_source/fonts/NotoSansKR-Regular"
font_path = "temp_source/fonts/NotoSansCJK-Regular.ttc"
# font_path = "temp_source/fonts/NotoSansSC-Regular"
# font_path = "temp_source/fonts/NotoSerifCJK-VF.ttf"


class TranslateService:
    """Translate服务类，提供模型翻译功能"""

    def __init__(
        self,
        translate_prompt: TranslatePrompt,
        ocr_service: OcrService,
        llm_base_service: LLMBaseService,
    ):
        self.translate_prompt = translate_prompt
        self.ocr_service = ocr_service
        self.llm_base_service = llm_base_service

    async def base(self, translate: Translate) -> str:
        """翻译单句"""
        prompt = []
        prompt.append(await self.translate_prompt.get_prompt_system())
        prompt.append(await self.translate_prompt.get_prompt_user(translate))
        request = ChatRequest(
            model_id=translate.model_id,
            messages=prompt
        )
        responses = await self.llm_base_service.chat_completion(request)
        return responses

    async def ocr(
        self,
        image: bytes,
        lang_in: Language,
        model_id: str,
        lang_translate: Language = Language.EN,
    ) -> dict:
        """OCR识别"""
        ocr_result =await self.ocr_service.ocr_all(image, True, True, lang_in.value, True)
        background = ocr_result["background"]
        results_ocr_old = ocr_result["results"]
        # 翻译
        ocr_result["results_translate"] = results_translate_list = []
        results_translate = None
        for ocr_old in results_ocr_old:
            # 首行
            if not results_translate:
                results_translate = {
                    "text": "",
                    "box": [],
                    "text_old": "",
                    "width": 0.001,
                    "width_max": 0.001,
                }
                results_translate_list.append(results_translate)
                results_translate["box"].extend(ocr_old["box"][0:2])
            # 第一行上划线宽度计算
            # TODO 考虑倾斜°
            results_translate["text"] += ocr_old["text"]
            x_row_start = ocr_old["box"][0][0]
            y_row_start = ocr_old["box"][0][1]
            x_row_end = ocr_old["box"][1][0]
            y_row_end = ocr_old["box"][2][1]
            width_new_row = math.sqrt(
                (x_row_end - x_row_start) ** 2 + (y_row_end - y_row_start) ** 2
            )
            if results_translate["width_max"] < width_new_row:
                results_translate["width_max"] = width_new_row
            results_translate["width"] += width_new_row
            # 尾行
            is_end = ocr_old.get("end") == "\n"
            if is_end:
                # 尾标符
                results_translate["box"].extend(ocr_old["box"][2:4])
                # 新一行
                results_translate["text_old"] = results_translate["text"]
                results_translate = None
        # llm批量翻译
        # 准备所有翻译任务
        translated_texts = []
        try:
            translate_tasks = []
            for result in results_translate_list:
                translate = Translate(
                    model_id=model_id, content=result["text"], lang=lang_translate
                )
                # 直接存储协程对象（不 await）
                translate_tasks.append(self.base(translate))

            # 并行执行所有任务
            translated_texts = await asyncio.gather(*translate_tasks)
        except Exception as e:
            logger.error(e)

        # 更新结果
        for result, translated_text in zip(results_translate_list, translated_texts):
            result["text"] = translated_text

        # 首先将OpenCV图像转换为Pillow格式
        background_pil = Image.fromarray(cv2.cvtColor(background, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(background_pil)
        # 背景绘制 - 使用Pillow
        for result in results_translate_list:
            box = result["box"]
            text = result["text"]
            text = text.replace("\n", " ").replace("\r", " ")  # 先移除所有换行符
            text_old = result["text_old"]
            width = result["width"]
            width_max = result["width_max"]

            # 计算字体大小
            text_len_old = len(text_old) if text_old else 1
            font_size = int(width / text_len_old)
            # font = ImageFont.load_default()
            try:
                font = ImageFont.truetype(font_path, font_size/2)
            except IOError:
                font = ImageFont.load_default()
                logger.warning(f"Font {font_path} not found, using default font")

            # 计算绘制起始位置
            x, y = int(box[0][0]), int(box[0][1])
            max_width = min(box[0][0] + width_max, background_pil.width) - x

            # 分割文本为多行
            lines = []
            current_line = []
            for word in text:
                test_line = "".join(current_line + [word])
                test_width = draw.textlength(test_line, font=font)

                if test_width <= max_width:
                    current_line.append(word)
                else:
                    if current_line:  # 如果当前行有内容，则添加到lines
                        lines.append("".join(current_line))
                        # 重置
                        current_line = [word]
                    else:  # 如果单个单词就超长，强制换行
                        lines.append(word)

            if current_line:  # 添加最后一行
                lines.append(" ".join(current_line))

            # 绘制多行文本
            stroke_width = int(font_size * 0.02)  # 根据字体大小调整描边宽度
            line_height = int(font_size * LINE_HEIGHT_RATIO)

            for line in lines:
                # 检查是否超出底部边界
                if y + line_height > background_pil.height:
                    break

                draw.text(
                    (x, y), line, font=font, fill=FONT_COLOR, stroke_width=stroke_width
                )
                y += line_height  # 移动到下一行

        # 转换回OpenCV格式
        background = cv2.cvtColor(np.array(background_pil), cv2.COLOR_RGB2BGR)
        # 将图像编码为JPEG字节流,转换为Base64字符串
        encoded_img = cv2.imencode(".jpg", background)[1]
        background_base64 = base64.b64encode(encoded_img).decode("utf-8")
        ocr_result["background"] = background_base64
        return ocr_result
