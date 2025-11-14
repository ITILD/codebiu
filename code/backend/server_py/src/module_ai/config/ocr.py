from common.config.index import conf
from common.config.path import DIR_MODEL
import logging

logger = logging.getLogger(__name__)

DIR_OCR_MODEL = DIR_MODEL / "ocr"


conf_ocr = conf.ocr
if conf_ocr is None:
    logger.info("未配置ocr")
# onnxruntime 本地配置
conf_ocr_ort = conf_ocr.get("global")
conf_ocr_languages = conf_ocr.languages
# ocr 模型
conf_ocr_models = conf_ocr.models

# layout 模型
conf_ocr_models_layout = conf_ocr_models.layout
path_lout_model = DIR_OCR_MODEL / conf_ocr_models_layout
