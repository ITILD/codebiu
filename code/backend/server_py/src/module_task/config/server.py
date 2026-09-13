from common.config.lifespan import register_init_hook
from common.utils.fastapiEX.exceptions import BizFastAPI
import logging

from common.config.server import app

logger = logging.getLogger(__name__)

# 模块子应用(挂载到主应用 /task 路径下)
module_app = BizFastAPI()
app.mount("/task", module_app)

# 导入权限声明(注册到权限中心, 幂等)
from module_task.config.permissions import TASK_DEFINE  # noqa: F401, E402


@register_init_hook
async def recover_local_pending_tasks() -> None:
    """
    local 引擎 API 启动自愈: 无独立 worker 进程, 遗留的长期 PENDING 任务
    (如进程重启瞬间丢失的后台协程)由 API 启动时重新派发(进程内后台执行)。
    celery 引擎不在此恢复(由 app_task.py worker 启动时兜底)。
    """
    from common.config.tasks import TASK_ENGINE
    from module_task.tasks import recover_pending_tasks

    if TASK_ENGINE == "local":
        count = await recover_pending_tasks()
        if count:
            logger.info(f"local 引擎启动自愈: 恢复 {count} 个遗留 PENDING 任务")


logger.info("ok...server module_task服务配置")
