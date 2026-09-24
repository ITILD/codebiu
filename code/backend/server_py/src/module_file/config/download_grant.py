"""业务模块下载授权注册表

文件管理的下载权限(main:file:download)独立于浏览(read), 默认仅 admin 角色持有;
业务条目(rag 等以 source_module 标记的条目)可由来源模块注册授权钩子补充放行口径:

    rag: 条目位于项目根文件夹子树内 且 用户项目生效档位 >= project_editor 时放行

接入约定(与 ensure_module_root 同源):
    业务模块在自己的 config/server.py 导入期调用
    register_download_grant(module_key, fn) 注册异步判定函数;
    fn(user_id, entry) -> bool, 返回 True 表示放行下载。
    module_file 不反向依赖业务模块(避免循环导入), 注册方向始终为 业务 -> 文件。
"""
from collections.abc import Awaitable, Callable

from module_file.do.filesystem import FileEntry

# 授权钩子类型: (user_id, entry) -> 是否放行
DownloadGrantFn = Callable[[str, FileEntry], Awaitable[bool]]

_business_download_grants: dict[str, DownloadGrantFn] = {}


def register_download_grant(module_key: str, fn: DownloadGrantFn) -> None:
    """注册业务模块的下载授权判定钩子(后注册覆盖先注册, 幂等)"""
    _business_download_grants[module_key] = fn


def get_download_grant(module_key: str) -> DownloadGrantFn | None:
    """获取业务模块的下载授权钩子(未注册返回 None)"""
    return _business_download_grants.get(module_key)
