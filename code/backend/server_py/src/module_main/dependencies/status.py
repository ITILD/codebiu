from module_main.service.status import StatusService
from functools import lru_cache
@lru_cache(maxsize=1)
def get_status_service_singleton():
    return StatusService()
# 通过依赖注入系统控制生命周期（如 lru_cache或模块变量）
# 可以灵活定义生命周期范围（应用级/请求级）
# ​​软性单例​​：可通过 dependency_overrides临时替换实例（便于测试）
# # lru_cache 是线程安全的