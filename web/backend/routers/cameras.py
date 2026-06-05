import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from infrastructure.database_service import CameraRepository
from web.backend.auth import get_current_user, require_admin, TokenData

router = APIRouter()
repo = CameraRepository()

class CameraCreate(BaseModel):
    ten_camera: str
    tuyen_vao: Optional[str] = ""
    tuyen_ra: Optional[str] = ""

@router.get("")
async def list_cameras(current_user: TokenData = Depends(get_current_user)):
    """Lấy danh sách tất cả camera — Admin & Reviewer đều xem được."""
    try:
        return repo.get_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", status_code=201)
async def create_camera(body: CameraCreate, current_user: TokenData = Depends(require_admin)):
    """Thêm camera mới — chỉ Admin."""
    try:
        new_id = repo.add(body.ten_camera, body.tuyen_vao, body.tuyen_ra)
        return {"id": new_id, "ten_camera": body.ten_camera}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
