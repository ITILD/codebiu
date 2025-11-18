@echo off
REM 发布脚本用于将包发布到PyPI
echo 设置PyPI令牌为环境变量...
set UV_PUBLISH_TOKEN=pypi-**
REM 注意：您需要先设置UV_PUBLISH_TOKEN环境变量

echo 检查是否设置了PyPI令牌...
if "%UV_PUBLISH_TOKEN%"=="" (
    echo 错误：未设置UV_PUBLISH_TOKEN环境变量
    echo 请先设置您的PyPI令牌：
    echo set UV_PUBLISH_TOKEN=your_token_here
    exit /b 1
)

echo 构建包...
uv build

echo 发布包到PyPI...
uv publish

echo 发布完成！