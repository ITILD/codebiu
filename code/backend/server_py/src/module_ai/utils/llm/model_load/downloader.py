"""模型下载器

统一的模型下载入口，优先使用 ModelScope(国内加速)，
可选回退到 HuggingFace 镜像。支持本地缓存检查与断点续传。
"""
import logging
import os
from enum import Enum
from pathlib import Path

from module_ai.utils.llm.model_load.constants import (
    MODELS,
    ModelSpec,
    get_model_spec,
    list_model_keys,
)

logger = logging.getLogger(__name__)

# HuggingFace 国内镜像
HF_MIRROR_ENDPOINT = "https://hf-mirror.com"


class DownloadSource(str, Enum):
    """下载源枚举。"""

    MODELSCOPE = "modelscope"
    HUGGINGFACE = "huggingface"


class ModelDownloader:
    """规范的模型下载器。

    通过 source 选择下载渠道:
        - modelscope: 使用 ModelScope Hub(国内加速，推荐)。
        - huggingface: 使用 HuggingFace，自动切换 hf-mirror 镜像。

    Examples:
        >>> downloader = ModelDownloader(source="modelscope")
        >>> downloader.download("qwen_llm")
        >>> # 或直接指定仓库
        >>> downloader.download_repo("Qwen/Qwen3.5-0.8B", Path("./models/qwen"))
    """

    def __init__(
        self,
        source: DownloadSource | str = DownloadSource.MODELSCOPE,
        hf_token: str | None = None,
        use_hf_mirror: bool = True,
    ):
        """初始化下载器。

        Args:
            source: 下载源，默认 modelscope。
            hf_token: HuggingFace 访问令牌(用于受限模型)。
            use_hf_mirror: 使用 HF 时是否启用 hf-mirror 镜像。
        """
        self.source = DownloadSource(source)
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self.use_hf_mirror = use_hf_mirror

    # ------------------------------
    # 缓存检查
    # ------------------------------

    @staticmethod
    def is_local_model_ready(local_dir: Path) -> bool:
        """判断本地模型是否已下载完成(目录存在且非空)。"""
        local_dir = Path(local_dir)
        return local_dir.exists() and any(local_dir.iterdir())

    def is_downloaded(self, key: str) -> bool:
        """根据注册的 model key 检查是否已下载。"""
        spec = get_model_spec(key)
        return self.is_local_model_ready(spec.local_dir)

    # ------------------------------
    # 下载核心
    # ------------------------------

    def download_repo(
        self,
        repo_id: str,
        local_dir: Path,
        modelscope_id: str | None = None,
        is_gated: bool = False,
    ) -> Path:
        """下载指定仓库到本地目录。

        Args:
            repo_id: HuggingFace 仓库 ID。
            local_dir: 本地存放目录。
            modelscope_id: ModelScope 上的模型 ID(默认与 repo_id 相同)。
            is_gated: 是否为受限模型(需要 token)。

        Returns:
            本地模型目录 Path。
        """
        local_dir = Path(local_dir)

        if self.is_local_model_ready(local_dir):
            logger.info("本地模型已存在，跳过下载: %s", local_dir)
            return local_dir

        local_dir.mkdir(parents=True, exist_ok=True)

        if self.source == DownloadSource.MODELSCOPE:
            self._download_from_modelscope(
                modelscope_id or repo_id, local_dir
            )
        else:
            self._download_from_huggingface(repo_id, local_dir, is_gated)

        logger.info("下载完成: %s -> %s", repo_id, local_dir)
        return local_dir

    def download(self, key: str) -> Path:
        """根据注册的 model key 下载模型。

        Args:
            key: 注册表中的模型标识(qwen_llm/embedding/reranker)。

        Returns:
            本地模型目录 Path。
        """
        spec: ModelSpec = get_model_spec(key)
        return self.download_repo(
            repo_id=spec.hf_repo_id,
            local_dir=spec.local_dir,
            modelscope_id=spec.modelscope_id,
            is_gated=spec.is_gated,
        )

    def download_all(self, keys: list[str] | None = None) -> dict[str, Path]:
        """批量下载已注册的模型。

        Args:
            keys: 要下载的 model key 列表，None 表示全部。

        Returns:
            {key: local_dir} 映射。
        """
        keys = keys or list_model_keys()
        results: dict[str, Path] = {}
        for k in keys:
            try:
                results[k] = self.download(k)
            except Exception as e:
                logger.error("下载 %s 失败: %s", k, e)
                results[k] = Path()  # 占位
        return results

    # ------------------------------
    # 下载源实现
    # ------------------------------

    def _download_from_modelscope(self, model_id: str, local_dir: Path) -> None:
        """通过 ModelScope 下载。"""
        try:
            from modelscope.hub.snapshot_download import snapshot_download as ms_download
        except ImportError as e:
            raise RuntimeError(
                "未安装 modelscope，请执行 `pip install modelscope`"
            ) from e

        logger.info("[ModelScope] 开始下载 %s -> %s", model_id, local_dir)
        ms_download(
            model_id=model_id,
            local_dir=str(local_dir),
        )

    def _download_from_huggingface(
        self, repo_id: str, local_dir: Path, is_gated: bool
    ) -> None:
        """通过 HuggingFace(可选镜像) 下载。"""
        if self.use_hf_mirror:
            os.environ["HF_ENDPOINT"] = HF_MIRROR_ENDPOINT
            logger.info("[HuggingFace] 使用镜像: %s", HF_MIRROR_ENDPOINT)

        try:
            from huggingface_hub import snapshot_download as hf_download
        except ImportError as e:
            raise RuntimeError(
                "未安装 huggingface-hub，请执行 `pip install huggingface-hub`"
            ) from e

        token = self.hf_token if is_gated else None
        logger.info("[HuggingFace] 开始下载 %s -> %s", repo_id, local_dir)
        hf_download(
            repo_id=repo_id,
            local_dir=str(local_dir),
            token=token,
        )

    # ------------------------------
    # 信息
    # ------------------------------

    def status(self) -> list[dict]:
        """返回所有已注册模型的下载状态。"""
        info: list[dict] = []
        for key in list_model_keys():
            spec = get_model_spec(key)
            info.append(
                {
                    "key": key,
                    "local_dir": str(spec.local_dir),
                    "ready": self.is_local_model_ready(spec.local_dir),
                }
            )
        return info

    def __repr__(self) -> str:
        return f"ModelDownloader(source={self.source.value})"


# 便捷函数：等价于原 ensure_local_model，但走 ModelDownloader
def ensure_local_model(
    repo_id: str,
    local_dir: Path,
    source: DownloadSource | str = DownloadSource.MODELSCOPE,
) -> Path:
    """下载模型到本地；如果本地已存在则跳过。(兼容旧接口)

    Args:
        repo_id: 模型仓库 ID。
        local_dir: 本地存放目录。
        source: 下载源。

    Returns:
        本地模型目录 Path。
    """
    downloader = ModelDownloader(source=source)
    return downloader.download_repo(repo_id=repo_id, local_dir=local_dir)
