from fastapi import Depends, status, HTTPException, APIRouter
from common.enum.platform import PlatformId
from common.utils.sys.do.status import HardwareStatus, NetworkStatus
from common.config.server import app
from module_main.dependencies.status import get_status_service_singleton
from module_main.do.status import StatusServer
from module_main.service.status import StatusService

router = APIRouter()


@router.get("/cache", summary="获取主机状态60秒缓存")
async def status_cache(
    status_service: StatusService = Depends(get_status_service_singleton),
) -> StatusServer:
    """获取主机综合状态(60秒缓存版本,避免频繁采集)"""
    try:
        return await status_service.status_cache()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/sys-info", summary="获取主机型号")
async def sys_info(
    status_service: StatusService = Depends(get_status_service_singleton),
) -> PlatformId:
    """获取主机型号信息(平台/厂商/型号)"""
    return await status_service.sys_info()
@router.get("/hardware-status", summary="获取硬件状态")
async def hardware_status(
    status_service: StatusService = Depends(get_status_service_singleton),
) -> HardwareStatus:
    """获取硬件状态(CPU/内存/磁盘等使用率)"""
    try:
        return await status_service.hardware_status()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# 获取网络状态
@router.get("/network-status", summary="获取网络状态")
async def network_status(
    status_service: StatusService = Depends(get_status_service_singleton),
) -> list[NetworkStatus]:
    """获取网络状态(网卡列表及流量统计)"""
    try:
        return await status_service.network_status()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
# 查看挂载数量
@router.get("/mount-count", summary="查看app挂载路由")
async def mount_count(
    status_service: StatusService = Depends(get_status_service_singleton),
) -> list:
    """查看当前 app 已挂载的路由数量(用于调试模块挂载情况)"""
    try:
        return await status_service.mount_count(app)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

app.include_router(router, prefix="/server-status", tags=["server-status"])
