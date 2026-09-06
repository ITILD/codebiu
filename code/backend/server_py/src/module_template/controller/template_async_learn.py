import asyncio
import threading
import time

from fastapi.concurrency import run_in_threadpool
from module_template.config.server import module_app
from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# 通用日志函数
def log_info(operation: str, id: str, elapsed: float = None):
    thread_info = f"Thread-{threading.current_thread().ident}({threading.current_thread().name})"
    if elapsed is not None:
        logger.info(f"[{operation}] {id} done in {elapsed:.2f}s | {thread_info}")
    else:
        logger.info(f"[{operation}] {id} start | {thread_info}")

# 模拟同步耗时任务
def sync_heavy_task(task_id: str, duration: float):
    thread_info = f"Thread-{threading.current_thread().ident}({threading.current_thread().name})"
    logger.info(f"[Sync-Heavy-Task] {task_id} start | {thread_info}")
    time.sleep(duration)
    logger.info(f"[Sync-Heavy-Task] {task_id} done | {thread_info}")
    return f"Sync task {task_id} completed"

# 1. 同步耗时接口
@router.get("/sync/{id}/{duration_use}", summary="同步耗时接口(阻塞工作线程)")
def sync_endpoint(id: str, duration_use: float):
    """同步 def 路由: FastAPI 自动丢入线程池执行, 不阻塞事件循环

    Args:
        id: 任务标识
        duration_use: 模拟耗时(秒)
    """
    log_info("Sync", id)
    start_time = time.time()
    result = sync_heavy_task(id, duration_use)
    elapsed = time.time() - start_time
    log_info("Sync", id, elapsed)
    return {"id": id, "result": result}


# 2. 异步耗时接口
@router.get("/async/{id}/{duration_use}", summary="异步耗时接口(await 挂起)")
async def async_endpoint(id: str, duration_use: float):
    """async def 路由: 用 await asyncio.sleep 挂起协程, 期间事件循环可处理其他请求

    Args:
        id: 任务标识
        duration_use: 模拟耗时(秒)
    """
    log_info("Async", id)
    start_time = time.time()
    await asyncio.sleep(duration_use)
    elapsed = time.time() - start_time
    log_info("Async", id, elapsed)
    return {"id": id, "result": f"Async task {id} completed"}


# duration_use. 异步中调用同步任务(阻塞事件循环)
@router.get("/async-sync/{id}/{duration_use}", summary="异步路由中直接调用同步任务(反例:阻塞事件循环)")
async def async_sync_endpoint(id: str, duration_use: float):
    """async def 路由内直接调用 time.sleep 型同步任务: 会卡死事件循环(反面教材)

    Args:
        id: 任务标识
        duration_use: 模拟耗时(秒)
    """
    log_info("Async-Sync", id)
    start_time = time.time()
    result = sync_heavy_task(id, duration_use)
    elapsed = time.time() - start_time
    log_info("Async-Sync", id, elapsed)
    return {"id": id, "result": result}


# 4. 异步中使用线程池运行同步任务
@router.get("/async-threadpool/{id}/{duration_use}", summary="异步路由经线程池运行同步任务(推荐)")
async def async_threadpool_endpoint(id: str, duration_use: float):
    """async def 路由用 run_in_threadpool 把同步任务丢进线程池, 兼顾并发与不阻塞事件循环

    Args:
        id: 任务标识
        duration_use: 模拟耗时(秒)
    """
    log_info("Async-Threadpool", id)
    start_time = time.time()
    result = await run_in_threadpool(sync_heavy_task, id, duration_use)
    elapsed = time.time() - start_time
    log_info("Async-Threadpool", id, elapsed)
    return {"id": id, "result": result}

module_app.include_router(router, prefix="/template-async-learn", tags=["异步多线程并发模板"])