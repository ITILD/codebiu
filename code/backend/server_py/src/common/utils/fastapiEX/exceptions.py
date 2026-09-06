"""统一业务异常与全局异常处理器(FastAPI 扩展)

核心事实: 路由经 app.mount 挂载的子应用, 其异常处理与主应用相互独立
(Starlette ASGI 隔离), 主应用上注册的处理器不会传播。
故提供 BizFastAPI 子类, 让主应用与全部子应用构造时自动注册, 行为一致。
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class BizError(Exception):
    """业务异常基类: 携带 HTTP 状态码, 由全局处理器映射为 {"detail": ...} 响应"""

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str, *, status_code: int | None = None):
        """detail 为给前端展示的错误文案; status_code 可覆盖类默认值"""
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail)


class NotFoundError(BizError):
    """资源不存在 -> 404"""

    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(BizError):
    """资源冲突(重名/状态互斥) -> 409"""

    status_code = status.HTTP_409_CONFLICT


class BusinessError(BizError):
    """一般业务校验失败 -> 400"""

    status_code = status.HTTP_400_BAD_REQUEST


class UnauthorizedError(BizError):
    """未认证 -> 401"""

    status_code = status.HTTP_401_UNAUTHORIZED


class ForbiddenError(BizError):
    """无权限 -> 403"""

    status_code = status.HTTP_403_FORBIDDEN


def register_exception_handlers(target: FastAPI) -> None:
    """向 app(主应用或挂载子应用)注册全局异常处理器, 响应格式与 HTTPException 一致"""

    @target.exception_handler(BizError)
    async def biz_error_handler(request: Request, exc: BizError):
        """业务异常 -> 使用异常自带的 HTTP 状态码"""
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @target.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """历史遗留 ValueError -> 400(DAO/Service 层 not-found 迁移到 NotFoundError 后可收紧)"""
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})

    @target.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        """兜底 500 + 日志。

        HTTPException 正常由内层 ExceptionMiddleware 先行处理到不了这里,
        此处 isinstance 透传属防御性双保险, 绝不吞掉 HTTPException。
        """
        if isinstance(exc, StarletteHTTPException):
            return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})
        logger.exception("未处理异常 %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": str(exc)}
        )


class BizFastAPI(FastAPI):
    """自动注册全局异常处理器的 FastAPI 子类(主应用与挂载子应用统一行为)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        register_exception_handlers(self)
