from pydantic import BaseModel, Field, field_validator
from common.utils.code.language.lang2lang import Language


class Translate(BaseModel):
    model_id: str = Field(..., description="模型ID")
    content: str = Field(..., description="需要翻译的文本内容")
    lang: Language = Field(Language.EN, description="目标语言") 

