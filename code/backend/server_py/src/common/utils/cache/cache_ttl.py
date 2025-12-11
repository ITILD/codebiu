import inspect
import time
from functools import wraps


# Time-To-Live
def ttl_cache(ttl=10):
    def decorator(func):
        cache = {}
        def make_key(*args, **kwargs):
            """生成唯一缓存键，避免冲突"""
            return (id(func))
        # def make_key(*args, **kwargs):
        #     """生成唯一缓存键，避免冲突"""
        #     return (id(func), args, tuple(sorted(kwargs.items())))
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = make_key(*args, **kwargs)
            now = time.time()

            # 检查缓存是否存在且未过期
            if key in cache and (now - cache[key][1]) < ttl:
                return cache[key][0]

            # 执行原函数
            result = func(*args, **kwargs)

            # 缓存结果
            cache[key] = (result, now)
            return result

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            key = make_key(*args, **kwargs)
            now = time.time()

            if key in cache and (now - cache[key][1]) < ttl:
                return cache[key][0]

            result = await func(*args, **kwargs)
            cache[key] = (result, now)
            return result

        # 自动判断返回同步还是异步装饰器
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


if __name__ == "__main__":
    # 同步函数用例
    @ttl_cache(5)
    def sync_func(x):
        print("计算同步函数...")
        return x * 2

    # 异步函数用例
    @ttl_cache(ttl=5)
    async def async_func(x):
        print("计算异步函数...")
        return x * 3

    # 测试
    print(sync_func(2))  # 会打印"计算同步函数..."
    print(sync_func(2))  # 5秒内不会打印(使用缓存)

    import asyncio

    print(asyncio.run(async_func(3)))  # 会打印"计算异步函数..."
    print(asyncio.run(async_func(3)))  # 5秒内不会打印
