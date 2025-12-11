from enum import Enum
from pydantic import BaseModel, field_validator

class PaginationParams(BaseModel):
    """分页查询参数"""

    page: int = 1
    size: int = 10

    @property
    def offset(self):
        """分页偏移量"""
        return (self.page - 1) * self.size

    @property
    def limit(self):
        """每页最大记录数"""
        return self.size

    @field_validator("page")
    def validate_page(cls, v):
        """确保 page >= 1"""
        if v < 1:
            raise ValueError("page 必须大于等于 1")
        return v

    @field_validator("size")
    def validate_size(cls, v):
        """确保 size >= 1 且 <= 100(防止查询过大)"""
        if v < 1:
            raise ValueError("size 必须大于等于 1")
        if v > 100:
            raise ValueError("size 不能超过 100")
        return v


class PaginationResponse(BaseModel):
    """分页响应结构"""

    items: list  # 查询结果
    total: int  # 总记录数
    page: int  # 当前页码
    size: int  # 每页记录数
    pages: int  # 总页数

    @classmethod
    def create(cls, items: list, total: int, pagination: PaginationParams):
        return cls(
            items=items,
            total=total,  # 总记录数
            page=pagination.page,
            size=pagination.size,
            # 向下取整
            pages=(total + pagination.size - 1) // pagination.size,
        )


# #############################################滚动
class ScrollDirection(str, Enum):
    # 向上加载新
    UP = "up"
    DOWN = "down"


class InfiniteScrollParams(BaseModel):
    """无限滚动查询参数"""

    last_id: str | None = None  # 客户端最后获取的记录ID
    limit: int = 10  # 每次加载的数量
    direction: ScrollDirection = ScrollDirection.UP  # asc UP升序：从小到大，从早到晚  获取更新更晚更大的数据
    sort_by: str = "created_at"  # 排序字段，默认为创建时间


class InfiniteScrollResponse(BaseModel):
    """无限滚动响应结构"""

    items: list
    last_id: str | None = None
    has_more: bool

    @classmethod
    def create(
        cls, items: list, limit: int, direction: ScrollDirection = ScrollDirection.UP
    ):
        """
        创建无限滚动响应对象
        """
        # 1. 判断是否有更多数据(通过查询limit+1条来判断)
        has_more = len(items) > limit
        
        # 2. 截取实际要返回的数据(只返回limit条)
        items_result = items[:limit] if has_more else items
        
        # 3. 设置游标：根据方向确定使用第一条还是最后一条数据的ID
        if not items_result:
            last_id = None
        else:
            if direction == ScrollDirection.UP:
                # 升序：返回最后一条数据的ID(更大的值)
                last_id = items_result[-1].id
            else:
                # 降序：返回第一条数据的ID(更小的值)
                last_id = items_result[0].id
        
        return cls(
            items=items_result,
            last_id=last_id,
            has_more=has_more,
        )