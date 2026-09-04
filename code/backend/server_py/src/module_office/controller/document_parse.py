"""
文件解析成markdown
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pathlib import Path
from uuid import uuid4

from common.config.path import DIR_TEMP
from module_authorization.dependencies.auth import get_current_user_id
from module_office.config.server import module_app
from module_office.dependencies.document_parse import get_document_parse_service
from module_office.service.document_parse import DocumentParseService
from module_office.utils.file_parase.do.chunk import Chunk

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/get-markdown-by-file",
    summary="根据文件路径获取Markdown内容",
)
async def get_markdown_by_file(
    file: UploadFile,
    # 【关键】自动从 Token 中解析当前登录用户的 ID，无需前端手动传
    user_id: str = Depends(get_current_user_id),
    document_parse_service: DocumentParseService = Depends(get_document_parse_service),
) -> str:
    """
    文件解析成markdown
    :param file: 上传的文件
    :param user_id: 当前登录用户的 ID
    :return: 解析后的Markdown内容列表
    """
    try:
        result = ""
        # 临时存储
        temp_file = DIR_TEMP / file.filename
        # debug覆盖写入
        temp_file.write_bytes(file.file.read())
        logger.debug(f"测试_输入写入：{temp_file}")
        # debug_end

        result = await document_parse_service.file2markdown(temp_file)

        # debug覆盖写入
        temp_out_file = DIR_TEMP / f"{file.filename.split('.')[0]}.md"
        temp_out_file.write_text(result)
        logger.debug(f"测试写入：{temp_out_file}")
        # debug_end
    except ValueError as e:
        logger.error(f"解析异常：{e}")
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post(
    "/split-code",
    summary="按语义结构拆分 Python/Java 代码文件",
    response_model=list[Chunk],
)
async def split_code_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    document_parse_service: DocumentParseService = Depends(get_document_parse_service),
) -> list[Chunk]:
    """按模块、类、函数/方法拆分代码；语法不完整时返回可继续切分的全文块。"""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".py", ".java"}:
        raise HTTPException(status_code=400, detail="仅支持 .py 和 .java 文件")

    DIR_TEMP.mkdir(parents=True, exist_ok=True)
    temp_file = DIR_TEMP / f"code_{uuid4().hex}{suffix}"
    try:
        with temp_file.open("wb") as output:
            while data := await file.read(1024 * 1024):
                output.write(data)
        chunks = await document_parse_service.file2chunk(temp_file)
        # 临时物理名对调用方无意义，恢复上传时的原始文件名。
        for chunk in chunks:
            chunk.metadata = dict(chunk.metadata or {})
            chunk.metadata["source"] = file.filename or temp_file.name
        return chunks
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()
        temp_file.unlink(missing_ok=True)


# TODO rerank list ...


module_app.include_router(router, prefix="/document-parse")
