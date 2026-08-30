from fastapi import Depends
from module_office.dao.document_chunk_prompt import DocumentChunkPrompt
from module_office.service.document_chunk import DocumentChunkService



def get_document_chunk_prompt() -> DocumentChunkPrompt:
    return DocumentChunkPrompt()

def get_document_chunk_service(
    document_chunk_prompt: DocumentChunkPrompt = Depends(get_document_chunk_prompt),
) -> DocumentChunkService:
    return DocumentChunkService(document_chunk_prompt)
