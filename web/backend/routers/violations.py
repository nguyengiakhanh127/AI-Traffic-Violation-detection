import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from infrastructure.database_service import ViolationRepository, MongoConnection
from web.backend.auth import get_current_user, TokenData
from bson import ObjectId

router = APIRouter()
repo = ViolationRepository()

# Thư mục gốc chứa bằng chứng
EVIDENCE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "Evidence")
)

class StatusUpdate(BaseModel):
    trang_thai: int  # 1 = duyệt, -1 = từ chối, 0 = chờ

class LicensePlateUpdate(BaseModel):
    bien_so: str

@router.get("")
async def list_violations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    bien_so: Optional[str] = None,
    ma_loi: Optional[str] = None,
    loai_xe: Optional[str] = None,
    trang_thai: Optional[int] = None,
    current_user: TokenData = Depends(get_current_user)
):
    """Danh sách vi phạm với filter & phân trang."""
    filters = {}
    if bien_so:    filters["bien_so"] = bien_so
    if ma_loi:     filters["ma_loi"] = ma_loi
    if loai_xe:    filters["loai_xe"] = loai_xe
    if trang_thai is not None: filters["trang_thai"] = trang_thai
    try:
        data = repo.get_list(limit=limit, offset=offset, filters=filters)
        total = repo.get_total_count(filters=filters)
        return {"data": data, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/count")
async def count_violations(
    trang_thai: Optional[int] = None,
    current_user: TokenData = Depends(get_current_user)
):
    filters = {}
    if trang_thai is not None:
        filters["trang_thai"] = trang_thai
    return {"count": repo.get_total_count(filters=filters)}

@router.get("/{record_id}/evidence")
async def get_evidence_files(
    record_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Trả về danh sách file bằng chứng (ảnh, video) của một vi phạm."""
    try:
        db = MongoConnection.get_db()
        doc = db["ho_so_vi_pham"].find_one({"_id": ObjectId(record_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi")

        raw_path = doc.get("duong_dan_bang_chung", "")
        if not raw_path:
            return {"files": [], "folder": ""}

        # Chuẩn hoá: bỏ prefix 'evidence/' hoặc 'Evidence/'
        clean_rel = re.sub(r'^[Ee]vidence[/\\]', '', raw_path.replace("\\", "/"))
        folder_abs = os.path.join(EVIDENCE_ROOT, clean_rel.replace("/", os.sep))

        if not os.path.isdir(folder_abs):
            return {"files": [], "folder": clean_rel, "error": "Thu muc bang chung khong ton tai"}

        files = []
        for fname in sorted(os.listdir(folder_abs)):
            fpath = os.path.join(folder_abs, fname)
            if os.path.isfile(fpath):
                ext = fname.lower().rsplit(".", 1)[-1]
                ftype = "image" if ext in ("jpg", "jpeg", "png") else "video" if ext == "mp4" else "other"
                # Build URL: encode mỗi segment riêng để giữ dấu /
                url = "/evidence/" + "/".join(
                    p.replace(" ", "%20") for p in clean_rel.split("/")
                ) + "/" + fname.replace(" ", "%20")
                files.append({"name": fname, "type": ftype, "url": url})

        return {"files": files, "folder": clean_rel}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{record_id}/status")
async def update_status(
    record_id: str,
    body: StatusUpdate,
    current_user: TokenData = Depends(get_current_user)
):
    """Duyệt hoặc từ chối vi phạm — Admin & Reviewer."""
    success = repo.update_status(record_id, body.trang_thai)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi")
    return {"success": True, "record_id": record_id, "trang_thai": body.trang_thai}

@router.patch("/{record_id}/license-plate")
async def update_license_plate(
    record_id: str,
    body: LicensePlateUpdate,
    current_user: TokenData = Depends(get_current_user)
):
    """Cập nhật biển số thủ công."""
    success = repo.update_license_plate(record_id, body.bien_so)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi")
    return {"success": True, "bien_so": body.bien_so}

@router.delete("/{record_id}")
async def delete_violation(
    record_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Xóa bản ghi vi phạm."""
    success = repo.delete(record_id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi")
    return {"success": True, "record_id": record_id}
