# module_websearch 网页搜索模块

简易网页搜索服务,参考 [open-webSearch](https://github.com/Aas-ee/open-webSearch) 的引擎分层思路,
按本项目 MVC 模块规范实现。支持 **DuckDuckGo(默认,本地直连无需密钥)** 与 **Bing(网页解析,无需密钥)**。

## 目录结构

```
module_websearch/
├── config/
│   ├── server.py            # 挂载子应用到 /websearch
│   └── settings.py          # 读取 config.yaml 的 websearch 配置段
├── controller/
│   └── websearch.py         # REST 路由(/engines /search)
├── dependencies/
│   └── websearch.py         # Service 依赖注入工厂
├── service/
│   └── websearch.py         # WebSearchService:搜索分发
└── utils/
    └── websearch/
        ├── do/websearch.py  # Engine 枚举/SearchResult/SearchResponse/EngineInfo 模型
        ├── base.py          # SearchEngine 抽象基类(UA/超时/代理统一构建)
        ├── factory.py       # 引擎注册表(新引擎在此追加)
        └── engines/
            ├── duckduckgo.py # DuckDuckGo 引擎(默认)
            └── bing.py       # Bing 引擎
```

> 说明:搜索为无状态代理能力,不落库,故无 dao 层。

## 接口

| 方法 | 路径 | 说明 |
| :---: | :--- | :--- |
| GET | `/websearch/engines` | 可用引擎列表(默认引擎排前) |
| GET | `/websearch/search?query=fastapi&engine=bing&limit=5` | 执行搜索 |

示例:

```bash
# 默认引擎 duckduckgo
curl "http://127.0.0.1:2001/websearch/search?query=fastapi"

# 指定 bing,返回5条
curl "http://127.0.0.1:2001/websearch/search?query=fastapi&engine=bing&limit=5"
```

权限:casbin `main` 域 `search` 资源 `read` 动作(管理员/运维/访客均可用)。

## 配置(config.yaml 的 websearch 段,均有默认值)

```yaml
websearch:
  default_engine: duckduckgo   # 默认引擎
  timeout: 15                  # 请求超时(秒)
  max_results: 10              # 默认条数上限(接口可覆盖,最大30)
  proxy: null                  # 出网代理(国内访问引擎可按需配置)
```

## 新增引擎

1. 在 `utils/websearch/do/websearch.py` 的 `Engine` 枚举追加引擎标识
2. `utils/websearch/engines/` 下新建文件,继承 `base.SearchEngine`,实现 `search(query, limit)`
3. 在 `utils/websearch/factory.py` 的 `ENGINE_CLASSES` 追加引擎类

引擎自测:

```bash
# 需设置 PYTHONPATH=src
python -m module_websearch.utils.websearch.engines.bing "fastapi"
```
