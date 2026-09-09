"""
Celery 任务队列入口(Worker 启动文件 / 消费进程)

用法:
    python src/app_task.py          # 启动单个 worker(消费 task_queue 队列)
    celery -A src.app_task worker   # 等价命令行方式(Windows 建议加 --pool=solo)

多实例横向扩容:
    同机多开直接重复执行 `python src/app_task.py` 即可 —— 节点名自动携带 PID
    (task_worker@<主机名>#<PID>), 互不冲突; 所有实例竞争消费同一 task_queue 队列,
    由 Redis 分级子队列按任务 priority(0~9, 越大越优先)加权派发。

说明:
    - broker/backend 由 config.yaml 的 tasks 段配置(当前 dev 使用 Redis)
    - worker 消费 task_queue 队列, 任务执行中把 状态/百分比/阶段消息 实时回写 PostgreSQL
    - API 服务(app.py)与 worker(app_task.py) 可独立部署重启, 互不影响
    - 任务函数是"薄启动器": 经 load_task 读取 payload 与创建者 user_id,
      调用业务模块自己的 service 执行(主进程 controller 可直跑同一 service, 双路径兼容)
    - 任务账户与权限: worker 启动时以只读方式初始化 casbin enforcer,
      任务执行时以创建者 user_id 实时复检资源权限(权限回收后任务安全失败)

启动流程:
    建表(幂等) → 初始化权限上下文(只读) → 自愈重投递遗留 PENDING 任务 → 启动消费循环
"""
import logging
import os
import socket

from common.config.tasks import app as celery_app

# 导入任务注册(Worker 进程必须导入任务模块, 否则对应任务无法被路由执行)
from module_task.tasks import demo  # noqa: F401
from module_rag.tasks import project_document, project_document_chunk  # noqa: F401

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
    from module_task.tasks import (
        init_worker_authorization,
        recover_pending_tasks,
        run_async,
    )

    run_async(_ensure_task_table())
    # 权限上下文: 只读构建 casbin enforcer(任务执行时以创建者身份复检权限)
    run_async(init_worker_authorization())
    # 启动自愈: 重新投递"创建超 60s 仍 PENDING 且无投递ID"的遗留任务(消息丢失兜底)
    run_async(recover_pending_tasks())

    # Windows 推荐 solo 池(单进程顺序消费); 生产环境可换 prefork/gevent 并调大 concurrency
    # 节点名携带 PID: 同机多开多个 worker 实例互不冲突, 竞争消费同一队列
    node_name = f"task_worker@{socket.gethostname()}#{os.getpid()}"
    celery_app.worker_main(
        [
            "worker",
            "--loglevel=info",
            "--pool=solo",
            "--concurrency=1",
            "--queues=task_queue",
            f"--hostname={node_name}",
        ]
    )
