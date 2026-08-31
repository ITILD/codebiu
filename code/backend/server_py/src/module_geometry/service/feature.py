from common.utils.db.schema.pagination import (
    PaginationParams,
    PaginationResponse,
)
from module_geometry.dao.feature import GeoFeatureDao
from module_geometry.do.feature import (
    GeoFeatureCreate,
    GeoFeatureResponse,
    GeoFeatureUpdate,
)

# GeoJSON 类型 -> 本模块要素类型
_GEOJSON_TYPES = {"point", "linestring", "polygon"}


def geojson_to_wkt(geometry) -> str:
    """
    GeoJSON 几何体转 WKT 文本(点/线/面)
    :param geometry: GeoJSON 几何体 {type, coordinates}
    :return: WKT 字符串, 如 "POINT(116.4 39.9)"
    :raises ValueError: 类型不支持或坐标结构非法
    """

    def fmt(value: float) -> str:
        """经纬度转字符串(整数也保留一位小数, WKT 合法)"""
        return f"{float(value):.6f}".rstrip("0").rstrip(".")

    def coord(pair) -> str:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            raise ValueError("坐标必须是 [经度, 纬度] 结构")
        return f"{fmt(pair[0])} {fmt(pair[1])}"

    gtype = str(geometry.type).lower()
    coordinates = geometry.coordinates

    if gtype == "point":
        return f"POINT({coord(coordinates)})"

    if gtype == "linestring":
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            raise ValueError("线要素至少需要 2 个顶点")
        return "LINESTRING(" + ", ".join(coord(p) for p in coordinates) + ")"

    if gtype == "polygon":
        if not isinstance(coordinates, list) or not coordinates:
            raise ValueError("面要素至少需要 1 个闭合环")
        rings = []
        for ring in coordinates:
            if not isinstance(ring, list) or len(ring) < 3:
                raise ValueError("面的每个环至少需要 3 个顶点")
            # 首尾不闭合时自动补首点(PostGIS 要求闭合环)
            if ring[0] != ring[-1]:
                ring = list(ring) + [ring[0]]
            rings.append("(" + ", ".join(coord(p) for p in ring) + ")")
        return "POLYGON(" + ", ".join(rings) + ")"

    raise ValueError(f"不支持的几何类型: {geometry.type}(仅支持 Point/LineString/Polygon)")


class GeoFeatureService:
    """几何要素服务(地球点线面绘制数据管理)"""

    def __init__(self, geo_feature_dao: GeoFeatureDao):
        self.geo_feature_dao = geo_feature_dao or GeoFeatureDao()

    async def add(self, data: GeoFeatureCreate, user_id: str) -> str:
        """
        新增几何要素
        :param data: 创建数据(GeoJSON 几何体)
        :param user_id: 创建者用户ID
        :return: 新创建要素ID
        """
        wkt = geojson_to_wkt(data.geometry)
        return await self.geo_feature_dao.add(data, user_id, wkt)

    async def delete(self, feature_id: str) -> None:
        """
        删除几何要素
        :param feature_id: 要素ID
        """
        await self.geo_feature_dao.delete(feature_id)

    async def update(self, feature_id: str, data: GeoFeatureUpdate) -> None:
        """
        更新几何要素(几何体变更时重转 WKT)
        :param feature_id: 要素ID
        :param data: 更新数据(字段可选)
        """
        wkt = geojson_to_wkt(data.geometry) if data.geometry else None
        await self.geo_feature_dao.update(feature_id, data, wkt)

    async def get(self, feature_id: str) -> GeoFeatureResponse | None:
        """
        获取单个几何要素
        :param feature_id: 要素ID
        :return: 要素响应对象, 未找到返回None
        """
        return await self.geo_feature_dao.get(feature_id)

    async def list_all(
        self,
        pagination: PaginationParams,
        keyword: str | None = None,
        feature_type: str | None = None,
    ) -> PaginationResponse:
        """
        分页查询几何要素列表(支持名称模糊/类型精确过滤)
        :param pagination: 分页参数
        :param keyword: 要素名称模糊匹配
        :param feature_type: 几何类型精确过滤
        :return: 分页响应
        """
        if feature_type is not None and feature_type not in _GEOJSON_TYPES:
            raise ValueError(f"无效的几何类型: {feature_type}")
        items = await self.geo_feature_dao.list_all(
            pagination, keyword=keyword, feature_type=feature_type
        )
        total = await self.geo_feature_dao.count(
            keyword=keyword, feature_type=feature_type
        )
        return PaginationResponse.create(items, total, pagination)

    async def list_all_without_page(self) -> list[GeoFeatureResponse]:
        """
        查询全部几何要素(供地球场景一次性渲染)
        :return: 要素响应列表(最多2000条)
        """
        return await self.geo_feature_dao.list_all_without_page()
