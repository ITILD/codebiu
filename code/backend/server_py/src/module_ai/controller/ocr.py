from cv2 import Mat
from module_ai.config.server import module_app
from module_ai.dependencies.ocr import get_ocr_service
from module_ai.do.ocr import Base64File
from module_ai.service.ocr import OcrService
from common.utils.media.FileFormat import bytes_to_cv2
from module_ai.config.ocr import conf_ocr_languages
from common.utils.code.language.lang2lang import Language

# lib
from fastapi import APIRouter, HTTPException, status, Form, UploadFile, Depends
import base64

import logging

logger = logging.getLogger(__name__)


router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, summary="文字识别")
async def recognize(
    image: UploadFile,
    lang: str = Form(),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    """对上传图片执行 OCR 文字识别(启用检测与分类)

    :param image: 上传的图片文件
    :param lang: 识别语言代码(见 /languages 接口)
    :return: 识别结果(含文本框坐标/置信度/耗时)
    """
    try:
        image_bytes = await image.read()
        image_cv = bytes_to_cv2(image_bytes)
        result = ocr_service.recognize(image_cv, True, True, lang)
        return result
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@router.post("/segments", status_code=status.HTTP_201_CREATED, summary="文字识别 -> 分栏分段 ")
async def segment_layout(
    image: UploadFile,
    lang: str = Form(),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    """对上传图片执行文字识别并做分栏分段处理

    :param image: 上传的图片文件
    :param lang: 识别语言代码
    :return: 识别+分段结果
    """
    try:
        image_bytes = await image.read()
        image_cv: Mat = bytes_to_cv2(image_bytes)
        result = ocr_service.segment_layout(image_cv, True, True, lang)
        return result
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@router.post("/layout", status_code=status.HTTP_201_CREATED, summary="完整版面分析")
async def layout(
    image: UploadFile,
    ocr_service: OcrService = Depends(get_ocr_service),
):
    """对上传图片执行版面分析,识别标题/图片/表格/目录等区域

    :param image: 上传的图片文件
    :return: 版面区域框坐标/类别/置信度/耗时
    """
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
async def recognize_all(
    image: UploadFile,
    lang: Language = Form(),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    """组合接口:文字识别+分栏分段+版面分析(提取Figure/Table/Toc区域)

    :param image: 上传的图片文件
    :param lang: 识别语言代码
    :return: 识别结果与版面区域(layout)合并结果
    """
    try:
        image_bytes = await image.read()
        image_cv: Mat = bytes_to_cv2(image_bytes)
        result = await ocr_service.recognize_all(image_cv, True, True, lang, False)
        return result
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@router.get("/languages", status_code=status.HTTP_201_CREATED, summary="返回可用语言列表")
def get_languages():
    """返回可用语言列表"""
    try:
        result = [{"code": key, "name": val["name"]} for key, val in conf_ocr_languages.items()]
        return result
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@router.post(
    "/all-base64",
    status_code=status.HTTP_201_CREATED,
    summary="执行文字识别 -> 分栏分段 + 版面分析Figure/Table/Toc base64 ",
)
async def recognize_base64(
    base64_file: Base64File,
    ocr_service: OcrService = Depends(get_ocr_service),
):
    """同 /all 接口,但图片以 base64 编码传入(便于前端直传)

    :param base64_file: 含 base64 图片与识别参数的请求体
    :return: 识别结果与版面区域(layout)合并结果
    """
    try:
        image_bytes = base64.b64decode(base64_file.image_base64)
        image_cv: Mat = bytes_to_cv2(image_bytes)
        result = await ocr_service.recognize_all(
            image_cv, True, True, base64_file.lang, base64_file.inpaint
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


module_app.include_router(router, prefix="/ocr", tags=["ocr识别"])
