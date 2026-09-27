//! 除环与拓扑排序工具(对齐 Python module_graph/utils/graph_utils/remove_cycles.py)
//!
//! 算法语义与 Python 版一致: 反复尝试拓扑排序, 失败则按启发式
//! (优先移除指向"入度高"节点的边, Python 版 edge_score = -in_degree * weight)
//! 移除一条环上边后重试, 最多尝试"边数"次。

use std::collections::HashSet;

use super::graph::GraphData;

/// 除环/排序失败错误
#[derive(Debug, thiserror::Error)]
pub enum GraphError {
    /// 无法确定导致拓扑排序失败的边
    #[error("无法确定导致拓扑排序失败的边")]
    Unsolvable,
    /// 无法在 max_retries 次尝试内解决所有循环
    #[error("无法在 {0} 次尝试内解决所有循环")]
    MaxRetries(usize),
    /// 拓扑排序处理失败(兜底包装)
    #[error("拓扑排序处理失败: {0}")]
    Failed(#[from] Box<GraphError>),
}

/// 增强版拓扑排序与循环移除(对齐 Python topological_sort_with_remove_cycles)
///
/// :param graph: 原始有向图(不被修改)
/// :return: (拓扑序节点 id 列表, 移除循环边后的新图)
pub fn topological_sort_with_remove_cycles(
    graph: &GraphData,
) -> Result<(Vec<String>, GraphData), GraphError> {
    tracing::info!("开始循环检测和移除处理");

    let mut working = graph.clone();
    let max_retries = working.edge_count();
    let mut removed_edges: HashSet<(String, String)> = HashSet::new();

    for retry in 0..max_retries {
        if let Some(nodes_sorted) = working.topo_sort() {
            tracing::info!("拓扑排序成功, 移除了 {retry} 条循环边");
            return Ok((nodes_sorted, working));
        }

        tracing::warn!("检测到循环(第 {}/{} 次尝试)", retry + 1, max_retries);

        // 获取循环边
        let cycle_edges = working.find_cycle_edges(&removed_edges);

        // 选择最优边移除: 无环边可移除时尝试紧急处理
        let edge_to_remove = if cycle_edges.is_empty() {
            tracing::warn!("未找到循环边但排序失败, 尝试紧急处理");
            emergency_edge_removal(&working).ok_or(GraphError::Unsolvable)?
        } else {
            select_optimal_edge(&working, &cycle_edges)
        };

        working.remove_edge(&edge_to_remove.0, &edge_to_remove.1);
        removed_edges.insert(edge_to_remove.clone());
        tracing::warn!(
            "移除循环边: {} -> {}",
            edge_to_remove.0,
            edge_to_remove.1
        );
    }

    Err(GraphError::MaxRetries(max_retries))
}

/// 紧急处理: 尝试逐条移除边直到拓扑排序成功(对齐 Python emergency_edge_removal)
fn emergency_edge_removal(graph: &GraphData) -> Option<(String, String)> {
    // 按边插入序枚举(与 Python graph.edges() 一致)
    let mut candidate_edges = Vec::new();
    for cid in graph.node_ids() {
        for pid in graph.out_neighbors(cid) {
            candidate_edges.push((cid.to_string(), pid.clone()));
        }
    }
    for (u, v) in candidate_edges {
        let mut temp = graph.clone();
        temp.remove_edge(&u, &v);
        if temp.topo_sort().is_some() {
            return Some((u, v));
        }
    }
    None
}

/// 选择最优的边进行移除: 优先移除指向"入度高"节点的边
///
/// 对齐 Python select_optimal_edge 的评分 edge_score = -in_degree(v) * weight;
/// 边权重恒为 1(Python 侧 add_edge 从未设置 weight 属性, 始终取默认值 1)。
/// 环边序列来自 DFS 路径, 顺序确定, 评分相同时取先出现者(Python 版为集合无序,
/// 此处行为确定化)。
fn select_optimal_edge(graph: &GraphData, cycle_edges: &[(String, String)]) -> (String, String) {
    let mut best_idx = 0;
    let mut best_score = isize::MIN;
    for (i, (_u, v)) in cycle_edges.iter().enumerate() {
        let score = -(graph.in_degree(v) as isize);
        if score > best_score {
            best_score = score;
            best_idx = i;
        }
    }
    cycle_edges[best_idx].clone()
}
