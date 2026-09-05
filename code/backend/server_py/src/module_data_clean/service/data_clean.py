import json
import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from module_data_clean.do.data_clean import DataCleanRequest, DataCleanResponse
from module_ai.service.llm_base import LLMBaseService

logger = logging.getLogger(__name__)

# 数据清洗系统提示词
SYSTEM_PROMPT = (
    "你是一名数据清洗助手, 负责根据用户给出的清洗提示词, "
    "对输入的数据(JSON 或文本)进行清洗、规范化与整理。\n"
    "要求:\n"
    "1. 严格遵循清洗提示词执行, 不要添加与清洗无关的内容;\n"
    "2. 保持数据语义不变, 仅修正格式、噪声、冗余与不一致;\n"
    "3. 输出只包含清洗结果, 不要输出解释或 Markdown 代码块标记。"
)


class DataCleanService:
    """数据清洗服务: 复用 module_ai 的 LLMBaseService, 按输出类型(json/string)返回清洗结果"""

    def __init__(self, llm_base_service: LLMBaseService):
        """依赖注入: 复用 LLM 基础服务"""
        self.llm_base_service = llm_base_service

    async def clean(self, request: DataCleanRequest) -> DataCleanResponse:
        """执行数据清洗"""
        llm: BaseChatModel | None = await self.llm_base_service.get_llm(
            request.model_id, streaming=False
        )
        if llm is None:
            raise ValueError("模型配置不存在或不可用")
        messages = self._build_messages(request)
        if request.output_type == "json":
            result = await self._clean_json(llm, messages, request.json_schema)
        else:
            result = await self._clean_string(llm, messages)
        return DataCleanResponse(result=result)

    @staticmethod
    def _build_messages(request: DataCleanRequest) -> list:
        """构造 LLM 消息: 系统角色 + 用户内容(数据/提示词/结构要求)"""
        data_text = (
            json.dumps(request.data, ensure_ascii=False, indent=2)
            if not isinstance(request.data, str)
            else request.data
        )
        user_content = [
            f"### 清洗提示词\n{request.prompt or '(无, 请仅做通用规范化)'}",
            f"### 待清洗数据\n{data_text}",
        ]
        if request.output_type == "json":
            if request.json_schema:
                schema_text = json.dumps(
                    request.json_schema, ensure_ascii=False, indent=2
                )
                user_content.append(
                    f"### 输出结构要求(必须严格遵循此 JSON Schema)\n{schema_text}"
                )
            else:
                user_content.append(
                    "### 输出结构要求\n输出合法的 JSON(对象或数组), 不要包含 Markdown 代码块标记。"
                )
        return [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content="\n\n".join(user_content)),
        ]

    @staticmethod
    async def _clean_string(llm: BaseChatModel, messages: list) -> str:
        """字符串输出: 直接返回模型文本结果"""
        response = await llm.ainvoke(messages)
        content = response.content
        return content if isinstance(content, str) else json.dumps(
            content, ensure_ascii=False
        )

    @classmethod
    async def _clean_json(cls, llm: BaseChatModel, messages: list, json_schema: dict | None):
        """JSON 输出: 优先结构化输出(严格按 Schema), 失败回退为提示词约束 + 解析"""
        if json_schema:
            try:
                structured_llm = llm.with_structured_output(json_schema)
                return await structured_llm.ainvoke(messages)
            except Exception as e:
                logger.warning(f"结构化输出失败, 回退提示词解析: {e}")
        response = await llm.ainvoke(messages)
        return cls._parse_json_content(response.content)

    @staticmethod
    def _parse_json_content(content) -> object:
        """从模型文本中解析 JSON(容忍 ```json 围栏与首尾杂质)"""
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
