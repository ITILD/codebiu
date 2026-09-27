//! module-graph —— 图计算模块(对齐 Python module_graph)
//!
//! Python 侧该模块无任何业务端点(config/server.py 挂载到 /graph 的是空应用),
//! 仅提供 DAG 任务调度工具集, 供任务编排等场景作为库复用; Rust 侧保持纯库定位:
//! - utils::do_::graph       节点/关系/节点状态数据对象(对齐 utils/do/graph.py)
//! - utils::graph_utils      除环拓扑排序 + DAG 任务管理器(对齐 utils/graph_utils/*)
//!
//! 说明: Python 依赖 networkx, Rust 侧以等价的最小图结构(GraphData)手工实现,
//! 保持 Kahn 拓扑排序 + 三色 DFS 找环 + 启发式除环的算法语义一致。

pub mod utils;
