from pydantic import BaseModel, Field
from typing import Literal

############################################# 初步分块（文档转为多块markdown 带元数据）
class FileChunk(BaseModel):
    content:str 
    