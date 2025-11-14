from sqlmodel import and_, func, text
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection


class DBPostgreVector:
    async def create_index(
        self,
        conn: AsyncConnection,
        tablename="document",
        embedding_col="embedding",
        schema="public",
        m=16,
        ef_construction=64,
    ):
        # m = 16: 每个节点在图中将连接的边数(默认16) 取值范围：4-100 值越大，索引越精确但占用更多内存
        # ef_construction = 64: 构建索引时考虑的候选节点数(默认64) 取值范围：50-400 值越大，构建质量越高但构建时间越长
        index_name = f"{tablename}_{embedding_col}_hnsw_idx"
        # 检查索引是否已存在
        index_exists = await conn.scalar(
            text(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_indexes 
                        WHERE schemaname = '{schema}'
                        AND tablename = :tablename 
                        AND indexname = :index_name
                    )
                """).bindparams(tablename=tablename, index_name=index_name)
        )

        if not index_exists:
            await conn.execute(
                text(f"""
                        CREATE INDEX {index_name}
                        ON {schema}.{tablename} USING hnsw ( {embedding_col} vector_cosine_ops) 
                        WITH (m = {m}, ef_construction = {ef_construction})
                    """)
            )
            print(f"{index_name} HNSW created successfully")
        else:
            print(f"{index_name} HNSW exists already, no need to create")

    async def cosine(
        self,
        session: AsyncSession,
        model_in,
        model_out,
        search_vector,
        ntype,
        pids=["proj_1"],
        limit=3,
    ):
        # print(search_vector)
        """cosine similarity search"""
        query = (
            select(
                model_in.id,
                model_in.content,
                (1.0 - model_in.embedding.cosine(search_vector)).label("similarity"),
                model_in.node_id,
            )
            .where(model_in.pid.in_(pids))
            # 如果 ntype 为 None，则不添加 ntype 过滤条件
            .where(model_in.ntype == ntype if ntype else True)
            # 添加相似度过滤条件：1 - cosine距离 > 0.6
            .where(
                model_in.embedding.cosine(search_vector) < 0.7
            )  # 等价于 similarity > 0.3
            # .where(model_in.embedding.cosine(search_vector) < 0.5)  # 等价于 similarity > 0.3
            .order_by(model_in.embedding.l2(search_vector))
            # .order_by(model_in.embedding.cosine(search_vector))
            .limit(limit)
        )
        # log
        # sql = str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        # print("SQL 语句:")
        # logger.info(sql)
        # # results =await session.exec(text(sql))
        results = await session.exec(query)
        # 结果转换为DocumentSelect对象
        document_selects = []
        for row in results:
            document_selects.append(model_out(**row._asdict()))
        return document_selects

    async def cosine_by_node_ids(
        self,
        session: AsyncSession,
        model_in,
        model_out,
        search_vector,
        ntype,
        node_ids=[],
        limit=3,
    ):
        # print(search_vector)
        """cosine similarity search"""
        query = (
            select(
                model_in.id,
                model_in.content,
                (1.0 - model_in.embedding.cosine(search_vector)).label("similarity"),
                model_in.node_id,
                model_in.ntype,
                model_in.path,
                model_in.name,
            )
            .where(model_in.node_id.in_(node_ids))
            # 如果 ntype 为 None，则不添加 ntype 过滤条件
            .where(model_in.ntype == ntype if ntype else True)
            # .where(model_in.embedding.cosine(search_vector) < 0.5)  # 等价于 similarity > 0.3
            .order_by(model_in.embedding.l2(search_vector))
            # .order_by(model_in.embedding.cosine(search_vector))
            .limit(limit)
        )
        results = await session.exec(query)
        # 结果转换为DocumentSelect对象
        document_selects = []
        for row in results:
            document_selects.append(model_out(**row._asdict()))
        return document_selects

    async def tsquery(
        self,
        session: AsyncSession,
        model_in,
        model_out,
        keyWord,
        ntype,
        pids=["proj_1"],
        limit=3,
    ):
        # print(search_vector)
        """cosine similarity search"""
        placeholders = ""
        for pid in pids:
            placeholders += f"'{pid}'"
            # 如果还有更多的pid，则添加逗号
            if pid != pids[-1]:
                placeholders += ","

        keyWordSql = f"""
            SELECT id,node_id ,content,ntype,path,name,
            ts_rank(body_tsvector, to_tsquery('{keyWord}') ) AS similarity
            FROM document
            WHERE body_tsvector  @@ to_tsquery('{keyWord}') 
            and pid IN ({placeholders})
            order by similarity desc 
            limit {limit}
            """
        keyWordresult = await session.exec(text(keyWordSql))
        document_selects = []
        # for row in keyWordresult:
        #     document_selects.append(row._asdict())
        # # 结果转换为DocumentSelect对象

        for row in keyWordresult:
            document_selects.append(model_out(**row._asdict()))
        return document_selects

    async def tsquery_sm(
        self,
        session: AsyncSession,
        model_in,
        model_out,
        keyWord,
        ntype,
        pids=["proj_1"],
        limit=3,
    ):
        """cosine similarity search"""

        # 使用 SQLModel 的查询方式
        query = (
            select(
                model_in.id,
                model_in.node_id,
                model_in.content,
                model_in.ntype,
                model_in.path,
                model_in.name,
                func.ts_rank(model_in.body_tsvector, func.to_tsquery(keyWord)).label(
                    "similarity"
                ),
            )
            .where(
                and_(
                    model_in.body_tsvector.op("@@")(func.to_tsquery(keyWord)),
                    model_in.pid.in_(pids),
                )
            )
            .order_by(
                func.ts_rank(model_in.body_tsvector, func.to_tsquery(keyWord)).desc()
            )
            .limit(limit)
        )

        results = await session.exec(query)
        document_selects = []

        for row in results:
            document_selects.append(model_out(**row._asdict()))
        return document_selects


if __name__ == "__main__":
    pass
