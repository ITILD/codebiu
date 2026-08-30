import logging
from pathlib import Path
from typing import List
from module_office.config.server import module_app
from fastapi import APIRouter, HTTPException, status, Depends

logger = logging.getLogger(__name__)

router = APIRouter()

module_app.include_router(router, prefix="/document_chunk")
