from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import aliased
from sqlmodel import select, func, update, delete
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    PaginationParams,
    ScrollDirection,
)
from common.config.db import DaoRel
from module_nlp.do.synonym import (
    SynonymGroup,
    SynonymGroupCreate,
    SynonymGroupUpdate,
    SynonymGroupBatchDelete,
    Synonym,
    SynonymCreate,
    SynonymBatchCreate,
    SynonymBatchDelete,
)


class SynonymGroupDao:
    @DaoRel
    async def add(
        self, synonym_group: SynonymGroupCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增同义词组记录
        :param synonym_group: 同义词组创建数据
        :param session: 可选数据库会话
        :return: 新创建同义词组的ID
        """
        db_synonym_group = SynonymGroup.model_validate(
            synonym_group.model_dump(exclude_unset=True)
        )
        session.add(db_synonym_group)
        await session.flush()
        return db_synonym_group.id

    @DaoRel
    async def delete(self, id: str, session: AsyncSession | None = None) -> None:
        """
        删除同义词组及组内所有同义词
        :param id: 要删除的同义词组ID
        :param session: 可选数据库会话
        """
        synonym_group = await session.get(SynonymGroup, id)
        if not synonym_group:
            raise ValueError(f"未找到ID为 {id} 的同义词组")

        # 删除组内所有同义词
        stmt = delete(Synonym).where(Synonym.group_id == id)
        await session.exec(stmt)

        await session.delete(synonym_group)
        await session.flush()

    @DaoRel
    async def delete_by_id_and_pid(
        self, id: str, pid: str, session: AsyncSession | None = None
    ) -> None:
        """
        通过ID和项目ID删除同义词组及组内所有同义词
        :param id: 要删除的同义词组ID
        :param pid: 项目ID
        :param session: 可选数据库会话
        """
        synonym_group = await session.get(SynonymGroup, id)
        if not synonym_group:
            raise ValueError(f"未找到ID为 {id} 的同义词组")
        
        if synonym_group.pid != pid:
            raise ValueError(f"同义词组不属于项目 {pid}")

        # 删除组内所有同义词
        stmt = delete(Synonym).where(Synonym.group_id == id)
        await session.exec(stmt)

        await session.delete(synonym_group)
        await session.flush()

    @DaoRel
    async def batch_delete(
        self, batch_delete: SynonymGroupBatchDelete, session: AsyncSession | None = None
    ) -> int:
        """
        批量删除同义词组及组内所有同义词
        :param batch_delete: 批量删除同义词组请求模型
        :param session: 可选数据库会话
        :return: 实际删除的记录数
        """
        # 先获取所有同义词组ID
        stmt = select(SynonymGroup.id).where(SynonymGroup.id.in_(batch_delete.ids))
        result = await session.exec(stmt)
        group_ids = [row[0] for row in result.all()]

        if group_ids:
            # 删除所有相关同义词
            stmt = delete(Synonym).where(Synonym.group_id.in_(group_ids))
            await session.exec(stmt)

        # 删除同义词组
        stmt = delete(SynonymGroup).where(SynonymGroup.id.in_(batch_delete.ids))
        result = await session.exec(stmt)
        await session.flush()
        return result.rowcount

    @DaoRel
    async def batch_delete_by_ids_and_pid(
        self, batch_delete: SynonymGroupBatchDelete, pid: str, session: AsyncSession | None = None
    ) -> int:
        """
        通过ID列表和项目ID批量删除同义词组及组内所有同义词
        :param batch_delete: 批量删除同义词组请求模型
        :param pid: 项目ID
        :param session: 可选数据库会话
        :return: 实际删除的记录数
        """
        // 先获取所有符合条件的同义词组ID
        stmt = select(SynonymGroup.id).where(
            SynonymGroup.id.in_(batch_delete.ids),
            SynonymGroup.pid == pid
        )
        result = await session.exec(stmt)
        group_ids = [row[0] for row in result.all()]

        if group_ids:
            // 删除所有相关同义词
            stmt = delete(Synonym).where(Synonym.group_id.in_(group_ids))
            await session.exec(stmt)

            // 删除同义词组
            stmt = delete(SynonymGroup).where(SynonymGroup.id.in_(group_ids))
            result = await session.exec(stmt)
            await session.flush()
            return result.rowcount
        
        return 0

    @DaoRel
    async def update(
        self,
        synonym_group_id: str,
        synonym_group: SynonymGroupUpdate,
        session: AsyncSession | None = None,
    ) -> str:
        """
        直接更新同义词组记录(不先查询)
        :param synonym_group_id: 要更新的同义词组ID
        :param synonym_group: 同义词组更新数据
        :param session: 可选数据库会话
        :return: 更新成功的同义词组ID
        :raises: ValueError 如果同义词组不存在
        """
        update_data = synonym_group.model_dump(exclude_unset=True)
        stmt = (
            update(SynonymGroup)
            .where(SynonymGroup.id == synonym_group_id)
            .values(**update_data)
        )
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {synonym_group_id} 的同义词组")
        await session.flush()

    @DaoRel
    async def get(
        self, id: str, session: AsyncSession | None = None
    ) -> SynonymGroup | None:
        """
        查询单个同义词组
        :param id: 要查询的同义词组ID
        :param session: 可选数据库会话
        :return: 同义词组对象，未找到返回None
        """
        return await session.get(SynonymGroup, id)

    @DaoRel
    async def get_by_id_and_pid(
        self, id: str, pid: str, session: AsyncSession | None = None
    ) -> SynonymGroup | None:
        """
        通过ID和项目ID查询单个同义词组
        :param id: 要查询的同义词组ID
        :param pid: 项目ID
        :param session: 可选数据库会话
        :return: 同义词组对象，未找到返回None
        """
        stmt = select(SynonymGroup).where(SynonymGroup.id == id, SynonymGroup.pid == pid)
        result = await session.exec(stmt)
        return result.first()

    @DaoRel
    async def list_all(
        self, pagination: PaginationParams, session: AsyncSession | None = None
    ) -> list[SynonymGroup]:
        """
        分页查询同义词组列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 同义词组列表
        """
        statement = (
            select(SynonymGroup).offset(pagination.offset).limit(pagination.limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def list_all_by_pid(
        self, pagination: PaginationParams, pid: str, session: AsyncSession | None = None
    ) -> list[SynonymGroup]:
        """
        通过项目ID分页查询同义词组列表
        :param pagination: 分页参数
        :param pid: 项目ID
        :param session: 可选数据库会话
        :return: 同义词组列表
        """
        statement = (
            select(SynonymGroup)
            .where(SynonymGroup.pid == pid)
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def get_scroll(
        self, params: InfiniteScrollParams, session: AsyncSession | None = None
    ) -> list[SynonymGroup]:
        """
        无限滚动分页查询
        :param params: 无限滚动分页参数
        :param session: 可选数据库会话
        :return: 同义词组列表
        """
        statement = select(SynonymGroup)
        sort_by = params.sort_by if params.sort_by else "created_at"

        if params.last_id:
            last_synonym_group = await session.get(SynonymGroup, params.last_id)
            if not last_synonym_group:
                raise ValueError(f"未找到ID为 {params.last_id} 的同义词组")

            sort_value = getattr(last_synonym_group, sort_by)
            search_value = getattr(SynonymGroup, sort_by)
            condition = None
            if params.direction == ScrollDirection.UP:
                condition = search_value > sort_value
            else:
                condition = search_value < sort_value
            statement = statement.where(condition)

        order = None
        if params.direction == ScrollDirection.UP:
            order = getattr(SynonymGroup, sort_by).asc()
        else:
            order = getattr(SynonymGroup, sort_by).desc()

        statement = statement.order_by(order)
        statement = statement.limit(params.limit + 1)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None) -> int:
        """
        统计同义词组总数
        :param session: 可选数据库会话
        :return: 同义词组总数量
        """
        statement = select(func.count()).select_from(SynonymGroup)
        result = await session.exec(statement)
        return result.one()


class SynonymDao:
    @DaoRel
    async def add(
        self, synonym: SynonymCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增单个同义词记录
        :param synonym: 同义词创建数据
        :param session: 可选数据库会话
        :return: 新创建同义词的ID
        """
        db_synonym = Synonym.model_validate(synonym.model_dump(exclude_unset=True))
        session.add(db_synonym)
        await session.flush()
        return db_synonym.id

    @DaoRel
    async def batch_add(
        self, batch_create: SynonymBatchCreate, session: AsyncSession | None = None
    ) -> list[str]:
        """
        批量新增同义词记录
        :param batch_create: 批量创建同义词请求模型
        :param session: 可选数据库会话
        :return: 新创建同义词的ID列表
        """
        synonyms = [
            Synonym(
                pid=batch_create.pid,
                group_id=batch_create.group_id,
                word=word,
                language=batch_create.language,
            )
            for word in batch_create.words
        ]
        session.add_all(synonyms)
        await session.flush()
        return [synonym.id for synonym in synonyms]

    @DaoRel
    async def delete(self, id: str, session: AsyncSession | None = None) -> None:
        """
        删除同义词
        :param id: 要删除的同义词ID
        :param session: 可选数据库会话
        """
        synonym = await session.get(Synonym, id)
        if not synonym:
            raise ValueError(f"未找到ID为 {id} 的同义词")
        await session.delete(synonym)
        await session.flush()

    @DaoRel
    async def delete_by_id_and_pid(
        self, id: str, pid: str, session: AsyncSession | None = None
    ) -> None:
        """
        通过ID和项目ID删除同义词
        :param id: 要删除的同义词ID
        :param pid: 项目ID
        :param session: 可选数据库会话
        """
        stmt = delete(Synonym).where(Synonym.id == id, Synonym.pid == pid)
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {id} 且项目ID为 {pid} 的同义词")
        await session.flush()

    @DaoRel
    async def batch_delete(
        self, batch_delete: SynonymBatchDelete, session: AsyncSession | None = None
    ) -> int:
        """
        批量删除同义词记录
        :param batch_delete: 批量删除同义词请求模型
        :param session: 可选数据库会话
        :return: 实际删除的记录数
        """
        stmt = delete(Synonym).where(Synonym.id.in_(batch_delete.ids))
        result = await session.exec(stmt)
        await session.flush()
        return result.rowcount

    @DaoRel
    async def batch_delete_by_ids_and_pid(
        self, batch_delete: SynonymBatchDelete, pid: str, session: AsyncSession | None = None
    ) -> int:
        """
        通过ID列表和项目ID批量删除同义词
        :param batch_delete: 批量删除同义词请求模型
        :param pid: 项目ID
        :param session: 可选数据库会话
        :return: 实际删除的记录数
        """
        stmt = delete(Synonym).where(
            Synonym.id.in_(batch_delete.ids),
            Synonym.pid == pid
        )
        result = await session.exec(stmt)
        await session.flush()
        return result.rowcount

    @DaoRel
    async def get(self, id: str, session: AsyncSession | None = None) -> Synonym | None:
        """
        查询单个同义词
        :param id: 要查询的同义词ID
        :param session: 可选数据库会话
        :return: 同义词对象，未找到返回None
        """
        return await session.get(Synonym, id)

    @DaoRel
    async def list_by_group(
        self,
        group_id: str,
        pagination: PaginationParams,
        session: AsyncSession | None = None,
    ) -> list[Synonym]:
        """
        根据同义词组ID查询同义词列表
        :param group_id: 同义词组ID
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 同义词列表
        """
        statement = (
            select(Synonym)
            .where(Synonym.group_id == group_id)
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def search_by_word(
        self,
        word: str,
        pid: str,
        language: str | None = None,
        session: AsyncSession | None = None,
    ) -> list[Synonym]:
        """
        根据词语搜索同义词组的所有同义词
        :param word: 要搜索的词语
        :param pid: 项目ID
        :param language: 语言代码 (可选)
        :param session: 可选数据库会话
        :return: 该词语所在同义词组的所有同义词列表
        """
        # 创建别名以区分条件表与结果表
        source = aliased(Synonym)

        # 构建连接查询：通过 group_id 关联，筛选源表词语
        statement = (
            select(Synonym)
            .join(source, Synonym.group_id == source.group_id)
            .where(source.word == word)
            .where(source.pid == pid)
        )

        if language:
            statement = statement.where(source.language == language)

        # 执行查询并去重，防止源表匹配多条导致结果重复
        result = await session.exec(statement.distinct())
        return result.all()

    @DaoRel
    async def batch_search_by_words(
        self,
        words: list[str],
        pid: str,
        language: str | None = None,
        session: AsyncSession | None = None,
    ) -> list[Synonym]:
        """
        批量根据词语搜索其所在同义词组的所有同义词
        :param words: 要搜索的词语列表
        :param pid: 项目ID
        :param language: 语言代码 (可选)
        :param session: 可选数据库会话
        :return: 所有词语所在同义词组的所有同义词列表
        """
        # 构建子查询：distinct获取匹配词语的唯一 group_id 集合
        subquery = (
            select(Synonym.group_id)
            .where(Synonym.word.in_(words))
            .where(Synonym.pid == pid)
            .distinct()
        )
        if language:
            subquery = subquery.where(Synonym.language == language)

        # 主查询：通过 group_id 集合筛选最终结果
        statement = select(Synonym).where(Synonym.group_id.in_(subquery))
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def get_synonyms_by_group(
        self, group_id: str, session: AsyncSession | None = None
    ) -> list[str]:
        """
        获取同义词组的所有同义词(仅返回词语列表)
        :param group_id: 同义词组ID
        :param session: 可选数据库会话
        :return: 同义词词语列表
        """
        statement = select(Synonym.word).where(Synonym.group_id == group_id)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None) -> int:
        """
        统计同义词总数
        :param session: 可选数据库会话
        :return: 同义词总数量
        """
        statement = select(func.count()).select_from(Synonym)
        result = await session.exec(statement)
        return result.one()
