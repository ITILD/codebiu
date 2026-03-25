@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Nuitka 编译脚本
echo ========================================

:: 设置变量
set TARGET_DIR=build\app.dist
set MODULE_OUTPUT_DIR=build\modules

:: 清理和创建目录
if exist "%TARGET_DIR%" (
    echo 清空目录: %TARGET_DIR%
    rd /s /q "%TARGET_DIR%" >nul 2>&1
)
echo 创建目录: %TARGET_DIR%
mkdir "%TARGET_DIR%" 2>nul

if not exist "%MODULE_OUTPUT_DIR%" (
    mkdir "%MODULE_OUTPUT_DIR%" 2>nul
)

:: 激活虚拟环境
if exist ".venv\Scripts\activate.bat" (
    echo 激活虚拟环境...
    call .venv\Scripts\activate.bat
) else (
    echo 警告: 未找到虚拟环境
)

:: 编译步骤
echo.
echo [1/3] 编译 module_cv 模块...
python -m nuitka ^
    --module ^
    --output-dir=build/modules ^
    src/module_cv

echo module_cv
if errorlevel 1 (
    echo 错误: module_cv 模块编译失败!
    goto :error
)