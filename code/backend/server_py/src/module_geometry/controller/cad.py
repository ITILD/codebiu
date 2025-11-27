from fastapi import APIRouter, Depends
from service.cad import CadService
from dependencies.cad import get_cad_service

router = APIRouter()

@router.post("/bbox")
async def bbox(dwg: ezdxf.document.Drawing, cad_service: CadService = Depends(get_cad_service)):
    return await cad_service.bbox(dwg)

module_app.include_router(router, prefix="/cad", tags=["CAD"])

