from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
import json


class DataCleanRequest(BaseModel):
    """数据清洗请求模型

    - data: 待清洗数据, 可为 JSON 对象/数组或字符串(字符串会先尝试解析为 JSON)
    - prompt: 清洗提示词, 说明清洗规则与目标
    - output_type: 输出类型, json=结构化 JSON, string=纯字符串
    - json_schema: 输出 JSON 结构(JSON Schema), output_type=json 时提供可保证结构
    """

    model_id: str = Field(..., description="模型配置ID或模型标识名称")
    data: Any = Field(..., description="待清洗的数据(JSON对象/数组或字符串)")
    prompt: str = Field("", description="清洗提示词(说明清洗规则/目标)")
    output_type: Literal["json", "string"] = Field(
        "json", description="输出类型: json=结构化JSON, string=纯字符串"
    )
    json_schema: dict[str, Any] | None = Field(
        None, description="输出JSON结构(JSON Schema), output_type=json 时建议提供"
    )

    @field_validator("data", mode="before")
    @classmethod
    def parse_data(cls, v: Any) -> Any:
        """字符串入参时先尝试解析为 JSON, 解析失败则按原字符串处理"""
        if isinstance(v, str):
            try:
                return json.loads(v.strip())
            except (json.JSONDecodeError, ValueError):
                return v
        return v


class DataCleanResponse(BaseModel):
    """数据清洗响应模型"""

    result: Any = Field(
        ..., description="清洗结果: output_type=string 时为字符串, json 时为结构化对象"
    )
