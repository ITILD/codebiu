//! 节点/关系/节点状态(对齐 Python module_graph/utils/do/graph.py)
//!
//! Python 侧 Node 仅声明 id 字段(其余 __main__ 示例参数被 pydantic 忽略),
//! Relation 为 (cid, pid, rel) 三元组, NodeStatus 为节点生命周期状态。

use serde::{Deserialize, Serialize};

/// 节点
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Node {
    /// 节点唯一标识
    pub id: String,
}

/// 关系: cid 依赖 pid(边 cid → pid, pid 是 cid 的前置条件)
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Relation {
    /// 子节点(被依赖方所在任务的下游)
    pub cid: String,
    /// 父节点(前置条件)
    pub pid: String,
    /// 关系类型(belong/reference 等业务自定义字符串)
    pub rel: String,
}

/// 节点状态枚举(序列化为小写字符串, 与 Python str Enum 值一致)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum NodeStatus {
    /// 等待处理
    Pending,
    /// 准备就绪
    Ready,
    /// 处理中
    Processing,
    /// 已完成
    Completed,
    /// 失败
    Failed,
}
