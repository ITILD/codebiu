from enum import StrEnum
from pydantic import BaseModel
from sqlmodel import Field,SQLModel


class BrowserType(StrEnum):
    """浏览器类型枚举"""

    CHROME = "chrome"
    FIREFOX = "firefox"
    EDGE = "msedge"


class SearchEngine(StrEnum):
    """搜索引擎枚举"""

    BAIDU = "baidu"
    GOOGLE = "google"
    BING = "bing"


# # 各搜索引擎配置 base_url https://www.google.com/search?q=   num   派出的关键字等
class HtmlSearchConfigBase(SQLModel):
    """搜索引擎配置模型"""

    engine: SearchEngine = Field(default=SearchEngine.BAIDU)
    base_url: str = Field(default="https://www.baidu.com/s?wd=")
    exclude_method: str = Field(
        default="-site:", description="排除的方法，默认排除csdn.net"
    )
    # 排除的网址数组
    exclude_url_list: list[str] = Field(
        default=["csdn.net"], description="排除的网址数组，默认排除csdn.net"
    )
    # 查询的selector
    elements_selector: str = Field(
        default="#content_left .result", description="查询的单个结果"
    )
    # 带url 标题的selector
    title_selector: str = Field(
        default="h3 a", description="标题的selector"
    )
    # 摘要的selector
    snippet_selector: str = Field(
        default="span.summary-text_560AW", description="摘要的selector"
    )


class SearchResult(BaseModel):
    title: str | None
    url: str | None
    # 摘要
    snippet: str | None
