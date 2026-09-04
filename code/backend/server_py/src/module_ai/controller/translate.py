from common.utils.media.FileFormat import bytes_to_cv2
from module_ai.config.server import module_app
from fastapi import APIRouter, Depends, Form, UploadFile
from module_ai.dependencies.translate import get_translate_service
from module_ai.do.translate import Translate
from module_ai.service.translate import TranslateService
from common.utils.code.language.lang2lang import Language

router = APIRouter()


@router.post("/base", summary="基础翻译")
async def translate_base(
    translate: Translate,
    translate_service: TranslateService = Depends(get_translate_service),
) -> str:
    """文本基础翻译:将源语言文本翻译为目标语言

    :param translate: 翻译请求(含原文与目标语言)
    :return: 翻译后的文本
    """
    result = await translate_service.translate_base(translate)
    return result


@router.post("/ocr", summary="图片识别结果翻译")
async def translate_ocr(
    image: UploadFile,
    model_id: str = Form(),
    lang_ocr: Language = Form(),
    lang_translate: Language = Form(),
    translate_service: TranslateService = Depends(get_translate_service),
):
    """图片文字识别并翻译:先 OCR 识别图片文本,再将结果翻译为目标语言

    :param image: 上传的图片文件
    :param model_id: 使用的模型配置ID
    :param lang_ocr: 图片识别语言
    :param lang_translate: 翻译目标语言
    :return: 翻译后的文本
    """
    image_bytes = await image.read()
    image_cv = bytes_to_cv2(image_bytes)
    # 识别
    result = await translate_service.translate_ocr(image_cv, lang_ocr, model_id, lang_translate)
    return result


module_app.include_router(router, prefix="/translate", tags=["翻译"])
