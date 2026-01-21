from pathlib import Path
from sqlmodel import SQLModel, Field, select, Column, DateTime
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from contextlib import asynccontextmanager
import json
from fastapi import FastAPI, applications, Depends, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from uuid import uuid4
from datetime import datetime, timezone

# 基础log
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
# 基础配置
HOST = "0.0.0.0"
PORT = 3100
# 静态文件配置
DIR_PUBLIC = Path("source")
DIR_HTML_MAIN = DIR_PUBLIC / "main"
# 临时文件配置
temp_path = Path("temp_source")
temp_path.mkdir(parents=True, exist_ok=True)
# 数据库配置
# SQLite数据库URL
database_url = f"sqlite+aiosqlite:///{temp_path}/template.db"


# 定义用户模型，结合了SQLAlchemy和Pydantic的功能
class User(SQLModel, table=True):
    """
    用户数据模型
    结合了SQLAlchemy ORM功能和Pydantic验证功能
    """

    __tablename__ = "users"

    id: str | None = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="唯一标识符",
    )
    name: str = Field(min_length=1, max_length=50, description="用户姓名")
    email: str = Field(max_length=100, unique=True, description="用户邮箱地址")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
        description="创建时间",
    )


# 定义创建用户的请求模型
class UserCreate(SQLModel):
    """创建用户时的请求体模型"""

    name: str
    email: str


# 定义更新用户的请求模型
class UserUpdate(SQLModel):
    """更新用户时的请求体模型"""

    name: str
    email: str


# 定义用户响应模型
class UserResponse(SQLModel):
    """用户API响应模型"""

    id: str
    name: str
    email: str
    created_at: datetime


# 创建应用实例
app = FastAPI(
    title="用户管理系统",
    description="基于SQLModel的用户增删改查系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


def swagger_ui_source_local(*args, **kwargs):
    """自定义Swagger UI资源路径"""
    return get_swagger_ui_html(
        *args,
        **kwargs,
        swagger_js_url="common/assets/js/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="common/assets/js/swagger-ui/swagger-ui.css",
    )


applications.get_swagger_ui_html = swagger_ui_source_local


# 主页路由 - 返回HTML页面
@app.get(
    "/",
    response_class=HTMLResponse,
    summary="主页",
    tags=["frontend"],
    description="返回用户管理系统的主页",
)
async def server():
    """返回主页HTML文件"""
    html_file = open(DIR_HTML_MAIN / "index.html", "r", encoding="utf-8").read()
    return html_file


# 挂载静态文件目录
app.mount(
    "/static",
    StaticFiles(directory=DIR_HTML_MAIN, html=True),
    name="static",
)

app.mount(
    "/common",
    StaticFiles(directory=DIR_PUBLIC / "common"),
    name="common",
)


# 创建异步引擎
engine = create_async_engine(
    database_url,
    echo=True,  # 打印SQL语句
    pool_pre_ping=True,  # 连接池检查连接有效性
    json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),  # 中文序列化
)


# 应用生命周期管理 - 用于初始化数据库
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器，用于在启动时创建数据库表"""
    async with engine.begin() as conn:
        # 删除所有表
        await conn.run_sync(SQLModel.metadata.drop_all)
        # 创建所有表
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


app.router.lifespan_context = lifespan


# 数据库会话依赖项
async def get_session():
    """获取数据库会话的依赖项"""
    async with AsyncSession(engine) as session:
        yield session


# 用户API路由
@app.post("/users/", summary="创建用户", response_model=UserResponse)
async def create_user(user: UserCreate, session: AsyncSession = Depends(get_session)):
    """
    创建新用户
    - **name**: 用户姓名
    - **email**: 用户邮箱
    """
    # 检查邮箱是否已存在
    existing_user = await session.exec(select(User).where(User.email == user.email))
    if existing_user.first():
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    # 创建新用户
    db_user = User.model_validate(user)
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


@app.get("/users/", summary="获取所有用户", response_model=list[UserResponse])
async def get_users(session: AsyncSession = Depends(get_session)):
    """获取所有用户列表"""
    users = await session.exec(select(User))
    return users.all()


@app.get("/users/{user_id}", summary="根据ID获取用户", response_model=UserResponse)
async def get_user(user_id: str, session: AsyncSession = Depends(get_session)):
    """根据ID获取特定用户"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@app.put("/users/{user_id}", summary="更新用户", response_model=UserResponse)
async def update_user(
    user_id: str, user_data: UserUpdate, session: AsyncSession = Depends(get_session)
):
    """更新指定ID的用户信息"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查邮箱是否与其他用户冲突
    existing_user = await session.exec(
        select(User).where(User.email == user_data.email, User.id != user_id)
    )
    if existing_user.first():
        raise HTTPException(status_code=400, detail="该邮箱已被其他用户使用")

    # 更新用户信息
    user.name = user_data.name
    user.email = user_data.email
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@app.delete("/users/{user_id}", summary="删除用户")
async def delete_user(user_id: str, session: AsyncSession = Depends(get_session)):
    """删除指定ID的用户"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    await session.delete(user)
    await session.commit()
    return {"message": "用户删除成功"}


# log信息
logger.info(f"swagger测试接口页面: http://localhost:{PORT}/docs")
logger.info(f"示例页面: http://localhost:{PORT}")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
    )
