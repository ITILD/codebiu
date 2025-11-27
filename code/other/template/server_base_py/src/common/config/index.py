from pathlib import Path
from dynaconf import Dynaconf

# 基础配置
conf = Dynaconf(
    settings_files=[Path("config.yaml")],
    # 为可能不存在的配置项设置默认值
    merge_enabled=True,
    # # 设置默认值
    # default_settings={
    #     "dir": {
    #         "base": "temp",
    #         "base_child": {
    #             "log": "logs"
    #         }
    #     }
    # }
)
is_dev: bool = conf.state.is_dev

if __name__ == "__main__":
    print(conf.state.is_dev)  # True
