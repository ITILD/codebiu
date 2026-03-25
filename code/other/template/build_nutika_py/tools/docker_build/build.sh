#!/bin/bash
# 如果有就清空dist_nuitka/app.dist目录内容
# 定义源目录和目标目录
TARGET_DIR="build/modules"  # 目标发布目录
if [ -d "$TARGET_DIR" ]; then
    echo "清空目录: $TARGET_DIR"
    rm -rf "$TARGET_DIR"/*  # 清空目录内容
else
    echo "创建目录: $TARGET_DIR"
    mkdir -p "$TARGET_DIR"  # 创建目标目录
fi


echo "开始使用Nuitka编译..."

# 激活 UV 环境（假设您已经通过 uv 创建了虚拟环境）
source .venv/bin/activate  # Linux/macOS
# 或者对于 Windows: .venv\Scripts\activate

# 使用 UV 环境中的 Python 和 Nuitka 进行编译
python -m nuitka \
    --show-progress \
    --jobs=8  \
    --module \
    --lto=no \
    --output-dir=build \
    src/module_cv