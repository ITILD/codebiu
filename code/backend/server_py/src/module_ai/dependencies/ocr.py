from module_ai.service.ocr import OcrService

# 全局单例(在线引擎按配置缓存, 本地流水线/版面分析惰性加载)


def get_ocr_service() -> OcrService:
    """获取 OCR 服务单例"""
    return _ocr_service


_ocr_service = OcrService()
