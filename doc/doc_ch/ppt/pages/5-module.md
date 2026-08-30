---
layout: two-cols
layoutClass: gap-6
clicks: 3
---

# 新模块开发：六步法

以 `module_demo` 为例：

## ① 建目录

```
src/module_demo/
├── config/server.py
├── controller/demo.py
├── dao/demo.py
├── do/demo.py
├── service/demo.py
└── dependencies/demo.py
```

## ② 挂载路由 config/server.py

```python
from common.config.server import app
from fastapi import FastAPI

module_app = FastAPI()
app.mount("/demo", module_app)
```

## ③ 定义数据对象 do/

```python
# 表模型 + Create/Update 模式
class DemoCreate(BaseModel): ...
```

::right::

## ④ DAO 数据访问 dao/

```python
@DaoRel
async def get_all(self, session=None):
    statement = select(Demo)
    return (await session.exec(statement)).all()
```

## ⑤ Service 业务层 + Controller 路由

```python
# controller 末尾注册路由
module_app.include_router(
    router, prefix="/demo", tags=["示例"]
)
```

## ⑥ app.py 引入

```python
from module_demo.controller import demo
```

<div v-click class="note-tip">
全过程可参考 <code>module_template</code> 模块 — 它就是为此而存在的参考实现。
</div>
