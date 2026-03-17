import os
import stat
import shutil
from pathlib import Path
from datetime import datetime

class DirManager:
    """目录管理工具类"""
    
    @staticmethod
    def _handle_remove_readonly(func, path,exc_info):
        """处理只读文件删除的内部方法"""
        print(f"修改文件权限为可写删除目录: {path}")
        os.chmod(path, stat.S_IWRITE)
        func(path)
    
    @staticmethod
    def create_dir(dir_path: str, permissions=0o777):
        """
        创建文件夹并赋予权限
        :param dir_path: 文件夹路径
        :param permissions: 权限设置，默认0o777(所有权限)
        :return: 创建的Path对象
        """
        path = Path(dir_path)
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(str(path), permissions)
        return path
    
    @staticmethod
    def remove_dir(dir_path: str):
        """
        删除文件夹(包括只读文件)
        :param dir_path: 要删除的文件夹路径
        """
        path = Path(dir_path)
        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path, onerror=DirManager._handle_remove_readonly)
    
    @staticmethod
    def get_dir_info(dir_path: str):
        """
        获取文件夹信息
        :param dir_path: 文件夹路径
        :return: 包含文件夹信息的字典
        """
        path = Path(dir_path)
        if not path.exists():
            return None
            
        stat_info = os.stat(str(path))
        return {
            'path': str(path.absolute()),
            'size': sum(f.stat().st_size for f in path.glob('**/*') if f.is_file()),
            'created': datetime.fromtimestamp(stat_info.st_ctime),
            'modified': datetime.fromtimestamp(stat_info.st_mtime),
            'file_count': sum(1 for _ in path.glob('**/*') if _.is_file()),
            'dir_count': sum(1 for _ in path.glob('**/*') if _.is_dir())
        }
    
    @staticmethod
    def copy_dir(src_dir: str, dest_dir: str = None, overwrite=False):
        """
        复制文件夹到新位置
        :param src_dir: 源文件夹路径
        :param dest_dir: 目标文件夹路径(不指定则自动添加日期后缀)
        :param overwrite: 是否覆盖已存在的目录
        :return: 新目录的Path对象
        """
        if not dest_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_dir = f"{src_dir}_{timestamp}"
        
        dest_path = Path(dest_dir)
        
        if dest_path.exists():
            if overwrite:
                DirManager.remove_dir(dest_dir)
            else:
                raise FileExistsError(f"目标目录已存在: {dest_dir}")
        
        shutil.copytree(src_dir, dest_dir)
        return dest_path
    
    @staticmethod
    def set_permissions(dir_path: str, permissions=0o777):
        """
        设置文件夹及其内容权限
        :param dir_path: 文件夹路径
        :param permissions: 权限设置，默认0o777(所有权限)
        """
        path = Path(dir_path)
        for root, dirs, files in os.walk(str(path)):
            for d in dirs:
                os.chmod(os.path.join(root, d), permissions)
            for f in files:
                os.chmod(os.path.join(root, f), permissions)
        os.chmod(str(path), permissions)