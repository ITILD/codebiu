from pathlib import Path
from dynaconf import Dynaconf

# 基础配置
conf = Dynaconf(settings_files=[Path("config.yaml")])
# 开发配置
if conf.state.get("config_path"):
    config_path = conf.state.config_path
    if not Path(conf.state.config_path).exists():
        raise FileNotFoundError(f"配置文件 {conf.state.config_path} 不存在")
    conf = Dynaconf(settings_files=[Path(conf.state.config_path)])
# 开发环境标识(影响系统log\数据库log的级别和模式)
is_dev: bool = conf.state.is_dev

if __name__ == "__main__":
    print(conf.state.is_dev)  # True
