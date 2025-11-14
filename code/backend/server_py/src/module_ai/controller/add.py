from module_ai.config.server import module_app

from module_ai.service.add import add


from fastapi import APIRouter, HTTPException, status, Depends
router = APIRouter()

@router.get(
    "", summary="创建模板", status_code=status.HTTP_201_CREATED, response_model=str
)
async def add(a: int, b: int) -> int:
    return add(a, b)
    
module_app.include_router(router, prefix="/add", tags=["加法"])