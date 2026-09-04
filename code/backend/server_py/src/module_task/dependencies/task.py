from fastapi import Depends

from module_task.dao.task import TaskQueueDao
from module_task.service.task import TaskQueueService


async def get_task_queue_dao() -> TaskQueueDao:
    """任务队列DAO工厂"""
    return TaskQueueDao()


async def get_task_queue_service(
    dao: TaskQueueDao = Depends(get_task_queue_dao),
) -> TaskQueueService:
    """任务队列Service工厂"""
    return TaskQueueService(dao)
