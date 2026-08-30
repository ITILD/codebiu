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
    async def list_by_pid(
        self,
        pid: str | None,
        pagination: PaginationParams,
        name: str | None = None,
        session: AsyncSession | None = None,
    ) -> list[FileEntry]:
        """
        分页查询指定目录下的条目(目录排前,名称排序)
        :param pid: 父目录ID(为空表示根目录)
        :param pagination: 分页参数
        :param name: 名称模糊过滤(为空不过滤)
        :param session: 可选数据库会话
        :return: 条目列表
        """
        # pid 为空时匹配根级条目(数据库中以 NULL/空串存储)
        pid_condition = (
            FileEntry.pid == pid if pid else FileEntry.pid.is_(None) | (
                FileEntry.pid == ""
            )
        )
        conditions = [FileEntry.is_active == True, pid_condition]  # noqa: E712
        if name:
            conditions.append(FileEntry.name.ilike(f"%{name}%"))
        statement = (
            select(FileEntry)
            .where(*conditions)
            .order_by(FileEntry.is_directory.desc(), FileEntry.name.asc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count_by_pid(
        self,
        pid: str | None,
        name: str | None = None,
        session: AsyncSession | None = None,
    ) -> int:
        """
        统计指定目录下的条目总数
        :param pid: 父目录ID(为空表示根目录)
        :param name: 名称模糊过滤(为空不过滤)
        :param session: 可选数据库会话
        :return: 条目总数
        """
        pid_condition = (
            FileEntry.pid == pid if pid else FileEntry.pid.is_(None) | (
                FileEntry.pid == ""
            )
        )
        conditions = [FileEntry.is_active == True, pid_condition]  # noqa: E712
        if name:
            conditions.append(FileEntry.name.ilike(f"%{name}%"))
        statement = select(func.count(FileEntry.id)).where(*conditions)
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def exists_by_pid_name(
        self,
        pid: str | None,
        name: str,
        exclude_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> bool:
        """
        检查指定目录下是否已存在同名活跃条目
        :param pid: 父目录ID(为空表示根目录)
        :param name: 条目名称
        :param exclude_id: 排除自身ID(重命名场景)
        :param session: 可选数据库会话
        :return: 是否存在同名条目
        """
        pid_condition = (
            FileEntry.pid == pid if pid else FileEntry.pid.is_(None) | (
                FileEntry.pid == ""
            )
        )
        conditions = [
            FileEntry.is_active == True,  # noqa: E712
            pid_condition,
            FileEntry.name == name,
        ]
        if exclude_id:
            conditions.append(FileEntry.id != exclude_id)
        statement = select(func.count(FileEntry.id)).where(*conditions)
        result = await session.exec(statement)
        return result.one() > 0

    @DaoRel
    async def list_dirs_by_pid(
        self, pid: str | None, session: AsyncSession | None = None
    ) -> list[FileEntry]:
        """
        查询指定目录下的全部子目录(不分页,用于目录树选择)
        :param pid: 父目录ID(为空表示根目录)
        :param session: 可选数据库会话
        :return: 子目录列表
        """
        pid_condition = (
            FileEntry.pid == pid if pid else FileEntry.pid.is_(None) | (
                FileEntry.pid == ""
            )
        )
        statement = (
            select(FileEntry)
            .where(
                FileEntry.is_active == True,  # noqa: E712
                pid_condition,
                FileEntry.is_directory == True,  # noqa: E712
            )
            .order_by(FileEntry.name.asc())
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def update_children_path_prefix(
        self,
        old_prefix: str,
        new_prefix: str,
        session: AsyncSession | None = None,
    ) -> int:
        """
        批量更新子树逻辑路径前缀(目录重命名/移动时同步子孙路径)
        :param old_prefix: 原目录逻辑路径(如 /a/b)
        :param new_prefix: 新目录逻辑路径(如 /a/c)
        :param session: 可选数据库会话
        :return: 更新的条目数量
        """
        # 仅匹配该目录的直接与间接子孙(以 old_prefix/ 开头)
        statement = select(FileEntry).where(
            FileEntry.is_active == True,  # noqa: E712
            FileEntry.logical_path.like(f"{old_prefix}/%"),
        )
        result = await session.exec(statement)
        rows = result.all()
        # 逐条在应用层替换前缀(避免方言相关的SQL字符串函数)
        prefix_len = len(old_prefix)
        for row in rows:
            row.logical_path = new_prefix + row.logical_path[prefix_len:]
        session.add_all(rows)
        await session.flush()
        return len(rows)

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
        # 注意: 模型中父级字段为 pid
        stmt = text("""
            WITH RECURSIVE subtree AS (
                SELECT id FROM file_entry
                WHERE id = :folder_id AND is_active = TRUE
                UNION ALL
                SELECT fe.id FROM file_entry fe
                INNER JOIN subtree s ON fe.pid = s.id
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
        # 软删除标志字段为 is_active
        stmt = update(FileEntry).where(FileEntry.id.in_(ids)).values(is_active=False)
        await session.exec(stmt)

    @DaoRel
    async def get_content_hashes_by_ids(
        self, ids: list[str], session: AsyncSession
    ) -> list[str]:
        """根据文件 ID 列表获取去重后的 content_hash 列表（仅非目录项）"""
        stmt = (
            select(FileEntry.content_hash)
            .distinct()
            .where(
                FileEntry.id.in_(ids),
                FileEntry.is_directory == False,  # noqa: E712
                FileEntry.content_hash.isnot(None),
            )
        )
        result = await session.execute(stmt)
        return [row[0] for row in result.fetchall()]
