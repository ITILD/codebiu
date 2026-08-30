from module_office.service.document_parse import DocumentParseService


def get_document_parse_service() -> DocumentParseService:
    return DocumentParseService()
