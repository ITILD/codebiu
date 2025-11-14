
from pydantic import BaseModel
class Base64File(BaseModel):
    image_base64: str
    lang: str
    inpaint:bool = False