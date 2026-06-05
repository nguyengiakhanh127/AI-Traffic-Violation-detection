import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
from infrastructure.database_service import ViolationRepository, CameraRepository, MongoConnection
from web.backend.auth import get_current_user, require_admin, TokenData

router = APIRouter()
v_repo = ViolationRepository()
c_repo = CameraRepository()

@router.get("/overview")
async def get_overview(current_user: TokenData = Depends(get_current_user)):
    """Thống kê tổng quan cho dashboard."""
    try:
        total     = v_repo.get_total_count()
        pending   = v_repo.get_total_count({"trang_thai": 0})
        approved  = v_repo.get_total_count({"trang_thai": 1})
        rejected  = v_repo.get_total_count({"trang_thai": -1})
        cameras   = len(c_repo.get_all())
        return {
            "total_violations": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "total_cameras": cameras,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/by-day")
async def get_by_day(
    days: int = 7,
    current_user: TokenData = Depends(get_current_user)
):
    """Vi phạm theo ngày — N ngày gần nhất."""
    try:
        db = MongoConnection.get_db()
        col = db["ho_so_vi_pham"]
        since = datetime.utcnow() - timedelta(days=days)

        pipeline = [
            {"$match": {"thoi_gian_vi_pham": {"$gte": since}}},
            {"$group": {
                "_id": {
                    "year":  {"$year":  "$thoi_gian_vi_pham"},
                    "month": {"$month": "$thoi_gian_vi_pham"},
                    "day":   {"$dayOfMonth": "$thoi_gian_vi_pham"},
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}}
        ]
        result = list(col.aggregate(pipeline))

        # Tạo đủ N ngày kể cả ngày không có vi phạm
        labels, counts = [], []
        for i in range(days - 1, -1, -1):
            day = datetime.utcnow() - timedelta(days=i)
            label = day.strftime("%d/%m")
            labels.append(label)
            matched = next(
                (r["count"] for r in result
                 if r["_id"]["day"] == day.day
                 and r["_id"]["month"] == day.month
                 and r["_id"]["year"] == day.year),
                0
            )
            counts.append(matched)

        return {"labels": labels, "counts": counts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/by-type")
async def get_by_type(current_user: TokenData = Depends(get_current_user)):
    """Phân loại vi phạm theo mã lỗi."""
    try:
        db = MongoConnection.get_db()
        col = db["ho_so_vi_pham"]
        pipeline = [
            {"$group": {"_id": "$ma_loi_vi_pham", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        result = list(col.aggregate(pipeline))
        labels = [r["_id"] or "Không rõ" for r in result]
        counts = [r["count"] for r in result]
        return {"labels": labels, "counts": counts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/by-vehicle")
async def get_by_vehicle(current_user: TokenData = Depends(get_current_user)):
    """Phân loại vi phạm theo loại phương tiện."""
    try:
        db = MongoConnection.get_db()
        col = db["ho_so_vi_pham"]
        pipeline = [
            {"$group": {"_id": "$loai_phuong_tien", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        result = list(col.aggregate(pipeline))
        labels = [r["_id"] or "Không rõ" for r in result]
        counts = [r["count"] for r in result]
        return {"labels": labels, "counts": counts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
