"""conftest.py pytest 默认测试配置文件
所有同目录测试文件运行前都会执行 conftest.py，不需要 import 导入。
"""

import logging

from common.config.path import DIR_LOG
from common.config.index import is_dev
from common.utils.log.logging_rich import LoggingRich

# ==================== 使用 ====================
dev_log = LoggingRich(DIR_LOG, is_dev)
dev_log.setup()
logger = logging.getLogger(__name__)

logger.info("test log is set up ok")
logger.info("运行环境: %s", "测试 (tests)")
