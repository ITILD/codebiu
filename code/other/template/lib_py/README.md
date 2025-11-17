# lib-py

一个包含函数和类的示例 Python 包。

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