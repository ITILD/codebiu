#!/bin/bash
# 发布脚本用于将包发布到PyPI
# 注意：您需要先设置UV_PUBLISH_TOKEN环境变量
echo "设置PyPI令牌为环境变量..."
export UV_PUBLISH_TOKEN="pypi-**"

echo "检查是否设置了PyPI令牌..."
if [ -z "$UV_PUBLISH_TOKEN" ]; then
    echo "错误：未设置UV_PUBLISH_TOKEN环境变量"
    echo "请先设置您的PyPI令牌："
    echo "export UV_PUBLISH_TOKEN=your_token_here"
    exit 1
fi

echo "构建包..."
uv build

echo "发布包到PyPI..."
uv publish

echo "发布完成！"