# lib-py

一个包含函数和类的示例 Python 包。

## 打包发布
```bash
uv build
```
## 安装

安装此包，请使用：
```bash
uv add .
```

## 使用方法

安装后，您可以按如下方式使用该包：

```python
from lib_py import demo_function, DemoClass

# 使用 demo 函数
result = demo_function("世界")
print(result)  # 输出：Hello, 世界！这是一个示例函数。

# 使用 demo 类
demo_instance = DemoClass("示例")
result = demo_instance.greet()
print(result)  # 输出：Hello from DemoClass, 示例！
```

## 开发结构

该包的组织结构如下：
- `demo_function.py`：包含 `demo_function` 函数
- `demo_class.py`：包含 `DemoClass` 类

两者均通过包的 `__init__.py` 文件导出。

## 发布到PyPI

要使用uv将此包发布到PyPI，您可以使用我们提供的脚本：

### 使用脚本发布（推荐）

1. 首先设置您的PyPI令牌为环境变量：
   ```bash
   # Windows (PowerShell)
   $env:UV_PUBLISH_TOKEN = "your_pypi_token_here"
   
   # Linux/macOS
   export UV_PUBLISH_TOKEN="your_pypi_token_here"
   ```

2. 运行发布脚本：
   ```bash
   # Windows
   publish.bat
   
   # Linux/macOS
   chmod +x publish.sh
   ./publish.sh
   ```

### 手动发布步骤：

1. 设置PyPI令牌为环境变量（如上所示）

2. 构建包：
   ```bash
   uv build
   ```

3. 发布包：
   ```bash
   uv publish
   ```