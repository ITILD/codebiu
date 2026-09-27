//! module-life 业务逻辑层(对齐 Python module_life/service/*.py)
//!
//! 业务规则(参数校验/模型可用性回退链/推算编排/分页组装)在此层;
//! 数据读写委托 dao 层, 经典算法调用 utils 层。

pub mod baby_name;
