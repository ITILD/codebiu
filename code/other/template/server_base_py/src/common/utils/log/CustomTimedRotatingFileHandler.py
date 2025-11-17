from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from pathlib import Path


class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, file:Path, when, interval, backupCount, custom_function=None, **kwargs):
        # 将 filename_pattern 转换为字符串（兼容 Path 对象）
        file_str = file.as_posix()
        # 使用当前时间格式化文件名作为初始文件名
        initial_filename = datetime.now().strftime(file_str)
        
        # 确保目录存在
        log_dir = Path(initial_filename).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        super().__init__(
            filename=initial_filename,
            when=when,
            interval=interval,
            backupCount=backupCount,
            encoding='utf-8',
            **kwargs
        )
        
        self.filename_pattern = file_str
        self.custom_function = custom_function

    def doRollover(self):
        if self.custom_function:
            try:
                self.custom_function()
            except Exception:
                # 避免rollover失败导致日志丢失
                pass

        # 根据当前时间生成新的文件名
        new_filename = datetime.now().strftime(self.filename_pattern)
        self.baseFilename = new_filename
        
        # 调用基类的方法完成实际的日志滚动
        super().doRollover()

# if __name__ == '__main__':
#     def external_custom_function():
#         print("Custom function called when the log file is rolled over.")

#     logger = logging.getLogger()
#     logger.setLevel(logging.DEBUG)

#     debug_handler = CustomTimedRotatingFileHandler(
#         'd:\\debug_%Y-%m-%d.log', when='midnight', interval=1, backupCount=7, custom_function=external_custom_function
#     )
#     error_handler = CustomTimedRotatingFileHandler(
#         'error_%Y-%m-%d.log', when='midnight', interval=1, backupCount=7, custom_function=external_custom_function
#     )

#     debug_handler.setLevel(logging.DEBUG)
#     error_handler.setLevel(logging.ERROR)

#     formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#     debug_handler.setFormatter(formatter)
#     error_handler.setFormatter(formatter)

#     logger.addHandler(debug_handler)
#     logger.addHandler(error_handler)

#     logger.info("This is a debug message")
#     logger.error("This is an error message")