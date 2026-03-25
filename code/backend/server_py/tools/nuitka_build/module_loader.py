#!/usr/bin/env python3
"""
模块加载器
支持从编译模块目录加载扩展模块
"""

import sys
from pathlib import Path


def setup_module_path():
    """
    设置模块搜索路径
    将编译模块目录添加到sys.path
    """
    # 获取可执行文件所在目录
    if getattr(sys, 'frozen', False):
        # 打包后的环境
        base_dir = Path(sys.executable).parent
    else:
        # 开发环境
        base_dir = Path(__file__).parent.parent.parent
    
    # 添加编译模块目录
    compiled_modules_dir = base_dir / "compiled_modules"
    if compiled_modules_dir.exists() and str(compiled_modules_dir) not in sys.path:
        sys.path.insert(0, str(compiled_modules_dir))
        print(f"✓ 添加编译模块路径: {compiled_modules_dir}")
    
    # 添加源码目录（用于未编译的模块）
    src_dir = base_dir / "src"
    if src_dir.exists() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
        print(f"✓ 添加源码路径: {src_dir}")


if __name__ == "__main__":
    setup_module_path()
    print("\n当前模块搜索路径:")
    for p in sys.path[:5]:
        print(f"  - {p}")