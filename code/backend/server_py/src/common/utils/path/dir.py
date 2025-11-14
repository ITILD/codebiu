from pathlib import Path
import logging

class Dir:
    @staticmethod
    def ensure_dir(path: Path) -> Path:
        """确保目录存在，返回Path对象。如果创建失败，记录日志但不中断程序。"""
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logging.warning(f"无法创建目录 {path}: {e}")
        return path