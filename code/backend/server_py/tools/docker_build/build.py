#!/usr/bin/env python3
"""
Nuitka 跨平台编译脚本
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def clean_directory(target_dir):
    """
    清空或创建目标目录
    
    Args:
        target_dir: 目标目录路径
    """
    target_path = Path(target_dir)
    
    if target_path.exists():
        print(f"清空目录: {target_dir}")
        for item in target_path.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    else:
        print(f"创建目录: {target_dir}")
        target_path.mkdir(parents=True, exist_ok=True)


def get_platform_specific_args():
    """
    获取平台特定的编译参数
    
    Returns:
        平台特定的Nuitka参数列表
    """
    system = sys.platform
    
    if system.startswith("win"):
        # Windows 平台参数
        return [
            # "--windows-icon-from-ico=source/img/ion/favicon.ico",
            "--windows-disable-console",  # GUI应用时使用
            "--msvc=latest",  # Python 3.13下需要指定MSVC编译器
        ]
    elif system.startswith("darwin"):
        # macOS 平台参数
        return [
            "--macos-create-app-bundle",
        ]
    else:
        # Linux 平台参数
        return []


def build_with_nuitka(
    source_file,
    target_dir="dist_nuitka",
    include_packages=None,
    include_modules=None,
    exclude_modules=None,
    data_files=None
):
    """
    使用Nuitka编译Python应用
    
    Args:
        source_file: 源Python文件路径
        target_dir: 输出目录
        include_packages: 需要包含的包列表
        include_modules: 需要包含的模块列表
        exclude_modules: 需要排除的模块列表
        data_files: 数据文件映射 {源文件: 目标文件名}
    """
    # 清空目标目录
    clean_directory(target_dir)
    
    print("开始使用Nuitka编译...")
    
    # 构建Nuitka命令
    cmd = [
        sys.executable, "-m", "nuitka",
        "--show-progress",
        "--jobs=8",
        "--standalone",
        "--lto=no",  # 禁用链接时优化以提高兼容性
        f"--output-dir={target_dir}",
    ]
    
    # 添加平台特定参数
    cmd.extend(get_platform_specific_args())
    
    # 添加包含的模块
    if include_modules:
        for module in include_modules:
            cmd.append(f"--include-module={module}")
    
    # 添加包含的包
    if include_packages:
        for package in include_packages:
            cmd.append(f"--include-package={package}")
    
    # 添加排除的模块
    if exclude_modules:
        for module in exclude_modules:
            cmd.append(f"--nofollow-import-to={module}")
    
    # 添加数据文件
    if data_files:
        for src, dst in data_files.items():
            cmd.append(f"--include-data-file={src}={dst}")
    
    # 添加源文件
    cmd.append(source_file)
    
    # 执行编译命令
    try:
        subprocess.run(cmd, check=True, env=os.environ)
        print(f"Python跨平台编译完成！输出目录: {target_dir}")
    except subprocess.CalledProcessError as e:
        print(f"编译失败: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("错误: 未找到Nuitka，请确保已安装Nuitka并激活了正确的Python环境")
        sys.exit(1)


def main():
    """主函数"""
    # 定义编译配置
    source_file = "src/app.py"
    target_dir = "dist_nuitka/app.dist"
    
    # 配置包含的模块
    include_modules = [
        "http.cookies",
        "zoneinfo"
    ]
    
    # 配置包含的包
    include_packages = [
        # "langchain_core",
        # "langchain_core.embeddings",
        # "setuptools",
        # "numpy",
        # "attr",
        # "pyaml",
        # "langchain_aws",
        # "langchain_community",
        # "langchain_ollama",
        # "langchain_openai",
        # "langchain_text_splitters",
        # "langchain",
        # "pydantic",
        # "pydantic_core",
        # "pydantic_settings"
    ]
    
    # 配置排除的模块
    exclude_modules = [
        # "neo4j"
    ]
    
    # 配置数据文件
    data_files = {
        "config.yaml": "config.yaml",
        "config.dev.yaml": "config.dev.yaml"
    }
    
    # 执行编译
    build_with_nuitka(
        source_file=source_file,
        target_dir=target_dir,
        include_packages=include_packages,
        include_modules=include_modules,
        exclude_modules=exclude_modules,
        data_files=data_files
    )


if __name__ == "__main__":
    main()