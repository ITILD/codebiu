import os
from pathlib import Path

_REMOTE_ENV = bool(os.environ.get("VSCODE_IPC_HOOK_CLI") or os.environ.get("SSH_CONNECTION"))
_PATH_CWD = Path.cwd()
def get_link_path(path_str: str) -> str:
    """根据 log_file 生成 OSC 8 链接，终端里 ctrl+click 可直接打开日志文件。"""
    if _REMOTE_ENV:
        return path_str
    return f"file://{path_str}"

def get_link(path_str: str, link_name: str) -> str:
    """根据 path_str 生成 OSC 8 链接，终端里 ctrl+click 可直接打开文件。"""
    return f"[link={get_link_path(path_str)}]{link_name}[/link]"

def get_rel_path(path:Path):
    try:
        return path.relative_to(_PATH_CWD)
    except ValueError:
        return path  # 不在项目内则返回原路径
    