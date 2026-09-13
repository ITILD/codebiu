"""工作流执行引擎: 按 Vue Flow 图(nodes/edges)驱动智能体工作流

- 图约定: node.type ∈ {start, end, llm, condition, template}, condition 出边以 sourceHandle=true/false 分支
- 变量引用: {{node_id.path.to.field}} 模板插值(整串单引用透传原对象, 否则字符串插值)
- 执行语义: 从 start 沿边 DFS; 合流为"首次到达执行, 重复到达跳过"(DAG, 一期不支持循环)
- 轨迹: 每节点记录输入/输出/耗时/状态, 失败即终止并抛 WorkflowExecuteError(携带已完成轨迹)
"""

import json
import logging
import re
import time
from enum import StrEnum
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from module_agent.do.agent import Agent, AgentIOType
from module_agent.do.agent_run import AgentRunRequest

logger = logging.getLogger(__name__)

# 变量引用语法: {{node_id.path.to.field}}(节点ID后可跟点路径)
_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\-]+)((?:\.[a-zA-Z0-9_\-]+)*)\s*\}\}")

# 一期支持的节点类型
NODE_TYPES = {"start", "end", "llm", "condition", "template"}

# 条件节点支持的运算符
CONDITION_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "empty", "regex"}


class WorkflowExecuteError(Exception):
    """工作流执行失败异常(携带已完成节点轨迹, 供运行历史落库排查)"""

    def __init__(self, message: str, traces: list["NodeTrace"] | None = None):
        super().__init__(message)
        self.traces = traces or []


class NodeTrace(BaseModel):
    """单节点执行轨迹(运行历史的节点级明细)"""

    node_id: str = Field(..., description="节点ID")
    node_type: str = Field(..., description="节点类型")
    status: str = Field(..., description="执行状态: success/failed/skipped")
    input: Any = Field(None, description="节点输入(上游节点输出快照)")
    output: Any = Field(None, description="节点输出")
    duration_ms: int = Field(default=0, description="执行耗时(毫秒)")
    error: str | None = Field(None, description="失败原因(status=failed 时)")


class TraceStatus(StrEnum):
    """节点执行状态"""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


def parse_json_content(content: Any) -> Any:
    """从模型文本中解析 JSON(容忍 ```json 围栏与首尾杂质; 供简单/工作流两链路共用)"""
    if not isinstance(content, str):
        return content
    text = content.strip()
    # 去掉 Markdown 代码块围栏
    if text.startswith("```"):
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text.strip("`")
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 截取首个 { 或 [ 到最后一个 } 或 ] 之间的内容再尝试
        start = -1
        for idx in (text.find("{"), text.find("[")):
            if idx != -1 and (start == -1 or idx < start):
                start = idx
        if start != -1:
            end_char = "}" if text[start] == "{" else "]"
            end = text.rfind(end_char)
            if end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
        return text


def validate_workflow(workflow: dict | None) -> list[str]:
    """静态校验工作流图, 返回错误列表(空列表=通过; 保存前与运行前均可调用)"""
    errors: list[str] = []
    if not isinstance(workflow, dict) or not workflow:
        return ["工作流图不能为空"]
    nodes = workflow.get("nodes") or []
    edges = workflow.get("edges") or []
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return ["工作流图 nodes/edges 格式不合法"]

    # 节点基础校验
    node_map: dict[str, dict] = {}
    for n in nodes:
        if not isinstance(n, dict):
            errors.append("存在格式不合法的节点")
            continue
        nid, ntype = n.get("id"), n.get("type")
        if not nid:
            errors.append("存在缺少 id 的节点")
            continue
        if nid in node_map:
            errors.append(f"节点 ID 重复: {nid}")
            continue
        if ntype not in NODE_TYPES:
            errors.append(f"节点 {nid} 类型不合法: {ntype}")
            continue
        node_map[nid] = n

    starts = [n for n in node_map.values() if n.get("type") == "start"]
    ends = [n for n in node_map.values() if n.get("type") == "end"]
    if len(starts) != 1:
        errors.append(f"开始节点必须恰好 1 个, 当前 {len(starts)} 个")
    if len(ends) != 1:
        errors.append(f"结束节点必须恰好 1 个, 当前 {len(ends)} 个")

    # 连线校验 + 上下游映射
    valid_edges: list[tuple[str, str]] = []
    for e in edges:
        if not isinstance(e, dict):
            errors.append("存在格式不合法的连线")
            continue
        src, tgt = e.get("source"), e.get("target")
        if src not in node_map or tgt not in node_map:
            errors.append(f"连线端点不存在: {src} → {tgt}")
            continue
        if src == tgt:
            errors.append(f"节点 {src} 不能连接自身")
            continue
        valid_edges.append((src, tgt))
        if node_map[src].get("type") == "condition":
            if e.get("sourceHandle") not in ("true", "false"):
                errors.append(f"条件节点 {src} 的出边必须使用 true/false 分支")

    # 条件节点必须同时具备 true/false 两条出边 + 数据校验
    for n in node_map.values():
        nid, ntype, data = n.get("id"), n.get("type"), n.get("data") or {}
        if ntype == "condition":
            handles = {
                e.get("sourceHandle")
                for e in edges
                if isinstance(e, dict) and e.get("source") == nid
            }
            if "true" not in handles or "false" not in handles:
                errors.append(f"条件节点 {nid} 必须同时连接 true 与 false 分支")
            if data.get("left_source") not in node_map:
                errors.append(f"条件节点 {nid} 的左值来源节点不存在: {data.get('left_source')}")
            if data.get("operator") not in CONDITION_OPERATORS:
                errors.append(f"条件节点 {nid} 运算符不合法: {data.get('operator')}")
        # 模板引用的节点必须存在
        texts: list[str] = []
        if ntype == "llm":
            texts.append(data.get("prompt") or "")
        elif ntype == "template":
            texts.append(data.get("template") or "")
        elif ntype == "end" and data.get("result"):
            texts.append(data.get("result"))
        for text in texts:
            for m in _VAR_PATTERN.finditer(text):
                if m.group(1) not in node_map:
                    errors.append(f"节点 {nid} 引用了不存在的节点: {m.group(1)}")

    # 环检测(Kahn 拓扑): 一期仅支持 DAG
    indegree = {nid: 0 for nid in node_map}
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_map}
    for src, tgt in valid_edges:
        adjacency[src].append(tgt)
        indegree[tgt] += 1
    queue = [nid for nid, deg in indegree.items() if deg == 0]
    visited_count = 0
    while queue:
        cur = queue.pop()
        visited_count += 1
        for nxt in adjacency[cur]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if visited_count != len(node_map):
        errors.append("工作流存在循环连线, 暂不支持循环")

    return errors


class WorkflowService:
    """工作流执行引擎(拓扑驱动 + 节点轨迹)"""

    def __init__(self, llm_service=None):
        """依赖注入构造器: llm_service 为 module_ai 的 LLMService(避免类型硬依赖)"""
        if llm_service is None:
            from module_ai.service.llm import LLMService

            llm_service = LLMService()
        self.llm_service = llm_service

    async def run_workflow(
        self, agent: Agent, request: AgentRunRequest
    ) -> tuple[Any, list[NodeTrace]]:
        """执行工作流: 拓扑序驱动(可达性由条件分支动态决定), 返回(结束节点输出, 节点轨迹)

        :param agent: 工作流智能体(agent.workflow 为图定义)
        :param request: 运行请求(input 为开始节点输入, model_id 为 LLM 节点默认模型)
        :raises WorkflowExecuteError: 节点失败即终止(异常携带已完成轨迹)
        """
        workflow = agent.workflow or {}
        nodes = {
            n["id"]: n
            for n in (workflow.get("nodes") or [])
            if isinstance(n, dict) and n.get("id")
        }
        out_edges: dict[str, list[dict]] = {}
        upstream: dict[str, list[str]] = {}
        for e in workflow.get("edges") or []:
            if not isinstance(e, dict):
                continue
            src, tgt = e.get("source"), e.get("target")
            if src in nodes and tgt in nodes:
                out_edges.setdefault(src, []).append(e)
                upstream.setdefault(tgt, []).append(src)

        start = next((n for n in nodes.values() if n.get("type") == "start"), None)
        if start is None:
            raise WorkflowExecuteError("工作流缺少开始节点")
        end = next((n for n in nodes.values() if n.get("type") == "end"), None)
        if end is None:
            raise WorkflowExecuteError("工作流缺少结束节点")

        # Kahn 拓扑排序: 保证可达上游均先于下游执行(环在保存校验拦截, 此处兜底)
        indegree = {nid: 0 for nid in nodes}
        adjacency: dict[str, list[str]] = {nid: [] for nid in nodes}
        for src, targets in out_edges.items():
            for e in targets:
                adjacency[src].append(e["target"])
                indegree[e["target"]] += 1
        queue = [nid for nid, deg in indegree.items() if deg == 0]
        topo: list[str] = []
        while queue:
            cur = queue.pop()
            topo.append(cur)
            for nxt in adjacency[cur]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        if len(topo) != len(nodes):
            raise WorkflowExecuteError("工作流存在循环连线, 暂不支持循环")

        traces: list[NodeTrace] = []
        ctx: dict[str, Any] = {}  # 节点输出上下文: node_id -> output
        active = {start["id"]}  # 可达节点集(条件分支未命中的路径不激活)

        for node_id in topo:
            if node_id not in active:
                continue  # 不可达节点(分支未命中路径)不执行
            node = nodes[node_id]
            ntype = node.get("type", "")
            node_input = {src: ctx.get(src) for src in upstream.get(node_id, [])}
            trace = NodeTrace(
                node_id=node_id,
                node_type=ntype,
                status=TraceStatus.SUCCESS.value,
                input=node_input or None,
            )
            started = time.monotonic()
            try:
                output = await self._execute_node(node, agent, request, ctx, traces)
                trace.output = output
                ctx[node_id] = output
            except Exception as e:
                trace.status = TraceStatus.FAILED.value
                trace.error = str(e)
                trace.duration_ms = int((time.monotonic() - started) * 1000)
                traces.append(trace)
                raise WorkflowExecuteError(f"节点 {node_id}({ntype}) 执行失败: {e}", traces) from e
            trace.duration_ms = int((time.monotonic() - started) * 1000)
            traces.append(trace)

            # 激活下游(条件节点仅激活布尔结果对应分支)
            for edge in out_edges.get(node_id, []):
                if ntype == "condition":
                    if edge.get("sourceHandle") == ("true" if output else "false"):
                        active.add(edge["target"])
                else:
                    active.add(edge["target"])

        if end["id"] not in ctx:
            raise WorkflowExecuteError("结束节点不可达(分支路径未连通结束节点)", traces)
        return ctx[end["id"]], traces

    async def _execute_node(
        self,
        node: dict,
        agent: Agent,
        request: AgentRunRequest,
        ctx: dict[str, Any],
        traces: list[NodeTrace],
    ) -> Any:
        """执行单个节点(按类型分发)"""
        ntype = node.get("type")
        data = node.get("data") or {}
        if ntype == "start":
            return request.input
        if ntype == "llm":
            return await self._run_llm_node(data, agent, request, ctx)
        if ntype == "condition":
            return self._evaluate_condition(data, ctx)
        if ntype == "template":
            return self._resolve_value(data.get("template") or "", ctx)
        if ntype == "end":
            result_text = data.get("result")
            if result_text:
                return self._resolve_value(result_text, ctx)
            # 默认取最后一个成功的 LLM 节点输出
            for trace in reversed(traces):
                if trace.node_type == "llm" and trace.status == TraceStatus.SUCCESS.value:
                    return ctx.get(trace.node_id)
            raise ValueError("结束节点未配置结果引用, 且工作流中没有已执行的 LLM 节点")
        raise ValueError(f"不支持的节点类型: {ntype}")

    async def _run_llm_node(
        self, data: dict, agent: Agent, request: AgentRunRequest, ctx: dict[str, Any]
    ) -> Any:
        """执行 LLM 节点: prompt 模板插值 → 模型推理(str 直出 / json 结构化+回退解析)"""
        prompt = self._resolve_value(data.get("prompt") or "", ctx)
        model_id = data.get("model_id") or request.model_id
        llm = await self.llm_service.get_llm(model_id, streaming=False)
        if llm is None:
            raise ValueError(f"模型配置不存在或不可用: {model_id}")

        messages = [
            SystemMessage(content=agent.system_prompt),
            HumanMessage(content=str(prompt)),
        ]
        output_type = data.get("output_type") or AgentIOType.STR
        if output_type == AgentIOType.JSON:
            schema = data.get("output_schema")
            if schema:
                messages[-1].content += (
                    f"\n\n### 输出结构要求(必须严格遵循此 JSON Schema)\n"
                    f"{json.dumps(schema, ensure_ascii=False)}"
                )
                try:
                    structured_llm = llm.with_structured_output(schema)
                    return await structured_llm.ainvoke(messages)
                except Exception as e:
                    logger.warning(f"结构化输出失败, 回退提示词解析: {e}")
            else:
                messages[-1].content += (
                    "\n\n### 输出结构要求\n输出合法的 JSON(对象或数组), 不要包含 Markdown 代码块标记。"
                )
            response = await llm.ainvoke(messages)
            return parse_json_content(response.content)
        response = await llm.ainvoke(messages)
        content = response.content
        return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)

    @staticmethod
    def _evaluate_condition(data: dict, ctx: dict[str, Any]) -> bool:
        """计算条件节点布尔结果(left_source.left_path 与 right 按 operator 比较)"""
        left_source = data.get("left_source")
        if left_source not in ctx:
            raise ValueError(f"条件左值来源节点尚未执行: {left_source}")
        left = ctx[left_source]
        left_path = data.get("left_path") or ""
        if left_path:
            for part in left_path.split("."):
                if not isinstance(left, dict) or part not in left:
                    raise ValueError(f"条件左值路径不合法: {left_path}")
                left = left[part]

        op = data.get("operator")
        right = data.get("right")

        def to_num(v: Any) -> float | None:
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        def to_text(v: Any) -> str:
            if isinstance(v, bool):
                return "true" if v else "false"
            return str(v)

        if op == "empty":
            return left is None or left == "" or left == [] or left == {}
        if op == "contains":
            if isinstance(left, (list, dict)):
                return right in left
            return to_text(right) in to_text(left)
        if op == "regex":
            return re.search(to_text(right), to_text(left)) is not None

        left_num, right_num = to_num(left), to_num(right)
        if op in ("gt", "gte", "lt", "lte"):
            if left_num is None or right_num is None:
                raise ValueError(f"运算符 {op} 需要可比较的数值, 左值={left!r} 右值={right!r}")
            return {
                "gt": left_num > right_num,
                "gte": left_num >= right_num,
                "lt": left_num < right_num,
                "lte": left_num <= right_num,
            }[op]
        # eq / ne: 数值可比按数值, 否则按文本(布尔统一为 true/false)
        if left_num is not None and right_num is not None:
            equal = left_num == right_num
        else:
            equal = to_text(left) == to_text(right)
        return equal if op == "eq" else not equal

    @staticmethod
    def _resolve_value(text: Any, ctx: dict[str, Any]) -> Any:
        """解析模板中的 {{node_id.path}} 引用

        - 整串仅一个引用且完全匹配时透传原对象(可为 dict/list/标量)
        - 否则做字符串插值(引用值非字符串时 JSON 序列化)
        - 引用节点未执行或路径未命中时报错
        """
        if not isinstance(text, str):
            return text
        matches = list(_VAR_PATTERN.finditer(text))
        if not matches:
            return text

        def lookup(ref_id: str, path: str) -> Any:
            if ref_id not in ctx:
                raise ValueError(f"引用的节点尚未执行: {ref_id}")
            value = ctx[ref_id]
            if path:
                for part in path.lstrip(".").split("."):
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        raise ValueError(f"节点 {ref_id} 输出中不存在字段路径: {path.lstrip('.')}")
            return value

        if len(matches) == 1 and matches[0].span() == (0, len(text)):
            return lookup(matches[0].group(1), matches[0].group(2))
        result = text
        for m in matches:
            value = lookup(m.group(1), m.group(2))
            replacement = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            result = result.replace(m.group(0), replacement)
        return result
