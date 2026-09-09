from langchain_core.messages import content
from pydantic import BaseModel, Field

class StreamOne(BaseModel):
    content: str = Field(..., description="模型返回的内容")
    node_name: str = Field(..., description="节点名称")