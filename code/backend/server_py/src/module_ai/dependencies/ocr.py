from fastapi import Depends
from module_ai.service.ocr import OcrService
async def get_ocr_service() -> OcrService:
    """获取ocr服务"""
    return OcrService()
