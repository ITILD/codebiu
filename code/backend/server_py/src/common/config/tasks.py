"""Celery 应用配置(模块级单例)

- broker/backend 从 config.yaml 的 tasks 段读取
- 未配置时默认 memory:// 本地内存队列(无需额外服务,适合开发/测试)
- 生产部署配置 redis 即可,如:
    tasks:
      broker_url: redis://127.0.0.1:6379/1
      result_backend: redis://127.0.0.1:6379/2
"""
import logging

from celery import Celery

from common.config.index import conf

logger = logging.getLogger(__name__)

try:
    conf_tasks = conf.tasks
    if conf_tasks is None:
        conf_tasks = {}
except Exception:
    conf_tasks = {}

BROKER_URL: str = conf_tasks.get("broker_url", "memory://")
RESULT_BACKEND: str = conf_tasks.get("result_backend", "cache+memory://")

app = Celery(
    "base_server",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    # 导入各模块注册的任务(按需追加)
    include=["module_task.tasks.demo"],
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
)

logger.info(f"ok...tasks celery配置加载完成 broker={BROKER_URL}")
