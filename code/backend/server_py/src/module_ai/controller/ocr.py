from cv2 import Mat
from module_ai.config.server import module_app
from module_ai.dependencies.ocr import get_ocr_service
from module_ai.do.ocr import Base64File
from module_ai.service.ocr import OcrService
from common.utils.media.FileFormat import bytes_to_cv2
from module_ai.config.ocr import get_ocr_languages
from common.utils.code.language.lang2lang import Language

# lib
from fastapi import APIRouter, status, Form, UploadFile, Depends
import base64

import logging

logger = logging.getLogger(__name__)


router = APIRouter()

# engine 参数公共描述(OCR 引擎方案: 本地 paddle-onnx / 阿里云在线)
_ENGINE_DESC = "OCR 引擎方案：paddle(本地 onnx) / dashscope(阿里云在线)，缺省时按模型配置自动选择"

# 未配置本地 ocr 节(如仅启用 dashscope 在线方案)时的默认语言列表
# code 与 common.utils.code.language.lang2lang.Language 枚举对齐
_DEFAULT_LANGUAGES = [
    {"code": "ch", "name": "中文"},
    {"code": "cht", "name": "中文繁体"},
    {"code": "en", "name": "English"},
]


@router.post("/", status_code=status.HTTP_201_CREATED, summary="文字识别")
async def recognize(
    image: UploadFile,
    lang: str = Form(description="识别语言代码(见 /languages 接口)"),
    engine: str | None = Form(None, description=_ENGINE_DESC),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    """对上传图片执行 OCR 文字识别(启用检测与分类)

    :param image: 上传的图片文件
    :param lang: 识别语言代码(见 /languages 接口)
    :param engine: 引擎方案 paddle/dashscope(缺省按模型配置自动选择)
    :return: 识别结果(含文本框坐标/置信度/耗时)
    """
    image_bytes = await image.read()
    image_cv = bytes_to_cv2(image_bytes)
    result = await ocr_service.recognize(image_cv, True, True, lang, engine=engine)
    return result


@router.post("/segments", status_code=status.HTTP_201_CREATED, summary="文字识别 -> 分栏分段 ")
async def segment_layout(
    image: UploadFile,
    lang: str = Form(description="识别语言代码(见 /languages 接口)"),
    engine: str | None = Form(None, description=_ENGINE_DESC),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    """对上传图片执行文字识别并做分栏分段处理(仅本地 paddle 方案)

    :param image: 上传的图片文件
    :param lang: 识别语言代码
    :param engine: 引擎方案 paddle/dashscope(缺省按模型配置自动选择)
    :return: 识别+分段结果
    """
    image_bytes = await image.read()
    image_cv: Mat = bytes_to_cv2(image_bytes)
    result = await ocr_service.segment_layout(image_cv, True, True, lang, engine=engine)
    return result


@router.post("/layout", status_code=status.HTTP_201_CREATED, summary="完整版面分析")
async def layout(
    image: UploadFile,
    engine: str | None = Form(None, description=_ENGINE_DESC),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    """对上传图片执行版面分析,识别标题/图片/表格/目录等区域(仅本地 paddle 方案)

    :param image: 上传的图片文件
    :param engine: 引擎方案 paddle/dashscope(缺省按模型配置自动选择)
    :return: 版面区域框坐标/类别/置信度/耗时
    """
    image_bytes = await image.read()
    image_cv: Mat = bytes_to_cv2(image_bytes)
    boxes, scores, class_names, elapse = await ocr_service.layout(image_cv, engine=engine)
    result = {
        "boxes": boxes.tolist(),
        "scores": scores.tolist(),
        "clss_names": class_names,
        "elapse": elapse,
    }
    return result


@router.post(
    "/all",
    status_code=status.HTTP_201_CREATED,
    summary="执行文字识别 -> 分栏分段 + 版面分析Figure/Table/Toc",
)
async def recognize_all(
    image: UploadFile,
    lang: Language = Form(description="识别语言代码(见 /languages 接口)"),
    engine: str | None = Form(None, description=_ENGINE_DESC),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    """组合接口:文字识别+分栏分段+版面分析(提取Figure/Table/Toc区域, 仅本地 paddle 方案)

    :param image: 上传的图片文件
    :param lang: 识别语言代码
    :param engine: 引擎方案 paddle/dashscope(缺省按模型配置自动选择)
    :return: 识别结果与版面区域(layout)合并结果
    """
    image_bytes = await image.read()
    image_cv: Mat = bytes_to_cv2(image_bytes)
    result = await ocr_service.recognize_all(image_cv, True, True, lang, False, engine=engine)
    return result


@router.get("/languages", status_code=status.HTTP_200_OK, summary="返回可用语言列表")
def get_languages():
    """读取 OCR 可用语言, 返回 [{code, name}] 列表供前端选择识别语言

    优先读取本地 ocr 配置节(paddle 流水线语言); 未配置该节(如仅启用
    dashscope 在线方案)时返回默认语言列表, 保证接口可用不因缺配置 500。
    """
    try:
        languages = get_ocr_languages()
    except RuntimeError:
        # 缺少本地 ocr 配置节: 在线引擎不依赖语言配置, 回落默认列表
        return _DEFAULT_LANGUAGES
    return [{"code": key, "name": val["name"]} for key, val in languages.items()]


@router.post(
    "/all-base64",
    status_code=status.HTTP_201_CREATED,
    summary="执行文字识别 -> 分栏分段 + 版面分析Figure/Table/Toc base64 ",
)
async def recognize_base64(
    base64_file: Base64File,
    engine: str | None = Form(None, description=_ENGINE_DESC),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    """同 /all 接口,但图片以 base64 编码传入(便于前端直传, 仅本地 paddle 方案)

    :param base64_file: 含 base64 图片与识别参数的请求体
    :param engine: 引擎方案 paddle/dashscope(缺省按模型配置自动选择)
    :return: 识别结果与版面区域(layout)合并结果
    """
    image_bytes = base64.b64decode(base64_file.image_base64)
    image_cv: Mat = bytes_to_cv2(image_bytes)
    result = await ocr_service.recognize_all(
        image_cv, True, True, base64_file.lang, base64_file.inpaint, engine=engine
    )
    return result


module_app.include_router(router, prefix="/ocr", tags=["ocr识别"])
