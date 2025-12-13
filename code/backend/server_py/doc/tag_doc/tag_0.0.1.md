# python 项目初始化

## 1. 项目概述

基于fastapi+pydantic+sqlmodel的基础项目模板，用于快速搭建和开发API服务。

### 1.1项目配置

| 类别           | 配置项                   | 内容   |
| -------------- | ------------------------ | ----------- |
| **包管理器**   | 包管理工具               | uv          |
| **开发服务器** | 服务器工具               | uvicorn     |
| **框架**       | 主框架                   | fastapi     |
| **ORM框架**    | 关系数据库对象关系映射库 | sqlmodel    |
| **项目类型**   | 应用类型                 | 后端api服务 |

### 1.2工程初始化

本地或 Git 托管网站上创建项目：

```bash
# 拉取基础代码(如果需要)
git clone http://zwork1.w1.luyouxia.net/gitea/codebiu_2025/base_server.git
```

## 2. 初始化 python 项目

### 2.1 创建新项目

```bash
# 使用uv init命令创建新项目
uv init
```

### 2.2 基础依赖库添加

```sh
# 选择基础依赖库(临时指定国内源--default-index)
uv add fastapi pydantic sqlmodel uvicorn --default-index https://pypi.tuna.tsinghua.edu.cn/simple
```

## 3. 迁移代码

如果需要将生成的项目迁移到其他目录：

```bash
# 删除main.py文件(Windows系统)
del main.py
# rm -rf ./main.py
# 创建src
mkdir src
# 添加基础app.py
# touch src/app.py
# 添加基础app.py(Windows系统)
echo "" > src/app.py
```

## 4. 安装依赖并运行

```bash
# 安装依赖
uv sync
# 运行项目
uv run
```

## 5. 添加 Git 配置

创建 `.gitignore` 文件并添加必要的忽略规则。
本地.git\config文件内添加账号密码
```diff
[remote "origin"]
-	# url = http://zwork1.w1.luyouxia.net/gitea/codebiu_2025/base_server.git
+	url = http://name:passworld@zwork1.w1.luyouxia.net/gitea/codebiu_2025/base_server.git
+ [user]
+        name = XXX
+        email = XXX
```


## 项目结构说明

项目初始化完成后，你将获得一个包含以下功能的 python 项目：
- 基于 FastAPI 的高性能 RESTful API 服务器
- 集成 SQLModel 的 ORM 数据库操作层
- 自动生成的 Swagger UI 交互式文档
- 简易控制台日志记录
- 单文件MVC分层结构