"""动态配置组 schema(单一事实来源: 组元数据/字段类型/脱敏声明/表单描述全在此声明)

约定:
- _group 必须与 config.dev.yaml 对应顶层节同名(首启种子按名取节)
- 字段默认值 = 现 yaml 值; 首启种子 = yaml 节覆盖默认值, 此后 DB 为准
- 密钥类字段进 _secret_fields(回读打码/更新时缺省保持); 嵌套子组字段写 "tavily.api_key" 形式
- _restart_required=True 的组为连接级配置(改后重启生效), 页面顶部会标注
"""
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class SettingsGroup(BaseModel):
    """配置组基类(顶层组与嵌套子组共用; extra=forbid 拒绝未知字段)"""

    model_config = ConfigDict(extra="forbid")

    _group: ClassVar[str] = ""
    _name: ClassVar[str] = ""
    _description: ClassVar[str] = ""
    _restart_required: ClassVar[bool] = False
    _secret_fields: ClassVar[frozenset[str]] = frozenset()  # 顶层字段; 嵌套组字段写 "tavily.api_key" 形式


# ############################# 令牌认证 #############################
class TokenSettings(SettingsGroup):
    _group = "token"
    _name = "令牌认证"
    _description = "JWT 签名与有效期; 修改签名密钥会使所有已登录用户令牌失效(需重新登录)"

    secret_key: str = Field("test123456789123456789123456789123456789", title="签名密钥", description="JWT 签名密钥(≥32位随机字符串)")
    algorithm: str = Field("HS256", title="签名算法")
    expire_minutes: int = Field(30, title="访问令牌有效期(分钟)", ge=1)
    refresh_expire_days: int = Field(20, title="刷新令牌有效期(天)", ge=1)

    _secret_fields = frozenset({"secret_key"})


# ############################# 邮箱服务 #############################
class EmailSettings(SettingsGroup):
    _group = "email"
    _name = "邮箱服务"
    _description = "SMTP 发件配置; 用于注册验证码等邮件发送"

    smtp_server: str = Field("smtp.qq.com", title="SMTP 服务器")
    smtp_port: int = Field(465, title="SMTP 端口", ge=1, le=65535)
    sender_email: str = Field("biubiulight@foxmail.com", title="发件邮箱")
    sender_password: str = Field("rpwuyspeqmmebcgf", title="SMTP 授权码", description="邮箱服务商提供的授权码(非登录密码)")
    sender_name: str = Field("Python邮件服务", title="发件人名称", description="可留空")
    use_for_register: bool = Field(False, title="注册需邮箱验证", description="开启后注册需先获取邮件验证码")

    _secret_fields = frozenset({"sender_password"})


# ############################# 网页搜索 #############################
class TavilySettings(SettingsGroup):
    api_key: str = Field("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", title="API Key", description="https://app.tavily.com 免费注册获取; 为空则该引擎不可用")
    search_depth: Literal["basic", "advanced"] = Field("basic", title="搜索深度", description="advanced 更全但更慢、消耗额度更多")
    include_answer: bool = Field(False, title="返回 AI 摘要答案")


class FirecrawlSettings(SettingsGroup):
    api_key: str = Field("fc-c7b3192b9a814a33837725d8c62c037c", title="API Key", description="https://www.firecrawl.dev 免费注册获取; 为空则该引擎不可用")
    api_base: str = Field("https://api.firecrawl.dev", title="API 地址", description="可替换为自部署实例地址")


class WebSearchSettings(SettingsGroup):
    _group = "websearch"
    _name = "网页搜索"
    _description = "module_websearch 模块全局参数(duckduckgo 直连无需密钥)"

    default_engine: Literal["duckduckgo", "tavily", "firecrawl"] = Field("duckduckgo", title="默认搜索引擎")
    timeout: float = Field(15, title="请求超时(秒)", gt=0)
    max_results: int = Field(10, title="默认返回条数上限", ge=1, le=30)
    proxy: str | None = Field(None, title="出网代理", description="为空直连; 如 http://127.0.0.1:7890")

    tavily: TavilySettings = Field(default_factory=TavilySettings, title="Tavily 配置")
    firecrawl: FirecrawlSettings = Field(default_factory=FirecrawlSettings, title="Firecrawl 配置")

    _secret_fields = frozenset({"tavily.api_key", "firecrawl.api_key"})


# ############################# 文件存储 #############################
class FileSystemSettings(SettingsGroup):
    _group = "file_system"
    _name = "文件存储"
    _description = "上传限额即时生效; 存储类型与连接信息变更需重启(切换存储请先走文件迁移流程)"

    storage_type: Literal["local", "s3", "rustfs"] = Field("s3", title="存储类型")
    max_size: float = Field(10, title="上传大小限制(MB)", gt=0)
    allowed_extensions: list[str] = Field(
        default_factory=lambda: [
            "application/zip",
            "application/pdf",
            "image/*",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        title="允许的 MIME 类型",
    )
    endpoint_url: str = Field("http://47.94.107.62:20004", title="S3 Endpoint", description="S3/MinIO/rustfs 地址")
    access_key: str = Field("minioadmin", title="Access Key")
    secret_key: str = Field("minioadmin", title="Secret Key")
    bucket: str = Field("bucket0", title="存储桶")
    region: str = Field("us-east-1", title="Region")
    secure: bool = Field(False, title="启用 HTTPS")

    _secret_fields = frozenset({"access_key", "secret_key"})
    _restart_required = True


# ############################# 数据库(缓存/向量/图) #############################
class DBCacheSettings(SettingsGroup):
    _group = "db_cache"
    _name = "缓存数据库"
    _description = "Redis/Fakeredis 连接; 变更需重启生效"

    type: str = Field("redis", title="类型", description="redis / fakeredis(本地内存)")
    db: int = Field(0, title="逻辑库编号", ge=0)
    host: str = Field("47.94.107.62", title="主机")
    port: int = Field(20002, title="端口", ge=1, le=65535)
    password: str = Field("here940901940901", title="密码")
    database: str = Field("temp_source\\db\\redis.db", title="持久化文件", description="Fakeredis 持久化地址; Redis 模式留作记录")

    _secret_fields = frozenset({"password"})
    _restart_required = True


class DBVectorSettings(SettingsGroup):
    _group = "db_vector"
    _name = "向量数据库"
    _description = "Milvus/LanceDB 连接; 变更需重启生效, 更换向量库后需重建向量索引"

    type: str = Field("milvus", title="类型", description="milvus / lancedb(本地文件)")
    host: str = Field("http://47.94.107.62", title="主机", description="milvus 专用")
    port: int = Field(20005, title="端口", ge=1, le=65535, description="milvus 专用")
    user: str = Field("root", title="用户名", description="milvus 专用")
    password: str | None = Field(None, title="密码", description="milvus 专用")
    database: str = Field("default", title="数据库", description="milvus 为库名; lancedb 为本地目录路径")

    _secret_fields = frozenset({"password"})
    _restart_required = True


class DBGraphSettings(SettingsGroup):
    _group = "db_graph"
    _name = "图数据库"
    _description = "graph_local/neo4j 连接; 变更需重启生效"

    type: str = Field("graph_local", title="类型", description="graph_local(本地文件) / neo4j")
    database: str = Field("temp_source/db/db_graph_local.db", title="数据库", description="graph_local 为文件路径; neo4j 为库名")
    host: str | None = Field(None, title="主机", description="neo4j 专用")
    port: int | None = Field(None, title="端口", ge=1, le=65535, description="neo4j 专用")
    user: str | None = Field(None, title="用户名", description="neo4j 专用")
    password: str | None = Field(None, title="密码", description="neo4j 专用")

    _secret_fields = frozenset({"password"})
    _restart_required = True


# ############################# 任务队列 #############################
class TasksSettings(SettingsGroup):
    _group = "tasks"
    _name = "任务队列"
    _description = "engine 切换(local=进程内协程/celery=Redis worker)对新建任务即时生效; broker 地址变更需重启 worker"

    engine: Literal["local", "celery"] = Field("local", title="执行引擎")
    broker_url: str = Field("memory://", title="Broker 地址", description="celery 引擎的 Redis broker(与缓存库同实例分库)")
    result_backend: str = Field("cache+memory://", title="结果后端", description="celery 引擎的结果回写地址")

    _secret_fields = frozenset({"broker_url", "result_backend"})  # URL 内嵌密码, 一并打码


# ############################# 默认管理员 #############################
class AdminSettings(SettingsGroup):
    _group = "admin"
    _name = "默认管理员"
    _description = "启动引导账户(绑定全局 admin 角色); reset_password 开启时每次启动将密码重置为配置值(忘记密码自救)"

    username: str = Field("admin", title="用户名")
    password: str = Field("admin123", title="密码", description="引导创建/重置用; 日常改密请走用户管理")
    nickname: str = Field("系统管理员", title="昵称")
    email: str = Field("admin@codebiu.local", title="邮箱")
    reset_password: bool = Field(False, title="启动时重置密码")

    _secret_fields = frozenset({"password"})


# 注册表(UI 展示顺序即此顺序)
GROUPS: list[type[SettingsGroup]] = [
    TokenSettings,
    EmailSettings,
    WebSearchSettings,
    FileSystemSettings,
    DBCacheSettings,
    DBVectorSettings,
    DBGraphSettings,
    TasksSettings,
    AdminSettings,
]
