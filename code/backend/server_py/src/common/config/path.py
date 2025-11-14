from pathlib import Path
from common.config.index import conf
from common.utils.path.dir import Dir

# 基础配置
DIR_BASE: Path = Path(conf.dir.base)
DIR_SOURCE: Path = Dir.ensure_dir(DIR_BASE / conf.dir.base_child.source)
DIR_UPLOAD: Path = Dir.ensure_dir(DIR_BASE / conf.dir.base_child.upload)
DIR_LOG: Path = Dir.ensure_dir(DIR_BASE / conf.dir.base_child.log)
DIR_SYS_OUT: Path = Dir.ensure_dir(DIR_BASE / conf.dir.base_child.sys_out)
DIR_TEMP: Path = Dir.ensure_dir(DIR_BASE / conf.dir.base_child.temp)
DIR_DB: Path = Dir.ensure_dir(DIR_BASE / conf.dir.base_child.db)
DIR_TEST: Path = Dir.ensure_dir(DIR_BASE / conf.dir.base_child.test)
DIR_MODEL: Path = Dir.ensure_dir(DIR_BASE / conf.dir.base_child.model)

# 静态资源路径
DIR_PUBLIC: Path = Dir.ensure_dir(Path(conf.dir.public))