# conftest.py
import sys
import logging
from common.config.path import DIR_LOG
from common.utils.log.ColoredConsoleHandler import ColoredConsoleHandler
from common.utils.log.CustomTimedRotatingFileHandler import (
    CustomTimedRotatingFileHandler,
)
import datetime
"""
conftest.py pytest 默认测试配置文件
所有同目录测试文件运行前都会执行conftest.py文件 不需要import导入
"""


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
    console_handler = ColoredConsoleHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # ==================== 文件处理器 ====================
    def on_rollover():
        """日志轮转时的钩子 安全地记录轮转事件到独立文件"""
        try:
            with open(DIR_LOG / "test-rollover.log", "a") as f:
                f.write(f"{datetime.datetime.now().isoformat()} - log rotated\n")
        except Exception as e:
            print(f"记录日志轮转事件失败: {e}")

    # INFO 日志(记录 INFO 及以上)
    info_log_path = DIR_LOG / "test-info"
    info_handler = CustomTimedRotatingFileHandler(
        filename=info_log_path,
        when="midnight",
        interval=1,
        # 保留 31 天的日志文件
        backupCount=31,
        custom_function=on_rollover,
    )
    info_handler.setFormatter(formatter)
    info_handler.setLevel(logging.INFO)
    logger.addHandler(info_handler)

    # ERROR 日志(只记录 ERROR 及以上)
    error_log_path = DIR_LOG / "test-error"
    error_handler = CustomTimedRotatingFileHandler(
        filename=error_log_path,
        when="midnight",
        interval=1,
        backupCount=31,
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
    logger.info("test log is set up ok")
    logger.info("运行环境: %s", "测试 (tests)")


# 立即配置日志系统
setup_logging()
logger = logging.getLogger(__name__)
