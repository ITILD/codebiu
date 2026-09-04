"""
Celery 任务队列入口(Worker 启动文件 / 模拟消费进程)

用法:
    python src/app_task.py          # 启动 worker(消费 task_queue 队列)
    celery -A src.app_task worker   # 等价命令行方式(Windows 建议加 --pool=solo)

说明:
    - broker/backend 由 config.yaml 的 tasks 段配置(当前 dev 使用 Redis)
    - worker 消费 task_queue 队列, 任务执行中把 状态/百分比/阶段消息 实时回写 PostgreSQL
    - API 服务(app.py)与 worker(app_task.py) 可独立部署重启, 互不影响
"""
import logging

from common.config.tasks import app as celery_app

# 导入任务注册(Worker 进程必须导入任务模块, 否则对应任务无法被路由执行)
from module_task.tasks import demo  # noqa: F401

logger = logging.getLogger(__name__)

__all__ = ("celery_app",)


async def _ensure_task_table() -> None:
    """Worker 进程内幂等建表(仅创建本进程已导入模型对应的表; 常规由 API 启动时创建)"""
    from common.config.db import db_manager

    await db_manager.db_rel.create_all()
    logger.info("task_queue table ensured.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 通过 worker 常驻循环执行(与任务协程共享同一连接池所在的事件循环)
    from module_task.tasks import run_async

    run_async(_ensure_task_table())
    # Windows 推荐 solo 池(单进程顺序消费, 即"模拟单个消费进程"); 生产环境可换 prefork/gevent
    celery_app.worker_main(
        [
            "worker",
            "--loglevel=info",
            "--pool=solo",
            "--concurrency=1",
            "--queues=task_queue",
            "--hostname=task_worker@%h",
        ]
    )
