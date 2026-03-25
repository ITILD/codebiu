"""使用 Nuitka 编译 Python 模块和主程序"""
# import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> int:
    """执行命令并实时流式输出日志"""
    print(f"开始：{description}")
    
    # 合并 stderr 到 stdout，确保日志顺序一致
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # 逐行读取并打印，实现动态效果
    if process.stdout:
        for line in process.stdout:
            print(line, end="", flush=True)
            
    process.wait()
    print(f"结束：{description} (返回码：{process.returncode})")
    return process.returncode


def build_module_cv() -> None:
    """编译 module_cv 子模块为共享库（.pyd 文件）"""
    project_root = Path(__file__).parent.parent.parent
    module_path = project_root / "src" / "module_cv"
    output_dir = project_root / "build" / "modules"
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Nuitka 编译模块命令
    cmd = [
        sys.executable,
        "-m", "nuitka",
        "--module",
        "--force-stdout-spec=%PROCESS%",  # 强制实时输出日志
        "--assume-yes-for-downloads",      # 自动确认下载依赖（关键参数）
         f"--output-dir={output_dir}",
        "src/module_cv"
    ]
    
    run_command(cmd, "编译 module_cv 子模块")


def build_app() -> None:
    """编译 app.py 主程序为独立可执行文件"""
    project_root = Path(__file__).parent.parent.parent
    app_path = project_root / "src" / "app.py"
    output_dir = project_root / "build" / "executable"
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Nuitka 编译主程序命令
    cmd = [
        sys.executable,
        "-m", "nuitka",
        "--standalone",
        str(app_path),
        f"--output-dir={output_dir}",
        "--include-module=module_cv.img_read",
        "--include-package=opencv-python",
        "--include-package=cv2",
        "--include-data-dir=public=public",
        "--assume-yes-for-downloads",
        "--show-progress",
        "--show-memory",
        "--enable-plugin=anti-bloat",
    ]
    
    run_command(cmd, "编译 app.py 主程序")


def build_all() -> None:
    """编译所有模块和主程序"""
    print("\n🚀 开始构建所有模块...")
    
    # 编译子模块
    build_module_cv()
    
    # 编译主程序
    build_app()
    
    print("\n🎉 所有模块编译完成！")
    print("\n📦 输出位置:")
    project_root = Path(__file__).parent.parent.parent
    print(f"  - 子模块共享库: {project_root / 'build' / 'modules'}")
    print(f"  - 主程序可执行文件: {project_root / 'build' / 'executable'}")


if __name__ == "__main__":
    import argparse
    
    # parser = argparse.ArgumentParser(description="使用 Nuitka 编译 Python 模块")
    # parser.add_argument(
    #     "--target",
    #     choices=["module", "app", "all"],
    #     default="all",
    #     help="编译目标: module(仅子模块), app(仅主程序), all(全部)"
    # )
    
    # args = parser.parse_args()
    
    # if args.target == "module":
    #     build_module_cv()
    # elif args.target == "app":
    #     build_app()
    # else:
    build_module_cv()