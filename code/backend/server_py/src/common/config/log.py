# common/utils/log/setup.py
import logging
import sys

from common.config.path import DIR_LOG
from common.config.index import is_dev
from common.utils.log.logging_rich import LoggingRich

# ==================== 使用 ====================
dev_log = LoggingRich(DIR_LOG, is_dev)
dev_log.setup()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.debug("test: This is a debug message")
    logger.info("test: This is an info message")
    logger.warning("test: This is a warning message")
    logger.error("test: This is an error message")
    logger.critical("test: This is a critical message")
