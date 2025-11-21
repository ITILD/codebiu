@echo off
setlocal enabledelayedexpansion

REM 定义目标目录
set "TARGET_DIR=build\app.dist"

REM 检查目录是否存在，不存在则创建，存在则清空
if not exist "%TARGET_DIR%" (
    echo 创建目录: %TARGET_DIR%
    mkdir "%TARGET_DIR%"
) else (
    echo 清空目录: %TARGET_DIR%
    del /q "%TARGET_DIR%\*.*" 2>nul
    for /d %%i in ("%TARGET_DIR%\*") do (
        rd /s /q "%%i" 2>nul
    )
)

echo 目录准备完成: %TARGET_DIR%
echo 开始使用Nuitka编译...

REM 激活 UV 环境
call .venv\Scripts\activate.bat

REM 使用 Nuitka 进行编译
python -m nuitka ^
    --show-progress ^
    --jobs=8 ^
    --standalone ^
    --lto=no ^
    --include-module=http.cookies,zoneinfo ^
    --include-package=langchain_core ^
    --include-package=langchain_core.embeddings ^
    --include-package=setuptools ^
    --include-package=numpy ^
    --include-package=attr ^
    --include-package=pyaml ^
    --include-package=langchain_aws ^
    --include-package=langchain_community ^
    --include-package=langchain_ollama ^
    --include-package=langchain_openai ^
    --include-package=langchain_text_splitters ^
    --include-package=langchain ^
    --include-package=pydantic ^
    --include-package=pydantic_core ^
    --include-package=pydantic_settings ^
    --nofollow-import-to=neo4j ^
    --include-data-file=config.yaml=config.yaml ^
    --include-data-file=config.dev.yaml=config.dev.yaml ^
    --output-dir=dist_nuitka ^
    --windows-icon-from-ico=source\img\ion\favicon.ico ^
    src\app.py

echo Nuitka编译完成！

REM 取消注释以下部分以启用文件复制功能
REM echo 开始复制依赖文件...
REM 
REM set "SOURCE_DIR=.venv\lib\python3.13\site-packages\"
REM set "ITEMS_TO_COPY=neo4j"
REM 
REM for %%a in (%ITEMS_TO_COPY%) do (
REM     set "SRC=%SOURCE_DIR%%%a"
REM     set "DST=%TARGET_DIR%\%%a"
REM 
REM     if exist "!SRC!" (
REM         if exist "!SRC!\*" (
REM             echo 正在复制文件夹: !SRC! -^> !DST!
REM             xcopy /e /i /y "!SRC!" "!DST!"
REM         ) else (
REM             echo 正在复制文件: !SRC! -^> !DST!
REM             copy /y "!SRC!" "!DST!"
REM         )
REM     ) else (
REM         echo 警告: 未找到项目 - !SRC!
REM     )
REM )
REM 
REM set "SOURCE_DIR_1=source"
REM set "SRC=!SOURCE_DIR_1!"
REM set "DST=%TARGET_DIR%\source"
REM 
REM if exist "!SRC!" (
REM     if exist "!SRC!\*" (
REM         echo 正在复制文件夹: !SRC! -^> !DST!
REM         xcopy /e /i /y "!SRC!" "!DST!"
REM     ) else (
REM         echo 正在复制文件: !SRC! -^> !DST!
REM         copy /y "!SRC!" "!DST!"
REM     )
REM )
REM 
REM echo 文件复制操作完成!

echo 所有操作已完成!
endlocal