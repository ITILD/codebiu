import uuid
import geoalchemy2 as ga
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB


class GeoJSONGeometry(SQLModel):
    """A GeoJSON geometry fragment."""

    type: "Point" | "LineString" | "Polygon"
    coordinates: (
        tuple[float, float]
        | list[tuple[float, float]]
        | list[list[tuple[float, float]]]
    )


class Feature(SQLModel, table=True):
    id: uuid.UUID | None = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    pid: uuid.UUID | None = Field(
        nullable=True,
    )
    geometry: bytes = Field(
        sa_type=ga.Geometry,
        nullable=False,
    )
    properties: dict | None = Field(
        default=None,
        sa_type=JSONB,
        nullable=True,
    )
