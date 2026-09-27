//! DAG 任务管理器(对齐 Python module_graph/utils/graph_utils/dag_tasks.py::DagTasks)
//!
//! 支持有向无环图的任务调度和依赖管理: 拓扑排序(含除环) → 初始就绪队列 →
//! 节点完成后解锁父节点(返回父节点在原图上的全部入边关系, 供业务按关系类型处理)。
//!
//! 并发说明: Python 版以 asyncio.Lock 保护 node_complete; Rust 版改为 `&mut self`
//! 独占借用, 由调用方(如 `Arc<tokio::sync::Mutex<DagTasks>>`)保证串行, 语义等价。

use std::collections::{HashMap, HashSet};

use super::graph::GraphData;
use super::remove_cycles::{topological_sort_with_remove_cycles, GraphError};
use crate::utils::do_::graph::{Node, NodeStatus, Relation};

/// DAG 任务管理器 —— 支持有向无环图的任务调度和依赖管理
#[derive(Debug, Default)]
pub struct DagTasks {
    /// 原始图
    graph: GraphData,
    /// 拓扑排序结果(节点 id 列表)
    nodes_sorted: Vec<String>,
    /// 正在处理的图(节点完成后逐步摘除)
    graph_dealing: Option<GraphData>,
    /// 节点状态跟踪
    node_status: HashMap<String, NodeStatus>,
}

impl DagTasks {
    /// 初始化(对齐 Python __init__ 的启动日志)
    pub fn new() -> Self {
        tracing::info!("======初始化DAG任务管理器======");
        Self::default()
    }

    /// 设置图结构(整图替换)
    pub fn set_graph(&mut self, graph: GraphData) {
        self.graph = graph;
    }

    /// 添加节点并初始化状态为等待处理
    pub fn add_node(&mut self, node: Node) {
        self.graph.add_node(node.clone());
        self.node_status.insert(node.id, NodeStatus::Pending);
    }

    /// 获取节点对象
    pub fn get_node(&self, node_id: &str) -> Option<&Node> {
        self.graph.get_node(node_id)
    }

    /// 添加边, 表示 pid 依赖 cid(cid 是 pid 的前置条件)
    pub fn add_edge(&mut self, relation: Relation) {
        self.graph.add_edge(relation);
    }

    /// 准备任务: 拓扑排序(附带循环移除)并返回初始可执行队列
    pub async fn prepare(&mut self) -> Result<Vec<Node>, GraphError> {
        // 拓扑排序(附带循环移除), 结果图作为原始图
        let (nodes_sorted, working) = topological_sort_with_remove_cycles(&self.graph)?;
        self.nodes_sorted = nodes_sorted;
        self.graph = working;
        // 初始化处理图(克隆副本, 与 Python graph.copy() 一致)
        self.graph_dealing = Some(self.graph.clone());
        // 重置所有节点状态
        self.node_status = self
            .graph
            .node_ids()
            .map(|id| (id.to_string(), NodeStatus::Pending))
            .collect();
        // 获取入度为 0 的初始队列并置为就绪
        let initial_queue = self.initial_queue();
        for node in &initial_queue {
            self.node_status.insert(node.id.clone(), NodeStatus::Ready);
        }
        Ok(initial_queue)
    }

    /// 重新准备图, 用于任务失败后的恢复(仅对处理图重排序)
    pub async fn repare_graph(&mut self) -> Result<Vec<Node>, GraphError> {
        let dealing = self
            .graph_dealing
            .take()
            .ok_or(GraphError::Unsolvable)?;
        let (nodes_sorted, working) = topological_sort_with_remove_cycles(&dealing)?;
        self.nodes_sorted = nodes_sorted;
        self.graph_dealing = Some(working);
        let initial_queue = self.initial_queue();
        for node in &initial_queue {
            self.node_status.insert(node.id.clone(), NodeStatus::Ready);
        }
        Ok(initial_queue)
    }

    /// 获取处理图中入度为 0 的初始队列(按拓扑序截取前缀, 对齐 Python _get_initial_queue)
    fn initial_queue(&self) -> Vec<Node> {
        let dealing = match &self.graph_dealing {
            Some(g) => g,
            None => return Vec::new(),
        };
        let mut initial_queue = Vec::new();
        for node_id in &self.nodes_sorted {
            if dealing.in_degree(node_id) != 0 {
                break;
            }
            if let Some(node) = dealing.get_node(node_id) {
                initial_queue.push(node.clone());
            }
        }
        initial_queue
    }

    /// 节点处理完成, 获取可执行的父节点及其原始关系集合
    ///
    /// :param node_complete_ids: 已完成的节点 id 列表
    /// :return: 键为可执行的父节点 id(入度归零), 值为该父节点在原图上的全部入边关系
    pub async fn node_complete(
        &mut self,
        node_complete_ids: Vec<String>,
    ) -> HashMap<String, HashSet<Relation>> {
        let mut relation_node_all_dict: HashMap<String, HashSet<Relation>> = HashMap::new();
        let mut affected_parent_ids: Vec<String> = Vec::new();

        // 处理每个完成的节点
        let dealing = match self.graph_dealing.as_mut() {
            Some(g) => g,
            None => return relation_node_all_dict,
        };
        for node_complete_id in node_complete_ids {
            if !dealing.contains_node(&node_complete_id) {
                tracing::warn!("节点 {node_complete_id} 不存在于处理图中");
                continue;
            }
            // 更新节点状态
            self.node_status
                .insert(node_complete_id.clone(), NodeStatus::Completed);
            // 收集所有受影响的父节点(保序去重)
            for parent_id in dealing.out_neighbors(&node_complete_id) {
                if !affected_parent_ids.iter().any(|p| p == parent_id) {
                    affected_parent_ids.push(parent_id.clone());
                }
            }
            // 删除已完成节点, 减少父节点入度
            dealing.remove_node(&node_complete_id);
        }

        // 检查哪些父节点现在可以处理(入度为 0)
        for parent_id in affected_parent_ids {
            if dealing.contains_node(&parent_id) && dealing.in_degree(&parent_id) == 0 {
                // 从原图获取所有指向该父节点的关系
                let entry = relation_node_all_dict.entry(parent_id.clone()).or_default();
                for rel in self.graph.in_edges(&parent_id) {
                    entry.insert(rel.clone());
                }
                // 更新父节点状态
                self.node_status.insert(parent_id, NodeStatus::Ready);
            }
        }
        relation_node_all_dict
    }

    /// 获取节点状态(未知节点视为等待处理)
    pub fn get_node_status(&self, node_id: &str) -> NodeStatus {
        self.node_status
            .get(node_id)
            .copied()
            .unwrap_or(NodeStatus::Pending)
    }

    /// 获取所有待处理的节点(按节点插入序)
    pub fn get_all_pending_nodes(&self) -> Vec<Node> {
        self.graph
            .node_ids()
            .filter(|id| self.get_node_status(id) == NodeStatus::Pending)
            .filter_map(|id| self.graph.get_node(id).cloned())
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn node(id: &str) -> Node {
        Node { id: id.to_string() }
    }

    fn rel(cid: &str, pid: &str, r: &str) -> Relation {
        Relation { cid: cid.to_string(), pid: pid.to_string(), rel: r.to_string() }
    }

    /// 链式依赖: C → B → A(无环), 验证拓扑序/初始队列/级联解锁
    #[tokio::test]
    async fn chain_dag_schedule() {
        let mut dag = DagTasks::new();
        for id in ["A", "B", "C"] {
            dag.add_node(node(id));
        }
        dag.add_edge(rel("B", "A", "belong"));
        dag.add_edge(rel("C", "B", "reference"));

        let initial = dag.prepare().await.unwrap();
        // 拓扑序为 C,B,A, 初始队列只含入度 0 的 C
        assert_eq!(initial, vec![node("C")]);
        assert_eq!(dag.get_node_status("C"), NodeStatus::Ready);

        // C 完成 → B 入度归零, 返回 B 在原图上的全部入边关系
        let unlocked = dag.node_complete(vec!["C".into()]).await;
        assert_eq!(dag.get_node_status("C"), NodeStatus::Completed);
        assert_eq!(dag.get_node_status("B"), NodeStatus::Ready);
        let rels = unlocked.get("B").unwrap();
        assert_eq!(rels.len(), 1);
        assert!(rels.contains(&rel("C", "B", "reference")));

        // B 完成 → A 解锁
        let unlocked = dag.node_complete(vec!["B".into()]).await;
        assert!(unlocked.contains_key("A"));
        assert_eq!(dag.get_node_status("A"), NodeStatus::Ready);
        assert!(dag.get_all_pending_nodes().is_empty());
    }

    /// 复刻 Python __main__ 场景: 存在 A-D/B-D 双环, 验证自动除环后调度
    #[tokio::test]
    async fn cyclic_graph_remove_cycles_and_schedule() {
        let mut dag = DagTasks::new();
        for id in ["A", "B", "C", "D", "E", "F"] {
            dag.add_node(node(id));
        }
        let nodes_rels = [
            rel("B", "A", "belong"),
            rel("C", "A", "belong"),
            rel("D", "A", "belong"),
            rel("C", "B", "reference"),
            rel("D", "B", "reference"),
            rel("A", "D", "reference"),
            rel("B", "D", "reference"),
            rel("D", "F", "reference"),
            rel("D", "E", "reference"),
        ];
        for r in nodes_rels {
            dag.add_edge(r.clone());
        }

        let initial = dag.prepare().await.unwrap();
        // 除环后 C、D 入度归零, 构成初始可执行队列
        assert_eq!(initial, vec![node("C"), node("D")]);

        // C 完成: 其父节点 A/B 仍各有一条入边, 暂无解锁
        let unlocked = dag.node_complete(vec!["C".into()]).await;
        assert!(unlocked.is_empty());
        assert_eq!(dag.get_node_status("C"), NodeStatus::Completed);

        // D 完成 → B/E/F 解锁(关系集取自原图入边)
        let unlocked = dag.node_complete(vec!["D".into()]).await;
        assert_eq!(unlocked.get("B").unwrap().len(), 2);
        assert!(unlocked.get("E").unwrap().contains(&rel("D", "E", "reference")));
        assert!(unlocked.get("F").unwrap().contains(&rel("D", "F", "reference")));
        assert_eq!(dag.get_node_status("B"), NodeStatus::Ready);
        assert_eq!(dag.get_node_status("E"), NodeStatus::Ready);
        assert_eq!(dag.get_node_status("F"), NodeStatus::Ready);
        assert_eq!(dag.get_node_status("A"), NodeStatus::Pending);

        // B 完成 → A 解锁(原图 3 条入边关系)
        let unlocked = dag.node_complete(vec!["B".into()]).await;
        assert_eq!(unlocked.get("A").unwrap().len(), 3);
        assert_eq!(dag.get_node_status("A"), NodeStatus::Ready);
        assert!(dag.get_all_pending_nodes().iter().all(|n| n.id == "A"));
    }
}
