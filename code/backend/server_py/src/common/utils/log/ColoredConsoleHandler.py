import logging
# self
from common.enum.color import Color, LogLevelColor

class ColoredConsoleHandler(logging.StreamHandler):
    """自定义日志处理器"""
    def emit(self, record):
        try:
            # 获取日志级别对应的颜色
            color = LogLevelColor[record.levelname].value if record.levelname in LogLevelColor.__members__ else Color.RESET
            message = self.format(record)
            # 输出带颜色的日志
            self.stream.write(color.value + message + Color.RESET.value + '\n')
        except Exception:
            self.handleError(record)
            
# if __name__ == '__main__':
#     # 创建日志器
#     logger = logging.getLogger()
#     logger.setLevel(logging.DEBUG)

#     # 创建控制台处理器并设置日志格式
#     debug_handler = ColoredConsoleHandler()
#     formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#     debug_handler.setFormatter(formatter)

#     # 将控制台处理器添加到日志器
#     logger.addHandler(debug_handler)
#     # 示例日志
#     logger.info('First message: %s, Second message: %s', '1', 2)
#     logger.info("This is a debug message")
#     logger.info("This is an info message")
#     logger.warning("This is a warning message")
#     logger.error("This is an error message")
#     logger.critical("This is a critical message")












