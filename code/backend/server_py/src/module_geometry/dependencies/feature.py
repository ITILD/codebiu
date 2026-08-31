from fastapi import Depends

from module_geometry.dao.feature import GeoFeatureDao
from module_geometry.service.feature import GeoFeatureService


async def get_geo_feature_dao() -> GeoFeatureDao:
    """几何要素DAO工厂"""
    return GeoFeatureDao()


async def get_geo_feature_service(
    dao: GeoFeatureDao = Depends(get_geo_feature_dao),
) -> GeoFeatureService:
    """几何要素Service工厂"""
    return GeoFeatureService(dao)
