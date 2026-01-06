from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from pathlib import Path
import time
import os


class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, custom_function, **kwargs):
        # 自定义log尾标
        self.my_suffix = ".log"
        self.filename = Path(kwargs["filename"])
        # 确保文件名后缀为自定义的log尾标
        kwargs["filename"] = self.filename.with_suffix(self.my_suffix)
        super().__init__(encoding="utf-8", **kwargs)
        self.custom_function = custom_function

    def doRollover(self):
        """更改轮转log的格式"""
        # 轮转时触发函数custom_function
        if self.custom_function:
            try:
                self.custom_function()
            except Exception:
                # 避免rollover失败导致日志丢失
                pass
        # get the time that this sequence started at and make it a TimeTuple
        currentTime = int(time.time())
        t = self.rolloverAt - self.interval
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
            dstNow = time.localtime(currentTime)[-1]
            dstThen = timeTuple[-1]
            if dstNow != dstThen:
                if dstNow:
                    addend = 3600
                else:
                    addend = -3600
                timeTuple = time.localtime(t + addend)
        # 去除尾标重新赋予
        dfn = self.rotation_filename(
            f"{self.filename}_{time.strftime(self.suffix, timeTuple)}{self.my_suffix}"
        )
        if os.path.exists(dfn):
            # Already rolled over.
            return

        if self.stream:
            self.stream.close()
            self.stream = None
        self.rotate(self.baseFilename, dfn)
        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                os.remove(s)
        if not self.delay:
            self.stream = self._open()
        self.rolloverAt = self.computeRollover(currentTime)
