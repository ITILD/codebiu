# module_websearch 网页搜索模块

简易网页搜索服务,参考 [open-webSearch](https://github.com/Aas-ee/open-webSearch) 的引擎分层思路,
按本项目 MVC 模块规范实现。支持三个引擎:

| 引擎 | 需要密钥 | 说明 |
| ---- | -------- | ---- |
| DuckDuckGo(默认) | 否 | 本地直连,HTML 端点解析 |
| Tavily | 是 | AI 搜索 API,原生支持屏蔽站点(exclude_domains)与时间范围(time_range) |
| Firecrawl | 是 | 搜索+抓取 API,支持时间范围(tbs),屏蔽站点为本地过滤 |

- Tavily API Key: https://app.tavily.com
- Firecrawl API Key: https://www.firecrawl.dev
- 密钥统一配置在 `config.yaml` 的 `websearch` 段(见 `config.dev.yaml`)
- 国内直连 DuckDuckGo 可能超时,可在 `websearch.proxy` 配置出网代理

## 接口

挂载路径前缀: `/websearch`

### GET /websearch/engines

返回引擎元信息列表(标识/说明/是否默认/是否需要 API Key/是否已配置可用)。

### POST /websearch/search

请求体:

```json
{
  "query": "查询信息(句子或关键词)",
  "engine": "duckduckgo",
  "limit": 10,
  "date_range": "any",
  "blocked_sites": ["example.com", "baidu.com"]
}
```

- `engine`: 可选 `duckduckgo` / `tavily` / `firecrawl`,为空使用 `websearch.default_engine`
- `limit`: 1~30,为空使用 `websearch.max_results`
- `date_range`: `any` / `day` / `week` / `month` / `year`,限制结果时间范围
- `blocked_sites`: 屏蔽的站点来源域名列表(自动去协议/路径/www. 前缀,父域名匹配,如 example.com 会同时屏蔽其子域)

响应包含 `title / url / description / source / engine / published_date` 等字段。
