from fastapi import APIRouter, Depends, HTTPException

from module_data_clean.config.server import module_app
from module_data_clean.dependencies.data_clean import get_data_clean_service
from module_data_clean.do.data_clean import DataCleanRequest, DataCleanResponse
from module_data_clean.service.data_clean import DataCleanService

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", summary="LLM 数据清洗", response_model=DataCleanResponse)
async def clean(
    request: DataCleanRequest,
    data_clean_service: DataCleanService = Depends(get_data_clean_service),
) -> DataCleanResponse:
    """对输入数据(JSON 或字符串)按清洗提示词与输出类型(json 结构/字符串)进行清洗

    - **model_id**: 模型配置ID或模型标识名称(复用 module_ai 的模型配置)
    - **data**: 待清洗数据, 可为 JSON 对象/数组或字符串
    - **prompt**: 清洗提示词(说明清洗规则与目标)
    - **output_type**: 输出类型, json=结构化 JSON, string=纯字符串
    - **json_schema**: 输出 JSON 结构(JSON Schema), output_type=json 时提供可保证结构
    """
    try:
        return await data_clean_service.clean(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"数据清洗失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据清洗失败: {str(e)}")


module_app.include_router(router, prefix="/clean", tags=["数据清洗"])
