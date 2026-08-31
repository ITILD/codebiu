from fastapi import APIRouter, Depends, HTTPException, Query, status

from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.dependencies.permission import require_permission
from module_geometry.config.server import module_app
from module_geometry.dependencies.feature import get_geo_feature_service
from module_geometry.do.feature import (
    GeoFeatureCreate,
    GeoFeatureResponse,
    GeoFeatureUpdate,
)
from module_geometry.service.feature import GeoFeatureService

router = APIRouter()


@router.post("", summary="创建几何要素", status_code=status.HTTP_201_CREATED, response_model=str)
async def create_geo_feature(
    data: GeoFeatureCreate,
    current_user_id: str = Depends(require_permission("geometry", "feature", "create")),
    service: GeoFeatureService = Depends(get_geo_feature_service),
) -> str:
    """
    创建几何要素(前端地球绘制的点/线/面, 以 GeoJSON 提交)
    :param data: 要素数据(名称 + GeoJSON 几何体)
    :param current_user_id: 当前用户ID(权限依赖注入)
    :param service: 几何要素服务依赖注入
    :return: 新创建要素ID
    """
    try:
        return await service.add(data, current_user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/all", summary="查询全部几何要素", response_model=list[GeoFeatureResponse])
async def list_all_geo_features(
    current_user_id: str = Depends(require_permission("geometry", "feature", "read")),
    service: GeoFeatureService = Depends(get_geo_feature_service),
) -> list[GeoFeatureResponse]:
    """
    查询全部几何要素(不分页, 供地球场景一次性渲染, 最多2000条)
    :param current_user_id: 当前用户ID(权限依赖注入)
    :param service: 几何要素服务依赖注入
    :return: 要素响应列表
    """
    try:
        return await service.list_all_without_page()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/list", summary="分页查询几何要素列表", response_model=PaginationResponse)
async def list_geo_features(
    pagination: PaginationParams = Depends(),
    keyword: str | None = Query(None, max_length=100, description="要素名称模糊搜索"),
    feature_type: str | None = Query(
        None, description="几何类型过滤(point/linestring/polygon)"
    ),
    current_user_id: str = Depends(require_permission("geometry", "feature", "read")),
    service: GeoFeatureService = Depends(get_geo_feature_service),
) -> PaginationResponse:
    """
    分页查询几何要素列表(支持名称/类型多字段过滤)
    :param pagination: 分页参数
    :param keyword: 要素名称模糊搜索
    :param feature_type: 几何类型过滤(point/linestring/polygon)
    :param current_user_id: 当前用户ID(权限依赖注入)
    :param service: 几何要素服务依赖注入
    :return: 分页响应结果
    """
    try:
        return await service.list_all(
            pagination, keyword=keyword, feature_type=feature_type
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{feature_id}", summary="获取单个几何要素", response_model=GeoFeatureResponse)
async def get_geo_feature(
    feature_id: str,
    current_user_id: str = Depends(require_permission("geometry", "feature", "read")),
    service: GeoFeatureService = Depends(get_geo_feature_service),
) -> GeoFeatureResponse:
    """
    获取单个几何要素详情(geometry 以 GeoJSON 返回)
    :param feature_id: 要素ID
    :param current_user_id: 当前用户ID(权限依赖注入)
    :param service: 几何要素服务依赖注入
    :return: 要素详情
    """
    try:
        result = await service.get(feature_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="GeoFeature not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{feature_id}", summary="更新几何要素", status_code=status.HTTP_204_NO_CONTENT)
async def update_geo_feature(
    feature_id: str,
    data: GeoFeatureUpdate,
    current_user_id: str = Depends(require_permission("geometry", "feature", "update")),
    service: GeoFeatureService = Depends(get_geo_feature_service),
) -> None:
    """
    更新几何要素(重命名/重绘几何体)
    :param feature_id: 要素ID
    :param data: 更新数据(字段可选)
    :param current_user_id: 当前用户ID(权限依赖注入)
    :param service: 几何要素服务依赖注入
    """
    try:
        await service.update(feature_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/{feature_id}", summary="删除几何要素", status_code=status.HTTP_204_NO_CONTENT)
async def delete_geo_feature(
    feature_id: str,
    current_user_id: str = Depends(require_permission("geometry", "feature", "delete")),
    service: GeoFeatureService = Depends(get_geo_feature_service),
) -> None:
    """
    删除几何要素
    :param feature_id: 要素ID
    :param current_user_id: 当前用户ID(权限依赖注入)
    :param service: 几何要素服务依赖注入
    """
    try:
        await service.delete(feature_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


module_app.include_router(router, prefix="/features", tags=["几何要素"])
