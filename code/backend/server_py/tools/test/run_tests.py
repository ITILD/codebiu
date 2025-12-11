#!/usr/bin/env python3
"""
测试运行工具
支持运行单个测试文件或整个测试目录
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_pytest(test_path: str, verbose: bool = False, log_level: str = "INFO") -> bool:
    """
    运行pytest测试
    
    Args:
        test_path: 测试路径(文件或目录)
        verbose: 是否显示详细输出
        log_level: 日志级别
        
    Returns:
        bool: 测试是否通过
    """
    # 构建pytest命令
    cmd = ["pytest", test_path]
    
    # 添加详细输出选项
    if verbose:
        cmd.extend(["-v", "-s"])
    
    # 添加日志级别
    cmd.extend(["--log-cli-level", log_level])
    
    # 添加项目路径
    cmd.extend(["--pythonpath", ".", "--pythonpath", "src"])
    
    print(f"运行测试: {' '.join(cmd)}")
    print("=" * 60)
    
    # 运行测试
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent.parent.parent)
        return result.returncode == 0
    except FileNotFoundError:
        print("错误: 未找到pytest命令，请确保已安装pytest")
        return False
    except Exception as e:
        print(f"运行测试时出错: {e}")
        return False


def list_test_files() -> None:
    """列出所有可用的测试文件"""
    tests_dir = Path(__file__).parent.parent.parent / "tests"
    
    print("可用的测试文件:")
    print("-" * 40)
    
    for test_file in tests_dir.rglob("test_*.py"):
        relative_path = test_file.relative_to(tests_dir.parent)
        print(f"  {relative_path}")
    
    print("-" * 40)
    print("使用示例:")
    print("  python tools/test/run_tests.py tests/common/config/test_db.py")
    print("  python tools/test/run_tests.py tests/module_main")
    print("  python tools/test/run_tests.py tests")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="测试运行工具")
    parser.add_argument(
        "test_path", 
        nargs="?", 
        default="tests",
        help="测试路径(文件或目录)，默认为整个tests目录"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true",
        help="显示详细输出"
    )
    parser.add_argument(
        "-l", "--log-level", 
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="日志级别(默认: INFO)"
    )
    parser.add_argument(
        "--list", 
        action="store_true",
        help="列出所有可用的测试文件"
    )
    
    args = parser.parse_args()
    
    # 列出测试文件
    if args.list:
        list_test_files()
        return
    
    # 检查测试路径是否存在
    test_path = Path(args.test_path)
    if not test_path.exists():
        # 尝试在tests目录下查找
        tests_path = Path("tests") / test_path
        if not tests_path.exists():
            print(f"错误: 测试路径 '{args.test_path}' 不存在")
            print("使用 --list 参数查看可用的测试文件")
            sys.exit(1)
        test_path = tests_path
    
    # 运行测试
    success = run_pytest(str(test_path), args.verbose, args.log_level)
    
    # 输出结果
    print("=" * 60)
    if success:
        print("✅ 所有测试通过!")
    else:
        print("❌ 测试失败!")
        sys.exit(1)


if __name__ == "__main__":
    main()