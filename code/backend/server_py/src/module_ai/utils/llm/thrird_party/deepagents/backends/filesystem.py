from deepagents.backends.filesystem import FilesystemBackend
from deepagents.backends.protocol import WriteResult, EditResult

class FilesystemBackendNoEdit(FilesystemBackend):
    
    # 禁止所有写入
    def write(self, file_path: str, content: str) -> WriteResult:
        return WriteResult(error="Write operations are not allowed")

    # 禁止所有编辑
    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        return EditResult(error="Edit operations are not allowed")
