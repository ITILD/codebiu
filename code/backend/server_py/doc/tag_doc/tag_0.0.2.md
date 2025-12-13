# 添加基础开发组件

引入本地 api docs,基础 config,log 配置,补全基础项目结构

```sh
# import yaml
uv add PyYAML dynaconf
```

## 1. 调试设置

### 调试指定环境变量

.env 文件添加，用于

```diff
## win11
PYTHONPATH=./src;./
# ubuntu24
# PYTHONPATH=./src:./
```

.gitignore

```diff
- .env
```

.vscode\settings.json 添加

```json
{
  "python.pythonPath": "venv\\Scripts\\python.exe",
  "python.envFile": ".env"
}
```

## 2. 添加本地 api docs(swagger)

fastapi 默认 swagger 是线上地址，可以自定义本地地址

```py
# 自定义 Swagger
swagger_local(
    swagger_js_url=SERVER_ROOT_PATH
    + "/common/assets/js/swagger-ui/swagger-ui-bundle.js",
    swagger_css_url=SERVER_ROOT_PATH + "/common/assets/js/swagger-ui/swagger-ui.css",
)
```

## 3. 添加基础 config,log 配置

初始化时使用代码灵活配置 log，主要涉及每日更新日志文件，控制台和文件日志输出格式级别，控制台输出样式

```py
# 开发文件引入log
import logging
logger = logging.getLogger(__name__)
```

## 4. 添加启动监控

监测服务主机的 cpu，内存，磁盘，网络等状态

```sh
uv add psutil
```

## 5.测试配置
setting.json 配置添加
```json
  "python.testing.pytestArgs": [
    "-v",          // 显示详细输出
    "-s",          // 禁用输出捕获(关键！)
    "--log-cli-level=INFO"  //  启用日志输出到控制台
  ]
}
```

## 6.模板模块

代码模板，module_template文件夹  
考虑常用增删改查、翻页和滚动、接口测试、文件上传、sse流式输出和websocket接口等常用功能