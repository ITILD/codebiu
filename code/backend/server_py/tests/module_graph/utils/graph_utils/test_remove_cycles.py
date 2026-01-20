import networkx as nx

from src.module_graph.utils.graph_utils.remove_cycles import (
    topological_sort_with_remove_cycles,
)
from src.module_graph.utils.do.graph import Node, Relation, NodeStatus
import pytest
import logging

logger = logging.getLogger(__name__)

relations = [
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

@pytest.mark.asyncio
async def test_remove_cycles():
    """测试除环功能"""
    # 创建包含循环的图
    graph = nx.DiGraph()
    for node in nodes:
        graph.add_node(node.id, node=node)
    for rel in relations:
        graph.add_edge(rel.cid, rel.pid, relation=rel)

    # 验证原始图确实包含循环
    try:
        list(nx.topological_sort(graph))
        assert False, "原始图应该包含循环，但拓扑排序成功了"
    except nx.NetworkXUnfeasible:
        logger.info("✓ 原始图确实包含循环")

    # 测试除环功能

    nodes_sorted, processed_graph = await topological_sort_with_remove_cycles(graph)

    # 验证处理后的图不再包含循环
    try:
        list(nx.topological_sort(processed_graph))
        logger.info("✓ 处理后的图不再包含循环")
    except nx.NetworkXUnfeasible:
        assert False, "处理后的图仍然包含循环"

    # 验证拓扑排序结果
    logger.info(f"拓扑排序结果: {nodes_sorted}")

    # 验证某些节点的顺序应该正确（根据依赖关系）
    # 例如，A依赖于D，所以D应该在A之前（但在这个循环中，我们需要看实际被移除的边）
    # 检查是否有合理的排序
    assert len(nodes_sorted) > 0, "拓扑排序结果不应该为空"

    logger.info(f"原始节点数: {len(graph.nodes())}")
    logger.info(f"原始边数: {len(graph.edges())}")
    logger.info(f"处理后节点数: {len(processed_graph.nodes())}")
    logger.info(f"处理后边数: {len(processed_graph.edges())}")
    logger.info(f"移除的边数: {len(graph.edges()) - len(processed_graph.edges())}")

    # 验证节点数量保持不变
    assert len(graph.nodes()) == len(processed_graph.nodes()), "节点数量应该保持不变"

    # 验证边的数量减少了（因为移除了循环边）
    assert len(graph.edges()) >= len(processed_graph.edges()), (
        "处理后的边数不应比原来多"
    )

    logger.info("✓ 所有测试通过！除环功能正常工作")


@pytest.mark.asyncio
async def test_dag_tasks_functionality():
    """测试DagTasks功能，使用原来的测试逻辑  有随机性"""
    from src.module_graph.utils.graph_utils.dag_tasks import DagTasks

    # 初始化DAG任务
    dag_tasks = DagTasks()
    for node in nodes:
        dag_tasks.add_node(node)
    for rel in relations:
        dag_tasks.add_edge(rel)

    initial_queue = await dag_tasks.prepare()
    logger.info(f"初始队列: {[n.id for n in initial_queue]}")

    # 测试节点完成
    relation_node_all_dict = await dag_tasks.node_complete(["D"])
    logger.info(f"完成节点D后可执行的父节点: {list(relation_node_all_dict.keys())}")

    relation_node_all_dict = await dag_tasks.node_complete(["C"])
    logger.info(f"完成节点C后可执行的父节点: {list(relation_node_all_dict.keys())}")

    relation_node_all_dict = await dag_tasks.node_complete(["B"])
    logger.info(f"完成节点B后可执行的父节点: {list(relation_node_all_dict.keys())}")

    # 验证所有节点最终都被处理
    all_nodes_processed = all(
        dag_tasks.get_node_status(node.id) in [NodeStatus.COMPLETED, NodeStatus.READY]
        for node in nodes
    )
    assert all_nodes_processed, "所有节点应该都被处理"
