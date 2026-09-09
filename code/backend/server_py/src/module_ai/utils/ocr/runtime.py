"""onnxruntime 推理会话工厂 - OCR 全部子模型(detect/classify/recognize/layout)的统一加载入口

设备切换策略(取自 conf_ocr_ort 全局配置):
    - use_cuda=true 且环境具备 CUDAExecutionProvider 时启用 GPU
    - Windows 10+ 且具备 DmlExecutionProvider 时启用 DirectML
    - 均不可用时自动回退 CPUExecutionProvider
各子模型包不再自行维护会话创建逻辑, 统一通过 OrtInferSession 获得一致行为。
"""
import logging
import warnings

from onnxruntime import (
    get_available_providers,
    get_device,
    GraphOptimizationLevel,
    InferenceSession,
    SessionOptions,
)

from module_ai.config.ocr import DIR_OCR_MODEL, get_ocr_ort

logger = logging.getLogger(__name__)

# 执行提供者标识
CUDA_EP = "CUDAExecutionProvider"
CPU_EP = "CPUExecutionProvider"
DML_EP = "DmlExecutionProvider"


def build_providers(use_cuda: bool | None = None) -> list:
    """按配置构建执行提供者优先级列表: CUDA(可选) -> DirectML(可选) -> CPU(兜底)

    :param use_cuda: 显式覆盖全局 use_cuda 配置; None 时取 ocr.global.use_cuda
    """
    ort_conf = get_ocr_ort()
    if use_cuda is None:
        use_cuda = bool(ort_conf.get("use_cuda", False))
    providers: list = []
    available = get_available_providers()
    if use_cuda and get_device() == "GPU" and CUDA_EP in available:
        providers.append((CUDA_EP, ort_conf.get(CUDA_EP, {})))
    if DML_EP in available:
        providers.append((DML_EP, {}))
    providers.append((CPU_EP, {"arena_extend_strategy": "kSameAsRequested"}))
    return providers


class OrtInferSession:
    """onnxruntime 推理会话封装

    :param model_path: onnx 模型相对路径(相对 OCR 模型根目录 DIR_OCR_MODEL)
    :param use_cuda: 显式设备覆盖; None 时取全局 conf_ocr_ort["use_cuda"]
    """

    def __init__(self, model_path: str, use_cuda: bool | None = None):
        ort_conf = get_ocr_ort()
        sess_opt = SessionOptions()
        sess_opt.log_severity_level = 4
        sess_opt.enable_cpu_mem_arena = False
        sess_opt.graph_optimization_level = GraphOptimizationLevel.ORT_ENABLE_ALL
        # cpu 推理线程数(全局配置, 默认 4)
        sess_opt.intra_op_num_threads = int(ort_conf.get("intra_op_num_threads", 4) or 4)

        self.use_cuda = use_cuda if use_cuda is not None else bool(ort_conf.get("use_cuda", False))
        self.session = InferenceSession(
            str(DIR_OCR_MODEL / model_path),
            sess_options=sess_opt,
            providers=build_providers(use_cuda),
        )
        self._warn_cuda_fallback()

    def _warn_cuda_fallback(self):
        """请求 GPU 但实际回退 CPU 时给出可操作的警告"""
        if self.use_cuda and CUDA_EP not in self.session.get_providers():
            warnings.warn(
                f"{CUDA_EP} 不可用, 推理已自动回退 {CPU_EP}。"
                "请确认 onnxruntime-gpu 版本与 cuda/cudnn 匹配: "
                "https://onnxruntime.ai/docs/execution-providers/CUDA-Execution-Provider.html",
                RuntimeWarning,
            )

    def get_input_name(self, input_idx: int = 0) -> str:
        return self.session.get_inputs()[input_idx].name

    def get_output_name(self, output_idx: int = 0) -> str:
        return self.session.get_outputs()[output_idx].name

    def get_character_list(self) -> list[str]:
        """读取模型元数据中的类别名(版面分析 YOLOv8 模型使用)"""
        names = self.session.get_modelmeta().custom_metadata_map.get("names", "")
        return [n for n in names.split("\n") if n]
