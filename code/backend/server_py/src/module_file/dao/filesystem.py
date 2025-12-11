from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    PaginationParams,
    ScrollDirection,
)
from common.config.db import DaoRel
from module_file.do.file import File, FileCreate, FileUpdate


class FileDao:
    @DaoRel
    async def add(
        self, file: FileCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增文件记录
        :param file: 文件创建数据
        :param session: 可选数据库会话
        :return: 新创建文件的ID
        """
        db_file = File.model_validate(file.model_dump(exclude_unset=True))
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
        file = await session.get(File, id)
        if not file:
            raise ValueError(f"未找到ID为 {id} 的文件")
        await session.delete(file)
        await session.flush()

    @DaoRel
    async def update(
        self,
        file_id: str,
        file: FileUpdate,
        session: AsyncSession | None = None,
    ) -> str:
        """
        更新文件记录
        :param file_id: 要更新的文件ID
        :param file: 文件更新数据
        :param session: 可选数据库会话
        :return: 更新成功的文件ID
        :raises: ValueError 如果文件不存在
        """
        # 准备更新数据(排除未设置的字段)
        update_data = file.model_dump(exclude_unset=True)

        # 执行直接更新
        stmt = update(File).where(File.id == file_id).values(**update_data)

        result = await session.exec(stmt)

        # 检查是否实际更新了记录
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {file_id} 的文件")
        await session.flush()

    @DaoRel
    async def get(self, id, session: AsyncSession | None = None) -> File | None:
        """
        查询单个文件
        :param id: 要查询的文件ID
        :param session: 可选数据库会话
        :return: 文件对象，未找到返回None
        """
        return await session.get(File, id)

    @DaoRel
    async def list_all(
        self, pagination: PaginationParams, session: AsyncSession | None = None
    ) ->list:
        """
        分页查询文件列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 文件列表
        """
        statement = select(File).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def get_scroll(
        self, params: InfiniteScrollParams, session: AsyncSession | None = None
    ) ->list:
        """
        滚动加载文件列表
        :param params: 滚动参数
        :param session: 可选数据库会话
        :return: 文件列表
        """
        statement = select(File)
        # 设置默认排序字段为 created_at
        sort_by = params.sort_by if params.sort_by else "created_at"
        # 根据游标
        if params.last_id:
            last_file = await session.get(File, params.last_id)
            if not last_file:
                raise ValueError(f"未找到ID为 {params.last_id} 的文件")
            
            # 获取排序字段的值
            sort_value = getattr(last_file, sort_by)
            search_value = getattr(File, sort_by)
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
            order = getattr(File, sort_by).asc()
        else:
            order = getattr(File, sort_by).desc()
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
        statement = select(func.count(File.id))
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def get_by_md5(self, md5: str, session: AsyncSession | None = None) -> File | None:
        """
        根据MD5查询文件(用于文件去重)
        :param md5: 文件MD5值
        :param session: 可选数据库会话
        :return: 文件对象，未找到返回None
        """
        statement = select(File).where(File.md5 == md5)
        result = await session.exec(statement)
        return result.first()