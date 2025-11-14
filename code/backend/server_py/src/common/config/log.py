# common/utils/log/setup.py
import logging
import sys

from common.config.path import DIR_LOG
from common.config.index import is_dev
from common.utils.log.ColoredConsoleHandler import ColoredConsoleHandler
from common.utils.log.CustomTimedRotatingFileHandler import (
    CustomTimedRotatingFileHandler,
)

def setup_logging():
    """
    配置全局日志系统：
    - 开发环境：控制台输出 + info/error 日志文件
    - 生产环境：仅输出 warn+ 日志到文件
    """
    logger = logging.getLogger()
    if logger.handlers:
        return  # 已配置，防止重复添加 handler

    logger.propagate = False
    logger.setLevel(logging.DEBUG)

    # 确保日志目录存在且有写入权限
    try:
        DIR_LOG.mkdir(parents=True, exist_ok=True)
        test_file = DIR_LOG / "test_permission.log"
        test_file.touch(exist_ok=True)
        test_file.unlink()
    except (PermissionError, OSError) as e:
        print(f"无法创建或写入日志目录: {DIR_LOG}, 错误: {e}")
        return

    # 通用格式
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # ==================== 控制台处理器 ====================
    if is_dev:
        # 控制台输出颜色
        console_handler = ColoredConsoleHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)

    # ==================== 文件处理器 ====================
    def on_rollover():
        """日志轮转时的钩子"""
        logging.info("...new log")

    # INFO 日志（记录 INFO 及以上）
    info_log_path = DIR_LOG / "info_%Y-%m-%d.log"
    info_handler = CustomTimedRotatingFileHandler(
        file=info_log_path,
        when="midnight",
        interval=1,
        backupCount=14,
        custom_function=on_rollover,
    )
    info_handler.setFormatter(formatter)
    info_handler.setLevel(logging.WARN if not is_dev else logging.INFO)
    logger.addHandler(info_handler)

    # ERROR 日志（只记录 ERROR 及以上）
    error_log_path = DIR_LOG / "error_%Y-%m-%d.log"
    error_handler = CustomTimedRotatingFileHandler(
        file=error_log_path,
        when="midnight",
        interval=1,
        backupCount=14,
        custom_function=on_rollover,
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    logger.addHandler(error_handler)

    # ==================== 全局异常处理器 ====================
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("未捕获的异常", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception

    # ==================== 启动日志 ====================
    logger.info("log is set up ok")
    logger.info("运行环境: %s", "开发 (development)" if is_dev else "生产 (production)")

# 立即配置日志系统
setup_logging()
logger = logging.getLogger(__name__)

# # 输出带颜色的日志
# logger.info("%s %s", "config log test:", "info")
# logger.error("%s %s", "config log test:", "error")

if __name__ == "__main__":
    logger.debug("test: This is a debug message")
    logger.info("test: This is an info message")
    logger.warning("test: This is a warning message")
    logger.error("test: This is an error message")
    logger.critical("test: This is a critical message")