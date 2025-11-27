import asyncio
import json


class IndexService:
    def __init__(self):
        pass

    async def stream_get(self):
        for i in range(10):
            await asyncio.sleep(1)  # 模拟处理时间
            yield f"data: {json.dumps({'count': i, 'message': f'Item {i}'})}\n\n"
        yield "data: [DONE]\n\n"
        
    async def data_get(self):
        return {"message": "GET请求数据"}
    
    