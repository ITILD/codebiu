//! 有向图数据结构 —— networkx.DiGraph 的最小等价子集
//!
//! 仅覆盖 Python 侧实际用到的能力: 加点/加边/入度/出入边/删点/拓扑排序/找环;
//! 通过插入序 Vec 保证遍历顺序确定(与 networkx 节点/边插入序语义一致)。

use std::collections::{HashMap, HashSet, VecDeque};

use crate::utils::do_::graph::{Node, Relation};

/// 有向图(边不可重: 同一 (cid, pid) 重复加边时覆盖关系, 与 networkx.DiGraph 一致)
#[derive(Debug, Clone, Default)]
pub struct GraphData {
    /// 节点(插入序)
    nodes: Vec<Node>,
    /// 节点 id → nodes 下标
    node_index: HashMap<String, usize>,
    /// 出边邻接表: cid → [pid](插入序)
    out_adj: HashMap<String, Vec<String>>,
    /// 入边邻接表: pid → [cid](插入序)
    in_adj: HashMap<String, Vec<String>>,
    /// 边集合: (cid, pid) → 关系
    edges: HashMap<(String, String), Relation>,
}

impl GraphData {
    /// 构建空图
    pub fn new() -> Self {
        Self::default()
    }

    /// 添加节点(重复添加忽略, 幂等)
    pub fn add_node(&mut self, node: Node) {
        if self.node_index.contains_key(&node.id) {
            return;
        }
        self.node_index.insert(node.id.clone(), self.nodes.len());
        self.nodes.push(node);
    }

    /// 添加边(cid → pid, 表示 pid 依赖 cid; 同 (cid,pid) 重复添加覆盖关系)
    pub fn add_edge(&mut self, relation: Relation) {
        // networkx 语义: add_edge 自动补齐端点节点
        self.add_node(Node { id: relation.cid.clone() });
        self.add_node(Node { id: relation.pid.clone() });
        let key = (relation.cid.clone(), relation.pid.clone());
        if self.edges.insert(key.clone(), relation).is_none() {
            self.out_adj.entry(key.0.clone()).or_default().push(key.1.clone());
            self.in_adj.entry(key.1.clone()).or_default().push(key.0.clone());
        }
    }

    /// 删除边
    pub fn remove_edge(&mut self, cid: &str, pid: &str) {
        if self.edges.remove(&(cid.to_string(), pid.to_string())).is_some() {
            if let Some(list) = self.out_adj.get_mut(cid) {
                list.retain(|v| v != pid);
            }
            if let Some(list) = self.in_adj.get_mut(pid) {
                list.retain(|u| u != cid);
            }
        }
    }

    /// 删除节点及其所有关联边
    pub fn remove_node(&mut self, id: &str) {
        if !self.node_index.contains_key(id) {
            return;
        }
        // 先摘除关联边再删点(避免遍历时修改邻接表)
        for pid in self.out_adj.get(id).cloned().unwrap_or_default() {
            self.remove_edge(id, &pid);
        }
        for cid in self.in_adj.get(id).cloned().unwrap_or_default() {
            self.remove_edge(&cid, id);
        }
        self.out_adj.remove(id);
        self.in_adj.remove(id);
        self.node_index.remove(id);
        self.nodes.retain(|n| n.id != id);
    }

    /// 节点是否存在
    pub fn contains_node(&self, id: &str) -> bool {
        self.node_index.contains_key(id)
    }

    /// 按插入序遍历节点 id
    pub fn node_ids(&self) -> impl Iterator<Item = &str> {
        self.nodes.iter().map(|n| n.id.as_str())
    }

    /// 获取节点对象
    pub fn get_node(&self, id: &str) -> Option<&Node> {
        self.node_index.get(id).map(|&i| &self.nodes[i])
    }

    /// 节点数
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    /// 边数
    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }

    /// 入度(节点不存在时为 0)
    pub fn in_degree(&self, id: &str) -> usize {
        self.in_adj.get(id).map_or(0, Vec::len)
    }

    /// 出边邻接(插入序, 节点不存在时为空)
    pub fn out_neighbors(&self, id: &str) -> &[String] {
        self.out_adj.get(id).map_or(&[], Vec::as_slice)
    }

    /// 指向某节点的全部关系(原图 in_edges 语义)
    pub fn in_edges(&self, pid: &str) -> Vec<&Relation> {
        self.in_adj
            .get(pid)
            .map(|cids| cids.iter().map(|cid| &self.edges[&(cid.clone(), pid.to_string())]).collect())
            .unwrap_or_default()
    }

    /// Kahn 拓扑排序(队列按插入序消费, 与 networkx.topological_sort 顺序语义一致);
    /// 存在环时返回 None(对应 nx.NetworkXUnfeasible)。
    pub fn topo_sort(&self) -> Option<Vec<String>> {
        let mut indegree: HashMap<&str, usize> = self
            .nodes
            .iter()
            .map(|n| (n.id.as_str(), self.in_degree(&n.id)))
            .collect();
        let mut queue: VecDeque<&str> = self
            .nodes
            .iter()
            .filter(|n| indegree[n.id.as_str()] == 0)
            .map(|n| n.id.as_str())
            .collect();
        let mut sorted = Vec::with_capacity(self.nodes.len());
        while let Some(u) = queue.pop_front() {
            sorted.push(u.to_string());
            for v in self.out_neighbors(u) {
                let d = indegree.get_mut(v.as_str())?;
                *d -= 1;
                if *d == 0 {
                    queue.push_back(v);
                }
            }
        }
        (sorted.len() == self.nodes.len()).then_some(sorted)
    }

    /// 三色 DFS 找一条回路并返回环上边(对应 networkx.find_cycle 的单回路语义);
    /// `removed` 中的边视为已删除、不参与找环。未找到环返回空。
    pub fn find_cycle_edges(&self, removed: &HashSet<(String, String)>) -> Vec<(String, String)> {
        #[derive(Clone, Copy, PartialEq)]
        enum Color {
            White,
            Gray,
            Black,
        }
        let mut color: HashMap<&str, Color> =
            self.nodes.iter().map(|n| (n.id.as_str(), Color::White)).collect();
        let mut path: Vec<&str> = Vec::new();
        let mut pos: HashMap<&str, usize> = HashMap::new();

        // 递归 DFS: 命中灰色节点即回溯收集环上边, 找到一条即止
        fn visit<'g>(
            g: &'g GraphData,
            u: &'g str,
            color: &mut HashMap<&'g str, Color>,
            path: &mut Vec<&'g str>,
            pos: &mut HashMap<&'g str, usize>,
            removed: &HashSet<(String, String)>,
            out: &mut Vec<(String, String)>,
        ) -> bool {
            color.insert(u, Color::Gray);
            pos.insert(u, path.len());
            path.push(u);
            for v in g.out_neighbors(u) {
                if removed.contains(&(u.to_string(), v.clone())) {
                    continue;
                }
                match color.get(v.as_str()).copied().unwrap_or(Color::White) {
                    Color::White => {
                        if visit(g, v, color, path, pos, removed, out) {
                            return true;
                        }
                    }
                    // 回边 u → v: 收集 v..u→v 路径上的边
                    Color::Gray => {
                        let start = pos[v.as_str()];
                        for i in start..path.len() - 1 {
                            out.push((path[i].to_string(), path[i + 1].to_string()));
                        }
                        out.push((u.to_string(), v.clone()));
                        return true;
                    }
                    Color::Black => {}
                }
            }
            color.insert(u, Color::Black);
            path.pop();
            pos.remove(u);
            false
        }

        let mut out = Vec::new();
        // 复制节点序避免借用冲突
        let order: Vec<String> = self.node_ids().map(str::to_string).collect();
        for id in &order {
            if color[id.as_str()] == Color::White
                && visit(self, id, &mut color, &mut path, &mut pos, removed, &mut out)
            {
                break;
            }
        }
        out
    }
}
