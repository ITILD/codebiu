"""开发日志工具：LoggingRich 统一配置控制台（Rich 美化）与文件（纯文本轮转）两类输出。"""

import logging
import runpy
import os
import sys
import datetime
import textwrap
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown
from rich.traceback import install as install_rich_tracebacks
from rich.markup import escape

from common.utils.log.CustomTimedRotatingFileHandler import (
    CustomTimedRotatingFileHandler,
)
from common.utils.sys.server_env import get_rel_path

# 文件日志默认纯文本格式
DEFAULT_FILE_FORMAT = (
    "%(asctime)s [%(levelname)-8s] %(filename)s:%(lineno)d - %(message)s"
)
# 轮转文件保留天数
BACKUP_DAYS = 31
# 控制台单条消息最大显示长度，超长截断（完整内容仍写入日志文件）
MAX_CONSOLE_MSG_LEN = 200

class _TruncateFormatter(logging.Formatter):
    """控制台专用 formatter：超长消息截断显示，提示全文在日志文件中。

    只作用于控制台 handler；文件 handler 使用独立的 Formatter，不受影响。
    截断提示带 OSC 8 链接，终端里 ctrl+click 可直接打开日志文件。
    """

    def __init__(
        self, max_len: int = MAX_CONSOLE_MSG_LEN, log_file: Path | None = None
    ):
        super().__init__("%(message)s")
        self.max_len = max_len
        self.log_file = log_file

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        if self.log_file and len(msg) > self.max_len:
            hidden = len(msg) - self.max_len
            log_file_path_rel = get_rel_path(self.log_file)
            # 用 escape() 转义截断提示，防止 markup=True 时将 [] 误解析为样式标签
            suffix = escape(f"[truncated {hidden} chars,full log in {log_file_path_rel}]")
            return f"{msg[:self.max_len]}... \n{suffix}"
        return msg


class _TopTimeRichHandler(RichHandler):
    """控制台 handler：时间（毫秒级）单独一行显示，级别彩色，消息内容从行首输出。"""

    def emit(self, record: logging.LogRecord) -> None:
        # %f 为 6 位微秒，截取前 3 位得到毫秒
        ts = datetime.datetime.fromtimestamp(record.created).strftime(
            "%Y-%m-%d %H:%M:%S,%f"
        )[:-3]
        # 来源 跳转到对应源码位置
        filr_path_rel = get_rel_path(Path(record.pathname))
        path_str = f"{filr_path_rel}:{record.lineno}"
        self.console.print(
            f"[dim]{ts}[/dim] [logging.level.{record.levelname.lower()}]{record.levelname:<8}[/] "
            f"[dim]{path_str}[/dim]"
        )
        super().emit(record)


class _NoConsoleNoiseFilter(logging.Filter):
    """控制台降噪过滤器：屏蔽第三方库的高频/DEBUG 噪音，文件日志不受影响。"""

    # 屏蔽的 logger 名称前缀：SQL 回显 / gRPC / asyncio / casbin 模型加载
    NOISY_PREFIXES = ("sqlalchemy.engine", "grpc", "asyncio", "casbin")

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith(self.NOISY_PREFIXES)


class LoggingRich:
    """开发日志工具类。

    用法：
        dev_log = LoggingRich()
        dev_log.setup()
        logger = logging.getLogger(__name__)

    也可自定义参数：
        LoggingRich(log_dir=tmp_path, is_dev=False, format_string="...")
    """

    def __init__(
        self,
        log_dir: Path | None = None,
        is_dev: bool = False,
        format_string: str = DEFAULT_FILE_FORMAT,
        console: Console | None = None,
    ) -> None:
        self.log_dir = log_dir
        self.is_dev = is_dev
        self.console = console or Console()
        # 文件日志通用纯文本格式
        self.file_formatter = logging.Formatter(format_string)
        self._configured = False

    # ==================== 入口 ====================

    def setup(self) -> None:
        """一键配置全部日志（幂等，重复调用或已有 handler 时不会重复添加）。"""
        root = logging.getLogger()
        if self._configured or root.handlers:
            self._configured = True
            return

        root.propagate = False
        root.setLevel(logging.DEBUG)
        # 屏蔽 markdown_it 解析器的 DEBUG 噪音
        logging.getLogger("markdown_it").setLevel(logging.WARNING)
        # echo=True 时 SQLAlchemy 会在 sqlalchemy.engine.Engine 子 logger 上自加
        # 默认 stdout handler，导致每条 SQL 打印两遍；handler 不随 logger 层级继承，
        # NullHandler 必须精确挂在 Engine 上才能阻止（记录仍传播到根 logger 统一输出）
        logging.getLogger("sqlalchemy.engine.Engine").addHandler(logging.NullHandler())

        self.setup_console_logging()
        self.setup_file_logging()

        root.info("Log system initialized successfully.")
        root.info("Environment: %s", "Development" if self.is_dev else "Production")
        self._configured = True

    # ==================== 控制台日志 ====================

    def setup_console_logging(self) -> None:
        """终端输出：毫秒时间单独一行、级别彩色、消息从行首、traceback 美化。仅开发环境生效。"""
        if not self.is_dev:
            return

        handler = _TopTimeRichHandler(
            console=self.console,
            show_time=False,  # 时间由 _TopTimeRichHandler 单独打印在上一行
            show_level=False,  # 级别同样在上一行，消息才能从行首开始
            show_path=False,
            markup=True,  # 允许在日志消息中使用 rich 标记
            rich_tracebacks=True,  # 美化已捕获异常的 traceback
            # tracebacks_show_locals=True, # traceback 中显示局部变量
            tracebacks_show_locals=False,  # ← 关闭 locals 显示（最大噪音源）
            tracebacks_max_frames=6,  # ← 限制最大帧数（默认无限制）
            tracebacks_width=120,  # ← 限制宽度，避免超宽换行
            tracebacks_suppress=[logging, runpy],
        )
        handler.setLevel(logging.DEBUG)
        # 控制台超长消息截断显示（SQL 等长日志缩略，全文进日志文件，提示可点击跳转）
        handler.setFormatter(_TruncateFormatter(log_file=self._log_file_path("info")))
        # 屏蔽第三方库高频噪音（SQL 回显/grpc/asyncio/casbin），文件日志仍全量记录
        handler.addFilter(_NoConsoleNoiseFilter())
        logging.getLogger().addHandler(handler)

        # rich 接管 sys.excepthook，美化未捕获崩溃的 traceback
        install_rich_tracebacks(show_locals=True)

    def log_markdown(self, md_text: str) -> None:
        """在终端渲染并输出 Markdown 内容。仅用于终端展示，不会写入标准日志文件。"""
        self.console.print(Markdown(md_text))

    # ==================== 文件日志 ====================

    def setup_file_logging(self) -> None:
        """文件输出：纯文本格式，info/error 双文件按天轮转，各保留 31 天。"""
        self._ensure_log_directory()

        # INFO 日志 (生产环境仅记录 WARN 及以上)
        self._add_file_handler("info", logging.INFO if self.is_dev else logging.WARN)
        # ERROR 日志 (仅记录 ERROR 及以上)
        self._add_file_handler("error", logging.ERROR)

    def _log_file_path(self, name: str) -> Path:
        """与 CustomTimedRotatingFileHandler 的实际写入文件名保持一致（强制 .log 后缀）。"""
        return (self.log_dir / name).with_suffix(".log")

    def _add_file_handler(self, name: str, level: int) -> None:
        """添加一个按天轮转的文件日志，记录 level 及以上的日志到 <log_dir>/<name>.log。"""
        handler = CustomTimedRotatingFileHandler(
            filename=self._log_file_path(name),
            when="midnight",
            interval=1,
            backupCount=BACKUP_DAYS,
            custom_function=self._on_rollover,
        )
        handler.setFormatter(self.file_formatter)
        handler.setLevel(level)
        logging.getLogger().addHandler(handler)

    # ==================== 内部实现 ====================
    def _ensure_log_directory(self) -> None:
        """确保日志目录存在且具有写入权限，失败则退出程序。"""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            test_file = self.log_dir / "test_permission.log"
            test_file.touch(exist_ok=True)
            test_file.unlink()
        except (PermissionError, OSError) as e:
            self.console.print(
                f"[bold red]无法创建或写入日志目录: {self.log_dir}, 错误: {e}[/bold red]"
            )
            sys.exit(1)

    def _on_rollover(self) -> None:
        """日志轮转时的钩子：安全地记录轮转事件到独立文件。"""
        try:
            with open(self.log_dir / "rollover.log", "a", encoding="utf-8") as f:
                f.write(f"{datetime.datetime.now().isoformat()} - log rotated\n")
        except Exception as e:
            # 使用 console 打印错误，避免死循环
            self.console.print(f"[bold red]记录日志轮转事件失败: {e}[/bold red]")


if __name__ == "__main__":

    from common.config.path import DIR_LOG
    from common.config.index import is_dev

    # ==================== 使用 ====================
    dev_log = LoggingRich(DIR_LOG, is_dev)
    dev_log.setup()
    logger = logging.getLogger(__name__)
    # 测试 rich 标记支持
    logger.debug("This is a [bold blue]debug[/bold blue] message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    # 测试超长log
    logger.error(
        """
    This is 0 long error message that should be truncated in the console.
    This is 1 long error message that should be truncated in the console.
    This is 2 long error message that should be truncated in the console.
    This is 3 long error message that should be truncated in the console.
    This is 4 long error message that should be truncated in the console.
    This is 5 long error message that should be truncated in the console.
    """
    )
    # 测试异常美化
    try:
        # pyrefly: ignore [division-by-zero]
        1 / 0
    except Exception:
        logger.exception("Caught an expected division by zero error")

    # 测试 Markdown 独立输出（必须 dedent，否则 4 空格缩进会被解析为代码块）
    md_content = textwrap.dedent(
        """
    # System Status
    - **CPU**: Normal
    - **Memory**: `45%` utilized
    """
    )
    dev_log.log_markdown(md_content)
