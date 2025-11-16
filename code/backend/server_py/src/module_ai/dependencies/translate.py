from fastapi import Depends
from module_ai.dao.translate_prompt import TranslatePrompt
from module_ai.service.translate import TranslateService
from module_ai.dependencies.ocr import get_ocr_service
from module_ai.service.ocr import OcrService
from module_ai.dependencies.llm_base import get_llm_base_service
from module_ai.service.llm_base import LLMBaseService

async def get_translate_prompt() -> TranslatePrompt:
    """获取翻译提示"""
    return TranslatePrompt()
async def get_translate_service(
    translate_prompt: TranslatePrompt = Depends(get_translate_prompt),
    ocr_service: OcrService = Depends(get_ocr_service),
    llm_base_service: LLMBaseService = Depends(get_llm_base_service),
) -> TranslateService:
    """获取翻译服务"""
    return TranslateService(translate_prompt, ocr_service, llm_base_service)
