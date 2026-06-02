from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json
import os
from utils.enums import TrafficVehicleType, ViolationType
from core.rules import ViolationRegistry
from core.vehicle import Vehicle
from core.engine import ViolationEvent

@dataclass
class ViolationRecord:
    camera_name: str
    vehicle_id: int
    vehicle_type: str
    violation_code: str
    violation_desc: str
    violation_time: str
    license_plate: str = "TODO" 

    def to_dict(self) -> dict:
        return {
            "camera_name": self.camera_name,
            "vehicle_id": self.vehicle_id,
            "vehicle_type": self.vehicle_type,
            "license_plate": self.license_plate,
            "violation_time": self.violation_time,
            "violation_error": {
                "code": self.violation_code,
                "description": self.violation_desc
            }
        }

class ViolationRecordManager:
    def __init__(self, camera_name: str = "Camera_Default", root_dir: str = "evidence"):
        self.camera_name = camera_name
        self.root_dir = root_dir
        self._records: List[ViolationRecord] = []
        self._logged_violations: Dict[int, set] = {}
        
        self._current_date_str: str = ""

    def log_violation(self, vehicle: Vehicle, event: ViolationEvent, current_time: datetime) -> Optional[ViolationRecord]:
        vehicle_id = vehicle.id
        violation_type = event.violation_type
        
        if vehicle_id not in self._logged_violations:
            self._logged_violations[vehicle_id] = set()

        if violation_type in self._logged_violations[vehicle_id]:
            return None
        
        formatted_time = current_time.strftime("%d/%m/%Y/%H:%M")

        record = ViolationRecord(
            camera_name=self.camera_name,
            vehicle_id=vehicle_id,
            vehicle_type=vehicle.vehicle_type.name,
            violation_code=event.error_name,
            violation_desc=event.description,
            violation_time=formatted_time
        )

        self._records.append(record)
        self._logged_violations[vehicle_id].add(violation_type)
        
        return record

    def clear_vehicle_cache(self, vehicle_id: int) -> None:
        if vehicle_id in self._logged_violations:
            del self._logged_violations[vehicle_id]

    def get_all_records(self) -> List[ViolationRecord]:
        return self._records

    def export_to_json(self, filepath: str) -> None:
        data = [record.to_dict() for record in self._records]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def get_evidence_directory(self, violation_code: str, vehicle_type_name: str, current_time: datetime) -> str:
        """
        [CẬP NHẬT: Cấu trúc Đóng gói Đồng bộ]
        Khởi tạo thư mục duy nhất chứa toàn bộ vòng đời của một sự kiện vi phạm.
        Cấu trúc: Root / Camera / YYYY_MM_DD / Lỗi / Loại_Xe / [HHh_MMm_SSs_ms] /
        Trả về đường dẫn thư mục sự kiện.
        """
        # Ngày hiện tại để tạo Folder cha
        date_str = current_time.strftime("%Y_%m_%d")
        
        # Cơ chế Rollover qua ngày
        if date_str != self._current_date_str:
            self._current_date_str = date_str
            
        # Thời gian sự kiện cụ thể để làm tên thư mục con (vd: 14h30m15s_123)
        event_time_str = current_time.strftime("%Hh%Mm%Ss_%f")[:-3]
        
        # Xây dựng đường dẫn trọn vẹn
        event_path = os.path.join(
            self.root_dir, 
            self.camera_name, 
            date_str, 
            violation_code, 
            vehicle_type_name,
            event_time_str  # Thư mục sự kiện đóng gói
        )
        
        # Khởi tạo thư mục vật lý nếu chưa có
        if not os.path.exists(event_path):
            os.makedirs(event_path)
            
        return event_path

    def export_single_record_json(self, record: ViolationRecord, folder_path: str) -> None:
        """
        [THÊM MỚI] Trích xuất riêng bản ghi JSON của sự kiện này và lưu vào cùng thư mục bằng chứng.
        """
        json_filepath = os.path.join(folder_path, "metadata.json")
        try:
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(record.to_dict(), f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"❌ Lỗi ghi file JSON metadata: {e}")