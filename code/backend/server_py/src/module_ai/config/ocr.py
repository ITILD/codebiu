from pathlib import Path

from common.config.index import conf
from common.config.path import DIR_MODEL
import logging

logger = logging.getLogger(__name__)

DIR_OCR_MODEL = DIR_MODEL / "ocr"


# 使用 conf.get 以便未配置时得到 None(dynaconf 属性访问缺失键会抛 AttributeError)
conf_ocr = conf.get("ocr")
if conf_ocr is None:
    # OCR 子系统在导入时即加载语言模型,缺失配置无法继续;给出可操作的错误提示
    raise RuntimeError(
        "配置文件中缺少 ocr 配置节: module_ai OCR/版面分析功能不可用。"
        "请参考 config_template_full.yaml 的 ocr 节补全配置,或在 app.py 中取消挂载相关路由"
    )
# onnxruntime 本地配置
conf_ocr_ort = conf_ocr.get("global")
conf_ocr_languages = conf_ocr.languages
# ocr 模型
conf_ocr_models = conf_ocr.models

# layout 模型
conf_ocr_models_layout = conf_ocr_models.layout
path_lout_model = DIR_OCR_MODEL / conf_ocr_models_layout
