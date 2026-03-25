#!/usr/bin/env python3
"""
Nuitka 模块化编译脚本
每个子模块独立编译为扩展模块（.pyd/.so）
主程序打包时直接包含，无需修改源码
"""

import os
import sys
import yaml
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional


class ModuleCompiler:
    """模块编译器"""
    
    def __init__(self, config_path: str = "tools/nuitka_build/module_build_config.yaml"):
        """
        初始化模块编译器
        
        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        self.project_root = Path(__file__).parent.parent.parent
        self.output_dir = self.project_root / self.config["build_config"]["output_dir"]
        self.modules_dir = self.output_dir / self.config["build_config"]["modules_dir"]
        
    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        config_file = self.project_root / config_path
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
        
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    
    def get_extension_suffix(self) -> str:
        """获取扩展模块后缀"""
        if sys.platform.startswith("win"):
            return ".pyd"
        elif sys.platform.startswith("darwin"):
            return ".so"
        else:
            return ".so"
    
    def compile_module(self, module: Dict) -> bool:
        """
        编译单个模块为扩展模块
        
        Args:
            module: 模块配置
            
        Returns:
            是否编译成功
        """
        module_name = module["name"]
        module_path = self.project_root / module["path"]
        
        if not module_path.exists():
            print(f"✗ 模块路径不存在: {module_path}")
            return False
        
        print(f"\n{'='*60}")
        print(f"编译模块: {module_name}")
        print(f"{'='*60}")
        
        # 构建Nuitka命令
        cmd = [
            sys.executable, "-m", "nuitka",
            "--module",  # 编译为扩展模块
            f"--output-dir={self.modules_dir}",
            "--show-progress",
            f"--jobs={self.config['compile_options']['jobs']}",
            f"--lto={self.config['compile_options']['lto']}",
        ]
        
        # 添加包含的包
        if "include_packages" in module:
            for pkg in module["include_packages"]:
                cmd.append(f"--include-package={pkg}")
        
        # 添加排除的模块
        if "exclude_modules" in module:
            for mod in module["exclude_modules"]:
                cmd.append(f"--nofollow-import-to={mod}")
        
        # 添加全局包含的模块
        for mod in self.config["build_config"]["global_include_modules"]:
            cmd.append(f"--include-module={mod}")
        
        # 添加模块路径
        cmd.append(str(module_path))
        
        print(f"命令: {' '.join(cmd[:8])} ...")
        
        # 执行编译
        try:
            subprocess.run(cmd, check=True, env=os.environ)
            print(f"✓ 模块 {module_name} 编译成功")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ 模块 {module_name} 编译失败: {e}")
            return False
    
    def compile_all_modules(
        self, 
        module_names: Optional[List[str]] = None,
        clean: bool = False
    ) -> Dict[str, bool]:
        """
        编译所有或指定模块
        
        Args:
            module_names: 要编译的模块列表，None表示编译所有标记为compile=true的模块
            clean: 是否清理之前的编译
            
        Returns:
            编译结果字典 {模块名: 是否成功}
        """
        # 清理编译目录
        if clean and self.modules_dir.exists():
            print(f"清理编译目录: {self.modules_dir}")
            shutil.rmtree(self.modules_dir)
        
        self.modules_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取要编译的模块
        modules_to_compile = []
        if module_names:
            # 编译指定模块
            for module in self.config["modules"]:
                if module["name"] in module_names:
                    modules_to_compile.append(module)
        else:
            # 编译所有标记为compile=true的模块
            for module in self.config["modules"]:
                if module.get("compile", False):
                    modules_to_compile.append(module)
        
        if not modules_to_compile:
            print("没有需要编译的模块")
            return {}
        
        # 按优先级排序
        modules_to_compile.sort(key=lambda m: m["priority"])
        
        print(f"\n准备编译 {len(modules_to_compile)} 个模块...")
        
        # 编译每个模块
        results = {}
        for module in modules_to_compile:
            results[module["name"]] = self.compile_module(module)
        
        # 打印摘要
        print(f"\n{'='*60}")
        print("编译摘要")
        print(f"{'='*60}")
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        print(f"成功: {success_count}/{total_count}")
        for name, success in results.items():
            status = "✓" if success else "✗"
            print(f"  {status} {name}")
        
        return results
    
    def build_main_app(self, clean: bool = False) -> bool:
        """
        编译主程序
        
        Args:
            clean: 是否清理之前的构建
            
        Returns:
            是否编译成功
        """
        print(f"\n{'='*60}")
        print("编译主程序")
        print(f"{'='*60}")
        
        # 清理输出目录
        if clean and self.output_dir.exists():
            # 只删除主程序相关文件，保留编译的模块
            for item in self.output_dir.iterdir():
                if item.is_file() or (item.is_dir() and item.name != self.config["build_config"]["modules_dir"]):
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
        
        # 构建Nuitka命令
        cmd = [
            sys.executable, "-m", "nuitka",
            "--standalone",
            f"--output-dir={self.output_dir}",
            "--show-progress",
            f"--jobs={self.config['compile_options']['jobs']}",
            f"--lto={self.config['compile_options']['lto']}",
        ]
        
        # 添加平台特定参数
        if sys.platform.startswith("win"):
            pass
        elif sys.platform.startswith("darwin"):
            cmd.append("--macos-create-app-bundle")
        
        # 添加全局包含的模块
        for mod in self.config["build_config"]["global_include_modules"]:
            cmd.append(f"--include-module={mod}")
        
        # 添加数据文件
        for src, dst in self.config["build_config"]["data_files"].items():
            src_path = self.project_root / src
            if src_path.exists():
                cmd.append(f"--include-data-file={src}={dst}")
        
        # 添加数据目录
        for data_dir in self.config["build_config"]["data_dirs"]:
            data_dir_path = self.project_root / data_dir
            if data_dir_path.exists():
                cmd.append(f"--include-data-dir={data_dir}={data_dir}")
        
        # 添加编译好的模块目录
        if self.modules_dir.exists():
            cmd.append(f"--include-data-dir={self.modules_dir}=compiled_modules")
        
        # 添加主入口文件
        entry_point = self.project_root / self.config["build_config"]["entry_point"]
        cmd.append(str(entry_point))
        
        print(f"命令: {' '.join(cmd[:8])} ...")
        
        # 执行编译
        try:
            subprocess.run(cmd, check=True, env=os.environ)
            print(f"\n✓ 主程序编译成功")
            print(f"✓ 输出目录: {self.output_dir}")
            
            # 复制编译的模块到主程序目录
            self._copy_compiled_modules()
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"\n✗ 主程序编译失败: {e}")
            return False
    
    def _copy_compiled_modules(self):
        """复制编译的模块到主程序目录"""
        if not self.modules_dir.exists():
            return
        
        # 找到主程序的可执行文件目录
        app_dist_dir = None
        for item in self.output_dir.iterdir():
            if item.is_dir() and item.name.endswith(".dist"):
                app_dist_dir = item
                break
        
        if not app_dist_dir:
            print("⚠ 未找到主程序目录，跳过复制编译模块")
            return
        
        # 复制编译的模块
        target_dir = app_dist_dir / "compiled_modules"
        if target_dir.exists():
            shutil.rmtree(target_dir)
        
        shutil.copytree(self.modules_dir, target_dir)
        print(f"✓ 编译模块已复制到: {target_dir}")
        
        # 创建__init__.py以便Python识别为包
        self._create_init_files(target_dir)
    
    def _create_init_files(self, root_dir: Path):
        """递归创建__init__.py文件"""
        for item in root_dir.iterdir():
            if item.is_dir():
                init_file = item / "__init__.py"
                if not init_file.exists():
                    init_file.write_text("")
                self._create_init_files(item)
    
    def build_full(self, module_names: Optional[List[str]] = None, clean: bool = False):
        """
        完整构建：编译模块 + 编译主程序
        
        Args:
            module_names: 要编译的模块列表
            clean: 是否清理之前的构建
        """
        print(f"\n{'#'*60}")
        print("开始完整构建")
        print(f"{'#'*60}")
        
        # 编译模块
        module_results = self.compile_all_modules(module_names, clean)
        
        # 编译主程序
        app_success = self.build_main_app(clean=False)
        
        # 最终结果
        print(f"\n{'#'*60}")
        print("构建完成")
        print(f"{'#'*60}")
        print(f"模块编译: {sum(1 for v in module_results.values() if v)}/{len(module_results)}")
        print(f"主程序编译: {'成功' if app_success else '失败'}")
        print(f"输出目录: {self.output_dir}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Nuitka 模块化编译工具")
    parser.add_argument(
        "--modules",
        nargs="+",
        help="要编译的模块列表（如: common module_main）"
    )
    parser.add_argument(
        "--all-modules",
        action="store_true",
        help="编译所有模块（包括标记为compile=false的）"
    )
    parser.add_argument(
        "--main-only",
        action="store_true",
        help="只编译主程序（不编译模块）"
    )
    parser.add_argument(
        "--modules-only",
        action="store_true",
        help="只编译模块（不编译主程序）"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="清理之前的构建"
    )
    
    args = parser.parse_args()
    
    # 创建编译器
    compiler = ModuleCompiler()
    
    # 执行构建
    if args.main_only:
        # 只编译主程序
        compiler.build_main_app(clean=args.clean)
    elif args.modules_only:
        # 只编译模块
        if args.all_modules:
            # 编译所有模块
            module_names = [m["name"] for m in compiler.config["modules"]]
            compiler.compile_all_modules(module_names, clean=args.clean)
        else:
            # 编译指定模块或默认模块
            compiler.compile_all_modules(args.modules, clean=args.clean)
    else:
        # 完整构建
        if args.all_modules:
            module_names = [m["name"] for m in compiler.config["modules"]]
            compiler.build_full(module_names, clean=args.clean)
        else:
            compiler.build_full(args.modules, clean=args.clean)


if __name__ == "__main__":
    main()