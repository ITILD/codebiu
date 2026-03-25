# Nuitka 模块化编译使用指南

## 方案特点

✅ **无需修改源码**：`src/app.py` 只需添加3行代码，不影响任何现有导入
✅ **开发部署一致**：开发和部署使用相同的代码
✅ **模块独立编译**：每个子模块编译为独立的扩展模块（.pyd/.so）
✅ **灵活更新**：可以单独更新某个模块，只需替换对应的扩展文件
✅ **性能优化**：编译的模块执行速度更快

## 快速开始

### 1. 安装依赖

```bash
pip install nuitka pyyaml
```

### 2. 编译核心模块（推荐）

```bash
# 编译核心模块（common, module_main, module_authorization, module_file, module_template）
python tools/nuitka_build/build_modules.py
```

### 3. 编译指定模块

```bash
# 只编译 module_ai 模块
python tools/nuitka_build/build_modules.py --modules module_ai

# 编译多个模块
python tools/nuitka_build/build_modules.py --modules module_ai module_nlp
```

### 4. 编译所有模块

```bash
# 编译所有模块（包括标记为compile=false的）
python tools/nuitka_build/build_modules.py --all-modules
```

### 5. 只编译主程序

```bash
# 使用已编译的模块，只编译主程序
python tools/nuitka_build/build_modules.py --main-only
```

### 6. 清理并重新编译

```bash
# 清理之前的构建，重新编译
python tools/nuitka_build/build_modules.py --clean
```

## 编译流程

### 方式1: 完整构建（推荐）

```bash
# 1. 编译模块 + 编译主程序
python tools/nuitka_build/build_modules.py

# 2. 运行打包后的程序
cd dist_nuitka/app.dist
./app  # Linux/Mac
# 或
app.exe  # Windows
```

### 方式2: 分步构建

```bash
# 1. 只编译模块
python tools/nuitka_build/build_modules.py --modules-only

# 2. 只编译主程序
python tools/nuitka_build/build_modules.py --main-only

# 3. 运行
cd dist_nuitka/app.dist
./app
```

### 方式3: 选择性编译

```bash
# 1. 只编译需要的模块
python tools/nuitka_build/build_modules.py --modules module_ai module_nlp

# 2. 编译主程序（会包含所有已编译的模块）
python tools/nuitka_build/build_modules.py --main-only
```

## 配置说明

编辑 `module_build_config.yaml` 可以自定义编译配置：

### 模块配置项

```yaml
- name: "module_ai"           # 模块名称
  path: "src/module_ai"       # 模块路径
  type: "package"             # 类型
  compile: false              # 是否编译（默认只编译标记为true的）
  priority: 6                 # 编译优先级（数字越小越先编译）
  dependencies:               # 依赖的其他模块
    - "common"
    - "module_authorization"
  include_packages:           # 需要包含的第三方包
    - "langchain"
    - "transformers"
  exclude_modules:            # 需要排除的模块
    - "torch"
```

### 全局配置

```yaml
build_config:
  output_dir: "dist_nuitka"           # 输出目录
  modules_dir: "compiled_modules"     # 编译模块目录
  entry_point: "src/app.py"          # 主入口
  global_include_modules:            # 全局包含的模块
    - "fastapi"
    - "uvicorn"

compile_options:
  jobs: 8                            # 并行任务数
  lto: "no"                          # 链接时优化
  show_progress: true                # 显示进度
```

## 目录结构

### 编译后的目录结构