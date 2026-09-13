"""OCR 服务门面: 识别/分段/版面分析统一入口

引擎方案由 model_config 表驱动(与 voice 服务同构):
    - model_type=ocr + server_type=paddle(本地 PP-OCR onnx) / dashscope(阿里云在线) 的记录即为可选方案
    - engine 参数可选: 指定时精确匹配 server_type, 缺省时取 ocr 类型第一条配置
    - 表中无配置时回落本地 paddle onnx 流水线(历史行为)
模型加载策略: 本地流水线/版面分析惰性加载并缓存, 首次调用才加载模型;
在线引擎按配置(id+updated_at)缓存, 配置变更自动重建。
"""
import logging
from functools import lru_cache

from common.utils.fastapiEX.exceptions import BusinessError
from module_ai.config.ocr import get_layout_model_path
from module_ai.dao.model_config import ModelConfigDao
from module_ai.do.model_config import ModelConfig
from module_ai.utils.ocr.dashscope import DashscopeOCR
from module_ai.utils.ocr.layout import RapidLayout
from module_ai.utils.ocr.pipeline import detect_recognize
from module_ai.utils.ocr.segment.parser_multi_para import MultiPara

logger = logging.getLogger(__name__)

# 本地方案标识(与 ModelServerType.PADDLE 对齐)
LOCAL_ENGINE = "paddle"
# 在线方案标识(与 ModelServerType.DASHSCOPE 对齐)
REMOTE_ENGINE = "dashscope"
# OCR 支持的引擎方案集合
_ENGINE_CHOICES = (LOCAL_ENGINE, REMOTE_ENGINE)

# 排版分段引擎(纯算法, 不加载模型)
segment_engine = MultiPara()


@lru_cache(maxsize=1)
def get_layout_engine() -> RapidLayout:
    """获取版面分析引擎(惰性加载, 全局缓存)"""
    return RapidLayout(model_path=get_layout_model_path())


def _engine_conf(config: ModelConfig | None) -> dict:
    """ModelConfig -> 在线引擎配置字典(model/url/api_key/extra 展平)"""
    if config is None:
        return {}
    conf = dict(config.extra or {})
    # model/url/api_key 字段优先(extra 中可被显式覆盖)
    conf.setdefault("model", config.model)
    if config.url:
        conf.setdefault("url", config.url)
    if config.api_key:
        conf.setdefault("api_key", config.api_key)
    return conf


class OcrService:
    """OCR 服务: 按模型配置选择 本地paddle-onnx / 阿里云在线 引擎"""

    def __init__(self, model_config_dao: ModelConfigDao | None = None):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.model_config_dao = model_config_dao or ModelConfigDao()
        # 在线引擎缓存: (server_type, cache_key) -> 引擎实例
        self._remote_engines: dict[tuple[str, str], DashscopeOCR] = {}

    async def _resolve_engine(self, engine: str | None = None) -> tuple[str, DashscopeOCR | None]:
        """
        解析实际生效的 OCR 方案
        :param engine: 指定方案(paddle/dashscope, None 时取第一条 ocr 配置)
        :return: (生效方案标识, 在线引擎实例; 本地方案返回 None)
        """
        # 查询 ocr 模型配置(指定 engine 时按 server_type 精确匹配)
        config = await self.model_config_dao.get_first_by_type(
            "ocr", server_type=engine if engine in _ENGINE_CHOICES else None
        )
        # 实际生效的方案(未指定时取配置自身的 server_type; 无配置时回落本地)
        effective = engine if engine in _ENGINE_CHOICES else None
        if config is not None:
            server_type = config.server_type
            server_type = server_type.value if hasattr(server_type, "value") else str(server_type)
            if effective is None and server_type in _ENGINE_CHOICES:
                effective = server_type
        elif effective is None:
            effective = LOCAL_ENGINE

        if effective != REMOTE_ENGINE:
            return LOCAL_ENGINE, None

        # 在线引擎: 缓存键 = 配置ID + updated_at(配置变更自动失效)
        cache_key = "static" if config is None else f"{config.id}:{config.updated_at}"
        key = (REMOTE_ENGINE, cache_key)
        if key not in self._remote_engines:
            self._remote_engines[key] = DashscopeOCR(_engine_conf(config))
            logger.info("OCR 在线引擎已构建: dashscope (来源: %s)", cache_key)
        return REMOTE_ENGINE, self._remote_engines[key]

    async def recognize(
        self, image_cv, detect: bool, classify: bool, lang: str, inpaint: bool = False, engine: str | None = None
    ) -> dict:
        """执行文字识别(OCR)处理，支持多语言识别、文本检测和分类

        Args:
            image_cv: 输入图像，支持OpenCV格式(numpy.ndarray)或文件路径(str)
            detect: 是否启用文本检测(定位文字区域)
            classify: 是否启用文本分类(识别文本类型如标题/正文)
            lang: 目标语言代码(如'en'/'zh')，支持多语言混合识别
            inpaint: 是否启用图像去除检测位置，默认False
            engine: 指定引擎方案(paddle/dashscope, 缺省按模型配置自动选择)
        """
        server_type, remote = await self._resolve_engine(engine)
        if remote is not None:
            # 在线方案: 整图文本识别, 返回与本地同构的结果
            return remote.recognize(image_cv)
        # 本地方案: PP-OCR onnx 流水线
        result = detect_recognize(
            image_cv, lang=lang, detect=detect, classify=classify, inpaint=inpaint
        )
        results = result["results"]
        # 循环修改results中的每个元素
        for i in range(len(results)):
            resultOne = results[i]
            resultOne["box"] = resultOne["box"].tolist()
            # numpy.float32转float
            resultOne["score"] = float(resultOne["score"])
        return result

    async def segment_layout(
        self, image_cv, detect: bool, classify: bool, lang: str, inpaint: bool = False, engine: str | None = None
    ) -> dict:
        """执行文字识别/分栏分段(仅本地 paddle 方案支持, 在线方案无坐标框)"""
        _, remote = await self._resolve_engine(engine)
        if remote is not None:
            raise BusinessError("在线 OCR(dashscope) 不支持分栏分段, 请切换本地 paddle 引擎")
        result = await self.recognize(image_cv, detect, classify, lang, inpaint=inpaint)
        results = result["results"]
        if len(results) > 0:
            result["results"] = segment_engine.run(results)
        return result

    async def layout(self, image_cv, engine: str | None = None):
        """版面分析(仅本地 paddle 方案支持, 在线方案无版面模型)"""
        _, remote = await self._resolve_engine(engine)
        if remote is not None:
            raise BusinessError("在线 OCR(dashscope) 不支持版面分析, 请切换本地 paddle 引擎")
        boxes, scores, class_names, elapse = get_layout_engine().check(image_cv)
        return boxes, scores, class_names, elapse

    async def recognize_all(
        self, image_cv, detect: bool, classify: bool, lang: str, inpaint: bool = False, engine: str | None = None
    ) -> dict:
        """执行文字识别/分栏分段/版面分析(仅本地 paddle 方案支持)"""
        _, remote = await self._resolve_engine(engine)
        if remote is not None:
            raise BusinessError("在线 OCR(dashscope) 不支持分栏分段/版面分析, 请切换本地 paddle 引擎")
        # 1 文字识别+分栏分段
        result = await self.segment_layout(image_cv, detect, classify, lang, inpaint=inpaint)
        boxes, scores, class_names, elapse = get_layout_engine().check(image_cv)
        layout = []
        i = 0
        for class_name in class_names:
            # 如果是图片、表格或目录，则将bbox添加到结果中
            if (
                class_name == "Title"
                or class_name == "Figure"
                or class_name == "Table"
                or class_name == "Toc"
            ):
                layout.append(boxes[i].tolist())
            i = i + 1
        result["layout"] = layout
        return result
