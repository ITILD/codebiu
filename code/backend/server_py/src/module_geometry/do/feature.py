from datetime import datetime, timezone
from uuid import uuid4

from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, DateTime, Field, SQLModel


class GeoJSONGeometry(SQLModel):
    """
    GeoJSON 几何体(仅支持点/线/面三种基础类型)
    coordinates 结构:
        Point       -> [lon, lat]
        LineString  -> [[lon, lat], ...]
        Polygon     -> [[[lon, lat], ...], ...] (外环在前, 首尾自动闭合)
    """

    type: str = Field(description="几何类型(Point/LineString/Polygon)")
    coordinates: list = Field(description="GeoJSON 坐标(嵌套数字数组)")


class GeoFeatureBase(SQLModel):
    """几何要素基础模型(不含数据库表配置)"""

    name: str = Field(max_length=100, description="要素名称")
    feature_type: str = Field(max_length=10, description="几何类型(point/line/polygon)")
    properties: dict | None = Field(
        default=None,
        sa_column=Column(JSONB),
        description="GeoJSON properties 扩展属性",
    )


class GeoFeature(GeoFeatureBase, table=True):
    """
    几何要素数据库模型(PostGIS 存储, SRID=4326 即 WGS84 经纬度)
    """

    __tablename__ = "geo_feature"

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="唯一标识符",
    )
    user_id: str = Field(index=True, description="创建者用户ID")
    geometry: object = Field(
        sa_column=Column(
            Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True),
            nullable=False,
        ),
        description="PostGIS 空间几何列",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
        description="最后更新时间",
    )


class GeoFeatureCreate(SQLModel):
    """创建几何要素的请求模型(前端传 GeoJSON 几何体)"""

    name: str = Field(max_length=100, description="要素名称")
    geometry: GeoJSONGeometry = Field(description="GeoJSON 几何体")
    properties: dict | None = Field(default=None, description="扩展属性")


class GeoFeatureUpdate(SQLModel):
    """更新几何要素的请求模型(字段全部可选)"""

    name: str | None = Field(default=None, max_length=100, description="要素名称")
    geometry: GeoJSONGeometry | None = Field(default=None, description="GeoJSON 几何体")
    properties: dict | None = Field(default=None, description="扩展属性")


class GeoFeatureResponse(SQLModel):
    """几何要素响应模型(geometry 已转为 GeoJSON)"""

    id: str
    name: str
    feature_type: str
    properties: dict | None
    user_id: str
    geometry: GeoJSONGeometry | None = None
    created_at: datetime
    updated_at: datetime
