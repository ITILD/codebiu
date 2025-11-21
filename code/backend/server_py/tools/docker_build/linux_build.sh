#!/bin/bash
# 如果有就清空dist_nuitka/app.dist目录内容
# 定义源目录和目标目录

TARGET_DIR="build/app.dist"  # 目标发布目录
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
    --standalone \
    --lto=no \
    --include-module=http.cookies,zoneinfo \
    --include-package=langchain_core,langchain_core.embeddings,setuptools,numpy,attr,pyaml \
    --include-package=langchain_aws,langchain_community,langchain_ollama,langchain_openai,langchain_text_splitters,langchain \
    --include-package=pydantic,pydantic_core,pydantic_settings \
    --nofollow-import-to=neo4j \
    --include-data-file=config.yaml=config.yaml \
    --include-data-file=config.dev.yaml=config.dev.yaml \
    --output-dir=dist_nuitka \
    --windows-icon-from-ico=source/img/ion/favicon.ico \
    src/app.py

# echo "Nuitka编译完成！"

# 第二部分：将必要的文件复制到目标目录

echo "开始复制依赖文件..."



# # 需要复制的项目列表（数组）
# ITEMS_TO_COPY=(
#     "neo4j"
# ) # 可以添加更多需要复制的项目
# # 复制所有列表中的项目
# SOURCE_DIR=".venv/lib/python3.13/site-packages/"  # Python包安装目录
# for ITEM in "${ITEMS_TO_COPY[@]}"; do
#     SRC="$SOURCE_DIR/$ITEM"  # 源路径
#     DST="$TARGET_DIR/$ITEM"  # 目标路径

#     if [ -e "$SRC" ]; then  # 检查项目是否存在
#         if [ -d "$SRC" ]; then  # 如果是目录
#             echo "正在复制文件夹: $SRC -> $DST"
#             cp -r "$SRC" "$DST"  # 递归复制目录
#         else
#             echo "正在复制文件: $SRC -> $DST"
#             cp "$SRC" "$DST"  # 复制单个文件
#         fi
#     else
#         echo "警告: 未找到项目 - $SRC"  # 文件/目录不存在的警告
#     fi
# done


# # 复制source文件夹
# SOURCE_DIR_1="source"  
# SRC="$SOURCE_DIR_1"
# DST="$TARGET_DIR/source"

# if [ -e "$SRC" ]; then  # 检查目录是否存在
#     if [ -d "$SRC" ]; then  # 如果是目录
#         echo "正在复制文件夹: $SRC -> $DST"
#         cp -r "$SRC" "$DST"  # 递归复制目录
#     else
#         echo "正在复制文件: $SRC -> $DST"
#         cp "$SRC" "$DST"  # 复制单个文件
#     fi
# fi

# echo "文件复制操作完成!"

echo "所有操作已完成!"