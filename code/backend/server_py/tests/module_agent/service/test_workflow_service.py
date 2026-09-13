# -*- coding: utf-8 -*-
"""module_agent/workflow 工作流执行引擎单测(纯逻辑, mock LLM)
覆盖: 图静态校验(开始/结束唯一/环检测/条件分支/引用存在性)/执行(直线流/变量插值/对象透传/
条件分支可达性/拓扑序合流/LLM节点/失败即终止携带轨迹)
"""

import pytest

from module_agent.do.agent import Agent
from module_agent.do.agent_run import AgentRunRequest
from module_agent.service.workflow import (
    TraceStatus,
    WorkflowExecuteError,
    WorkflowService,
    parse_json_content,
    validate_workflow,
)


# ---------------- 测试替身 ----------------

class _FakeResponse:
    def __init__(self, content):
        self.content = content


class _FakeLLM:
    """最小 LLM 替身(仅 ainvoke; with_structured_output 触发回退)"""

    def __init__(self, reply: str):
        self.reply = reply
        self.invoked_messages: list = []

    async def ainvoke(self, messages):
        self.invoked_messages = messages
        return _FakeResponse(self.reply)

    def with_structured_output(self, schema):
        raise RuntimeError("structured not supported")


class _FakeLLMService:
    """LLM 服务替身: 按配置返回固定回复"""

    def __init__(self, reply: str = "测试回复"):
        self.reply = reply
        self.requested_models: list[str] = []
        self.last_llm: _FakeLLM | None = None

    async def get_llm(self, model_id: str, streaming: bool = False):
        self.requested_models.append(model_id)
        self.last_llm = _FakeLLM(self.reply)
        return self.last_llm


def _make_agent(workflow: dict) -> Agent:
    """构造工作流智能体(不入库, 仅传参)"""
    return Agent(name="wf", system_prompt="你是测试智能体", agent_type="workflow", workflow=workflow)


def _node(nid: str, ntype: str, data: dict | None = None) -> dict:
    return {"id": nid, "type": ntype, "position": {"x": 0, "y": 0}, "data": data or {}}


def _edge(src: str, tgt: str, handle: str | None = None) -> dict:
    return {"id": f"{src}-{tgt}-{handle or ''}", "source": src, "target": tgt, "sourceHandle": handle}


def _graph(nodes: list[dict], edges: list[dict]) -> dict:
    return {"nodes": nodes, "edges": edges}


async def _run(svc: WorkflowService, graph: dict, input_data) -> tuple:
    return await svc.run_workflow(
        _make_agent(graph), AgentRunRequest(model_id="fake-model", input=input_data)
    )


# ---------------- validate_workflow ----------------

def test_validate_minimal_graph_ok():
    """最简合法图(开始→结束)校验通过"""
    errors = validate_workflow(_graph([_node("s", "start"), _node("e", "end")], [_edge("s", "e")]))
    assert errors == [], errors


def test_validate_missing_start_or_end():
    """缺少开始/结束节点应报错"""
    errors = validate_workflow(_graph([_node("a", "llm", {"prompt": "x"})], []))
    assert any("开始节点" in e for e in errors), errors
    assert any("结束节点" in e for e in errors), errors


def test_validate_duplicate_and_unknown_type():
    """节点ID重复/类型不合法应报错"""
    errors = validate_workflow(_graph([_node("s", "start"), _node("s", "end"), _node("x", "unknown")], []))
    assert any("重复" in e for e in errors), errors
    assert any("类型不合法" in e for e in errors), errors


def test_validate_cycle_detected():
    """循环连线应报错(一期仅支持 DAG)"""
    errors = validate_workflow(
        _graph(
            [
                _node("s", "start"),
                _node("c", "condition", {"left_source": "s", "operator": "eq", "right": "1"}),
                _node("e", "end"),
            ],
            [
                _edge("s", "c", "true"), _edge("s", "c", "false"),
                _edge("c", "e", "true"), _edge("c", "e", "false"),
                _edge("e", "c"),  # 回边成环
            ],
        )
    )
    assert any("循环" in e for e in errors), errors


def test_validate_condition_requires_branches():
    """条件节点缺 true/false 出边应报错"""
    errors = validate_workflow(
        _graph(
            [
                _node("s", "start"),
                _node("c", "condition", {"left_source": "s", "operator": "eq", "right": "1"}),
                _node("e", "end"),
            ],
            [_edge("s", "c"), _edge("c", "e", "true")],
        )
    )
    assert any("true 与 false" in e for e in errors), errors


def test_validate_condition_bad_source_and_operator():
    """条件节点左值来源不存在/运算符不合法应报错"""
    errors = validate_workflow(
        _graph(
            [
                _node("s", "start"),
                _node("c", "condition", {"left_source": "ghost", "operator": "approx", "right": "1"}),
                _node("e", "end"),
            ],
            [_edge("s", "c"), _edge("c", "e", "true"), _edge("c", "e", "false")],
        )
    )
    assert any("来源节点不存在" in e for e in errors), errors
    assert any("运算符不合法" in e for e in errors), errors


def test_validate_template_unknown_reference():
    """模板引用不存在的节点应报错"""
    errors = validate_workflow(
        _graph(
            [_node("s", "start"), _node("e", "end", {"result": "{{ghost.output}}"})],
            [_edge("s", "e")],
        )
    )
    assert any("ghost" in e for e in errors), errors


# ---------------- parse_json_content ----------------

def test_parse_json_content_fenced_json():
    """容忍 ```json 围栏"""
    assert parse_json_content('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_content_extract_from_noise():
    """从杂质文本中截取 JSON 主体"""
    assert parse_json_content('结果如下: {"a": [1, 2]} 以上。') == {"a": [1, 2]}


# ---------------- WorkflowService 执行 ----------------

@pytest.mark.asyncio
async def test_run_linear_template_flow():
    """直线流: 开始→模板(插值)→结束, 全程无需 LLM"""
    svc = WorkflowService(llm_service=_FakeLLMService())
    graph = _graph(
        [
            _node("s", "start"),
            _node("t", "template", {"template": "处理: {{s}}"}),
            _node("e", "end", {"result": "{{t}}"}),
        ],
        [_edge("s", "t"), _edge("t", "e")],
    )
    result, traces = await _run(svc, graph, "hello")
    assert result == "处理: hello"
    assert [t.status for t in traces] == [TraceStatus.SUCCESS.value] * 3
    assert all(t.duration_ms >= 0 for t in traces)


@pytest.mark.asyncio
async def test_run_end_object_passthrough():
    """结束节点整串单引用透传原对象(不做字符串化)"""
    svc = WorkflowService(llm_service=_FakeLLMService())
    graph = _graph(
        [_node("s", "start"), _node("e", "end", {"result": "{{s.data}}"})],
        [_edge("s", "e")],
    )
    result, _ = await _run(svc, graph, {"data": {"k": [1, 2]}, "score": 9})
    assert result == {"k": [1, 2]}


@pytest.mark.asyncio
async def test_run_condition_true_branch():
    """条件分支: 命中 true 分支, false 路径不执行"""
    svc = WorkflowService(llm_service=_FakeLLMService())
    graph = _graph(
        [
            _node("s", "start"),
            _node("c", "condition", {"left_source": "s", "left_path": "score",
                                     "operator": "gte", "right": "60"}),
            _node("ok", "template", {"template": "及格: {{s.score}}"}),
            _node("e", "end", {"result": "{{ok}}"}),
        ],
        [_edge("s", "c"), _edge("c", "ok", "true"), _edge("c", "e", "false"), _edge("ok", "e")],
    )
    result, traces = await _run(svc, graph, {"score": 88})
    assert result == "及格: 88"
    executed = {t.node_id for t in traces}
    assert executed == {"s", "c", "ok", "e"}, executed


@pytest.mark.asyncio
async def test_run_condition_false_branch_dead_path():
    """条件 false 分支: true 路径不执行; 结束节点引用未执行节点应报错"""
    svc = WorkflowService(llm_service=_FakeLLMService())
    graph = _graph(
        [
            _node("s", "start"),
            _node("c", "condition", {"left_source": "s", "operator": "eq", "right": "1"}),
            _node("t", "template", {"template": "命中"}),
            _node("e", "end", {"result": "{{t}}"}),
        ],
        [_edge("s", "c"), _edge("c", "t", "true"), _edge("c", "e", "false"), _edge("t", "e")],
    )
    with pytest.raises(WorkflowExecuteError) as exc_info:
        await _run(svc, graph, "2")  # 条件为 false, t 不可达
    failed = [t for t in exc_info.value.traces if t.status == TraceStatus.FAILED.value]
    assert len(failed) == 1 and failed[0].node_id == "e", exc_info.value.traces


@pytest.mark.asyncio
async def test_run_merge_topological_order():
    """合流: 两个上游分支按拓扑序先于汇点执行(引用两路输出)"""
    svc = WorkflowService(llm_service=_FakeLLMService())
    graph = _graph(
        [
            _node("s", "start"),
            _node("a", "template", {"template": "A{{s}}"}),
            _node("b", "template", {"template": "B{{s}}"}),
            _node("e", "end", {"result": "{{a}}-{{b}}"}),
        ],
        [_edge("s", "a"), _edge("s", "b"), _edge("a", "e"), _edge("b", "e")],
    )
    result, traces = await _run(svc, graph, "1")
    assert result == "A1-B1"
    assert {t.node_id for t in traces} == {"s", "a", "b", "e"}


@pytest.mark.asyncio
async def test_run_llm_node_with_model_fallback():
    """LLM 节点: prompt 插值 + 默认回退运行请求的 model_id; 结束节点默认取最后 LLM 输出"""
    fake_llm_service = _FakeLLMService(reply="模型结果")
    svc = WorkflowService(llm_service=fake_llm_service)
    graph = _graph(
        [
            _node("s", "start"),
            _node("n", "llm", {"prompt": "总结 {{s}}"}),
            _node("e", "end"),
        ],
        [_edge("s", "n"), _edge("n", "e")],
    )
    result, traces = await _run(svc, graph, "原始数据")
    assert result == "模型结果"  # 结束节点未配置 result, 取最后 LLM 节点输出
    assert fake_llm_service.requested_models == ["fake-model"]
    # 系统提示词取 agent.system_prompt, 用户消息为插值后的 prompt
    assert fake_llm_service.last_llm.invoked_messages[0].content == "你是测试智能体"
    assert fake_llm_service.last_llm.invoked_messages[1].content == "总结 原始数据"
    assert traces[-1].node_id == "e"


@pytest.mark.asyncio
async def test_run_llm_node_json_fallback_parse():
    """LLM 节点 json 输出: 结构化失败回退文本解析(容忍围栏)"""
    class _JsonReplyService(_FakeLLMService):
        async def get_llm(self, model_id: str, streaming: bool = False):
            llm = _FakeLLM('```json\n{"ok": true}\n```')
            self.last_llm = llm
            return llm

    svc = WorkflowService(llm_service=_JsonReplyService())
    graph = _graph(
        [
            _node("s", "start"),
            _node("n", "llm", {"prompt": "转JSON", "output_type": "json"}),
            _node("e", "end", {"result": "{{n.ok}}"}),
        ],
        [_edge("s", "n"), _edge("n", "e")],
    )
    result, _ = await _run(svc, graph, "x")
    assert result is True


@pytest.mark.asyncio
async def test_run_template_serializes_objects_inline():
    """混排插值: 非字符串引用值 JSON 序列化后内联"""
    svc = WorkflowService(llm_service=_FakeLLMService())
    graph = _graph(
        [
            _node("s", "start"),
            _node("t", "template", {"template": "清单 {{s.items}} 共 {{s.count}} 项"}),
            _node("e", "end", {"result": "{{t}}"}),
        ],
        [_edge("s", "t"), _edge("t", "e")],
    )
    result, _ = await _run(svc, graph, {"items": ["x", "y"], "count": 2})
    assert result == '清单 ["x", "y"] 共 2 项'


@pytest.mark.asyncio
async def test_run_node_failure_carries_traces():
    """节点失败即终止: 异常携带已完成轨迹, 失败节点记录 error"""
    svc = WorkflowService(llm_service=_FakeLLMService())
    graph = _graph(
        [
            _node("s", "start"),
            _node("t", "template", {"template": "引用未执行节点 {{ghost.x}}"}),
            _node("e", "end", {"result": "{{t}}"}),
        ],
        [_edge("s", "t"), _edge("t", "e")],
    )
    # ghost 未在图中(校验场景外直接构造运行时错误)
    with pytest.raises(WorkflowExecuteError) as exc_info:
        await _run(svc, graph, "hello")
    traces = exc_info.value.traces
    assert [t.status for t in traces] == [TraceStatus.SUCCESS.value, TraceStatus.FAILED.value]
    assert "ghost" in (traces[-1].error or "")
