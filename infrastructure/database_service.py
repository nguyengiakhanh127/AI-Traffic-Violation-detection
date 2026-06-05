# --- START OF FILE infrastructure/database_service.py ---

import os
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

from dotenv import load_dotenv
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure, PyMongoError
from bson import ObjectId

# Đọc biến môi trường từ file .env
load_dotenv()

logger = logging.getLogger("DatabaseService")

# ==========================================================
# 1. SINGLETON KẾT NỐI MONGODB
# ==========================================================

class MongoConnection:
    """Singleton quản lý MongoClient, tái sử dụng kết nối xuyên suốt app."""
    _client: Optional[MongoClient] = None
    _db = None

    @classmethod
    def get_db(cls):
        if cls._client is None:
            url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
            db_name = os.getenv("DATABASE_NAME", "traffic_violation")
            try:
                cls._client = MongoClient(url, serverSelectionTimeoutMS=10000)
                cls._client.admin.command("ping")  # Kiểm tra kết nối ngay
                cls._db = cls._client[db_name]
                logger.info(f"✅ Kết nối MongoDB thành công: {db_name}")
            except ConnectionFailure as e:
                logger.error(f"❌ Không thể kết nối tới MongoDB: {e}")
                raise e
        return cls._db

    @classmethod
    def close(cls):
        if cls._client:
            cls._client.close()
            cls._client = None
            cls._db = None


def _to_str_id(doc: dict) -> dict:
    """Chuyển ObjectId thành str để tương thích với GUI hiện tại."""
    if doc is None:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    if "camera_id" in doc and isinstance(doc["camera_id"], ObjectId):
        doc["camera_id"] = str(doc["camera_id"])
    return doc


# ==========================================================
# 2. REPOSITORIES
# ==========================================================

class CameraRepository:
    COLLECTION = "danh_muc_camera"

    def get_collection(self):
        return MongoConnection.get_db()[self.COLLECTION]

    def add(self, ten_camera: str, tuyen_vao: str = "", tuyen_ra: str = "") -> str:
        """Thêm camera mới. Nếu đã tồn tại thì trả về id cũ."""
        col = self.get_collection()
        existing = col.find_one({"ten_camera": ten_camera})
        if existing:
            return str(existing["_id"])

        result = col.insert_one({
            "ten_camera": ten_camera,
            "link_rtsp": "",
            "duong_dan_cau_hinh": "",
            "tuyen_duong_vao": tuyen_vao,
            "tuyen_duong_ra": tuyen_ra
        })
        return str(result.inserted_id)

    def get_all(self) -> List[Dict]:
        col = self.get_collection()
        docs = col.find().sort("ten_camera", 1)
        return [_to_str_id(d) for d in docs]

    def update_config_path(self, camera_id: str, file_path: str) -> bool:
        col = self.get_collection()
        try:
            result = col.update_one(
                {"_id": ObjectId(camera_id)},
                {"$set": {"duong_dan_cau_hinh": file_path}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ Lỗi update_config_path: {e}")
            return False


class ViolationRepository:
    COLLECTION = "ho_so_vi_pham"

    def get_collection(self):
        return MongoConnection.get_db()[self.COLLECTION]

    def insert(self, camera_id: str, thoi_gian: str, ma_loi: str, loai_xe: str,
               lan_duong: str, duong_dan: str, bien_so: str = "Chưa rõ") -> str:
        col = self.get_collection()
        # Chuyển thoi_gian sang datetime object nếu là string
        if isinstance(thoi_gian, str):
            try:
                thoi_gian_dt = datetime.strptime(thoi_gian, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                thoi_gian_dt = datetime.now()
        else:
            thoi_gian_dt = thoi_gian

        doc = {
            "camera_id": camera_id,
            "thoi_gian_vi_pham": thoi_gian_dt,
            "ma_loi_vi_pham": ma_loi,
            "loai_phuong_tien": loai_xe,
            "lan_duong": lan_duong,
            "bien_so_xe": bien_so,
            "duong_dan_bang_chung": duong_dan,
            "trang_thai_duyet": 0
        }
        result = col.insert_one(doc)
        return str(result.inserted_id)

    def update_status(self, record_id: str, trang_thai: int) -> bool:
        col = self.get_collection()
        try:
            result = col.update_one(
                {"_id": ObjectId(record_id)},
                {"$set": {"trang_thai_duyet": trang_thai}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ Lỗi update_status: {e}")
            return False

    def get_list(self, limit: int = 20, offset: int = 0, filters: dict = None) -> List[Dict]:
        col = self.get_collection()
        cam_col = MongoConnection.get_db()[CameraRepository.COLLECTION]

        query = self._build_query(filters)

        docs = list(
            col.find(query)
               .sort("thoi_gian_vi_pham", DESCENDING)
               .skip(offset)
               .limit(limit)
        )

        # Thêm tên camera vào từng record (tương đương LEFT JOIN)
        result = []
        for doc in docs:
            doc = _to_str_id(doc)
            cam = cam_col.find_one({"_id": ObjectId(doc["camera_id"])}) if doc.get("camera_id") else None
            doc["ten_camera"] = cam["ten_camera"] if cam else "Không rõ"
            # Chuẩn hoá timestamp thành string cho GUI
            if isinstance(doc.get("thoi_gian_vi_pham"), datetime):
                doc["thoi_gian_vi_pham"] = doc["thoi_gian_vi_pham"].strftime("%Y-%m-%d %H:%M:%S")
            result.append(doc)

        return result

    def get_total_count(self, filters: dict = None) -> int:
        col = self.get_collection()
        query = self._build_query(filters)
        try:
            return col.count_documents(query)
        except Exception as e:
            logger.error(f"❌ Lỗi đếm tổng DB: {e}")
            return 0

    def update_license_plate(self, record_id: str, bien_so: str) -> bool:
        col = self.get_collection()
        try:
            result = col.update_one(
                {"_id": ObjectId(record_id)},
                {"$set": {"bien_so_xe": bien_so}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ Lỗi update_license_plate: {e}")
            return False

    def _build_query(self, filters: dict) -> dict:
        """Xây dựng MongoDB query từ dict filter (tương đương WHERE clause SQL)."""
        query = {}
        if not filters:
            return query

        if filters.get("bien_so"):
            query["bien_so_xe"] = {"$regex": filters["bien_so"], "$options": "i"}
        if filters.get("ma_loi"):
            query["ma_loi_vi_pham"] = filters["ma_loi"]
        if filters.get("loai_xe"):
            query["loai_phuong_tien"] = filters["loai_xe"]
        if filters.get("trang_thai") is not None:
            query["trang_thai_duyet"] = filters["trang_thai"]
        if filters.get("start_time"):
            query.setdefault("thoi_gian_vi_pham", {})["$gte"] = filters["start_time"]
        if filters.get("end_time"):
            query.setdefault("thoi_gian_vi_pham", {})["$lte"] = filters["end_time"]

        return query


# ==========================================================
# 3. FACADE SERVICE (Giao tiếp bên ngoài - giữ nguyên API)
# ==========================================================

class DatabaseService:
    """
    Facade giữ nguyên interface cũ để các module khác (GUI, services)
    không cần sửa đổi cách gọi.
    """
    def __init__(self):
        try:
            MongoConnection.get_db()  # Khởi tạo kết nối sớm để báo lỗi ngay
        except Exception as e:
            logger.error(f"❌ DatabaseService không thể khởi tạo: {e}")

        self.cameras = CameraRepository()
        self.violations = ViolationRepository()

    # ---- Các method tiện ích dùng ở main_window.py ----

    def get_total_count(self) -> int:
        """Đếm tổng số vi phạm (dùng để kiểm tra trước khi seed data)."""
        return self.violations.get_total_count()

    def add_camera(self, ten_camera: str, tuyen_vao: str = "", tuyen_ra: str = "") -> str:
        return self.cameras.add(ten_camera, tuyen_vao, tuyen_ra)

    def insert_violation(self, data: dict) -> str:
        """
        Wrapper nhận dict tổng hợp — tương thích với _seed_fake_data() ở main_window.
        data keys: camera_id, timestamp, violation_code, vehicle_type, lane_id,
                   license_plate, evidence_path
        """
        return self.violations.insert(
            camera_id=data.get("camera_id", ""),
            thoi_gian=data.get("timestamp", ""),
            ma_loi=data.get("violation_code", ""),
            loai_xe=data.get("vehicle_type", ""),
            lan_duong=data.get("lane_id", ""),
            duong_dan=data.get("evidence_path", ""),
            bien_so=data.get("license_plate", "Chưa rõ")
        )

    def update_violation_status(self, record_id: str, new_status: int) -> bool:
        return self.violations.update_status(record_id, new_status)
