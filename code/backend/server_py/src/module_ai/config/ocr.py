"""OCR 配置(惰性加载)

OCR 子系统仅在实际使用(创建会话/加载流水线)时才要求配置节存在,
导入本模块不触发校验, 保证未配置 ocr 的环境中 module_ai 其余功能可用。
"""
import logging
from pathlib import Path

from common.config.index import conf
from common.config.path import DIR_MODEL

logger = logging.getLogger(__name__)

# ocr 模型根目录 temp_source/model/ocr
DIR_OCR_MODEL: Path = DIR_MODEL / "ocr"


def _require_conf():
    """获取 ocr 配置节, 缺失时抛出可操作的错误提示"""
    conf_ocr = conf.get("ocr")
    if conf_ocr is None:
        raise RuntimeError(
            "配置文件中缺少 ocr 配置节: module_ai OCR/版面分析功能不可用。"
            "请参考 config_template_full.yaml 的 ocr 节补全配置,或在 app.py 中取消挂载相关路由"
        )
    return conf_ocr


def get_ocr_ort() -> dict:
    """onnxruntime 运行时配置(use_cuda/线程数/provider 参数)"""
    return _require_conf().get("global")


def get_ocr_languages() -> dict:
    """语言级流水线配置 {lang: {config:..., models:...}}"""
    return _require_conf().languages


def get_ocr_models() -> dict:
    """onnx 子模型配置 {detect/classify/recognize/layout: {name: {path, config}}}"""
    return _require_conf().models


def get_layout_model_path() -> Path:
    """版面分析模型文件路径"""
    return DIR_OCR_MODEL / get_ocr_models().layout
