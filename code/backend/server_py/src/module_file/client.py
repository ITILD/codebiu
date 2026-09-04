# src/module_file/client.py
# 跨模块文件操作统一入口(其他模块增删改查文件的唯一推荐方式)
#
# 用法(模块内直接导入单例):
#   from module_file.client import file_client
#
#   # 增
#   entry = await file_client.upload_bytes(data, "report.pdf", path="/rag/docs", user_id=uid)
#   entry = await file_client.save_text("hello", "note.txt", path="/notes")
#   folder = await file_client.mkdir("/rag/exports")          # mkdir -p 语义
#
#   # 删
#   await file_client.remove_by_path("/rag/docs/report.pdf")  # 文件
#   await file_client.remove_tree("/rag/exports")             # 目录(递归)
#
#   # 改
#   await file_client.rename(entry_id, "new_name.txt")
#   await file_client.move(entry_id, target_pid) / .copy(entry_id, target_pid)
#
#   # 查
#   entry = await file_client.get_by_path("/rag/docs/report.pdf")
#   data: bytes = await file_client.read_bytes(entry.id)
#   text: str = await file_client.read_text(entry.id)
#   items = await file_client.list_dir(pid) / .list_by_path("/rag/docs")
#
#   # 底层直连(不建虚拟条目,按物理键读写,仅内部场景)
#   await file_client.storage.save("tmp/x.bin", b"...")
#   data = await file_client.storage.load("tmp/x.bin")
import logging

from module_file.do.filesystem import FileEntry, FileEntryUpdate
from module_file.service.filesystem import FileService
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse

logger = logging.getLogger(__name__)


class FileClient:
    """
    文件系统客户端(跨模块操作文件的门面,聚合 FileService 全部能力)

    与存储类型无关: local/rustfs/s3 下的行为完全一致,
    物理文件由 FileService 内部的 StorageInterface 屏蔽。
    """

    def __init__(self, service: FileService | None = None):
        self.service = service or FileService()

    # ============ 底层存储直连(不建虚拟条目,慎用) ============
    @property
    def storage(self):
        """存储接口实例(save/load/exists/delete/iter_chunks)"""
        return self.service.storage

    # ============ 增 ============
    async def upload_bytes(
        self,
        data: bytes,
        filename: str,
        pid: str | None = None,
        path: str | None = None,
        description: str | None = None,
        user_id: str | None = None,
    ) -> FileEntry:
        """
        上传字节内容为文件(内容哈希去重,相同内容秒传)
        :param data: 文件字节内容
        :param filename: 文件名
        :param pid: 父目录ID(与 path 二选一,同时提供时优先 pid)
        :param path: 目标目录逻辑路径(如 /rag/docs,不存在自动创建)
        :param description: 文件描述
        :param user_id: 归属用户ID
        :return: 文件条目
        """
        if not pid and path:
            folder = await self.mkdir(path, user_id=user_id)
            pid = folder.id
        return await self.service._upload_content(
            data, filename, description, pid, user_id
        )

    async def save_text(
        self,
        text: str,
        filename: str,
        pid: str | None = None,
        path: str | None = None,
        encoding: str = "utf-8",
        user_id: str | None = None,
    ) -> FileEntry:
        """
        保存文本内容为文件
        :param text: 文本内容
        :param filename: 文件名
        :param pid: 父目录ID(与 path 二选一)
        :param path: 目标目录逻辑路径
        :param encoding: 文本编码
        :param user_id: 归属用户ID
        :return: 文件条目
        """
        return await self.upload_bytes(
            text.encode(encoding), filename, pid=pid, path=path, user_id=user_id
        )

    async def mkdir(
        self, path: str, user_id: str | None = None
    ) -> FileEntry:
        """
        按逻辑路径递归创建目录(mkdir -p 语义,已存在直接返回)
        :param path: 目录逻辑路径(如 /rag/docs/images)
        :param user_id: 归属用户ID
        :return: 最终层目录条目
        """
        return await self.service.mkdir_p(path, owner_user_id=user_id)

    # ============ 删 ============
    async def remove(self, entry_id: str) -> None:
        """
        删除文件(逻辑删除,内容引用计数-1,归零时清理物理文件)
        :param entry_id: 文件条目ID
        """
        await self.service.delete_file(entry_id)

    async def remove_tree(self, folder_id: str) -> None:
        """
        递归删除目录及其全部子项
        :param folder_id: 目录条目ID
        """
        await self.service.delete_folder(folder_id)

    async def remove_by_path(self, path: str) -> None:
        """
        按逻辑路径删除(自动判断文件/目录)
        :param path: 逻辑路径(如 /rag/docs 或 /rag/docs/report.pdf)
        """
        entry = await self.get_by_path(path)
        if entry.is_directory:
            await self.remove_tree(entry.id)
        else:
            await self.remove(entry.id)

    # ============ 改 ============
    async def rename(self, entry_id: str, new_name: str) -> FileEntry:
        """
        重命名条目(目录同步更新子树逻辑路径)
        :param entry_id: 条目ID
        :param new_name: 新名称
        :return: 更新后的条目
        """
        return await self.service.rename(entry_id, new_name)

    async def move(self, entry_id: str, target_pid: str | None = None) -> FileEntry:
        """
        移动条目到目标目录(目录同步更新子树路径,含环形防护)
        :param entry_id: 条目ID
        :param target_pid: 目标父目录ID(为空表示根目录)
        :return: 更新后的条目
        """
        return await self.service.move(entry_id, target_pid)

    async def move_to_path(self, entry_id: str, target_path: str) -> FileEntry:
        """
        移动条目到目标逻辑路径目录(目标目录不存在自动创建)
        :param entry_id: 条目ID
        :param target_path: 目标目录逻辑路径(如 /archive/2026)
        :return: 更新后的条目
        """
        folder = await self.mkdir(target_path)
        return await self.service.move(entry_id, folder.id)

    async def copy(self, entry_id: str, target_pid: str | None = None) -> FileEntry:
        """
        复制条目(文件共享内容哈希,目录递归整树复制)
        :param entry_id: 源条目ID
        :param target_pid: 目标父目录ID(为空表示根目录)
        :return: 新条目
        """
        return await self.service.copy_entry(entry_id, target_pid)

    async def set_description(self, entry_id: str, description: str) -> FileEntry:
        """
        更新条目描述
        :param entry_id: 条目ID
        :param description: 新描述
        :return: 更新后的条目
        """
        return await self.service.update(entry_id, FileEntryUpdate(description=description))

    # ============ 查 ============
    async def get(self, entry_id: str) -> FileEntry | None:
        """
        按ID查询条目
        :param entry_id: 条目ID
        :return: 条目对象,不存在返回None
        """
        return await self.service.get_file_entry(entry_id)

    async def get_by_path(self, path: str) -> FileEntry | None:
        """
        按逻辑路径查询条目
        :param path: 逻辑路径
        :return: 条目对象,不存在返回None
        """
        return await self.service.get_by_path(path)

    async def list_dir(
        self, pid: str | None = None, name: str | None = None,
        page: int = 1, size: int = 100,
    ) -> PaginationResponse:
        """
        浏览目录(pid 或 path 二选一)
        :param pid: 父目录ID(为空表示根目录)
        :param name: 名称模糊过滤
        :param page: 页码
        :param size: 每页条数
        :return: 分页结果(items 为 FileEntry 列表)
        """
        return await self.service.list_by_pid(
            pid, PaginationParams(page=page, size=size), name
        )

    async def list_by_path(
        self, path: str, name: str | None = None,
        page: int = 1, size: int = 100,
    ) -> PaginationResponse:
        """
        按逻辑路径浏览目录
        :param path: 目录逻辑路径
        :param name: 名称模糊过滤
        :param page: 页码
        :param size: 每页条数
        :return: 分页结果
        """
        return await self.service.list_by_path(
            path, PaginationParams(page=page, size=size), name
        )

    async def search(
        self, keyword: str, page: int = 1, size: int = 50
    ) -> PaginationResponse:
        """
        全树模糊搜索(匹配名称或逻辑路径)
        :param keyword: 关键字
        :param page: 页码
        :param size: 每页条数
        :return: 分页结果
        """
        return await self.service.search(keyword, PaginationParams(page=page, size=size))

    async def read_bytes(self, entry_id: str) -> bytes:
        """
        读取文件完整字节内容(大文件请用 iter_file 流式读取)
        :param entry_id: 文件条目ID
        :return: 字节内容
        """
        return await self.service.read_file_bytes(entry_id)

    async def read_text(self, entry_id: str, encoding: str = "utf-8") -> str:
        """
        读取文本文件内容
        :param entry_id: 文件条目ID
        :param encoding: 文本编码
        :return: 文本内容
        """
        return await self.service.read_file_text(entry_id, encoding)

    def iter_file(self, entry_id: str, chunk_size: int = 8192):
        """
        流式读取文件内容(异步生成器,大文件/转发下载用)
        :param entry_id: 文件条目ID
        :param chunk_size: 块大小
        :return: AsyncIterator[bytes]
        """
        return self.service.stream_entry_chunks(entry_id, chunk_size)

    async def stats(self) -> dict:
        """
        存储统计
        :return: {storage_type, entry_total, file_total, folder_total, content_total, used_bytes}
        """
        return (await self.service.get_stats()).model_dump()


# 模块级单例: 其他模块直接 `from module_file.client import file_client`
file_client = FileClient()
