from fastapi import Depends, status, HTTPException, APIRouter
from common.utils.enum.platform import PlatformId
from common.utils.sys.do.status import HardwareStatus, NetworkStatus
from common.config.server import app
from module_main.dependencies.status import get_status_service_singleton
from module_main.do.status import StatusServer
from module_main.service.status import StatusService

router = APIRouter()


@router.get("/status_cache", summary="获取主机状态60秒缓存")
async def status_cache(
    status_service: StatusService = Depends(get_status_service_singleton),
) -> StatusServer:
    try:
        return await status_service.status_cache()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/sys_info", summary="获取主机型号")
async def sys_info(
    status_service: StatusService = Depends(get_status_service_singleton),
) -> PlatformId:
    return await status_service.sys_info()
@router.get("/hardware_status", summary="获取硬件状态")
async def hardware_status(
    status_service: StatusService = Depends(get_status_service_singleton),
) -> HardwareStatus:
    try:
        return await status_service.hardware_status()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# 获取网络状态
@router.get("/network_status", summary="获取网络状态")
async def network_status(
    status_service: StatusService = Depends(get_status_service_singleton),
) -> list[NetworkStatus]:
    try:
        return await status_service.network_status()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
# 查看挂载数量
@router.get("/mount_count", summary="查看app挂载路由")
async def mount_count(
    status_service: StatusService = Depends(get_status_service_singleton),
) -> list:
    try:
        return await status_service.mount_count(app)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

app.include_router(router, prefix="/server_status", tags=["server_status"])
