from sqlalchemy.types import UserDefinedType
from common.utils.db.extention.vector.colum.vector_pg import VectorPG
from common.utils.db.extention.vector.colum.vector_sqlite import VectorSqlite


def get_base_vector_mixin(db_type) -> UserDefinedType:
    if db_type == "postgre":
        return VectorPG
    elif db_type == "sqlite":
        return VectorSqlite
