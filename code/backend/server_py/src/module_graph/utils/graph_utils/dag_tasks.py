import asyncio
import networkx as nx
from module_graph.utils.graph_utils.remove_cycles import (
    topological_sort_with_remove_cycles,
)
from module_graph.utils.do.graph import Node, Relation, NodeStatus
import logging
logger = logging.getLogger(__name__)


class DagTasks:
    """DAG任务管理器 - 支持有向无环图的任务调度和依赖管理"""

    def __init__(self):
        logger.info("======初始化DAG任务管理器======")
        self.graph = nx.DiGraph()  # 原始图
        self.nodes_sorted: list[str] = []  # 拓扑排序结果（节点ID列表）
        self.graph_dealing: nx.DiGraph | None = None  # 正在处理的图
        self.graph_lock = asyncio.Lock()
        self.node_status: dict[str, NodeStatus] = {}  # 节点状态跟踪

    def set_graph(self, graph: nx.DiGraph):
        """设置图结构"""
        self.graph = graph

    def add_node(self, node: Node):
        """添加节点并初始化状态"""
        self.graph.add_node(node.id, node=node)
        self.node_status[node.id] = NodeStatus.PENDING

    def get_node(self, node_id: str) -> Node:
        """获取节点对象"""
        return self.graph.nodes[node_id]["node"]

    def add_edge(self, relation: Relation):
        """添加边，表示pid依赖cid（cid是pid的前置条件）"""
        # add_edge(u, v) 表示 u → v，即 v 依赖 u
        self.graph.add_edge(relation.cid, relation.pid, relation=relation)

    async def prepare(self) -> list[Node]:
        """准备任务，执行拓扑排序并返回初始可执行队列"""
        # 拓扑排序（附带循环移除）
        self.nodes_sorted, self.graph = await topological_sort_with_remove_cycles(
            self.graph
        )
        # 初始化处理图（使用浅拷贝优化性能）
        self.graph_dealing = self.graph.copy()
        # 重置所有节点状态
        self.node_status = {
            node_id: NodeStatus.PENDING for node_id in self.graph.nodes()
        }
        # 获取入度为0的初始队列
        initial_queue = self._get_initial_queue(self.nodes_sorted)
        # 更新初始队列节点状态
        for node in initial_queue:
            self.node_status[node.id] = NodeStatus.READY
        return initial_queue

    async def repare_graph(self) -> list[Node]:
        """重新准备图，用于任务失败后的恢复"""
        (
            self.nodes_sorted,
            self.graph_dealing,
        ) = await topological_sort_with_remove_cycles(self.graph_dealing)
        initial_queue = self._get_initial_queue(self.nodes_sorted)
        # 更新初始队列节点状态
        for node in initial_queue:
            self.node_status[node.id] = NodeStatus.READY
        return initial_queue

    def _get_initial_queue(self, sorted_nodes: list[str]) -> list[Node]:
        """获取初始入度为0的节点"""
        initial_queue: list[Node] = []
        # nodes_sorted 是按拓扑排序的节点ID列表
        for node_id in sorted_nodes:
            if self.graph_dealing.in_degree(node_id) != 0:
                break
            node = self.graph_dealing.nodes[node_id]["node"]
            initial_queue.append(node)
        return initial_queue

    async def node_complete(
        self, node_complete_ids: list[str]
    ) -> dict[str, set[Relation]]:
        """
        节点处理完成，获取可执行的父节点及其关系

        Args:
            node_complete_ids: 已完成的节点ID列表

        Returns:
            字典，键为可执行的父节点ID，值为该父节点的所有关系集合
        """
        relation_node_all_dict: dict[str, set[Relation]] = {}
        affected_parent_ids: set[str] = set()

        async with self.graph_lock:
            # 处理每个完成的节点
            for node_complete_id in node_complete_ids:
                if not self.graph_dealing.has_node(node_complete_id):
                    logger.warning(f"节点 {node_complete_id} 不存在于处理图中")
                    continue

                # 更新节点状态
                self.node_status[node_complete_id] = NodeStatus.COMPLETED

                # 收集所有受影响的父节点
                for _, parent_id, _ in self.graph_dealing.out_edges(
                    node_complete_id, data=True
                ):
                    affected_parent_ids.add(parent_id)

                # 删除已完成节点，减少父节点入度
                self.graph_dealing.remove_node(node_complete_id)

            # 检查哪些父节点现在可以处理（入度为0）
            for parent_id in affected_parent_ids:
                if self.graph_dealing.in_degree(parent_id) == 0:
                    # 从原图获取所有指向该父节点的关系
                    if parent_id not in relation_node_all_dict:
                        relation_node_all_dict[parent_id] = set()

                    for _, _, edge_attrs in self.graph.in_edges(parent_id, data=True):
                        relation_node_all_dict[parent_id].add(edge_attrs["relation"])

                    # 更新父节点状态
                    self.node_status[parent_id] = NodeStatus.READY

            return relation_node_all_dict

    def get_node_status(self, node_id: str) -> NodeStatus:
        """获取节点状态"""
        return self.node_status.get(node_id, NodeStatus.PENDING)

    def get_all_pending_nodes(self) -> list[Node]:
        """获取所有待处理的节点"""
        return [
            self.graph.nodes[node_id]["node"]
            for node_id, status in self.node_status.items()
            if status == NodeStatus.PENDING
        ]


if __name__ == "__main__":
    nodes_rels = [
        Relation(cid="B", pid="A", rel="belong"),
        Relation(cid="C", pid="A", rel="belong"),
        Relation(cid="D", pid="A", rel="belong"),
        Relation(cid="C", pid="B", rel="reference"),
        Relation(cid="D", pid="B", rel="reference"),
        Relation(cid="A", pid="D", rel="reference"),
        Relation(cid="B", pid="D", rel="reference"),
        Relation(cid="D", pid="F", rel="reference"),
        Relation(cid="D", pid="E", rel="reference"),
    ]
    nodes = [
        Node(id="A", node_type="file", content="文件A"),
        Node(id="B", node_type="function", content="函数B"),
        Node(id="C", node_type="function", content="函数C"),
        Node(id="D", node_type="function", content="函数D"),
        Node(id="E", node_type="function", content="函数E"),
        Node(id="F", node_type="function", content="函数F"),
    ]

    async def main():
        # 初始化DAG任务
        dag_tasks = DagTasks()
        for node in nodes:
            dag_tasks.add_node(node)
        for rel in nodes_rels:
            dag_tasks.add_edge(rel)

        initial_queue = await dag_tasks.prepare()
        print(f"初始队列: {initial_queue}")
        relation_node_all_dict = await dag_tasks.node_complete(["D"])
        print(f"node:{node},relation_node_all_dict:{relation_node_all_dict}")
        relation_node_all_dict = await dag_tasks.node_complete(["C"])
        print(f"node:{node},relation_node_all_dict:{relation_node_all_dict}")

        # relation_node_all_dict = await dag_tasks.node_complete(["D","C"])
        # print(f"node:{node},relation_node_all_dict:{relation_node_all_dict}")
        relation_node_all_dict = await dag_tasks.node_complete(["B"])
        print(f"node:{node},relation_node_all_dict:{relation_node_all_dict}")

        pass

    asyncio.run(main())
