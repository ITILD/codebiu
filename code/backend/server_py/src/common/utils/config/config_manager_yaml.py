import yaml
from pathlib import Path

class ConfigManagerYaml:
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.config = {}
        self.load()

    def load(self):
        """加载配置文件，失败时使用空配置"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    self.config = data if data is not None else {}
            else:
                self.config = {}
        except (yaml.YAMLError, OSError) as e:
            raise RuntimeError(f"无法加载配置文件 {self.config_path}: {e}")

    def save(self):
        """保存配置到文件"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, allow_unicode=True, sort_keys=False, indent=2)
        except (OSError, yaml.YAMLError) as e:
            raise RuntimeError(f"无法保存配置文件 {self.config_path}: {e}")

    def get(self, key, default=None):
        """通过点号访问嵌套配置"""
        keys = key.split('.')
        value = self.config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key, value):
        """设置配置项（不立即保存）"""
        keys = key.split('.')
        current = self.config
        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value

    def delete(self, key):
        """删除配置项"""
        keys = key.split('.')
        try:
            current = self.config
            for k in keys[:-1]:
                current = current[k]
            del current[keys[-1]]
            return True
        except (KeyError, TypeError):
            return False

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)

    def __delitem__(self, key):
        if not self.delete(key):
            raise KeyError(key)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.save()

    def validate(self, required_keys):
        """检查必需的配置是否存在"""
        return all(self.get(key) is not None for key in required_keys)
        
if __name__ == '__main__':
    # 初始化配置管理器
    config = ConfigManagerYaml('config.yaml')

    # 获取配置项 __getitem__
    print(config.get('state').get('is_dev'))  # 输出: True
    print(config['server.host'])  # 输出: 0.0.0.0
    print(config['server.port'])  # 输出: 2666
    # 修改配置项
    # config['server.port'] = 3000
    # config.set('ai.new_provider.api_key', 'new_key_value')

    # # 添加新配置项
    # config['new_section'] = {
    #     'key1': 'value1',
    #     'key2': {
    #         'subkey': 'subvalue'
    #     }
    # }

    # # 删除配置项
    # del config['database.neo4j']
    # config.delete('ai.aliyun')

    # 检查配置是否已保存
    config.load()  # 重新加载确认更改
    