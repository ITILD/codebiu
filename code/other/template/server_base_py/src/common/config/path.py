from pathlib import Path
from common.config.index import conf
from common.utils.path.dir import Dir

# 基础配置
DIR_BASE: Path = Path(conf.dir.base)
DIR_LOG: Path = Dir.ensure_dir(DIR_BASE / conf.dir.base_child.log)