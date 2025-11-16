from common.utils.media.FileFormat import bytes_to_cv2
from module_ai.config.server import module_app
from fastapi import APIRouter, Depends, Form, UploadFile
from module_ai.dependencies.translate import get_translate_service
from module_ai.do.translate import Translate
from module_ai.service.translate import TranslateService
from common.utils.code.language.lang2lang import Language

router = APIRouter()


@router.post("/base", summary="基础翻译")
async def base(
    translate: Translate,
    translate_service: TranslateService = Depends(get_translate_service),
) -> str:
    result = await translate_service.base(translate)
    return result


@router.post("/ocr", summary="图片识别结果翻译")
async def ocr(
    image: UploadFile,
    model_id: str = Form(),
    lang_ocr: Language = Form(),
    lang_translate: Language = Form(),
    translate_service: TranslateService = Depends(get_translate_service),
):
    image_bytes = await image.read()
    image_cv = bytes_to_cv2(image_bytes)
    # 识别
    result = await translate_service.ocr(image_cv, lang_ocr, model_id, lang_translate)
    return result


module_app.include_router(router, prefix="/translate", tags=["翻译"])
