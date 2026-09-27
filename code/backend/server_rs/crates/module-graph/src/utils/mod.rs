//! utils 子包(对齐 Python module_graph/utils)

// 图数据对象层(目录与 Python utils/do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;
// 图算法工具(对齐 Python utils/graph_utils/)
pub mod graph_utils;
