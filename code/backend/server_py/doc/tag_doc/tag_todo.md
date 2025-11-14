# casbin模块添加
使用 FastAPI、SQLModel 和 Casbin 构建一个基础的 RBAC (基于角色的访问控制) 权限管理系统

### 核心概念

在我们开始编码之前，先简单理解一下这三个核心组件：

  * **FastAPI**: 一个现代、快速（高性能）的 Python Web 框架，用于构建 API。它基于标准的 Python类型提示，可以自动生成交互式 API 文档（Swagger UI 和 ReDoc）。
  * **SQLModel**: 由 FastAPI 的作者创建，它结合了 SQLAlchemy 和 Pydantic 的优点。你可以用它来创建同时具备数据库模型和数据校验功能的 Python 类，从而减少代码冗余。
  * **Casbin**: 一个强大且高效的开源访问控制库。其核心思想是将访问控制模型、策略和请求进行解耦。它支持多种访问控制模型，如 ACL, RBAC, ABAC 等。我们这里主要使用 RBAC。

### RBAC 核心思想

RBAC 的核心很简单： **“谁” (Subject) 对 “什么” (Object) 有 “什么权限” (Action)**。

  * **Subject (sub)**: 主体，通常指用户或用户角色。
  * **Object (obj)**: 客体，指需要被访问的资源，例如一个 API 路径、一个文件或一个菜单。
  * **Action (act)**: 动作，指对资源进行的操作，例如 `read` (读), `write` (写), `delete` (删除) 等。在 Web 应用中，通常是 HTTP 方法，如 `GET`, `POST`, `PUT`, `DELETE`。

Casbin 通过一个 **模型文件 (model file)** 和一个 **策略文件 (policy file)** 来定义和存储这些规则。

-----

### 项目搭建步骤

#### 1\. 安装必要的库

首先，我们需要安装所有需要的 Python 库。

```bash
pip install fastapi uvicorn sqlmodel casbin casbin-sqlalchemy-adapter
```

  * `fastapi`: Web 框架。
  * `uvicorn`: ASGI 服务器，用于运行 FastAPI 应用。
  * `sqlmodel`: ORM，用于数据库交互。
  * `casbin`: 核心权限控制库。
  * `casbin-sqlalchemy-adapter`: Casbin 的 SQLAlchemy 适配器，让 Casbin 可以将策略规则持久化到数据库中。

#### 2\. Casbin 模型和策略配置

##### a. `rbac_model.conf` (模型文件)

创建一个名为 `rbac_model.conf` 的文件。这个文件定义了 RBAC 的结构和匹配规则。

```ini
# Request definition
# 请求定义：[请求者, 请求的资源, 请求的动作]
[request_definition]
r = sub, obj, act

# Policy definition
# 策略定义：[策略规则的组成部分]
[policy_definition]
p = sub, obj, act

# Role definition
# 角色定义：g 是角色继承关系，_ 表示角色，_ 表示用户
# g = _, _  表示前面的角色/用户继承了后面的角色的权限
[role_definition]
g = _, _

# Policy effect
# 策略效果：当至少有一条策略规则匹配并且结果为 allow 时，请求就被允许
[policy_effect]
e = some(where (p.eft == allow))

# Matchers
# 匹配器：定义如何匹配请求和策略
# r.sub == p.sub：请求的主体（用户/角色）与策略中的主体匹配
# r.obj == p.obj：请求的资源与策略中的资源匹配
# r.act == p.act：请求的动作与策略中的动作匹配
# g(r.sub, p.sub) 是一个关键函数，表示 r.sub (请求者) 是否属于 p.sub (策略中定义的角色)
[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act

```

##### b. 策略规则 (我们后续会通过代码添加到数据库)

策略规则 (Policy Rules) 会遵循 `policy_definition` 的格式，例如：

  * `p, admin, /api/v1/users, GET`  (策略：admin 角色可以 GET `/api/v1/users` 路径)
  * `p, user, /api/v1/me, GET` (策略：user 角色可以 GET `/api/v1/me` 路径)
  * `g, alice, admin` (角色继承：用户 alice 属于 admin 角色)
  * `g, bob, user` (角色继承：用户 bob 属于 user 角色)

#### 3\. 数据库和 SQLModel 模型定义 (`database.py` 和 `models.py`)

我们将使用 SQLite 作为示例数据库，因为它不需要额外配置。

##### `database.py`

```python
# database.py
from sqlmodel import create_engine, SQLModel

# 定义数据库文件名为 database.db
DATABASE_URL = "sqlite:///database.db"

# 创建数据库引擎
# connect_args={"check_same_thread": False} 是 SQLite 特有的配置，允许多个线程访问同一个连接
engine = create_engine(DATABASE_URL, echo=True, connect_args={"check_same_thread": False})

def create_db_and_tables():
    """
    创建数据库和所有定义的表
    """
    SQLModel.metadata.create_all(engine)

```

##### `models.py`

```python
# models.py
from typing import Optional
from sqlmodel import Field, SQLModel

class User(SQLModel, table=True):
    """
    用户模型
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password: str # 在实际应用中，这里应该存储哈希后的密码

```

**注意**: Casbin 的 `casbin-sqlalchemy-adapter` 会自动创建一张名为 `casbin_rule` 的表来存储策略规则，所以我们不需要为 Casbin 规则创建 SQLModel 模型。

#### 4\. Casbin 核心配置 (`casbin_config.py`)

这个文件将初始化 Casbin 的核心组件：`enforcer`。

```python
# casbin_config.py
import casbin
from casbin_sqlalchemy_adapter import Adapter
from .database import DATABASE_URL

# 初始化 Casbin 的 SQLAlchemy 适配器
# 这会让 Casbin 将其策略存储在我们的数据库中
adapter = Adapter(DATABASE_URL)

# 初始化 Casbin enforcer
# 第一个参数是模型文件的路径
# 第二个参数是适配器实例
# aenforcer = await casbin.AsyncEnforcer('path/to/model.conf', adapter) # 异步版本
enforcer = casbin.Enforcer("./rbac_model.conf", adapter)

def get_enforcer() -> casbin.Enforcer:
    """
    依赖注入函数，用于在 FastAPI 路由中获取 enforcer 实例
    """
    return enforcer
```

#### 5\. FastAPI 应用 (`main.py`)

这是我们将所有部分组合在一起的主文件。

```python
# main.py
from fastapi import FastAPI, Depends, HTTPException, status
from sqlmodel import Session, select
import casbin

from .database import engine, create_db_and_tables
from .models import User
from .casbin_config import get_enforcer

# --- FastAPI 应用实例 ---
app = FastAPI(title="FastAPI SQLModel Casbin RBAC Demo")

# --- 依赖注入 ---
def get_db_session():
    """
    为每个请求创建一个数据库会话，并在请求结束后关闭它。
    """
    with Session(engine) as session:
        yield session




# --- 应用启动事件 ---
@app.on_event("startup")
def on_startup():
    """
    应用启动时执行的函数。
    """
    print("应用启动...")
    # 1. 创建数据库和表
    create_db_and_tables()
    print("数据库和表已创建。")

    # 2. 初始化 Casbin 策略 (如果不存在)
    enforcer = get_enforcer()
    
    # 检查策略是否已存在，避免重复添加
    if not enforcer.get_policy():
        print("未找到 Casbin 策略，正在初始化...")
        # --- 添加策略规则 ---
        # p, subject, object, action
        
        # admin 角色可以访问所有用户数据 (GET) 和管理页面 (GET)
        enforcer.add_policy("admin", "/api/v1/users", "GET")
        enforcer.add_policy("admin", "/api/v1/admin", "GET")
        
        # user 角色只能访问自己的信息 (GET)
        enforcer.add_policy("user", "/api/v1/me", "GET")

        # --- 添加角色继承规则 ---
        # g, user, role
        enforcer.add_grouping_policy("alice", "admin") # alice 是 admin
        enforcer.add_grouping_policy("bob", "user")   # bob 是 user
        
        enforcer.save_policy()
        print("Casbin 策略初始化完成。")
    else:
        print("Casbin 策略已存在。")




```

#### 6\. 运行应用

在你的终端中，运行以下命令：

```bash
uvicorn main:app --reload
```

  * `main`: 指的是 `main.py` 文件。
  * `app`: 指的是在 `main.py` 中创建的 `app = FastAPI()` 对象。
  * `--reload`: 这个参数会让服务器在代码变动后自动重启，非常适合开发阶段。

-----
