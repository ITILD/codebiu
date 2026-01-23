# 除环工具类
import networkx as nx
import logging
logger = logging.getLogger(__name__)


async def topological_sort_with_remove_cycles(graph: nx.DiGraph) -> tuple[list[str], nx.DiGraph]:
    """
    增强版的拓扑排序与循环移除算法

    优化点：
    1. 减少深拷贝次数，提升性能
    2. 优化循环检测和边移除策略
    3. 增加详细的日志记录
    4. 添加最大重试保护机制
    5. 使用 find_cycle 替代 simple_cycles 提升性能
    """
    logger.info("开始循环检测和移除处理")

    try:
        working_graph = graph.copy()
        max_retries = len(graph.edges())
        retry_count = 0
        removed_edges: set[tuple[str, str]] = set()

        while retry_count < max_retries:
            try:
                nodes_sorted = list(nx.topological_sort(working_graph))
                logger.info(f"拓扑排序成功，移除了 {retry_count} 条循环边")
                return nodes_sorted, working_graph

            except nx.NetworkXUnfeasible:
                retry_count += 1
                logger.warning(f"检测到循环（第 {retry_count}/{max_retries} 次尝试）")

                # 获取循环边
                cycle_edges = find_cycle_edges(working_graph, removed_edges)

                if not cycle_edges:
                    logger.error("未找到循环边但排序失败，尝试紧急处理")
                    edge_to_remove = emergency_edge_removal(working_graph)
                    if edge_to_remove:
                        working_graph.remove_edge(*edge_to_remove)
                        removed_edges.add(edge_to_remove)
                        logger.warning(f"紧急移除边: {edge_to_remove[0]} -> {edge_to_remove[1]}")
                        continue
                    raise RuntimeError("无法确定导致拓扑排序失败的边")

                # 选择最优边移除
                edge_to_remove = select_optimal_edge(working_graph, cycle_edges)

                # 先获取权重再移除边
                weight = working_graph[edge_to_remove[0]][edge_to_remove[1]].get('weight', 1)
                working_graph.remove_edge(*edge_to_remove)
                removed_edges.add(edge_to_remove)

                logger.warning(
                    f"移除循环边: {edge_to_remove[0]} -> {edge_to_remove[1]} "
                    f"(入度: {working_graph.in_degree(edge_to_remove[1]) + 1}, 权重: {weight})"
                )

        raise RuntimeError(f"无法在 {max_retries} 次尝试内解决所有循环")

    except Exception as e:
        logger.error(
            f"拓扑排序失败: {str(e)} | "
            f"节点数={len(working_graph.nodes())}, 边数={len(working_graph.edges())}"
        )
        logger.debug("当前图边信息:\n" + "\n".join(f"{u} -> {v}" for u, v in working_graph.edges()))
        raise RuntimeError("拓扑排序处理失败") from e


def find_cycle_edges(graph: nx.DiGraph, removed_edges: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """查找图中的循环边"""
    cycle_edges: set[tuple[str, str]] = set()
    try:
        # 使用 find_cycle 快速找到一个循环
        cycle = nx.find_cycle(graph, orientation='original')
        for edge in cycle:
            # nx.find_cycle 返回三元组 (u, v, key)，我们只需要前两个元素
            u, v = edge[0], edge[1]
            if (u, v) not in removed_edges:
                cycle_edges.add((u, v))
    except nx.NetworkXNoCycle:
        pass
    return cycle_edges


def emergency_edge_removal(graph: nx.DiGraph) -> tuple[str, str] | None:
    """紧急处理：尝试逐条移除边直到拓扑排序成功"""
    for u, v in list(graph.edges()):
        temp_graph = graph.copy()
        temp_graph.remove_edge(u, v)
        try:
            list(nx.topological_sort(temp_graph))
            return (u, v)
        except nx.NetworkXUnfeasible:
            continue
    return None


def select_optimal_edge(graph: nx.DiGraph, cycle_edges: set[tuple[str, str]]) -> tuple[str, str]:
    """选择最优的边进行移除：优先移除入度小、权重低的边"""
    edge_scores: list[tuple[str, str, int]] = []
    for u, v in cycle_edges:
        in_degree_v = graph.in_degree(v)
        weight = graph[u][v].get('weight', 1)
        edge_scores.append((u, v, -in_degree_v * weight))

    edge_scores.sort(key=lambda x: x[2])
    return edge_scores[0][:2]

