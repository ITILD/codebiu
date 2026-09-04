from module_office.service.document_parse import DocumentParseService


def get_document_parse_service() -> DocumentParseService:
    """文档解析服务工厂(FastAPI依赖注入)"""
    return DocumentParseService()
