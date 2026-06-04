import os
import json
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from utils.enums import TrafficVehicleType, ViolationType
from core.rules import ViolationRegistry
from core.vehicle import Vehicle
from core.engine import ViolationEvent

# ==========================================
# 1. MODEL (Mô hình dữ liệu)
# ==========================================

@dataclass
class ViolationRecord:
    camera_name: str
    vehicle_id: int
    vehicle_type: str
    violation_code: str
    violation_desc: str
    timestamp: datetime  # Giữ nguyên object datetime gốc
    license_plate: str = "UNKNOWN" 

    def to_dict(self) -> dict:
        return {
            "camera_name": self.camera_name,
            "vehicle_id": self.vehicle_id,
            "vehicle_type": self.vehicle_type,
            "license_plate": self.license_plate,
            "violation_time": self.timestamp.strftime("%d/%m/%Y %H:%M:%S"),
            "violation_error": {
                "code": self.violation_code,
                "description": self.violation_desc
            }
        }

# ==========================================
# 2. EVIDENCE PATH BUILDER (Quản lý đường dẫn OS)
# ==========================================

class EvidencePathBuilder:
    """Chuyên trách việc tính toán đường dẫn và khởi tạo thư mục vật lý"""
    def __init__(self, root_dir: str = "evidence"):
        self.root_dir = root_dir

    def build_event_directory(self, record: ViolationRecord) -> str:
        """
        Cấu trúc: Root / Camera / YYYY_MM_DD / Lỗi / Loại_Xe / HHh_MMm_SSs_ms /
        """
        date_str = record.timestamp.strftime("%Y_%m_%d")
        event_time_str = record.timestamp.strftime("%Hh%Mm%Ss_%f")[:-3]
        
        event_path = os.path.join(
            self.root_dir, 
            record.camera_name, 
            date_str, 
            record.violation_code, 
            record.vehicle_type,
            event_time_str
        )
        
        if not os.path.exists(event_path):
            os.makedirs(event_path)
            
        return event_path

# ==========================================
# 3. STORAGE STRATEGIES (Chiến lược lưu trữ - Dependency Inversion)
# ==========================================

class IRecordStorage(ABC):
    """Interface (Hợp đồng) cho mọi phương pháp lưu trữ"""
    @abstractmethod
    def save(self, record: ViolationRecord, evidence_dir: str) -> None:
        pass

class JsonRecordStorage(IRecordStorage):
    """Cụ thể: Lưu metadata ra file json vào folder evidence"""
    def save(self, record: ViolationRecord, evidence_dir: str) -> None:
        json_filepath = os.path.join(evidence_dir, "metadata.json")
        try:
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(record.to_dict(), f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[LỖI] Không thể ghi JSON metadata: {e}")

# TODO: Sau này dễ dàng thêm DatabaseStorage(IRecordStorage) hoặc ApiStorage(IRecordStorage)


# ==========================================
# 4. MANAGER (Quản lý quy trình ghi nhận lỗi)
# ==========================================

class ViolationRecordManager:
    """Quản lý cache chống lặp lỗi và điều phối việc lưu trữ"""
    def __init__(
        self, 
        camera_name: str = "Camera_Default", 
        storage: Optional[IRecordStorage] = None,
        path_builder: Optional[EvidencePathBuilder] = None,
        max_ui_history: int = 100
    ):
        self.camera_name = camera_name
        
        # Tiêm phụ thuộc (Dependency Injection)
        self.storage = storage or JsonRecordStorage()
        self.path_builder = path_builder or EvidencePathBuilder()
        
        # [TỐI ƯU RAM]: Chỉ giữ N record mới nhất để trả về cho UI hiển thị
        self._recent_records: deque[ViolationRecord] = deque(maxlen=max_ui_history)
        
        # Cache chống báo lỗi liên tục (Mỗi xe chỉ bị phạt 1 lỗi/1 loại)
        self._logged_violations: Dict[int, set] = {}

    def log_violation(self, vehicle: Vehicle, event: ViolationEvent, current_time: datetime) -> Optional[ViolationRecord]:
        vehicle_id = vehicle.id
        violation_type = event.violation_type
        
        # 1. Kiểm tra Cache
        if vehicle_id not in self._logged_violations:
            self._logged_violations[vehicle_id] = set()
        if violation_type in self._logged_violations[vehicle_id]:
            return None # Đã ghi nhận lỗi này rồi, bỏ qua
        
        # 2. Tạo đối tượng Record
        record = ViolationRecord(
            camera_name=self.camera_name,
            vehicle_id=vehicle_id,
            vehicle_type=vehicle.vehicle_type.name,
            violation_code=event.error_name,
            violation_desc=event.description,
            timestamp=current_time
        )

        # 3. Tạo thư mục bằng chứng
        evidence_dir = self.path_builder.build_event_directory(record)

        # 4. Lưu trữ (Ủy quyền cho Storage Strategy)
        self.storage.save(record, evidence_dir)

        # 5. Cập nhật bộ nhớ đệm UI & Trạng thái
        self._recent_records.append(record)
        self._logged_violations[vehicle_id].add(violation_type)
        
        # Tiện ích: Trả về record VÀ thư mục để module bên ngoài có thể save Ảnh vào đó
        # (Vì Manager này không biết về ảnh, ảnh thuộc về Vehicle)
        return record, evidence_dir

    def clear_vehicle_cache(self, vehicle_id: int) -> None:
        """Gọi hàm này khi xe hoàn toàn biến mất khỏi khung hình"""
        if vehicle_id in self._logged_violations:
            del self._logged_violations[vehicle_id]

    def get_recent_records(self) -> List[ViolationRecord]:
        """Dùng cho giao diện PyQt6 cập nhật bảng (Table)"""
        return list(self._recent_records)