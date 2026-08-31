import json

from geoalchemy2 import WKTElement
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from common.config.db import DaoRel
from common.utils.db.schema.pagination import PaginationParams
from module_geometry.do.feature import (
    GeoFeature,
    GeoFeatureCreate,
    GeoFeatureUpdate,
    GeoFeatureResponse,
)


class GeoFeatureDao:
    @DaoRel
    async def add(
        self,
        data: GeoFeatureCreate,
        user_id: str,
        wkt: str,
        session: AsyncSession | None = None,
    ) -> str:
        """
        新增几何要素(几何体由 service 预转为 WKT)
        :param data: 创建数据(名称/类型/属性)
        :param user_id: 创建者用户ID
        :param wkt: WKT 格式几何文本(SRID=4326)
        :param session: 可选数据库会话
        :return: 新创建要素的ID
        """
        feature = GeoFeature(
            name=data.name,
            feature_type=data.geometry.type.lower(),
            properties=data.properties,
            user_id=user_id,
            geometry=WKTElement(wkt, srid=4326),
        )
        session.add(feature)
        await session.flush()
        return feature.id

    @DaoRel
    async def delete(self, feature_id: str, session: AsyncSession | None = None) -> None:
        """
        删除几何要素
        :param feature_id: 要素ID
        :param session: 可选数据库会话
        """
        feature = await session.get(GeoFeature, feature_id)
        if not feature:
            raise ValueError(f"未找到ID为 {feature_id} 的几何要素")
        await session.delete(feature)
        await session.flush()

    @DaoRel
    async def update(
        self,
        feature_id: str,
        data: GeoFeatureUpdate,
        wkt: str | None,
        session: AsyncSession | None = None,
    ) -> None:
        """
        更新几何要素(几何体更新时由 service 预转 WKT)
        :param feature_id: 要素ID
        :param data: 更新数据(字段可选)
        :param wkt: WKT 几何文本(为 None 表示不更新几何)
        :param session: 可选数据库会话
        """
        feature = await session.get(GeoFeature, feature_id)
        if not feature:
            raise ValueError(f"未找到ID为 {feature_id} 的几何要素")
        if data.name is not None:
            feature.name = data.name
        if data.properties is not None:
            feature.properties = data.properties
        if wkt is not None:
            feature.geometry = WKTElement(wkt, srid=4326)
            feature.feature_type = data.geometry.type.lower() if data.geometry else feature.feature_type
        session.add(feature)
        await session.flush()

    @DaoRel
    async def get(
        self, feature_id: str, session: AsyncSession | None = None
    ) -> GeoFeatureResponse | None:
        """
        查询单个几何要素(geometry 列经 ST_AsGeoJSON 转为 GeoJSON)
        :param feature_id: 要素ID
        :param session: 可选数据库会话
        :return: 要素响应对象, 未找到返回None
        """
        statement = (
            select(GeoFeature, func.ST_AsGeoJSON(GeoFeature.geometry).label("geojson"))
            .where(GeoFeature.id == feature_id)
        )
        result = await session.exec(statement)
        row = result.first()
        if not row:
            return None
        feature, geojson_text = row
        return self._to_response(feature, geojson_text)

    @DaoRel
    async def list_all(
        self,
        pagination: PaginationParams,
        session: AsyncSession | None = None,
        keyword: str | None = None,
        feature_type: str | None = None,
    ) -> list[GeoFeatureResponse]:
        """
        分页查询几何要素列表(支持名称模糊/类型精确过滤)
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :param keyword: 要素名称模糊匹配
        :param feature_type: 几何类型精确过滤(point/line/polygon)
        :return: 要素响应列表
        """
        statement = select(GeoFeature, func.ST_AsGeoJSON(GeoFeature.geometry).label("geojson"))
        conditions = []
        if keyword:
            conditions.append(GeoFeature.name.contains(keyword))
        if feature_type:
            conditions.append(GeoFeature.feature_type == feature_type)
        if conditions:
            statement = statement.where(*conditions)
        statement = (
            statement.order_by(GeoFeature.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await session.exec(statement)
        return [self._to_response(row[0], row[1]) for row in result.all()]

    @DaoRel
    async def list_all_without_page(
        self, session: AsyncSession | None = None, limit: int = 2000
    ) -> list[GeoFeatureResponse]:
        """
        查询全部几何要素(供地球场景一次性渲染, 最多 limit 条)
        :param session: 可选数据库会话
        :param limit: 最大返回条数
        :return: 要素响应列表
        """
        statement = (
            select(GeoFeature, func.ST_AsGeoJSON(GeoFeature.geometry).label("geojson"))
            .order_by(GeoFeature.created_at.desc())
            .limit(limit)
        )
        result = await session.exec(statement)
        return [self._to_response(row[0], row[1]) for row in result.all()]

    @DaoRel
    async def count(
        self,
        session: AsyncSession | None = None,
        keyword: str | None = None,
        feature_type: str | None = None,
    ) -> int:
        """
        统计几何要素总数(与列表过滤条件保持一致)
        :param session: 可选数据库会话
        :param keyword: 要素名称模糊匹配
        :param feature_type: 几何类型精确过滤
        :return: 要素总数
        """
        conditions = []
        if keyword:
            conditions.append(GeoFeature.name.contains(keyword))
        if feature_type:
            conditions.append(GeoFeature.feature_type == feature_type)
        statement = select(func.count()).select_from(GeoFeature)
        if conditions:
            statement = statement.where(*conditions)
        result = await session.exec(statement)
        return result.one()

    @staticmethod
    def _to_response(feature: GeoFeature, geojson_text: str) -> GeoFeatureResponse:
        """
        ORM 对象转响应模型(geometry 文本转 GeoJSON 几何体)
        :param feature: 数据库要素对象
        :param geojson_text: ST_AsGeoJSON 输出的 GeoJSON 字符串
        :return: 要素响应对象
        """
        geojson = json.loads(geojson_text) if geojson_text else None
        return GeoFeatureResponse(
            id=feature.id,
            name=feature.name,
            feature_type=feature.feature_type,
            properties=feature.properties,
            user_id=feature.user_id,
            geometry=geojson,
            created_at=feature.created_at,
            updated_at=feature.updated_at,
        )
