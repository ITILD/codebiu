"""任务队列配置(模块级单例)

- broker/backend/engine 从 config.yaml 的 tasks 段读取
- engine 双引擎: local(FastAPI 进程内后台协程) / celery(Redis broker + worker)
- 未配置 broker 时默认 memory:// 本地内存队列(无需额外服务,适合开发/测试)
- 生产部署配置 redis 即可,如:
    tasks:
      engine: celery
      broker_url: redis://127.0.0.1:6379/1
      result_backend: redis://127.0.0.1:6379/2
"""
import logging

from common.config.index import conf

logger = logging.getLogger(__name__)

try:
    conf_tasks = conf.tasks
    if conf_tasks is None:
        conf_tasks = {}
except Exception:
    conf_tasks = {}

# 任务执行引擎: local(FastAPI 进程内后台协程, 无需 Redis/worker) / celery(Redis broker)
# 未显式配置时默认 celery(向后兼容既有部署)
TASK_ENGINE: str = str(conf_tasks.get("engine", "celery")).strip().lower()

BROKER_URL: str = conf_tasks.get("broker_url", "memory://")
RESULT_BACKEND: str = conf_tasks.get("result_backend", "cache+memory://")

_celery_app = None  # Celery 实例缓存(首次访问 app 时才创建)


def _build_celery_app():
    """惰性创建 Celery 实例

    celery 库与实例创建延迟到首次访问, engine=local 时 Web 进程全程不加载 celery
    """
    from celery import Celery

    app = Celery(
        "base_server",
        broker=BROKER_URL,
        backend=RESULT_BACKEND,
        # 导入各模块注册的任务(按需追加)
        include=["module_task.tasks.demo", "module_rag.tasks.project_document", "module_rag.tasks.project_document_chunk"],
    )

    # 序列化与结果过期配置
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        result_expires=3600,
        timezone="Asia/Shanghai",
        # 默认队列(与 app_task.py worker 消费的队列一致)
        task_default_queue="task_queue",
        broker_connection_retry_on_startup=True,
        # 任务优先级(Redis 分级队列): priority 0~9, 数值越大越先被消费;
        # 生产者(send_task)与消费者(worker)共用本配置, 分级子队列语义一致
        broker_transport_options={
            "priority_steps": list(range(10)),
            "queue_order_strategy": "priority",
        },
        task_inherit_parent_priority=True,
    )

    logger.info(f"ok...tasks celery配置加载完成 broker={BROKER_URL}")
    return app


def __getattr__(name: str):
    """PEP 562 模块级惰性属性: `from common.config.tasks import app` 访问时才触发创建"""
    if name == "app":
        global _celery_app
        if _celery_app is None:
            _celery_app = _build_celery_app()
        return _celery_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


async def refresh_tasks_runtime() -> None:
    """从动态配置刷新任务引擎快照(init_runtime 装配时与配置更新钩子调用)"""
    try:
        from common.config.dynamic import get_settings
        from common.config.dynamic.schemas import TasksSettings

        s = await get_settings(TasksSettings)
        engine, broker, backend = s.engine, s.broker_url, s.result_backend
    except Exception:
        return  # runtime/动态配置未就绪(如纯 import 场景), 保留 yaml 兜底值
    global TASK_ENGINE, BROKER_URL, RESULT_BACKEND
    TASK_ENGINE, BROKER_URL, RESULT_BACKEND = engine, broker, backend
    logger.info(f"任务引擎快照已刷新: engine={engine}")


def invalidate_celery_app() -> None:
    """配置更新钩子: 使缓存的 celery app 失效, 下次访问 app 时按新参数重建"""
    global _celery_app
    _celery_app = None
