# 项目依赖管理表

### Python 依赖安装

```bash
# 安装所有 Python 依赖
uv sync
```

## Python 后端生产依赖

运行时必需的库,会打包到最终产品中,影响应用功能

以下是补全后的依赖表格，包含各依赖库的具体用途描述：

| 依赖名称      | 版本     | 类型 | 功能描述               | 用途                                                   | 安装命令           | 引入方式                         |
| ------------- | -------- | ---- | ---------------------- | ------------------------------------------------------ | ------------------ | -------------------------------- |
| **fastapi**   | ≥0.116.1 | 生产 | 高性能 Web 框架        | 构建 API 接口、微服务、后端应用                        | `uv add fastapi`   | `from fastapi import FastAPI`    |
| **pydantic**  | ≥2.11.7  | 生产 | 数据验证和设置管理     | 请求/响应数据验证、配置模型定义、类型注解              | `uv add pydantic`  | `from pydantic import BaseModel` |
| **sqlmodel**  | ≥0.0.24  | 生产 | SQL 数据库 ORM         | 数据库操作、结合 SQLAlchemy 和 Pydantic 的 ORM 工具    | `uv add sqlmodel`  | `from sqlmodel import SQLModel`  |
| **uvicorn**   | ≥0.35.0  | 生产 | ASGI 服务器            | 运行 FastAPI 应用的服务器、支持 HTTP/WebSocket         | `uv add uvicorn`   | `import uvicorn`                 |
| **dynaconf**  | ≥3.2.11  | 生产 | 配置管理               | 多环境配置管理（开发/测试/生产）、敏感信息分离         | `uv add dynaconf`  | `from dynaconf import settings`  |
| **psutil**    | ≥7.0.0   | 生产 | 系统监控               | 监控 CPU/内存/磁盘/网络使用情况、进程管理              | `uv add psutil`    | `import psutil`                  |
| **aiohttp**   | ≥3.12.15 | 生产 | HTTP 客户端/服务端     | 异步 HTTP 请求、爬虫开发、微服务通信、WebSocket 客户端 | `uv add aiohttp`   | `import aiohttp`                 |
| **requests**  | ≥2.32.5  | 生产 | HTTP 客户端            | 同步 HTTP 请求、API 调用、爬虫开发                     | `uv add requests`  | `import requests`                |
| **numpy**     | ≥2.3.2   | 生产 | 矩阵计算库             | 数值计算、科学计算、数据分析、机器学习                 | `uv add numpy`     | `import numpy`                   |
| **aiosqlite** | ≥0.21.0  | 生产 | 异步 SQLite 数据库     | 异步操作 SQLite 数据库                                 | `uv add aiosqlite` | `import aiosqlite`               |
| **asyncpg**   | ≥0.30.0  | 生产 | 异步 PostgreSQL 数据库 | 异步操作 PostgreSQL 数据库                             | `uv add asyncpg`   | `import asyncpg`                 |
| **python-multipart** | ≥0.0.20 | 生产 | 处理 multipart/form-data | 处理文件上传、表单数据解析                             | `uv add python-multipart` | `import multipart`               |
| **websockets** | ≥15.0.1  | 生产 | WebSocket 客户端/服务端 | WebSocket 通信、实时应用、聊天室、在线游戏              | `uv add websockets` | `import websockets`              |
| **aiofiles** | ≥25.1.0 | 生产 | 异步文件操作 | 异步读写文件，提高文件操作性能 | `uv add aiofiles` | `import aiofiles` |
| **casbin** | ≥1.43.0 | 生产 | 权限管理框架 | 支持 ACL、RBAC、ABAC 等多种访问控制模型 | `uv add casbin` | `import casbin` |
| **casbin-async-sqlalchemy-adapter** | ≥1.13.0 | 生产 | Casbin SQLAlchemy 适配器 | 为 Casbin 提供 SQLAlchemy 数据库适配器支持 | `uv add casbin-async-sqlalchemy-adapter` | `import casbin_async_sqlalchemy_adapter` |
| **fakeredis** | ≥2.32.1 | 生产 | Redis 模拟器 | 在测试环境中模拟 Redis 服务器 | `uv add fakeredis` | `import fakeredis` |
| **nuitka** | ≥2.8.9 | 生产 | Python 编译器 | 将 Python 代码编译为 C++，提高执行速度 | `uv add nuitka` | `import nuitka` |
| **httpx** | ≥0.28.1 | 生产 | 异步 HTTP 客户端 | 支持异步和同步的 HTTP 客户端，功能比 requests 更丰富 | `uv add httpx` | `import httpx` |
| **pyjwt** | ≥2.10.1 | 生产 | JWT 处理库 | 生成和验证 JSON Web Tokens | `uv add pyjwt` | `import jwt` |
| **pwdlib** | ≥0.2.1 | 生产 | 密码哈希库 | 安全地哈希和验证密码，支持 Argon2 算法 | `uv add pwdlib[argon2]` | `import pwdlib` |
| **pyyaml** | ≥6.0.2 | 生产 | YAML 解析器 | 读写 YAML 格式的配置文件 | `uv add pyyaml` | `import yaml` |
| **sqlite-vec** | ≥0.1.6 | 生产 | SQLite 向量扩展 | 为 SQLite 添加向量相似性搜索功能 | `uv add sqlite-vec` | `import sqlite_vec` |
| **opencv-contrib-python** | ≥4.11.0.86 | 生产 | 计算机视觉库 | 图像处理、计算机视觉算法 | `uv add opencv-contrib-python` | `import cv2` |
| **onnxruntime** | ≥1.22.1 | 生产 | 机器学习推理引擎 | 运行 ONNX 格式的机器学习模型 | `uv add onnxruntime` | `import onnxruntime` |
| **pillow** | ≥11.3.0 | 生产 | 图像处理库 | 图像处理和操作 | `uv add pillow` | `from PIL import Image` |
| **shapely** | ≥2.1.1 | 生产 | 几何对象处理 | 处理和分析几何对象 | `uv add shapely` | `import shapely` |
| **pyclipper** | ≥1.4.0 | 生产 | 多边形裁剪 | 多边形的并集、交集、差集等操作 | `uv add pyclipper` | `import pyclipper` |
| **freetype-py** | ≥2.5.1 | 生产 | 字体渲染库 | 使用 FreeType 渲染字体 | `uv add freetype-py` | `import freetype` |
| **beautifulsoup4** | ≥4.14.3 | 生产 | HTML/XML 解析器 | 解析和提取 HTML 或 XML 文档中的数据 | `uv add beautifulsoup4` | `from bs4 import BeautifulSoup` |
| **lxml** | ≥6.0.2 | 生产 | XML/HTML 处理器 | 高性能的 XML 和 HTML 处理库 | `uv add lxml` | `from lxml import etree` |
| **playwright** | ≥1.55.0 | 生产 | 浏览器自动化 | 跨浏览器自动化测试和网页抓取 | `uv add playwright` | `import playwright` |
| **brotlicffi** | ≥1.1.0.0 | 生产 | 数据压缩库 | Brotli 压缩算法的 CFFI 绑定 | `uv add brotlicffi` | `import brotlicffi` |
| **polars** | ≥1.35.2 | 生产 | 数据分析框架 | 高性能的数据分析库，类似 pandas 但更快 | `uv add polars` | `import polars as pl` |
| **openpyxl** | ≥3.1.5 | 生产 | Excel 文件处理 | 读写 Excel 2010 xlsx/xlsm 文件 | `uv add openpyxl` | `import openpyxl` |
| **fastexcel** | ≥0.17.2 | 生产 | 高性能 Excel 读取 | 快速读取 Excel 文件 | `uv add fastexcel` | `import fastexcel` |
| **xlsxwriter** | ≥3.2.9 | 生产 | Excel 文件生成 | 创建 Excel xlsx 文件 | `uv add xlsxwriter` | `import xlsxwriter` |
| **deepagents** | ≥0.2.8 | 生产 | 深度强化学习框架 | 构建和训练深度强化学习智能体 | `uv add deepagents` | `import deepagents` |
| **langchain-openai** | ≥1.1.0 | 生产 | LangChain OpenAI 集成 | LangChain 对 OpenAI API 的集成 | `uv add langchain-openai` | `from langchain_openai import ChatOpenAI` |
| **langchain-aws** | ≥1.1.0 | 生产 | LangChain AWS 集成 | LangChain 对 AWS 服务的集成 | `uv add langchain-aws` | `from langchain_aws import ChatBedrock` |
| **kuzu** | ≥0.11.3 | 生产 | 图数据库引擎 | 嵌入式的图数据库系统 | `uv add kuzu` | `import kuzu` |
| **neo4j** | ≥6.0.3 | 生产 | 图数据库驱动 | Neo4j 图数据库的官方 Python 驱动 | `uv add neo4j` | `from neo4j import GraphDatabase` |
| **universal-pathlib** | ≥0.3.7 | 生产 | 路径处理库 | 跨平台的路径处理，支持云存储 | `uv add universal-pathlib` | `from upath import UPath` |
| **lancedb** | ≥0.25.3 | 生产 | 向量数据库 | 现代化的向量数据库，用于嵌入和 LLM 应用 | `uv add lancedb` | `import lancedb` |
| **pymilvus** | ≥2.6.5 | 生产 | 向量搜索引擎 | Milvus 向量数据库的 Python SDK | `uv add pymilvus` | `import pymilvus` |

## 后端开发依赖

仅开发阶段使用,可以不打包到最终产品中,影响应用功能(包括构建工具、测试工具、代码检查等)

| 依赖名称   | 版本   | 类型 | 功能描述        | 用途                                                           | 安装命令        | 引入方式        |
| ---------- | ------ | ---- | --------------- | -------------------------------------------------------------- | --------------- | --------------- |
| **pytest** | ≥9.0.2 | 测试 | Python 测试框架 | 单元测试/集成测试/功能测试、支持异步和参数化测试、生成测试报告 | `uv add pytest` | `import pytest` |
| **pytest-asyncio** | ≥1.1.0 | 测试 | 异步测试框架    | 支持 asyncio 的测试框架、异步测试用例、异步 fixture          | `uv add pytest-asyncio` | `import pytest_asyncio` |
