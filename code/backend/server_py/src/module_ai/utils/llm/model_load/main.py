"""模型加载演示入口

从原 llm_local_todo.py 的 main() 迁移，演示下载 → 测试 → 缓存转换的完整流程。
可直接运行: python -m module_ai.utils.llm.model_load.main
"""
import logging

from module_ai.utils.llm.model_load.cache_converter import CacheConverter
from module_ai.utils.llm.model_load.constants import list_model_keys
from module_ai.utils.llm.model_load.downloader import DownloadSource, ModelDownloader
from module_ai.utils.llm.model_load.tester import ModelTester

logger = logging.getLogger(__name__)


def main() -> None:
    """运行 下载 → 测试 → 缓存检查 完整演示。"""

    # 1. 下载模型(默认走 ModelScope 国内加速)
    downloader = ModelDownloader(source=DownloadSource.MODELSCOPE)
    print(f"下载源: {downloader}")
    print(f"已注册模型: {list_model_keys()}")
    print("下载状态:", downloader.status())

    downloader.download_all()

    # 2. 冒烟测试
    tester = ModelTester()
    tester.test_all()

    # 3. 缓存检查示例(以 embedding 为例)
    from module_ai.utils.llm.model_load.constants import get_model_spec

    spec = get_model_spec("embedding")
    converter = CacheConverter(spec.local_dir)
    info = converter.inspect_cache()
    print("\n缓存检查:", info)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
