from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, exists, update
from common.config.db import DaoRel
from module_file.do.filesystem import FileContent, FileContentCreate, FileContentUpdate
from common.enum.task import TaskStatus


class FileContentDao:
    @DaoRel
    async def add(
        self, file: FileContentCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增文件记录
        :param file: 文件创建数据
        :param session: 可选数据库会话
        :return: 新创建文件的hash值
        """
        db_file = FileContent.model_validate(file.model_dump(exclude_unset=True))
        session.add(db_file)
        await session.flush()
        return db_file.content_hash

    @DaoRel
    async def delete(
        self, content_hash: str, session: AsyncSession | None = None
    ) -> str:
        """
        删除文件记录
        :param content_hash: 要删除的文件hash值
        :param session: 可选数据库会话
        """
        file = await session.get(FileContent, content_hash)
        if not file:
            raise ValueError(f"未找到hash值为 {content_hash} 的文件")
        await session.delete(file)
        await session.flush()

    @DaoRel
    async def update(
        self,
        content_hash: str,
        file: FileContentUpdate,
        session: AsyncSession | None = None,
    ):
        """
        物理存储迁移
        :param content_hash: 要更新的文件hash值
        :param file: 文件更新数据
        :param session: 可选数据库会话
        :return: 更新成功的文件ID
        :raises: ValueError 如果文件不存在
        """
        # 准备更新数据(排除未设置的字段)
        update_data = file.model_dump(exclude_unset=True)

        # 执行直接更新
        stmt = (
            update(FileContent)
            .where(FileContent.content_hash == content_hash)
            .values(**update_data)
        )

        result = await session.exec(stmt)

        # 检查是否实际更新了记录
        if result.rowcount == 0:
            raise ValueError(f"未找到hash值为 {content_hash} 的文件")
        await session.flush()

    @DaoRel
    async def get_by_content_hash(
        self,
        content_hash: str,
        session: AsyncSession | None = None,
    ) -> FileContent | None:
        """
        查询单个文件
        :param content_hash: 要查询的文件hash值
        :param session: 可选数据库会话
        :return: 文件对象，未找到返回None
        """
        result = await session.exec(
            select(FileContent).where(FileContent.content_hash == content_hash)
        )
        return result.first()

    # @DaoRel
    # async def is_exist(
    #     self, content_hash: str, session: AsyncSession | None = None
    # ) -> bool:
    #     """
    #     检查文件是否存在
    #     :param content_hash: 要检查的文件hash值
    #     :param session: 可选数据库会话
    #     :return: 如果文件存在则返回True，否则返回False
    #     """
    #     stmt = select(exists().where(FileContent.content_hash == content_hash))
    #     result = await session.exec(stmt)
    #     return result.scalar()

    @DaoRel
    async def ref_count_change(
        self, content_hash: str, change: int = 1, session: AsyncSession | None = None
    ) -> None:
        """
        原子地增加文件引用计数（仅对已完成文件）
        """
        stmt = (
            update(FileContent)
            .where(FileContent.content_hash == content_hash)
            .values(
                ref_count=FileContent.ref_count + change,
                content_status=TaskStatus.SUCCESS,
            )
        )
        result = await session.execute(stmt)

        if result.rowcount == 0:
            raise ValueError(f"未找到可引用的已完成文件: {content_hash}")
