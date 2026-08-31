"""
module_rag 字典种子声明(知识库模块域字典)

字典项编码直接从模块代码枚举(RagRole/KbCategory/ParseStatus/DocType)派生,
保证字典与代码取值一致,不产生两处维护的漂移问题。

启动时由 DictBootstrapService 统一批量幂等同步到 dict_type/dict_item 表。
"""
from module_main.config.dict_seed import DictTypeSeed, DictItemSeed, dict_seed_registry
from module_rag.do.project_member import RagRole
from module_rag.do.project import KbCategory
from module_rag.do.project_document import ParseStatus, DocType

# 注册: 项目成员角色(与 RagRole.PROJECT_ROLES 对齐)
dict_seed_registry.register(
    DictTypeSeed(
        type_code="rag_member_role",
        type_name="项目成员角色",
        description="项目成员表 role 字段的固定档位",
        sort_order=1,
        items=[
            DictItemSeed(item_code=RagRole.PROJECT_ADMIN, item_name="项目管理员",
                         description="项目内全部操作"),
            DictItemSeed(item_code=RagRole.PROJECT_EDITOR, item_name="项目编辑",
                         description="可读写文档与对话"),
            DictItemSeed(item_code=RagRole.PROJECT_READER, item_name="项目只读",
                         description="仅可读"),
        ],
    )
)

# 注册: 知识库分类(与 KbCategory 对齐)
_KB_CATEGORY_NAMES: dict[str, str] = {
    KbCategory.PERSONAL: "个人知识库",
    KbCategory.PROJECT: "项目知识库",
    KbCategory.COMPANY: "企业知识库",
}
dict_seed_registry.register(
    DictTypeSeed(
        type_code="rag_kb_category",
        type_name="知识库分类",
        description="项目 kb_category 字段的分类显示字典",
        sort_order=2,
        items=[
            DictItemSeed(item_code=c.value, item_name=_KB_CATEGORY_NAMES[c.value])
            for c in KbCategory
        ],
    )
)

# 注册: 文档解析状态(与 ParseStatus 对齐)
_PARSE_STATUS_NAMES: dict[str, str] = {
    ParseStatus.PENDING: "待解析",
    ParseStatus.PARSING: "解析中",
    ParseStatus.COMPLETED: "已完成",
    ParseStatus.FAILED: "解析失败",
}
dict_seed_registry.register(
    DictTypeSeed(
        type_code="rag_doc_parse_status",
        type_name="文档解析状态",
        description="项目文档 parse_status 字段的状态显示字典",
        sort_order=3,
        items=[
            DictItemSeed(item_code=s.value, item_name=_PARSE_STATUS_NAMES[s.value])
            for s in ParseStatus
        ],
    )
)

# 注册: 文档类型(与 DocType 对齐)
_DOC_TYPE_NAMES: dict[str, str] = {
    "pdf": "PDF文档", "docx": "Word文档", "pptx": "PPT演示文稿", "xlsx": "Excel表格",
    "png": "PNG图片", "jpg": "JPG图片", "jpeg": "JPEG图片", "tiff": "TIFF图片",
    "mp3": "MP3音频", "wav": "WAV音频", "mp4": "MP4视频", "avi": "AVI视频",
    "txt": "文本文件", "md": "Markdown文档", "csv": "CSV表格",
    "py": "Python代码", "java": "Java代码",
}
# 从 DocType 类常量派生全部扩展名(过滤非字符串的类属性)
_doc_type_exts = [v for k, v in vars(DocType).items() if not k.startswith("_") and isinstance(v, str)]
dict_seed_registry.register(
    DictTypeSeed(
        type_code="rag_doc_type",
        type_name="文档类型",
        description="项目文档 doc_type 字段的类型显示字典",
        sort_order=4,
        items=[
            DictItemSeed(item_code=ext, item_name=_DOC_TYPE_NAMES.get(ext, ext.upper()))
            for ext in _doc_type_exts
        ],
    )
)
