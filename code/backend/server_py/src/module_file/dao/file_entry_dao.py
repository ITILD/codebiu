from sqlmodel.ext.asyncio.session import AsyncSession
from common.config.db import DaoRel
from sqlmodel import select, func, update, delete, text
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    PaginationParams,
    ScrollDirection,
)
from module_file.do.filesystem import (
    FileEntry,
    FileEntryCreate,
    FileEntryUpdate,
    FileContent,
    FileEntryWithContent,
)


class FileEntryDao:
    @DaoRel
    async def add(
        self, file: FileEntryCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增文件记录
        :param file: 文件创建数据
        :param session: 可选数据库会话
        :return: 新创建文件的ID
        """
        db_file = FileEntry.model_validate(file.model_dump(exclude_unset=True))
        session.add(db_file)
        await session.flush()
        return db_file.id

    @DaoRel
    async def delete(self, id, session: AsyncSession | None = None) -> str:
        """
        删除文件记录
        :param id: 要删除的文件ID
        :param session: 可选数据库会话
        """
        result = await session.exec(delete(FileEntry).where(FileEntry.id == id))
        if result.rowcount == 0:
            raise ValueError(f"File with ID '{id}' not found")

    @DaoRel
    async def soft_delete(self, id, session: AsyncSession | None = None):
        """
        删除文件记录
        :param id: 要删除的文件ID
        :param session: 可选数据库会话
        """
        stmt = update(FileEntry).where(FileEntry.id == id).values(is_active=False)
        await session.exec(stmt)

    @DaoRel
    async def update(
        self,
        file_content_id: str,
        file: FileEntryUpdate,
        session: AsyncSession | None = None,
    ):
        """
        更新文件记录
        :param file_content_id: 要更新的文件ID
        :param file: 文件更新数据
        :param session: 可选数据库会话
        :return: 更新成功的文件ID
        :raises: ValueError 如果文件不存在
        """
        # 准备更新数据(排除未设置的字段)
        update_data = file.model_dump(exclude_unset=True)

        # 执行直接更新
        stmt = (
            update(FileEntry)
            .where(FileEntry.id == file_content_id)
            .values(**update_data)
        )

        result = await session.exec(stmt)

        # 检查是否实际更新了记录
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {file_content_id} 的文件")
        await session.flush()

    @DaoRel
    async def get(self, id, session: AsyncSession | None = None) -> FileEntry | None:
        """
        查询单个文件
        :param id: 要查询的文件ID
        :param session: 可选数据库会话
        :return: 文件对象，未找到返回None
        """
        return await session.get(FileEntry, id)

    @DaoRel
    async def list_all(
        self, pagination: PaginationParams, session: AsyncSession | None = None
    ) -> list:
        """
        分页查询文件列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 文件列表
        """
        statement = select(FileEntry).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def get_scroll(
        self, params: InfiniteScrollParams, session: AsyncSession | None = None
    ) -> list:
        """
        滚动加载文件列表
        :param params: 滚动参数
        :param session: 可选数据库会话
        :return: 文件列表
        """
        statement = select(FileEntry)
        # 设置默认排序字段为 created_at
        sort_by = params.sort_by if params.sort_by else "created_at"
        # 根据游标
        if params.last_id:
            last_file = await session.get(FileEntry, params.last_id)
            if not last_file:
                raise ValueError(f"未找到ID为 {params.last_id} 的文件")

            # 获取排序字段的值
            sort_value = getattr(last_file, sort_by)
            search_value = getattr(FileEntry, sort_by)
            condition = None
            if params.direction == ScrollDirection.UP:
                condition = search_value > sort_value
            else:
                condition = search_value < sort_value
            statement = statement.where(condition)
        # 正反排序
        order = None
        if params.direction == ScrollDirection.UP:
            # 升序：从小到大，从早到晚
            order = getattr(FileEntry, sort_by).asc()
        else:
            order = getattr(FileEntry, sort_by).desc()
        statement = statement.order_by(order)
        # 限制结果数量  实际查询 limit + 1 条
        statement = statement.limit(params.limit + 1)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None) -> int:
        """
        获取文件总数
        :param session: 可选数据库会话
        :return: 文件总数
        """
        statement = select(func.count(FileEntry.id))
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def get_by_content_hash_and_filesize(
        self,
        content_hash: str,
        file_size_bytes: int,
        session: AsyncSession | None = None,
    ) -> FileEntry | None:
        """
        根据内容哈希值和文件大小查询文件(用于文件去重)
        :param content_hash: 文件内容哈希值
        :param session: 可选数据库会话
        :return: 文件对象，未找到返回None
        """
        statement = select(FileEntry).where(
            FileEntry.content_hash == content_hash,
            FileEntry.file_size_bytes == file_size_bytes,
        )
        result = await session.exec(statement)
        return result.first()

    @DaoRel
    async def get_file_entry_with_content(
        self, file_id: str, session: AsyncSession | None = None
    ) -> FileEntryWithContent | None:
        """
        根据文件ID查询文件记录(包含文件内容记录)
        :param file_id: 文件ID
        :param session: 可选数据库会话
        :return: 文件记录和内容记录
        """
        query = (
            select(FileEntry, FileContent)
            .join(
                FileContent,
                FileEntry.content_hash == FileContent.content_hash,
                isouter=True,
            )
            .where(FileEntry.id == file_id)
        )
        result = await session.exec(query)
        row = result.first()
        if not row or not row[0]:
            return None
        return FileEntryWithContent.from_models(entry=row[0], content=row[1])

    @DaoRel
    async def get_subtree_ids(
        self, folder_id: str, session: AsyncSession | None = None
    ) -> list[str]:
        """
        获取目录及其所有子项的 ID 列表（深度优先）
        假设表结构有 parent_id 字段
        """
        # 使用递归 CTE（Common Table Expression）—— PostgreSQL / SQLite 3.8.3+ / MySQL 8.0+
        # 兼容性说明：SQLite 需启用 recursive_triggers，MySQL 需 8.0+

        """获取目录子树所有 ID（类型安全 + 高性能）"""
        stmt = text("""
            WITH RECURSIVE subtree AS (
                SELECT id FROM file_entry 
                WHERE id = :folder_id AND is_active = TRUE
                UNION ALL
                SELECT fe.id FROM file_entry fe
                INNER JOIN subtree s ON fe.parent_id = s.id
                WHERE fe.is_active = TRUE
            )
            SELECT id FROM subtree;
        """)

        # 使用 session.exec + select(模型字段) 保证返回类型为 list[str]
        result = await session.exec(
            select(FileEntry.id).from_statement(stmt), params={"folder_id": folder_id}
        )
        return result.all()

    @DaoRel
    async def batch_soft_delete(self, ids: list[str], session: AsyncSession) -> None:
        """批量逻辑删除"""
        if not ids:
            return
        stmt = update(FileEntry).where(FileEntry.id.in_(ids)).values(is_deleted=True)
        await session.exec(stmt)

    @DaoRel
    async def get_content_hashes_by_ids(
        self, ids: list[str], session: AsyncSession
    ) -> list[str]:
        """根据文件 ID 列表获取 content_hash 列表（仅非目录项）"""
        stmt = select(FileEntry.content_hash).where(
            FileEntry.id.in_(ids),
            FileEntry.is_directory == False,
            FileEntry.content_hash.isnot(None),
        )
        result = await session.execute(stmt)
        return [row[0] for row in result.fetchall()]
