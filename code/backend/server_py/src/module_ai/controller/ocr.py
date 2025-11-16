from cv2 import Mat
from module_ai.config.server import module_app
from module_ai.dependencies.ocr import get_ocr_service
from module_ai.do.ocr import Base64File
from module_ai.service.ocr import OcrService
from common.utils.media.FileFormat import bytes_to_cv2
from module_ai.config.ocr import conf_ocr_languages
from common.utils.code.language.lang2lang import Language
import logging

logger = logging.getLogger(__name__)

# lib
from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Form,
    UploadFile,
)
import base64
from fastapi import Depends

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, summary="文字识别")
async def ocr(
    image: UploadFile,
    lang: str = Form(),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    try:
        image_bytes = await image.read()
        image_cv = bytes_to_cv2(image_bytes)
        result = ocr_service.ocr(image_cv, True, True, lang)
        return result
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@router.post(
    "/tupu", status_code=status.HTTP_201_CREATED, summary="文字识别 -> 分栏分段 "
)
async def tupu(
    image: UploadFile,
    lang: str = Form(),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    try:
        image_bytes = await image.read()
        image_cv: Mat = bytes_to_cv2(image_bytes)
        result = ocr_service.ocr_tupu(image_cv, True, True, lang)
        return result
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@router.post("/layout", status_code=status.HTTP_201_CREATED, summary="完整版面分析")
async def layout(
    image: UploadFile,
    ocr_service: OcrService = Depends(get_ocr_service),
):
    """返回可用语言列表"""
    try:
        image_bytes = await image.read()
        image_cv: Mat = bytes_to_cv2(image_bytes)
        boxes, scores, class_names, elapse = ocr_service.layout(image_cv)
        result = {
            "boxes": boxes.tolist(),
            "scores": scores.tolist(),
            "clss_names": class_names,
            "elapse": elapse,
        }
        return result
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@router.post(
    "/all",
    status_code=status.HTTP_201_CREATED,
    summary="执行文字识别 -> 分栏分段 + 版面分析Figure/Table/Toc",
)
async def ocr_all(
    image: UploadFile,
    lang: Language = Form(),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    try:
        image_bytes = await image.read()
        image_cv: Mat = bytes_to_cv2(image_bytes)
        result = await ocr_service.ocr_all(image_cv, True, True, lang, False)
        return result
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@router.get("/lang", status_code=status.HTTP_201_CREATED, summary="文字识别")
def get_languages():
    """返回可用语言列表"""
    try:
        result = [
            {"code": key, "name": val["name"]}
            for key, val in conf_ocr_languages.items()
        ]
        return result
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))

@router.post(
    "/all_base64",
    status_code=status.HTTP_201_CREATED,
    summary="执行文字识别 -> 分栏分段 + 版面分析Figure/Table/Toc base64 ",
)
async def ocr_base64(
    base64_file: Base64File,
    ocr_service: OcrService = Depends(get_ocr_service),
):
    try:
        image_bytes = base64.b64decode(base64_file.image_base64)
        image_cv: Mat = bytes_to_cv2(image_bytes)
        result = await ocr_service.ocr_all(
            image_cv, True, True, base64_file.lang, base64_file.inpaint
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


module_app.include_router(router, prefix="/ocr", tags=["ocr识别"])
