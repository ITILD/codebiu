from sqlmodel import SQLModel, create_engine, Session
import sqlite3
import sqlite_vec
from sqlalchemy import text

# 初始化 SQLite 连接并加载扩展
conn = sqlite3.connect(":memory:")
conn.enable_load_extension(True)
sqlite_vec.load(conn)
conn.enable_load_extension(False)

# 获取版本信息
sqlite_version, vec_version = conn.execute(
    "select sqlite_version(), vec_version()"
).fetchone()
print(f"sqlite_version={sqlite_version}, vec_version={vec_version}")

# 创建虚拟表(8维向量)
conn.execute("CREATE VIRTUAL TABLE vec_examples USING vec0(sample_embedding float[8] distance_metric=cosine)")

# 创建 SQLModel 引擎
engine = create_engine("sqlite://", creator=lambda: conn)

# 准备测试数据
items = [
    (1, '[-0.200, 0.250, 0.341, -0.211, 0.645, 0.935, -0.316, -0.924]'),
    (2, '[0.443, -0.501, 0.355, -0.771, 0.707, -0.708, -0.185, 0.362]'),
    (3, '[0.716, -0.927, 0.134, 0.052, -0.669, 0.793, -0.634, -0.162]'),
    (4, '[-0.710, 0.330, 0.656, 0.041, -0.990, 0.726, 0.385, -0.958]'),
]
query = '[-0.710, 0.330, 0.656, 0.041, -0.990, 0.726, 0.385, -0.958]'

# 插入数据
with Session(engine) as session:
    for item_id, embedding_str in items:
        stmt = text("INSERT INTO vec_examples(rowid, sample_embedding) VALUES (:id, :embedding)")
        stmt = stmt.bindparams(id=item_id, embedding=embedding_str)
        session.exec(stmt)
    session.commit()

# 执行查询
with Session(engine) as session:
    stmt = text("""
        SELECT
            rowid,
            distance
        FROM vec_examples
        WHERE sample_embedding MATCH :query
        ORDER BY distance
        LIMIT :limit
    """)
    stmt = stmt.bindparams(query=query, limit=2)
    result = session.exec(stmt)
    rows = result.all()
    print("查询结果:", rows)